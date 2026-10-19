# LLM Adapter 與實際驗證狀態

更新日期：2026-10-17（臺灣）。

> 2026-10-19 續驗：使用者要求預留 OpenAI、Google AI Studio 與 OpenRouter（openrouter/free），隨後明確選擇「暫不建立金鑰」。三家欄位保持空白且不連動現有Adapter，不宣稱已完成原生或相容串接；詳見[供應商設定狀態](PROVIDER_SETUP.md)。本輪完整後端離線重驗與非LLM流程另見[驗收紀錄](ACCEPTANCE_NO_KEYS_20261019.md)，以下原101項描述為早期歷史。

本輪完整後端190/190中，AI測試實際113項；仍是本機規則／檢索與離線傳輸邊界，不含任何真實模型請求。

**Adapter 程式與離線 HTTP transport tests 已完成；真實 provider requests 因尚未配置／授權 credential 仍為 BLOCKED。** 本輪沒有建立、挪用或讀出既有金鑰，也沒有送出任何真實模型 API 請求。不可將下列離線測試列為外部 LLM 整合驗收通過。

## 已實作的範圍

- 預設 `grounded_rules`：執行本機官方資料檢索與確定性規則，不使用 LLM，回覆 `provider: grounded_rules`、`is_simulated: false`。
- 可選 `openai_compatible`：以後端 `httpx.AsyncClient` 呼叫設定服務的 `/chat/completions`，使用 Bearer 驗證及 `response_format: {type: json_object}`。模型必須由操作者明確指定，程式沒有預選模型。
- `UnavailableLLMProvider` 保留：不支援的 provider 或缺少必要設定會產生明確錯誤。外部請求失敗時不回退成本機規則或 Mock 成功結果。
- 所有分類、條件提案、文件要求、案件及文件狀態仍由確定性規則與 API 處理；模型沒有任何修改案件或送件工具。

此實作依 [OpenAI Chat Completions 參考文件](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) 與 [Structured Outputs 說明](https://developers.openai.com/api/docs/guides/structured-outputs) 使用 JSON mode，另在伺服器驗證完整結構。JSON mode 本身不代表內容符合專案的引用與安全要求。

## 後端環境變數

| 變數 | 預設／要求 | 說明 |
|---|---|---|
| `LLM_PROVIDER` | `grounded_rules` | 只有明確改為 `openai_compatible` 才選用外部 adapter |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | 受信任的後端部署設定；必須是 HTTPS 公開網域，不可含帳密、查詢參數、fragment 或 IP 位址 |
| `LLM_API_KEY` | 無預設，外部模式必填 | 只能留在後端環境；不沿用 `OPENAI_API_KEY`，不讀取其他 env 檔，不送往前端 |
| `LLM_MODEL` | 無預設，外部模式必填 | 由操作者指定可使用且支援所需參數的模型 |

範本應保留空白金鑰及模型，預設仍為本機模式：

```dotenv
LLM_PROVIDER=grounded_rules
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=
LLM_MODEL=
```

部署環境負責將值注入後端 process。前端不得使用 `VITE_` 或其他方式公開這些值。本輪沒有修改任何真實 env 檔；未取得授權前也不切換執行環境至真實外部模式。

服務網址只由部署環境決定，使用者問題、文件及檢索內容均無法改變服務位置。程式拒絕明顯內部／IP 網址、禁止重新導向，並忽略 proxy 環境設定。部署者仍應以網路出口政策限制核准供應商；本機語法驗證不等同 DNS 或正式網路政策驗收。

## 模型的證據與輸出邊界

1. 先執行本機官方規則。引導分類、追問、保障／金額／資格問題、安全拒答及無支持內容不會呼叫模型；這些回覆仍清楚標為 `grounded_rules`。
2. 只有已受本機資料支持的文件準備回答會進入外部 adapter。傳送內容只有本次檢索的標題、完整段落、來源 ID 與頁碼，不含原始醫療文件、案件物件、使用者對話歷史或來源 URL。
3. 模型只能選取完整、原樣的已查核段落，不能自由增加敘述或省略條件。這是保守的證據整理模式，尚未實作任意自然語言改寫的語意事實查核。
4. 模型 JSON 只能包含 `explanations`、`source_references`、空白的 `proposed_case_updates`。每個説明項目須對應本次 evidence ID，文字須等於該完整段落。
5. 引用必須精確等於所選段落的來源 ID／頁碼。即使來源在全域 registry 中存在，若不是本次所選證據也不能引用。URL 由伺服器從已查核 registry 還原，模型不可生成網址。
6. 任何增刪條件、虛構資格或金額、未知引用、URL、案件更新、非 JSON、截斷及拒答回應均拒絕，不把它們包裝成成功結果。

執行時只有 HTTP 成功且全部驗證通過，才回 `provider: openai_compatible`。離線測試會檢查同一回傳形狀，但 fixture 產生的回覆不構成真實模型結果或真實服務驗證。

## 健康檢查與錯誤

`provider_status()` 不會送出任何外部請求，也不回傳金鑰、模型名稱或服務網址。

- 預設：`llm_provider: grounded_rules`、`llm_configured: false`、`llm_verified: false`。
- 已選外部但缺 key／model 或設定無效：`llm_configured: false`，對話回 503，不隱形回退。
- 外部設定齊全：`llm_configured: true`，仍為 `llm_verified: false`。此值只表示必要設定齊備，不證明憑證有效、模型可用或已完成正式驗收。
- 本版的 `llm_verified` 保持 false，不因離線 fixture、健康檢查或環境變數而變成已驗證。

| HTTP | code | 行為 |
|---|---|---|
| 503 | `LLM_NOT_CONFIGURED` | 外部 key／model 缺少 |
| 503 | `INVALID_LLM_CONFIG` | 網址、模型或逾時設定無效 |
| 503 | `LLM_TIMEOUT` | 單次及整體請求逾時 |
| 503 | `LLM_PROVIDER_ERROR` | 網路、HTTP 錯誤或重新導向 |
| 503 | `INVALID_LLM_RESPONSE` | 內容、格式、引用或更新提案未通過驗證 |

請求上限 20 秒，回應上限 64 KiB。供應商原始錯誤內容、請求 prompt、Authorization header 及原始模型回覆均不寫入專案紀錄或回傳使用者。`store: false` 是送出的請求參數，不能在未查核供應商條款前宣稱其資料保留政策已通過驗證。

## 離線測試與仍待完成的驗收

執行：

```powershell
.venv\Scripts\python.exe -m pytest backend\tests\test_ai.py -q --basetemp=.local/pytest/ai-unique
```

本輪結果：**101 項 AI 測試通過**，其中 65 項涵蓋本機 RAG／規則，36 項涵蓋 adapter 邊界與離線情境。外部傳輸測試使用 [HTTPX MockTransport](https://www.python-httpx.org/advanced/transports/#mock-transports)，驗證實際 HTTP client 所組合的方法、路徑、JSON、記憶體中的合成測試用 Authorization、逾時、大小限制及失敗處理；不連線至任何模型服務。

尚待取得明確授權並安全配置供應商、模型與憑證後，才能執行真實 request、核對實際模型能力／參數與引用、測試失敗恢復及前端串接，並另行保存不含敏感內容的驗證結果。完成前，Phase 2 的真實 LLM 驗收必須維持 BLOCKED。
