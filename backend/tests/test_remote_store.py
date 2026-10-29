"""HTTP case-store contract tests; no network, credentials or database is used."""

from datetime import datetime, timezone
from hashlib import sha256
import importlib
import json
import traceback
from uuid import UUID, uuid4

import httpx
import pytest

from backend.app.errors import ApiError


URL = "https://synthetic-claim-store.workers.dev/__internal/cases"
TOKEN = "synthetic-private-case-store-token"
OWNER = "synthetic-owner-cookie-do-not-forward"


def module():
    try:
        return importlib.import_module("backend.app.remote_store")
    except ImportError as error:
        pytest.fail(f"HTTPCaseStore is not implemented: {error}")


def case():
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid4()), "entry_path": "direct", "claim_type_id": "inpatient",
        "conditions": {"cause": "unknown", "surgery": "unknown"},
        "documents": [], "messages": [], "revision": 0,
        "created_at": now, "updated_at": now,
    }


@pytest.mark.parametrize('value', ['yes', 'no', 'unknown'])
def test_official_medical_authorization_condition_is_not_a_credential(value):
    item = case()
    item['conditions']['insurer_requested_medical_authorization'] = value
    item['dialogue_state'] = {'conditions': dict(item['conditions'])}
    store, requests = store_with_response(lambda request: httpx.Response(200, json={'result': json.loads(request.content)['case']}))
    assert store.create(item, OWNER) == item
    assert len(requests) == 1


@pytest.mark.parametrize('value', ['synthetic-private-credential', None, {}, [], True])
def test_medical_authorization_condition_does_not_allow_arbitrary_secret_values(value):
    item = case()
    item['conditions']['insurer_requested_medical_authorization'] = value
    store, requests = store_with_response(item)
    with pytest.raises(ApiError) as caught:
        store.create(item, OWNER)
    assert caught.value.code == 'VALIDATION_ERROR'
    assert requests == []


def store_with_response(response, requests=None):
    requests = requests if requests is not None else []

    def handle(request):
        requests.append(request)
        return response(request) if callable(response) else httpx.Response(200, json={"result": response})

    return module().HTTPCaseStore(URL, TOKEN, transport=httpx.MockTransport(handle)), requests


def assert_safe_error(error, code="CASE_STORE_UNAVAILABLE", status=503):
    assert isinstance(error, ApiError)
    assert (error.code, error.status) == (code, status)
    public_error = " ".join((str(error), repr(error), error.message,
                             "".join(traceback.format_exception(error))))
    assert TOKEN not in public_error
    assert "SYNTHETIC-MEDICAL-CONTENT" not in public_error


def test_create_posts_only_hashed_owner_with_auth_in_header_and_detached_data():
    item = case()
    store, requests = store_with_response(item)
    created = store.create(item, OWNER)
    assert created == item
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == URL
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert "cookie" not in request.headers
    payload = json.loads(request.content)
    assert payload == {"op": "create", "owner_hash": sha256(OWNER.encode()).hexdigest(), "case": item}
    assert OWNER.encode() not in request.content
    assert TOKEN.encode() not in request.content
    created["conditions"]["cause"] = "accident"
    item["conditions"]["surgery"] = "yes"
    assert payload["case"]["conditions"] == {"cause": "unknown", "surgery": "unknown"}


def test_create_supplies_uuid_and_utc_timestamp_before_sending(monkeypatch):
    monkeypatch.setattr(module().time, "time", lambda: 1793275200.0)
    item = case()
    for name in ("id", "created_at", "updated_at"):
        item.pop(name)
    store, requests = store_with_response(lambda request: httpx.Response(200, json={"result": json.loads(request.content)["case"]}))
    created = store.create(item, OWNER)
    assert UUID(created["id"])
    assert created["created_at"] == "2026-10-29T12:00:00+00:00"
    assert created["updated_at"] == created["created_at"]
    assert "id" not in item
    assert json.loads(requests[0].content)["case"] == created


@pytest.mark.parametrize("operation,result", [("get", None), ("delete", False)])
def test_missing_case_and_unowned_case_return_store_compatible_values(operation, result):
    store, requests = store_with_response(result)
    identifier = str(uuid4())
    assert getattr(store, operation)(identifier, OWNER) is result
    assert json.loads(requests[0].content) == {
        "op": operation, "owner_hash": sha256(OWNER.encode()).hexdigest(), "id": identifier,
    }


