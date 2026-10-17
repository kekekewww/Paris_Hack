# 展示操作腳本

更新日期：2026-10-17（臺灣）。只使用本專案合成文件，不輸入真實身分、病歷或保單資料，不送出真實保險申請。此腳本列出可重現操作與預期結果，並非 Phase 2／Phase 3 通過報告。

## 展示前確認

依 [README](../README.md) 安裝、建置並啟動服務。在本機完整服務使用 `http://127.0.0.1:8000/?service=api`；前端開發服務使用 `http://127.0.0.1:5174/?service=mock`。API 模式需要後端可用，Mock 模式可獨立操作。Docker 映像不內含展示文件，上傳檔案請從專案的 `demo/documents/` 選取。

本腳本 A–H 維持預設 `LLM_PROVIDER=grounded_rules`。先讀取 `/api/v1/health`，確認 `service_mode=api`、`llm_provider=grounded_rules`、`llm_configured=false`、`llm_verified=false`，並檢查實際 `ocr_provider`。向觀眾說明：此模式的對話是本機官方規則與詞彙檢索，不是生成式 LLM；PDF 文字擷取／RapidOCR 是實際文件處理。若 OCR 依賴不可用，先處理依賴或明確展示錯誤，不能拿 Mock 充當真實結果。

| 模式 | 開啟方式 | 應向觀眾說明 |
|---|---|---|
| Mock | 網址加 `?service=mock` | 對話與分析為固定模擬情境，`provider=mock`、`is_simulated=true` |
| API + 本機規則 | 網址加 `?service=api`，後端 `LLM_PROVIDER=grounded_rules` | 真實 HTTP、本機官方檢索／規則、真實 OCR；不宣稱生成式 AI |
| 可選外部 Adapter，未配置 | 僅在隔離測試環境設定 `LLM_PROVIDER=openai_compatible`，key／model 保持空白後重啟 | 對話回 `503 / LLM_NOT_CONFIGURED`，不退回 Mock；不能宣稱真實外部整合已通過 |

`openai_compatible` Adapter 已實作，離線 HTTP transport 測試不能替代真實模型請求。外部設定僅限後端：`LLM_BASE_URL` 預設 `https://api.openai.com/v1`，`LLM_API_KEY` 與 `LLM_MODEL` 都必須由操作者明確配置，沒有預設模型。本輪展示不要求提供金鑰、不切換至真實外部服務；真實 LLM 驗收仍為 BLOCKED，詳見 [LLM 整合紀錄](LLM_INTEGRATION.md)。

外部設定齊全時，`llm_configured=true` 仍只代表設定齊備，`llm_verified` 固定為 `false`。即使日後啟用外部模式，類別／條件提案與無依據拒答仍由規則產生；只有有依據的準備回答會傳送本次檢索證據，不傳使用者問題、對話歷史或原始上傳文件。模型只可選取完整原樣段落，失敗不回退成成功結果。展示時須逐次核對實際回覆的 `provider`，不能由健康檢查 `ok` 推定模型已呼叫成功。

## 合成文件

檔案由 `demo/generate_documents.py` 產生，是測試用簡化申請書，不是官方空白表單。檔名的 complete／clear 僅描述合成輸入，不表示正式審核完成。

| 檔案（位於 `demo/documents/`） | 用途 | API 分析預期 |
|---|---|---|
| `application-complete.pdf` | 有文字層的指定欄位完整樣本 | `pdf_text`；仍有簽名人工確認 |
| `application-missing.pdf` | 有文字層的缺漏樣本 | 指定欄位疑點與簽名提醒 |
| `application-clear.png` | 清晰圖片 | `rapidocr`；保留人工確認 |
| `application-clear.jpg` | 清晰 JPG | 圖片解碼與 OCR 路徑 |
| `application-missing.png` | 圖片缺漏樣本 | 姓名／日期等未可靠辨識內容的提醒 |
| `application-blurred.png` | 模糊圖片 | `uncertain`、清晰度與人工確認提示 |
| `application-scanned.pdf` | 無文字層掃描 PDF | `rapidocr`，可回傳頁碼與正規化框線 |
| `application-eleven-pages.pdf` | 11 頁邊界案例 | 前端頁數檢查及後端均應拒絕，不產生成功分析 |
| `application-mixed-quality.pdf` | 清晰文字頁與模糊掃描頁共存 | `pdf_text`、整體 uncertain；第 2 頁有品質提示，不錯指第 1 頁 |

