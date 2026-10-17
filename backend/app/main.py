"""同源理賠準備服務；不提供正式送件、資格判定或給付計算。"""
import asyncio
import copy
import inspect
import mimetypes
import os
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from .errors import ApiError
from .models import Analysis, AssistantResponse, Case, Conditions, CreateCase, DocumentUpdate, MessageInput, UpdateCase
from .registry import get_source, validate_official_url
from .rules import build_checklist, get_claim_types
from .store import CaseStore

ROOT = Path(__file__).resolve().parents[2]
MAX_FILE_BYTES = 10 * 1024 * 1024
COOKIE_NAME = "claim_session"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def error_response(code: str, message: str, status: int, headers=None):
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status, headers=headers)


class RequestProtection:
    """在 multipart parser 前限制原始 request 大小；不信任轉送的 IP 標頭。"""

    def __init__(self, app, *, allowed_origins: set[str], limit: int, secure_cookie: bool):
        self.app = app
        self.allowed_origins = allowed_origins
        self.limit = max(1, limit)
        self.secure_cookie = secure_cookie
        self.requests: dict[str, deque] = defaultdict(deque)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = scope.get("path", "").startswith("/api/")
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        token = None
        if is_api:
            raw_cookie = headers.get(b"cookie", b"").decode("latin-1")
            for part in raw_cookie.split(";"):
                key, _, value = part.strip().partition("=")
                if key == COOKIE_NAME and re.fullmatch(r"[A-Za-z0-9_-]{43}", value):
                    token = value
                    break
        new_session = is_api and token is None
        token = token or secrets.token_urlsafe(32)
        scope.setdefault("state", {})["owner"] = token
        response_started = False

        async def secure_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                response_headers = list(message.get("headers", []))
                response_headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    (b"content-security-policy", b"default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; worker-src 'self' blob:; connect-src 'self'; object-src 'self' blob:; frame-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"),
                ])
                if is_api:
                    response_headers.append((b"cache-control", b"no-store"))
                if new_session:
                    secure = "; Secure" if self.secure_cookie or scope.get("scheme") == "https" else ""
                    cookie = f"{COOKIE_NAME}={token}; HttpOnly; Path=/; Max-Age=86400; SameSite=strict{secure}"
                    response_headers.append((b"set-cookie", cookie.encode("ascii")))
                message["headers"] = response_headers
            await send(message)

        async def reject(code, message, status, response_headers=None):
            await error_response(code, message, status, response_headers)(scope, receive, secure_send)

        async def invoke(app_receive):
            try:
                await self.app(scope, app_receive, secure_send)
            except Exception:
                # 不讓含文件／供應商內容的例外文字進入 ASGI server 堆疊日誌。
                if not response_started:
                    await reject("INTERNAL_ERROR", "服務暫時發生問題，請稍後重試。", 500)

        if not is_api:
            await invoke(receive)
            return
        if sum(len(key) + len(value) for key, value in scope.get("headers", [])) > 16384:
            await reject("HEADERS_TOO_LARGE", "請求標頭過大。", 431)
            return
        origin = headers.get(b"origin", b"").decode("latin-1")
        fetch_site = headers.get(b"sec-fetch-site", b"").decode("latin-1")
        if (origin and origin not in self.allowed_origins) or fetch_site == "cross-site":
            await reject("ORIGIN_NOT_ALLOWED", "此來源無法存取案件服務。", 403)
            return
        now = time.monotonic()
        peer = (scope.get("client") or ("unknown",))[0]
        if len(self.requests) > 2048:
            self.requests = defaultdict(deque, {key: values for key, values in self.requests.items() if values and values[-1] > now - 60})
        timestamps = self.requests[peer]
        while timestamps and timestamps[0] <= now - 60:
            timestamps.popleft()
        if len(timestamps) >= self.limit:
            await reject("RATE_LIMITED", "操作過於頻繁，請稍後重試。", 429, {"Retry-After": "60"})
            return
        timestamps.append(now)
        body_limit = MAX_FILE_BYTES + 65536 if scope["path"].endswith("/analyze") else 65536
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            await reject("VALIDATION_ERROR", "請求格式不正確。", 400)
            return
        if declared < 0 or declared > body_limit:
            await reject("FILE_TOO_LARGE", "檔案不可超過 10 MB，請求內容超出限制。", 413)
            return
        # 最多保留 10 MB + multipart 邊界；解析後不持久保存 raw body。
        body = bytearray()
        while True:
            part = await receive()
            if part["type"] == "http.disconnect":
                return
            if part["type"] != "http.request":
                continue
            body.extend(part.get("body", b""))
            if len(body) > body_limit:
                await reject("FILE_TOO_LARGE", "檔案不可超過 10 MB。", 413)
                return
            if not part.get("more_body", False):
                break
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await invoke(replay)


