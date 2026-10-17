import copy

from backend.app.registry import get_registry, get_source
from backend.app.rules import build_checklist, get_claim_types


def case(kind="inpatient", **conditions):
    return {"claim_type_id": kind, "conditions": conditions}


def document(documents, identifier):
    return next(item for item in documents if item["id"] == identifier)


def test_registry_contains_verified_sources_and_submission():
    registry = get_registry()
    assert len(registry["sources"]) == 11
    assert len(registry["rules"]) == 22
    assert all(source["verification_status"] == "verified" for source in registry["sources"])
    assert get_source("cardif-claims")["submission"]["support"]["phone"] == "0800-012-899"
    assert [item["id"] for item in get_claim_types()] == ["inpatient", "outpatient", "critical_illness"]


def test_unknown_conditions_never_exempt_conditional_documents():
    documents = build_checklist(case())
    assert document(documents, "application")["requirement_type"] == "required"
    assert document(documents, "passbook")["applicability"] is None
    assert document(documents, "passbook")["review_required"] is True
    assert document(documents, "passbook")["status"] == "not_started"
    assert build_checklist(case(None)) == []


def test_surgery_is_exempt_only_when_official_condition_is_clearly_false():
    documents = build_checklist(case(surgery="no"))
    assert document(documents, "surgery")["status"] == "not_applicable"
    documents = build_checklist(case(surgery="yes", diagnosis_has_surgery_details="no"))
    assert document(documents, "surgery")["applicability"] is True
    assert document(documents, "surgery")["source_references"][0]["page_number"] == 3


def test_nonfirst_critical_claim_retains_pathology_review():
    documents = build_checklist(case("critical_illness", first_claim="no"))
    pathology = document(documents, "pathology")
    assert pathology["applicability"] is False
    assert pathology["review_required"] is True
    assert pathology["status"] == "not_started"


def test_outpatient_receipt_is_required_and_has_conflict_review():
    documents = build_checklist(case("outpatient", receipt_type="daily"))
    assert document(documents, "receipt")["requirement_type"] == "required"
    assert document(documents, "receipt")["review_required"] is True
    assert document(documents, "receipt")["download_url"] is None
    assert not any(doc["id"] == "receipt" for doc in build_checklist(case("inpatient", receipt_type="actual")))


def test_recalculation_preserves_existing_analysis_and_does_not_mutate_input():
    documents = build_checklist(case())
    application = document(documents, "application")
    application.update(status="needs_attention", analysis={"findings": [{"id": "signature"}]}, confirmed_findings=["signature"])
    original = copy.deepcopy(documents)
    updated = build_checklist(case(payment_method="remittance"), documents)
    assert document(updated, "application")["analysis"] == application["analysis"]
    assert document(updated, "application")["status"] == "needs_attention"
    assert documents == original
