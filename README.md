# 理賠文件準備助手

> 最新依使用者授權改用DeepSeek V4.1 Flash 1017及新key，固定官方供應商，300秒等待與文件規則保持。[目前設定與真實驗證](docs/DEEPSEEK_SETUP.md)／[續作狀態](STATUS.md)。舊free的成功、限流與INVALID均保留為歷史證據，不當作新程序驗收。

延續團隊原始 HTML 的法國巴黎人壽黑客松原型，提供「描述情況、逐步確認」與「直接選擇類別」兩條路徑，整理官方文件、預覽 PDF、初步檢查指定欄位，再產生送件前摘要。

這是文件準備工具。它不判定資格、不計算給付、不驗證簽名真偽，也不向保險公司提交理賠；展示僅使用 `demo/documents/` 的合成文件。

## 目前提供的服務

| 模式 | 對話 | 文件檢查 | 保存方式 |
| --- | --- | --- | --- |
| `?service=mock` | 固定展示邏輯，有模擬標示 | 完整／缺漏／模糊的指定情境 | 分頁 sessionStorage；不存原檔 |
| `?service=api` | 展示服務已設定指定 DeepSeek；提供真語意對話與官方證據問答，語意4096／證據1800。未配置金鑰的本機預設grounded_rules | PDF文字擷取／本機RapidOCR；品質不足先提示重傳 | SQLite結構化結果；不持久保存原檔或抽取全文 |

`grounded_rules` **不是生成式LLM**。明確設定 `openai_compatible`、官方OpenRouter端點及指定DeepSeek模型後，模型處理引導與一般補充的語意；文件問答由模型選證據、伺服器重建完整官方段落。安全、資格與金額等限制仍由規則處理，每則訊息依實際來源標示。原free設定可選且保留零費用護欄。

語意對話會送出必要的當前訊息與最多8則歷史，以及已確認類型與cause／surgery兩項最小案件狀態。對話合計最多6000字，當前訊息最多4000字；歷史只保留完整句段與短答必要問句，排除文件問答／分析上下文。明顯識別資料先做盡力遮罩，未匹配資訊仍可能外送，並非全面去識別。不自動附加原始上傳檔、OCR／抽取全文或分析欄位。使用者自行輸入的事故、就醫或個人文字可能包含敏感資訊，展示仍只用合成資料。

文件問答另只附本次必要遮罩query與官方證據，不附對話歷史、完整案件或檔案；模型依問題選取完整官方段落，伺服器驗證並重建引用。

模型提出語意與類型／條件提案，官方文件要求由伺服器規則決定；新案件由使用者確認並建立清單後才寫入，已建立案件只提醒確認，不由語意回覆直接覆寫條件。外部失敗明確報錯，不自動重試、不換模型，也不回退Mock／本機假成功。OpenAI／Gemini仍暫緩。