def _public_provider_error(error: Exception) -> ApiError:
    if all(hasattr(error, name) for name in ("code", "message", "status")):
        return ApiError(error.code, error.message, error.status)
    return ApiError("PROVIDER_UNAVAILABLE", "分析服務暫時無法使用，請稍後重試。", 503)


def create_app() -> FastAPI:
    # Windows 登錄檔可將 .mjs 誤設為 text/plain；module worker 與 WASM
    # 必須使用瀏覽器接受的固定 MIME，不能依賴主機的系統關聯設定。
    mimetypes.add_type("text/javascript", ".mjs")
    mimetypes.add_type("application/wasm", ".wasm")
    db_path = Path(os.getenv("CASE_DB_PATH", str(ROOT / ".local" / "cases.sqlite3")))
    store = CaseStore(db_path)

    @asynccontextmanager
    async def lifespan(application):
        store.cleanup()

        async def janitor():
            while True:
                await asyncio.sleep(300)
                await run_in_threadpool(store.cleanup)

        task = asyncio.create_task(janitor())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    app = FastAPI(title="理賠文件準備 API", version="1.0.0", lifespan=lifespan)
    app.state.store = store
    # 固定數量鎖避免任意 case ID 請求耗盡記憶體；同一案件寫入保持序列。
    locks = [asyncio.Lock() for _ in range(128)]

    def lock_for(identifier):
        return locks[hash(identifier) % len(locks)]

    origins = {item.strip().rstrip("/") for item in os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5174,http://localhost:5174").split(",") if item.strip()}
    app.add_middleware(CORSMiddleware, allow_origins=sorted(origins), allow_credentials=True,
                       allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Content-Type"])
    app.add_middleware(RequestProtection, allowed_origins=origins,
                       limit=int(os.getenv("RATE_LIMIT_REQUESTS", "120")), secure_cookie=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true")

    @app.exception_handler(ApiError)
    async def api_error_handler(request, error):
        return error_response(error.code, error.message, error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request, error):
        return error_response("VALIDATION_ERROR", "輸入資料格式不正確，請確認欄位與選項。", 422)

    @app.exception_handler(HTTPException)
    async def http_error_handler(request, error):
        return error_response("NOT_FOUND" if error.status_code == 404 else "REQUEST_ERROR", "找不到此服務。" if error.status_code == 404 else "請求無法處理。", error.status_code)

    @app.exception_handler(Exception)
    async def unknown_error_handler(request, error):
        return error_response("INTERNAL_ERROR", "服務暫時發生問題，請稍後重試。", 500)

    def read_case(identifier, request):
        item = store.get(identifier, request.state.owner)
        if item is None:
            raise ApiError("CASE_NOT_FOUND", "找不到此案件，請重新開始。", 404)
        return item

    def find_document(item, identifier):
        document = next((doc for doc in item["documents"] if doc["id"] == identifier), None)
        if document is None:
            raise ApiError("DOCUMENT_NOT_FOUND", "找不到這份案件文件。", 404)
        return document

    def save_case(item, request):
        item["updated_at"] = utc_now()
        Case.model_validate(item)
        return store.save(item, request.state.owner)

    @app.get("/api/v1/health")
    async def health():
        try:
            from .ai.conversation import provider_status
            llm_status = provider_status()
            if inspect.isawaitable(llm_status):
                llm_status = await llm_status
        except ImportError:
            llm_status = {"llm_provider": "unavailable", "llm_configured": False}
        try:
            from .ocr.analyzer import provider_status as ocr_status_fn
            ocr_status = ocr_status_fn()
        except ImportError:
            ocr_status = {"ocr_provider": "unavailable"}
        if isinstance(ocr_status, str):
            ocr_status = {"ocr_provider": ocr_status}
        return {"status": "ok", "service_mode": "api", **llm_status, **ocr_status}

    @app.get("/api/v1/claim-types")
    async def claim_types():
        return get_claim_types()

    @app.post("/api/v1/cases", status_code=201)
    async def create_case(data: CreateCase, request: Request):
        timestamp = utc_now()
        item = {"id": str(uuid.uuid4()), "entry_path": data.entry_path, "claim_type_id": data.claim_type_id,
                "conditions": data.conditions.model_dump(), "documents": [], "messages": [],
                "created_at": timestamp, "updated_at": timestamp}
        item["documents"] = build_checklist(item)
        Case.model_validate(item)
        return store.create(item, request.state.owner)

    @app.get("/api/v1/cases/{case_id}")
    async def get_case(case_id: str, request: Request):
        return read_case(case_id, request)

    @app.patch("/api/v1/cases/{case_id}")
    async def update_case(case_id: str, data: UpdateCase, request: Request):
        async with lock_for(case_id):
            item = read_case(case_id, request)
            if "claim_type_id" in data.model_fields_set:
                item["claim_type_id"] = data.claim_type_id
            if data.conditions is not None:
                item["conditions"].update(data.conditions.model_dump(exclude_unset=True))
            item["documents"] = build_checklist(item, item["documents"])
            return save_case(item, request)

    @app.get("/api/v1/cases/{case_id}/checklist")
    async def checklist(case_id: str, request: Request):
        return read_case(case_id, request)["documents"]

    @app.post("/api/v1/cases/{case_id}/messages")
    async def send_message(case_id: str, data: MessageInput, request: Request):
        async with lock_for(case_id):
            item = read_case(case_id, request)
            if data.document_id:
                find_document(item, data.document_id)
            if len(item["messages"]) >= 200:
                raise ApiError("MESSAGE_LIMIT", "此案件已達 100 次對話上限，請重新建立展示案件。", 429)
            try:
                from .ai.conversation import respond
                raw = await asyncio.wait_for(respond(copy.deepcopy(item), data.message, data.document_id), timeout=45)
                response = AssistantResponse.model_validate(raw).model_dump(exclude_unset=True)
                if response["is_simulated"]:
                    raise ApiError("INVALID_PROVIDER_RESPONSE", "真實服務不可回傳模擬結果。", 503)
                for source in response["source_references"]:
                    validate_official_url(source["official_url"])
                    verified = get_source(source["source_id"])
                    if source["official_url"] != verified["official_url"]:
                        raise ApiError("INVALID_PROVIDER_RESPONSE", "回答來源未通過查核。", 503)
            except ApiError:
                raise
            except (ImportError, TimeoutError):
                raise ApiError("PROVIDER_UNAVAILABLE", "對話服務暫時無法使用，請稍後重試。", 503) from None
            except ValidationError:
                raise ApiError("INVALID_PROVIDER_RESPONSE", "對話服務回傳格式不正確，請稍後重試。", 503) from None
            except Exception as error:
                raise _public_provider_error(error) from None
            timestamp = utc_now()
            item["messages"].extend([
                {"id": str(uuid.uuid4()), "role": "user", "content": data.message, "created_at": timestamp},
                {"id": str(uuid.uuid4()), "role": "assistant", "content": response["message"], "response": response, "created_at": timestamp},
            ])
            return {"case": save_case(item, request), "response": response}

    @app.patch("/api/v1/cases/{case_id}/documents/{document_id}")
    async def update_document(case_id: str, document_id: str, data: DocumentUpdate, request: Request):
        async with lock_for(case_id):
            item = read_case(case_id, request)
            doc = find_document(item, document_id)
            if "status" in data.model_fields_set:
                if data.status not in {"not_started", "uploaded", "not_applicable"}:
                    raise ApiError("INVALID_DOCUMENT_STATUS", "分析狀態由文件檢查產生，不能直接手動標記通過。")
                if data.status == "not_applicable" and doc["requirement_type"] == "required":
                    raise ApiError("REQUIRED_DOCUMENT", "必要文件不能標為不適用，請向官方確認。")
                uncertain = doc.get("analysis") and (doc["analysis"]["findings"] or doc["analysis"]["requires_human_review"] or doc["analysis"]["analysis_status"] == "uncertain")
                doc["status"] = "needs_attention" if data.status == "uploaded" and uncertain else data.status
                if data.status == "not_started":
                    doc.update(analysis=None, confirmed_findings=[], file=None)
            if "confirmed_findings" in data.model_fields_set:
                valid_ids = {finding["id"] for finding in (doc.get("analysis") or {}).get("findings", [])}
                if data.confirmed_findings is None or any(identifier not in valid_ids for identifier in data.confirmed_findings):
                    raise ApiError("INVALID_FINDING", "只能確認本次分析中存在的待確認項目。")
                doc["confirmed_findings"] = list(dict.fromkeys(data.confirmed_findings))
            return save_case(item, request)

    @app.post("/api/v1/cases/{case_id}/documents/{document_id}/analyze")
    async def analyze(case_id: str, document_id: str, request: Request, file: UploadFile = File(...)):
        try:
            async with lock_for(case_id):
                item = read_case(case_id, request)
                doc = find_document(item, document_id)
                if doc["status"] == "not_applicable":
                    raise ApiError("DOCUMENT_NOT_APPLICABLE", "此文件目前不適用，請先重新確認案件條件。")
                data = await file.read(MAX_FILE_BYTES + 1)
                if not data:
                    raise ApiError("EMPTY_FILE", "檔案內容為空，請重新選擇。")
                if len(data) > MAX_FILE_BYTES:
                    raise ApiError("FILE_TOO_LARGE", "檔案不可超過 10 MB。", 413)
                filename = re.split(r"[/\\]", file.filename or "")[-1][:255]
                content_type = file.content_type or ""
                extension = filename.rsplit(".", 1)[-1].lower()
                types = {"application/pdf": {"pdf"}, "image/jpeg": {"jpg", "jpeg"}, "image/png": {"png"}}
                if content_type not in types or extension not in types[content_type]:
                    raise ApiError("UNSUPPORTED_FILE_TYPE", "僅支援 PDF、JPG、PNG，副檔名必須與格式一致。", 415)
                signatures = {"application/pdf": data.startswith(b"%PDF-"), "image/jpeg": data.startswith(b"\xff\xd8\xff"), "image/png": data.startswith(b"\x89PNG\r\n\x1a\n")}
                if not signatures[content_type]:
                    raise ApiError("INVALID_FILE", "檔案內容與宣告格式不符，請選擇有效文件。")
                try:
                    from .ocr.analyzer import analyze_document
                    raw = await asyncio.wait_for(run_in_threadpool(analyze_document, data, filename, content_type, copy.deepcopy(doc)), timeout=90)
                    result = Analysis.model_validate(raw).model_dump()
                    if result["is_simulated"] or result["document_id"] != document_id:
                        raise ApiError("INVALID_PROVIDER_RESPONSE", "分析服務回傳資料未通過查核。", 503)
                except ApiError:
                    raise
                except ImportError:
                    raise ApiError("OCR_UNAVAILABLE", "OCR 服務尚未可用，請稍後重試。", 503) from None
                except TimeoutError:
                    raise ApiError("OCR_TIMEOUT", "文件分析逾時，請縮減檔案或稍後重試。", 503) from None
                except ValidationError:
                    raise ApiError("INVALID_PROVIDER_RESPONSE", "分析服務回傳格式不正確，請稍後重試。", 503) from None
                except Exception as error:
                    raise _public_provider_error(error) from None
                doc["analysis"] = result
                doc["file"] = {"name": filename, "type": content_type, "size": len(data)}
                doc["confirmed_findings"] = []
                doc["status"] = "needs_attention" if result["findings"] or result["requires_human_review"] or result["analysis_status"] == "uncertain" or result["confidence"] < 0.8 else "precheck_passed"
                return save_case(item, request)
        finally:
            await file.close()

    @app.get("/api/v1/sources/{source_id}")
    async def source(source_id: str):
        return get_source(source_id)

    @app.delete("/api/v1/cases/{case_id}")
    async def delete_case(case_id: str, request: Request):
        async with lock_for(case_id):
            read_case(case_id, request)
            store.delete(case_id, request.state.owner)
            return {"deleted": True, "id": case_id}

    dist = ROOT / "dist"
    for folder in ("assets", "pdfjs"):
        if (dist / folder).is_dir():
            app.mount(f"/{folder}", StaticFiles(directory=dist / folder, check_dir=True), name=folder)

    @app.get("/", include_in_schema=False)
    async def frontend():
        if not (dist / "index.html").is_file():
            raise ApiError("FRONTEND_UNAVAILABLE", "前端尚未建置，請先執行 npm run build。", 503)
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
