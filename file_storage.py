import os
import uuid
import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

class StorageManager:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)
        self.files_dir = self.base_dir / "files"
        self.db_path = self.base_dir / "storage.db"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_db()

    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_db(self):
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                original_name TEXT,
                stored_name TEXT,
                content_type TEXT,
                size INTEGER,
                uploaded_at REAL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                file_id INTEGER,
                chunk_idx INTEGER,
                text TEXT,
                meta_json TEXT,
                FOREIGN KEY(file_id) REFERENCES files(id)
            )
            """
        )
        conn.commit()
        conn.close()

    def save_file_from_bytes(self, file_bytes: bytes, original_name: str, content_type: str = "") -> Dict[str, Any]:
        """
        Save raw bytes to disk and register in DB. Return metadata dict.
        """
        ext = Path(original_name).suffix
        stored_name = f"{uuid.uuid4().hex}{ext}"
        stored_path = self.files_dir / stored_name

        with open(stored_path, "wb") as f:
            f.write(file_bytes)

        size = stored_path.stat().st_size
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO files (original_name, stored_name, content_type, size, uploaded_at) VALUES (?, ?, ?, ?, ?)",
            (original_name, stored_name, content_type, size, time.time()),
        )
        file_id = c.lastrowid
        conn.commit()
        conn.close()

        return {"file_id": file_id, "stored_path": str(stored_path), "original_name": original_name, "size": size}

    def save_chunks(self, file_id: int, chunks: List[Dict[str, Any]]):
        conn = self._conn()
        c = conn.cursor()
        for ch in chunks:
            text = ch["text"]
            meta_json = json.dumps(ch.get("meta", {}), ensure_ascii=False)
            chunk_idx = ch.get("meta", {}).get("chunk_idx", 0)
            c.execute("INSERT INTO chunks (file_id, chunk_idx, text, meta_json) VALUES (?, ?, ?, ?)",
                      (file_id, chunk_idx, text, meta_json))
        conn.commit()
        conn.close()

    def get_file_by_id(self, file_id: int) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT * FROM files WHERE id = ?", (file_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return dict(row)

    def query_chunks_by_file(self, file_id: int) -> List[Dict[str, Any]]:
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT chunk_idx, text, meta_json FROM chunks WHERE file_id = ? ORDER BY chunk_idx", (file_id,))
        rows = c.fetchall()
        conn.close()
        return [{"chunk_idx": r["chunk_idx"], "text": r["text"], "meta": json.loads(r["meta_json"])} for r in rows]
