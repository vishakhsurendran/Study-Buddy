# file_storage.py
import os
import logging
import time
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path
from io import BytesIO

from supabase_client import supabase

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _extract_resp_data(resp: Any) -> Optional[Any]:
    if resp is None:
        return None
    if isinstance(resp, dict):
        if "data" in resp:
            return resp.get("data")
        if "body" in resp:
            return resp.get("body")
        return resp
    if hasattr(resp, "data"):
        try:
            return getattr(resp, "data")
        except Exception:
            pass
    if hasattr(resp, "json"):
        try:
            return resp.json()
        except Exception:
            pass
    return None


def _extract_resp_error(resp: Any) -> Optional[Any]:
    if resp is None:
        return None
    if isinstance(resp, dict):
        if "error" in resp:
            return resp.get("error")
        if "errors" in resp:
            return resp.get("errors")
    if hasattr(resp, "error"):
        try:
            return getattr(resp, "error")
        except Exception:
            pass
    for attr in ("errors", "status_code", "message"):
        if hasattr(resp, attr):
            try:
                v = getattr(resp, attr)
                if v:
                    return v
            except Exception:
                pass
    return None


class StorageManager:
    """
    Supabase-backed storage manager wrapper. Expects:
      - supabase: a supabase client created in supabase_client.py
      - tables: files, chunks, summaries in Postgres (via Supabase)
      - storage buckets: 'files' and 'exports' (or configured names)
    """

    def __init__(self, files_bucket: str = "files", exports_bucket: str = "exports"):
        self.files_bucket = files_bucket
        self.exports_bucket = exports_bucket
        self.supabase = supabase

    # ---------- files ----------
    def save_file_from_bytes(self, file_bytes: bytes, original_name: str, content_type: str = "") -> Dict[str, Any]:
        try:
            meta = {
                "original_name": original_name,
                "stored_name": None,
                "content_type": content_type,
                "size": len(file_bytes),
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
            }

            logger.info("Inserting file metadata into Supabase files table")
            resp = self.supabase.table("files").insert(meta).execute()

            logger.debug("Supabase insert response: %r", resp)

            error = _extract_resp_error(resp)
            data = _extract_resp_data(resp)

            if error:
                logger.error("Supabase returned error on insert: %s", error)
                raise RuntimeError(f"DB insert failed: {error}")

            inserted_row = None
            if isinstance(data, list) and len(data) > 0:
                inserted_row = data[0]
            elif isinstance(data, dict) and "id" in data:
                inserted_row = data
            else:
                if isinstance(resp, dict) and "data" in resp and isinstance(resp["data"], list) and resp["data"]:
                    inserted_row = resp["data"][0]

            if not inserted_row:
                logger.error("Could not determine inserted row from response: %r", resp)
                raise RuntimeError("DB insert did not return row data")

            file_id = int(inserted_row.get("id"))
            key = f"{file_id}_{original_name}"

            # Try upload; supabase client versions accept different arg shapes.
            logger.info("Uploading file bytes to Supabase storage '%s' as key '%s'", self.files_bucket, key)
            try:
                bucket = self.supabase.storage.from_(self.files_bucket)
                # try to set content-type if available (so stored object has correct MIME)
                upload_resp = None
                try:
                    upload_resp = bucket.upload(key, file_bytes, {"content-type": content_type or "application/octet-stream"})
                except TypeError:
                    try:
                        upload_resp = bucket.upload(key, file_bytes, content_type=content_type or "application/octet-stream")
                    except TypeError:
                        # fallback: file-like or raw bytes
                        try:
                            upload_resp = bucket.upload(key, BytesIO(file_bytes))
                        except Exception:
                            upload_resp = bucket.upload(key, file_bytes)
                logger.debug("Supabase storage upload response: %r", upload_resp)
            except Exception as e:
                logger.exception("Supabase storage upload threw exception: %s", e)
                upload_resp = None

            try:
                self.supabase.table("files").update({"stored_name": key}).eq("id", file_id).execute()
            except Exception:
                logger.exception("Failed to update stored_name for file %s in DB", file_id)

            return {"file_id": file_id, "stored_path": f"{self.files_bucket}/{key}", "original_name": original_name, "size": len(file_bytes)}
        except Exception as e:
            logger.exception("save_file_from_bytes failed: %s", e)
            raise

    # ---------- chunks ----------
    def save_chunks(self, file_id: int, chunks: List[Dict[str, Any]]):
        try:
            rows = []
            for ch in chunks:
                meta = ch.get("meta", {}) or {}
                rows.append({
                    "file_id": int(file_id),
                    "chunk_idx": meta.get("chunk_idx", 0),
                    "text": ch.get("text", ""),
                    "meta_json": meta,
                    "page": meta.get("page")
                })
            if rows:
                resp = self.supabase.table("chunks").insert(rows).execute()
                logger.debug("Supabase chunks insert resp: %r", resp)
                err = _extract_resp_error(resp)
                if err:
                    logger.error("Error inserting chunks: %s", err)
        except Exception as e:
            logger.exception("save_chunks failed: %s", e)
            raise

    # ---------- query helpers ----------
    def get_file_by_id(self, file_id: int) -> Optional[Dict[str, Any]]:
        try:
            resp = self.supabase.table("files").select("*").eq("id", file_id).execute()
            logger.debug("get_file_by_id resp: %r", resp)
            data = _extract_resp_data(resp)
            if isinstance(data, list) and data:
                return data[0]
            if isinstance(data, dict) and data:
                return data
        except Exception as e:
            logger.exception("get_file_by_id error: %s", e)
        return None

    def query_chunks_by_file(self, file_id: int) -> List[Dict[str, Any]]:
        try:
            resp = (
                self.supabase
                .table("chunks")
                .select("chunk_idx, text, meta_json, page")
                .eq("file_id", int(file_id))
                .order("chunk_idx")
                .execute()
            )
            data = _extract_resp_data(resp) or []
            rows: List[Dict[str, Any]] = []
            if isinstance(data, list):
                for r in data:
                    meta = r.get("meta_json") or {}
                    if r.get("page") is not None:
                        meta["page"] = r.get("page")
                    rows.append({"chunk_idx": r.get("chunk_idx"), "text": r.get("text"), "meta": meta})
            return rows
        except Exception as e:
            logger.exception("query_chunks_by_file error: %s", e)
            return []

    def save_summary(self, file_id: Optional[int], summary_text: str) -> int:
        try:
            record = {
                "file_id": int(file_id) if file_id is not None else None,
                "summary_text": summary_text,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            resp = self.supabase.table("summaries").insert(record).execute()
            logger.debug("save_summary resp: %r", resp)
            data = _extract_resp_data(resp)
            if isinstance(data, list) and data:
                return int(data[0].get("id"))
            if isinstance(data, dict) and data.get("id"):
                return int(data.get("id"))
        except Exception as e:
            logger.exception("save_summary insert error: %s", e)
        return -1

    def get_summary_by_id(self, summary_id: int) -> Optional[Dict[str, Any]]:
        try:
            resp = self.supabase.table("summaries").select("*").eq("id", int(summary_id)).execute()
            data = _extract_resp_data(resp)
            if isinstance(data, list) and data:
                return data[0]
            if isinstance(data, dict) and data:
                return data
        except Exception as e:
            logger.exception("get_summary_by_id error: %s", e)
        return None

    # ---------- exports ----------
    def upload_export_file(self, local_path: str, dest_filename: str) -> Optional[str]:
        """
        Upload local file to exports bucket and return public URL (or signed URL fallback).
        Tries to set content-type to application/pdf so Supabase serves with correct MIME.
        Returns None on failure.
        """
        try:
            key = f"exports/{dest_filename}"
            bucket = self.supabase.storage.from_(self.exports_bucket)
            logger.info("Uploading export file %s -> bucket key %s", local_path, key)
            with open(local_path, "rb") as fh:
                data = fh.read()

            upload_resp = None
            # Try several common signatures to set content-type depending on client version
            try:
                # some clients accept an options dict as the 3rd arg
                upload_resp = bucket.upload(key, data, {"content-type": "application/pdf"})
            except TypeError:
                try:
                    # some clients accept keyword arg content_type
                    upload_resp = bucket.upload(key, data, content_type="application/pdf")
                except TypeError:
                    # some clients accept bytes only and infer type: fallback
                    upload_resp = bucket.upload(key, data)

            logger.debug("upload_export_file resp: %r", upload_resp)

            # Try to get a public URL; prefer object/public endpoint
            try:
                public = bucket.get_public_url(key)
                logger.debug("get_public_url resp: %r", public)
                if isinstance(public, dict):
                    url = public.get("publicUrl") or public.get("public_url") or public.get("publicURL")
                    if url:
                        return url
                if hasattr(public, "publicUrl"):
                    return getattr(public, "publicUrl")
                if hasattr(public, "public_url"):
                    return getattr(public, "public_url")
            except Exception:
                logger.exception("get_public_url failed")

            # fallback: create signed url
            try:
                signed = bucket.create_signed_url(key, 60 * 60)
                logger.debug("create_signed_url resp: %r", signed)
                if isinstance(signed, dict):
                    return signed.get("signedURL") or signed.get("signed_url") or None
            except Exception:
                logger.exception("create_signed_url failed")
            return None
        except Exception as e:
            logger.exception("upload_export_file failed: %s", e)
            return None
        