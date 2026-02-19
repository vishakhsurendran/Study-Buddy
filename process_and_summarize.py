import sys
from pathlib import Path
from processing import process_file_bytes, get_file_chunks
from connector import generate_file_summary

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_process_and_summarize.py /path/to/file.pdf")
        return
    p = Path(sys.argv[1])
    if not p.exists():
        print("File not found:", p)
        return

    print("Processing file:", p)
    b = p.read_bytes()
    summary = process_file_bytes(b, p.name, content_type="")
    print("Processing result:", summary)
    if "file_id" not in summary:
        print("Error during processing:", summary.get("error"))
        return

    fid = summary["file_id"]
    print(f"Found file_id={fid}, generating summary...")
    out = generate_file_summary(fid)
    print("Summary generated:", out.get("summary_id"))
    print("Preview of summary (first 1200 chars):")
    print(out.get("summary", "")[:1200])

if __name__ == "__main__":
    main()
    