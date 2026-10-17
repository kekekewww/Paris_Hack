"""以真實 HTTP 驗證本機 API；只使用 demo/ 的合成文件。"""
from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

import httpx


ROOT = Path(__file__).resolve().parents[1]
API_PREFIX = "/api/v1"


class SmokeFailure(Exception):
    def __init__(self, code: str):
        self.code = code


def loopback_url(value: str) -> str:
    """拒絕外站、認證資訊、重新導向入口與額外路徑。"""
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        is_loopback = host.lower() == "localhost"
        if not is_loopback:
            is_loopback = ipaddress.ip_address(host).is_loopback
        if (parsed.scheme not in {"http", "https"} or not is_loopback
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
                or "\\" in value or parsed.port == 0):
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError("僅允許不含認證資訊及額外路徑的本機 loopback HTTP(S) 網址。") from None
    return f"{parsed.scheme}://{parsed.netloc}"


def safe_code(value, fallback="HTTP_ERROR") -> str:
    return value if isinstance(value, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value) else fallback


def provider_label(value) -> str:
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.+; -]{1,80}", value) else "unknown"


def require(condition, code: str, summary: dict):
    if not condition:
        raise SmokeFailure(code)
    summary["checks"] += 1


def request_json(client: httpx.Client, method: str, path: str, summary: dict, expected=200, **kwargs):
    response = client.request(method, API_PREFIX + path, **kwargs)
    try:
        payload = response.json()
    except (ValueError, UnicodeError):
        raise SmokeFailure("INVALID_JSON_RESPONSE") from None
    if response.status_code != expected:
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        raise SmokeFailure(safe_code(error.get("code"), f"HTTP_{response.status_code}"))
    summary["checks"] += 1
    return payload


def verified_references(references) -> bool:
    if not isinstance(references, list) or not references:
        return False
    for source in references:
        if not isinstance(source, dict) or source.get("verification_status") != "verified":
            return False
        parsed = urlsplit(source.get("official_url", ""))
        if parsed.scheme != "https" or parsed.hostname != "life.cardif.com.tw" or parsed.username or parsed.password:
            return False
    return True


def application_document(case: dict) -> dict:
    return next((item for item in case.get("documents", []) if item.get("id") == "application"), {})


def analyze_synthetic(client, case_id: str, filename: str, mime: str, provider: str, summary: dict,
                      *, quality_page: int | None = None, quality_only: bool = False):
    path = ROOT / "demo" / "documents" / filename
    with path.open("rb") as document:
        case = request_json(client, "POST", f"/cases/{case_id}/documents/application/analyze", summary,
                            files={"file": (filename, document, mime)})
    analysis = application_document(case).get("analysis") or {}
    require(analysis.get("is_simulated") is False, "SIMULATED_ANALYSIS_REJECTED", summary)
    require(analysis.get("provider") == provider, "UNEXPECTED_OCR_PROVIDER", summary)
    if quality_only:
        require(analysis.get("extracted_fields") == [], "QUALITY_PRECHECK_INVENTED_FIELDS", summary)
    else:
        require(bool(analysis.get("extracted_fields")), "NO_EXTRACTED_FIELDS", summary)
    require(bool(analysis.get("findings")), "NO_PRECHECK_FINDINGS", summary)
    require(application_document(case).get("status") == "needs_attention", "UNSAFE_DOCUMENT_STATUS", summary)
    result = {"provider": provider_label(analysis.get("provider")), "findings_count": len(analysis["findings"])}
    if quality_page is not None:
        require(analysis.get("analysis_status") == "uncertain", "QUALITY_PRECHECK_NOT_UNCERTAIN", summary)
        quality_findings = [finding for finding in analysis["findings"] if finding.get("field") == "image_quality"]
        require(len(quality_findings) == 1, "INVALID_QUALITY_FINDINGS_COUNT", summary)
        quality_finding = quality_findings[0]
        quality_box = quality_finding.get("bounding_box", {})
        require(quality_finding.get("page_number") == quality_page and quality_box.get("page_number") == quality_page,
                "QUALITY_FINDING_WRONG_PAGE", summary)
        if quality_only:
            require(len(analysis["findings"]) == 1 and analysis.get("bounding_boxes") == [quality_box],
                    "QUALITY_PRECHECK_INVENTED_FINDINGS", summary)
        else:
            fields = analysis["extracted_fields"]
            masked_values = {"已辨識內容（隱私遮罩）", "未可靠辨識內容"}
            require(any(field.get("value") == "已辨識內容（隱私遮罩）" for field in fields)
                    and all(field.get("field") == "document_type" or field.get("value") in masked_values for field in fields),
                    "MIXED_QUALITY_FIELDS_NOT_MASKED", summary)
            require(quality_box in analysis.get("bounding_boxes", []), "QUALITY_BOX_NOT_PERSISTED", summary)
        result.update(analysis_status=analysis["analysis_status"], extracted_fields_count=len(analysis["extracted_fields"]),
                      quality_findings_count=len(quality_findings))
    return result


