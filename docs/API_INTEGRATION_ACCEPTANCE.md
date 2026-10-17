# 真實 API 與前端整合驗收紀錄

更新日期：2026-10-17。此文件記錄實際執行結果，與 `PHASE1_ACCEPTANCE.md` 的 Mock 驗收分開。

## 驗收範圍

- `tests/api-e2e.spec.js`：9 個情境，1440×1000、768×1024、390×844 三種尺寸，共 27 項。
- FastAPI 同源 `http://127.0.0.1:8000` 提供 production `dist`，前端使用 `?service=api`。
- 實際呼叫健康檢查、案件 CRUD、文件清單、條件規則、對話、來源查詢、文件分析與人工確認；成功業務資料均來自真實 API，未替換為模擬結果。
- 清晰／缺漏 PNG 與掃描 PDF 由真實 `rapidocr`、有文字層 PDF 由 `pdf_text` 處理；驗證 `is_simulated=false`、實際欄位、信心、位置、缺漏及持續需要人工覆核。模糊影像改由真實清晰度預檢 `quality_precheck` 保守處理，明示未執行 OCR。
- 工作區提問也透過真實對話 API 顯示回覆；HTTP 規則檢查涵蓋手術適用條件的 yes→no 重算，以及重大疾病資訊不足時病理文件維持待確認。
- PDF 預覽需檢查 canvas 實際有文件像素內容，並驗證前後端均拒絕超過 10 頁的文件。
- API 回應僅有兩類明確的時序／故障控制：將單次瀏覽器健康檢查替換為 503 以驗證錯誤恢復；延後交付原樣的真實對話回應以驗證導覽競態。前後另以實際 HTTP 確認服務正常。
- 官方外部視窗測試確認實際連結開啟到指定官方 PDF URL，該外部頁面的內容由測試提供標示文字；此項不代表官方網址即時可用性查核，來源查核另見官方來源文件。

