# connector.py
import logging
from typing import List, Dict, Any, Tuple

from file_storage import StorageManager
from info_sum import summarize_text

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

storage = StorageManager(base_dir="data", reset_db_on_start=False)


# ---------- NEW: strict validator ----------
def _is_valid_summary(text: str) -> bool:
    """
    Reject model garbage outputs.
    """
    if not text:
        return False

    t = text.strip().lower()

    if t in [
        "",
        "none",
        "no summary generated",
        "no content was found",
        "[no summary generated]",
        "null",
    ]:
        return False

    if len(t) < 20:  # too short to be real summary
        return False

    return True


def _make_provenance_chunk_text(chunks: List[Dict[str, Any]]) -> List[str]:
    out = []
    for ch in chunks:
        meta = ch.get("meta", {}) or {}
        source = meta.get("source", "unknown")
        page = meta.get("page")
        chunk_idx = meta.get("chunk_idx", ch.get("chunk_idx"))

        header = f"SOURCE: {source} | page: {page if page is not None else 'unknown'} | chunk: {chunk_idx}"

        content = ch.get("text") or ""

        out.append(header + "\nCONTENT:\n" + content.strip())

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
    if not texts:
        return "", []
    batches = _batch_texts_by_words(texts, max_words=batch_words)
    batch_summaries: List[str] = []

    # -------- Batch summarize --------
    for i, b in enumerate(batches):
        try:
            logger.info("Summarizing internal batch %d/%d", i + 1, len(batches))

            logger.info(
                "BATCH PREVIEW (%d chars): %s",
                len(b),
                b[:500].replace("\n", " "),
            )

            s = summarize_text(
                b,
                output_format=output_format,
                max_tokens=2000,
                temperature=temperature,
            )

            logger.info("RAW MODEL OUTPUT: %r", s)
            if not _is_valid_summary(s):
                logger.warning(
                    "Invalid summary rejected for batch %d", i
                )
                continue
            batch_summaries.append(s.strip())
        except Exception as e:

            logger.exception(
                "summarize_text failed for batch %d: %s", i, e
            )

    # -------- If nothing valid, STOP --------
    if not batch_summaries:
        logger.error("ALL batch summaries invalid")
        return "", []

    # -------- Hierarchical final --------
    if hierarchical_final and len(batch_summaries) > 1:
        combined = "\n\n".join(batch_summaries)
        if not target_words:
            total_words = sum(len(t.split()) for t in texts)
            target_words = max(150, int(total_words * 0.12))

        tokens = min(int(target_words * 1.33), max_tokens_cap)

        try:
            logger.info(
                "Running hierarchical final summarize: target_words=%d tokens=%d",
                target_words,
                tokens,
            )

            final = summarize_text(
                combined,
                output_format=output_format,
                max_tokens=tokens,
                temperature=temperature,
                target_words=target_words,
            )

            logger.info("FINAL MODEL OUTPUT: %r", final)
            
            if _is_valid_summary(final):
                return final.strip(), batch_summaries
            else:
                logger.warning(
                    "Final summary invalid, using batch concatenation"
                )

        except Exception as e:
            logger.exception("final summarize failed: %s", e)

    # fallback safe return
    return "\n\n".join(batch_summaries), batch_summaries

# ---------- FILE summarize ----------
def summarize_file(
    file_id: int,
    *,
    output_format="latex",
    batch_words=1200,
    hierarchical=True,
    target_ratio=0.12,
):

    file_meta = storage.get_file_by_id(file_id)
    
    if not file_meta:
        raise ValueError("file not found")

    chunks = storage.query_chunks_by_file(file_id)

    if not chunks:
        return {"file_id": file_id, "summary": "", "note": "no chunks"}

    prov = _make_provenance_chunk_text(chunks)

    total_words = sum(len(t.split()) for t in prov)

    target_words = max(150, int(total_words * target_ratio))

    final, batch = summarize_large_text(
        prov,
        output_format=output_format,
        batch_words=batch_words,
        hierarchical_final=hierarchical,
        target_words=target_words,
    )

    summary_id = storage.save_summary(file_id, final)

    return {
        "file_id": file_id,
        "summary_id": summary_id,
        "summary": final,
        "batches": len(batch),
    }

# ---------- MULTI FILE ----------
def summarize_multiple_files(
    file_ids,
    *,
    output_format="latex",
    batch_words=1200,
    hierarchical=True,
    target_ratio=0.12,
):
    per = []

    for fid in file_ids:
        per.append(
            summarize_file(
                fid,
                output_format=output_format,
                batch_words=batch_words,
                hierarchical=hierarchical,
                target_ratio=target_ratio,
            )
        )

    combined_parts = []

    for f in per:
        meta = storage.get_file_by_id(f["file_id"]) or {}
        name = meta.get("original_name", f"file_{f['file_id']}")
        summary = f.get("summary") or ""

        if _is_valid_summary(summary):
            combined_parts.append(
                f"=== DOCUMENT: {name} ===\n\n{summary}"
            )

    if not combined_parts:
        return {"per_file": per, "combined": {"summary": ""}}

    combined_final, _ = summarize_large_text(
        combined_parts,
        output_format=output_format,
        batch_words=batch_words,
        hierarchical_final=hierarchical,
    )

    combined_id = storage.save_summary(None, combined_final)

    return {
        "per_file": per,
        "combined": {
            "summary_id": combined_id,
            "summary": combined_final,
        },
    }
    