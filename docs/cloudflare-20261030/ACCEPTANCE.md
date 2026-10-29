# Cloudflare固定展示驗收

日期：2026-10-30（臺灣）。部署延伸項目 **DONE**，原型範圍驗收通過。

[開啟網站](https://paris-claim-demo.kevinyaungputra.workers.dev)；AI入口格式為`/?key=<你的短期OpenRouter金鑰>`。本機含key連結保存在受使用者限定權限保護的`.local/secrets/cloudflare-demo-link.txt`，沒有上傳或在報告重述。

## 部署與功能

沿用指定email的既有Cloudflare Workers Paid，沒有新訂閱。Workers Static Assets供應原Vanilla／Vite前端，原FastAPI與PyMuPDF／RapidOCR在Container執行；案件由獨立SQLite Durable Object持久保存，電腦不需持續開機。沒有Vercel部署、DNS變更或其他網站操作。

最後Worker版本`95fbf09b-4c2d-40d5-8909-2b18b3fd1942`，Wrangler4.155.0、原生durable_object容器排程；映像`sha256:da0d6c05a195b179e0a6a6170eaaf4792aa9579be0742c5b5106880396761b00`。單一具名路由、standard-1、180秒閒置；沒有平台max_instances硬上限。新映像在下次冷啟採用，不強制打斷活躍工作。

前端Runtime key只在當次分頁記憶體及必要同源標頭出現；後端依請求／工作隔離並送往OpenRouter，缺key不使用伺服器fallback。文件需求仍來自官方規則，真實模型固定已授權DeepSeek／OpenRouter；300秒模型、310秒後端、330秒網頁與費用／來源／語意守門保留。health的verified刻意逐請求為false，不能用它代替本次模型結果。

## 證據

| 驗證 | 結果 | 範圍 |
|---|---|---|
| 後端全套 | 1045／1045 | 真app遠端儲存契約、rules、OCR、模型守門、runtime隔離；1既有Starlette警告 |
| Node全套 | 225／225 | actor30、native控制器27、gateway18及既有前端 |
| 三尺寸Mock | 87／87 | 雙入口、操作、錯誤、鍵盤、axe與回歸；不冒充真API |
| Runtime瀏覽器 | 12／12 | 正式preview、受控合成傳輸、URL移除、標頭白名單、刷新、302拒絕 |
| 雲端真HTTP | 83／83 | HTTPS、cookie、owner、CAS、官方302目錄／8FAQ、缺key／非法key、文件及清理 |
| 雲端真分析 | 4次 | 可擷取PDF、缺漏PNG、掃描PDF、5,945,747 bytes合法PDF；保留人工覆核，manual_ready及reload一致 |
| 三尺寸真助手 | 3／3，16則成功回覆 | 問候→車禍→否定住院→必要追問→選型與獨立建立；一案文件問答、摘要／刷新／缺key；134.367秒 |
| 真文件問答 | 通過 | 直接回答九欄位、簽名日期、法真實限制、非核准及唯一官方申請書p1；不以任一官方URL當切題證明 |
| 雲端視覺 | 1440／768／390通過 | 首頁／工作區，零pageerror與水平溢出；實際截圖已檢視，過場截圖另重拍 |
| 容器冷啟與案件 | 通過 | 閒置194.7秒後先觀察停止，再讀回完整原案，觀察新boot與正確映像，刪後404 |
| 最後版本HTTP | 45／45 | 冷啟後首頁／資產／私有路徑／key拒絕／CRUD與隔離；未額外呼叫模型或OCR |
| 產物與安全 | 232檔hash一致 | 映像無key、DB、上傳原檔；Git／產物真key精確比對0命中，原HTML兩份hash不變 |

16則是成功網站助手回覆數，API未公開逐回覆model／cost metadata；模型與費用等驗證由已測試的後端執行。OpenRouter前後唯讀總用量增加且在驗收預算界線內，此快照不等於逐請求收據，也不保證未來容量。最後新增私有status的Worker與真模型測試使用同一後端／前端映像，最終HTTP45另驗最後Worker版本。

可機讀紀錄：[總表](tests.json)、[真HTTP](http.json)、[真助手](live-browser.json)、[冷啟](lifecycle.json)、[終驗](final-http.json)、[視覺](visual.json)、[映像指紋](image-hashes.json)、[安全掃描](security-scan.json)。

## 失敗與限制

首次default排程遭帳號拒絕，依官方新版介面修正。真建立案422來自憑證尾綴誤擋官方病歷授權條件，先RED再精確三態例外修復，三類完整app遠端契約通過。Mock首輪缺瀏覽器路徑已停止，選現有Chrome後87通過。

首輪真對話已成功，但驗收工具仍要求舊版整段原文；依當前受控回答契約修正、18個離線正負例與最後真流程通過。首輪總用量未增加保留為觀測，未猜原因或宣稱零成本。初次lifecycle begin assertion未記具體階段，後續加入stage及失敗清理；不能確認該次是否建立匿名空白合成案，若有依24小時TTL清理。所有有捕捉到ID的後續測試案皆刪除並404，不宣稱資料庫全面清空。

URL金鑰的初始請求仍經過瀏覽器／Cloudflare，Navigation Timing亦可能保留；不外送效能／URL至Analytics或RUM。此方式僅限使用者明確接受的短期限額Demo，重整需重開含key連結。key本身的到期／用量與既有Cloudflare計費仍是外部依賴。

案件24小時TTL／每owner20案／CAS不等於即時物理抹除平台備份。原檔只在分頁受限記憶體，重整重選；容器重啟中的背景工作失效，沒有付費自動重試。首次冷啟可能短暫顯示可操作的重試頁。OpenAI／Gemini維持使用者暫緩決定；未驗完整保單代碼、全面手寫或正式理賠核准，界線見[已知限制](../KNOWN_LIMITATIONS.md)。
