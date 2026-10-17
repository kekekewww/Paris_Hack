# 運行與部署準備

本文件提供本機容器與可選 HTTPS 的可重現步驟。設定檔存在、`docker compose config` 成功、映像建置成功、端到端驗收通過及外部部署成功是不同結果；必須按實際輸出記錄，不能互相替代。外部主機、網域／DNS、平台帳號與部署授權尚未由本文件取得。

2026-10-17 已依使用者明確要求另外建立 Cloudflare Quick Tunnel，完成臨時公開 HTTPS 的 HTTP 23 項及桌面瀏覽器 3 項實測。[Quick Tunnel 紀錄](QUICK_TUNNEL.md)包含網址、精確 origin、Secure cookie、獨立資料庫及存活限制；以下 Caddy 自有網域部署為另一種可選方式。

## 1. 本機容器

需要支援 Linux 容器的 Docker Engine 與 Compose v2。根目錄的 `Dockerfile` 以 Node.js 22 執行 `npm ci`／`npm run build`，再以 Python 3.12 slim 安裝鎖定的 runtime requirements。OCR 使用 CPU，需保留記憶體給 PyMuPDF、Pillow、ONNX Runtime 與 RapidOCR；第一次辨識可能比後續慢。

先複製 `.env.example` 成 `.env`；已有設定時請保留並核對。以下指令各自獨立執行：

```powershell
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

開啟 `http://127.0.0.1:8000/?service=api`，用 `demo/documents/` 的合成文件跑一次完整流程。`config` 不需要啟動容器，也不驗證 Python 套件可安裝、映像能運行、OCR 模型可載入或 HTTPS 可取得憑證；這些必須在後續實際驗收記錄。

預設只發佈 loopback 8000 埠。FastAPI 同時提供 `dist` 與 `/api/v1`，不需要在外部暴露 Vite。容器以 UID/GID `10001:10001` 執行應用，程式根目錄唯讀，僅 `/app/.local` 具名 volume 與有上限的 `/tmp` 可寫，移除額外 capabilities，停用 Uvicorn access log。

**僅支援單 worker、單應用副本。** Docker 預設 1 個 Uvicorn worker；不要增加 `--workers`、設定多程序 `WEB_CONCURRENCY` 或對 app 水平擴充。目前的 128 個案件 async lock 與速率限制都是程序內狀態，SQLite 的單次寫入交易不能避免不同程序先讀後寫造成更新遺失。擴充前須先完成資料庫版本比對（CAS）及跨程序一致性設計與驗證。

建置 context 採允許清單；映像只包含前端產物、`backend/app`、鎖定 runtime 依賴與官方 registry，不含 `.env`、`.venv`、原始設計備份、測試報告、目前資料庫或展示文件。PDF.js worker 與字型／CMap／WASM 等資源在建置時從鎖定的 npm 依賴產生，不透過 CDN 載入。

## 2. 設定對照

| 名稱 | 用途／預設 |
| --- | --- |
| `VITE_SERVICE_MODE` | 建置時的 UI 預設服務，Compose 預設 `api`；更改後須重新建置。網址 `?service=mock/api` 可明確覆寫。 |
| `CASE_DB_PATH` | 本機 Python 預設為專案 `.local/cases.sqlite3`；Compose 固定 `/app/.local/cases.sqlite3`，避免脫離 volume。 |
| `ALLOWED_ORIGINS` | 逗號分隔完整 origin，必須包含實際瀏覽器使用的 scheme、host、port；不使用萬用字元。 |
| `RATE_LIMIT_REQUESTS` | 每來源 IP、每分鐘 API 請求上限，預設 `120`；反向代理下有共用 IP 限制，見下文。 |
| `SESSION_COOKIE_SECURE` | 本機 HTTP 為 `false`；HTTPS 部署必須 `true`。 |
| `LLM_PROVIDER` | 預設 `grounded_rules` 執行真本機規則／檢索；可選 `openai_compatible`，client 已實作但真 API 驗收仍 BLOCKED。 |
| `LLM_BASE_URL` | 預設 `https://api.openai.com/v1`；外部 adapter 的受信後端 HTTPS 服務位置，不能由對話或文件指定。 |
| `LLM_API_KEY` | 範例為空；外部模式必填，只注入後端執行環境，不作為建置參數或送往前端。 |
| `LLM_MODEL` | 範例為空；外部模式必填，沒有預選模型。 |
| `DOMAIN` | 僅供 Caddy 的 HTTPS site address 使用，不是已註冊或已驗證的網域。 |

