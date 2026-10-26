"""官方文件查詢與保單版本邊界；不使用網路、案件或模型。"""
import importlib
import importlib.util
from urllib.parse import urlsplit

import pytest


def library():
    assert importlib.util.find_spec("backend.app.library") is not None, "缺少官方文件查詢模組"
    return importlib.import_module("backend.app.library")


def test_catalog_search_returns_real_official_claim_form_and_category():
    result = library().get_library(query="保險金申請書", category="all")
    assert result["total"] > 0
    assert any("保險金申請書" in doc["title"] for doc in result["documents"])
    assert result["query"] == "保險金申請書"
    assert any(item["id"] == "claims" for item in result["categories"])


def test_category_filter_excludes_other_documents_and_unknown_category_is_empty():
    result = library().get_library(category="health")
    assert result["total"] > 0
    assert all(doc["category_id"] == "health" for doc in result["documents"])
    assert library().get_library(category="does-not-exist")["documents"] == []


def test_search_is_case_insensitive_but_does_not_invent_complete_policy_code():
    result = library().get_library(query="ihi_vie")
    assert result["total"] >= 1
    assert all(doc["asset_code"] == "IHI_VIE" for doc in result["documents"])
    assert not library().get_library(query="IHI_C_1131001")["documents"]


def test_external_url_query_does_not_fetch_or_turn_into_official_source():
    result = library().get_library(query="http://127.0.0.1/private")
    assert result["documents"] == []
    assert result["total"] == 0


def test_all_returned_links_and_metadata_have_verified_provenance():
    result = library().get_library()
    assert result["total"] >= 30
    assert "全" in result["scope_note"]
    ids = set()
    for doc in result["documents"]:
        assert doc["id"] not in ids
        ids.add(doc["id"])
        assert doc["title"] and doc["category_label"] and doc["checked_at"]
        assert doc["verification_status"] == "verified"
        assert "version" in doc and "product_code" in doc and "page_number" in doc
        for key in ("official_url", "source_page_url"):
            parsed = urlsplit(doc[key])
            assert parsed.scheme == "https" and parsed.hostname == "life.cardif.com.tw"
            assert not parsed.username and not parsed.password
            assert parsed.port in (None, 443)


def test_other_insurance_categories_are_document_lookup_only():
    categories = library().get_library()["categories"]
    assert {item["id"] for item in categories} >= {"claims", "investment", "life", "accident", "health", "credit", "participating", "endorsement"}
    assert all(item["preparation_supported"] is False for item in categories if item["id"] != "claims")
    assert all("僅" in doc["scope_note"] for doc in library().get_library(category="life")["documents"])


def test_faq_answers_resolve_to_verified_sources_with_pages_when_pdf():
    faq = library().get_faq()
    assert len(faq) >= 4
    for item in faq:
        assert item["question"] and item["answer"] and item["sources"]
        assert all(source["verification_status"] == "verified" for source in item["sources"])
        assert set(item["source_ids"]) == {source["id"] for source in item["sources"]}


def test_unknown_policy_code_never_guesses_product_or_benefits():
    result = library().lookup_product("IHI_UNKNOWN_9999999")
    assert result["verification_status"] == "unverified"
    assert result["product_name"] is None and result["versions"] == []
    assert result["preparation_supported"] is False
    assert "確認" in result["scope_note"]


def test_specific_product_lookup_keeps_requested_version_separate():
    result = library().lookup_product(" ihi_c_1131001 ")
    assert result["normalized_code"] == "IHI_C_1131001"
    assert result["preparation_supported"] is False
    if result["verification_status"] == "verified":
        assert result["product_name"] and result["versions"]
        assert all(item["product_code"] == "IHI_C_1131001" for item in result["versions"])
    else:
        assert result["product_name"] is None and result["versions"] == []


def test_official_future_date_is_preserved_as_evidence_but_requires_confirmation():
    result = library().get_library(query="COIAUTO_Provision")
    assert result["total"] == 1
    doc = result["documents"][0]
    assert doc["version"] is None and doc["version_date"] is None
    assert doc["version_status"] == "requires_confirmation"
    assert any(item["date"] == "2026-12-31" for item in doc["version_evidence"])
    assert "晚於" in doc["version_note"]


def test_claim_requirement_and_service_guide_are_not_blank_application_forms():
    requirements = library().get_library(query="申請身故(完全失能)理賠應檢附文件")["documents"]
    assert len(requirements) == 1
    assert requirements[0]["document_type"] == "pdf_requirements"
    service_guides = library().get_library(query="保險理賠受益人安心陪伴")["documents"]
    assert service_guides
    assert all(doc["document_type"] == "pdf_guide" for doc in service_guides)


def test_catalog_and_faq_return_independent_copies():
    result = library().get_library()
    result["documents"][0]["title"] = "被呼叫者改寫"
    result["categories"].clear()
    assert library().get_library()["documents"][0]["title"] != "被呼叫者改寫"
    assert library().get_library()["categories"]
    faq = library().get_faq()
    faq[0]["sources"].clear()
    assert library().get_faq()[0]["sources"]


@pytest.mark.parametrize("value", ["http://life.cardif.com.tw/zh/a314", "https://life.cardif.com.tw.evil.example/a", "https://user@life.cardif.com.tw/a", "https://127.0.0.1/a", "https://life.cardif.com.tw:8443/a"])
def test_catalog_rejects_unsafe_source_urls(value):
    from backend.app.errors import ApiError
    with pytest.raises(ApiError):
        library().validate_library_url(value)
