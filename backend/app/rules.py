import copy

from .errors import ApiError
from .registry import get_registry, get_source

DESCRIPTIONS = {
    "inpatient": "住院醫療相關文件準備，仍須依保單確認適用項目。",
    "outpatient": "醫療門診相關文件準備，請確認就醫與收據資料。",
    "critical_illness": "防癌或重大疾病相關文件準備，疾病定義及給付須依保單確認。",
}


def get_claim_types() -> list[dict]:
    return [{"id": item["claim_type_id"], "title": item["label"], "description": DESCRIPTIONS[item["claim_type_id"]]}
            for item in get_registry()["claim_types"]]


def evaluate_condition(condition: dict, conditions: dict) -> bool | None:
    if condition.get("op") == "always":
        return True
    if "all" in condition:
        values = [evaluate_condition(item, conditions) for item in condition["all"]]
        return False if False in values else None if None in values else True
    field = condition.get("field")
    value = conditions.get("surgery" if field == "had_surgery" else field, "unknown")
    if value is None or value == "unknown":
        return None
    if isinstance(condition.get("equals"), bool):
        value = True if value == "yes" else False if value == "no" else value
    return value == condition.get("equals")


def build_checklist(case: dict, previous: list[dict] | None = None) -> list[dict]:
    if not case.get("claim_type_id"):
        return []
    registry = get_registry()
    if case["claim_type_id"] not in DESCRIPTIONS:
        raise ApiError("VALIDATION_ERROR", "此理賠類別尚未支援。")
    previous_by_id = {doc["id"]: doc for doc in previous or []}
    definitions = {doc["document_id"]: doc for doc in registry["documents"]}
    result = []
    for rule in registry["rules"]:
        if rule["claim_type_id"] != case["claim_type_id"]:
            continue
        definition = definitions[rule["document_id"]]
        source = get_source(rule["source_id"], rule.get("page_number"), include_submission=False)
        download = get_source(definition["download_source_id"], include_submission=False) if definition.get("download_source_id") else None
        examples = [get_source(identifier, include_submission=False) for identifier in definition["example_source_ids"]]
        example = next((item for item in examples if case["claim_type_id"] in item["related_claim_types"]), None)
        applicability = evaluate_condition(rule["condition"], case.get("conditions", {}))
        old = previous_by_id.get(definition["document_id"], {})
        safely_not_applicable = applicability is False and not rule["review_required"]
        old_status = old.get("status", "not_started")
        status = "not_applicable" if safely_not_applicable else "not_started" if old_status == "not_applicable" else old_status
        references = list(dict.fromkeys([rule["source_id"], *rule.get("additional_source_ids", [])]))
        result.append({
            "id": definition["document_id"], "title": definition["title"], "description": definition["description"],
            "requirement_type": rule["requirement_type"], "condition": copy.deepcopy(rule["condition"]),
            "applicability": applicability, "requirement_explanation": rule["explanation"],
            "review_required": bool(rule["review_required"] or applicability is None),
            "source_id": rule["source_id"], "official_url": source["official_url"],
            "download_url": download["official_url"] if download else None,
            "example_url": example["official_url"] if example else None,
            "source_references": [get_source(identifier, rule.get("page_number") if identifier == rule["source_id"] else None, include_submission=False) for identifier in references],
            "status": status, "analysis": copy.deepcopy(old.get("analysis")),
            "confirmed_findings": copy.deepcopy(old.get("confirmed_findings", [])), "file": copy.deepcopy(old.get("file")),
        })
    return result