def test_get_returns_detached_structured_case():
    item = case()
    store, requests = store_with_response(item)
    first = store.get(item["id"], OWNER)
    first["conditions"]["cause"] = "accident"
    assert store.get(item["id"], OWNER)["conditions"]["cause"] == "unknown"
    assert len(requests) == 2


def test_owner_isolation_uses_different_hashes_and_never_sends_original_cookie():
    item = case()

    def respond(request):
        owner_hash = json.loads(request.content)["owner_hash"]
        return httpx.Response(200, json={"result": item if owner_hash == sha256(OWNER.encode()).hexdigest() else None})

    store, requests = store_with_response(respond)
    assert store.get(item["id"], OWNER) == item
    assert store.get(item["id"], "other-owner-cookie") is None
    assert len({json.loads(request.content)["owner_hash"] for request in requests}) == 2
    assert all(OWNER.encode() not in request.content and b"other-owner-cookie" not in request.content for request in requests)


def test_save_sends_compare_and_swap_and_keeps_remote_original_creation_time():
    item = case()
    original_time = item["created_at"]
    item["revision"] = 2
    item["created_at"] = "2099-01-01T00:00:00Z"
    returned = {**item, "created_at": original_time}
    store, requests = store_with_response(returned)
    saved = store.save(item, OWNER)
    assert saved == returned
    assert saved["created_at"] == original_time
    assert json.loads(requests[0].content) == {
        "op": "save", "owner_hash": sha256(OWNER.encode()).hexdigest(), "case": item, "expected_revision": 1,
    }


def test_legacy_case_without_revision_remains_save_compatible():
    item = case()
    item.pop("revision")
    store, requests = store_with_response(item)
    assert store.save(item, OWNER) == item
    assert "expected_revision" not in json.loads(requests[0].content)


def test_delete_and_cleanup_forward_boolean_and_count_without_owner_for_cleanup():
    responses = iter([True, 3, 0])
    store, requests = store_with_response(lambda _: httpx.Response(200, json={"result": next(responses)}))
    assert store.delete(str(uuid4()), OWNER) is True
    assert store.cleanup() == 3
    assert store.cleanup() == 0
    assert json.loads(requests[1].content) == {"op": "cleanup"}
    assert json.loads(requests[2].content) == {"op": "cleanup"}


@pytest.mark.parametrize("operation", ["create", "save"])
@pytest.mark.parametrize("field", ["raw_file", "file_bytes", "file_content", "raw_content", "raw_text", "blob", "base64", "data_url", "content_bytes", "RAW_TEXT"])
def test_raw_content_is_rejected_before_any_request(operation, field):
    item = case()
    item["documents"] = [{"id": "application", field: "SYNTHETIC-MEDICAL-CONTENT"}]
    store, requests = store_with_response(item)
    with pytest.raises(ApiError) as caught:
        getattr(store, operation)(item, OWNER)
    assert caught.value.code == "VALIDATION_ERROR"
    assert requests == []


@pytest.mark.parametrize("field", [
    "api_key", "LLM_API_KEY", "case_store_token", "authorization", "x_openrouter_key",
    "apiKey", "Api Key", "cookie", "client_secret", "password", "access_token", "rawFile", "raw-file",
    "gemini_api_key", "x_api_key", "bearerToken", "session_token", "shared_secret",
])
def test_credentials_cannot_be_smuggled_into_case_payload(field):
    item = case()
    item["nested"] = [{field: TOKEN}]
    store, requests = store_with_response(item)
    with pytest.raises(ApiError) as caught:
        store.create(item, OWNER)
    assert_safe_error(caught.value, "VALIDATION_ERROR", 422)
    assert requests == []


@pytest.mark.parametrize("bad_case", [None, [], {"documents": [b"raw"]}, {"value": float("nan")}, {"documents": [{"file": {"content": "raw"}}]}])
def test_non_json_and_file_content_payloads_are_rejected_locally(bad_case):
    store, requests = store_with_response(None)
    with pytest.raises(ApiError) as caught:
        store.create(bad_case, OWNER)
    assert caught.value.code == "VALIDATION_ERROR"
    assert requests == []


