# 模型供應商設定狀態

> 本輪（2026-10-20）已獲授權加入真實 OpenRouter 語意對話，必要的當前訊息與有限歷史會送交模型；原始上傳檔與 OCR 資料不送。語意4096版本已部署，最終公開live首輪真AI通過、第二輪限流，完整流程gate仍BLOCKED。本輪實作、真實請求、公開檢查及同程序verified的最終狀態以 [語意對話紀錄](SEMANTIC_CONVERSATION.md) 為準，不能沿用舊程序結果。

前輪連續追問修復已發布（2026-10-19），後端347／前端56、Mock87／API27、容器追問12／公開6通過；該輪真模型回503限流，原公開完整腳本在模型verified斷言失敗，沒有以規則成功代替模型成功。[歷史追問修復報告](ASSISTANT_FOLLOWUP.md)

更新日期：2026-10-20（臺灣）。使用者已明確授權安全保存提供的 OpenRouter 金鑰與必要對話文字外送，並且只允許 `openrouter/free`。這項新授權取代先前「暫不建立金鑰」對 OpenRouter 的限制；OpenAI 與 Google AI Studio／Gemini 仍暫緩，沒有因此啟用。

## 目前設定與驗證

| 服務 | 後端設定 | 目前狀態 |
| --- | --- | --- |
| OpenAI API | `OPENAI_API_KEY` 預留欄位 | 仍暫緩；本輪未建立、使用或驗證 OpenAI 金鑰 |
| Google AI Studio／Gemini API | `GEMINI_API_KEY` 預留欄位 | 仍暫緩；沒有 Gemini 原生 Adapter，本輪未呼叫 Gemini |
| OpenRouter | 透過既有 `openai_compatible` Adapter，固定官方端點與 `openrouter/free` | 既有文件問答曾真實接通；調整前程序的前三輪引導與獨立探測成功；三次完整live及新4096工作區探測仍失敗，gate BLOCKED |

OpenRouter 金鑰保存在後端私有檔 `.local/secrets/.env.openrouter`，不在此文件顯示內容。啟動時明確映射至 Adapter 使用的 canonical `LLM_API_KEY`，不依賴自動尋找或沿用其他供應商的金鑰。後端不會自行載入任意 env 檔；前端及建置產物不得讀取秘密檔。

語意對話不新增環境開關；明確選用以下 OpenRouter 設定後，後端會分流語意對話與既有官方證據問答。

~~~dotenv
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openrouter/free
LLM_TIMEOUT_SECONDS=300
# LLM_API_KEY 僅在後端啟動環境安全注入，此處不提供值。
~~~

OpenRouter 設定拒絕其他端點、其他請求模型及超過300秒的整體逾時；預設也是300秒。後端對話310秒、前端總等待330秒，背景工作以短請求查詢結果。[長等待說明](LLM_WAIT.md)。請求固定 `provider.max_price` 的 `prompt`、`completion`、`request`、`image` 四項為 `0`，並設定 `require_parameters=true`、`allow_fallbacks=false`、`reasoning.effort=minimal`。`max_completion_tokens` 依分流為語意4096、官方證據1800，一般相容profile仍為1800；metadata按當次cap驗證，仍須 `finish_reason=stop`與cost0。不自動重試、不改用付費模型，也不以 Mock 或本機規則回覆掩蓋外部失敗。[費用與參數邊界](LLM_INTEGRATION.md)

前輪金鑰資訊 GET 查核顯示限制為 US$0.10、當時 usage 為0；這不是變更帳號或方案，也不等同無限制免費服務。當輪多次推論的實際 `usage.cost` 為0，但免費供應商也曾回429、503或逾時。前輪實際模型、用量與錯誤見 [OpenRouter 歷史驗收](OPENROUTER_ACCEPTANCE.md)，本輪語意模式驗收以 [語意對話紀錄](SEMANTIC_CONVERSATION.md) 為準；不能保證免費模型持續可用。

`llm_configured` 只表示設定齊備。`llm_verified=true` 只表示同一程序、同一配置曾有通過驗證的真實請求；程序重啟或配置變更會使紀錄失效，health 不探測模型，也不保證即時 readiness。

## 安全與資料邊界

