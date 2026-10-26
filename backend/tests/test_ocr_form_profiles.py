"""Versioned form regressions use real synthetic PDFs, never medical uploads."""
import importlib
from io import BytesIO

import pymupdf as fitz
import pytest
from PIL import Image

from demo.generate_review_documents import application_pdf


DOCUMENT = {"id": "application", "source_id": "cardif-application"}


def analyze(**options):
    module = importlib.import_module("backend.app.ocr.analyzer")
    return module.analyze_document(application_pdf(**options), "synthetic.pdf", "application/pdf", DOCUMENT)


def findings(result):
    return {item["field"]: item for item in result["findings"]}


def test_central_empty_choices_and_phone_are_not_mistaken_for_completed_values():
    result = analyze(overrides={"連絡電話": "____", "付款方式": "[ ] 同最近一次理賠帳戶 [ ] 匯款至下列銀行帳戶 [ ] 支票給付", "稅務聲明": "[ ] 本人僅為中華民國稅務居住者 [ ] 本人為具有FATCA身分或其他稅務居住者"})
    assert {"contact_phone", "payment_method", "tax_declaration"} <= findings(result).keys()
    assert result["requires_human_review"] is True


def test_versioned_filled_printed_fixture_checks_fields_without_claiming_signature_validity():
    result = analyze()
    assert result["analysis_status"] == "completed"
    assert result["requires_human_review"] is True
    assert findings(result).keys() == {"signature", "tax_roc_confirmation"}
    assert {"contact_phone", "occupation", "payment_method", "tax_declaration", "bank_account"} <= {item["field"] for item in result["extracted_fields"]}


def test_remittance_checks_account_fields_but_cheque_does_not():
    empty = {"戶名": "____", "銀行/郵局": "____", "分行": "____", "帳號": "____"}
    assert {"account_holder", "bank_name", "bank_branch", "bank_account"} <= findings(analyze(overrides=empty)).keys()
    cheque = analyze(overrides={**empty, "付款方式": "[ ] 同最近一次理賠帳戶 [ ] 匯款至下列銀行帳戶 [X] 支票給付"})
    assert not {"account_holder", "bank_name", "bank_branch", "bank_account"} & findings(cheque).keys()


def test_outpatient_exempts_reason_and_accident_details_but_accident_requires_details():
    outpatient = analyze(overrides={"申請項目": "[X] 門診 [ ] 住院、手術", "申請事由": "____", "事故時間": "____"})
    assert not {"claim_reason", "accident_datetime", "accident_location", "accident_description"} & findings(outpatient).keys()
    accident = analyze(overrides={"申請事由": "[X] 意外 [ ] 疾病", "事故時間": "____"})
    assert {"accident_datetime", "accident_location", "accident_description"} <= findings(accident).keys()


def test_roc_only_tax_choice_exempts_continuation_pages():
    assert not {"tax_continuation", "tax_questions", "tax_signature"} & findings(analyze()).keys()
    result = analyze(overrides={"稅務聲明": "[ ] 本人僅為中華民國稅務居住者 [X] 本人為具有FATCA身分或其他稅務居住者"})
    assert "tax_continuation" in findings(result)
    assert findings(result)["tax_continuation"]["bounding_box"] is None
    assert result["analysis_status"] == "uncertain"


def test_continuation_is_detected_by_content_and_inspected_on_actual_page():
    result = analyze(overrides={"稅務聲明": "[ ] 本人僅為中華民國稅務居住者 [X] 本人為具有FATCA身分或其他稅務居住者"}, continuation=True)
    assert "tax_continuation" not in findings(result)
    assert any(item["field"] == "tax_taiwan_resident" and item["page_number"] == 2 for item in result["extracted_fields"])
    assert findings(result)["tax_signature"]["page_number"] == 3


def test_tax_question_does_not_borrow_next_questions_opposite_answer():
    result = analyze(overrides={"稅務聲明": "[ ] 本人僅為中華民國稅務居住者 [X] 本人為具有FATCA身分或其他稅務居住者"}, continuation=True)
    tax_fields = [item for item in result["extracted_fields"] if item["field"].startswith("tax_") and item["field"] != "tax_declaration"]
    assert len(tax_fields) == 4
    assert all(item["value"] == "已辨識勾選（仍須核對）" for item in tax_fields)


def test_unrelated_extra_pages_do_not_count_as_tax_continuation():
    module = importlib.import_module("backend.app.ocr.analyzer")
    with fitz.open(stream=application_pdf(overrides={"稅務聲明": "[ ] 本人僅為中華民國稅務居住者 [X] 本人為具有FATCA身分或其他稅務居住者"}), filetype="pdf") as pdf:
        for _ in range(3):
            page = pdf.new_page()
            page.insert_text((20, 40), "Synthetic unrelated attachment. Not a tax declaration.")
        result = module.analyze_document(pdf.tobytes(), "synthetic.pdf", "application/pdf", DOCUMENT)
    assert "tax_continuation" in findings(result)


