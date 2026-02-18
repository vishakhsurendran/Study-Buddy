import logging
from typing import Dict, Any, List
from pathlib import Path

from resource_intake import ResourceIntake
from file_storage import StorageManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

storage = StorageManager(base_dir="data")

def process_file_bytes(file_bytes: bytes, original_name: str, content_type: str = "") -> Dict[str, Any]:
    saved = storage.save_file_from_bytes(file_bytes, original_name, content_type)
    file_id = saved["file_id"]
    stored_path = saved["stored_path"]

    try:
        extracted = ResourceIntake.extract_from_path(stored_path, chunk_words=200, overlap=40, ocr_if_empty=True)
        storage.save_chunks(file_id, extracted)
        summary = {
            "file_id": file_id,
            "original_name": saved["original_name"],
            "stored_path": stored_path,
            "size": saved["size"],
            "chunks_extracted": len(extracted)
        }
        logger.info("Processed file %s -> %d chunks", original_name, len(extracted))
        return summary
    except Exception as e:
        logger.exception("Failed to process file %s", stored_path)
        return {"file_id": file_id, "error": str(e)}


def get_file_chunks(file_id: int) -> Dict[str, Any]:
    # Returns file metadata + list of chunks for that file_id.
    file_meta = storage.get_file_by_id(file_id)
    if file_meta is None:
        return {"error": "file not found"}
    chunks = storage.query_chunks_by_file(file_id)
    return {"file": file_meta, "chunks_count": len(chunks), "chunks": chunks}
