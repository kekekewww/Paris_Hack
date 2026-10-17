"""Real, local OCR. Never infer eligibility or verify a signature.

Only the selected application fields are inspected. Finding references point to
the verified official application, page 1; conditional FATCA pages are not made
universally mandatory. Uploaded bytes and extracted text are never persisted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import PurePath
import importlib.util
import logging
import re
import threading
import time
import uuid
import unicodedata
import warnings

import pymupdf as fitz
import numpy as np
from PIL import Image, UnidentifiedImageError


MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 10
MAX_IMAGE_PIXELS = 20_000_000
MAX_SECONDS = 45
_engine = None
_engine_lock = threading.Lock()
_logger = logging.getLogger(__name__)
_EXTENSIONS = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
_DISCLAIMER = "僅為指定欄位的初步可辨識性檢查；非正式理賠審核，不驗證文件、身分或簽名真偽。欄位適用性及應備文件請依官方表單、保單與承辦人確認。"


class OCRValidationError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def provider_status():
    return {"ocr_provider": "pymupdf+rapidocr" if importlib.util.find_spec("rapidocr_onnxruntime") else "pymupdf; image_ocr_unavailable"}


@dataclass
class TextLine:
    text: str
    confidence: float
    box: dict


def _box(page, x, y, width, height):
    x, y = max(0.0, min(0.9999, float(x))), max(0.0, min(0.9999, float(y)))
    return {"page_number": page, "x": round(x, 6), "y": round(y, 6), "width": round(max(0.0001, min(1 - x, float(width))), 6), "height": round(max(0.0001, min(1 - y, float(height))), 6)}


def _validate_upload(data, filename, content_type):
    if not data:
        raise OCRValidationError("EMPTY_FILE", "檔案是空的，請重新選擇 PDF、JPG 或 PNG。")
    if len(data) > MAX_BYTES:
        raise OCRValidationError("FILE_TOO_LARGE", "檔案超過 10 MB 上限。", 413)
    extension = PurePath(filename or "").suffix.lower()
    mime = (content_type or "").lower().strip()
    if extension not in _EXTENSIONS or mime not in _EXTENSIONS.values():
        raise OCRValidationError("UNSUPPORTED_FILE_TYPE", "僅接受 PDF、JPG 與 PNG。", 415)
    detected = "application/pdf" if data.startswith(b"%PDF-") else "image/png" if data.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if data.startswith(b"\xff\xd8\xff") else None
    if detected != mime or _EXTENSIONS[extension] != mime:
        raise OCRValidationError("INVALID_FILE", "檔案內容、格式與副檔名不一致，請使用原始 PDF、JPG 或 PNG。")
    return mime


def _check_time(start):
    if time.monotonic() - start > MAX_SECONDS:
        raise OCRValidationError("OCR_TIMEOUT", "文件辨識超時，請改傳較少頁或較清楚的文件後重試。", 503)


def _log_runtime_failure(error):
    """Log code locations only; never render the exception or frame locals."""
    frames = []
    traceback = error.__traceback__
    while traceback is not None:
        code = traceback.tb_frame.f_code
        frames.append(f"{PurePath(code.co_filename).name}:{code.co_name}:{traceback.tb_lineno}")
        traceback = traceback.tb_next
    _logger.warning("OCR_RUNTIME_FAILURE exception_type=%s traceback=%s", type(error).__name__, "|".join(frames[-6:]))


def _sharpness(image):
    with image.convert("L") as grey:
        grey.thumbnail((1600, 1600))
        pixels = np.asarray(grey, dtype=np.float32)
        if min(pixels.shape) < 3:
            return 0.0
        laplacian = -4 * pixels[1:-1, 1:-1] + pixels[2:, 1:-1] + pixels[:-2, 1:-1] + pixels[1:-1, 2:] + pixels[1:-1, :-2]
        return float(laplacian.var())


def _ocr_lines(image, page_number, start):
    global _engine
    _check_time(start)
    if not _engine_lock.acquire(timeout=5):
        raise OCRValidationError("OCR_BUSY", "文件辨識服務忙碌中，請稍後重試。", 503)
    try:
        if _engine is None:
            from rapidocr_onnxruntime import RapidOCR
            _engine = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1, det_limit_side_len=1280)
        with image.convert("RGB") as rgb:
            rgb.thumbnail((1800, 1800))
            width, height = rgb.size
            # The PIL path lets RapidOCR correctly convert RGB to its BGR input.
            result, _ = _engine(rgb)
        lines = []
        for points, text, confidence in result or []:
            xs, ys = [point[0] for point in points], [point[1] for point in points]
            lines.append(TextLine(str(text), float(confidence), _box(page_number, min(xs) / width, min(ys) / height, (max(xs) - min(xs)) / width, (max(ys) - min(ys)) / height)))
        _check_time(start)
        return lines
    except OCRValidationError:
        raise
    except Exception as error:
        _log_runtime_failure(error)
        raise OCRValidationError("OCR_UNAVAILABLE", "本機 OCR 無法處理此文件，請稍後重試或人工檢查。", 503) from error
    finally:
        _engine_lock.release()


def _image_from_bytes(data, mime):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise OCRValidationError("IMAGE_TOO_LARGE", "圖片解壓縮後超過 2,000 萬像素，請縮小後重試。", 413)
                expected = "PNG" if mime == "image/png" else "JPEG"
                if image.format != expected or getattr(image, "n_frames", 1) != 1:
                    raise OCRValidationError("INVALID_FILE", "請上傳單張且格式正確的 PNG 或 JPG。")
                image.load()
                return image.convert("RGB")
    except OCRValidationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise OCRValidationError("IMAGE_TOO_LARGE", "圖片像素過大，請縮小後重試。", 413) from error
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise OCRValidationError("INVALID_FILE", "圖片無法解碼，請重新匯出 PNG 或 JPG。") from error


def _extract(data, mime):
    start = time.monotonic()
    if mime != "application/pdf":
        with _image_from_bytes(data, mime) as image:
            poor_quality = _sharpness(image) < 8 or min(image.size) < 300
            if poor_quality:
                _check_time(start)
                return [], "quality_precheck", True, 1, [1]
            return _ocr_lines(image, 1, start), "rapidocr", poor_quality, 1, []
    try:
        with fitz.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise OCRValidationError("ENCRYPTED_PDF", "PDF 已加密，請上傳不需密碼的副本。")
            if pdf.page_count > MAX_PAGES:
                raise OCRValidationError("TOO_MANY_PAGES", "PDF 超過 10 頁上限，請拆分後重試。", 413)
            if pdf.page_count == 0 or pdf.is_repaired:
                raise OCRValidationError("INVALID_FILE", "PDF 損壞或結構不完整，請重新匯出。")
            lines, rejected_pages, used_ocr, poor_quality = [], [], False, False
            for index, page in enumerate(pdf):
                _check_time(start)
                native = []
                # Text dictionaries otherwise include decoded embedded images.
                for block in page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)["blocks"]:
                    for line in block.get("lines", []):
                        text = "".join(span["text"] for span in line["spans"]).strip()
                        if text:
                            x0, y0, x1, y1 = line["bbox"]
                            native.append(TextLine(text, 0.99, _box(index + 1, x0 / page.rect.width, y0 / page.rect.height, (x1 - x0) / page.rect.width, (y1 - y0) / page.rect.height)))
                if sum(len(line.text) for line in native) >= 20:
                    lines.extend(native)
                else:
                    if not page.rect.width or not page.rect.height:
                        raise OCRValidationError("INVALID_FILE", "PDF 頁面尺寸無效。")
                    scale = min(2.0, 1800 / max(page.rect.width, page.rect.height))
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
                    with Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples) as image:
                        page_poor_quality = _sharpness(image) < 8 or min(image.size) < 300
                        poor_quality = poor_quality or page_poor_quality
                        if page_poor_quality:
                            rejected_pages.append(index + 1)
                            continue
                        lines.extend(_ocr_lines(image, index + 1, start))
                    used_ocr = True
            _check_time(start)
            provider = "rapidocr" if used_ocr else "pdf_text" if lines else "quality_precheck"
            return lines, provider, poor_quality, pdf.page_count, rejected_pages
    except OCRValidationError:
        raise
    except Exception as error:
        raise OCRValidationError("INVALID_FILE", "PDF 無法解析，請重新匯出或改傳清晰圖片。") from error


_LABELS = {
    "insured_name": ("被保人姓名", "被保險人姓名", "Insured name"),
    "policy_number": ("保單號碼", "Policy number"),
    "identity_number": ("身分證字號", "身份證字號", "Identity number"),
    "claim_selection": ("申請項目", "申请项目", "申請目", "Claim selection"),
    "application_date": ("簽署日期", "签署日期", "署日期", "申請日期", "Signed date"),
}
_NAMES = {"insured_name": "被保人姓名", "policy_number": "保單號碼", "identity_number": "身分證字號", "claim_selection": "申請項目", "application_date": "簽署日期"}
_KNOWN_LABELS = tuple(alias for aliases in _LABELS.values() for alias in aliases) + ("連絡電話", "聯絡電話", "事故時間", "戶名", "帳號", "銀行", "e-mail", "職業")


def _find_field(lines, aliases):
    for line in lines:
        compact = re.sub(r"\s+", "", unicodedata.normalize("NFKC", line.text))
        for alias in aliases:
            normalized = re.sub(r"\s+", "", alias)
            position = compact.lower().find(normalized.lower())
            if position >= 0:
                value = compact[position + len(normalized):].lstrip("：: ")
                if not value:
                    # Only an adjacent line on the right counts as a possible value.
                    for candidate in lines:
                        gap = candidate.box["x"] - (line.box["x"] + line.box["width"])
                        if candidate is not line and candidate.box["page_number"] == line.box["page_number"] and abs(candidate.box["y"] - line.box["y"]) < 0.015 and -0.01 <= gap <= 0.04:
                            candidate_value = re.sub(r"\s+", "", unicodedata.normalize("NFKC", candidate.text))
                            if any(label in candidate_value for label in _KNOWN_LABELS):
                                continue
                            value = candidate_value
                            break
                if any(label in value for label in _KNOWN_LABELS):
                    value = ""
                return value, line
    return None, None


def _nonempty(value):
    return bool(value and re.sub(r"[\s＿_\-—.．。:：□▢\[\]()（）/／]", "", value))


def _valid_date(value):
    value = unicodedata.normalize("NFKC", value or "")
    match = re.search(r"(?:中華民國|民國)?\s*(\d{2,4})\s*[年/.-]\s*(\d{1,2})\s*[月/.-]\s*(\d{1,2})\s*日?", value or "")
    if not match:
        return False
    year, month, day = map(int, match.groups())
    if year < 1911:
        year += 1911
    try:
        parsed = date(year, month, day)
        return 1900 <= parsed.year <= date.today().year + 1
    except ValueError:
        return False


def analyze_document(data: bytes, filename: str, content_type: str, document: dict) -> dict:
    """Return the v1 Analysis contract; raises structured OCRValidationError."""
    mime = _validate_upload(data, filename, content_type)
    lines, provider, poor_quality, page_count, rejected_pages = _extract(data, mime)
    confidence = round(sum(line.confidence * len(line.text) for line in lines) / max(1, sum(len(line.text) for line in lines)), 3)
    if poor_quality:
        confidence = min(confidence, 0.49)
    findings, fields = [], []
    default_box = _box(1, 0.05, 0.05, 0.9, 0.15)
    is_application = document.get("id", document.get("document_id")) == "application"
    source_id = "cardif-application" if is_application else document.get("source_id", "cardif-claims")

    def finding(field, name, message, suggestion, line=None, severity="warning", page_number=None, confidence_override=None):
        box = line.box if line else default_box
        if page_number is not None:
            box = {**box, "page_number": page_number}
        finding_confidence = confidence_override if confidence_override is not None else line.confidence if line else confidence
        findings.append({"id": f"finding-{uuid.uuid4().hex}", "field": field, "field_name": name, "severity": severity, "message": message, "suggestion": suggestion, "confidence": round(finding_confidence, 3), "page_number": box["page_number"], "bounding_box": box, "source_id": source_id, "requires_human_review": True})

    title_line = next((line for line in lines if "保險金申請書" in re.sub(r"\s+", "", line.text)), None)
    if title_line is None:
        # The bundled Chinese model may omit complex traditional glyphs.
        # Accept a partial title only with two independent application labels;
        # this identifies the apparent type, never its authenticity.
        anchor_count = sum(_find_field(lines, _LABELS[field])[1] is not None for field in ("insured_name", "policy_number", "identity_number"))
        if anchor_count >= 2:
            title_line = next((line for line in lines if re.search(r"保[險险]?金申[請请][書书]", re.sub(r"\s+", "", line.text))), None)
    uncertain = poor_quality or confidence < 0.75 or not lines
    for rejected_page in rejected_pages:
        finding("image_quality", "文件清晰度", "此頁清晰度不足，未執行 OCR，無法可靠判斷指定欄位。", "請重新掃描清楚、無反光的完整頁面，或逐項人工確認。", page_number=rejected_page, confidence_override=0.0)
    if not rejected_pages and (confidence < 0.75 or not lines):
        finding("image_quality", "文件清晰度", "文件模糊或辨識信心不足，無法可靠判斷指定欄位。", "請重新掃描清楚、無反光的完整頁面，或逐項人工確認。")
    quality_only = provider == "quality_precheck" or (poor_quality and not any(line.box["page_number"] == 1 for line in lines))
    if quality_only:
        # No fields were read on the inspected page. Report quality alone;
        # absence of OCR evidence is not evidence of blank fields or wrong type.
        pass
    elif not is_application:
        finding("manual_review", "人工確認", "此類文件目前僅完成文字擷取，尚無經驗證的自動欄位規則。", "請依文件清單與官方來源人工確認；不能視為初步檢查通過。")
        uncertain = True
    elif not title_line:
        finding("document_type", "文件類型", "無法可靠辨識為保險金申請書。", "請確認上傳的是保險金申請書完整清晰頁面，或使用官方表單。")
        uncertain = True
    else:
        # Selected form checks apply to the official first-page form only.
        form_lines = [line for line in lines if line.box["page_number"] == 1]
        signature_line = next((line for line in form_lines if "受益人" in re.sub(r"\s+", "", line.text) and any(label in re.sub(r"\s+", "", line.text) for label in ("簽名", "签名", "受益人名"))), None)
        fields.append({"field": "document_type", "value": "可辨識保險金申請書標題；未驗真", "confidence": title_line.confidence, "page_number": title_line.box["page_number"]})
        for field, aliases in _LABELS.items():
            value, line = _find_field(form_lines, aliases)
            if field == "application_date" and line is None:
                # The actual official signature area prints the ROC date directly.
                if signature_line:
                    line = next((item for item in form_lines if signature_line.box["y"] - 0.015 <= item.box["y"] <= signature_line.box["y"] + 0.18 and "中華民國" in re.sub(r"\s+", "", item.text) and re.search(r"\d+年", re.sub(r"\s+", "", item.text))), None)
                value = re.sub(r"\s+", "", line.text) if line else None
            present = _nonempty(value)
            fields.append({"field": field, "value": "已辨識內容（隱私遮罩）" if present else "未可靠辨識內容", "confidence": round(line.confidence if line else 0, 3), "page_number": line.box["page_number"] if line else 1})
            if not present:
                finding(field, _NAMES[field], f"{_NAMES[field]}未辨識到內容或疑似空白；仍需依個別情況確認適用性。", "請對照官方第 1 頁表單原件，人工確認此欄是否適用及已填寫。", line)
            elif field == "application_date" and not _valid_date(value):
                finding(field, _NAMES[field], "簽署日期未辨識為有效的西元或民國年月日。", "請對照簽署區的中華民國年月日，確認日期與日曆有效性。", line)
            elif field == "claim_selection" and not re.search(r"\[[xXvV×✓✔]\]|[☑✅■√✓✔]|已勾選", value):
                finding(field, _NAMES[field], "辨識到申請項目文字，但無法確認實際勾選。", "請依申請情況人工確認所選項目，不能僅以選項文字判定已勾選。", line)
        finding("signature", "受益人簽名", "簽署區需人工確認；OCR 無法驗證是否親簽、本人性或法律效力。", "請人工檢查官方第 1 頁的受益人簽署與日期；代理人等欄位依適用情況確認。", signature_line, "info")
    return {"analysis_id": f"analysis-{uuid.uuid4().hex}", "document_id": document.get("id", document.get("document_id")), "analysis_status": "uncertain" if uncertain else "completed", "provider": provider, "is_simulated": False, "extracted_fields": fields, "findings": findings, "confidence": confidence, "page_number": 1, "bounding_boxes": [item["bounding_box"] for item in findings], "requires_human_review": True, "disclaimer": _DISCLAIMER}