@pytest.mark.parametrize("field", ["FILE", "File", "f_i_l_e"])
def test_normalized_file_field_cannot_bypass_metadata_only_validation(field):
    item = case()
    item["documents"] = [{field: "SYNTHETIC-MEDICAL-CONTENT"}]
    store, requests = store_with_response(item)
    with pytest.raises(ApiError) as caught:
        store.create(item, OWNER)
    assert caught.value.code == "VALIDATION_ERROR"
    assert requests == []


@pytest.mark.parametrize("operation", ["create", "get", "save", "delete"])
def test_invalid_owner_is_rejected_without_request(operation):
    store, requests = store_with_response(None)
    argument = case() if operation in {"create", "save"} else str(uuid4())
    with pytest.raises(ApiError) as caught:
        getattr(store, operation)(argument, "")
    assert caught.value.code == "VALIDATION_ERROR"
    assert requests == []


@pytest.mark.parametrize("operation", ["create", "get", "save", "delete"])
def test_invalid_uuid_is_rejected_before_any_request(operation):
    item = case()
    item["id"] = "../../other-case"
    store, requests = store_with_response(None)
    with pytest.raises(ApiError) as caught:
        getattr(store, operation)(item if operation in {"create", "save"} else item["id"], OWNER)
    assert caught.value.code == "VALIDATION_ERROR"
    assert requests == []


@pytest.mark.parametrize("timestamp", [None, "bad", "2026-10-29T12:00:00", 1793275200])
def test_create_rejects_missing_timezone_or_invalid_timestamp(timestamp):
    item = case()
    item["created_at"] = timestamp
    store, requests = store_with_response(item)
    with pytest.raises(ApiError) as caught:
        store.create(item, OWNER)
    assert caught.value.code == "VALIDATION_ERROR"
    assert requests == []


@pytest.mark.parametrize("revision", [0, -1, True, 1.5, "1", None])
def test_save_rejects_invalid_or_non_incremented_revision(revision):
    item = case()
    item["revision"] = revision
    store, requests = store_with_response(item)
    with pytest.raises(ApiError) as caught:
        store.save(item, OWNER)
    assert caught.value.code == "VALIDATION_ERROR"
    assert requests == []


@pytest.mark.parametrize("url", [
    "http://synthetic.workers.dev/__internal/cases", "https://synthetic.workers.dev/other",
    "https://synthetic.workers.dev/__internal/cases/", "https://synthetic.workers.dev/__internal/cases?token=hidden",
    "https://synthetic.workers.dev/__internal/cases#fragment", "https://user:password@synthetic.workers.dev/__internal/cases",
    "https://synthetic.workers.dev:8443/__internal/cases", "https://127.0.0.1/__internal/cases",
    "https://[::1]/__internal/cases", "https://localhost/__internal/cases", "https://store.local/__internal/cases",
    "https://synthetic.workers.dev\\@evil.test/__internal/cases", "https://synthetic.workers.dev/__internal/../cases",
    "https://synthetic.workers.dev/__internal/%63ases", "https://synthetic.workers.dev/__internal/cases\n",
    "https://arbitrary.example/__internal/cases", "https://workers.dev/__internal/cases",
    "https://synthetic.workers.dev.evil.test/__internal/cases", "", None,
])
def test_unsafe_or_non_fixed_internal_endpoint_is_rejected(url):
    with pytest.raises(ApiError) as caught:
        module().HTTPCaseStore(url, TOKEN)
    assert_safe_error(caught.value, "INVALID_CASE_STORE_CONFIG", 503)


@pytest.mark.parametrize("token", [None, "", " ", "has space", "synthetic\r\nInjected: header"])
def test_missing_or_header_unsafe_token_fails_closed(token):
    with pytest.raises(ApiError) as caught:
        module().HTTPCaseStore(URL, token)
    assert_safe_error(caught.value, "INVALID_CASE_STORE_CONFIG", 503)


def test_environment_uses_only_case_store_settings_and_repr_omits_token(monkeypatch):
    monkeypatch.setenv("CASE_STORE_URL", URL)
    monkeypatch.setenv("CASE_STORE_TOKEN", TOKEN)
    monkeypatch.setenv("LLM_API_KEY", "must-not-be-used-as-storage-auth")
    store = module().HTTPCaseStore.from_environment()
    assert TOKEN not in repr(store)
    monkeypatch.delenv("CASE_STORE_TOKEN")
    with pytest.raises(ApiError) as caught:
        module().HTTPCaseStore.from_environment()
    assert_safe_error(caught.value, "INVALID_CASE_STORE_CONFIG", 503)


