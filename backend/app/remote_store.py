"""Owner-isolated structured case storage through the private Worker endpoint.

The configured endpoint is a backend-only deployment setting. Owner cookies,
raw document content and runtime model credentials never enter its JSON body.
SQLite remains the default store; this adapter is selected explicitly by the
application factory for the Cloudflare container deployment.
"""

from datetime import datetime, timezone
import ipaddress
import os
import re
import time
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from .errors import ApiError
from .store import CaseStore


_PUBLIC_ERRORS = {
    (400, "VALIDATION_ERROR"): ("VALIDATION_ERROR", "案件儲存請求格式不正確。", 400),
    (422, "VALIDATION_ERROR"): ("VALIDATION_ERROR", "案件儲存請求格式不正確。", 422),
    (404, "CASE_NOT_FOUND"): ("CASE_NOT_FOUND", "查無案件，或案件已清除。", 404),
    (409, "CASE_EXISTS"): ("CASE_EXISTS", "案件識別碼已存在。", 409),
    (409, "CASE_CONFLICT"): ("CASE_CONFLICT", "案件已更新，請重新載入後再試。", 409),
    (413, "PAYLOAD_TOO_LARGE"): ("PAYLOAD_TOO_LARGE", "案件資料超過暫存大小上限，請建立新案件。", 413),
    (429, "CASE_LIMIT"): ("CASE_LIMIT", "暫存案件數量已達上限，請先清除不再使用的案件。", 429),
}
_FORBIDDEN_FIELDS = {
    "rawfile", "rawfiles", "filebytes", "filecontent", "rawcontent", "rawtext",
    "blob", "base64", "dataurl", "contentbytes", "filedata", "filebase64",
    "imagebase64", "documentbytes", "pdfbytes", "rawdocument", "rawdocuments",
    "key", "apikey", "llmapikey", "openrouterkey", "xopenrouterkey", "openrouterapikey",
    "openaiapikey", "providerapikey", "casestoretoken", "authorization", "proxyauthorization",
    "credentials", "credential", "secret", "clientsecret", "password", "passwd", "token",
    "accesstoken", "refreshtoken", "idtoken", "privatekey", "cookie", "setcookie",
}


def _unavailable():
    return ApiError("CASE_STORE_UNAVAILABLE", "案件暫存服務目前無法使用，請稍後重試。", 503)


