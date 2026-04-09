# /src/backend/connector.py
import logging
from typing import List, Dict, Any, Tuple
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from file_storage import StorageManager
from info_sum import summarize_text
from export_utils import write_latex, try_make_pdf_from_latex
# keep supabase_utils for backwards compatibility / optional use
from supabase_utils import upload_pdf_to_supabase

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Use the same StorageManager that other modules import (ensures consistent buckets)
storage = StorageManager(files_bucket="files", exports_bucket="exports")

def _make_provenance_chunk_text(chunks: List[Dict[str, Any]]) -> str:
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
            clean_excerpt = excerpt[:120].replace("\n", " ")
            header += f" | excerpt: {clean_excerpt}"
        out_parts.append(f"{header}\nCONTENT:\n{ch.get('text','')}")
    return "\n\n".join(out_parts)


def _batch_texts_by_words(texts: List[str], max_words_per_batch: int) -> List[List[str]]:
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

# func used for parallelized requests
def _process_batch(i, b, output_format):
    joined = "\n\n".join(b)
    summ = summarize_text(
        joined,
        output_format=output_format,
        max_tokens=2000,
        temperature=0.2
    )

    debug_info = {
        "batch": i,
        "words_in_batch": sum(len(x.split()) for x in b),
        "summary_words": len(summ.split())
    }

    return i, summ, debug_info


def summarize_large_text(chunks_provenance_texts: List[str], *, output_format: str = "latex",
                         batch_words: int = 1200, hierarchical_final: bool = True, target_words: int = 800) -> Tuple[str, Dict[str, Any]]:
    texts = [t for t in chunks_provenance_texts if t and t.strip()]
    if not texts:
        return "", {"steps": []}

    batches = _batch_texts_by_words(texts, batch_words)
    # batch_summaries = []
    debug = {"batches": len(batches), "batch_sizes": [len(b) for b in batches], "steps": []}
    batch_summaries = [None] * len(batches)

    logger.info('Running with 10 threads.')
    with ThreadPoolExecutor(max_workers=10) as executor:  # adjust concurrency
        futures = [
            executor.submit(_process_batch, i, b, output_format)
            for i, b in enumerate(batches)
        ]

        for future in as_completed(futures):
            i, summ, debug_info = future.result()
            batch_summaries[i] = summ
            debug["steps"].append(debug_info)

    ''' old code, serialized
    for i, b in enumerate(batches):
        joined = "\n\n".join(b)
        summ = summarize_text(joined, output_format=output_format, max_tokens=2000, temperature=0.2)
        batch_summaries.append(summ)
        debug["steps"].append({
            "batch": i,
            "words_in_batch": sum(len(x.split()) for x in b),
            "summary_words": len(summ.split())
        })
    '''

    if len(batch_summaries) == 1 or not hierarchical_final:
        return batch_summaries[0], debug

    combined_for_final = [f"--- BATCH {i+1} SUMMARY ---\n{ s }" for i, s in enumerate(batch_summaries)]
    combined_text = "\n\n".join(combined_for_final)

    final_summary = summarize_text(combined_text, output_format=output_format, max_tokens=3000, temperature=0.1)
    debug["final_summary_words"] = len(final_summary.split())
    return final_summary, debug


def summarize_file(file_id: int, *, output_format: str = "latex", batch_words: int = 1200, hierarchical: bool = True, target_ratio: float = 0.12) -> Dict[str, Any]:
    chunks = storage.query_chunks_by_file(file_id)
    if not chunks:
        return {"file_id": file_id, "summary": ""}

    grouped = []
    if chunks and "meta" in chunks[0] and chunks[0]["meta"].get("page") is not None:
        by_page = {}
        for ch in chunks:
            p = ch["meta"].get("page", 0)
            by_page.setdefault(p, []).append(ch)
        for p in sorted(by_page.keys()):
            grouped.append(_make_provenance_chunk_text(by_page[p]))
    else:
        for ch in chunks:
            grouped.append(_make_provenance_chunk_text([ch]))

    estimated_target_words = max(200, int(sum(len(x.split()) for x in grouped) * target_ratio))
    final, debug = summarize_large_text(grouped, output_format=output_format, batch_words=batch_words, hierarchical_final=hierarchical, target_words=estimated_target_words)

    summary_id = storage.save_summary(file_id, final) if final else None

    return {"file_id": file_id, "summary": final or "", "summary_id": summary_id, "debug": debug}


