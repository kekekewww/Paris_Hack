"""Real parser/OCR tests; fixtures contain synthetic data only."""
from pathlib import Path
import importlib
import io
import logging
import re

import pymupdf as fitz
import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "demo" / "documents"
DOCUMENT = {"id": "application", "title": "保險金申請書", "source_id": "cardif-application"}


def analyze(data, filename="document.pdf", mime="application/pdf", document=None):
    module = importlib.import_module("backend.app.ocr.analyzer")
    return module.analyze_document(data, filename, mime, document or DOCUMENT)


def assert_error(data, filename, mime, code, status):
    module = importlib.import_module("backend.app.ocr.analyzer")
    with pytest.raises(module.OCRValidationError) as caught:
        analyze(data, filename, mime)
    assert caught.value.code == code
    assert caught.value.status == status
    assert caught.value.message


def test_text_pdf_reports_real_extraction_and_redacts_private_values():
    result = analyze((FIXTURES / "application-complete.pdf").read_bytes())
    assert result["provider"] == "pdf_text"
    assert result["is_simulated"] is False
    # This original simplified demo has no supported official version marker.
    # High native-text confidence must not claim a complete form inspection.
    assert result["analysis_status"] == "uncertain"
    assert any(f["field"] == "form_version" and f["bounding_box"] is None for f in result["findings"])
    assert result["requires_human_review"] is True
    assert result["confidence"] > 0.8
    assert {f["field"] for f in result["extracted_fields"]} >= {"insured_name", "identity_number", "application_date"}
    assert "王小明" not in str(result)
    assert "SYNTHETIC-0001" not in str(result)
    assert any(f["field"] == "signature" and f["requires_human_review"] for f in result["findings"])
    for box in result["bounding_boxes"]:
        assert 0 <= box["x"] <= 1 and 0 <= box["y"] <= 1
        assert 0 < box["width"] <= 1 and 0 < box["height"] <= 1
        assert box["x"] + box["width"] <= 1.001
        assert box["y"] + box["height"] <= 1.001


def test_health_reports_installed_local_ocr_without_loading_models():
    module = importlib.import_module("backend.app.ocr.analyzer")
    assert module.provider_status()["ocr_provider"] == "pymupdf+rapidocr"


def test_missing_fields_and_invalid_date_are_findings_not_a_pass():
    result = analyze((FIXTURES / "application-missing.pdf").read_bytes())
    fields = {f["field"] for f in result["findings"]}
    assert {"insured_name", "application_date", "signature"} <= fields
    assert all(f["source_id"] == "cardif-application" for f in result["findings"])
    assert result["requires_human_review"] is True


@pytest.mark.parametrize("name,mime", [("application-clear.png", "image/png"), ("application-clear.jpg", "image/jpeg"), ("application-scanned.pdf", "application/pdf")])
def test_real_chinese_image_and_scan_ocr(name, mime):
    result = analyze((FIXTURES / name).read_bytes(), name, mime)
    assert result["provider"] == "rapidocr"
    assert result["is_simulated"] is False
    assert result["confidence"] > 0.65
    fields = {f["field"] for f in result["extracted_fields"]}
    assert {"document_type", "insured_name"} <= fields
    assert not any(f["field"] == "document_type" for f in result["findings"])


def test_blurred_image_stays_uncertain_without_running_ocr(monkeypatch):
    module = importlib.import_module("backend.app.ocr.analyzer")

    def unexpected_ocr(*args):
        pytest.fail("A quality-rejected page must not enter the OCR model")

    monkeypatch.setattr(module, "_ocr_lines", unexpected_ocr)
    result = analyze((FIXTURES / "application-blurred.png").read_bytes(), "blurred.png", "image/png")
    assert result["provider"] == "quality_precheck"
    assert result["is_simulated"] is False
    assert result["analysis_status"] == "uncertain"
    assert result["requires_human_review"] is True
    assert result["extracted_fields"] == []
    assert {f["field"] for f in result["findings"]} == {"image_quality"}


def scanned_pdf(*names):
    with fitz.open() as doc:
        for name in names:
            page = doc.new_page(width=595, height=842)
            page.insert_image(page.rect, stream=(FIXTURES / name).read_bytes())
        return doc.tobytes(garbage=4, deflate=True)