目前展示：[理賠準備助手](https://tulsa-ppc-message-builders.trycloudflare.com/?service=api)。模型最多300秒，後端310秒、網頁整體330秒，以背景工作查詢結果；一般請求15秒。正式dist與Docker均以API為預設，Mock仍可透過明確query使用。

## 歷史驗收

以下為先前版本的成功與失敗，當前結果以[DeepSeek報告](docs/DEEPSEEK_SETUP.md)及[STATUS](STATUS.md)為準。

先前回報「你好 → 我出車禍了 → 沒有住院」時，原公開版三句都是 `grounded_rules` 並重複追問 `care_setting`，沒有呼叫模型；當時 Adapter 會先跑規則並在非文件回答時早退。這段重現與接通證據保留為歷史，本輪改為已授權的語意對話分工，不將舊成功視為新模式成功。

前輪逐輪追問、否定更正、Mock 一致性與舊訊息修復的驗收為後端347／前端56、Mock87／API27及容器追問12／公開6；該輪真模型重驗仍限流，原公開完整腳本未過。[歷史修復紀錄](docs/ASSISTANT_FOLLOWUP.md) 保留成功與失敗，本輪語意對話狀態另見 [本輪報告](docs/SEMANTIC_CONVERSATION.md)。每則回覆仍依自身來源標示「規則引導／AI回覆／模擬／來源未標示」。

提高語意預算前的公開程序曾完成「你好 → 我出車禍了 → 沒有住院」三輪200、真provider、非模擬與正確AI標示，並由該次intake建立verified；另有NVIDIA獨立改述cost0與問候診斷成功。三次完整live依序在第四輪限流、第一輪 `INVALID_LLM_RESPONSE`（未復現）、第一輪限流而失敗，仍不合併成完整通過。該程序的公開HTTP23項也原封不動通過，但新程序重啟後不能沿用其verified或公開檢查結果。

預算修正後AI離線400項、完整後端477項通過（1項既有Starlette警告、108.76秒），新映像7c6afbc9…建置成功並部署語意4096；前端58／Mock87及預算修正前471項結果保留。新程序公開live首輪200、真provider、非模擬及AI標示通過，第二輪限流，整次1項失敗（39.5秒），完整gate仍BLOCKED。另一次4096工作區真探測雖stop／cost0，仍因事實來源驗證被拒，沒有放寬防護。公開HTTP、verified、容器與最終gate以 [語意對話紀錄](docs/SEMANTIC_CONVERSATION.md) 為準。

Health 的 `llm_configured` 只表示設定齊備；`llm_verified=true` 只表示同一程序、同一配置曾有通過驗證的真實請求，重啟或配置變更即失效。它不保證即時可用，也不表示目前這則回覆來自模型。前輪公開住院文件問答曾回 `503 / LLM_RATE_LIMITED`，不列為新的模型成功證據；前輪實測見 [OpenRouter 驗收紀錄](docs/OPENROUTER_ACCEPTANCE.md)。OpenAI／Gemini 是可選後續項目，不阻擋 MVP。

Phase 1 證據見 [前端驗收報告](docs/PHASE1_ACCEPTANCE.md)；前輪 Phase 2／3 原型範圍的整合與交付驗收見 [OpenRouter 驗收紀錄](docs/OPENROUTER_ACCEPTANCE.md)。固定網域、常駐部署與商業級保險服務驗收不在本次 MVP 範圍。

前輪 2026-10-19 的 [Quick Tunnel 臨時 HTTPS 展示](https://retirement-trim-reported-jesus.trycloudflare.com/?service=api) 曾通過公開 HTTP 23 項及真實模型瀏覽器流程1/1（27.8秒）。這些是 OpenRouter 接通版本的歷史證據，不能代替本輪語意完整流程驗收。電腦、本機應用與隧道必須保持執行；該輪結果見 [OpenRouter 驗收](docs/OPENROUTER_ACCEPTANCE.md)，本輪修復與發版狀態見 [語意對話紀錄](docs/SEMANTIC_CONVERSATION.md)。

前輪[介面簡化](docs/UI_SIMPLIFICATION.md)已通過三尺寸視覺、33項單元、Mock 75項、PDF 2項、真API 27項與故障恢復1項。工作區同情境可見文字減少45.7%，只突出下一份文件；來源、案件管理與助手採漸進揭露。當時外部 LLM 依使用者決定稍後設定。

前輪[無金鑰完整重驗收](docs/ACCEPTANCE_NO_KEYS_20261019.md)亦通過：後端190、前端33、Mock75、真API27、PDF2、公開及容器流程、來源11項與依賴掃描均有實測。這份歷史報告當時依「暫不建立金鑰」執行；後續授權只解除 OpenRouter 限制，OpenAI／Gemini 仍暫緩。[目前供應商狀態](docs/PROVIDER_SETUP.md)

前輪[引導確認修正](docs/GUIDED_CHOICE.md)已發布：送出描述後先選一種類型，再按「建立文件清單」；單一建議也不預選，點選／改選不寫入案件。單元36、三尺寸Mock87、真API27、PDF2／G1、公開與新版Docker皆已實際回歸。

前輪 OpenRouter 接通驗收的相關後端測試103項與完整後端293項通過。本機真模型 UI 首輪2項通過、平板1項因限流失敗，平板獨立重驗1項通過，沒有合併宣稱單次3/3。新版 Docker 真 OCR smoke 56項、重啟保存與真模型瀏覽器1項亦通過；多次推論 cost 為0，免費容量仍有限。重大疾病額外 CLI 探測兩輪遇429，保留為擴充覆蓋限制，不宣稱三類模型探測全部通過。完整結果見 [OpenRouter 驗收紀錄](docs/OPENROUTER_ACCEPTANCE.md)。

## 本機啟動（PowerShell）

需要 Node.js 22、Python 3.12，以及可用的桌面瀏覽器。先在專案根目錄執行：

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm ci
if (!(Test-Path .venv)) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -c backend/constraints.txt -r backend/requirements-dev.txt
npm run build
```

如 `.env` 或 `.venv` 已存在，保留既有內容並核對範例，不需覆寫或重建。Vite 與 Docker Compose 會讀取根目錄 `.env`；Python 後端不會自動載入它。啟動後端時設定實際 shell 環境：

```powershell
$env:LLM_PROVIDER = 'grounded_rules'
$env:ALLOWED_ORIGINS = 'http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5174,http://localhost:5174'
$env:SESSION_COOKIE_SECURE = 'false'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

開啟 [真實本機 API 模式](http://127.0.0.1:8000/?service=api) 或 [Mock 模式](http://127.0.0.1:8000/?service=mock)。後端同時供應建置後的前端；不用另開 Vite。使用同一個主機名稱，避免把 `localhost` 與 `127.0.0.1` 的 cookie／分頁進度混在一起。

後端必須維持 **1 個 worker、1 個應用副本**。目前案件鎖與速率限制只在單一程序內生效；多 worker 可能發生並行更新遺失。請勿增加 `--workers` 或水平擴充，正式擴充前須加入資料庫版本比對（CAS）與跨程序協調。Docker 目前預設單 worker。

若要修改前端，保持後端啟動，在第二個終端機執行 `npm run dev`，再開啟 [Vite 開發頁面](http://127.0.0.1:5174/?service=api)。Vite 將 `/api` 代理到 8000。`npm run build` 會準備本機 PDF.js 字型、CMap、WASM、ICC 與 worker，展示不依賴外部 PDF CDN。

macOS／Linux 對應命令為 `python3.12 -m venv .venv`、`.venv/bin/python -m pip ...` 與 `.venv/bin/python -m uvicorn ...`；使用 `export` 設定相同環境變數。

## OpenRouter 模型

OpenRouter目前依使用者新授權使用 `LLM_MODEL=deepseek/deepseek-v4.1-flash-1017`，以 `LLM_PROVIDER=openai_compatible` 與固定 `LLM_BASE_URL=https://openrouter.ai/api/v1` 啟用。付費profile只允許這個requested model及DeepSeek官方供應商，不自動改用其他模型；原 `openrouter/free` profile仍保留且要求零費用。新key只保存在後端私有 `.local/secrets/.env.openrouter`，啟動時明確映射至 canonical `LLM_API_KEY`；不在前端、Git、Docker build args或映像提供秘密值。[新設定與真實驗證](docs/DEEPSEEK_SETUP.md)

`LLM_TIMEOUT_SECONDS=300`，OpenRouter預設及最高等待五分鐘；後端310秒、前端330秒。前端以背景工作與短請求查詢結果，避免展示隧道中斷長HTTP請求。[長等待說明](docs/LLM_WAIT.md)

DeepSeek請求設定 `provider.only=["deepseek"]`、`require_parameters=true`、`allow_fallbacks=false`與 `reasoning.effort=low`。單價上限為每百萬token輸入US$0.30／輸出US$1.20，固定request／image費率上限0；回覆cost必須為有限數字且在0–US$0.05間，這是事後驗證而非退款或供應商硬停。新key的總額上限US$2及2026-11-19到期已由官方GET確認，未修改帳號。`max_completion_tokens` 維持語意4096／官方證據1800，來源、事實、正常完成與用量檢查不變。預設 `grounded_rules` 不需要金鑰；OpenAI／Gemini 尚未啟用或驗證。[LLM整合說明](docs/LLM_INTEGRATION.md)

## 檢查與測試

```powershell
npm test
.\.venv\Scripts\python.exe -m pytest backend/tests -q
npm run build
npx playwright install chromium
npm run test:e2e
npm run test:pdf
node node_modules/@playwright/test/cli.js test -c playwright.demo.config.js
```

瀏覽器安裝只需在缺少對應 Chromium 時執行；也可設定 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 指向既有相容執行檔。

API 測試會對真正的本機 HTTP 服務發請求並建立／清除合成案件，不代表已呼叫外部 LLM。先停止一般展示後端，在獨立終端機使用測試資料庫及較高測試配額，讓 Playwright 啟動後端：

```powershell
$env:CASE_DB_PATH = '.local/api-e2e.sqlite3'
$env:RATE_LIMIT_REQUESTS = '1000'
npm run test:api
```

測試後關閉此終端機，避免測試環境變數影響日常展示。若要使用其他獨立服務，可用 `CLAIM_API_BASE_URL`、`CLAIM_API_SERVER_COMMAND`，並同步設定該服務正確的 origin；已有 8000 服務時 Playwright 會重用，不能假定測試設定已更改它的資料庫或配額。

健康檢查可使用 `Invoke-RestMethod http://127.0.0.1:8000/api/v1/health`。成功只表示 API 存活，請同時核對 `service_mode`、`llm_provider`、`llm_configured`、`llm_verified` 與 `ocr_provider`，並以實際合成文件完成上傳檢查。`llm_verified` 只記錄同程序、同配置的過往真實成功；health不發送推論請求，也不保證供應商此刻可用。

已啟動的本機API也可執行 `.venv/Scripts/python.exe scripts/smoke_api.py --include-ocr`。腳本只接受loopback網址，以合成PDF／PNG真正呼叫API、核對來源與隔離，最後刪除自己建立的案件。它使用既有後端設定；若已啟用OpenRouter，對話會使用該配置並可能產生費用或消耗免費配額，不自行切換模型。容器改用 `--base-url http://127.0.0.1:8001` 等實際本機埠。

展示前先等 health 成功，再執行上述合成文件 smoke。Health 不代表圖片模型已暖機；本機容器實測曾首次圖片請求超出 45 秒，安全回 `OCR_TIMEOUT`，模型載入後重試 39 項通過。保留此限制，先確認已保存狀態再重試，不將超時當成檢查通過。

前輪 OpenRouter 整合的完整測試也曾出現 OCR `bad allocation`；該單項重驗與當輪最終293項通過，但尚無根因已修復的證據，限制仍見 [已知限制](docs/KNOWN_LIMITATIONS.md)。

## 容器與文件

Docker Compose 預設只將服務綁定到 `127.0.0.1:8000`，SQLite 使用具名 volume。建置／啟動與可選 Caddy HTTPS 步驟見 [部署說明](docs/DEPLOYMENT.md)；固定主機與自有網域的部署仍需相應主機、DNS 及授權。Quick Tunnel 臨時展示不需要自有網域。

- [API 契約](docs/API_CONTRACT.md)：方法、欄位、來源及錯誤語意。
- [架構](docs/ARCHITECTURE.md)、[官方來源查核](docs/OFFICIAL_SOURCES.md)。
- [本輪語意對話](docs/SEMANTIC_CONVERSATION.md)、[LLM 整合與驗證狀態](docs/LLM_INTEGRATION.md)、[OpenRouter 前輪驗收](docs/OPENROUTER_ACCEPTANCE.md)、[歷史助手追問修復](docs/ASSISTANT_FOLLOWUP.md)。
- [展示腳本](docs/DEMO.md)、[已知限制](docs/KNOWN_LIMITATIONS.md)。
- [實際整合驗收](docs/API_INTEGRATION_ACCEPTANCE.md)、[容器驗收](docs/CONTAINER_ACCEPTANCE.md)、[依賴掃描](docs/DEPENDENCY_AUDIT.md)、[獨立審查](docs/FINAL_REVIEW.md)。
- [最終驗收與待辦阻礙](docs/FINAL_ACCEPTANCE.md)。
- [專案規範](AGENTS.md)、[專案計畫](PROJECT_PLAN.md)、[任務](TASKS.md)、[狀態](STATUS.md)、[決策](DECISIONS.md)。

案件按建立時間保留最多 24 小時；更新不延長期限。仍可從介面「清除測試案件」立即刪除目前案件。對話與結構化結果也可能含敏感資訊，請勿放入真實個資或醫療文件。官方規範、文件版本與送件方式應再次核對 [官方理賠頁面](https://life.cardif.com.tw/zh/a314)。
