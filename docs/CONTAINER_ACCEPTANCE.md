# 本機容器驗收

> 最新引導修正（2026-10-19）：先以具名radio選類型、再獨立建立清單，已發布。單元36、三尺寸Mock87、PDF2、真API27、G1、公開HTTP23／browser3（51.6秒）及新版容器60checks／引導browser1（11.3秒）與真restart均通過。[完整報告](GUIDED_CHOICE.md)含新版映像、截圖與去敏感結果；下方先前輪次保留為歷史，不混稱目前版本。外部LLM仍未驗證。

> 2026-10-19無金鑰續驗：重用下述b25049ed映像，另建隔離容器完成60checks、瀏覽器1/1（9.6秒），並真restart確認案件完全一致、刪除404；權限與私有檔檢查通過，測試容器／volume已清。未改產品或宣稱重新build，新證據見[本輪報告](ACCEPTANCE_NO_KEYS_20261019.md)。

## 2026-10-19 引導選擇修正產物

目前tag：`cardif-claim-preparation:guided-20261019`，image ID：`sha256:8380799888f4d4783df2815292e833c77ec77a281ad721bcf5de42fed50434f0`。實際Docker build exit0，前端新radio與build操作存在、舊confirm-suggestion不存在。以專用paris-claim-guided-20261019 container／paris_claim_guided_20261019 volume及loopback8004驗收60checks PASS、引導browser1/1（11.3秒），再真restart確認同cookie案件完全一致及刪除404。UID10001、唯讀、capdropALL、no-new-privileges及私有檔排除皆通過，專用資源已清除、image保留；未傳入金鑰。新版[metadata](guided-choice/container-runtime.json)、[smoke](guided-choice/container-smoke.json)及[重啟紀錄](guided-choice/container-persistence.json)提供實際證據。

## 前輪：2026-10-19 介面簡化產物

`docker build --progress plain -t cardif-claim-preparation:ux-20261019 .` 實際exit0；image ID為 `sha256:b25049ed997c4d2167562056356dbed1d464cb8112918740d3cde3fc3c3130af`。映像內實際確認含「描述我的狀況」新版入口，UID10001／rootfs唯讀／capdropALL／no-new-privileges，無.env／.git／tests／demo／docs。沒有傳入金鑰或改動後端依賴。

以專用 `paris-claim-ux-20261019` container、`paris_claim_ux_20261019` volume、loopback8004運行，等HTTP ready後執行同一 `scripts/smoke_api.py --include-ocr`：**60 checks PASS、cleanup=VERIFIED_DELETED、exit0**。清晰圖為真rapidocr、模糊圖quality_precheck／未OCR／uncertain、mixed以pdf_text與第2頁品質提示。再以該容器實跑新版快速選擇門診／清晰PNG／保存／摘要瀏覽器 **1/1 PASS（11.9秒）**，console／pageerror0。證據在 `.local/ui-simplification/container-browser-results`。

核對container映像與volume識別後，只清除此專用container／volume，保留image與公開8002。本輪後端／權限設定未改；下方重啟持續性及其他10/17結果保留為歷史，沒有將其當作新版再次執行。建置工具的Git metadata擷取警告不影響exit0，映像識別以上述digest為準。

以下為10/17版本歷史；目前新版UI完整驗收另見[介面報告](UI_SIMPLIFICATION.md)。

日期：2026-10-17（臺灣）。結果：**實際映像建置、本機容器運行、HTTP／真實 OCR、資料持續性與基本執行限制均通過**。此結果不代表公開 HTTPS 或外部生成式 LLM 驗收通過。

## 建置與識別

Windows Docker Desktop 的 Linux Engine 29.8.1 實際執行：

```powershell
npm run build
docker compose --env-file .env.example config --quiet
docker compose --env-file .env.example --profile https config --quiet
docker build --progress plain -t cardif-claim-preparation:validation .
```

設定解析及多輪實際映像建置皆退出碼 0。最後一輪包含品質預檢、逐頁提示、安全診斷及上傳狀態修復；其 image ID／manifest list digest 為：

```text
sha256:a7e45621b8284cebe41c57cd0b0cf99d5887d55e4f71dc364effd929be72b7cc
```

Node 22 建置靜態前端，Python 3.12 slim 執行 FastAPI 與本機 OCR；沒有將 key 作為 build arg。此 digest 是本次產物識別，不宣稱日後未固定基底 tag 的建置必然逐位元一致。

## 本機實際運行

驗收容器與 volume 使用專屬名稱，只綁定 loopback 8001，未發佈公開服務：

```powershell
docker volume create --label project=paris-claim-validation paris_claim_validation_20261017
docker run -d --name paris-claim-validation-20261017 --label project=paris-claim-validation --init --read-only --cap-drop ALL --security-opt no-new-privileges:true --tmpfs /tmp:rw,noexec,nosuid,size=67108864,mode=1777 --mount type=volume,source=paris_claim_validation_20261017,target=/app/.local -p 127.0.0.1:8001:8000 -e ALLOWED_ORIGINS=http://127.0.0.1:8001 -e RATE_LIMIT_REQUESTS=120 cardif-claim-preparation:validation
.venv/Scripts/python.exe scripts/smoke_api.py --base-url http://127.0.0.1:8001
.venv/Scripts/python.exe scripts/smoke_api.py --base-url http://127.0.0.1:8001 --include-ocr
```

