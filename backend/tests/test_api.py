import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("CASE_DB_PATH", str(tmp_path / "cases.sqlite3"))
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1000")
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as result:
        yield result


def create(client, **kwargs):
    response = client.post("/api/v1/cases", json={"entry_path": "direct", "claim_type_id": "inpatient", **kwargs})
    assert response.status_code == 201, response.text
    return response.json()


def find(case, identifier="application"):
    return next(doc for doc in case["documents"] if doc["id"] == identifier)


def test_health_creates_secure_session_and_truthfully_reports_providers(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["service_mode"] == "api"
    assert response.json()["llm_provider"] == "grounded_rules"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert response.headers["x-content-type-options"] == "nosniff"


def test_direct_case_lifecycle_and_source_contract(client):
    case = create(client)
    identifier = case["id"]
    assert case["conditions"]["payment_method"] == "unknown"
    assert client.get(f"/api/v1/cases/{identifier}").json() == case
    assert client.get(f"/api/v1/cases/{identifier}/checklist").json() == case["documents"]
    changed = client.patch(f"/api/v1/cases/{identifier}", json={"conditions": {"payment_method": "other", "surgery": "no"}}).json()
    assert find(changed, "passbook")["status"] == "not_applicable"
    assert find(changed, "surgery")["status"] == "not_applicable"
    assert client.get("/api/v1/claim-types").json()[0]["title"] == "住院醫療"
    assert client.get("/api/v1/sources/cardif-claims").json()["submission"]["postal"]["address"]
    assert client.delete(f"/api/v1/cases/{identifier}").json() == {"deleted": True, "id": identifier}
    assert client.get(f"/api/v1/cases/{identifier}").status_code == 404


def test_case_access_is_isolated_between_browser_sessions(app, client):
    case = create(client)
    with TestClient(app) as other:
        for method in (other.get, other.delete):
            response = method(f"/api/v1/cases/{case['id']}")
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "CASE_NOT_FOUND"


@pytest.mark.parametrize("payload", [
    {"entry_path": "wrong"},
    {"entry_path": "direct", "claim_type_id": "invented"},
    {"entry_path": "direct", "conditions": {"surgery": True}},
    {"entry_path": "direct", "conditions": {"secret": "sensitive"}},
    {"entry_path": "direct", "unknown": "sensitive"},
])
def test_invalid_json_never_echoes_sensitive_input(client, payload):
    response = client.post("/api/v1/cases", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "sensitive" not in response.text and "detail" not in response.json()


def test_invalid_status_cannot_fabricate_approval_or_exempt_required_document(client):
    case = create(client)
    url = f"/api/v1/cases/{case['id']}/documents/application"
    assert client.patch(url, json={"status": "precheck_passed"}).json()["error"]["code"] == "INVALID_DOCUMENT_STATUS"
    assert client.patch(url, json={"status": "not_applicable"}).json()["error"]["code"] == "REQUIRED_DOCUMENT"
    assert client.patch(url, json={"confirmed_findings": ["invented"]}).json()["error"]["code"] == "INVALID_FINDING"
    uploaded = client.patch(url, json={"status": "uploaded"}).json()
    assert find(uploaded)["status"] == "uploaded"
    assert find(uploaded)["analysis"] is None


def test_cross_site_mutations_are_rejected(client):
    response = client.post("/api/v1/cases", json={"entry_path": "direct"}, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"
    response = client.post("/api/v1/cases", json={"entry_path": "direct"}, headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403


def test_missing_resources_and_invalid_messages_use_safe_structured_errors(client):
    assert client.get("/api/v1/sources/invented").json()["error"]["code"] == "SOURCE_NOT_FOUND"
    case = create(client)
    for message in ("   ", "x" * 4001):
        response = client.post(f"/api/v1/cases/{case['id']}/messages", json={"message": message})
        assert response.status_code == 422
    response = client.post(f"/api/v1/cases/{case['id']}/messages", json={"message": "欄位？", "document_id": "invented"})
    assert response.status_code == 404
    assert client.get(f"/api/v1/cases/{case['id']}").json()["messages"] == []


def test_repository_configuration_and_registry_are_not_public_static_files(client):
    for path in ("/.env", "/.git/config", "/data/official-sources.json", "/backend/app/main.py", "/PROJECT_PLAN.md"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.headers["x-content-type-options"] == "nosniff"


def test_pdf_worker_and_wasm_use_portable_static_mime_types(tmp_path, monkeypatch):
    import mimetypes
    from backend.app import main

    assets = tmp_path / "dist" / "assets"
    pdfjs = tmp_path / "dist" / "pdfjs"
    assets.mkdir(parents=True)
    pdfjs.mkdir(parents=True)
    worker = b"export const worker = true;"
    wasm = b"\x00asm\x01\x00\x00\x00"
    (assets / "pdf.worker.mjs").write_bytes(worker)
    (pdfjs / "decoder.wasm").write_bytes(wasm)
    mimetypes.init()
    # Windows registry entries can override Python's built-in extension map.
    monkeypatch.setitem(mimetypes.types_map, ".mjs", "text/plain")
    monkeypatch.setitem(mimetypes.types_map, ".wasm", "application/octet-stream")
    monkeypatch.setattr(main, "ROOT", tmp_path)
    monkeypatch.setenv("CASE_DB_PATH", str(tmp_path / "static.sqlite3"))
    with TestClient(main.create_app()) as client:
        response = client.get("/assets/pdf.worker.mjs")
        assert response.status_code == 200
        assert response.content == worker
        assert response.headers["content-type"].split(";")[0] in {"text/javascript", "application/javascript"}
        response = client.get("/pdfjs/decoder.wasm")
        assert response.status_code == 200
        assert response.content == wasm
        assert response.headers["content-type"].split(";")[0] == "application/wasm"


def test_unexpected_errors_do_not_reach_server_logs_or_echo_private_input(app, monkeypatch, caplog):
    def broken_create(*args):
        raise RuntimeError("SENSITIVE_PRIVATE_DOCUMENT")

    monkeypatch.setattr(app.state.store, "create", broken_create)
    # Default TestClient rethrows unhandled errors, matching a server's error logger.
    with TestClient(app) as client:
        response = client.post("/api/v1/cases", json={"entry_path": "direct"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "SENSITIVE_PRIVATE_DOCUMENT" not in response.text
    assert "SENSITIVE_PRIVATE_DOCUMENT" not in caplog.text


def test_unconfigured_llm_returns_503_without_creating_fake_messages(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "external_missing_credentials")
    case = create(client)
    response = client.post(f"/api/v1/cases/{case['id']}/messages", json={"message": "住院文件？"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLM_NOT_CONFIGURED"
    assert client.get(f"/api/v1/cases/{case['id']}").json()["messages"] == []


def test_oversized_requests_rejected_before_parser(client):
    response = client.post("/api/v1/cases", content=b"{}", headers={"content-type": "application/json", "content-length": "20000000"})
    assert response.status_code == 413


def test_rate_limit_responds_with_retry_after(tmp_path, monkeypatch):
    monkeypatch.setenv("CASE_DB_PATH", str(tmp_path / "limit.sqlite3"))
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "2")
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/health").status_code == 200
        response = client.get("/api/v1/health")
        assert response.status_code == 429
        assert response.headers["retry-after"]


def test_upload_validation_and_error_recovery(client):
    case = create(client)
    url = f"/api/v1/cases/{case['id']}/documents/application/analyze"
    for file, expected in [(("empty.pdf", b"", "application/pdf"), "EMPTY_FILE"), (("a.txt", b"fake", "text/plain"), "UNSUPPORTED_FILE_TYPE"), (("a.pdf", b"notpdf", "application/pdf"), "INVALID_FILE")]:
        response = client.post(url, files={"file": file})
        assert response.json()["error"]["code"] == expected, response.text
    assert find(client.get(f"/api/v1/cases/{case['id']}").json())["analysis"] is None


def test_upload_rejects_actual_oversized_file_and_eleven_page_pdf(client):
    import fitz

    case = create(client)
    url = f"/api/v1/cases/{case['id']}/documents/application/analyze"
    response = client.post(url, files={"file": ("oversized.pdf", b"%PDF-" + b"x" * (10 * 1024 * 1024), "application/pdf")})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    doc = fitz.open()
    for _ in range(11):
        doc.new_page()
    data = doc.tobytes()
    doc.close()
    response = client.post(url, files={"file": ("eleven.pdf", data, "application/pdf")})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "TOO_MANY_PAGES"
    assert find(client.get(f"/api/v1/cases/{case['id']}").json())["analysis"] is None


def test_grounded_conversation_requires_confirmation_before_case_updates(client):
    case = create(client, entry_path="guided", claim_type_id=None)
    response = client.post(f"/api/v1/cases/{case['id']}/messages", json={"message": "上星期車禍住院三天，想準備文件"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["response"]["is_simulated"] is False
    assert result["response"]["provider"] == "grounded_rules"
    assert result["response"]["source_references"]
    assert result["response"]["proposed_case_updates"] == {}
    assert result["response"]["pending_question"]["field"] == "surgery"
    assert result["case"]["claim_type_id"] is None
    assert len(result["case"]["messages"]) == 2
    assert result["case"]["messages"][1]["response"] == result["response"]
    for field in ("payment_method", "claim_type_id"):
        response = client.post(f"/api/v1/cases/{case['id']}/messages", json={"message": "稍後確認"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["response"]["pending_question"]["field"] == field
        assert result["case"]["claim_type_id"] is None
    assert result["response"]["proposed_case_updates"]["claim_type_id"] == "inpatient"
    assert result["response"]["proposal"]["base_revision"] == result["case"]["revision"]


def test_real_pdf_analysis_has_actual_provider_and_findings_cannot_be_washed_away(client):
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((40, 40), "Synthetic insurance claim application. Name: Demo. Policy: TEST123")
    data = doc.tobytes()
    doc.close()
    case = create(client)
    url = f"/api/v1/cases/{case['id']}/documents/application"
    response = client.post(url + "/analyze", files={"file": ("synthetic.pdf", data, "application/pdf")})
    assert response.status_code == 200, response.text
    document = find(response.json())
    assert document["analysis"]["is_simulated"] is False
    assert document["analysis"]["provider"] != "mock"
    assert document["status"] == "needs_attention"
    assert document["analysis"]["findings"]
    findings = [item["id"] for item in document["analysis"]["findings"]]
    assert client.patch(url, json={"confirmed_findings": findings, "status": "uploaded"}).status_code == 409
    changed = client.patch(url, json={"confirmed_findings": findings, "status": "uploaded", "analysis_id": document["analysis"]["analysis_id"]}).json()
    assert find(changed)["status"] == "needs_attention"
    assert find(changed)["analysis"]["findings"] == document["analysis"]["findings"]
    reset = client.patch(url, json={"status": "not_started"}).json()
    assert find(reset)["analysis"] is None
    assert find(reset)["file"] is None
