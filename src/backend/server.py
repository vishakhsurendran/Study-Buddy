from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import uvicorn
import shutil
import os
import tempfile
import logging

from processing import process_file_bytes
from connector import summarize_multiple_files

logger = logging.getLogger("backend")
logger.setLevel(logging.INFO)

app = FastAPI(title="Study-Buddy Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite default
        "http://127.0.0.1:5173",   # some browsers use 127.0.0.1
        "http://localhost:3000",   # keep if you sometimes use 3000
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/process")
async def process_files(files: List[UploadFile] = File(...), output_format: str = Form("markdown")):
    """
    Accepts multiple files, runs your existing process_file_bytes -> summarize pipeline,
    and returns the combined summary and per-file summaries as JSON.

    Synchronous: call will return once summarization completes.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    file_ids = []

    try:
        for uploaded in files:
            # read file bytes
            b = await uploaded.read()
            # process_file_bytes returns a dict with "file_id"
            summary = process_file_bytes(b, uploaded.filename, content_type=uploaded.content_type or "")
            if "file_id" not in summary:
                logger.error("Processing failed for %s: %s", uploaded.filename, summary)
                raise HTTPException(status_code=500, detail=f"Processing failed for {uploaded.filename}")
            file_ids.append(summary["file_id"])

        # call summarizer (uses connector.summarize_multiple_files)
        combined = summarize_multiple_files(
            file_ids,
            output_format=output_format,
            batch_words=1200,
            hierarchical=True
        )

        # prepare response: include per-file summaries and combined summary
        return {
            "ok": True,
            "file_count": len(file_ids),
            "per_file": combined.get("per_file", []),
            "combined_summary": combined.get("combined", {}).get("summary", ""),
            "combined_summary_format": output_format
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in /process: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    # for local dev
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=True)
    