import os
from supabase import create_client
import logging

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
BUCKET_NAME = os.environ.get("SUPABASE_EXPORTS_BUCKET", "exports")

def _client():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def upload_pdf_to_supabase(local_pdf_path: str, dest_name: str) -> str:
    client = _client()
    bucket = client.storage().from_(BUCKET_NAME)
    with open(local_pdf_path, "rb") as f:
        data = f.read()

    res = None
    try:
        try:
            res = bucket.upload(dest_name, data, {"content-type": "application/pdf"})
        except TypeError:
            try:
                res = bucket.upload(dest_name, data, content_type="application/pdf")
            except TypeError:
                res = bucket.upload(dest_name, data)
    except Exception as e:
        logger.exception("Supabase upload threw: %s", e)
        return ""

    logger.info("Supabase upload response: %s", res)
    if isinstance(res, dict) and res.get("error"):
        logger.error("Supabase upload error: %s", res["error"])
        return ""

    # get public url / signed url as before...
    try:
        public = bucket.get_public_url(dest_name)
        logger.info("Supabase get_public_url response: %s", public)
        if isinstance(public, dict):
            url = public.get("publicUrl") or public.get("public_url") or public.get("publicURL")
            if url:
                return url
        signed = bucket.create_signed_url(dest_name, 60 * 60)
        logger.info("Supabase signed url response: %s", signed)
        if isinstance(signed, dict):
            return signed.get("signedURL") or signed.get("signed_url") or ""
    except Exception as e:
        logger.exception("Failed to retrieve public or signed url: %s", e)
    return ""
