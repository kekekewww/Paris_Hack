"""New synthetic OCR regression documents; never overwrite the original demo.

These deliberately simplified layouts exercise versioned *label* rules. They
are not official forms, accepted applications, or handwriting benchmarks.
Run: .venv/Scripts/python.exe demo/generate_review_documents.py
"""
from io import BytesIO
from pathlib import Path

import pymupdf as fitz
from PIL import Image


OUTPUT = Path(__file__).resolve().parent / "review-documents"


def application_pdf(*, overrides=None, continuation=False, mixed=False, scribble=False, version=True):
    values = {
        "被保人姓名": "王範例（合成）", "保單號碼": "SYNTHETIC-REVIEW",
        "身分證字號": "SYNTHETIC-ID", "連絡電話": "SYNTHETIC-PHONE",
        "事故當時職業/工作內容": "合成展示工作", "申請項目": "[X] 住院、手術 [ ] 門診",
        "申請事由": "[ ] 意外 [X] 疾病", "事故時間": "2026/10/03",
        "其他公司申請理賠": "[X] 否 [ ] 是", "付款方式": "[ ] 同最近一次理賠帳戶 [X] 匯款至下列銀行帳戶 [ ] 支票給付",
        "戶名": "王範例（合成）", "銀行/郵局": "合成銀行", "分行": "合成分行", "帳號": "SYNTHETIC-ACCOUNT",
        "稅務聲明": "[X] 本人僅為中華民國稅務居住者 [ ] 本人為具有FATCA身分或其他稅務居住者",
        "(申請人)受益人簽名": "合成印字，須人工核對", "簽署日期": "2026/10/26",
    }
    values.update(overrides or {})
    with fitz.open() as pdf:
        page = pdf.new_page(width=650, height=1000)
        page.insert_text((25, 35), "保險金申請書", fontname="china-t", fontsize=18)
        page.insert_text((25, 58), "合成測試／非官方表單／不可送件", fontname="china-t", fontsize=12)
        if version:
            page.insert_text((25, 82), "VIE_Claim.2024.01", fontsize=12)
        for index, (label, value) in enumerate(values.items()):
            y = 120 + index * 43
            page.insert_text((25, y), f"{label}：{'' if (mixed or scribble) and label == '連絡電話' else value}", fontname="china-t", fontsize=11)
            if mixed and label == "連絡電話":
                # Printed value is a raster overlay, deliberately absent from
                # the PDF text layer (same extraction risk as scanned ink).
                with fitz.open() as stamp:
                    stamp_page = stamp.new_page(width=180, height=28)
                    stamp_page.insert_text((2, 20), "SYNTHETIC-PHONE", fontsize=15)
                    raster = stamp_page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    page.insert_image(fitz.Rect(88, y - 17, 260, y + 8), stream=raster.tobytes("png"))
            if scribble and label == "連絡電話":
                # Deliberately illegible synthetic pen paths, not real personal
                # handwriting and not a claim of handwriting model accuracy.
                page.draw_polyline([(100, y - 10), (104, y + 1), (108, y - 12), (112, y), (118, y - 9), (120, y + 2), (127, y - 11), (132, y)], color=(0.1, 0.1, 0.4), width=1.4)
        if continuation:
            page = pdf.new_page(width=650, height=1000)
            rows = ["FATCA及CRS身份確認同意暨聲明書(個人)", "VIE_Claim.2024.01", "臺灣稅務居民身分：[X] 是 [ ] 否", "美國納稅義務人身分：[ ] 是 [X] 否", "具有下列任一項指標：[ ] 是 [X] 否", "其他國家或地區之稅務居民身分：[ ] 是 [X] 否"]
            for index, text in enumerate(rows):
                page.insert_text((25, 50 + index * 45), text, fontname="china-t", fontsize=13)
            page = pdf.new_page(width=650, height=1000)
            for index, text in enumerate(["第三部分：稅籍資料", "VIE_Claim.2024.01", "立同意書人(受益人)簽名：合成印字", "填寫日期：2026/10/26"]):
                page.insert_text((25, 50 + index * 45), text, fontname="china-t", fontsize=13)
        return pdf.tobytes(garbage=4, deflate=True)


def generate(output=OUTPUT):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    scenarios = {
        "central-complete.pdf": {},
        "central-missing.pdf": {"overrides": {"連絡電話": "____", "付款方式": "[ ] 同最近一次理賠帳戶 [ ] 匯款至下列銀行帳戶 [ ] 支票給付", "稅務聲明": "[ ] 本人僅為中華民國稅務居住者 [ ] 本人為具有FATCA身分或其他稅務居住者"}},
        "central-cheque-outpatient.pdf": {"overrides": {"申請項目": "[X] 門診 [ ] 住院、手術", "申請事由": "____", "事故時間": "____", "付款方式": "[ ] 同最近一次理賠帳戶 [ ] 匯款至下列銀行帳戶 [X] 支票給付", "戶名": "____", "銀行/郵局": "____", "分行": "____", "帳號": "____"}},
        "central-tax-continuation.pdf": {"overrides": {"稅務聲明": "[ ] 本人僅為中華民國稅務居住者 [X] 本人為具有FATCA身分或其他稅務居住者"}, "continuation": True},
        "central-mixed-layer.pdf": {"mixed": True},
        "central-handwritten-uncertain.pdf": {"scribble": True},
        "central-unversioned.pdf": {"version": False},
    }
    for name, options in scenarios.items():
        (output / name).write_bytes(application_pdf(**options))
    with fitz.open(stream=application_pdf(), filetype="pdf") as pdf:
        pixels = pdf[0].get_pixmap(matrix=fitz.Matrix(1.6, 1.6))
        with Image.open(BytesIO(pixels.tobytes("png"))) as image:
            image.save(output / "central-scanned.png")
    return sorted(path.name for path in output.iterdir())


if __name__ == "__main__":
    print("\n".join(generate()))
