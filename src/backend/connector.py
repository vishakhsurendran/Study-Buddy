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
    """Batch list of texts into strings where each batch is approximately <= max_words words."""
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
    output_format: str = "markdown",
    batch_words: int = 1200,
    hierarchical_final: bool = True,
    max_tokens: int = 1500,
    temperature: float = 0.2
) -> Tuple[str, List[str]]:
    """
    Summarize a (potentially large) list of provenance-prefixed chunk strings.
    Returns (final_summary, batch_summaries_list).
    - texts: list[str], each element is "SOURCE: ...\\n<chunk text>"
    - batch_words: approximate words per batch
    - hierarchical_final: whether to run a final summarize on concatenated batch summaries
    """
    if not texts:
        return "", []

    batches = _batch_texts_by_words(texts, max_words=batch_words)
    batch_summaries: List[str] = []

    for i, b in enumerate(batches):
        try:
            logger.info("Summarizing internal batch %d/%d", i + 1, len(batches))
            s = summarize_text(b, output_format=output_format, max_tokens=max_tokens, temperature=temperature)
            batch_summaries.append(s)
        except Exception as e:
            logger.exception("summarize_text failed for internal batch %d: %s", i, e)
            batch_summaries.append(f"[ERROR in internal batch {i}: {e}]")

    if hierarchical_final and len(batch_summaries) > 1:
        combined_for_final = "\n\n".join(batch_summaries)
        try:
            logger.info("Running hierarchical final summarize on %d batch summaries", len(batch_summaries))
            final = summarize_text(combined_for_final, output_format=output_format, max_tokens=max_tokens, temperature=temperature)
        except Exception as e:
            logger.exception("final hierarchical summarize failed: %s", e)
            final = combined_for_final 
    else:
        final = "\n\n".join(batch_summaries)

    return final, batch_summaries


def summarize_file(file_id: int, *, output_format: str = "markdown", batch_words: int = 1200, hierarchical: bool = True) -> Dict[str, Any]:
    file_meta = storage.get_file_by_id(file_id)
    if not file_meta:
        raise ValueError("file not found")

    chunks = storage.query_chunks_by_file(file_id)
    if not chunks:
        return {"file_id": file_id, "summary": "", "note": "no chunks"}

    prov_texts = _make_provenance_chunk_text(chunks)

    # Use summarize_large_text to safely handle large input
    final, batch_summaries = summarize_large_text(
        prov_texts,
        output_format=output_format,
        batch_words=batch_words,
        hierarchical_final=hierarchical
    )

    summary_id = storage.save_summary(file_id, final)

    return {"file_id": file_id, "summary_id": summary_id, "summary": final, "batches": len(batch_summaries)}


def summarize_multiple_files(file_ids: List[int], *, output_format: str = "markdown", batch_words: int = 1200, hierarchical: bool = True) -> Dict[str, Any]:
    per_file = []
    for fid in file_ids:
        res = summarize_file(fid, output_format=output_format, batch_words=batch_words, hierarchical=hierarchical)
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
        hierarchical_final=hierarchical
    )

    combined_summary_id = storage.save_summary(None if not file_ids else file_ids[0], combined_final)

    return {"per_file": per_file, "combined": {"summary_id": combined_summary_id, "summary": combined_final}}
