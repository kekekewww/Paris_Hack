# Cloudflare Quick Tunnel 臨時展示

> 2026-10-20 目前網址：[理賠準備助手](https://boots-deaf-found-arrange.trycloudflare.com/?service=api)。真實語意模式已部署，最終新程序公開HTTP23原斷言通過，verified來自本輪真模型招呼；完整模型旅程仍受免費限流阻擋。477後端、最終容器追問12與三尺寸視覺通過，詳見[本輪報告](SEMANTIC_CONVERSATION.md)及[目前狀態](../STATUS.md)。以下為歷史網址與歷史驗收，不代表目前程序。

> 最新連續追問修復已發布（2026-10-19），後端347／前端56、Mock87／API27、最終容器追問12／公開6通過。但本輪真模型回503限流，原公開完整腳本在模型verified斷言失敗；當前整體gate保持BLOCKED。以下OpenRouter成功與程序為前輪歷史，最新以[追問修復報告](ASSISTANT_FOLLOWUP.md)為準。

> 最新OpenRouter交付（2026-10-19）：真實免費路由已啟用，原訂MVP的P2／P3整體gate已通過。最終後端293、本機三尺寸成功證據（原2pass1fail＋平板重驗1pass）、容器56checks真OCR／live1／restart及公開live1／HTTP23均完成。免費限流與額外CLI未通過仍保留，完整結果以[OpenRouter驗收](OPENROUTER_ACCEPTANCE.md)為準。以下舊版「未驗證／BLOCKED」為當時歷史，已由新授權與實測取代。

> 最新引導修正（2026-10-19）：先以具名radio選類型、再獨立建立清單，已發布。單元36、三尺寸Mock87、PDF2、真API27、G1、公開HTTP23／browser3（51.6秒）及新版容器60checks／引導browser1（11.3秒）與真restart均通過。[完整報告](GUIDED_CHOICE.md)含新版映像、截圖與去敏感結果；下方先前輪次保留為歷史，不混稱目前版本。外部LLM仍未驗證。

> 本輪無金鑰完整續驗：相同公開網址HTTP22 checks與瀏覽器3/3（36.4秒）再次通過，測試案件清除，服務維持運行；無外部模型請求。下方46.8秒為前一輪UI驗收歷史，最新完整結果見[續驗報告](ACCEPTANCE_NO_KEYS_20261019.md)。

## 前輪版本：2026-10-19 介面簡化

最新網址：[理賠文件準備助手](https://retirement-trim-reported-jesus.trycloudflare.com/?service=api)。新版已正式建置至 dist，公開 HTTP **22 checks PASS**、瀏覽器 **3/3 PASS（46.8秒）**，涵蓋兩入口、缺漏／清晰 PNG 真 RapidOCR、PDF／mixed 第2頁、人工確認、重新整理與摘要下載；console／pageerror0，合成測試案件均已刪除。

8002 與 cloudflared 沿用當日重啟程序（listener40288、tunnel36692），本輪實際 health 與完整公開流程均正常；未操作其他8000／3137服務。精確 origin、Secure／HttpOnly／Strict host-only cookie、私有路徑404與origin403再次驗證。證據在 `.local/ui-simplification/public-http.json` 與 `public-results`，UI與三尺寸驗收見[介面報告](UI_SIMPLIFICATION.md)。生成式LLM仍未設定，`llm_verified=false`。

以下10/17網址、PID與數字保留為歷史，不能當作目前入口。臨時網址仍需本機與隧道持續執行。

## 2026-10-19 目前展示

依使用者要求重啟後的新網址：[開啟理賠文件準備助手](https://retirement-trim-reported-jesus.trycloudflare.com/?service=api)。原專案8002與舊隧道已停止；本次重新啟動專用8002及Quick Tunnel，未操作其他服務。精確新origin、Secure cookie、單worker、no-proxy-headers及grounded_rules沿用；外部LLM仍未配置。

本次公開HTTP **11項通過**：首頁、health、API模式／模型狀態、安全cookie、no-store、惡意來源403、案件建立／同cookie讀取／另一owner404／刪除／刪除後404。公開桌面門診流程 **1/1通過，18.1秒**：清晰PNG真RapidOCR、遮罩欄位、重新整理、具來源問答及摘要下載；console／pageerror0，測試案件已清除。產品程式未修改，歷史整套驗收沒有重跑。

目前cloudflared PID36692、app launcher38128、8002 listener40288；PID與網址均可能在下次重啟改變，操作前需重新核對。日誌、URL、runtime JSON、HTTP與瀏覽器結果在`.local/quick-tunnel/2026-10-19/`，目前URL另存`.local/quick-tunnel/url.txt`。其他程序佔用8000與另一個3137隧道不在本次重啟範圍。

這是臨時網址，電腦、應用與隧道需保持執行。下方10/17網址與程序均為歷史，請使用上方最新連結。

## 2026-10-17 歷史紀錄

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