def test_blurred_scan_pdf_stops_at_quality_precheck(monkeypatch):
    module = importlib.import_module("backend.app.ocr.analyzer")

    def unexpected_ocr(*args):
        pytest.fail("A quality-rejected scanned page must not enter the OCR model")

    monkeypatch.setattr(module, "_ocr_lines", unexpected_ocr)
    result = analyze(scanned_pdf("application-blurred.png", "application-blurred.png"))
    assert result["provider"] == "quality_precheck" and result["is_simulated"] is False
    assert result["analysis_status"] == "uncertain" and result["requires_human_review"] is True
    assert result["extracted_fields"] == []
    assert {f["field"] for f in result["findings"]} == {"image_quality"}
    assert {f["page_number"] for f in result["findings"]} == {1, 2}
    assert all(f["bounding_box"]["page_number"] == f["page_number"] and f["confidence"] == 0 for f in result["findings"])


def test_native_and_blurred_pdf_preserves_pdf_text_provider(monkeypatch):
    module = importlib.import_module("backend.app.ocr.analyzer")

    def unexpected_ocr(*args):
        pytest.fail("Neither native text nor a quality-rejected scan needs OCR")

    monkeypatch.setattr(module, "_ocr_lines", unexpected_ocr)
    with fitz.open(stream=(FIXTURES / "application-complete.pdf").read_bytes(), filetype="pdf") as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=(FIXTURES / "application-blurred.png").read_bytes())
        result = analyze(doc.tobytes())
    assert result["provider"] == "pdf_text" and result["is_simulated"] is False
    assert result["analysis_status"] == "uncertain"
    quality = [f for f in result["findings"] if f["field"] == "image_quality"]
    assert len(quality) == 1
    assert quality[0]["page_number"] == 2
    assert quality[0]["bounding_box"]["page_number"] == 2
    assert quality[0]["confidence"] == 0
    assert any(f["field"] == "insured_name" for f in result["extracted_fields"])


def test_clear_and_blurred_scans_preserve_real_ocr_provider():
    result = analyze(scanned_pdf("application-clear.png", "application-blurred.png"))
    assert result["provider"] == "rapidocr" and result["is_simulated"] is False
    assert result["analysis_status"] == "uncertain"
    assert any(f["field"] == "image_quality" for f in result["findings"])
    assert any(f["field"] == "document_type" for f in result["extracted_fields"])


def test_blurred_first_page_does_not_invent_missing_fields_on_other_pages(monkeypatch):
    module = importlib.import_module("backend.app.ocr.analyzer")

    def unexpected_ocr(*args):
        pytest.fail("A quality-rejected page must not enter the OCR model")

    monkeypatch.setattr(module, "_ocr_lines", unexpected_ocr)
    with fitz.open(stream=scanned_pdf("application-blurred.png"), filetype="pdf") as doc, fitz.open(FIXTURES / "application-complete.pdf") as native:
        doc.insert_pdf(native)
        result = analyze(doc.tobytes())
    assert result["provider"] == "pdf_text" and result["analysis_status"] == "uncertain"
    assert result["extracted_fields"] == []
    assert {f["field"] for f in result["findings"]} == {"image_quality"}


def test_missing_png_reports_real_missing_content():
    result = analyze((FIXTURES / "application-missing.png").read_bytes(), "missing.png", "image/png")
    assert result["provider"] == "rapidocr" and result["is_simulated"] is False
    assert result["requires_human_review"] is True
    assert {"insured_name", "application_date"} <= {f["field"] for f in result["findings"]}


def test_unrecognized_document_cannot_pass_application_check():
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), "This is a shopping list. No insurance claim application.")
        data = doc.tobytes()
    result = analyze(data)
    assert result["analysis_status"] == "uncertain"
    assert any(f["field"] == "document_type" for f in result["findings"])


def test_unsupported_document_keeps_manual_review():
    result = analyze((FIXTURES / "application-complete.pdf").read_bytes(), document={"id": "diagnosis", "title": "診斷書", "source_id": "cardif-claims"})
    assert result["analysis_status"] == "uncertain"
    assert result["requires_human_review"] is True
    assert any(f["field"] == "manual_review" for f in result["findings"])


def test_empty_name_does_not_borrow_the_adjacent_column_label():
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 50), "保險金申請書", fontname="china-t")
        page.insert_text((40, 100), "被保人姓名：", fontname="china-t")
        page.insert_text((160, 100), "保單號碼：SYNTHETIC", fontname="china-t")
        data = doc.tobytes()
    result = analyze(data)
    assert any(f["field"] == "insured_name" for f in result["findings"])