`docker run -d` 返回不代表應用已就緒；先輪詢 `/api/v1/health` 到 200／status=ok 再執行 smoke。最終映像第一次立即執行時得到 `NETWORK_ERROR`、0 checks，屬啟動時差，未計作通過；加入就緒檢查後重新驗證。前一版映像 `08fbfd35…` 已通過 39 checks 與重啟持續性，後續 UI 修復後另建最終版，不將舊映像冒充最終結果。

前一版 `06078810…` 等待 HTTP 就緒後的第一個圖片請求因冷啟超出 45 秒回 `503 OCR_TIMEOUT`：33 checks 已通過、沒有成功圖片結果，案件清理成功。模型載入後同一腳本重試 **39 checks PASS、exit 0**。沒有增加預算或以 Mock 補結果。45 秒包含模型匯入、ONNX session／圖最佳化及首次推論，目前沒有分階段計時，不能將超時全歸因於初始化或主機資源。Health 僅代表 HTTP 存活及套件可找到，並非圖片模型已暖機；展示前先以合成文件 smoke 確認。

品質預檢與逐頁修復後重新建置上述 `a7e45621…` 最終版，等待 HTTP 就緒後首次完整 smoke **60 checks PASS、exit 0**，未發生冷啟逾時。此結果不抹除舊版本失敗，也不保證所有資源條件下皆不逾時。新 smoke 額外驗證模糊圖的真實品質量測（明示未 OCR）、混合 PDF 第 2 頁提示與遮罩欄位，未放寬任何斷言。

| 驗證 | 實際結果 |
|---|---|
| 非 root 與執行限制 | `user=10001:10001`、實際 `os.getuid()=10001`；rootfs 唯讀、cap_drop ALL、no-new-privileges |
| 可寫範圍 | `/app/.local` 測試檔成功寫入後刪除；程式目錄不可寫 |
| Health 真 HTTP | 200；`service_mode=api`、`grounded_rules`、`llm_configured=false`、`llm_verified=false`、`ocr_provider=pymupdf+rapidocr` |
| API／PDF smoke | **33 checks PASS**；3 類別、8 份此案件文件、已查核引用、owner 隔離、CRUD／規則／對話、文字 PDF |
| API／PDF＋圖片＋品質／混合 smoke | 最終版 **60 checks PASS**；缺漏 PDF 4 個 finding、清晰 PNG `rapidocr` 2 個 finding；模糊圖 `quality_precheck` 1 個品質提示、0 欄位；混合 PDF `pdf_text` 6 個遮罩欄位與第 2 頁品質提示，整體 uncertain |
| 案件清理 | 所有完成／錯誤 smoke 均執行 cleanup；最終版 `VERIFIED_DELETED`，DELETE 後 GET 404 |
| 重啟持續性 | 以同一 cookie 建立合成門診案件，`docker restart` 後 GET 200，內容完全一致；再刪除並驗 GET 404 |
| 靜態檔案 | 實際 module worker 200、`text/javascript; charset=utf-8`、`X-Content-Type-Options: nosniff` |
| 私有路徑 | HTTP `/.env`、`/AGENTS.md` 皆 404 |
| 映像內容 | `/app` 中 `.env`、`.venv`、`demo`、`tests`、`docs`、`.git`、AGENTS／PROJECT_PLAN 均不存在；案件目錄無上傳原檔 |
| 日誌 | 檢查啟停與 OCR 後日誌，未列原始文件或擷取內容；ONNX 出現唯讀環境不能持久保存 telemetry ID 的非阻擋 warning，辨識仍成功 |

所有輸入來自 `demo/documents` 合成資料；沒有真實保戶資料或理賠提交。Smoke 腳本只接受 loopback、禁止重新導向、不讀代理環境，不對外部模型發出付費請求。完整掃描 PDF、JPG、模糊、加密／損毀、頁數與像素限制另見後端 28 項 OCR 回歸及三尺寸 API 瀏覽器報告。

本次 smoke 與重啟測試未依賴 `.env`。最後只清理本次建立的驗收容器與專屬 volume；其他既有容器與資料不在清理範圍。映像保留於本機，可依上述命令重現。

## 驗收邊界

- 預設僅支援 1 worker／1 副本。程序內案件鎖、限流及 OCR 單工能力不代表水平擴充已完成。
- 套件已知漏洞查核見 [DEPENDENCY_AUDIT.md](DEPENDENCY_AUDIT.md)，不涵蓋基底作業系統／容器漏洞的完整掃描或正式資安認證。
- 公開部署仍缺主機、網域／DNS 及正式授權；未取得公開 TLS、未驗證外部 HTTPS 流程。
- 真實外部 LLM 金鑰依使用者決定稍後設定，相關驗收持續 BLOCKED。容器內本機規則與真 OCR 不能代替該證據。