- 金鑰只供後端使用，不放進前端、`VITE_` 變數、Git、Docker build args、映像或日誌；只回報保存及驗證狀態，不回報值。
- `.gitignore` 排除 `.env`、`.env.local` 與 `.local/`；Docker context 採執行必要檔案白名單。根目錄 [.env.example](../.env.example) 仍是空白金鑰範本。
- 本輪已授權語意模式傳送必要的當前訊息與最多8則歷史，合計最多9則／6000字；當前訊息為1–4000字，遮罩後完整保留。歷史user每則最多1000字、assistant最多600字，超長只留完整句段，無安全句段則排除。
- 保留最後安全引導回覆，以及「有／沒有／是／不是」短答所需的前一個結構化追問；若必要問句未能完整保留遮罩後內容（包含被上限縮減），短答一起排除。文件、answer、uncertain及不明配對不納入；歷史只取role／content，再加本次turn索引；另外只傳已確認類型與cause／surgery最小狀態，不附加完整案件、原始上傳檔、OCR／抽取全文或分析欄位。
- 明顯識別資料先做盡力遮罩，不是全面去識別；使用者自行輸入的文字仍可能含未匹配的個人與就醫資訊，展示只用合成資料。官方證據只由伺服器挑選。
- 模型內部只回facts／question／message，六項事實須有允許user turn的逐字引文；伺服器以有限語境、領域合理性與矛盾檢查驗證，並非完整語意證明。模型不能直接決定官方文件要求或修改案件；新案件確認後才透過既有API寫入，已建案語意回覆不帶更新提案。支援文件問答仍由伺服器依所選官方證據重建全文與引用。
- 免費路由會選擇實際供應模型，模型與容量可能改變；不得把 router 名稱當成固定模型承諾。[官方 Free Models Router](https://openrouter.ai/docs/cookbook/get-started/free-models-router-playground)

OpenAI 未來的安全建立流程仍須使用 OpenAI Developers 的安全選擇及本機目的地確認；本輪不啟動。Gemini 僅保留單一 `GEMINI_API_KEY` 欄位，避免別名優先順序混用；後續若獲授權再做獨立串接與驗證。[Google 官方金鑰文件](https://ai.google.dev/gemini-api/docs/api-key)

## 本輪與歷史驗收

預算調整前的後端471項／1警告（91.65秒）、前端58／Mock87結果保留。調整後AI離線400項、完整後端477項（1項既有Starlette警告、108.76秒）及新映像7c6afbc9…建置通過，不能代替真實流程。舊程序前三輪公開引導及獨立NVIDIA改述cost0／問候診斷成功；三次完整live依序第四輪限流、第一輪INVALID（未復現）、第一輪限流。另一次4096工作區真探測stop／cost0仍因事實來源驗證被拒。語意4096版本已部署，新程序最終公開live首輪真AI通過、第二輪限流，整次1項失敗（39.5秒），gate仍BLOCKED。公開HTTP、同程序verified、容器與最終gate以 [語意對話紀錄](SEMANTIC_CONVERSATION.md) 為準。

[無金鑰完整驗收](ACCEPTANCE_NO_KEYS_20261019.md) 保留為先前版本的實測歷史，當時沒有送出真實模型請求，不因本次新授權而改寫。前輪真實接通證據保留；提高預算前程序的前三輪語意引導已通過，但三次完整live均失敗；該程序verified來自真intake，原公開HTTP23項未改斷言且通過。新程序須以自身真實請求及公開檢查另行驗證，不能沿用舊程序；其最終結果見本輪報告。OpenAI／Gemini 仍未驗證，也不能由相容 Adapter 的存在推論三家都能使用。

前輪 OpenRouter 接通驗收的相關後端測試103項、完整後端293項通過。本機真模型 UI 首輪2項通過、平板1項因429失敗，平板獨立重驗1項通過，不合併宣稱單次3/3。新版 Docker 真 OCR smoke 56項、重啟保存及真模型瀏覽器1項通過；公開 HTTP 23項與真模型瀏覽器1項亦通過。這些是前輪 Phase 2／3 原型範圍的歷史驗收，結果見 [OpenRouter 驗收紀錄](OPENROUTER_ACCEPTANCE.md)。

重大疾病額外 CLI 真模型探測兩輪遇429，保留為擴充覆蓋的外部限制，不宣稱三類模型探測全部通過。OpenAI／Gemini 是可選後續項目，不阻擋本次 MVP；固定部署及商業級服務驗收不在此範圍。
