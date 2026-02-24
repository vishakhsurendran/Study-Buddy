import logging
from typing import Dict, Any, List
from pathlib import Path
import tempfile
import os

from resource_intake import ResourceIntake
from file_storage import StorageManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

storage = StorageManager(base_dir="data", reset_db_on_start=True)


def process_file_bytes(file_bytes: bytes, original_name: str, content_type: str = "") -> Dict[str, Any]:
    saved = storage.save_file_from_bytes(file_bytes, original_name, content_type)
    file_id = saved["file_id"]

    suffix = os.path.splitext(original_name)[1] or ""
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as t:
            t.write(file_bytes)
            tmp = t.name

        extracted = ResourceIntake.extract_from_path(tmp, chunk_words=200, overlap=0, ocr_if_empty=True)
        storage.save_chunks(file_id, extracted)

        summary = {
            "file_id": file_id,
            "original_name": saved["original_name"],
            "stored_path": saved["stored_path"],
            "size": saved["size"],
            "chunks_extracted": len(extracted)
        }
        logger.info("Processed file %s -> %d chunks", original_name, len(extracted))
        return summary
    except Exception as e:
        logger.exception("Failed to process file %s", original_name)
        return {"file_id": file_id, "error": str(e)}
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except Exception:
                pass


def get_file_chunks(file_id: int) -> Dict[str, Any]:
    file_meta = storage.get_file_by_id(file_id)
    if file_meta is None:
        return {"error": "file not found"}
    chunks = storage.query_chunks_by_file(file_id)
    return {"file": file_meta, "chunks_count": len(chunks), "chunks": chunks}
