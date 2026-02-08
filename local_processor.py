import sys
import json
from pathlib import Path
from processing import process_file_bytes, get_file_chunks

def main():
    if len(sys.argv) < 2:
        print("Usage: python process_local.py /path/to/file.pdf")
        return
    p = Path(sys.argv[1])
    if not p.exists():
        print("File not found:", p)
        return
    b = p.read_bytes()
    summary = process_file_bytes(b, p.name, content_type="")
    print("Summary:")
    print(json.dumps(summary, indent=2))
    if "file_id" in summary:
        details = get_file_chunks(summary["file_id"])
        print("\nStored chunks (first 5):")
        for c in details.get("chunks", [])[:5]:
            print(f"--- chunk {c['chunk_idx']} ---")
            print(c['text'][:400].replace("\n", " "))
            print("meta:", c["meta"])
    else:
        print("Processing returned error:", summary.get("error"))

if __name__ == "__main__":
    main()
