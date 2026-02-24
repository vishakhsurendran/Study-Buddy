# connector.py
import logging
from typing import List, Dict, Any, Tuple
import time

from file_storage import StorageManager
from info_sum import summarize_text

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

storage = StorageManager(base_dir="data", reset_db_on_start=False)


def _make_provenance_chunk_text(chunks: List[Dict[str, Any]]) -> List[str]:
    out = []
    for ch in chunks:
        meta = ch.get("meta", {}) or {}
        source = meta.get("source", "unknown")
        page = meta.get("page")
        chunk_idx = meta.get("chunk_idx", ch.get("chunk_idx"))
        header = f"SOURCE: {source} | page: {page if page is not None else 'unknown'} | chunk: {chunk_idx}"
        out.append(header + "\n" + ch["text"])
    return out


def _batch_texts_by_words(texts: List[str], max_words: int = 1200) -> List[str]:
    batches = []
    cur = []
    curw = 0
    for t in texts:
        w = len(t.split())
        if curw + w <= max_words or not cur:
            cur.append(t)
            curw += w
        else:
            batches.append("\n\n".join(cur))
            cur = [t]
            curw = w
    if cur:
        batches.append("\n\n".join(cur))
    return batches


def summarize_large_text(
    texts: List[str],
    *,
    output_format: str = "latex",
    batch_words: int = 1200,
    hierarchical_final: bool = True,
    max_tokens_cap: int = 16000,
    temperature: float = 0.2,
    target_words: int = None
) -> Tuple[str, List[str]]:
    """
    Summarize a list of provenance-prefixed chunk strings.
    Returns (final_summary, batch_summaries_list).
    """

    if not texts:
        return "", []

    # --- 1) Basic batching for safe model calls ---
    batches = _batch_texts_by_words(texts, max_words=batch_words)
    batch_summaries: List[str] = []

    for i, b in enumerate(batches):
        try:
            logger.info("Summarizing internal batch %d/%d", i + 1, len(batches))
            # for internal batches use a moderate token budget
            s = summarize_text(b, output_format=output_format, max_tokens=2000, temperature=temperature)
            batch_summaries.append(s)
        except Exception as e:
            logger.exception("summarize_text failed for internal batch %d: %s", i, e)
            batch_summaries.append(f"[ERROR in internal batch {i}: {e}]")

    # --- 2) Final hierarchical pass with target sizing if requested ---
    if hierarchical_final and len(batch_summaries) > 0:
        combined_for_final = "\n\n".join(batch_summaries)

        # If target_words not provided, try to infer from input size (words across 'texts') and use ratio
        if not target_words:
            total_words = sum(len(t.split()) for t in texts)
            # default ratio 12% if not passed by caller; caller can set
            # (caller of summarize_file/summarize_multiple_files will normally pass a target_ratio)
            # but we keep a fallback ratio here.
            target_ratio = 0.12
            target_words = max(150, int(total_words * target_ratio))

        # Convert target_words to tokens: approx tokens = target_words * 1.33
        # Step-by-step: tokens ≈ target_words * (1 / 0.75) ≈ target_words * 1.333...
        tokens = int(target_words * 1.33)
        if tokens > max_tokens_cap:
            tokens = max_tokens_cap

        try:
            logger.info(
                "Running hierarchical final summarize: target_words=%d, tokens=%d", target_words, tokens
            )
            final = summarize_text(
                combined_for_final,
                output_format=output_format,
                max_tokens=tokens,
                temperature=temperature,
                target_words=target_words,
            )
        except Exception as e:
            logger.exception("final hierarchical summarize failed: %s", e)
            final = combined_for_final
    else:
        final = "\n\n".join(batch_summaries)

    return final, batch_summaries


def summarize_file(file_id: int, *, output_format: str = "latex", batch_words: int = 1200, hierarchical: bool = True, target_ratio: float = 0.12) -> Dict[str, Any]:
    """
    Summarize one file with output_format='latex' by default.
    target_ratio: fraction of total words to aim for (0.10–0.15 recommended)
    """
    file_meta = storage.get_file_by_id(file_id)
    if not file_meta:
        raise ValueError("file not found")

    chunks = storage.query_chunks_by_file(file_id)
    if not chunks:
        return {"file_id": file_id, "summary": "", "note": "no chunks"}

    prov_texts = _make_provenance_chunk_text(chunks)

    # compute total words to pass a target_words to summarize_large_text
    total_words = sum(len(t.split()) for t in prov_texts)
    target_words = max(150, int(total_words * target_ratio))

    final, batch_summaries = summarize_large_text(
        prov_texts,
        output_format=output_format,
        batch_words=batch_words,
        hierarchical_final=hierarchical,
        target_words=target_words,
    )

    summary_id = storage.save_summary(file_id, final)
    return {"file_id": file_id, "summary_id": summary_id, "summary": final, "batches": len(batch_summaries)}


def summarize_multiple_files(file_ids: List[int], *, output_format: str = "latex", batch_words: int = 1200, hierarchical: bool = True, target_ratio: float = 0.12) -> Dict[str, Any]:
    per_file = []
    for fid in file_ids:
        res = summarize_file(fid, output_format=output_format, batch_words=batch_words, hierarchical=hierarchical, target_ratio=target_ratio)
        per_file.append(res)

    combined_text_parts = []
    for f in per_file:
        file_meta = storage.get_file_by_id(f["file_id"]) or {}
        name = file_meta.get("original_name", f"file_{f['file_id']}")
        combined_text_parts.append(f"=== DOCUMENT: {name} ===\n\n{f['summary']}")

    combined_final, _ = summarize_large_text(
        combined_text_parts,
        output_format=output_format,
        batch_words=batch_words,
        hierarchical_final=hierarchical,
        # estimate combined target words as sum of file targets (approx)
        target_words=int(sum(max(150, int(len(p.split()) * target_ratio)) for p in combined_text_parts))
    )

    combined_summary_id = storage.save_summary(None if not file_ids else file_ids[0], combined_final)
    return {"per_file": per_file, "combined": {"summary_id": combined_summary_id, "summary": combined_final}}