def test_missing_tax_question_cannot_borrow_another_questions_yes_answer():
    module = importlib.import_module("backend.app.ocr.analyzer")
    with fitz.open(stream=application_pdf(overrides={"稅務聲明": "[ ] 本人僅為中華民國稅務居住者 [X] 本人為具有FATCA身分或其他稅務居住者"}, continuation=True), filetype="pdf") as pdf:
        page = pdf[1]
        for rect in page.search_for("美國納稅義務人身分"):
            page.add_redact_annot(fitz.Rect(0, rect.y0 - 2, page.rect.width, rect.y1 + 2))
        page.apply_redactions()
        result = module.analyze_document(pdf.tobytes(), "synthetic.pdf", "application/pdf", DOCUMENT)
    question = next(item for item in result["extracted_fields"] if item["field"] == "tax_us_person")
    assert question["value"] == "未可靠辨識單一勾選"
    assert findings(result)["tax_us_person"]["bounding_box"] is None


def test_low_confidence_mark_never_enables_tax_exemption_or_remittance_rule():
    module = importlib.import_module("backend.app.ocr.analyzer")
    from backend.app.ocr.form_profiles import CHOICE_FIELDS
    lines = [
        module.TextLine("付款方式", .99, module._box(1, .1, .1, .2, .02), "native"),
        module.TextLine("[X] 匯款至下列銀行帳戶", .1, module._box(1, .1, .13, .4, .02), "ocr"),
    ]
    selected, _ = module._choices(lines, CHOICE_FIELDS["payment_method"], {"remittance": r"匯款至下列銀行帳戶"})
    assert selected == set()


def test_official_account_cover_instruction_is_not_a_filled_bank_account():
    module = importlib.import_module("backend.app.ocr.analyzer")
    with fitz.open(stream=application_pdf(overrides={"帳號": "____"}), filetype="pdf") as pdf:
        pdf[0].insert_text((25, 535), "受益人不只一人，可提供每位受益人之帳號封面影本。", fontname="china-t", fontsize=10)
        result = module.analyze_document(pdf.tobytes(), "synthetic.pdf", "application/pdf", DOCUMENT)
    assert "bank_account" in findings(result)
    assert findings(result)["bank_account"]["bounding_box"]["y"] > .6


def test_submission_unit_branch_cannot_replace_missing_bank_branch_label():
    module = importlib.import_module("backend.app.ocr.analyzer")
    with fitz.open(stream=application_pdf(), filetype="pdf") as pdf:
        page = pdf[0]
        page.add_redact_annot(fitz.Rect(0, 620, page.rect.width, 642))
        page.apply_redactions()
        page.insert_text((25, 905), "分行/分支機構(營業處)：合成送件欄", fontname="china-t", fontsize=11)
        result = module.analyze_document(pdf.tobytes(), "synthetic.pdf", "application/pdf", DOCUMENT)
    assert "bank_branch" in findings(result)
    assert findings(result)["bank_branch"]["bounding_box"] is None


def test_tax_explanatory_identity_text_does_not_hide_a_second_selected_option():
    module = importlib.import_module("backend.app.ocr.analyzer")
    from backend.app.ocr.form_profiles import CHOICE_FIELDS
    lines = [module.TextLine(text, .99, module._box(1, .1, y, .6, .015), "native") for text, y in [
        ("稅務聲明", .1),
        ("[X] 本人僅為中華民國稅務居住者", .12),
        ("其基本資料：姓名/身分證字號/出生日期，同本次所附證件。", .14),
        ("[X] 本人為具有FATCA所稱之美國納稅義務人", .16),
    ]]
    selected, _ = module._choices(lines, CHOICE_FIELDS["tax_declaration"], {"roc": r"本人僅為中華民國稅務居住者", "other": r"本人為具有"})
    assert selected == {"roc", "other"}


@pytest.mark.parametrize("size,copies", [((5001, 4000), 1), ((3500, 3000), 2)], ids=["oversized-embedded-image", "oversized-page-total"])
def test_mixed_pdf_checks_source_image_pixel_budget_before_rasterizing(size, copies, monkeypatch):
    module = importlib.import_module("backend.app.ocr.analyzer")
    raster = BytesIO()
    with Image.new("1", size, 1) as image:
        image.save(raster, "PNG")
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((20, 40), "Synthetic native text plus compressed large raster image.")
        for copy in range(copies):
            page.insert_image(fitz.Rect(0, 100 + copy * 200, 300, 290 + copy * 200), stream=raster.getvalue())
        data = pdf.tobytes(garbage=4, deflate=True)

    def forbidden_render(*args, **kwargs):
        pytest.fail("Source image limits must be checked before PDF rasterization")

    monkeypatch.setattr(fitz.Page, "get_pixmap", forbidden_render)
    with pytest.raises(module.OCRValidationError) as caught:
        module.analyze_document(data, "synthetic.pdf", "application/pdf", DOCUMENT)
    assert caught.value.code == "IMAGE_TOO_LARGE" and caught.value.status == 413


