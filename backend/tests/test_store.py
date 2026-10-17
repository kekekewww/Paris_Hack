"""Persistence, ownership, retention and privacy tests against real SQLite."""

import copy
import importlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest


def store_module():
    try:
        return importlib.import_module("backend.app.store")
    except ImportError as error:
        pytest.fail(f"CaseStore is not implemented: {error}")


def case():
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid4()),
        "entry_path": "direct",
        "claim_type_id": "inpatient",
        "conditions": {"cause": "unknown", "surgery": "unknown"},
        "documents": [],
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }


def test_create_survives_store_recreation_and_returns_detached_data(tmp_path):
    path = tmp_path / "cases.sqlite3"
    first = store_module().CaseStore(path)
    item = case()
    created = first.create(item, "synthetic-owner")
    assert created == item
    created["conditions"]["cause"] = "accident"
    item["conditions"]["surgery"] = "yes"
    restored = store_module().CaseStore(path).get(item["id"], "synthetic-owner")
    assert restored["conditions"] == {"cause": "unknown", "surgery": "unknown"}
    assert UUID(restored["id"])


def test_create_supplies_uuid_and_utc_timestamps_when_missing(tmp_path):
    item = case()
    for field in ("id", "created_at", "updated_at"):
        item.pop(field)
    created = store_module().CaseStore(tmp_path / "cases.db").create(item, "owner")
    assert UUID(created["id"])
    assert datetime.fromisoformat(created["created_at"].replace("Z", "+00:00")).utcoffset().total_seconds() == 0
    assert created["updated_at"] == created["created_at"]


def test_owner_cannot_read_overwrite_or_delete_another_case(tmp_path):
    store = store_module().CaseStore(tmp_path / "cases.db")
    item = store.create(case(), "alice-session")
    assert store.get(item["id"], "bob-session") is None
    assert store.delete(item["id"], "bob-session") is False
    changed = copy.deepcopy(item)
    changed["claim_type_id"] = "outpatient"
    with pytest.raises(Exception) as caught:
        store.save(changed, "bob-session")
    assert caught.value.code == "CASE_NOT_FOUND"
    assert caught.value.status == 404
    assert store.get(item["id"], "alice-session")["claim_type_id"] == "inpatient"


def test_save_persists_updated_structure_without_extending_creation_time(tmp_path):
    store = store_module().CaseStore(tmp_path / "cases.db")
    item = store.create(case(), "owner")
    created_at = item["created_at"]
    item["conditions"]["cause"] = "accident"
    item["created_at"] = "2099-01-01T00:00:00Z"
    saved = store.save(item, "owner")
    assert saved["created_at"] == created_at
    assert saved["conditions"]["cause"] == "accident"
    assert store.get(item["id"], "owner")["conditions"]["cause"] == "accident"


def test_delete_removes_only_the_owned_case(tmp_path):
    store = store_module().CaseStore(tmp_path / "cases.db")
    first = store.create(case(), "owner")
    second = store.create(case(), "owner")
    assert store.delete(first["id"], "owner") is True
    assert store.get(first["id"], "owner") is None
    assert store.delete(first["id"], "owner") is False
    assert store.get(second["id"], "owner") is not None


def test_database_contains_hashed_owner_and_no_session_cookie(tmp_path):
    path = tmp_path / "cases.db"
    store = store_module().CaseStore(path)
    store.create(case(), "do-not-store-this-cookie-value")
    assert b"do-not-store-this-cookie-value" not in path.read_bytes()
    with sqlite3.connect(path) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(cases)")]
        assert "owner_hash" in columns
        hashed = connection.execute("SELECT owner_hash FROM cases").fetchone()[0]
    assert len(hashed) == 64
    assert set(hashed) <= set("0123456789abcdef")


def test_raw_file_bytes_cannot_be_persisted(tmp_path):
    path = tmp_path / "cases.db"
    store = store_module().CaseStore(path)
    item = case()
    item["documents"] = [{"id": "application", "file": {"name": "test.pdf", "type": "application/pdf", "size": 25}, "raw_file": b"SYNTHETIC-RAW-MEDICAL-BYTES"}]
    with pytest.raises(Exception) as caught:
        store.create(item, "owner")
    assert caught.value.code == "VALIDATION_ERROR"
    assert b"SYNTHETIC-RAW-MEDICAL-BYTES" not in path.read_bytes()
    assert store.get(item["id"], "owner") is None


