import os
from pathlib import Path
from exec import run

UPLOAD_DIR = "uploads"

def main():

    files = []

    for f in Path(UPLOAD_DIR).glob("*"):
        if f.suffix.lower() in [".pdf", ".docx", ".pptx"]:
            files.append(str(f))

    if not files:
        print("No files found in uploads/")
        return

    run(files)


if __name__ == "__main__":
    main()
    