def test_official_full_fourth_tax_question_is_a_supported_label():
    module = importlib.import_module("backend.app.ocr.analyzer")
    from backend.app.ocr.form_profiles import TAX_QUESTIONS
    line = module.TextLine("4. 您是否具有除臺灣及美國以外之其他國家或地區之稅務居民身分？ [X] 是 [ ] 否", .99, module._box(2, .1, .1, .7, .02), "native")
    selected, anchor = module._choices([line], TAX_QUESTIONS[-1], {"yes": "是", "no": "否"})
    assert selected == {"yes"} and anchor is not None


@pytest.mark.parametrize("version", ["VIE_Claim.2024.010", "VIE_Claim.2024.01A", "VIE_Claim.2024.01-rev2"])
def test_unknown_version_extension_cannot_match_supported_version_prefix(version):
    module = importlib.import_module("backend.app.ocr.analyzer")
    with fitz.open(stream=application_pdf(version=False), filetype="pdf") as pdf:
        pdf[0].insert_text((25, 82), version, fontsize=12)
        result = module.analyze_document(pdf.tobytes(), "synthetic.pdf", "application/pdf", DOCUMENT)
    assert result["analysis_status"] == "uncertain" and "form_version" in findings(result)


def test_split_field_value_preserves_the_values_low_ocr_confidence():
    module = importlib.import_module("backend.app.ocr.analyzer")
    label = module.TextLine("連絡電話：", .99, module._box(1, .1, .1, .1, .02), "ocr")
    value = module.TextLine("SYNTHETIC-LOW-CONFIDENCE", .1, module._box(1, .21, .1, .4, .02), "ocr")
    _, anchor = module._find_field([label, value], ("連絡電話",))
    assert anchor.confidence == .1


def test_roc_exemption_cannot_be_inferred_from_generic_simplified_prefix(monkeypatch):
    module = importlib.import_module("backend.app.ocr.analyzer")
    data = application_pdf()
    lines, _, _, _, _ = module._extract(data, "application/pdf")
    for index, line in enumerate(lines):
        if line.text.startswith("稅務聲明"):
            lines[index] = module.TextLine("稅務聲明：[X] 本人仅为美国税务居住者 [ ] 本人為具有FATCA身分或其他稅務居住者", .99, line.box, "ocr")
    monkeypatch.setattr(module, "_extract", lambda *args: (lines, "rapidocr", False, 1, []))
    result = module.analyze_document(data, "synthetic.pdf", "application/pdf", DOCUMENT)
    assert result["analysis_status"] == "uncertain"
    assert "tax_declaration" in findings(result)
    assert "tax_roc_confirmation" not in findings(result)


def test_multiselect_exclusive_choices_are_flagged_and_not_used_for_exemptions():
    result = analyze(overrides={"付款方式": "[X] 同最近一次理賠帳戶 [X] 匯款至下列銀行帳戶 [ ] 支票給付", "稅務聲明": "[X] 本人僅為中華民國稅務居住者 [X] 本人為具有FATCA身分或其他稅務居住者"})
    assert {"payment_method", "tax_declaration"} <= findings(result).keys()
    assert result["analysis_status"] == "uncertain"


def test_unknown_version_is_uncertain_and_missing_labels_have_no_fabricated_box():
    result = analyze(version=False)
    assert result["analysis_status"] == "uncertain"
    assert findings(result)["form_version"]["bounding_box"] is None
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((20, 40), "保險金申請書", fontname="china-t")
        page.insert_text((20, 65), "VIE_Claim.2024.01", fontsize=11)
        module = importlib.import_module("backend.app.ocr.analyzer")
        result = module.analyze_document(pdf.tobytes(), "synthetic.pdf", "application/pdf", DOCUMENT)
    item = findings(result)["contact_phone"]
    assert item["bounding_box"] is None and item["location_status"] == "unlocated"
    assert all(box["width"] < 0.9 for box in result["bounding_boxes"])


def test_mixed_native_text_and_raster_ink_runs_real_ocr_and_retains_manual_review():
    result = analyze(mixed=True)
    assert result["provider"] == "pdf_text+rapidocr"
    assert any(item["field"] == "contact_phone" and item["value"] == "已辨識內容（隱私遮罩）" for item in result["extracted_fields"])
    assert "mixed_content" in findings(result)
    assert result["analysis_status"] == "uncertain"


def test_unreadable_synthetic_pen_strokes_are_never_claimed_to_be_blank_or_complete():
    result = analyze(scribble=True)
    assert result["provider"] == "pdf_text+rapidocr"
    assert result["analysis_status"] == "uncertain" and result["requires_human_review"] is True
    assert "mixed_content" in findings(result)
    if "contact_phone" in findings(result):
        assert "不代表原件空白" in findings(result)["contact_phone"]["message"]