## A：不知道類型，意外事故住院

1. API 首頁按「開始使用」。輸入「我因車禍住院三天，沒有接受手術，想準備文件」，按「送出描述」。
2. 檢查回覆有官方引用，提出住院醫療方向並保留未知條件；送出描述後尚未直接套用類別。
3. 按「確認並建立清單」，進入文件準備工作區。展開保險金申請書的「文件說明與官方來源」。
4. 開啟「官方應備文件依據」、「開啟官方空白表單」或填寫範例，核對是已查核的官方網址。關閉外部分頁後繼續本機流程。
5. 回工作區，按「上傳與檢查」，選 `application-missing.png`，按「開始分析」。檢查結果的 provider 應為 `rapidocr`、`is_simulated=false`；顯示提醒、位置及人工確認。
6. 點框線查看對應提醒，再按一個「我已人工確認」。提醒與信心保留，文件仍為需要補充或人工確認。
7. 關閉視窗，按「查看準備摘要」，再按「下載摘要」。摘要應包含未完成項目與官方送件資訊，明確表示不是核准或送件證明。

## B：已知道是醫療門診

1. 回首頁按「開始搜尋」，選「醫療門診」。事故原因選疾病、手術選沒有接受手術；其他不確定項目保留原值。
2. 按「建立文件清單」，確認必備、條件式及適用條件待確認分別呈現。展開診斷書／收據說明，核對來源與正副本差異，不宣稱個案必然適用。
3. 在申請書上傳 `application-clear.png`；也可另用 `application-clear.jpg` 重走圖片路徑。即使文字可辨識，簽名仍需人工確認。
4. 在未分析的其他文件選「我已自行備妥，尚未檢查」，確認只改準備狀態。搜尋清單、隱藏／開啟助手、查看摘要，再返回工作區。

## C：可能重大疾病，資訊不足

1. 從引導入口輸入「可能是重大疾病，但我還不確定」。
2. 預期系統追問本次住院、門診或確診情況，不以「可能」當作已確診，不直接產生給付結論。
3. 另由直接選擇進入「防癌或重大疾病」，首次申請與其他條件維持「尚不確定」，建立清單。
4. 確認病理／檢驗等條件式項目保持待確認；修改案件條件後再檢查清單。不得因未知或非首次便宣稱免附所有相關資料。

## D：指定欄位完整與缺漏比較

1. 在任一已確認類別的申請書上傳 `application-complete.pdf`。等待 PDF 頁數檢查完成，再按「開始分析」。
2. 查看 PDF 畫布、頁碼選擇及提醒。Network 回應應為 `provider=pdf_text`、`is_simulated=false`；完整指定文字欄位仍保留簽名人工確認與 `needs_attention`。
3. 換成 `application-missing.pdf` 再分析，比較缺漏提醒。人工確認只記錄已檢視，不能變成自動通過；選「我已自行備妥」也不能抹除既有分析疑點。
4. 選 `application-eleven-pages.pdf`，確認顯示超過 10 頁限制，沒有成功分析。後端直接 HTTP 的拒絕另由自動化測試驗證，不能只靠前端限制代表後端已測過。
5. 改傳 `application-mixed-quality.pdf`，確認第 1 頁仍有實際文字擷取，但整體 uncertain；切換預覽第 2 頁，點品質提示標記，對應提醒須標第 2 頁並顯示「官方表單參考」。清晰度標記是人工提示區，沒有推定第 1 頁有品質問題。

## E：模糊與掃描文件