def summarize_multiple_files(file_ids: List[int], *, output_format: str = "latex", batch_words: int = 1200, hierarchical: bool = True, target_ratio: float = 0.12) -> Dict[str, Any]:
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

    combined_final, debug_combined = summarize_large_text(
        combined_text_parts,
        output_format=output_format,
        batch_words=batch_words,
        hierarchical_final=hierarchical,
        target_words=int(sum(max(150, int(len(p.split()) * target_ratio)) for p in combined_text_parts))
    )

    combined_summary_id = storage.save_summary(None if not file_ids else file_ids[0], combined_final) if combined_final else None
    combined_result = {"summary_id": combined_summary_id, "summary": combined_final or ""}

    # provide default PDF fields / error
    combined_result["pdf_url"] = None
    combined_result["pdf_path"] = None
    combined_result["pdf_error"] = None

    # If latex output, try to write .tex, compile to PDF, and upload to Supabase (exports)
    if output_format.lower() == "latex" and combined_final and combined_final.strip():
        # use the container-local exports folder (matches server mount / exports static)
        exports_dir = Path(__file__).resolve().parent / "data" / "exports"
        ts = int(time.time())
        safe_name = f"combined_summary_{ts}"
        try:
            # Write the .tex locally (helpful for debugging)
            tex_path = write_latex(combined_final, str(exports_dir), safe_name)
            logger.info("Wrote .tex to %s", tex_path)

            # compile locally (returns local PDF path on success or empty string)
            local_pdf_path = try_make_pdf_from_latex(combined_final, str(exports_dir), safe_name)
            if local_pdf_path:
                logger.info("Local PDF created at %s", local_pdf_path)

                # If try_make_pdf_from_latex returned an absolute http(s) URL (some helper variants might),
                # treat it as a direct public URL.
                if isinstance(local_pdf_path, str) and (local_pdf_path.startswith("http://") or local_pdf_path.startswith("https://")):
                    combined_result["pdf_url"] = local_pdf_path
                    combined_result["pdf_path"] = Path(local_pdf_path).name
                    logger.info("PDF compilation returned a URL directly: %s", local_pdf_path)
                else:
                    # Upload the local PDF to Supabase exports bucket via StorageManager helper
                    local_pdf_path = str(local_pdf_path)
                    dest_filename = Path(local_pdf_path).name
                    upload_url = None
                    try:
                        # Use the StorageManager uploader which handles client differences
                        upload_url = storage.upload_export_file(local_pdf_path, dest_filename)
                    except Exception as e:
                        logger.exception("storage.upload_export_file threw: %s", e)

                    # fallback to supabase_utils if StorageManager didn't return a url
                    if not upload_url:
                        try:
                            upload_url = upload_pdf_to_supabase(local_pdf_path, f"combined/{dest_filename}")
                        except Exception:
                            logger.exception("upload_pdf_to_supabase fallback failed")

                    if upload_url:
                        combined_result["pdf_url"] = upload_url
                        combined_result["pdf_path"] = dest_filename
                        logger.info("Uploaded compiled PDF and got public URL: %s", upload_url)
                    else:
                        # upload failed: prefer to report an explicit error rather than silently letting UI guess
                        combined_result["pdf_error"] = "PDF compiled locally but upload to storage failed"
                        # keep local filename only if you know /exports is mounted and will be served; otherwise don't rely on it
                        if Path(local_pdf_path).exists():
                            combined_result["pdf_path"] = dest_filename
                            logger.warning("PDF compiled but upload failed; saving local file %s (server may serve via /exports if mounted)", dest_filename)
            else:
                # try_make_pdf failed; try_make_pdf_from_latex already saved debug artifacts in exports_dir
                combined_result["pdf_error"] = "LaTeX compilation failed; check debug folder in data/exports for details"
        except Exception as e:
            logger.exception("Failed to generate combined PDF: %s", e)
            combined_result["pdf_error"] = f"Unexpected PDF generation error: {e}"

    return {"per_file": per_file_results, "combined": combined_result}
