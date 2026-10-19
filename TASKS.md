# 開發任務

更新日期：2026-10-19（臺灣）。主要規範為 `AGENTS.md` 與 `PROJECT_PLAN.md`。**新版UI已發布，後續不含外部LLM的完整重驗收亦通過。三家金鑰依最新決定暫不建立，整案仍因真外部LLM維持BLOCKED。** DONE 僅限表列範圍，不代表外部閘門已通過。

使用者已選擇「先完成其餘工作，金鑰稍後設定」。介面減量及本次「先選類型、再建立」修正均已驗收發布；不再次索取金鑰，不以本機規則、Mock 或離線 transport 代替真實供應商驗證。

| ID | 階段 | 工作 | 優先 | 狀態 | 相依 | 驗收條件 | 驗證證據／外部依賴 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1-01 | 1 | 原型盤點、保留與基準截圖 | P0 | DONE | 無 | 完整檢查與可恢復原設計 | 原1598行HTML、備份與基準截圖；最終原檔／備份SHA再次一致；[盤點](docs/PROTOTYPE_AUDIT.md) |
| P1-02 | 1 | ES Modules、Mock、API Contract | P0 | DONE | P1-01 | 服務可替換、狀態語意分離 | 原Phase1單元20/20；最新單元36/36、Mock87/87；[契約](docs/API_CONTRACT.md)不變 |
| P1-03 | 1 | 原設計首頁與雙入口 | P0 | DONE | P1-02 | 兩路徑可完整操作 | 三尺寸完整Mock及真API流程通過，品牌與原始設計延續 |
| P1-04 | 1 | 引導、追問、確認與重試 | P0 | DONE | P1-02 | 不確定先追問，確認才更新 | 最新三尺寸先選再建立、改選不寫案、重述清選取、重試及reload回歸通過；[引導修正](docs/GUIDED_CHOICE.md) |
| P1-05 | 1 | 類別與條件直接選擇 | P0 | DONE | P1-02 | 三類別可建立案件 | Mock與真API直接選擇、條件更新與摘要通過 |
| P1-06 | 1 | 清單、狀態、來源與助手 | P0 | DONE | P1-04、P1-05 | 狀態可管理、保存，來源可追溯 | 重新整理／清除／收合／來源／人工確認皆經端到端驗證 |
| P1-07 | 1 | 上傳、預覽與Mock分析 | P0 | DONE | P1-06 | 檔案限制、位置與人工確認 | 最新Mock87、PDF2與競態回歸通過；真分析另列P2-06 |
| P1-08 | 1 | 摘要、下載與送件指引 | P0 | DONE | P1-06 | 可下載摘要且不宣稱核准 | 實際讀取下載內容；官方指引由來源服務提供；受控外部故障後仍可用 |
| P1-09 | 1 | 響應式、動畫、鍵盤與狀態 | P0 | DONE | P1-03至08 | 390／768／1440可完成操作 | 最新Mock各29/29、引導／首頁／工作區axe及非預期console／pageerror斷言通過；保留鍵盤、焦點與reduced-motion |
| P1-10 | 1 | Phase 1驗收 | P0 | DONE | P1-09 | 通過才開後端 | 原63/63及20/20通過後開後端；最新Mock87/87、1.9分鐘；[原閘門](docs/PHASE1_ACCEPTANCE.md)與[最新修正](docs/GUIDED_CHOICE.md) |
| P2-01 | 2 | FastAPI、模型、錯誤與健康檢查 | P0 | DONE | P1-10 | 本機契約與真HTTP可驗 | core49、新整套190/190與真API27/27；一般展示服務亦60checks PASS |
| P2-02 | 2 | 官方來源registry | P0 | DONE | P1-10 | URL／版本／頁碼／引用可追溯 | 11來源、9文件、22規則、8知識；來源及host一致；[來源紀錄](docs/OFFICIAL_SOURCES.md) |
| P2-03 | 2 | 三類文件規則引擎 | P0 | DONE | P2-02 | 條件式／unknown不誤判免附 | core49、全190與真API條件更新通過；review_required仍人工確認 |
| P2-04 | 2 | 真實外部LLM驗證 | P0 | BLOCKED | 後端安全配置與授權 | 真provider request、引用及失敗恢復 | 使用者金鑰稍後設定；未執行真模型請求，llm_verified=false，不能以離線113項代替 |
| P2-04A | 2 | LLM client／離線傳輸邊界 | P0 | DONE | P2-01、P2-05 | 結構、來源、逾時與錯誤處理 | AI113及整套190通過；外部client已實作、未真驗；[LLM說明](docs/LLM_INTEGRATION.md) |
| P2-05 | 2 | 官方RAG／引用／無依據處理 | P0 | DONE | P2-02 | 真本機檢索與保守回答 | AI113、全190與真HTTP通過；grounded_rules不是生成式LLM |
| P2-06 | 2 | 真PDF／圖片OCR與品質前檢 | P0 | DONE | P2-01 | 品質、欄位、逐頁位置及真HTTP | OCR28/28（29.44秒）、全190/190、品質6/6、API27/27、最終image60checks；歷史未明例外列known limitation |
| P2-07 | 2 | owner隔離、保存、刪除與隱私 | P0 | DONE | P2-01 | 24h TTL、不存raw、正確清除 | core49、全190、真API／容器隔離與刪除404；只支援單worker／單副本 |
| P2-08 | 2 | 本機HTTP／PDF預覽整合 | P0 | DONE | P2本機核心 | grounded_rules＋實際OCR端到端 | 最新API27/27、1.9分鐘、各9/9，選取期間0 PATCH／analysis、獨立建立才1次正確PATCH；Mock87／PDF2／G1與真OCR回歸通過 |
| P2-09 | 2 | Phase 2整體驗收 | P0 | BLOCKED | P2-04 | 包含真外部LLM的全部閘門 | 本機部分已驗收；尚缺真provider驗證及其整合實測，不自動標完成 |
| P3-01 | 3 | 本機整合、回歸與安全測試 | P0 | DONE | P2本機核心、P2-08 | 本機實際流程與失敗恢復 | 最新前端36、API27、Mock87、PDF2、G1、公開HTTP23及容器60checks通過；後端190為未改範圍前輪證據 |
| P3-02 | 3 | A–H合成展示與mixed情境 | P1 | DONE | P2-08 | 本機流程、缺漏／模糊／無來源／受控故障 | 9合成檔、原8檔hash未變；G1證明PDF受控失敗後案件摘要可用；不代表官方真故障 |
| P3-03 | 3 | 本機安全與可靠性檢查 | P0 | DONE | P2本機核心 | 檔案、來源、注入、隔離及保守品質處理 | 全套與最終runtime已過；保留冷啟／單工／未明歷史例外限制，不宣稱正式安全認證 |
| P3-03A | 3 | 依賴與源碼基本檢查 | P0 | DONE | 鎖定依賴 | 已知漏洞及依賴一致性有證據 | Python33/33、0known／0skip；npm88依賴0；pip check一致，源碼scan無token、原HTML hash一致；[證據](docs/DEPENDENCY_AUDIT.md) |
| P3-04 | 3 | 臨時HTTPS展示部署驗收 | P1 | DONE | P3-04A至C | 本機及公開HTTPS展示實測 | 最新公開HTTP23及瀏覽器3/3（51.6秒）通過；[引導驗收](docs/GUIDED_CHOICE.md)與[歷史紀錄](docs/QUICK_TUNNEL.md) |
| P3-04A | 3 | Docker設定與最終image build | P1 | DONE | P2本機核心 | 多階段建置、鎖定依賴與資產 | 新版guided-20261019 image 83807998…實際build exit0；完整digest及歷史見[容器報告](docs/CONTAINER_ACCEPTANCE.md) |
| P3-04B | 3 | 最終版本本機容器 | P0 | DONE | P3-04A | 真API／OCR、權限、volume及重啟 | 新映像60checks與引導browser1/1（11.3秒）、真restart同case及刪除404通過，UID10001／唯讀／capdrop／無私有檔；專用容器與volume已清 |
| P3-04C | 3 | Quick Tunnel公開HTTPS展示 | P1 | DONE | P3-04B、使用者本輪授權 | TLS、Secure cookie、origin、隔離與公開流程 | 最新23checks、桌面3/3（51.6秒）、選類型至摘要及真OCR／PDF通過；非固定網址或常駐部署 |
| P3-05 | 3 | provider、品質與模擬標示 | P0 | DONE | P2-08 | 不冒充模型辨識或外部驗證 | allskip明示未OCR；mixed依實際provider且uncertain；頁2位置正確；標為初步檢查參考信心，非純平均／整檔準確率；llm_verified=false |
| P3-06 | 3 | 文件、限制及驗收報告 | P0 | DONE | 已有本機證據與外部阻礙 | 重現方式、歷程與續作資訊完整 | README／架構／來源／LLM／展示／限制／容器／依賴與[最終報告](docs/FINAL_ACCEPTANCE.md)齊全，無待執行本機驗收 |
| P3-GATE | 3 | Phase 3／整案最終gate | P0 | BLOCKED | P2-09 | 包含真外部LLM的全部必要整體gate | 臨時HTTPS已驗證；真外部LLM仍待使用者稍後配置，整案不標Completed |
| OPS-20261019 | 3 | 重新啟動展示伺服器與Quick Tunnel | P0 | DONE | 使用者要求、現有建置 | 新HTTPS首頁／API、案件隔離及實際OCR流程 | HTTP11項＋公開桌面門診1/1（18.1秒）；console0，測試案件已清除；新網址與程序見[續作狀態](STATUS.md) |
| UX-20261019 | 1／3 | 減少文字與視覺雜訊、突出下一步 | P0 | DONE | 既有前後端 | 漸進揭露、三尺寸視覺／Mock／API回歸、誠實模式與來源 | 單元33/33、Mock75/75、PDF2/2、API27/27、G1/1；公開HTTP22及瀏覽器3/3；三尺寸截圖與文字量測、axe／console均通過；[完整紀錄](docs/UI_SIMPLIFICATION.md) |
| KEY-20261019 | 2 | 三家供應商設定預留與保護檢查 | P1 | DONE | 使用者暫緩建立金鑰 | 空白欄位、不啟用模型、不洩漏至建置／公開介面 | 三家key空白；build四合成值掃207檔零洩漏，runtime仍grounded_rules／configured=false／verified=false；[狀態](docs/PROVIDER_SETUP.md) |
| KEY-CREDENTIALS | 2 | 安全取得及保存三家真實金鑰 | P1 | BLOCKED | 使用者稍後安排 | 安全確認目的地、後端保存且不曝露值 | 最新回覆「暫不建立金鑰」；本輪不開建立流程、不寫secret、不呼叫模型 |
| ACC-20261019 | 1／2／3 | 不含外部LLM的完整重驗收 | P0 | DONE | 既有原型 | 後端／前端／真API／OCR／來源／安全與部署證據完整 | 後端190／前端33／Mock75／API27／PDF2／G1；公開HTTP22及browser3、容器60及browser1與restart一致；來源11／依賴重掃通過；[完整證據](docs/ACCEPTANCE_NO_KEYS_20261019.md) |
| GUIDED-20261019 | 1／3 | 引導候選先選取、再獨立建立清單 | P0 | DONE | 使用者回饋、既有guided契約 | 類型具名且不預選、點選不寫案、獨立建立、改選／重述／重試／reload安全、三尺寸與真API驗證 | 單元36、target9、Mock87／三尺寸目視、PDF2、真API27、G1、公開HTTP23／browser3與新Docker60／browser1／restart全部通過；[完整紀錄](docs/GUIDED_CHOICE.md) |

後端185前輪、Mock58/63、API26/27、容器冷啟失敗及後續成功均保留於[最終報告](docs/FINAL_ACCEPTANCE.md)。26/27底層例外在18/18輪替HTTP未復現、原因仍未知；品質前檢並非證明上游cause已根治，列已知限制供後續監測，不再列為當前待跑本機bug。