@pytest.mark.parametrize("field", ["raw_file", "file_bytes", "base64", "raw_text"])
def test_encoded_or_raw_document_content_cannot_be_persisted(tmp_path, field):
    store = store_module().CaseStore(tmp_path / "cases.db")
    item = case()
    item["documents"] = [{"id": "application", field: "SYNTHETIC-RAW-DOCUMENT-CONTENT"}]
    with pytest.raises(Exception) as caught:
        store.create(item, "owner")
    assert caught.value.code == "VALIDATION_ERROR"
    assert store.get(item["id"], "owner") is None


def test_file_metadata_cannot_smuggle_encoded_content(tmp_path):
    store = store_module().CaseStore(tmp_path / "cases.db")
    item = case()
    item["documents"] = [{"id": "application", "file": {"name": "synthetic.pdf", "type": "application/pdf", "size": 22, "content": "ENCODED-RAW-CONTENT"}}]
    with pytest.raises(Exception) as caught:
        store.create(item, "owner")
    assert caught.value.code == "VALIDATION_ERROR"


def test_duplicate_uuid_cannot_replace_another_owners_case(tmp_path):
    store = store_module().CaseStore(tmp_path / "cases.db")
    first = store.create(case(), "first-owner")
    second = copy.deepcopy(first)
    second["claim_type_id"] = "outpatient"
    with pytest.raises(Exception) as caught:
        store.create(second, "second-owner")
    assert caught.value.code == "CASE_EXISTS"
    assert store.get(first["id"], "first-owner")["claim_type_id"] == "inpatient"
    assert store.get(first["id"], "second-owner") is None


def test_limit_is_per_owner_and_delete_releases_capacity(tmp_path):
    store = store_module().CaseStore(tmp_path / "cases.db", max_cases_per_owner=2)
    first = store.create(case(), "owner")
    store.create(case(), "owner")
    with pytest.raises(Exception) as caught:
        store.create(case(), "owner")
    assert caught.value.code == "CASE_LIMIT"
    assert caught.value.status == 429
    assert store.create(case(), "different-owner")
    store.delete(first["id"], "owner")
    assert store.create(case(), "owner")


def test_default_limit_rejects_twenty_first_case(tmp_path):
    store = store_module().CaseStore(tmp_path / "cases.db")
    for _ in range(20):
        store.create(case(), "owner")
    with pytest.raises(Exception) as caught:
        store.create(case(), "owner")
    assert caught.value.code == "CASE_LIMIT"
    assert caught.value.status == 429


@pytest.mark.parametrize("operation", ["create", "get", "save", "delete", "cleanup"])
def test_every_operation_expires_old_cases_by_created_at(tmp_path, monkeypatch, operation):
    module = store_module()
    now = datetime.now(timezone.utc).timestamp()
    monkeypatch.setattr(module.time, "time", lambda: now)
    path = tmp_path / "cases.db"
    store = module.CaseStore(path, ttl_seconds=10)
    old_case = case()
    old_case["created_at"] = datetime.fromtimestamp(now, timezone.utc).isoformat()
    expired = store.create(old_case, "old-owner")
    active = store.create({**old_case, "id": str(uuid4())}, "active-owner")
    now += 5
    active = store.save(active, "active-owner")
    now += 5
    if operation == "create":
        fresh = case()
        fresh["created_at"] = datetime.fromtimestamp(now, timezone.utc).isoformat()
        store.create(fresh, "new-owner")
    elif operation == "get":
        assert store.get(expired["id"], "old-owner") is None
    elif operation == "save":
        with pytest.raises(Exception) as caught:
            store.save(active, "active-owner")
        assert caught.value.code == "CASE_NOT_FOUND"
    elif operation == "delete":
        assert store.delete(expired["id"], "old-owner") is False
    else:
        assert store.cleanup() == 2
        assert store.cleanup() == 0
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM cases WHERE id IN (?, ?)", (expired["id"], active["id"])).fetchone()[0] == 0


def test_threaded_creates_respect_limit_without_database_errors(tmp_path):
    store = store_module().CaseStore(tmp_path / "cases.db", max_cases_per_owner=4)

    def create_one(_):
        try:
            return store.create(case(), "shared-owner")["id"]
        except Exception as error:
            assert error.code == "CASE_LIMIT"
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(create_one, range(12)))
    assert len({result for result in results if result}) == 4


def test_delete_physically_removes_structured_sensitive_values(tmp_path):
    path = tmp_path / "cases.db"
    store = store_module().CaseStore(path)
    item = case()
    item["messages"] = [{"role": "user", "content": "SYNTHETIC-DELETE-ME-428165"}]
    saved = store.create(item, "owner")
    assert b"SYNTHETIC-DELETE-ME-428165" in path.read_bytes()
    store.delete(saved["id"], "owner")
    assert b"SYNTHETIC-DELETE-ME-428165" not in path.read_bytes()