def run_smoke(base_url: str, include_ocr: bool) -> dict:
    summary = {"status": "PASS", "code": "OK", "checks": 0, "conversation": "SKIPPED_PROVIDER_NOT_GROUNDED", "image_ocr": "SKIPPED_NOT_REQUESTED"}
    case_id = None
    # 不讀取代理環境、不追蹤重新導向，避免合成文件離開 loopback。
    options = {"base_url": base_url, "headers": {"Origin": base_url}, "timeout": 65.0,
               "follow_redirects": False, "trust_env": False}
    with httpx.Client(**options) as client:
        try:
            health = request_json(client, "GET", "/health", summary)
            require(health.get("status") == "ok" and health.get("service_mode") == "api", "NOT_REAL_API_SERVICE", summary)
            summary["llm_provider"] = provider_label(health.get("llm_provider"))
            summary["ocr_provider"] = provider_label(health.get("ocr_provider"))

            claim_types = request_json(client, "GET", "/claim-types", summary)
            require(isinstance(claim_types, list) and any(item.get("id") == "inpatient" for item in claim_types), "MISSING_CLAIM_TYPE", summary)
            summary["claim_types_count"] = len(claim_types)
            source = request_json(client, "GET", "/sources/cardif-claims", summary)
            require(verified_references([source]) and bool(source.get("submission", {}).get("postal")), "INVALID_OFFICIAL_SOURCE", summary)

            case = request_json(client, "POST", "/cases", summary, expected=201,
                                json={"entry_path": "direct", "claim_type_id": "inpatient"})
            case_id = case.get("id")
            require(isinstance(case_id, str) and bool(case_id), "INVALID_CASE_ID", summary)
            loaded = request_json(client, "GET", f"/cases/{case_id}", summary)
            require(loaded == case, "CASE_NOT_PERSISTED", summary)

            with httpx.Client(**options) as stranger:
                for method in ("GET", "DELETE"):
                    denied = request_json(stranger, method, f"/cases/{case_id}", summary, expected=404)
                    require(denied.get("error", {}).get("code") == "CASE_NOT_FOUND", "CASE_ISOLATION_FAILED", summary)
            request_json(client, "GET", f"/cases/{case_id}", summary)

            changed = request_json(client, "PATCH", f"/cases/{case_id}", summary,
                                   json={"conditions": {"surgery": "no", "payment_method": "other"}})
            checklist = request_json(client, "GET", f"/cases/{case_id}/checklist", summary)
            require(checklist == changed.get("documents"), "CHECKLIST_NOT_PERSISTED", summary)
            require(any(doc.get("id") == "surgery" and doc.get("status") == "not_applicable" for doc in checklist), "RULES_NOT_APPLIED", summary)
            summary["documents_count"] = len(checklist)

            if health.get("llm_provider") == "grounded_rules":
                answer = request_json(client, "POST", f"/cases/{case_id}/messages", summary,
                                      json={"message": "診斷書需要什麼格式？"})
                response = answer.get("response", {})
                require(response.get("provider") == "grounded_rules" and response.get("is_simulated") is False, "NOT_GROUNDED_RESPONSE", summary)
                require(verified_references(response.get("source_references")), "UNVERIFIED_ANSWER_REFERENCES", summary)
                require(len(answer.get("case", {}).get("messages", [])) == 2, "MESSAGES_NOT_PERSISTED", summary)
                summary["conversation"] = "VERIFIED_GROUNDED_RULES"
                summary["source_references_count"] = len(response["source_references"])

            summary["pdf_analysis"] = analyze_synthetic(client, case_id, "application-missing.pdf", "application/pdf", "pdf_text", summary)
            if include_ocr:
                summary["image_ocr"] = analyze_synthetic(client, case_id, "application-clear.png", "image/png", "rapidocr", summary)
                summary["blurred_analysis"] = analyze_synthetic(client, case_id, "application-blurred.png", "image/png", "quality_precheck", summary,
                                                                quality_page=1, quality_only=True)
                summary["mixed_quality_analysis"] = analyze_synthetic(client, case_id, "application-mixed-quality.pdf", "application/pdf", "pdf_text", summary,
                                                                      quality_page=2)
        except SmokeFailure as error:
            summary.update(status="FAIL", code=error.code)
        except httpx.RequestError:
            summary.update(status="FAIL", code="NETWORK_ERROR")
        except OSError:
            summary.update(status="FAIL", code="DEMO_FILE_UNAVAILABLE")
        except (TypeError, KeyError, AttributeError, ValueError):
            summary.update(status="FAIL", code="INVALID_RESPONSE_SHAPE")
        finally:
            if case_id:
                try:
                    deleted = request_json(client, "DELETE", f"/cases/{case_id}", summary)
                    require(deleted.get("deleted") is True and deleted.get("id") == case_id, "CASE_DELETE_FAILED", summary)
                    missing = request_json(client, "GET", f"/cases/{case_id}", summary, expected=404)
                    require(missing.get("error", {}).get("code") == "CASE_NOT_FOUND", "CASE_DELETE_NOT_PERSISTED", summary)
                    summary["cleanup"] = "VERIFIED_DELETED"
                except (SmokeFailure, httpx.RequestError, TypeError, AttributeError):
                    summary["cleanup"] = "CLEANUP_FAILED"
                    if summary["status"] == "PASS":
                        summary.update(status="FAIL", code="CLEANUP_FAILED")
    return summary


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="以真實 HTTP 驗證本機理賠準備 API；只上傳 demo 合成文件，結束時刪除案件。")
    parser.add_argument("--base-url", type=loopback_url, default="http://127.0.0.1:8000", help="loopback 服務根網址（預設 http://127.0.0.1:8000）")
    parser.add_argument("--include-ocr", action="store_true", help="加驗清楚 PNG 的真實 RapidOCR、模糊 PNG 品質預檢及混合品質 PDF 的第二頁標記")
    args = parser.parse_args()
    summary = run_smoke(args.base_url, args.include_ocr)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
