# 續作狀態

更新：2026-10-30（臺灣）。**Cloudflare固定雲端與Runtime金鑰部署驗收通過。**

- current_phase：Phase 3／固定雲端展示 DONE。
- current_task：DEPLOY-20261029 DONE；最後交付同步GitHub進行中，完成後核對遠端SHA。
- last_completed_task：真模型三尺寸、真OCR、雲端容器停止／冷啟後持久案件與最終HTTP45驗收。
- last_successful_test：全後端1045／Node225、三尺寸Mock87、受控Runtime key browser12、雲端HTTP83／4真分析、三尺寸16則真助手回覆／134.367秒、終驗HTTP45；232映像檔hash一致。冷啟停止194.7秒後觀察新boot、正確映像、原案一致及刪404。
- public_url：https://paris-claim-demo.kevinyaungputra.workers.dev
- runtime：Cloudflare Worker paris-claim-demo，最後版本95fbf09b-4c2d-40d5-8909-2b18b3fd1942；Workers Static Assets＋native durable_object Container＋獨立ClaimStore SQLite DO。電腦關機仍可用，不依賴舊Quick Tunnel或本機PID。
- runtime_settings：沿用已確認Workers Paid，未開新訂閱／變更其他站點；Wrangler4.155.0、standard-1、單一具名路由、180秒閒置，無平台max_instances硬上限。新映像於冷啟載入，不強制中斷活躍工作。
- storage：HTTPS內部回呼以獨立secret保護；owner hash、24h TTL／alarm、20案、CAS、只存結構化結果，原檔不持久。平台備份非即時物理抹除。
- model：固定deepseek/deepseek-v4.1-flash-1017／官方DeepSeek／low，300秒模型／310秒後端／330秒網頁。來源／語意／model／cost等守門保留，無自動重試或換模型。
- runtime_key：RUNTIME_LLM_KEYS=true，分頁從URL讀入後移除，僅必要同源header；無key時AI401，其他官方規則／文件／OCR可用。runtime health configured依當次header，verified刻意false，不沿用別人成功。真key未上雲／入Git／DB／產物。
- private_demo_link：.local/secrets/cloudflare-demo-link.txt，僅本機使用者權限，已Git／Docker排除。不要在對話或工具輸出重述內容。
- privacy：初始URL仍經瀏覽器／Cloudflare，Navigation Timing可能保留；禁止Analytics／RUM外送。刷新後需重開含key連結；必要語意／query外送界線見API契約。
- image：sha256:da0d6c05a195b179e0a6a6170eaaf4792aa9579be0742c5b5106880396761b00，232hash同源，無憑證／DB／上傳原檔；最後Worker私有status改動未改後端／前端映像。
- source_repository：https://github.com/kekekewww/Paris_Hack ，預設分支main；本機implementation/claim-preparation保持，無force push。
- current_blockers：原型部署無阻擋。OpenAI／Gemini依使用者決定暫緩；完整商品碼仍unverified，不當成保障證明。key到期／用量與Cloudflare方案計費為後續外部依賴。
- limitations：容器重啟中的背景工作會失效；原檔重整重選；第一次冷啟可能短暫需重試。早期lifecycle begin未記階段，無法確認是否有空白匿名合成fixture，若有依24h TTL清理，不能宣稱資料庫全面清零。
- saved_evidence：docs/cloudflare-20261030/ACCEPTANCE.md與tests／HTTP／live／lifecycle／final-http／image-hashes／security-scan JSON；首輪排程、欄位誤擋與harness失敗保留，不改寫歷史。
- design：原HTML與備份SHA256仍59a6fd5053e9811560823b3f12637ef0c7bbe7f3aa2fd9a1abe1ea90fad1c8a1，原品牌與Vanilla架構延續，Mock保留。

## 下次工作的三步

1. 先讀規範與進度，核對Git／Cloudflare版本；不要憑舊本機PID或Quick Tunnel重啟其他服務。
2. 使用自己的短期限額key連結測試；runtime health verified=false是設計，不應改為共用驗證。模型失敗保留安全stage，避免記原文／key。
3. 修改後依相關範圍重驗並更新文件；部署保留DO綁定／migration與內部secret。商用、更多保單或供應商需另有官方來源與實際驗證。

本輪部署方法見docs/CLOUDFLARE_DEPLOYMENT.md；2026-10-26以前的功能／隧道／模型結果均是歷史，不當成本次雲端證據。