class HTTPCaseStore:
    """CaseStore-compatible client with a fixed HTTPS destination and no retry.

    The transport argument is solely the HTTP boundary injection point, allowing
    contract tests without a real endpoint. Clients are short-lived so container
    shutdown does not require introducing a new store lifecycle interface.
    """

    def __init__(self, url, token, *, transport=None):
        try:
            if not isinstance(url, str) or any(ord(char) <= 32 for char in url):
                raise ValueError()
            endpoint = urlsplit(url)
            host = endpoint.hostname or ""
            labels = host.split(".")
            invalid = (
                endpoint.scheme != "https" or not host or not host.endswith(".workers.dev") or len(labels) < 3
                or endpoint.username is not None or endpoint.password is not None
                or endpoint.port not in (None, 443) or "?" in url or "#" in url or "\\" in url
                or endpoint.path != "/__internal/cases"
                or host in {"localhost", "localhost.localdomain"}
                or host.endswith((".local", ".localhost"))
                or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)
            )
            try:
                ipaddress.ip_address(host)
                invalid = True
            except ValueError:
                pass
            if invalid or not isinstance(token, str) or not token or any(not 33 <= ord(char) < 127 for char in token):
                raise ValueError()
        except (TypeError, ValueError):
            raise ApiError("INVALID_CASE_STORE_CONFIG", "案件儲存服務設定格式不正確。", 503) from None
        self._url = url
        self._token = token
        self._transport = transport

    @classmethod
    def from_environment(cls):
        # Never inspect files, use an LLM key as a fallback, or silently select
        # local storage when a remote deployment is missing its private token.
        return cls(os.getenv("CASE_STORE_URL", ""), os.getenv("CASE_STORE_TOKEN", ""))

    @staticmethod
    def _structured(case):
        item = CaseStore._structured(case)
        pending = [item]
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                for field, value in node.items():
                    normalized = re.sub(r"[_\-\s]", "", field).lower()
                    # This official checklist condition describes whether an
                    # insurer requested a form; it is a three-state flag, not
                    # an Authorization credential. Reject all other values.
                    if normalized == "insurerrequestedmedicalauthorization":
                        if not isinstance(value, str) or value not in {"yes", "no", "unknown"}:
                            raise ApiError("VALIDATION_ERROR", "案件僅能保存結構化資料與檔案中繼資料。", 422)
                        continue
                    if normalized in _FORBIDDEN_FIELDS or re.search(r"(?:apikey|token|secret|password|privatekey|authorization)$", normalized):
                        raise ApiError("VALIDATION_ERROR", "案件僅能保存結構化資料與檔案中繼資料。", 422)
                    if normalized == "file":
                        CaseStore._structured({"file": value})
                    pending.append(value)
            elif isinstance(node, list):
                pending.extend(node)
        return item

    def _request(self, payload):
        try:
            with httpx.Client(transport=self._transport, trust_env=False, follow_redirects=False, timeout=10.0) as client:
                response = client.post(self._url, json=payload, headers={"Authorization": f"Bearer {self._token}"})
        except httpx.RequestError:
            # Transport exceptions may contain request headers or response data.
            # Suppress their chain as well as their message from public errors.
            raise _unavailable() from None
        try:
            body = response.json()
        except (ValueError, RecursionError):
            raise _unavailable() from None
        if response.status_code != 200:
            error = body.get("error") if isinstance(body, dict) else None
            code = error.get("code") if isinstance(error, dict) else None
            public = _PUBLIC_ERRORS.get((response.status_code, code)) if isinstance(code, str) else None
            if public:
                raise ApiError(*public) from None
            raise _unavailable() from None
        if not isinstance(body, dict) or set(body) != {"result"}:
            raise _unavailable() from None
        return body["result"]

    def _case_result(self, result, identifier):
        try:
            item = self._structured(result)
            if CaseStore._case_id(item.get("id")) != identifier:
                raise ValueError()
            CaseStore._created_timestamp(item.get("created_at"))
            if "revision" in item and (type(item["revision"]) is not int or item["revision"] < 0):
                raise ValueError()
            return item
        except (ApiError, ValueError):
            raise _unavailable() from None

    def cleanup(self):
        """The Durable Object enforces TTL before each operation and by alarm."""
        result = self._request({"op": "cleanup"})
        if type(result) is not int or result < 0:
            raise _unavailable() from None
        return result

    def create(self, case, owner):
        owner_hash = CaseStore._owner_hash(owner)
        item = self._structured(case)
        item.setdefault("id", str(uuid4()))
        CaseStore._case_id(item["id"])
        item.setdefault("created_at", datetime.fromtimestamp(time.time(), timezone.utc).isoformat())
        item.setdefault("updated_at", item["created_at"])
        CaseStore._created_timestamp(item["created_at"])
        if "revision" in item and (type(item["revision"]) is not int or item["revision"] != 0):
            raise ApiError("VALIDATION_ERROR", "案件版本格式無效。", 422)
        result = self._request({"op": "create", "owner_hash": owner_hash, "case": item})
        return self._case_result(result, item["id"])

    def get(self, id, owner):
        owner_hash = CaseStore._owner_hash(owner)
        identifier = CaseStore._case_id(id)
        result = self._request({"op": "get", "owner_hash": owner_hash, "id": identifier})
        return None if result is None else self._case_result(result, identifier)

    def save(self, case, owner):
        owner_hash = CaseStore._owner_hash(owner)
        item = self._structured(case)
        identifier = CaseStore._case_id(item.get("id"))
        payload = {"op": "save", "owner_hash": owner_hash, "case": item}
        if "revision" in item:
            if type(item["revision"]) is not int or item["revision"] < 1:
                raise ApiError("VALIDATION_ERROR", "案件版本格式無效。", 422)
            payload["expected_revision"] = item["revision"] - 1
        result = self._request(payload)
        return self._case_result(result, identifier)

    def delete(self, id, owner):
        owner_hash = CaseStore._owner_hash(owner)
        identifier = CaseStore._case_id(id)
        result = self._request({"op": "delete", "owner_hash": owner_hash, "id": identifier})
        if type(result) is not bool:
            raise _unavailable() from None
        return result
