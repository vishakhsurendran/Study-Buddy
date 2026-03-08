# connector.py
import logging
from typing import List, Dict, Any, Tuple
import time
from pathlib import Path
import math

from file_storage import StorageManager
from info_sum import summarize_text
from export_utils import write_latex, try_make_pdf_from_latex

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Use the same base_dir as the rest of your app (make sure server mounts the same dir)
storage = StorageManager(base_dir="data", reset_db_on_start=False)


def _make_provenance_chunk_text(chunks: List[Dict[str, Any]]) -> str:
    """
    Turn a list of chunk dicts into a provenance-rich string for the LLM.
    Each chunk dict is expected to have keys: text, meta (with page, source etc).
    """
    out_parts = []
    for ch in chunks:
        meta = ch.get("meta", {}) or {}
        source = meta.get("source", "unknown")
        page = meta.get("page")
        excerpt = meta.get("excerpt", "")
        header = f"--- SOURCE: {source}"
        if page:
            header += f" | page: {page}"
        if excerpt:
            header += f" | excerpt: {excerpt[:120].replace('\\n',' ')}"
        out_parts.append(f"{header}\nCONTENT:\n{ch.get('text','')}")
    return "\n\n".join(out_parts)


def _batch_texts_by_words(texts: List[str], max_words_per_batch: int) -> List[List[str]]:
    """
    Batch a list of texts (strings) into batches of approx max_words_per_batch.
    Returns list of batches, each batch is a list of texts joined later.
    """
    batches = []
    cur = []
    cur_words = 0
    for t in texts:
        w = len(t.split())
        if cur and (cur_words + w > max_words_per_batch):
            batches.append(cur)
            cur = [t]
            cur_words = w
        else:
            cur.append(t)
            cur_words += w
    if cur:
        batches.append(cur)
    return batches


def summarize_large_text(chunks_provenance_texts: List[str], *, output_format: str = "latex",
                         batch_words: int = 1200, hierarchical_final: bool = True, target_words: int = 800) -> Tuple[str, Dict[str, Any]]:
    """
    Accepts a list of provenance-rich strings (one per file or per chunk-group).
    If the input is large, summarize in batches then optionally do a hierarchical final merge.
    Returns (final_summary_text, debug_info)
    """
    # flatten input texts to list of strings
    texts = [t for t in chunks_provenance_texts if t and t.strip()]
    if not texts:
        return "", {"steps": []}

    # Split into batches by words
    batches = _batch_texts_by_words(texts, batch_words)
    batch_summaries = []
    debug = {"batches": len(batches), "batch_sizes": [len(b) for b in batches], "steps": []}

    for i, b in enumerate(batches):
        joined = "\n\n".join(b)
        # ask model to summarize this batch
        summ = summarize_text(joined, output_format=output_format, max_tokens=2000, temperature=0.2)
        batch_summaries.append(summ)
        debug["steps"].append({"batch": i, "words_in_batch": sum(len(x.split()) for x in b), "summary_words": len(summ.split())})

    # If only one batch, return it (already final)
    if len(batch_summaries) == 1 or not hierarchical_final:
        final = batch_summaries[0]
        return final, debug

    # Otherwise, combine batch summaries into a final pass
    combined_for_final = []
    for i, s in enumerate(batch_summaries):
        # add light provenance for the batch
        combined_for_final.append(f"--- BATCH {i+1} SUMMARY ---\n{ s }")
    combined_text = "\n\n".join(combined_for_final)

    final_summary = summarize_text(combined_text, output_format=output_format, max_tokens=3000, temperature=0.1)
    debug["final_summary_words"] = len(final_summary.split())
    return final_summary, debug


def summarize_file(file_id: int, *, output_format: str = "latex", batch_words: int = 1200, hierarchical: bool = True, target_ratio: float = 0.12) -> Dict[str, Any]:
    """
    Summarize chunks for a single file_id.
    Returns dict: {file_id, summary, summary_id (if saved)}.
    """
    chunks = storage.query_chunks_by_file(file_id)
    if not chunks:
        return {"file_id": file_id, "summary": ""}

    # Build provenance-rich small strings for each chunk (or group by page)
    # Here we group by page if page metadata exists, else keep chunk-level
    grouped = []
    if chunks and "meta" in chunks[0] and chunks[0]["meta"].get("page") is not None:
        # group by page
        by_page = {}
        for ch in chunks:
            p = ch["meta"].get("page", 0)
            by_page.setdefault(p, []).append(ch)
        for p in sorted(by_page.keys()):
            grouped.append(_make_provenance_chunk_text(by_page[p]))
    else:
        # keep chunk-level items
        for ch in chunks:
            grouped.append(_make_provenance_chunk_text([ch]))

    # Now summarize grouped text (use summarize_large_text so it batches if needed)
    estimated_target_words = max(200, int(sum(len(x.split()) for x in grouped) * target_ratio))
    final, debug = summarize_large_text(grouped, output_format=output_format, batch_words=batch_words, hierarchical_final=hierarchical, target_words=estimated_target_words)

    # Save summary to DB (optional)
    summary_id = storage.save_summary(file_id, final) if final else None

    return {"file_id": file_id, "summary": final or "", "summary_id": summary_id, "debug": debug}


def summarize_multiple_files(file_ids: List[int], *, output_format: str = "latex", batch_words: int = 1200, hierarchical: bool = True, target_ratio: float = 0.12) -> Dict[str, Any]:
    """
    Summarize many files and produce a combined summary. If latex requested, attempt to create a combined PDF.
    Returns {"per_file": [...], "combined": {"summary": "...", "summary_id":..., "pdf_path": "<filename>"?}}
    """
    per_file_results = []
    combined_text_parts = []

    for fid in file_ids:
        res = summarize_file(fid, output_format=output_format, batch_words=batch_words, hierarchical=hierarchical, target_ratio=target_ratio)
        per_file_results.append(res)
        file_meta = storage.get_file_by_id(fid) or {}
        name = file_meta.get("original_name", f"file_{fid}")
        s = res.get("summary", "") or ""
        if s.strip():
            combined_text_parts.append(f"=== DOCUMENT: {name} ===\n\n{s}")
        else:
            combined_text_parts.append(f"=== DOCUMENT: {name} ===\n\n[NO SUMMARY GENERATED]")

    # Combined summarization pass (could be latex or markdown)
    combined_final, debug_combined = summarize_large_text(combined_text_parts, output_format=output_format, batch_words=batch_words, hierarchical_final=hierarchical, target_words=int(sum(max(150, int(len(p.split()) * target_ratio)) for p in combined_text_parts)))
    combined_summary_id = storage.save_summary(None if not file_ids else file_ids[0], combined_final) if combined_final else None

    combined_result = {"summary_id": combined_summary_id, "summary": combined_final or ""}

    # If latex output, attempt to write .tex and compile to pdf, return filename only (server serves folder)
    if output_format.lower() == "latex" and combined_final and combined_final.strip():
        exports_dir = Path(storage.base_dir) / "exports"
        ts = int(time.time())
        safe_name = f"combined_summary_{ts}"
        try:
            # write tex (for debug)
            write_latex(combined_final, str(exports_dir), safe_name)
            # compile
            pdf_path = try_make_pdf_from_latex(combined_final, str(exports_dir), safe_name)
            if pdf_path:
                combined_result["pdf_path"] = Path(pdf_path).name
        except Exception as e:
            logger.exception("Failed to generate combined PDF: %s", e)

    return {"per_file": per_file_results, "combined": combined_result}
