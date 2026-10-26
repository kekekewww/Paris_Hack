"""封存官方文件目錄：只查詢本機已查核資料，不下載使用者網址。"""
import copy
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from .errors import ApiError

LIBRARY_PATH = Path(__file__).resolve().parents[2] / "data" / "official-library.json"


def validate_library_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme == "https" and parsed.hostname == "life.cardif.com.tw"
                 and not parsed.username and not parsed.password
                 and parsed.port in (None, 443) and bool(parsed.path))
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ApiError("INVALID_LIBRARY_SOURCE", "官方文件網址未通過安全檢查。", 503)
    return url


@lru_cache(maxsize=1)
def _load_library() -> dict:
    catalog = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    categories = {item["id"] for item in catalog["categories"]}
    ids = set()
    for doc in catalog["documents"]:
        validate_library_url(doc["official_url"])
        validate_library_url(doc["source_page_url"])
        if (doc["id"] in ids or doc["category_id"] not in categories
                or doc["verification_status"] != "verified"):
            raise ApiError("INVALID_LIBRARY", "官方文件目錄尚未通過查核。", 503)
        ids.add(doc["id"])
    for faq in catalog["faq"]:
        if not faq["source_ids"] or any(source_id not in ids for source_id in faq["source_ids"]):
            raise ApiError("INVALID_LIBRARY", "常見問題的官方來源不完整。", 503)
    for product in catalog.get("product_lookups", []):
        references = product.get("version_ids", []) + product.get("candidate_source_ids", [])
        if any(source_id not in ids for source_id in references):
            raise ApiError("INVALID_LIBRARY", "商品版本的官方來源不完整。", 503)
    return catalog


def get_library(query: str = "", category: str = "all") -> dict:
    catalog = _load_library()
    query = str(query or "").strip()[:200]
    category = str(category or "all").strip()[:80]
    terms = query.casefold().split()
    documents = []
    for doc in catalog["documents"]:
        if category != "all" and doc["category_id"] != category:
            continue
        searchable = " ".join(str(doc.get(key) or "") for key in (
            "title", "category_label", "product_code", "asset_code", "version", "product_name", "keywords"
        )).casefold()
        if all(term in searchable for term in terms):
            documents.append(copy.deepcopy(doc))
    categories = copy.deepcopy(catalog["categories"])
    for item in categories:
        item["document_count"] = sum(doc["category_id"] == item["id"] for doc in catalog["documents"])
    return {
        "schema_version": catalog["schema_version"], "checked_at": catalog["checked_at"],
        "scope_note": catalog["scope_note"], "categories": categories, "documents": documents,
        "total": len(documents), "query": query, "category": category,
    }


def get_faq() -> list[dict]:
    catalog = _load_library()
    documents = {doc["id"]: doc for doc in catalog["documents"]}
    result = copy.deepcopy(catalog["faq"])
    for item in result:
        item["sources"] = [copy.deepcopy(documents[source_id]) for source_id in item["source_ids"]]
    return result


def lookup_product(code: str) -> dict:
    catalog = _load_library()
    requested = str(code or "").strip()[:120]
    normalized = requested.upper()
    documents = {doc["id"]: doc for doc in catalog["documents"]}
    product = next((item for item in catalog.get("product_lookups", [])
                    if item["code"].upper() == normalized), None)
    result = {
        "requested_code": requested, "normalized_code": normalized,
        "verification_status": "unverified", "product_name": None, "versions": [],
        "candidate_sources": [], "preparation_supported": False,
        "scope_note": "尚無可核對此完整商品代碼與版本的官方資料，請確認保單面頁並洽官方客服；不可據此判定保障、資格或金額。",
        "checked_at": catalog["checked_at"],
    }
    if product:
        result.update({key: copy.deepcopy(product[key]) for key in (
            "verification_status", "product_name", "scope_note"
        )})
        result["versions"] = [copy.deepcopy(documents[source_id]) for source_id in product.get("version_ids", [])]
        result["candidate_sources"] = [copy.deepcopy(documents[source_id]) for source_id in product.get("candidate_source_ids", [])]
    return result