def test_request_has_fixed_timeout_ignores_proxy_env_and_does_not_retry(monkeypatch):
    original_client = httpx.Client
    options = []

    def capture_client(**kwargs):
        options.append(kwargs)
        return original_client(**kwargs)

    monkeypatch.setattr(httpx, "Client", capture_client)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    store, requests = store_with_response(None)
    assert store.get(str(uuid4()), OWNER) is None
    assert options[0]["trust_env"] is False
    assert options[0]["follow_redirects"] is False
    assert requests[0].extensions["timeout"] == {"connect": 10.0, "read": 10.0, "write": 10.0, "pool": 10.0}


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_redirect_never_forwards_token_or_request_to_another_url(status):
    store, requests = store_with_response(lambda _: httpx.Response(status, headers={"location": "https://evil.test/steal"}))
    with pytest.raises(ApiError) as caught:
        store.cleanup()
    assert_safe_error(caught.value)
    assert len(requests) == 1
    assert str(requests[0].url) == URL


@pytest.mark.parametrize("status,code,want_code,want_status", [
    (400, "VALIDATION_ERROR", "VALIDATION_ERROR", 400),
    (404, "CASE_NOT_FOUND", "CASE_NOT_FOUND", 404),
    (409, "CASE_EXISTS", "CASE_EXISTS", 409), (409, "CASE_CONFLICT", "CASE_CONFLICT", 409),
    (429, "CASE_LIMIT", "CASE_LIMIT", 429),
    (413, "PAYLOAD_TOO_LARGE", "PAYLOAD_TOO_LARGE", 413),
    (401, "UNAUTHORIZED", "CASE_STORE_UNAVAILABLE", 503),
    (403, "FORBIDDEN", "CASE_STORE_UNAVAILABLE", 503),
    (500, "INTERNAL_ERROR", "CASE_STORE_UNAVAILABLE", 503),
    (502, "CASE_NOT_FOUND", "CASE_STORE_UNAVAILABLE", 503),
    (409, "SYNTHETIC-MEDICAL-CONTENT", "CASE_STORE_UNAVAILABLE", 503),
])
def test_upstream_errors_have_fixed_local_messages_without_upstream_content(status, code, want_code, want_status):
    response = lambda _: httpx.Response(status, json={"error": {"code": code, "message": f"{TOKEN} SYNTHETIC-MEDICAL-CONTENT"}})
    store, _ = store_with_response(response)
    with pytest.raises(ApiError) as caught:
        store.cleanup()
    assert_safe_error(caught.value, want_code, want_status)


@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError])
def test_transport_failures_are_sanitized_without_retries(error_type):
    def fail(request):
        raise error_type(f"{TOKEN} SYNTHETIC-MEDICAL-CONTENT", request=request)

    store, requests = store_with_response(fail)
    with pytest.raises(ApiError) as caught:
        store.cleanup()
    assert_safe_error(caught.value)
    assert len(requests) == 1


@pytest.mark.parametrize("operation,result", [
    ("cleanup", True), ("cleanup", -1), ("cleanup", "1"), ("delete", 1), ("get", []),
    ("create", None), ("save", []), ("get", {"id": "invalid", "created_at": "bad"}),
    ("get", {"id": str(uuid4()), "created_at": "2026-10-29T12:00:00Z", "raw_text": "SYNTHETIC-MEDICAL-CONTENT"}),
])
def test_malformed_success_result_is_not_exposed(operation, result):
    store, _ = store_with_response(result)
    argument = case() if operation in {"create", "save"} else str(uuid4())
    if operation == "save":
        argument["revision"] = 1
    with pytest.raises(ApiError) as caught:
        getattr(store, operation)(*(() if operation == "cleanup" else (argument, OWNER)))
    assert_safe_error(caught.value)


@pytest.mark.parametrize("response", [
    lambda _: httpx.Response(200, content="not json"),
    lambda _: httpx.Response(200, json={}), lambda _: httpx.Response(200, json=[]),
    lambda _: httpx.Response(201, json={"result": 1}),
])
def test_invalid_response_envelope_and_unexpected_status_fail_closed(response):
    store, _ = store_with_response(response)
    with pytest.raises(ApiError) as caught:
        store.cleanup()
    assert_safe_error(caught.value)