def test_signature_date_does_not_borrow_an_accident_date():
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 50), "保險金申請書", fontname="china-t")
        page.insert_text((40, 100), "事故時間：中華民國115年10月3日", fontname="china-t")
        page.insert_text((40, 600), "(申請人)受益人簽名：虛構印字", fontname="china-t")
        data = doc.tobytes()
    result = analyze(data)
    assert any(f["field"] == "application_date" for f in result["findings"])


@pytest.mark.parametrize("data,name,mime,code,status", [
    (b"", "file.pdf", "application/pdf", "EMPTY_FILE", 422),
    (b"x" * (10 * 1024 * 1024 + 1), "file.pdf", "application/pdf", "FILE_TOO_LARGE", 413),
    (b"<html>bad</html>", "file.html", "text/html", "UNSUPPORTED_FILE_TYPE", 415),
    (b"fake PDF", "file.pdf", "application/pdf", "INVALID_FILE", 422),
    (b"%PDF-1.4\n%%EOF", "file.pdf", "application/pdf", "INVALID_FILE", 422),
    (b"%PDF-1.7", "file.png", "image/png", "INVALID_FILE", 422),
    (b"\x89PNG\r\n\x1a\ninvalid", "file.png", "image/png", "INVALID_FILE", 422),
    (b"\xff\xd8\xffinvalid", "file.jpg", "image/jpeg", "INVALID_FILE", 422),
], ids=["empty", "over-ten-mb", "unsupported", "fake-pdf", "corrupt-pdf", "magic-mismatch", "corrupt-png", "corrupt-jpg"])
def test_rejects_unsafe_upload(data, name, mime, code, status):
    assert_error(data, name, mime, code, status)


def test_extension_and_mime_must_agree_with_real_content():
    data = (FIXTURES / "application-clear.png").read_bytes()
    assert_error(data, "file.jpg", "image/jpeg", "INVALID_FILE", 422)
    assert_error(data, "file.png", "application/pdf", "INVALID_FILE", 422)


def test_rejects_encrypted_pdf_and_over_ten_pages():
    with fitz.open() as doc:
        doc.new_page()
        encrypted = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
        assert_error(encrypted, "locked.pdf", "application/pdf", "ENCRYPTED_PDF", 422)
        for _ in range(10):
            doc.new_page()
        assert_error(doc.tobytes(), "large.pdf", "application/pdf", "TOO_MANY_PAGES", 413)


def test_rejects_oversized_decompressed_image():
    output = io.BytesIO()
    with Image.new("1", (5000, 5000)) as image:
        image.save(output, "PNG")
    assert_error(output.getvalue(), "huge.png", "image/png", "IMAGE_TOO_LARGE", 413)


def test_runtime_failure_logs_only_exception_type_and_frame_metadata(monkeypatch, caplog):
    module = importlib.import_module("backend.app.ocr.analyzer")
    exception_secret = "synthetic secret content"
    uploaded_filename = "private-synthetic-filename.png"
    local_secret = "synthetic private OCR text and stack locals"

    class FailingEngine:
        def __call__(self, image):
            private_document_text = local_secret
            raise ValueError(exception_secret)

    monkeypatch.setattr(module, "_engine", FailingEngine())
    with caplog.at_level(logging.WARNING, logger=module.__name__):
        with pytest.raises(module.OCRValidationError) as caught:
            analyze((FIXTURES / "application-clear.png").read_bytes(), uploaded_filename, "image/png")
    assert caught.value.code == "OCR_UNAVAILABLE"
    diagnostic = [record for record in caplog.records if "OCR_RUNTIME_FAILURE" in record.getMessage()]
    assert len(diagnostic) == 1
    record = diagnostic[0]
    message = record.getMessage()
    assert record.levelno == logging.WARNING
    assert "ValueError" in message
    assert re.search(r"analyzer\.py:_ocr_lines:\d+", message)
    assert re.search(r"test_ocr\.py:__call__:\d+", message)
    assert record.exc_info is None and record.stack_info is None
    captured = repr(record.__dict__)
    for secret in (exception_secret, uploaded_filename, local_secret, "private_document_text"):
        assert secret not in captured
    assert str(ROOT) not in message
