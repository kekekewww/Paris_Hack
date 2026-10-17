# Cloudflare Quick Tunnel 臨時展示

日期：2026-10-17（臺灣）。使用者明確要求以 Cloudflare Quick Tunnel 提供公開連結；本輪已建立並實測 HTTPS 展示入口，沒有設定或使用外部 LLM 金鑰。

展示網址：[理賠文件準備助手](https://chevy-beach-pizza-triple.trycloudflare.com/?service=api)。這是臨時網址，電腦、本機應用與隧道必須持續執行；停止後失效。網址與存活期間依 [Cloudflare 官方說明](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)，不視為固定網址或常駐服務。

## 執行設定

- `cloudflared 2026.9.1 --no-autoupdate tunnel --url http://127.0.0.1:8002`，隱藏視窗啟動；無帳號變更、服務安裝或 DNS 變更。
- 專用 FastAPI 綁定 loopback 8002、單 worker、`--no-access-log --no-proxy-headers`；原 8000 本機展示服務保留。
- `ALLOWED_ORIGINS` 僅接受本次精確 HTTPS origin，`SESSION_COOKIE_SECURE=true`，cookie 仍為 host-only／HttpOnly／SameSite=strict。
- `LLM_PROVIDER=grounded_rules`，`llm_verified=false`；對話為官方資料檢索與規則，外部生成式模型仍待金鑰。
- 使用獨立 `.local/quick-tunnel/cases.sqlite3`，不公開原本機案件庫；不持久保存上傳原檔。只以合成文件展示。
- 保留 120 次／分鐘限制；因不信任轉送 IP，隧道訪客共用 loopback 計數。本次未擴充多副本或正式登入。

## 實際公開 HTTPS 驗證

**HTTP 23 項通過**：首頁、建置 JS、health、API 模式與 LLM 真實狀態、no-store／CSP／nosniff、安全 cookie、實際 Vite PDF worker 的 JavaScript MIME、WASM MIME、三個私有路徑 404、錯誤 Origin 與 cross-site 403、合成案件建立／讀取／更新、另一 cookie owner 讀取 404、刪除及再讀 404。測試案件已清除。

**Playwright 桌面 3/3 通過，39.2 秒**：

1. 引導路徑、官方連結、缺漏 PNG 的真 RapidOCR、人工確認、摘要與重新整理。
2. 快速選擇門診、清晰 PNG 的真 RapidOCR、問答、保存與摘要下載。
3. 真 PDF 文字擷取、畫布、混合 PDF 第 2 頁品質提示與對應框線。

三項均透過公開 HTTPS 執行，console／pageerror 0，逐案 DELETE 清除斷言通過。成功業務結果未改成 Mock；測試輸入全部為既有合成文件。

初輪 HTTP 驗證腳本曾猜測不存在的 `/pdfjs/pdf.worker.min.mjs` 而得到 404；改為查核建置產物 `/assets/pdf.worker-PhvoOpM7.mjs` 後 23 項通過，沒有更改產品程式或安全設定。

## 存活與接續

本次 cloudflared PID 為 74076；應用 launcher PID 45436，8002 listener PID 75472。PID 會變動，停止前需核對執行檔、命令及連接埠，避免操作其他服務。執行紀錄、PID、URL、HTTP 結果與瀏覽器證據存於忽略版控的 `.local/quick-tunnel/`；不提交 cookie 或案件資料庫。

重啟 Quick Tunnel 會取得新網址，必須以新 origin 重新啟動專用應用，再檢查 HTTPS 與 cookie。若下一工作階段程序已停止，舊網址不可當成仍然可用。固定網域、常駐主機與正式營運部署仍需另行安排，但不影響本輪已驗證的臨時 HTTPS 展示結果。

Phase 2 與整案仍等待真實外部 LLM 驗證；本輪不宣稱全部階段完成。