`.env` 由 Compose 及 Vite 讀取；本機 Python 不會自動載入。不要把 key 放入任何 `VITE_` 變數，或在日誌／`docker compose config` 的完整輸出中公開值；核對實際設定時可用 `config --quiet`。目前先保留本機規則模式與空白外部金鑰／模型，不需要為完成其餘工作切換 provider。

外部 client 的設定規則、資料傳送邊界與離線測試見 [LLM 整合說明](LLM_INTEGRATION.md)。即使 `llm_configured=true`，也只代表必填設定齊備；本版 `llm_verified=false`，真實模型請求與正式驗收仍 BLOCKED。離線 transport 測試、容器啟動與 health 成功都不能代替真實 provider 驗證。未配置、非預期回覆或請求失敗均回結構化錯誤，不回退 Mock。

## 3. 可選 HTTPS profile

只有在已獲外部部署授權、持有網域與主機，且 DNS 指向正確主機、80／443 可達時，才執行對外啟動。修改 `.env`：

```dotenv
DOMAIN=claims.example.com
ALLOWED_ORIGINS=https://claims.example.com
SESSION_COOKIE_SECURE=true
LLM_PROVIDER=grounded_rules
```

`claims.example.com` 是需替換的範例。接著核對設定並啟動：

```powershell
docker compose --profile https config --quiet
docker compose --profile https up --build -d
```

`Caddyfile` 使用 `DOMAIN` 代理至 `app:8000`，Caddy 的憑證與設定分別存於 `caddy_data`／`caddy_config` volume；預設沒有 access log。應用仍以非 root 執行；可選的官方 Caddy 容器為綁定 80／443 保留 `NET_BIND_SERVICE`，未授予其他 capabilities。

公開 HTTPS 後以實際網域檢查憑證、origin 防護、`Secure; HttpOnly; SameSite=strict` cookie、案件隔離、上傳與清除。`DOMAIN=localhost` 不代表可供外部使用的公開憑證；一般本機展示繼續使用預設 HTTP。

應用刻意不信任任意 `X-Forwarded-For`；Caddy 後方請求可能共用來源 IP，因此速率限制會合併計算。公開服務前須依實際受信代理拓撲調整，不能直接信任使用者提供的轉送標頭。這個原型也沒有正式登入、多租戶授權或完整營運監控。

## 4. 資料、關閉與故障排除

SQLite 僅保存短期案件、對話、檔案中繼資料與遮罩後的擷取結果，不保存上傳原檔或擷取全文；這些結構化資料仍須當作敏感資料保護。保留期限按建立時間固定 24 小時，更新不延長；啟動、資料操作與每 300 秒會清理。每個 cookie owner 上限 20 案，每案最多 100 回對話。

`docker compose down` 停止服務並保留具名 volume。避免將 `down -v` 當作例行關閉；它會刪除案件資料與 Caddy 憑證，需在明確授權清除時才執行。需要保留展示紀錄時可先下載介面的準備摘要，不應任意複製真實醫療資料庫。

| 現象 | 檢查方式 |
| --- | --- |
| Docker CLI 無法連線 Engine | 確認 Docker Desktop／Engine 已啟動並切到 Linux 容器；`config` 成功不代表 Engine 可用。 |
| 根頁面 503 `FRONTEND_UNAVAILABLE` | 本機先執行 `npm run build`；容器確認 build stage 成功並已複製 `dist`。 |
| API 403 `ORIGIN_NOT_ALLOWED` | 核對實際網址與 `ALLOWED_ORIGINS`，包括 5174 開發埠與 HTTPS。 |
| 案件建立後讀不到／404 | 使用同一 host、保留 cookie；HTTPS 配 `Secure=true`，本機 HTTP 配 `false`；案件可能已超過 24 小時。 |
| OCR 503／逾時 | 用清晰合成文件確認模型與 CPU 可用；查看結構化錯誤碼。不要把錯誤改成 Mock 成功。 |
| 對話 503 `LLM_NOT_CONFIGURED` | 外部模式缺少後端 `LLM_API_KEY`／`LLM_MODEL`；目前先使用 `grounded_rules`，金鑰稍後再安全設定。 |
| 對話 503 `INVALID_LLM_CONFIG`／`LLM_PROVIDER_ERROR` | 檢查受信服務網址及設定；勿輸出真金鑰或供應商原始錯誤，實際外部 API 尚待授權後驗證。 |
| API 429 | 停止密集重試並依 `Retry-After` 等待；多使用者可能共用代理 IP。 |

查看 `docker compose logs --tail 100 app` 時，請避免擴充成記錄原始上傳內容、個資或完整模型提示的日誌。正式部署與 Phase 3 交付是否通過，以當次實際驗收報告為準。