1. 在申請書上傳 `application-blurred.png`，確認 `provider=quality_precheck`、`analysis_status=uncertain`、欄位清單為空；畫面明示清晰度預檢、未執行 OCR、需重傳及人工確認。這是當次影像量測，不是官方清晰度要求，也不冒稱模型已辨識。
2. 改傳 `application-scanned.pdf`，確認走 `rapidocr`，不是 `pdf_text` 或 Mock。檢查頁碼、框線與原件能對照；不保證所有字形都辨識正確。
3. 關閉視窗並重新整理，確認結構化結果仍可讀；原件預覽需重新選取檔案，系統沒有保存供下載的原始文件。

## F：有依據與無依據問答

1. 在工作區助手輸入「診斷書需要正本嗎？」或「保險金申請書要注意哪些欄位？」。
2. 預期回覆是可追溯準備資訊，附官方引用；不能拿引用當作個人保障或給付結論。
3. 再問「可以保證賠多少錢？」；預期明確無法確認，引用若存在只用於服務邊界，不支持個案金額。
4. 再問「電子簽名有法律效力嗎？」；預期 `uncertain`，表示目前官方索引沒有足夠依據，不用不相關引用拼湊答案。

## 受控故障情境 G、H

以下是在測試環境主動阻擋請求，用來驗證失敗處理；不表示官方網站或真實外部服務當時已失效。測試後務必解除阻擋；不修改官方來源索引來製造故障。

### G：官方文件暫時無法開啟

1. 在桌面 Chromium 的開發者工具開啟 Network request blocking，新增 `*://life.cardif.com.tw/documents/*` 並啟用，讓所有對應分頁也套用阻擋；若工具只對目前分頁生效，改用下述 Playwright context 範圍。
2. 展開申請書來源，按「開啟官方空白表單」。預期新分頁顯示瀏覽器的受控下載／連線失敗，原工作區仍可操作，案件不會因此標成完成或改用未知網址。
3. 關閉失敗分頁，從頁首「官方理賠資訊」回官方入口核對；解除文件阻擋，再次開啟原連結。解除後是否真實可讀須另行觀察，不能以攔截回覆當作官方可用性證據。

Playwright 測試可在操作前套用以下攔截；`context` 必須是準備工作區與新分頁共用的 browser context：

```js
const officialDocuments = 'https://life.cardif.com.tw/documents/**';
await context.route(officialDocuments, route => route.abort('failed'));
// 以 UI 開啟官方表單，檢查失敗新分頁與仍可操作的工作區。
await context.unroute(officialDocuments);
```

### H：API 暫時失敗、重試及清除

1. 在 API 模式，用開發者工具阻擋 `*/api/v1/health`，再重新整理。
2. 預期顯示「服務暫時無法使用」與目前 API 模式，提供「重試」及官方入口；不能顯示模擬成功。
3. 解除阻擋，按「重試」，確認恢復原本 API 流程。也可只阻擋 `*/api/v1/cases/*/messages`，送出問題後解除，再按「重試」。
4. 開啟 Network 核對恢復後確實呼叫 `/api/v1`；在工作區按「清除測試案件」，確認對話框後應返回首頁。舊案件 GET 應為 404，不能再使用已清除結果。

現有 `tests/api-e2e.spec.js` 的「API 暫時 503 顯示錯誤並可重試，沒有回退到 Mock」案例，使用一次性的 `route.fulfill(503)` 後恢復真實請求。這是受控 503；同一測試中的其他真實請求仍需後端運作。

Mock 可另開「展示測試工具」→「模擬下次服務錯誤」，進行一次服務操作、查看錯誤並重試；這只能證明 Mock 的恢復邏輯。

## 每次展示的收尾與紀錄

在 1440、768、390 px 檢查主要流程、文件視窗及摘要無水平溢出；以鍵盤完成選項、上傳及關閉視窗，檢查焦點與 Console。下載摘要後回工作區「清除測試案件」，不要將合成文件當成真實理賠送件。

自動化入口為 `npm test`、`npm run test:e2e`、`npm run test:pdf`、`npm run test:api`；後端依 README 執行 pytest。API 測試需要已建置前端與後端依賴。具體通過數、失敗、環境與執行時間應記錄在該次驗收報告；本腳本不預填測試成果。Docker 實際建置／啟動與公開 HTTPS 部署須另外驗證。
