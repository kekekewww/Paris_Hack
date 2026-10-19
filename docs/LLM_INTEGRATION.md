# LLM Adapter 與實際驗證狀態

更新日期：2026-10-19（臺灣）。目前只授權 OpenRouter 的 `openrouter/free`；OpenAI 與 Google AI Studio／Gemini 仍暫緩。分類、追問及安全回答採本機規則，只有有依據的文件問答使用模型，並非每句助手回覆都由 LLM 產生。前輪 OpenRouter 的實際接通與零費用驗證仍成立，見 [接通驗收歷史](OPENROUTER_ACCEPTANCE.md)；本次追問問題的修復、驗收及發版狀態以 [助手追問修復紀錄](ASSISTANT_FOLLOWUP.md) 為準，修復已發布；本輪真模型重驗與原公開完整腳本因上游限流未過，當前整體gate為BLOCKED。

前輪 OpenRouter 接通驗收的相關後端測試 **103 項**、完整後端 **293 項**通過。本機真模型 UI 首輪2項通過、平板1項因限流失敗（整輪53.6秒），平板獨立重驗1項通過（13.7秒），沒有合併宣稱單次3/3。新版 Docker 真 OCR smoke 56項、重啟保存及真模型瀏覽器1項（18.2秒）通過；公開 HTTP 23項及真模型瀏覽器1項（27.8秒）亦通過。這些離線測試與真實請求分別記錄，不以 fixture、設定存在或本機規則代替外部驗證。先前 [無金鑰驗收](ACCEPTANCE_NO_KEYS_20261019.md) 的後端 190 項／AI 113 項，以及更早的 AI 101 項，保留為歷史證據；其中「尚未授權、未發送真實請求」只描述當時狀態，已由後續 OpenRouter 授權取代。

## 本次引導問題與修復範圍

原公開版重現「你好 → 我出車禍了 → 沒有住院」時，三句的 provider 都是 `grounded_rules`，並重複同一個 `care_setting` 追問。OpenRouter Adapter 會先跑本機 baseline；只要 `response_type` 不是 `answer` 就直接回傳，因此這三句從未呼叫模型。這是本機逐輪追問及狀態處理問題，不能描述成模型失憶或整個助手每句都有 AI。

本次以先寫失敗測試的方式修復逐輪追問、否定更正、Mock 一致性，以及已建立案件重新進入 intake 時的舊訊息混淆。每則助手回覆已依該則 provider／模擬狀態標示「規則引導／AI 回覆／模擬／來源未標示」；折疊服務說明已明示有依據文件問答使用模型，分類與安全回答採規則。既有 API Contract／schema、免費護欄、私有金鑰與雲端資料邊界不變，不新增 LLM 語意理解或其他資料外送。

本次額外公開住院文件問答觀察到 `503 / LLM_RATE_LIMITED`，不列為本次新的模型成功證據。後續測試結果與是否發版由 [助手追問修復紀錄](ASSISTANT_FOLLOWUP.md) 記錄，前輪103／293及公開成功結果只作歷史對照。

## 已實作的範圍

- 預設 `grounded_rules`：執行本機官方資料檢索與確定性規則，不使用 LLM，回覆 `provider: grounded_rules`、`is_simulated: false`。
- 可選 `openai_compatible`：使用既有後端 `httpx.AsyncClient` 呼叫 `/chat/completions`，不新增供應商 SDK。OpenRouter 使用此 Adapter 的免費專用設定；一般相容設定仍保留，但不代表 OpenAI／Gemini 已完成真實串接。
- 不支援的 provider、缺少必要設定及外部請求失敗都明確報錯，不隱形回退成本機規則、Mock 或其他模型。
- 分類、條件提案、文件要求、案件及文件狀態仍由確定性規則與 API 處理；模型沒有修改案件或送件工具。

JSON mode 只約束輸出格式，不能取代伺服器的證據、來源、用量與費用驗證。[OpenRouter Chat API](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion)

## 後端設定與免費費用界線

OpenRouter 金鑰保存在私有 `.local/secrets/.env.openrouter`，啟動時明確映射至 canonical `LLM_API_KEY`；應用不會掃描或自動載入其他 env 檔，也不沿用其他供應商金鑰。秘密值不出現在文件、前端、Git、Docker build args、映像或日誌。詳見 [供應商設定](PROVIDER_SETUP.md)。

| 變數 | 既有 OpenRouter 設定 | 邊界 |
| --- | --- | --- |
| `LLM_PROVIDER` | `openai_compatible` | 僅明確設定才使用外部 Adapter；預設範本仍為本機模式 |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter 僅接受這個 canonical 官方端點，不接受其他路徑、別名或覆寫 |
| `LLM_API_KEY` | 後端啟動環境安全注入 | 不提供範例值，不放入 `VITE_` 或前端程式 |
| `LLM_MODEL` | `openrouter/free` | 不接受其他請求模型、付費模型或 auto router |
| `LLM_TIMEOUT_SECONDS` | `35` | OpenRouter 整體請求上限可設定，但不得超過 40 秒 |

固定請求參數：

~~~json
{
  "model": "openrouter/free",
  "response_format": {"type": "json_object"},
  "stream": false,
  "max_completion_tokens": 1800,
  "reasoning": {"effort": "minimal"},
  "provider": {
    "require_parameters": true,
    "allow_fallbacks": false,
    "max_price": {
      "prompt": 0,
      "completion": 0,
      "request": 0,
      "image": 0
    }
  }
}
~~~

