"""Real, local OCR. Never infer eligibility or verify a signature.

Versioned label checks cover selected application fields and conditional tax
continuations. They cannot prove every blank, handwriting, or legal signature.
Uploaded bytes and extracted text are never persisted.
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

from .form_profiles import ACCIDENT_FIELDS, BANK_FIELDS, BASE_FIELDS, CHOICE_FIELDS, TAX_QUESTIONS, VERSION


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
    origin: str = "unknown"


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
            lines.append(TextLine(str(text), float(confidence), _box(page_number, min(xs) / width, min(ys) / height, (max(xs) - min(xs)) / width, (max(ys) - min(ys)) / height), "ocr"))
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
            lines, rejected_pages, used_ocr, poor_quality, mixed_content = [], [], False, False, False
            for index, page in enumerate(pdf):
                _check_time(start)
                native = []
                # Text dictionaries otherwise include decoded embedded images.
                for block in page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)["blocks"]:
                    for line in block.get("lines", []):
                        text = "".join(span["text"] for span in line["spans"]).strip()
                        if text:
                            x0, y0, x1, y1 = line["bbox"]
                            native.append(TextLine(text, 0.99, _box(index + 1, x0 / page.rect.width, y0 / page.rect.height, (x1 - x0) / page.rect.width, (y1 - y0) / page.rect.height), "native"))
                has_native = sum(len(line.text) for line in native) >= 20
                # Native printed labels do not account for raster handwriting
                # or pen/stylus paths. Rectangular table borders alone need no OCR.
                images = page.get_image_info()
                source_pixels = 0
                for image_info in images:
                    width, height = image_info.get("width"), image_info.get("height")
                    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
                        raise OCRValidationError("INVALID_FILE", "PDF 內嵌圖片尺寸無效，請重新匯出。")
                    pixels = width * height
                    source_pixels += pixels
                    if pixels > MAX_IMAGE_PIXELS or source_pixels > MAX_IMAGE_PIXELS:
                        raise OCRValidationError("IMAGE_TOO_LARGE", "PDF 每頁內嵌圖片解壓縮後合計超過 2,000 萬像素，請縮小圖片後重試。", 413)
                has_ink = bool(images) or any(
                    item[0] in {"l", "c"}
                    for drawing in page.get_drawings()
                    for item in drawing["items"]
                )
                if has_native:
                    lines.extend(native)
                if not has_native or has_ink:
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
                    mixed_content = mixed_content or has_native
            _check_time(start)
            provider = "pdf_text+rapidocr" if mixed_content else "rapidocr" if used_ocr else "pdf_text" if lines else "quality_precheck"
            return lines, provider, poor_quality, pdf.page_count, rejected_pages
    except OCRValidationError:
        raise
    except Exception as error:
        raise OCRValidationError("INVALID_FILE", "PDF 無法解析，請重新匯出或改傳清晰圖片。") from error


_ALL_RULES = BASE_FIELDS + BANK_FIELDS + ACCIDENT_FIELDS + tuple(CHOICE_FIELDS.values()) + TAX_QUESTIONS
_KNOWN_LABELS = tuple(alias for rule in _ALL_RULES for alias in rule.aliases) + ("e-mail",)


def _compact(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).lower()


def _find_field(lines, aliases):
    matches = []
    for line in lines:
        compact = _compact(line.text)
        for alias in aliases:
            normalized = _compact(alias)
            position = compact.find(normalized)
            if position < 0:
                continue
            # A label embedded in a sentence (e.g. the official instruction
            # "每位受益人之帳號封面影本") is not a filled table cell.
            prefix = compact[:position]
            for label in sorted(_KNOWN_LABELS, key=len, reverse=True):
                prefix = prefix.replace(_compact(label), "")
            if not re.fullmatch(r"[\d.、:：()（）\[\]xv×✓✔☑□▢◆*•_\-／/]*", prefix):
                continue
            if normalized == "分行" and compact[position:].startswith("分行/分支機構"):
                continue
            value = compact[position + len(normalized):].lstrip("：: ")
            # End at the next field label. Never borrow a neighbouring column.
            ends = [value.find(_compact(label)) for label in _KNOWN_LABELS if _compact(label) in value]
            if ends:
                value = value[:min(ends)]
            if not _nonempty(value):
                for candidate in lines:
                    gap = candidate.box["x"] - (line.box["x"] + line.box["width"])
                    if candidate is not line and candidate.box["page_number"] == line.box["page_number"] and abs(candidate.box["y"] - line.box["y"]) < 0.015 and -0.02 <= gap <= 0.08:
                        candidate_value = _compact(candidate.text)
                        if not any(_compact(label) in candidate_value for label in _KNOWN_LABELS):
                            value = candidate_value
                            line = TextLine(line.text, min(line.confidence, candidate.confidence), line.box, line.origin)
                            break
            matches.append((value, line))
            break
    if not matches:
        return None, None
    first = min(matches, key=lambda pair: (pair[1].box["page_number"], pair[1].box["y"]))[1]
    # Prefer an OCR-combined label/value over the empty native label at the
    # same place; never choose a duplicate field in a later section or page.
    nearby = [pair for pair in matches if pair[1].box["page_number"] == first.box["page_number"] and abs(pair[1].box["y"] - first.box["y"]) < 0.025]
    return max(nearby, key=lambda pair: (_nonempty(pair[0]), len(pair[0] or "")))


_CHECKBOX = re.compile(r"\[(?P<mark>[xXvV×✓✔\s]?)\]|(?P<glyph>[☑✅■√✓✔□▢])")


def _choices(lines, rule, options):
    """Read explicit marks beside known option text; printed labels are no vote.

    OCR may miss a pen mark. None/ambiguous stays manual; no visual presence
    test is presented as a semantic selection or a signature verification.
    """
    _, anchor = _find_field(lines, rule.aliases)
    if anchor is None and rule.field == "claim_selection":
        anchor = next((line for line in lines if any(re.search(pattern, _compact(line.text)) for pattern in options.values())), None)
    if anchor is None:
        return set(), None
    if anchor.confidence < 0.75:
        return set(), anchor
    next_labels = [line.box["y"] for line in lines if line.box["page_number"] == anchor.box["page_number"] and line.box["y"] > anchor.box["y"] + 0.015 and any(_find_field([line], other.aliases)[1] is not None for other in _ALL_RULES if other.field != rule.field)]
    end = min([anchor.box["y"] + 0.15, *next_labels])
    region = [line for line in lines if line.box["page_number"] == anchor.box["page_number"] and anchor.box["y"] - 0.015 <= line.box["y"] < end]
    selected, evidence_confidence = set(), []
    for line in region:
        if line.confidence < 0.75:
            continue
        text = _compact(line.text)
        marks = list(_CHECKBOX.finditer(text))
        for index, mark in enumerate(marks):
            checked = bool((mark.group("mark") or "").strip()) or mark.group("glyph") in {"☑", "✅", "■", "√", "✓", "✔"}
            if not checked:
                continue
            option = text[mark.end():marks[index + 1].start() if index + 1 < len(marks) else len(text)]
            for key, pattern in options.items():
                if re.search(pattern, option):
                    selected.add(key)
                    evidence_confidence.append(line.confidence)
                    break
    if evidence_confidence:
        anchor = TextLine(anchor.text, min(anchor.confidence, *evidence_confidence), anchor.box, anchor.origin)
    return selected, anchor


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
    is_application = document.get("id", document.get("document_id")) == "application"
    source_id = "cardif-application" if is_application else document.get("source_id", "cardif-claims")

    def finding(field, name, message, suggestion, line=None, severity="warning", page_number=None, confidence_override=None, whole_page=False):
        nonlocal uncertain
        number = page_number or (line.box["page_number"] if line else 1)
        box = line.box if line else _box(number, 0.01, 0.01, 0.98, 0.98) if whole_page else None
        if box and page_number is not None:
            box = {**box, "page_number": number}
        if box is None:
            uncertain = True
        finding_confidence = confidence_override if confidence_override is not None else line.confidence if line else confidence
        findings.append({"id": f"finding-{uuid.uuid4().hex}", "field": field, "field_name": name, "severity": severity, "message": message, "suggestion": suggestion, "confidence": round(finding_confidence, 3), "page_number": number, "bounding_box": box, "location_status": "page" if whole_page else "label" if box else "unlocated", "source_id": source_id, "requires_human_review": True})

    title_line = next((line for line in lines if "保險金申請書" in re.sub(r"\s+", "", line.text)), None)
    if title_line is None:
        # The bundled Chinese model may omit complex traditional glyphs.
        # Accept a partial title only with two independent application labels;
        # this identifies the apparent type, never its authenticity.
        anchor_count = sum(_find_field(lines, rule.aliases)[1] is not None for rule in BASE_FIELDS[:3])
        if anchor_count >= 2:
            title_line = next((line for line in lines if re.search(r"保[險险]?金申[請请][書书]", re.sub(r"\s+", "", line.text))), None)
    uncertain = poor_quality or confidence < 0.75 or not lines
    for rejected_page in rejected_pages:
        finding("image_quality", "文件清晰度", "此頁清晰度不足，未執行 OCR，無法可靠判斷指定欄位。", "請重新掃描清楚、無反光的完整頁面，或逐項人工確認。", page_number=rejected_page, confidence_override=0.0, whole_page=True)
    if not rejected_pages and (confidence < 0.75 or not lines):
        finding("image_quality", "文件清晰度", "文件模糊或辨識信心不足，無法可靠判斷指定欄位。", "請重新掃描清楚、無反光的完整頁面，或逐項人工確認。", whole_page=True)
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
        # Inspect the page containing the title, not arbitrary page 1 fields.
        form_page = title_line.box["page_number"]
        form_lines = [line for line in lines if line.box["page_number"] == form_page]
        signature_line = next((line for line in form_lines if "受益人" in re.sub(r"\s+", "", line.text) and any(label in re.sub(r"\s+", "", line.text) for label in ("簽名", "签名", "受益人名"))), None)
        fields.append({"field": "document_type", "value": "可辨識保險金申請書標題；未驗真", "confidence": title_line.confidence, "page_number": title_line.box["page_number"]})

        def inspect(rule, candidates=form_lines, suggestion=None):
            nonlocal uncertain
            value, line = _find_field(candidates, rule.aliases)
            if rule.field == "application_date" and line is None:
                # The actual official signature area prints the ROC date directly.
                if signature_line:
                    line = next((item for item in form_lines if signature_line.box["y"] - 0.015 <= item.box["y"] <= signature_line.box["y"] + 0.18 and "中華民國" in re.sub(r"\s+", "", item.text)), None)
                value = re.sub(r"\s+", "", line.text) if line else None
            present = _nonempty(value) and line is not None and line.confidence >= 0.75
            fields.append({"field": rule.field, "value": "已辨識內容（隱私遮罩）" if present else "未可靠辨識內容", "confidence": round(line.confidence if line else 0, 3), "page_number": line.box["page_number"] if line else form_page})
            if not present:
                message = f"{rule.name}疑似未填或未辨識到內容；請人工核對，辨識不到不代表原件空白。" if line else f"未可靠定位{rule.name}欄位，無法自動判斷是否已填；需人工確認。"
                finding(rule.field, rule.name, message, suggestion or "請對照官方表單原件，確認此欄適用性及內容；手寫可能無法辨識。", line, page_number=line.box["page_number"] if line else form_page)
            elif rule.field in {"application_date", "accident_datetime"} and not _valid_date(value):
                finding(rule.field, rule.name, f"{rule.name}未辨識為有效的西元或民國年月日。", "請對照原件確認完整年月日與日曆有效性。", line)
            if line and line.confidence < 0.75:
                uncertain = True
            return value, line

        def choice(rule, options, candidates=form_lines, exclusive=True):
            nonlocal uncertain
            selected, line = _choices(candidates, rule, options)
            valid = bool(selected) and (not exclusive or len(selected) == 1)
            fields.append({"field": rule.field, "value": "已辨識勾選（仍須核對）" if valid else "未可靠辨識單一勾選" if exclusive else "未可靠辨識勾選", "confidence": round(line.confidence if line else 0, 3), "page_number": line.box["page_number"] if line else form_page})
            if not valid:
                uncertain = True
                finding(rule.field, rule.name, f"{rule.name}無法確認{'單一選項' if exclusive else '實際勾選'}；可能未勾、多選或手寫未辨識。", "請對照原件人工確認；印有選項文字不表示已勾選，也不能依辨識結果代勾。", line, page_number=line.box["page_number"] if line else form_page)
            return selected if valid else set()

        version_pattern = rf"(?<![a-z0-9_.-]){re.escape(_compact(VERSION))}(?![a-z0-9_.-])"
        known_version = any(re.search(version_pattern, _compact(line.text)) for line in form_lines)
        if not known_version:
            finding("form_version", "表單版本", "無法核對為支援的 VIE_Claim.2024.01；僅列出可辨識欄位，無法套用完整條件檢查。", "請人工核對官方最新申請書與所有適用欄位；不把其他版型視為完整檢查。", page_number=form_page)
        for rule in BASE_FIELDS if known_version else (BASE_FIELDS[0], BASE_FIELDS[1], BASE_FIELDS[2], BASE_FIELDS[-1]):
            inspect(rule)
        selections = choice(CHOICE_FIELDS["claim_selection"], {"outpatient": r"門診|门诊", "inpatient": r"住院|手術|手术", "other": r"身故|失能|傷害|伤害|豁免|防癌|重大|定期|其他"}, exclusive=False)
        if known_version:
            if selections and selections != {"outpatient"}:
                reason = choice(CHOICE_FIELDS["claim_reason"], {"accident": r"意外", "illness": r"疾病"})
                # The reason section is explicitly exempt for outpatient only.
                # Accident place/story apply only to an explicit accident mark.
                inspect(ACCIDENT_FIELDS[0])
                if reason == {"accident"}:
                    for rule in ACCIDENT_FIELDS[1:]:
                        inspect(rule)
                choice(CHOICE_FIELDS["other_insurer_claim"], {"yes": r"是", "no": r"否"})
            payment = choice(CHOICE_FIELDS["payment_method"], {"previous": r"同最近一次理賠帳戶|同最近一次理赔账户", "remittance": r"匯款至下列銀行帳戶|汇款至下列银行账户", "cheque": r"支票給付|支票给付"})
            if payment == {"remittance"}:
                for rule in BANK_FIELDS:
                    inspect(rule, suggestion="選擇匯款至下列帳戶時請核對銀行資料；多位受益人可依官方說明改附帳號封面影本，需人工確認。")
            tax = choice(CHOICE_FIELDS["tax_declaration"], {"roc": r"本人僅為中華民國稅務居住者|本人仅为中华民国税务居住者", "other": r"本人為具有|本人为具有|不是或不僅|不是或不仅"})
            if tax == {"roc"}:
                _, tax_line = _find_field(form_lines, CHOICE_FIELDS["tax_declaration"].aliases)
                finding("tax_roc_confirmation", "稅務免填條件", "已辨識僅為中華民國稅務居住者選項；稅務身分與基本資料是否同本次所附證件仍須人工確認。", "符合官方第1頁此聲明條件才免填第2、3頁；OCR不判定稅籍或證件一致性。", tax_line, "info", page_number=form_page)
            elif tax == {"other"}:
                tax_title = next((line for line in lines if line.box["page_number"] != form_page and "fatca" in _compact(line.text) and "crs" in _compact(line.text) and "聲明書" in line.text), None)
                if tax_title is None:
                    finding("tax_continuation", "FATCA／CRS 續頁", "已辨識續填稅務聲明選項，但未可靠找到身份確認聲明續頁；不能僅依檔案頁數認定已附。", "請依官方第 2 頁及相關表格確認所需內容；僅為中華民國稅務居住者且符合聲明條件時才可免填第 2、3 頁。", page_number=form_page)
                else:
                    tax_lines = [line for line in lines if line.box["page_number"] == tax_title.box["page_number"]]
                    answers = {}
                    for rule in TAX_QUESTIONS:
                        if rule.field == "tax_us_indicators" and answers.get("tax_us_person") != {"no"}:
                            continue
                        answers[rule.field] = choice(rule, {"yes": r"是", "no": r"否"}, tax_lines)
                    signature = next((line for line in lines if line.box["page_number"] != form_page and "立同意書人" in line.text and "簽名" in line.text), None)
                    finding("tax_signature", "稅務聲明簽署及相關表格", "續頁簽署、W-9／W-8BEN與稅籍填寫條件須人工確認，不能由OCR驗證簽名或稅籍。", "美國納稅人依第2頁附W-9且第三部分免重填；其他稅籍及無識別碼原因須依第2、3頁各題條件核對，不一律判定識別碼留白為缺漏。", signature, "info", page_number=signature.box["page_number"] if signature else tax_title.box["page_number"])
                    uncertain = True
            elif not tax:
                uncertain = True
        if provider == "pdf_text+rapidocr":
            finding("mixed_content", "混合文字與影像／筆跡", "已同時讀取文字層與影像OCR；手寫、圖像勾選及未辨識區域仍可能漏讀。", "請逐項核對原件的手寫內容及勾選；文字層與高辨識分數不代表完整填寫。", page_number=form_page)
            uncertain = True
        finding("signature", "受益人簽名", "簽署區需人工確認；OCR 無法驗證是否親簽、本人性或法律效力。", "請人工檢查官方第 1 頁的受益人簽署與日期；代理人等欄位依適用情況確認。", signature_line, "info", page_number=form_page)
    return {"analysis_id": f"analysis-{uuid.uuid4().hex}", "document_id": document.get("id", document.get("document_id")), "analysis_status": "uncertain" if uncertain else "completed", "provider": provider, "is_simulated": False, "extracted_fields": fields, "findings": findings, "confidence": confidence, "page_number": 1, "bounding_boxes": [item["bounding_box"] for item in findings if item["bounding_box"] is not None and item["location_status"] == "label"], "requires_human_review": True, "disclaimer": _DISCLAIMER}
