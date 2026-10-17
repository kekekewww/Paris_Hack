# 開發任務

更新日期：2026-10-17（臺灣）。主要規範為 `AGENTS.md` 與 `PROJECT_PLAN.md`。**本機可展示版本的必要開發與驗收已完成；Phase 2／3 整體與整案仍因外部 LLM、公開 HTTPS 依賴維持 BLOCKED。** DONE 僅限表列範圍，不代表外部閘門已通過。

使用者已選擇「先完成其餘工作，金鑰稍後設定」。目前沒有待執行的必要本機測試；不再次索取金鑰，不以本機規則、Mock 或離線 transport 代替真實供應商驗證。

| ID | 階段 | 工作 | 優先 | 狀態 | 相依 | 驗收條件 | 驗證證據／外部依賴 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1-01 | 1 | 原型盤點、保留與基準截圖 | P0 | DONE | 無 | 完整檢查與可恢復原設計 | 原1598行HTML、備份與基準截圖；最終原檔／備份SHA再次一致；[盤點](docs/PROTOTYPE_AUDIT.md) |
| P1-02 | 1 | ES Modules、Mock、API Contract | P0 | DONE | P1-01 | 服務可替換、狀態語意分離 | 原Phase1單元20/20；最新單元24/24、source freeze後Mock63/63；[契約](docs/API_CONTRACT.md) |
| P1-03 | 1 | 原設計首頁與雙入口 | P0 | DONE | P1-02 | 兩路徑可完整操作 | 三尺寸完整Mock及真API流程通過，品牌與原始設計延續 |
| P1-04 | 1 | 引導、追問、確認與重試 | P0 | DONE | P1-02 | 不確定先追問，確認才更新 | 三尺寸引導、錯誤恢復、延遲回覆導覽回歸通過 |
| P1-05 | 1 | 類別與條件直接選擇 | P0 | DONE | P1-02 | 三類別可建立案件 | Mock與真API直接選擇、條件更新與摘要通過 |
| P1-06 | 1 | 清單、狀態、來源與助手 | P0 | DONE | P1-04、P1-05 | 狀態可管理、保存，來源可追溯 | 重新整理／清除／收合／來源／人工確認皆經端到端驗證 |
| P1-07 | 1 | 上傳、預覽與Mock分析 | P0 | DONE | P1-06 | 檔案限制、位置與人工確認 | Mock63、PDF2與原競態回歸通過；真分析另列P2-06 |
| P1-08 | 1 | 摘要、下載與送件指引 | P0 | DONE | P1-06 | 可下載摘要且不宣稱核准 | 實際讀取下載內容；官方指引由來源服務提供；受控外部故障後仍可用 |
| P1-09 | 1 | 響應式、動畫、鍵盤與狀態 | P0 | DONE | P1-03至08 | 390／768／1440可完成操作 | 最新Mock各21/21、axe0、console／pageerror0；保留鍵盤、焦點與reduced-motion |
| P1-10 | 1 | Phase 1驗收 | P0 | DONE | P1-09 | 通過才開後端 | 原63/63及20/20通過；最新source freeze後Mock63/63、1.4分鐘；[原報告](docs/PHASE1_ACCEPTANCE.md) |
| P2-01 | 2 | FastAPI、模型、錯誤與健康檢查 | P0 | DONE | P1-10 | 本機契約與真HTTP可驗 | core49、新整套190/190與真API27/27；一般展示服務亦60checks PASS |
| P2-02 | 2 | 官方來源registry | P0 | DONE | P1-10 | URL／版本／頁碼／引用可追溯 | 11來源、9文件、22規則、8知識；來源及host一致；[來源紀錄](docs/OFFICIAL_SOURCES.md) |
| P2-03 | 2 | 三類文件規則引擎 | P0 | DONE | P2-02 | 條件式／unknown不誤判免附 | core49、全190與真API條件更新通過；review_required仍人工確認 |
| P2-04 | 2 | 真實外部LLM驗證 | P0 | BLOCKED | 後端安全配置與授權 | 真provider request、引用及失敗恢復 | 使用者金鑰稍後設定；未執行真模型請求，llm_verified=false，不能以離線113項代替 |
| P2-04A | 2 | LLM client／離線傳輸邊界 | P0 | DONE | P2-01、P2-05 | 結構、來源、逾時與錯誤處理 | AI113及整套190通過；外部client已實作、未真驗；[LLM說明](docs/LLM_INTEGRATION.md) |
| P2-05 | 2 | 官方RAG／引用／無依據處理 | P0 | DONE | P2-02 | 真本機檢索與保守回答 | AI113、全190與真HTTP通過；grounded_rules不是生成式LLM |
| P2-06 | 2 | 真PDF／圖片OCR與品質前檢 | P0 | DONE | P2-01 | 品質、欄位、逐頁位置及真HTTP | OCR28/28（29.44秒）、全190/190、品質6/6、API27/27、最終image60checks；歷史未明例外列known limitation |
| P2-07 | 2 | owner隔離、保存、刪除與隱私 | P0 | DONE | P2-01 | 24h TTL、不存raw、正確清除 | core49、全190、真API／容器隔離與刪除404；只支援單worker／單副本 |
| P2-08 | 2 | 本機HTTP／PDF預覽整合 | P0 | DONE | P2本機核心 | grounded_rules＋實際OCR端到端 | 最新API27/27、1.9分鐘、各9/9、console0；品質／mixed6/6、28秒，Mock63／PDF2／G1通過 |
| P2-09 | 2 | Phase 2整體驗收 | P0 | BLOCKED | P2-04 | 包含真外部LLM的全部閘門 | 本機部分已驗收；尚缺真provider驗證及其整合實測，不自動標完成 |
| P3-01 | 3 | 本機整合、回歸與安全測試 | P0 | DONE | P2本機核心、P2-08 | 本機實際流程與失敗恢復 | 全190、前端24、API27、品質6、Mock63、PDF2、G1及兩環境60checks通過 |
| P3-02 | 3 | A–H合成展示與mixed情境 | P1 | DONE | P2-08 | 本機流程、缺漏／模糊／無來源／受控故障 | 9合成檔、原8檔hash未變；G1證明PDF受控失敗後案件摘要可用；不代表官方真故障 |
| P3-03 | 3 | 本機安全與可靠性檢查 | P0 | DONE | P2本機核心 | 檔案、來源、注入、隔離及保守品質處理 | 全套與最終runtime已過；保留冷啟／單工／未明歷史例外限制，不宣稱正式安全認證 |
| P3-03A | 3 | 依賴與源碼基本檢查 | P0 | DONE | 鎖定依賴 | 已知漏洞及依賴一致性有證據 | Python33/33、0known／0skip；npm88依賴0；pip check一致，源碼scan無token、原HTML hash一致；[證據](docs/DEPENDENCY_AUDIT.md) |
| P3-04 | 3 | 部署整體驗收 | P1 | BLOCKED | P3-04C | 本機與公開HTTPS分開驗收 | 本機build／runtime DONE；公開主機、網域／DNS及正式授權未提供 |
| P3-04A | 3 | Docker設定與最終image build | P1 | DONE | P2本機核心 | 多階段建置、鎖定依賴與資產 | config exit0；a7e45621… build9.3秒、exit0；完整digest見[容器報告](docs/CONTAINER_ACCEPTANCE.md) |
| P3-04B | 3 | 最終版本本機容器 | P0 | DONE | P3-04A | 真API／OCR、權限、volume及重啟 | HTTPready後首輪新版60checks PASS；UID10001／唯讀／capdrop／無私有檔／重啟同case／刪除404／worker JS再驗過；舊冷啟失敗保留 |
| P3-04C | 3 | 公開HTTPS部署 | P1 | BLOCKED | 主機／網域／授權 | DNS／TLS／Secure cookie／公開E2E | 未正式外部署；本機60checks不代替外部證據 |
| P3-05 | 3 | provider、品質與模擬標示 | P0 | DONE | P2-08 | 不冒充模型辨識或外部驗證 | allskip明示未OCR；mixed依實際provider且uncertain；頁2位置正確；標為初步檢查參考信心，非純平均／整檔準確率；llm_verified=false |
| P3-06 | 3 | 文件、限制及驗收報告 | P0 | DONE | 已有本機證據與外部阻礙 | 重現方式、歷程與續作資訊完整 | README／架構／來源／LLM／展示／限制／容器／依賴與[最終報告](docs/FINAL_ACCEPTANCE.md)齊全，無待執行本機驗收 |
| P3-GATE | 3 | Phase 3／整案最終gate | P0 | BLOCKED | P2-09、P3-04C | 全部必要外部閘門通過 | 真外部LLM與公開HTTPS仍缺依賴；不把本機DONE擴張為整案Completed |

後端185前輪、Mock58/63、API26/27、容器冷啟失敗及後續成功均保留於[最終報告](docs/FINAL_ACCEPTANCE.md)。26/27底層例外在18/18輪替HTTP未復現、原因仍未知；品質前檢並非證明上游cause已根治，列已知限制供後續監測，不再列為當前待跑本機bug。
