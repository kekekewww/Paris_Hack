# 模型長等待與背景對話

> 本頁保留長等待修正當輪結果；後續已依使用者授權改用指定DeepSeek付費模型，[最新模型與驗證](DEEPSEEK_SETUP.md)。300／310／330秒及背景查詢保持，下方free專用費用限制與限流結果為歷史。

更新日期：2026-10-20（臺灣）。使用者指出思考模型常需100–300秒，將OpenRouter等待由35秒延長至300秒。這是等待機制修正，完整模型旅程的驗收狀態另見[目前狀態](../STATUS.md)，不以配置或受控測試取代真實模型結果。

| 層級 | 期限與行為 |
| --- | --- |
| OpenRouter | 預設／最多300秒，包含等待及讀取完整回覆；`asyncio.timeout`整體期限與HTTPX timeout均保留 |
| 後端對話 | 模型及對話處理310秒；背景工作提交立即202，查詢使用短GET |
| 網站 | 全部提交、查詢及等待合計330秒；單次HTTP最多15秒，每3秒查詢一次 |
| 一般API／OCR | 一般15秒、前端分析95秒／後端90秒維持原設定 |

Cloudflare現行預設Proxy Read Timeout為125秒，官方建議長時間工作採狀態查詢；Quick Tunnel不支援SSE。因此網站改為提交一次背景工作，再以短HTTP查詢，避免單條HTTP連線等待五分鐘。[Cloudflare 524](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/)、[Quick Tunnel限制](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/#limitations)。延長本機等待不代表免費供應商保證在五分鐘內完成；上游限流、服務錯誤與不合規輸出仍會明確顯示。

`ApiClaimService.sendMessage()`對UI仍回原本`{case,response}`，API傳輸新增短POST `/cases/{id}/message-jobs`與GET `/cases/{id}/message-jobs/{job_id}`。[完整契約](API_CONTRACT.md)。等待畫面以原有狀態區顯示最多五分鐘，按鈕在完成或失敗前保持忙碌，不新增大量工具文字。

工作只保存在單worker記憶體，依owner及案件隔離、同案防重、限制執行與保留數量、15分鐘回收。長模型運算不持案件鎖，刪案可取消本機工作；寫入前重新確認案件存在及類型／條件，禁止舊回覆覆蓋新情境或重建刪除案件。文件準備進度可保留於最新案件，不以模型快照覆寫。重新啟動會清除工作狀態；重新整理會停止該分頁查詢，已完成訊息可從案件恢復。取消本機等待不保證非串流供應商已停止生成。[OpenRouter取消說明](https://openrouter.ai/docs/api_reference/streaming#stream-cancellation)

模型仍固定`openrouter/free`、零價格護欄、不重試或切付費備援、無Mock或本機假成功；語意4096／文件1800 token與finish、費用、來源及事實驗證保持。API key仍只在後端，變更私有配置時僅改逾時數字，不重述秘密值。

## 驗證與部署結果

| 檢查 | 本輪結果 |
| --- | --- |
| Provider長等待 | 新測試先2個預期RED；修正後103/103離線PASS。以100倍加速deadline讓合成100秒等待跨舊35秒期限，實際取消護欄也保留 |
| 全後端 | 544/544 PASS，28.96秒；既有Starlette棄用warning1。新manager44／jobs API22涵蓋隔離、共用容量、TTL、取消、刪案／關閉、虛擬180秒、情境改變與一次保存 |
| 全前端 | 69/69 PASS；jobs新增11項先RED，包含超50秒與330秒整體期限、HTTP取消、格式、單POST、終態停止及錯誤不fallback；Node MockTimers實驗warning1 |
| 三尺寸Mock | 87/87 PASS，2.8分鐘，三尺寸各29，console／pageerror0、axe9掃描違規0；[摘要](llm-wait-20261020/mock-summary.json) |
| 三尺寸真API／OCR | 27/27 PASS，2.0分鐘，三尺寸各9；獨立8004 grounded_rules與真PNG／PDF／RapidOCR，非外部模型成功 |
| 受控長等待UI | 桌面／手機4/4 PASS，22.3秒；虛擬超過126秒、至少42次pending短GET且最多1個in-flight、單POST、忙碌／失敗／手動重試、確認前零PATCH、完成停止查詢，console／pageerror／橫溢／失敗網路0 |
| 公開啟動檢查 | 15/15 PASS；首頁／JS／CSS、安全cookie、私有路徑與合成案件隔離／刪除，[證據](llm-wait-20261020/startup-smoke.json)，這組零模型請求 |
| 真OpenRouter新工作 | **FAIL：LLM_RATE_LIMITED**。唯一招呼探測整次6.946秒；POST202耗761ms、首個GET200耗452ms且failed，未重送，合成案件已刪除。這不是300秒逾時，也不是模型成功；[證據](llm-wait-20261020/public-job.json) |
| 新Docker build | **BLOCKED**：本機dockerDesktopLinuxEngine pipe不存在，引擎未啟動；沒有成功新映像。前輪semantic映像保持歷史，不含本輪修正 |

受控UI全API回覆均為合成fixture，保留`provider:mock／is_simulated:true`，畫面加上controlled_transport測試標示，不冒充真模型或後端。舊HEAD adapter的桌面RED只證明它仍送同步端點、沒有建立job；不能把這項RED當作真Cloudflare逾時實測。新版受控虛擬126秒通過則涵蓋舊前端50秒的回歸。兩尺寸截圖經實際目視：[桌面](llm-wait-20261020/controlled-wait-desktop.png)／[手機](llm-wait-20261020/controlled-wait-mobile.png)。

詳細測試數字及部署hash見[彙整](llm-wait-20261020/tests.json)。初次沙箱pytest／Playwright啟動停滯未取得結果，核對並清理己方程序後以授權執行正常測試；Mock初次未進tests紀錄另存。隔離build首次npm參數解析將outDir當root而失敗，改直接Vite CLI成功，未改產品斷言或公開舊dist。原完整模型驗收的成功、限流與INVALID仍保留於[語意紀錄](SEMANTIC_CONVERSATION.md)。

本輪實際秘密值presence-only掃描400檔零匹配、原始設計備份SHA256未變，文件連結261項通過。掃描不輸出秘密值；測試原始輸出目錄新增Git排除，僅保留已檢查的去敏感證據。

正式網站已重啟8002，沿用[展示網址](https://tulsa-ppc-message-builders.trycloudflare.com/?service=api)與既有案件庫；啟動log實際顯示`Backend model timeout seconds: 300.0`。本次正式JS為`index-h9YV-k--.js`，CSS及原設計保持，舊dist已備份。測試8004與5174／5176已核對清理；公開服務與隧道保留。`configured=true／verified=false`，本輪長等待任務DONE、完整模型及P2／P3整體gate仍BLOCKED。

重現方式：`npm test`、`.venv/Scripts/python.exe -m pytest -q`；受控UI使用`node node_modules/@playwright/test/cli.js test -c playwright.message-wait.config.js`，不呼叫模型。完整真模型仍需明確設定`LIVE_OPENROUTER=1`與`CLAIM_API_BASE_URL`再執行`playwright.openrouter.config.js`，每輪保留真模型、來源及確認斷言，不因free限流改付費或降標。
