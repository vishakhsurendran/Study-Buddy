# server.py
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import List
import uvicorn
import os
import logging

# import your pipeline functions
from processing import process_file_bytes
from connector import summarize_multiple_files

logger = logging.getLogger("backend")
logger.setLevel(logging.INFO)

app = FastAPI(title="Study-Buddy Backend")

# CORS: ensure your frontend origin is allowed (vite default 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
EXPORTS_DIR = BASE_DIR / "data" / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/process")
async def process_files(request: Request, files: List[UploadFile] = File(...), output_format: str = Form("markdown")):
    """
    Accepts multiple files, runs pipeline, returns per-file summaries and combined summary.
    If output_format == 'latex' and connector created a PDF, returns combined_pdf_url.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    file_ids = []

    try:
        for uploaded in files:
            b = await uploaded.read()
            summary = process_file_bytes(b, uploaded.filename, content_type=uploaded.content_type or "")
            if "file_id" not in summary:
                logger.error("Processing failed for %s: %s", uploaded.filename, summary)
                raise HTTPException(status_code=500, detail=f"Processing failed for {uploaded.filename}")
            file_ids.append(summary["file_id"])

        combined = summarize_multiple_files(
            file_ids,
            output_format=output_format,
            batch_words=1200,
            hierarchical=True
        )

        combined_summary = combined.get("combined", {}).get("summary", "")
        per_file = combined.get("per_file", [])

        result = {
            "ok": True,
            "file_count": len(file_ids),
            "per_file": per_file,
            "combined_summary": combined_summary,
            "combined_summary_format": output_format
        }

        # if connector generated a pdf filename, add full URL
        pdf_filename = combined.get("combined", {}).get("pdf_path")
        if pdf_filename:
            # request.base_url is like http://127.0.0.1:8000/
            # build URL: <base>/exports/<pdf_filename>
            base = str(request.base_url).rstrip("/")
            result["combined_pdf_url"] = f"{base}/exports/{pdf_filename}"

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in /process: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
    