`max_price` 是價格硬篩選物件；四項零價格、固定免費 router 與不提供其他模型共同限制每次請求費用。`require_parameters=true` 要求供應商支援所需參數，`allow_fallbacks=false` 禁止供應商備援；請求不自動重試，也沒有付費或 Mock fallback。[官方路由與價格設定](https://openrouter.ai/docs/guides/routing/provider-selection)

前輪實際金鑰資訊 GET 查核顯示限制 US$0.10、當時 usage 為 0；當輪多次推論的實際 `usage.cost` 均為 0。這些是已觀察結果，不能保證免費供應商日後持續有容量。實測亦出現 429、503 與逾時；重大疾病額外 CLI 真模型探測兩輪因429未完成，保留為擴充覆蓋的外部限制，不宣稱三類模型探測全部通過。完整紀錄見 [OpenRouter 驗收](OPENROUTER_ACCEPTANCE.md)。

服務網址只能由後端部署設定決定，使用者問題、文件與檢索內容無法改變目的地。程式禁止重新導向並忽略 proxy 環境設定；本機 URL 驗證不等同正式網路出口或 DNS 政策驗收。

## OpenRouter 的證據與輸出邊界

1. 先執行本機官方規則。引導分類、追問、保障／金額／資格問題、安全拒答與無支持內容不呼叫模型；回覆清楚標為 `grounded_rules`。
2. 只有已受本機資料支持的文件準備回答進入外部 Adapter。雲端只收到公開官方證據的 `id`、`title`、`text`，不送使用者問題、病歷、原始上傳檔、案件物件、對話歷史或來源 URL。
3. OpenRouter 模型只能以 `{"evidence_ids":["id"]}` 選回本次 1 至 3 個不重複證據 ID；不得輸出其他鍵、自由文字、網址、來源或案件更新。
4. 伺服器依所選 ID 重建完整 canonical 段落與官方來源／頁碼／URL，保留條件及不確定性；模型不負責改寫官方內容，也不能自行省略部分段落。
5. 未知、重複、超量或不屬於本次檢索的 ID，以及非 JSON、截斷、拒答、工具呼叫或額外生成欄位，一律拒絕。
6. 對外聊天 API 保留既有回傳形狀；實際模型與 token／cost 留在後端去敏感驗證紀錄，不附加到案件回覆。

一般非 OpenRouter 的相容設定保留原有完整段落比對及引用驗證，不等同 OpenRouter 的 ID-only wire schema。兩者都必須通過最終 `validate_assistant_response`，才能回 `provider: openai_compatible`、`is_simulated: false`。

## 真實模型、用量與健康狀態

OpenRouter 回應必須提供具體實際 `model`，不能只有 `openrouter/free` 等 router 別名。`usage.prompt_tokens`、`completion_tokens`、`total_tokens` 必須為有效正整數、總數相符，completion 不得超過 1800；`usage.cost` 必須是有限數值且恰為 0。缺失、錯型或非零費用不當作成功。

OpenRouter 現行 API 自動回傳 usage，不需要已棄用的 `usage.include`。實際供應模型可能隨免費容量改變，不能以請求的 router 名稱冒充固定模型。[官方 Usage Accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)、[Free Models Router](https://openrouter.ai/docs/cookbook/get-started/free-models-router-playground)

`provider_status()` 不送出外部請求，也不公開金鑰、模型名稱或服務網址：

- 預設本機模式：`llm_configured=false`、`llm_verified=false`。
- 外部模式缺少 key／model 或設定不合法：`llm_configured=false`，對話明確報錯。
- 設定齊全但此程序尚無成功真請求：`llm_configured=true`、`llm_verified=false`。
- 只有預設真實 transport 的 HTTP、具體模型、零費用、證據及最終回覆驗證全部通過，才記錄本程序同一配置的 `llm_verified=true`；MockTransport、離線 fixture 與本機規則回覆不能建立這項紀錄。
- 程序重啟、停用外部模式或觀察到配置變更會使舊驗證失效。`llm_verified` 是過往成功證據，不是即時 readiness；之後仍可能限流、故障或逾時。

## 錯誤、隱私與剩餘驗收

| HTTP | code | 行為 |
| --- | --- | --- |
| 503 | `LLM_NOT_CONFIGURED` | 外部 key／model 缺少 |
| 503 | `INVALID_LLM_CONFIG` | 網址、模型或逾時設定無效 |
| 503 | `LLM_TIMEOUT` | 單次及整體請求逾時 |
| 503 | `LLM_RATE_LIMITED` | 免費供應商回 429；顯示稍後重試，不自動重試 |
| 503 | `LLM_PROVIDER_ERROR` | 網路、其他 HTTP 錯誤或重新導向 |
| 503 | `INVALID_LLM_RESPONSE` | 模型、用量、費用、ID 或回覆驗證未通過 |

OpenRouter 內部預設 35 秒且最多 40 秒，低於後端對話路由 45 秒；前端對話逾時 50 秒。回應上限仍為 64 KiB。供應商原始錯誤 body、請求 prompt、Authorization 與原始模型回覆不寫入專案紀錄或回傳使用者。`store:false` 等請求參數不代表供應商資料保留政策已通過查核；目前的隱私界線是僅外送公開官方證據。

離線測試涵蓋固定端點與免費參數、ID-only 選取、實際模型／用量／費用、逾時、限流、不重試、不 fallback、配置隔離及 health 紀錄；使用 [HTTPX MockTransport](https://www.python-httpx.org/advanced/transports/#mock-transports) 的結果不列作真實 API 成功。前輪真實請求、前端、容器與公開版本的接通驗收見 [OpenRouter 驗收紀錄](OPENROUTER_ACCEPTANCE.md)，不能代替本次追問修復驗收。本次最後狀態以 [助手追問修復紀錄](ASSISTANT_FOLLOWUP.md) 為準；固定部署、商業級保險服務及額外模型覆蓋仍不在此範圍。
