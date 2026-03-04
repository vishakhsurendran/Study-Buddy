import sys
import json
from pathlib import Path
from typing import List, Union
from processing import process_file_bytes, get_file_chunks

def process_files(paths: Union[str, List[str]]) -> List[int]:
    """
    Process a directory path or list of file paths.
    Returns list of file_ids created in DB.
    """
    file_ids = []
    if isinstance(paths, str):
        p = Path(paths)
        if p.is_dir():
            files = sorted([x for x in p.iterdir() if x.is_file()])
        elif p.is_file():
            files = [p]
        else:
            raise ValueError("Provided path does not exist")
    else:
        files = [Path(x) for x in paths]

    for f in files:
        b = f.read_bytes()
        summary = process_file_bytes(b, f.name, content_type="")
        if "file_id" in summary:
            file_ids.append(summary["file_id"])
        else:
            print("Processing failed for", f, summary.get("error"))
    return file_ids


def main():
    if len(sys.argv) < 2:
        print("Usage: python local_processor.py /path/to/file.pdf OR python local_processor.py /path/to/directory")
        return
    p = Path(sys.argv[1])
    if not p.exists():
        print("File/dir not found:", p)
        return

    # single-file behavior for backwards compatibility
    if p.is_file():
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
    else:
        # directory mode
        file_ids = process_files(str(p))
        print("Processed files, file_ids:", file_ids)


if __name__ == "__main__":
    main()
    