"""Reproduce the clearly labelled synthetic OCR demonstration files.

Run from the project root: .venv/Scripts/python.exe demo/generate_documents.py
No official form is copied or completed. All names/identifiers/events are fictional.
"""
from pathlib import Path
import io

import pymupdf as fitz
from PIL import Image, ImageFilter


OUTPUT = Path(__file__).resolve().parent / "documents"


def application_pdf(missing=False):
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.draw_rect((0, 0, 595, 125), fill=(0.04, 0.28, 0.25), color=None)
        page.insert_text((38, 46), "保險金申請書", fontname="china-t", fontsize=26, color=(1, 1, 1))
        page.insert_text((38, 77), "合成展示文件｜虛構資料，非官方表單", fontname="china-t", fontsize=16, color=(1, 1, 1))
        page.insert_text((38, 101), "僅供 OCR 測試；不可送件，不能作為官方樣張。", fontname="china-t", fontsize=12, color=(1, 1, 1))
        rows = [
            ("被保人姓名", "＿＿＿＿＿＿" if missing else "王小明（虛構）"),
            ("保單號碼", "SYNTHETIC-POLICY-0001"),
            ("身分證字號", "SYNTHETIC-0001"),
            ("申請項目", "[ ] 住院／手術  [ ] 門診" if missing else "[X] 住院／手術  [ ] 門診"),
            ("事故時間", "2026/10/03（虛構事故）"),
            ("(申請人)受益人簽名", "＿＿＿＿＿＿" if missing else "王小明（虛構印字示意）"),
            ("簽署日期", "2026/02/31" if missing else "2026/10/17"),
        ]
        for index, (label, value) in enumerate(rows):
            y = 165 + index * 61
            page.draw_rect((32, y - 25, 563, y + 21), color=(0.74, 0.80, 0.78), fill=(0.96, 0.98, 0.97))
            page.insert_text((44, y), f"{label}：{value}", fontname="china-t", fontsize=14)
        notes = [
            "測試對照：簽署日期對應官方第 1 頁「中華民國 年 月 日」。",
            "此示意僅測指定欄位的可辨識性；不推定所有欄位皆為必填。",
            "簽名印字只供測試，OCR 無法驗證簽名或文件的真實性。",
            "沒有真實保戶、身分證號、醫療紀錄或銀行帳戶。",
        ]
        for index, text in enumerate(notes):
            page.insert_text((38, 640 + index * 23), text, fontname="china-t", fontsize=11, color=(0.23, 0.31, 0.29))
        page.insert_text((38, 793), "SYNTHETIC DEMO / NOT AN OFFICIAL CARDIF FORM / 1", fontsize=9)
        return doc.tobytes(garbage=4, deflate=True)


def render(pdf):
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        pixmap = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        return Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")


def generate_mixed_quality(output=OUTPUT):
    """第一頁保留合成文字層，第二頁只嵌入既有模糊圖片。"""
    output = Path(output)
    target = output / "application-mixed-quality.pdf"
    with fitz.open(output / "application-complete.pdf") as source, fitz.open() as mixed:
        mixed.insert_pdf(source, from_page=0, to_page=0)
        dimensions = source[0].rect
        page = mixed.new_page(width=dimensions.width, height=dimensions.height)
        page.insert_image(page.rect, filename=str(output / "application-blurred.png"))
        mixed.save(target, garbage=4, deflate=True)
    return target


def generate(output=OUTPUT):
    output.mkdir(parents=True, exist_ok=True)
    complete = application_pdf()
    missing = application_pdf(missing=True)
    (output / "application-complete.pdf").write_bytes(complete)
    (output / "application-missing.pdf").write_bytes(missing)
    with render(complete) as image:
        image.save(output / "application-clear.png")
        image.save(output / "application-clear.jpg", quality=93)
        raster = io.BytesIO()
        image.save(raster, format="PNG")
        with fitz.open() as scan:
            page = scan.new_page(width=595, height=842)
            page.insert_image(page.rect, stream=raster.getvalue())
            scan.save(output / "application-scanned.pdf", garbage=4, deflate=True)
        with image.resize((119, 168), Image.Resampling.BILINEAR).resize(image.size, Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(11)) as blurred:
            blurred.save(output / "application-blurred.png")
    with render(missing) as image:
        image.save(output / "application-missing.png")
    with fitz.open(stream=complete, filetype="pdf") as source, fitz.open() as many:
        for _ in range(11):
            many.insert_pdf(source)
        many.save(output / "application-eleven-pages.pdf", garbage=4, deflate=True)
    generate_mixed_quality(output)
    return sorted(path.name for path in output.iterdir() if path.is_file())


if __name__ == "__main__":
    for name in generate():
        print(name)
