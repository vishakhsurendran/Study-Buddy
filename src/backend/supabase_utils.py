# supabase_utils.py
import os
from supabase import create_client
from pathlib import Path
import logging
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
# name of bucket you created in Supabase Storage
BUCKET_NAME = os.environ.get("SUPABASE_EXPORTS_BUCKET", "exports")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logger.warning("Supabase env vars not set")

def _client():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def upload_pdf_to_supabase(local_pdf_path: str, dest_name: str) -> str:
    client = _client()
    bucket = client.storage().from_(BUCKET_NAME)
    with open(local_pdf_path, "rb") as f:
        data = f.read()

    # Use the correct upload signature: path (dest) and file bytes
    res = bucket.upload(dest_name, data)  # depending on client version it may accept bytes or file object
    logger.info("Supabase upload response: %s", res)
    # If the client returns an object with 'error', check and log
    if isinstance(res, dict) and res.get("error"):
        logger.error("Supabase upload error: %s", res["error"])
        return ""

    # Try to get a public URL
    try:
        public = bucket.get_public_url(dest_name)
        logger.info("Supabase get_public_url response: %s", public)
        # handle different return shapes
        if isinstance(public, dict):
            url = public.get("publicUrl") or public.get("public_url") or public.get("publicURL")
            if url:
                return url
        # fallback: create signed url
        signed = bucket.create_signed_url(dest_name, 60 * 60)
        logger.info("Supabase signed url response: %s", signed)
        if isinstance(signed, dict):
            return signed.get("signedURL") or signed.get("signed_url") or ""
    except Exception as e:
        logger.exception("Failed to retrieve public or signed url: %s", e)
    return ""
