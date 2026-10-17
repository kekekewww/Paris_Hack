"""SQLite storage for short-lived, owner-isolated structured claim cases.

The HTTP layer owns case validation and supplies only structured extraction
results and file metadata. This module never accepts file bytes or an owner
cookie in the persisted payload.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import threading
import time
from uuid import UUID, uuid4

from .errors import ApiError


class CaseStore:
    def __init__(self, path, ttl_seconds=86400, max_cases_per_owner=20):
        if ttl_seconds <= 0 or max_cases_per_owner <= 0:
            raise ValueError("Case retention and owner limit must be positive")
        self.path = Path(path)
        self.ttl_seconds = ttl_seconds
        self.max_cases_per_owner = max_cases_per_owner
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connection() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS cases ("
                "id TEXT PRIMARY KEY, owner_hash TEXT NOT NULL, "
                "created_at REAL NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS cases_owner ON cases(owner_hash)")
            connection.execute("CREATE INDEX IF NOT EXISTS cases_created ON cases(created_at)")
        self.cleanup()

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            # DELETE journaling avoids retaining prior case data in a WAL file.
            connection.execute("PRAGMA secure_delete=ON")
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _owner_hash(owner):
        if not isinstance(owner, str) or not owner:
            raise ApiError("VALIDATION_ERROR", "案件存取識別無效。", 422)
        return sha256(owner.encode("utf-8")).hexdigest()

    @staticmethod
    def _structured(case):
        try:
            if not isinstance(case, dict):
                raise ValueError("Case must be an object")
            # A JSON round trip makes every returned object independent of its
            # caller and rejects raw bytes, streams and other file objects.
            item = json.loads(json.dumps(case, ensure_ascii=False, allow_nan=False))
            pending = [item]
            raw_fields = {
                "raw_file", "file_bytes", "file_content", "raw_content",
                "raw_text", "blob", "base64", "data_url", "content_bytes",
            }
            while pending:
                node = pending.pop()
                if isinstance(node, dict):
                    for field, value in node.items():
                        if field.lower() in raw_fields:
                            raise ValueError("Raw document data is not retained")
                        if field == "file" and value is not None:
                            if not isinstance(value, dict) or set(value) - {"name", "type", "size"}:
                                raise ValueError("Only file metadata is retained")
                        pending.append(value)
                elif isinstance(node, list):
                    pending.extend(node)
            return item
        except (TypeError, ValueError, OverflowError, RecursionError) as error:
            raise ApiError("VALIDATION_ERROR", "案件僅能保存結構化資料與檔案中繼資料。", 422) from error

    @staticmethod
    def _created_timestamp(value):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("UTC offset required")
            return parsed.timestamp()
        except (AttributeError, TypeError, ValueError, OverflowError) as error:
            raise ApiError("VALIDATION_ERROR", "案件建立時間格式無效。", 422) from error

    @staticmethod
    def _case_id(value):
        try:
            UUID(value)
            return value
        except (TypeError, ValueError, AttributeError) as error:
            raise ApiError("VALIDATION_ERROR", "案件識別碼格式無效。", 422) from error

    def cleanup(self):
        """Erase expired cases across all owners and return the deleted count."""
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM cases WHERE created_at <= ?", (time.time() - self.ttl_seconds,)
            )
            return cursor.rowcount

    def create(self, case, owner):
        with self._lock:
            self.cleanup()
            owner_hash = self._owner_hash(owner)
            item = self._structured(case)
            item.setdefault("id", str(uuid4()))
            self._case_id(item["id"])
            item.setdefault("created_at", datetime.fromtimestamp(time.time(), timezone.utc).isoformat())
            item.setdefault("updated_at", item["created_at"])
            created = self._created_timestamp(item["created_at"])
            with self._connection() as connection:
                # Count and insertion are one transaction even if another
                # process or CaseStore instance opens the same SQLite database.
                connection.execute("BEGIN IMMEDIATE")
                count = connection.execute(
                    "SELECT COUNT(*) FROM cases WHERE owner_hash = ?", (owner_hash,)
                ).fetchone()[0]
                if count >= self.max_cases_per_owner:
                    raise ApiError("CASE_LIMIT", "暫存案件數量已達上限，請先清除不再使用的案件。", 429)
                try:
                    connection.execute(
                        "INSERT INTO cases(id, owner_hash, created_at, payload) VALUES (?, ?, ?, ?)",
                        (item["id"], owner_hash, created, json.dumps(item, ensure_ascii=False, allow_nan=False)),
                    )
                except sqlite3.IntegrityError as error:
                    raise ApiError("CASE_EXISTS", "案件識別碼已存在。", 409) from error
            return item

    def get(self, id, owner):
        with self._lock:
            self.cleanup()
            owner_hash = self._owner_hash(owner)
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT payload FROM cases WHERE id = ? AND owner_hash = ?", (id, owner_hash)
                ).fetchone()
            return json.loads(row[0]) if row else None

    def save(self, case, owner):
        with self._lock:
            self.cleanup()
            owner_hash = self._owner_hash(owner)
            item = self._structured(case)
            case_id = self._case_id(item.get("id"))
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT payload FROM cases WHERE id = ? AND owner_hash = ?", (case_id, owner_hash)
                ).fetchone()
                if row is None:
                    raise ApiError("CASE_NOT_FOUND", "查無案件，或案件已清除。", 404)
                # Retention is fixed at creation; editing a case cannot extend
                # the period for which its structured data remains on disk.
                item["created_at"] = json.loads(row[0])["created_at"]
                connection.execute(
                    "UPDATE cases SET payload = ? WHERE id = ? AND owner_hash = ?",
                    (json.dumps(item, ensure_ascii=False, allow_nan=False), case_id, owner_hash),
                )
            return item

    def delete(self, id, owner):
        with self._lock:
            self.cleanup()
            owner_hash = self._owner_hash(owner)
            with self._connection() as connection:
                cursor = connection.execute(
                    "DELETE FROM cases WHERE id = ? AND owner_hash = ?", (id, owner_hash)
                )
                return cursor.rowcount > 0
