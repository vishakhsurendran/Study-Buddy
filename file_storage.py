import os
import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

class StorageManager:
    def __init__(self, base_dir: str = "data", reset_db_on_start: bool = True):
        self.base_dir = Path(base_dir)
        self.files_dir = self.base_dir / "files" 
        self.db_path = self.base_dir / "storage.db"

        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)

        if reset_db_on_start and self.db_path.exists():
            try:
                self.db_path.unlink()
            except Exception:
                pass

        self._ensure_db()

    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_db(self):
        conn = self._conn()
        c = conn.cursor()

        # files table: 
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

        # chunks table with page column (nullable)
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                file_id INTEGER,
                chunk_idx INTEGER,
                text TEXT,
                meta_json TEXT,
                page INTEGER,
                FOREIGN KEY(file_id) REFERENCES files(id)
            )
            """
        )

        # summaries table
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY,
                file_id INTEGER,
                summary_text TEXT,
                created_at REAL,
                FOREIGN KEY(file_id) REFERENCES files(id)
            )
            """
        )

        conn.commit()

        c.execute("PRAGMA table_info(chunks)")
        cols = [r["name"] for r in c.fetchall()]
        if "page" not in cols:
            try:
                c.execute("ALTER TABLE chunks ADD COLUMN page INTEGER")
                conn.commit()
            except Exception:
                pass

        conn.close()

    def save_file_from_bytes(self, file_bytes: bytes, original_name: str, content_type: str = "") -> Dict[str, Any]:
        size = len(file_bytes)
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO files (original_name, stored_name, content_type, size, uploaded_at) VALUES (?, ?, ?, ?, ?)",
            (original_name, None, content_type, size, time.time()),
        )
        file_id = c.lastrowid
        conn.commit()
        conn.close()

        return {"file_id": file_id, "stored_path": None, "original_name": original_name, "size": size}

    def save_chunks(self, file_id: int, chunks: List[Dict[str, Any]]):
        conn = self._conn()
        c = conn.cursor()
        for ch in chunks:
            text = ch["text"]
            meta = ch.get("meta", {}) or {}
            meta_json = json.dumps(meta, ensure_ascii=False)
            chunk_idx = meta.get("chunk_idx", 0)
            page = meta.get("page")
            c.execute(
                "INSERT INTO chunks (file_id, chunk_idx, text, meta_json, page) VALUES (?, ?, ?, ?, ?)",
                (file_id, chunk_idx, text, meta_json, page),
            )
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
        c.execute(
            "SELECT chunk_idx, text, meta_json, page FROM chunks WHERE file_id = ? ORDER BY chunk_idx",
            (file_id,),
        )
        rows = c.fetchall()
        conn.close()
        result = []
        for r in rows:
            meta = json.loads(r["meta_json"]) if r["meta_json"] else {}
            if r["page"] is not None:
                meta["page"] = r["page"]
            result.append({"chunk_idx": r["chunk_idx"], "text": r["text"], "meta": meta})
        return result

    def save_summary(self, file_id: int, summary_text: str) -> int:
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO summaries (file_id, summary_text, created_at) VALUES (?, ?, ?)",
            (file_id, summary_text, time.time()),
        )
        summary_id = c.lastrowid
        conn.commit()
        conn.close()
        return summary_id

    def get_summary_by_id(self, summary_id: int) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT * FROM summaries WHERE id = ?", (summary_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return dict(row)
    