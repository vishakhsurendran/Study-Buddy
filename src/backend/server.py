from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import List
from pathlib import Path
from file_storage import StorageManager
import uvicorn
import os
import logging

from processing import process_file_bytes
from connector import summarize_multiple_files

# ---- logging ----
logger = logging.getLogger("backend")
logger.setLevel(logging.INFO)
logging.getLogger("uvicorn").setLevel(logging.INFO)

# Ensure exports directory exists and mount it at /exports
BASE_DIR = Path(__file__).resolve().parent
EXPORTS_DIR = BASE_DIR / "data" / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Study-Buddy Backend")
app.mount("/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")

# allow your frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        # allow vercel previews / production via regex if needed
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    client_host = request.client.host if request.client else "unknown"
    logger.info("Incoming request: %s %s from %s", request.method, request.url.path, client_host)
    resp = await call_next(request)
    logger.info("Response status: %s for %s %s", resp.status_code, request.method, request.url.path)
    return resp

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/process")
async def process_files(request: Request, files: List[UploadFile] = File(...), output_format: str = Form("markdown")):
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

        # If connector provided a PDF URL or an error, pass it to frontend
        pdf_url = None
        pdf_error = None
        combined_info = combined.get("combined", {}) if isinstance(combined, dict) else {}

        if combined_info.get("pdf_url"):
            pdf_url = combined_info.get("pdf_url")
        elif combined_info.get("pdf_path"):
            candidate = combined_info.get("pdf_path")
            # If pdf_path is already a full URL, use it
            if isinstance(candidate, str) and (candidate.startswith("http://") or candidate.startswith("https://")):
                pdf_url = candidate
            else:
                # Only build a static /exports URL if the file actually exists in EXPORTS_DIR
                candidate_name = Path(candidate).name
                local_file = EXPORTS_DIR / candidate_name
                if local_file.exists():
                    base = str(request.base_url).rstrip("/")
                    pdf_url = f"{base}/exports/{candidate_name}"
                else:
                    # do not fabricate a URL if local file missing; instead expose an error
                    pdf_error = combined_info.get("pdf_error") or "Compiled PDF present locally on worker but not uploaded or not available for download."

        if not pdf_url and combined_info.get("pdf_error"):
            pdf_error = combined_info.get("pdf_error")

        if pdf_url:
            result["combined_pdf_url"] = pdf_url
        if pdf_error:
            result["combined_pdf_error"] = pdf_error

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in /process: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/reset")
def reset_db():
    storage = StorageManager()
    storage.supabase.table("chunks").delete().neq("id", 0).execute()
    storage.supabase.table("summaries").delete().neq("id", 0).execute()
    storage.supabase.table("files").delete().neq("id", 0).execute()
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
    