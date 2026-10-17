"""只讀取已查核、固定於專案中的官方來源，不存取使用者提供的網址。"""
import copy
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from .errors import ApiError

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data" / "official-sources.json"


def validate_official_url(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "life.cardif.com.tw"
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ApiError("INVALID_SOURCE", "官方來源網址未通過安全檢查。")
    return url


@lru_cache(maxsize=1)
def _load_registry() -> dict:
    # app 在 backend/app，資料為專案根目錄 data/。
    path = Path(__file__).resolve().parents[2] / "data" / "official-sources.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    ids = set()
    for source in registry["sources"]:
        validate_official_url(source["official_url"])
        if source["source_id"] in ids or source["verification_status"] != "verified":
            raise ApiError("INVALID_REGISTRY", "官方來源索引尚未通過查核。", 503)
        ids.add(source["source_id"])
    document_ids = {doc["document_id"] for doc in registry["documents"]}
    claim_ids = {item["claim_type_id"] for item in registry["claim_types"]}
    for rule in registry["rules"]:
        references = [rule["source_id"], *rule.get("additional_source_ids", [])]
        if (rule["document_id"] not in document_ids or rule["claim_type_id"] not in claim_ids
                or any(identifier not in ids for identifier in references)):
            raise ApiError("INVALID_REGISTRY", "官方文件規則索引不完整。", 503)
    for document in registry["documents"]:
        references = [document["source_id"], *document.get("example_source_ids", [])]
        if document.get("download_source_id"):
            references.append(document["download_source_id"])
        if any(identifier not in ids for identifier in references):
            raise ApiError("INVALID_REGISTRY", "官方文件來源索引不完整。", 503)
    return registry


def get_registry() -> dict:
    return copy.deepcopy(_load_registry())


def get_source(source_id: str, page_number: int | None = None, *, include_submission: bool = True) -> dict:
    registry = _load_registry()
    source = next((item for item in registry["sources"] if item["source_id"] == source_id), None)
    if source is None:
        raise ApiError("SOURCE_NOT_FOUND", "找不到已查核的官方來源。", 404)
    result = copy.deepcopy(source)
    if page_number is not None:
        result["page_number"] = page_number
    if include_submission and source_id == "cardif-claims":
        result["submission"] = copy.deepcopy(registry["submission"])
    return result
