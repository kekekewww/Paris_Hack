# 助手連續追問修復與模型範圍

日期：2026-10-19（臺灣）。狀態：**追問修復已發布；當前真模型重驗因上游限流BLOCKED**。[同一公開網址](https://retirement-trim-reported-jesus.trycloudflare.com/?service=api)已更新。規則流程通過不代表模型重驗通過。

## 使用者回報與實際重現

公開版依序輸入「你好」「我出車禍了」「沒有住院」，三次均由`grounded_rules`回覆相同的`care_setting`追問，沒有呼叫OpenRouter，也沒有類別提案或案件更新。真HTTP重現及桌面瀏覽器兩項預期RED均已取得；第二項另重現已建立案件重進描述畫面時的舊訊息殘留。

OpenRouter曾經真實連通並驗證回覆的[前輪紀錄](OPENROUTER_ACCEPTANCE.md)仍成立；那不表示所有助手訊息都由模型產生。本輪額外已知住院文件問題的真模型探測回`503 / LLM_RATE_LIMITED`，不能用health的歷史verified=true當成這次成功。

## 根因與修復範圍

未選類型時，規則只取正向類別，沒有利用「已明確沒有住院」決定下一問；類別未知就一律回同句。OpenRouter adapter遇本機`clarification`會直接回傳，因此模型沒有參與這三輪。這是規則引導銜接問題；金鑰設定與免費供應商限流是各自獨立的狀態。

修復保留既有資料邊界與確認步驟：依已知事實追問未知資訊，不把沒有住院等同門診；肯定就醫後才提供可確認候選，獨立建立才更新案件。否定、未就醫、不確定與本次事件更正需保留，不沿用舊次手術。急診只有明確就醫陳述才可作待確認導航，是否適用仍須依個別保單與官方確認；[官方分類頁](https://life.cardif.com.tw/zh/a314)提供醫療門診資料，未明定急診保障，不以導航候選冒充保障依據。

每則助手訊息新增短標示「規則引導／AI回覆／模擬」，無來源的舊資料不猜成AI；既有服務說明揭露有依據的文件問答使用模型、類型釐清與安全回覆採規則。已建立案件重新開始描述時不顯示舊對話，但保留原案件至真正送出新描述，可繼續原工作區；尚未分類的草稿仍同案續聊。

本輪沒有擴成通用聊天、沒有把使用者原話或醫療檔案送到雲端，也沒有改免費路由、價格限制、API公開鍵值、官方文件規則、CSS或依賴。

## 驗證紀錄

| 驗證 | 最終結果與範圍 |
| --- | --- |
| 修復前公開重現 | 真HTTP三句全同一規則追問；桌面API兩個browser案例預期RED（含舊案訊息殘留） |
| 全後端 | **347/347，38.07秒**；含新追問54及相關AI270，僅既有Starlette deprecation warning1 |
| 前端單元 | **56/56，605.586ms**；含Mock35及元件21 |
| 既有Mock三尺寸 | 初輪84pass／3fail，原因是舊固定追問文案斷言；改為新澄清文案並新增空類別／空文件／clarification／無候選／無更新斷言後，**最終87/87，1.8分鐘** |
| 真API／OCR三尺寸 | **27/27，1.7分鐘**；最終backend/UI的首映像，之後只改Mock未確診詞防護，不冒稱此27項在最後映像重跑 |
| 最終映像雙服務追問 | **12/12，36.5秒**；Mock/API × 兩情境 × 1440／768／390 |
| 新公開追問 | **6/6，33.3秒**；API兩情境×三尺寸，非預期console／pageerror0、無溢出；合成案件均清除 |
| 新公開真模型 | **1 fail**，真正上游回`503 / LLM_RATE_LIMITED`，另保留對應network console1；沒有把它算成AI短標／模型回答成功 |
| 原公開完整腳本 | 原斷言未改，執行在`OpenRouter actual process verified` **FAIL**；後續安全檢查未執行，**本輪沒有23項全通過的結論** |
| 金鑰與私有檔 | key狀態實GET200、usage0／remaining0.1；Vite一般與@fs403、native私有路徑404，未含金鑰。這不替代真模型成功 |

後端／Mock審查發現的共同否定、未確診、後續明確確診、本次事件重設與舊手術沿用，均先RED後修；有限覆核已無殘留必要問題。先前333／50／54項GREEN及所有RED保留，不作最終版本的數字。沒有改OCR；本輪347及API27無OCR失敗，亦不宣稱歷史OCR例外根因已修。

三尺寸合成對話已目視檢查：[桌面](assistant-followup/desktop-1440.png)、[平板](assistant-followup/tablet-768.png)、[手機](assistant-followup/mobile-390.png)。每則短標清楚，既有品牌、CSS與版型保留。新followup與live關閉trace／失敗DOM快照，分享紀錄不含cookie或原始模型內容。

## 交付與當前阻礙

最終映像`cardif-claim-preparation:followup-20261019`，ID為`sha256:6e858e7909ded431ab4bfe41911c93c15054942a5ce6bb3d009d0e104d7a57ef`。公開dist來自同一最終映像，保留舊雜湊資產供既有頁面；同URL、DB與私有key保留。公開8002 parent65932／listener59552、cloudflared36692運行，單worker、原origin／Secure cookie設定保留；專用驗收容器及volume已核對清除，image保留。

追問bug修復任務DONE；新程序`llm_configured=true`，但因本輪尚無新真模型成功，`llm_verified=false`。ASSISTANT-LIVE、當前P2-04／P2-09／P3-04C／P3-GATE保持BLOCKED，等待免費容量恢復後用原live及原完整公開腳本重驗。前輪真成功仍可查，但不當成這次成功；未換付費模型、自動重送、Mock或規則假成功。

一次將公開腳本的模型verified=true改為只驗boolean型別的操作被自動審核拒絕，理由是弱化有意義的斷言。該命令未執行；保留原腳本並實跑其失敗，沒有以替代腳本繞過。[審核紀錄](assistant-followup/approval-review.json)。

[完整去敏感摘要](assistant-followup/test-summary.json)、[原公開三句重現](assistant-followup/probe-before.json)、[本輪真模型失敗](assistant-followup/public-live.json)、[原完整腳本失敗](assistant-followup/public-http.json)、[金鑰／私有檔查核](assistant-followup/final-key-status.json)與[清理紀錄](assistant-followup/cleanup.json)。原始RED／GREEN輸出保存在`.local/assistant-loop-20261019/`。

最後[health實讀](assistant-followup/health-final.json)為HTTP200／configured=true／verified=false；[真金鑰掃描](assistant-followup/leak-check.json)涵蓋355檔、匹配0。原HTML與備份SHA256均保持`59a6fd5053e9811560823b3f12637ef0c7bbe7f3aa2fd9a1abe1ea90fad1c8a1`。本機文件連結與差異格式檢查通過。
