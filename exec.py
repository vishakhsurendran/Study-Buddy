# exec.py
import sys
from pathlib import Path
from processing import process_file_bytes, get_file_chunks
from connector import summarize_multiple_files
from export_utils import write_latex, try_make_pdf_from_latex
import time
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

EXPORT_DIR = "data/exports"

def run(files, target_ratio: float = 0.12):
    processed_file_ids = []
    for p in files:
        p = Path(p)
        print("Processing:", p)
        b = p.read_bytes()
        summary = process_file_bytes(b, p.name, content_type="")
        if "file_id" in summary:
            processed_file_ids.append(summary["file_id"])
        else:
            print("Failed to process:", p, summary)

    if not processed_file_ids:
        print("No files processed. Exiting.")
        return

    # Summarize all processed files and produce a combined summary in LaTeX
    res = summarize_multiple_files(processed_file_ids, output_format="latex", batch_words=1200, hierarchical=True, target_ratio=target_ratio)

    # Export per-file summaries as .tex -> .pdf
    for per in res["per_file"]:
        fid = per["file_id"]
        file_meta = None
        try:
            from file_storage import StorageManager
            storage = StorageManager(base_dir="data", reset_db_on_start=False)
            file_meta = storage.get_file_by_id(fid)
        except Exception:
            pass
        name = (file_meta and file_meta.get("original_name")) or f"file_{fid}"
        safe_name = Path(name).stem
        ts = int(time.time())
        tex_path = write_latex(per["summary"], EXPORT_DIR, f"{safe_name}_summary_{ts}")
        pdf_path = try_make_pdf_from_latex(tex_path)
        print(f"Exported per-file summary for {name}:")
        print("  TEX:", tex_path)
        print("  PDF:", pdf_path if pdf_path else "(PDF not created)")

    # Export combined
    combined = res["combined"]["summary"]
    ts = int(time.time())
    tex_path = write_latex(combined, EXPORT_DIR, f"combined_summary_{ts}")
    pdf_path = try_make_pdf_from_latex(tex_path)
    print("Exported combined summary:")
    print("  TEX:", tex_path)
    print("  PDF:", pdf_path if pdf_path else "(PDF not created)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python exec.py file1.pdf file2.docx ...")
        sys.exit(1)
    run(sys.argv[1:])
    