## 執行方式

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH = 'C:\Users\kevin\AppData\Local\ms-playwright\chromium_headless_shell-1248\chrome-headless-shell-win64\chrome-headless-shell.exe'
node node_modules/@playwright/test/cli.js test --config=playwright.api.config.js --project=api-desktop-1440
node node_modules/@playwright/test/cli.js test --config=playwright.api.config.js
node node_modules/@playwright/test/cli.js test --config=playwright.config.js
node node_modules/@playwright/test/cli.js test --config=playwright.demo.config.js
```

本機 OCR 為單一執行鎖；API 測試使用一個 worker 串行，避免將同時分析導致的預期容量拒絕混入功能結果。伺服器測試容量為 `RATE_LIMIT_REQUESTS=1000`，未停用速率限制。所有測試只刪除自己建立的虛構案件。

## 失敗與修復歷程

| 輪次 | 實際結果 | 原因與處理 |
|---|---|---|
| 第一輪桌面（未完整跑完） | 兩個 UI 流程逾時；掃描 PDF 真實 HTTP 分析通過；中止後續執行 | 原生 `fetch` 作為 service 物件屬性呼叫時產生 `Illegal invocation`，UI 在尚未送出 API 前顯示連線失敗。實際獨立 HTTP 健康檢查仍為 200。修正 adapter 將原生 fetch 綁定 `globalThis`，並新增單元回歸。 |
| 第二輪桌面 | 4 passed／5 failed，2.1 分鐘 | 掃描 PDF、HTTP 契約／案件隔離／安全回應、503 重試、延遲真實回應導覽已通過。其餘失敗包含並行 OCR 容量、測試觀測問題及正式靜態檔案 MIME，詳如下列。 |
| 第三輪（前 3 項後中止） | 引導與缺漏 PNG 通過（46.8 秒）；清晰 PNG、完整 PDF 的原文姓名斷言失敗 | 最新 OCR 回傳已加入隱私遮罩，實際值為「已辨識內容（隱私遮罩）」。改驗欄位已辨識、信心至少 0.8、頁碼正確、姓名與日期無缺漏 finding，並驗證分析 JSON 沒有合成姓名／保單原文；不要求 API 洩漏原文。 |

第二輪的具體失敗：

1. 兩個 worker 同時分析，真實後端依單工鎖回傳 `503 OCR_BUSY`。改用一個 worker 驗證功能；未移除或放寬 OCR 結果斷言。
2. Chromium 對磁碟檔案組成的 multipart 請求回傳 `postDataBuffer()=null`，造成兩個已取得分析結果的測試觀測失敗。改為原樣轉送 native fetch，僅觀察實際 FormData 欄位名稱，仍要求只有 `file` 且實際 API 分析非模擬。
3. `GET /assets/pdf.worker-PhvoOpM7.mjs` 回 200，但 `Content-Type: text/plain; charset=utf-8`。瀏覽器拒絕 module worker，阻止 PDF 預覽及前端頁數驗證，屬產品整合問題。已提供實際 trace 與 HTTP Header 證據交由後端修復；不可忽略瀏覽器 module 安全要求。

重新啟動後的實際 HEAD 已確認該 `.mjs` 回 200、`Content-Type: text/javascript; charset=utf-8`；後續全 27 項瀏覽器測試已確認三尺寸的 PDF 預覽、真實文字擷取及頁數驗證均可運作。

只讀測試審查另修正問答 fixture：「保險金申請書應該如何準備？」過於籠統且未指定文件上下文，目前有限官方語料會安全回覆 `uncertain`，不保證有引用。成功問答案例改問「保險金申請書有哪些欄位與簽名需要確認？」，仍嚴格驗證真實 API 的 `response_type=answer`、來源引用及 UI 呈現。此為測試輸入對應能力邊界，未改產品以迎合測試。

## 已驗證結果

**最終凍結版本：27 passed（1.9 分鐘），exit 0；桌面、平板與手機各 9／9。** 包含真實 OCR、純清晰度預檢、混合 PDF 逐頁定位、已繪製 canvas、正式 HTTP 契約、來源引用、隱私遮罩、錯誤恢復及案件持續可用；每項均驗證主頁沒有未處理 JavaScript 或非預期 console error。`test-results-api/.last-run.json` 同時為 passed、failedTests 空陣列。

最終 `analysisResult` 品質／混合頁面分支與信心標籤凍結後，另重跑完整 Mock：**63 passed（1.4 分鐘），exit 0；三尺寸各 21／21，axe 零違規、console／pageerror 零錯誤。** 僅執行既有測試，未修改產品、測試或斷言；`test-results/.last-run.json` 為 passed、failedTests 空陣列。

本機 API／UI 功能驗收通過，不代表真實外部 LLM、公開 HTTPS、Phase 2／3 整體或專案已完成；外部依賴仍依下方能力邊界保留。

歷史成功：上傳按鈕狀態修復前也曾完整 **27 passed（5.6 分鐘），exit 0**，但後續確實發現單次 OCR 例外，未以該次成功覆蓋失敗，詳如下列。

本輪 Mock 回歸第一次完整執行為 **58 passed／5 failed（2.2 分鐘），exit 1**。失敗明細與待重跑項目：

- 三尺寸的 10 MB 拒絕訊息被「請先選擇文件」覆蓋：無效選檔清空 currentFile 後分析按鈕仍啟用。修復方向為統一按鈕狀態，無有效檔案及 PDF 檢查失敗時禁用，合法換檔後恢復。測試新增嚴格禁用斷言，保留原大小錯誤文字斷言。
- 平板與手機 axe 在首頁初始化按鈕由 disabled opacity 過渡到啟用時量到不完整對比。原測試在服務尚未 ready 前就等待動畫，隨後的新動畫未被涵蓋。改為兩入口先確認 enabled，再等待實際動畫；所有 WCAG 規則與零違規斷言保持完整。

上述修復後的結果：

| 套件 | 結果 | 檢查內容 |
|---|---|---|
| 三尺寸針對回歸 | 9 passed，38.9 秒，exit 0 | unsupported／合法換檔、10 MB／禁用、ready 後 axe |
| PDF 專用套件 | 2 passed，11.3 秒，exit 0 | 超過 10 頁與損毀 PDF 禁用；合法換檔啟用、canvas 可見及切頁 |
| 完整 Mock 回歸 | 63 passed，2.3 分鐘，exit 0 | 三尺寸各 21／21、axe 零違規、console／pageerror 零錯誤、原有競態回歸 |
| 情境 G 獨立桌面套件 | 1 passed，13.6 秒，exit 0 | 外部 PDF 注入失敗、真實案件未變、摘要可下載 |
| 新品質／混合 PDF 三尺寸針對驗證 | 6 passed，28.0 秒，exit 0 | 純預檢未執行 OCR、人工確認不洗白、混合 PDF 第 2 頁標記與參考連結 |
| 新品質／混合 PDF 最終完整 API | 27 passed，1.9 分鐘，exit 0 | 三尺寸各 9／9、真正 RapidOCR 及 PDF 文字擷取持續通過；第 2 頁對應提醒實際進入可見範圍 |
| 最終共用元件完整 Mock 回歸 | 63 passed，1.4 分鐘，exit 0 | 品質／混合 PDF 分支與信心標籤凍結後重跑；三尺寸各 21／21、axe 零違規、console／pageerror 零錯誤 |

品質預檢改善前，上傳按鈕修復後的全套曾為 **26 passed／1 failed（4.8 分鐘），exit 1**：桌面 9／9、平板 8／9、手機 9／9。唯一失敗是平板模糊 PNG 的真實 analyze endpoint 回 `503 OCR_UNAVAILABLE`，訊息「本機 OCR 無法處理此文件，請稍後重試或人工檢查。」；不是 `OCR_BUSY` 或 `OCR_TIMEOUT`。同一份文件在該輪桌面與手機均通過，先前完整 27 項也均通過。測試保留原 200 成功及零非預期 console error 斷言，未以純重跑消除問題。

已保存 [平板 OCR 服務失敗畫面](evidence/api-tablet-ocr-unavailable.png)；當次 trace 同時確認真實 HTTP 狀態與上述結構化錯誤回應。

之後的診斷未能重現底層例外，因此不宣稱所有模型例外都已根治。實際改善是沿用既有品質閾值，讓 Pillow 實測為低品質的影像先保守停止：回 `quality_precheck`、`uncertain`、空 `extracted_fields` 與 `image_quality` 提醒，不再將此類影像送進 OCR，也不偽造缺漏欄位。清晰／缺漏 PNG 與清晰掃描 PDF 仍嚴格要求 `rapidocr`；有文字層 PDF 仍嚴格要求 `pdf_text`。模型時間預算與成功／錯誤斷言均未放寬。

新增的合成 `application-mixed-quality.pdf` 有可擷取文字的第 1 頁及模糊掃描第 2 頁。完整測試保留第 1 頁欄位辨識斷言，同時要求整體 uncertain、品質 finding 與 bounding box 均在第 2 頁。UI 實際切換第 2 頁並點擊標記，對應 finding 至少一半進入視窗，且品質提醒只標「官方表單參考」，不把工程清晰度閾值說成官方理賠要求。

為避免與容器 OCR 競爭，曾啟動後立即依資源排程中止一次，沒有完成任何測項，不計作通過或 API 故障。最新這輪正式執行時已採單工，沒有同時執行其他 OCR 測試。

## 情境 G 的故障注入邊界

`tests/demo-failure.spec.js` 與 `playwright.demo.config.js` 為獨立一項桌面測試，不擴充原 API 27 項。只對清單中的官方 PDF URL 使用 `context.route(...).abort('failed')`；實際觀察 `requestfailed` 的 `ERR_FAILED`，且失敗 request 所屬頁面就是新開啟的 popup。沒有攔截本機 API。

失敗後透過真正的 GET 案件端點，比對完整 JSON 與建立時相同；UI 保持工作區可用，摘要顯示尚未準備並可實際下載，最後刪除該測試案件。這證明故障情境可重現，**不表示官方站台目前真的故障**，也不算官方 URL 可用性查核。見 [故障後仍可操作的摘要](evidence/demo-summary-after-failure.png)。

## 視覺證據

已人工檢查 PDF 畫布及手機摘要，延續原型品牌綠、薄荷底、圓角卡片與按鈕。手機 PDF 使用單欄並可捲動，沒有橫向溢出；遮罩只針對 API 欄位回傳，本機預覽仍是使用者自行選擇的虛構檔案。

| 尺寸 | PDF 預覽 | 摘要 |
|---|---|---|
| 1440×1000 | [桌面 PDF](evidence/api-desktop-pdf.png) | [桌面摘要](evidence/api-desktop-summary.png) |
| 768×1024 | [平板 PDF](evidence/api-tablet-pdf.png) | [平板摘要](evidence/api-tablet-summary.png) |
| 390×844 | [手機 PDF](evidence/api-mobile-pdf.png) | [手機摘要](evidence/api-mobile-summary.png) |

另見 [手機真實 OCR](baseline/phase2-mobile-ocr.png)。原有設計與 Phase 1 視覺證據見 `PROTOTYPE_AUDIT.md`、`PHASE1_ACCEPTANCE.md` 與 `baseline/`。

上列六張 PDF／摘要圖保留首次完整 API 通過時的基準；以下為最終新版，已人工檢查桌面／手機純預檢與混合 PDF 提醒，明示未執行 OCR、無文字信心及第 2 頁提示區域：

| 尺寸 | 混合 PDF 第 2 頁 | 非 OCR 清晰度預檢 |
|---|---|---|
| 1440×1000 | [桌面混合 PDF](evidence/api-desktop-mixed-pdf-page2.png) | [桌面預檢](evidence/api-desktop-quality-precheck.png) |
| 768×1024 | [平板混合 PDF](evidence/api-tablet-mixed-pdf-page2.png) | [平板預檢](evidence/api-tablet-quality-precheck.png) |
| 390×844 | [手機混合 PDF](evidence/api-mobile-mixed-pdf-page2.png) | [手機預檢](evidence/api-mobile-quality-precheck.png) |

## 真實能力邊界

- 預設對話 provider 為 `grounded_rules`，屬官方資料支援的確定性回答與檢索，並非外部生成模型。即使 `is_simulated=false`，也不能將此結果標為「真實外部 LLM 已驗證」。
- 缺少外部 LLM 金鑰與實際供應商執行證據，該項保持 BLOCKED；離線 adapter 測試不代替外部呼叫。
- OCR 僅為初步完整性檢查；清晰或完整文件仍保留簽名與法律真實性的人工覆核。人工確認不刪除原分析、不提高信心、不轉為理賠核准。
- OCR 實際讀取文字以進行欄位檢查，但回傳欄位原文均已遮罩；驗收依辨識狀態、信心與預先設計缺漏的差異核對，而非索取原文。
- 測試資料皆為明示虛構的合成文件，未提交真實保險理賠。
- 本機 OCR 以單工服務驗證，不能將功能通過結果外推為並行容量或冷啟動效能保證。冷啟動與資源限制另見 `KNOWN_LIMITATIONS.md`。
- 原始 HTML 與 `baseline/original.html` 再次實測 SHA256 均為 `59A6FD5053E9811560823B3F12637EF0C7BBE7F3AA2FD9A1ABE1EA90FAD1C8A1`，原始設計檔完整保留。
