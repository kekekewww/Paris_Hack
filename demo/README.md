# 合成文件與真實 OCR

`documents/` 內全部檔案均使用虛構資料，沒有真實保戶或醫療資料，也不是官方表單或可送件樣張。姓名明示「王小明（虛構）」，識別碼採 `SYNTHETIC`，不使用有效身分證字號。

| 檔案 | 展示用途 |
| --- | --- |
| application-complete.pdf | 可擷取文字的清楚 PDF；指定欄位有內容，簽名仍需人工確認 |
| application-missing.pdf / .png | 姓名與簽名疑似空白、未勾選申請項目、日期 2026/02/31 無效 |
| application-clear.png / .jpg | 清楚中文圖片，實際使用 RapidOCR 本機模型 |
| application-scanned.pdf | 僅含圖片的掃描 PDF，不能使用 PDF 文字層取代 OCR |
| application-blurred.png | 降解析度與模糊化，應回傳 uncertain 並要求人工確認 |
| application-eleven-pages.pdf | 11 頁純合成文件，應遭 10 頁上限拒絕 |
| application-mixed-quality.pdf | 第 1 頁文字層清晰、第 2 頁掃描模糊；保留實際文字擷取並在第 2 頁提示重傳 |

重新產生資料：

```powershell
.venv/Scripts/python.exe demo/generate_documents.py
```

執行實際解析與 OCR 測試（需要後端依賴）：

```powershell
.venv/Scripts/python.exe -m pytest backend/tests/test_ocr.py -q --basetemp=.local/pytest/ocr
```

清晰文件的實際 provider 為 `pdf_text` 或 `rapidocr`；品質不足影像回 `quality_precheck`，代表真實影像品質預檢並明示未執行 OCR，欄位清單為空、結果 uncertain，需重傳與人工確認。三者均 `is_simulated=false`。合成輸入不是模擬結果；判讀依當次輸入的文字擷取、模型或品質量測產生，不能將工程清晰度閾值當作官方規定。

檢查範圍是官方申請書第 1 頁指定欄位的可辨識性，不能推定所有欄位一律必填。官方簽署區印刷文字為「中華民國 年 月 日」，合成文件以「簽署日期」標示其測試對照。條件式 FATCA／CRS 頁面不一律要求填寫。任何文件與簽名均無法由本原型驗真；即使指定欄位可辨識，仍保留簽署人工確認提示。

已知限制：本機中文模型可能漏辨複雜繁體字，文件類型須以標題及多個獨立欄位交叉辨識。非申請書目前僅擷取文字並提示人工確認。45 秒處理預算在每頁及每次模型呼叫前後檢查；模型正在執行的單次呼叫未使用獨立程序硬中止，正式多使用者部署前需增加程序隔離與工作佇列。
