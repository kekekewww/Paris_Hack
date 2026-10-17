# 理賠文件準備助手

延續團隊原始 HTML 的法國巴黎人壽黑客松原型，提供「描述情況、逐步確認」與「直接選擇類別」兩條路徑，整理官方文件、預覽 PDF、初步檢查指定欄位，再產生送件前摘要。

這是文件準備工具。它不判定資格、不計算給付、不驗證簽名真偽，也不向保險公司提交理賠；展示僅使用 `demo/documents/` 的合成文件。

## 目前提供的服務

| 模式 | 對話 | 文件檢查 | 保存方式 |
| --- | --- | --- | --- |
| `?service=mock` | 固定展示邏輯，有模擬標示 | 完整／缺漏／模糊的指定情境 | 分頁 sessionStorage；不存原檔 |
| `?service=api` | 預設真實本機官方檢索／規則 `grounded_rules`；可選外部 client 尚待真 API 驗證 | PDF 文字擷取／本機 RapidOCR；品質不足先提示重傳 | SQLite 結構化結果；不持久保存原檔或抽取全文 |

`grounded_rules` **不是生成式 LLM**。外部 `openai_compatible` client 已實作並有離線 HTTP transport 測試，真實模型 API 驗證仍為 **BLOCKED**；目前先使用本機模式完成其餘流程。Health 的 `llm_configured` 只表示必要設定齊備，`llm_verified` 保持 `false`，不能把設定存在或離線測試當作真實連線成功。外部設定缺漏或請求失敗會明確報錯，不會以 Mock 冒充成功。API 分析會保留簽名等人工覆核事項，完整合成文件仍可能顯示「需要補充或人工確認」。

Phase 1 已通過，證據見 [前端驗收報告](docs/PHASE1_ACCEPTANCE.md)。Phase 2 整合驗證與後續交付仍以實際驗收紀錄為準；這份 README 不代表外部部署或所有階段已完成。

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

## 可選外部模型（稍後設定）

後端支援 `LLM_PROVIDER=openai_compatible`，`LLM_BASE_URL` 預設 `https://api.openai.com/v1`。`LLM_API_KEY` 與 `LLM_MODEL` 在範例保持空白；外部模式兩者必填，模型沒有預設值。這些變數只能注入後端，不可放入 `VITE_` 或前端程式。Docker Compose 只將它們交給應用執行環境，不作為前端建置參數或寫入映像。

設定與驗收邊界見 [LLM 整合說明](docs/LLM_INTEGRATION.md)。目前不執行真實模型請求；有授權且安全設定完成後，仍需另做真實請求與失敗恢復驗證，才能解除 LLM 驗收阻礙。預設 `grounded_rules` 不需要金鑰，可繼續其餘展示與測試。

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

健康檢查可使用 `Invoke-RestMethod http://127.0.0.1:8000/api/v1/health`。成功只表示 API 存活，請同時核對 `service_mode`、`llm_provider`、`llm_configured`、`llm_verified` 與 `ocr_provider`，並以實際合成文件完成上傳檢查；此版本的 `llm_verified=false` 不因設定齊備而改變。

已啟動的本機 API 也可執行 `.venv/Scripts/python.exe scripts/smoke_api.py --include-ocr`。腳本只接受 loopback 網址，以合成 PDF／PNG 真正呼叫 API、核對來源與隔離，最後刪除自己建立的案件；不呼叫外部付費模型。容器改用 `--base-url http://127.0.0.1:8001` 等實際本機埠。

展示前先等 health 成功，再執行上述合成文件 smoke。Health 不代表圖片模型已暖機；本機容器實測曾首次圖片請求超出 45 秒，安全回 `OCR_TIMEOUT`，模型載入後重試 39 項通過。保留此限制，先確認已保存狀態再重試，不將超時當成檢查通過。

## 容器與文件

Docker Compose 預設只將服務綁定到 `127.0.0.1:8000`，SQLite 使用具名 volume。建置／啟動與可選 HTTPS 步驟見 [部署說明](docs/DEPLOYMENT.md)；外部主機、DNS、帳號與部署授權仍須另行具備。

- [API 契約](docs/API_CONTRACT.md)：方法、欄位、來源及錯誤語意。
- [架構](docs/ARCHITECTURE.md)、[官方來源查核](docs/OFFICIAL_SOURCES.md)。
- [LLM 整合與真實驗證阻礙](docs/LLM_INTEGRATION.md)。
- [展示腳本](docs/DEMO.md)、[已知限制](docs/KNOWN_LIMITATIONS.md)。
- [實際整合驗收](docs/API_INTEGRATION_ACCEPTANCE.md)、[容器驗收](docs/CONTAINER_ACCEPTANCE.md)、[依賴掃描](docs/DEPENDENCY_AUDIT.md)、[獨立審查](docs/FINAL_REVIEW.md)。
- [最終驗收與待辦阻礙](docs/FINAL_ACCEPTANCE.md)。
- [專案規範](AGENTS.md)、[專案計畫](PROJECT_PLAN.md)、[任務](TASKS.md)、[狀態](STATUS.md)、[決策](DECISIONS.md)。

案件按建立時間保留最多 24 小時；更新不延長期限。仍可從介面「清除測試案件」立即刪除目前案件。對話與結構化結果也可能含敏感資訊，請勿放入真實個資或醫療文件。官方規範、文件版本與送件方式應再次核對 [官方理賠頁面](https://life.cardif.com.tw/zh/a314)。
