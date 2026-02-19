import time
import logging
from typing import List, Dict, Any

from file_storage import StorageManager
from info_sum import summarize

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

storage = StorageManager(base_dir="data", reset_db_on_start=False)

def _batch_chunks_by_words(chunks: List[Dict[str, Any]], max_words: int = 1200) -> List[str]:
    batches: List[str] = []
    cur_texts: List[str] = []
    cur_words = 0

    for ch in chunks:
        w = len(ch["text"].split())
        if cur_words + w <= max_words or not cur_texts:
            cur_texts.append(ch["text"])
            cur_words += w
        else:
            batches.append("\n\n".join(cur_texts))
            cur_texts = [ch["text"]]
            cur_words = w
    if cur_texts:
        batches.append("\n\n".join(cur_texts))
    return batches

def generate_file_summary(file_id: int, batch_words: int = 1200) -> Dict[str, Any]:
    file_meta = storage.get_file_by_id(file_id)
    if not file_meta:
        raise ValueError("file not found")

    chunks = storage.query_chunks_by_file(file_id)
    if not chunks:
        return {"file_id": file_id, "summary": "", "note": "no chunks found"}

    batches = _batch_chunks_by_words(chunks, max_words=batch_words)
    batch_summaries: List[str] = []

    for i, batch_text in enumerate(batches):
        try:
            logger.info("Summarizing batch %d/%d for file %d", i + 1, len(batches), file_id)
            s = summarize(batch_text)
            batch_summaries.append(s)
        except Exception as e:
            logger.exception("Summarization failed for batch %s", i)
            batch_summaries.append(f"[ERROR in batch {i}: {e}]")

    combined_summary = "\n\n%=== Batch Summaries ===\n\n".join(batch_summaries)

    summary_id = storage.save_summary(file_id, combined_summary)

    return {"file_id": file_id, "summary_id": summary_id, "summary": combined_summary}
