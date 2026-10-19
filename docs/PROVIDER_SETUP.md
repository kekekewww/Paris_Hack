# 模型供應商設定狀態

更新日期：2026-10-19（臺灣）。使用者已明確授權安全保存提供的 OpenRouter 金鑰，並且只允許 `openrouter/free`。這項新授權取代先前「暫不建立金鑰」對 OpenRouter 的限制；OpenAI 與 Google AI Studio／Gemini 仍暫緩，沒有因此啟用。

## 目前設定與驗證

| 服務 | 後端設定 | 目前狀態 |
| --- | --- | --- |
| OpenAI API | `OPENAI_API_KEY` 預留欄位 | 仍暫緩；本輪未建立、使用或驗證 OpenAI 金鑰 |
| Google AI Studio／Gemini API | `GEMINI_API_KEY` 預留欄位 | 仍暫緩；沒有 Gemini 原生 Adapter，本輪未呼叫 Gemini |
| OpenRouter | 透過既有 `openai_compatible` Adapter，固定官方端點與 `openrouter/free` | 已執行真實請求並驗證零費用、模型與官方證據；本機、容器及公開版本已完成原型範圍驗收 |

OpenRouter 金鑰保存在後端私有檔 `.local/secrets/.env.openrouter`，不在此文件顯示內容。啟動時明確映射至 Adapter 使用的 canonical `LLM_API_KEY`，不依賴自動尋找或沿用其他供應商的金鑰。後端不會自行載入任意 env 檔；前端及建置產物不得讀取秘密檔。

本次後端設定為：

~~~dotenv
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openrouter/free
LLM_TIMEOUT_SECONDS=35
# LLM_API_KEY 僅在後端啟動環境安全注入，此處不提供值。
~~~

OpenRouter 設定拒絕其他端點、其他請求模型及超過 40 秒的整體逾時。請求固定 `provider.max_price` 的 `prompt`、`completion`、`request`、`image` 四項為 `0`，並設定 `require_parameters=true`、`allow_fallbacks=false`、`reasoning.effort=minimal`、`max_completion_tokens=1800`。不自動重試、不改用付費模型，也不以 Mock 或本機規則回覆掩蓋外部失敗。[費用與參數邊界](LLM_INTEGRATION.md)

金鑰資訊的實際 GET 查核顯示限制為 US$0.10、當時 usage 為 0；這不是變更帳號或方案，也不等同無限制免費服務。本次多次推論的實際 `usage.cost` 為 0，但免費供應商也曾回 429、503 或逾時。實際模型、用量、錯誤與後續驗收以 [OpenRouter 驗收紀錄](OPENROUTER_ACCEPTANCE.md) 為準；不能保證免費模型持續可用。

`llm_configured` 只表示設定齊備。`llm_verified=true` 只表示同一程序、同一配置曾有通過驗證的真實請求；程序重啟或配置變更會使紀錄失效，health 不探測模型，也不保證即時 readiness。

## 安全與資料邊界

- 金鑰只供後端使用，不放進前端、`VITE_` 變數、Git、Docker build args、映像或日誌；只回報保存及驗證狀態，不回報值。
- `.gitignore` 排除 `.env`、`.env.local` 與 `.local/`；Docker context 採執行必要檔案白名單。根目錄 [.env.example](../.env.example) 仍是空白金鑰範本。
- 雲端只收到公開官方證據的 ID、標題與片段；不送使用者問題、病歷、案件物件、對話歷史或原始上傳檔。模型只能選回本次證據 ID，完整段落與官方引用由伺服器重建。
- 免費路由會選擇實際供應模型，模型與容量可能改變；不得把 router 名稱當成固定模型承諾。[官方 Free Models Router](https://openrouter.ai/docs/cookbook/get-started/free-models-router-playground)

OpenAI 未來的安全建立流程仍須使用 OpenAI Developers 的安全選擇及本機目的地確認；本輪不啟動。Gemini 僅保留單一 `GEMINI_API_KEY` 欄位，避免別名優先順序混用；後續若獲授權再做獨立串接與驗證。[Google 官方金鑰文件](https://ai.google.dev/gemini-api/docs/api-key)

## 歷史與剩餘驗收

[無金鑰完整驗收](ACCEPTANCE_NO_KEYS_20261019.md) 保留為先前版本的實測歷史，當時沒有送出真實模型請求，不因本次新授權而改寫。現在已新增 OpenRouter 真實請求證據；OpenAI／Gemini 仍未驗證，也不能由相容 Adapter 的存在推論三家都能使用。

本次 OpenRouter 相關後端測試103項、完整後端293項通過。本機真模型 UI 首輪2項通過、平板1項因429失敗，平板獨立重驗1項通過，不合併宣稱單次3/3。新版 Docker 真 OCR smoke 56項、重啟保存及真模型瀏覽器1項通過；公開 HTTP 23項與真模型瀏覽器1項亦通過。本輪已完成 Phase 2／3 原型範圍的整體驗收，結果見 [OpenRouter 驗收紀錄](OPENROUTER_ACCEPTANCE.md)。

重大疾病額外 CLI 真模型探測兩輪遇429，保留為擴充覆蓋的外部限制，不宣稱三類模型探測全部通過。OpenAI／Gemini 是可選後續項目，不阻擋本次 MVP；固定部署及商業級服務驗收不在此範圍。
