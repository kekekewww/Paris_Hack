# 開發任務

最新維護：UNCERTAIN-20261020 DONE；不確定重大疾病誤擋已修復、完整請求除錯文件已提供。本次652後端與公開目標2/2、最終映像224hash通過；下方632／完整15回覆3/3為切換當時證據，未冒稱本次重跑。

更新日期：2026-10-20（臺灣）。**指定DeepSeek模型與新key已安全啟用，真模型三尺寸3/3、後端632／前端69、HTTPS23與最終容器驗證全過，Phase 2／3當前原型gate DONE。300秒等待及官方文件規則保留。先前free與本輪失敗皆為歷史證據，不改寫成成功。**

| ID | 階段 | 工作 | 優先 | 狀態 | 相依 | 驗收條件 | 驗證證據／外部依賴 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UNCERTAIN-20261020 | 2／3 | 不確定重大疾病誤擋與完整模型流程除錯 | P0 | DONE | 使用者確切輸入、DeepSeek | 合理不確定重述通過；不推定確診／候選；未知肯定及洗白仍拒；真流程與除錯文件 | 真before舊126行FAIL、初修afterPASS；最終652／相關455／語意79及公開桌面手機2/2過、最終image224hash一致；[完整流程](docs/MODEL_REQUEST_FLOW.md) |
| DEEPSEEK-20261020 | 2／3 | 新金鑰及指定DeepSeek模型切換與驗收 | P0 | DONE | 使用者新授權、US$2／30天金鑰 | 私有保存、精確模型／費用驗證、300秒等待、完整真流程、無洩漏 | 後端632／前端69、公開真模型3/3共15回覆／116.253秒、HTTPS23、最終容器224hash／真問答／restart／安全／清理全過；使用量US$0.031929972；[本輪報告](docs/DEEPSEEK_SETUP.md) |
| LLM-WAIT-20261020 | 2／3 | 五分鐘模型等待與背景對話查詢 | P0 | DONE | 使用者回饋、既有免費模型與Quick Tunnel | 模型300／後端310／前端330秒；短HTTP查詢避開代理期限；隔離、防重、刪除與長等待回歸；更新正式服務 | provider先2 RED後103；全後端544／前端69／Mock87／真API及OCR27／受控長等待4／公開啟動15全部PASS；實際配置300已載入。真探測1次限流FAIL如實保留，未標模型成功；[報告](docs/LLM_WAIT.md) |
| LLM-WAIT-IMAGE | 3 | 長等待版本Docker映像與容器重驗 | P1 | DONE | Docker Desktop Linux引擎 | 新映像source／dist一致並通過容器流程 | 引擎已恢復，deepseek-final-20261020含長等待及語意修正；224hash一致／真job1／restart／安全／cleanup全過。後續docQ修正另待新image；首映像OCR56過，不冒稱delta重跑 |
| OPS-20261020 | 3 | 重新啟動展示伺服器與Quick Tunnel | P0 | DONE | 使用者要求、既有正式dist與私有配置 | 新HTTPS首頁／資產／API正常，安全cookie與案件隔離及清除通過 | 公開啟動檢查15/15；零模型／OCR分析請求，合成案件已刪除；[證據](docs/restart-20261020/smoke.json)，目前網址／PID見[狀態](STATUS.md)；整體模型gate不變 |
| SEMANTIC-20261020 | 2／3 | 語意對話整合與完整驗收 | P0 | DONE | SEMANTIC-IMPL、SEMANTIC-LIVE | 包含真模型的完整新流程通過 | 指定DeepSeek最終三尺寸3/3完整過，四輪語意、獨立確認、官方文件問答、PDF、摘要保存皆真測；先前三輪FAIL保留，未降斷言 |
| SEMANTIC-IMPL | 2／3 | 真模型語意、追問、有限上下文與官方規則隔離 | P0 | DONE | 最新授權、既有免費配置 | 真請求分流、事實及引用驗證、確認才改案、真成功與回歸、部署與紀錄 | 後端477／前端58／Mock87；三句真引導與改寫曾成功，新程序招呼亦真成功；最終容器追問12、公開HTTP23／視覺12圖過；API/OCR27同前端與不變規則profile過 |
| SEMANTIC-LIVE | 2／3 | 最終完整模型旅程及工作區語意重驗 | P0 | DONE | 新授權指定DeepSeek、官方供應商 | 真模型逐輪、候選、確認、官方清單、問答與摘要全程通過 | 單worker／retries0，desktop1440／tablet768／mobile390共15真回覆，3/3（116.253秒）；無橫溢／console／pageerror，案已刪404；[證據](docs/deepseek-20261020/public-final.json) |

更新日期：2026-10-19（臺灣）。主要規範為 `AGENTS.md` 與 `PROJECT_PLAN.md`。**本輪連續追問修復已發布且三尺寸驗證通過；前輪MVP曾完成真模型驗收。新程序真模型重驗仍因上游429受阻，當前P2／P3整體gate重開為BLOCKED，不將歷史成功冒充本輪通過。**

使用者回報的「你好→我出車禍了→沒有住院」重複追問已修復；ASSISTANT-LOOP-20261019 DONE。ASSISTANT-LIVE-20261019受免費供應商限流BLOCKED，原真模型及公開完整斷言保留。

使用者授權的OpenRouter免費路由已啟用；OpenAI／Gemini維持暫緩，兩家可選供應商不阻擋原訂MVP。既有Mock及本機規則保留，各自標示模式，不冒充外部模型。目前結果見[追問修復報告](docs/ASSISTANT_FOLLOWUP.md)，前輪模型連通證據見[歷史報告](docs/OPENROUTER_ACCEPTANCE.md)。

| ID | 階段 | 工作 | 優先 | 狀態 | 相依 | 驗收條件 | 驗證證據／外部依賴 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ASSISTANT-LIVE-20261019 | 2／3 | 真模型／AI標示與公開完整重驗 | P0 | DONE | 原free阻礙由新指定模型授權取代 | 真回覆、引用及AI標示通過 | 舊429保留為歷史；新DeepSeek完整三尺寸3/3及HTTPS23通過，不再要求舊free成功才能交付；[現行驗收](docs/DEEPSEEK_SETUP.md) |
| ASSISTANT-LOOP-20261019 | 1／2／3 | 逐輪追問、回覆來源短標與新舊引導畫面 | P0 | DONE | 使用者確切三句 | 不重問已否定住院、不推定門診；獨立確認才建立；三尺寸與公開回歸 | 後端347／前端56、最終Mock87、API27、最終容器followup12及公開6；三尺寸目視通過；[報告](docs/ASSISTANT_FOLLOWUP.md) |
| P1-01 | 1 | 原型盤點、保留與基準截圖 | P0 | DONE | 無 | 完整檢查與可恢復原設計 | 原1598行HTML、備份與基準截圖；最終原檔／備份SHA再次一致；[盤點](docs/PROTOTYPE_AUDIT.md) |
| P1-02 | 1 | ES Modules、Mock、API Contract | P0 | DONE | P1-01 | 服務可替換、狀態語意分離 | 本輪單元56、Mock87；[契約](docs/API_CONTRACT.md)未變，原20/36等數字為歷史 |
| P1-03 | 1 | 原設計首頁與雙入口 | P0 | DONE | P1-02 | 兩路徑可完整操作 | 三尺寸完整Mock及真API流程通過，品牌與原始設計延續 |
| P1-04 | 1 | 引導、追問、確認與重試 | P0 | DONE | P1-02 | 依已知事實追問，確認才更新 | 本輪雙服務三尺寸12及公開6通過，否定住院不推門診；[本輪修復](docs/ASSISTANT_FOLLOWUP.md) |
| P1-05 | 1 | 類別與條件直接選擇 | P0 | DONE | P1-02 | 三類別可建立案件 | Mock與真API直接選擇、條件更新與摘要通過 |
| P1-06 | 1 | 清單、狀態、來源與助手 | P0 | DONE | P1-04、P1-05 | 狀態可管理、保存，來源可追溯 | 重新整理／清除／收合／來源／人工確認皆經端到端驗證 |
| P1-07 | 1 | 上傳、預覽與Mock分析 | P0 | DONE | P1-06 | 檔案限制、位置與人工確認 | 本輪Mock87與API27回歸；專用PDF2／競態為前輪證據，不冒稱本輪重跑 |
| P1-08 | 1 | 摘要、下載與送件指引 | P0 | DONE | P1-06 | 可下載摘要且不宣稱核准 | 實際讀取下載內容；官方指引由來源服務提供；受控外部故障後仍可用 |
| P1-09 | 1 | 響應式、動畫、鍵盤與狀態 | P0 | DONE | P1-03至08 | 390／768／1440可完成操作 | 最新Mock各29/29、引導／首頁／工作區axe及非預期console／pageerror斷言通過；保留鍵盤、焦點與reduced-motion |
| P1-10 | 1 | Phase 1驗收 | P0 | DONE | P1-09 | 通過才開後端 | 原63及20通過後開後端；本輪最終Mock87／1.8分鐘，雙服務三尺寸追問12及公開6；[原閘門](docs/PHASE1_ACCEPTANCE.md)與[本輪修復](docs/ASSISTANT_FOLLOWUP.md) |
| P2-01 | 2 | FastAPI、模型、錯誤與健康檢查 | P0 | DONE | P1-10 | 本機契約與真HTTP可驗 | 本輪後端347、真API27及最終追問容器12；core49／190／293等為歷史 |
| P2-02 | 2 | 官方來源registry | P0 | DONE | P1-10 | URL／版本／頁碼／引用可追溯 | 11來源、9文件、22規則、8知識；來源及host一致；[來源紀錄](docs/OFFICIAL_SOURCES.md) |
| P2-03 | 2 | 三類文件規則引擎 | P0 | DONE | P2-02 | 條件式／unknown不誤判免附 | core49、全190與真API條件更新通過；review_required仍人工確認 |
| P2-04 | 2 | 當前版本／程序真實外部LLM重驗 | P0 | DONE | 指定DeepSeek、官方來源 | 真模型成功、引用及AI標示 | 新程序真語意／證據請求及公開3/3，精確model／cost／用量／引用驗證，非模擬；不以key或health替代 |
| P2-04A | 2 | LLM client／傳輸邊界 | P0 | DONE | P2-01、P2-05 | 結構、來源、逾時與錯誤處理 | 本輪AI489／全後端632；含paid/free費用／model白名單、300秒、遮罩query／generic不變及安全拒絕logging |
| P2-05 | 2 | 官方RAG／引用／無依據處理 | P0 | DONE | P2-02 | 真本機檢索與保守回答 | AI113、全190與真HTTP通過；grounded_rules不是生成式LLM |
| P2-06 | 2 | 真PDF／圖片OCR與品質前檢 | P0 | DONE | P2-01 | 品質、欄位、逐頁位置及真HTTP | 本輪後端347、API27無OCR失敗；原28／60／56smoke為歷史，未明例外仍列限制 |
| P2-07 | 2 | owner隔離、保存、刪除與隱私 | P0 | DONE | P2-01 | 24h TTL、不存raw、正確清除 | core49、全190、真API／容器隔離與刪除404；只支援單worker／單副本 |
| P2-08 | 2 | 本機HTTP／PDF預覽整合 | P0 | DONE | P2本機核心 | grounded_rules＋實際OCR端到端 | 本輪同版backend/UI真API27／1.7分鐘與最終雙服務追問12通過；外部模型另列阻礙 |
| P2-09 | 2 | 當前版本Phase 2整體重驗 | P0 | DONE | P2-04、本機核心 | 包含真模型的當前原型gate | 新模型三尺寸3/3＋632後端、真PDF流程／首映像OCR56、不變規則來源與既有API/OCR27差異證據；[報告](docs/DEEPSEEK_SETUP.md) |
| P3-01 | 3 | 整合、回歸與安全測試 | P0 | DONE | P2核心及P2-04 | 真模型及實際流程、失敗恢復 | 本輪後端632／前端69／公開真模型3／HTTPS23／容器真問答1／OCR56；歷史Mock87／API27／受控長等待4不冒稱重跑 |
| P3-02 | 3 | A–H合成展示與mixed情境 | P1 | DONE | P2-08 | 本機流程、缺漏／模糊／無來源／受控故障 | 9合成檔、原8檔hash未變；G1證明PDF受控失敗後案件摘要可用；不代表官方真故障 |
| P3-03 | 3 | 本機安全與可靠性檢查 | P0 | DONE | P2本機核心 | 檔案、來源、注入、隔離及保守品質處理 | 全套與最終runtime已過；保留冷啟／單工／未明歷史例外限制，不宣稱正式安全認證 |
| P3-03A | 3 | 依賴與源碼基本檢查 | P0 | DONE | 鎖定依賴 | 已知漏洞及依賴一致性有證據 | Python33/33、0known／0skip；npm88依賴0；pip check一致，源碼scan無token、原HTML hash一致；[證據](docs/DEPENDENCY_AUDIT.md) |
| P3-04 | 3 | 當前臨時HTTPS完整重驗 | P1 | DONE | P3-04C | 包含真模型的公開完整原斷言 | 最終三尺寸3/3與HTTPS23全過，精確URL／cookie／隔離／清除，臨時展示範圍；固定部署不在此gate |
| P3-04A | 3 | 新模型Docker設定與映像 | P1 | DONE | 最終source freeze | 真build、前後端產物一致 | deepseek-query-20261020／image3ea3b760…，backend17＋dist207共224hash與host一致；原生與容器皆預設API |
| P3-04B | 3 | 新模型容器／API／OCR回歸 | P0 | DONE | P3-04A | 真API/OCR、問答及持久性 | 首映像OCR56／5秒；最終delta真問答1／2.031秒、完整官方段落／source頁碼、案不變、restart／安全／cleanup皆過；OCR未變不假稱重跑 |
| P3-04C | 3 | 公開HTTPS當前完整重驗 | P1 | DONE | P2-04 | 原真模型verified及安全套件 | 最終同程序真模型3/3、原HTTP23全過；未降低verified=true或欄位／簽名品質斷言，早跑FAIL保留 |
| P3-05 | 3 | provider、品質與模擬標示 | P0 | DONE | P2-08 | 不冒充模型辨識或外部驗證 | Mock、grounded_rules與外部provider各自標示；verified只在同配置真成功後成立、重啟清除，不是即時readiness；OCR仍初檢非核准 |
| P3-06 | 3 | 文件、限制及驗收報告 | P0 | DONE | 本輪終驗及掃描 | 可接續紀錄、真實證據與限制完整 | 本輪DeepSeek報告／去敏感JSON、TASKS／STATUS／DECISIONS與契約／README更新；原FAIL及歷史證據保留 |
| P3-GATE | 3 | 當前版本最終原型gate | P0 | DONE | P2-09、P3-04C | 不放寬模型／公開／來源必要斷言 | 指定模型3/3、HTTPS23、後端632／前端69與最終容器hash／真問答／重啟／安全全過；不宣稱正式保險服務或常駐部署 |
| OPS-20261019 | 3 | 重新啟動展示伺服器與Quick Tunnel | P0 | DONE | 使用者要求、現有建置 | 新HTTPS首頁／API、案件隔離及實際OCR流程 | HTTP11項＋公開桌面門診1/1（18.1秒）；console0，測試案件已清除；新網址與程序見[續作狀態](STATUS.md) |
| UX-20261019 | 1／3 | 減少文字與視覺雜訊、突出下一步 | P0 | DONE | 既有前後端 | 漸進揭露、三尺寸視覺／Mock／API回歸、誠實模式與來源 | 單元33/33、Mock75/75、PDF2/2、API27/27、G1/1；公開HTTP22及瀏覽器3/3；三尺寸截圖與文字量測、axe／console均通過；[完整紀錄](docs/UI_SIMPLIFICATION.md) |
| KEY-20261019 | 2 | 三家供應商設定預留與保護檢查（歷史） | P1 | DONE | 當時使用者暫緩建立金鑰 | 當時空白欄位與建置保護 | 當時三家key空白，合成值掃207檔零洩漏，runtime為grounded_rules／false／false；新授權後OpenRouter已啟用／真驗，範本仍無key；[現況](docs/PROVIDER_SETUP.md) |
| KEY-CREDENTIALS | 2 | 可選其他供應商真實金鑰 | P1 | BLOCKED | 使用者稍後安排 | OpenAI／Gemini安全配置與各自真驗 | OpenRouter安全保存與實際啟用已完成；OpenAI／Gemini仍依使用者決定暫緩，不阻擋MVP |
| ACC-20261019 | 1／2／3 | 不含外部LLM的完整重驗收 | P0 | DONE | 既有原型 | 後端／前端／真API／OCR／來源／安全與部署證據完整 | 後端190／前端33／Mock75／API27／PDF2／G1；公開HTTP22及browser3、容器60及browser1與restart一致；來源11／依賴重掃通過；[完整證據](docs/ACCEPTANCE_NO_KEYS_20261019.md) |
| GUIDED-20261019 | 1／3 | 引導候選先選取、再獨立建立清單 | P0 | DONE | 使用者回饋、既有guided契約 | 類型具名且不預選、點選不寫案、獨立建立、改選／重述／重試／reload安全、三尺寸與真API驗證 | 單元36、target9、Mock87／三尺寸目視、PDF2、真API27、G1、公開HTTP23／browser3與新Docker60／browser1／restart全部通過；[完整紀錄](docs/GUIDED_CHOICE.md) |
| OPENROUTER-20261019 | 2／3 | OpenRouter免費路由安全設定、實際串接與完整驗收 | P0 | DONE | 使用者授權、提供金鑰及openrouter/free | 後端保存、免費護欄、真網站／容器／公開及回歸 | backend293／OpenRouter103、前端36、本機兩尺寸首次成功＋平板重驗、容器56及live1／restart、公開live1及HTTP23；key實GET使用量0；[全部證據](docs/OPENROUTER_ACCEPTANCE.md) |

後端185前輪、Mock58/63、API26/27、容器冷啟失敗及後續成功均保留於[最終報告](docs/FINAL_ACCEPTANCE.md)。26/27底層例外在18/18輪替HTTP未復現、原因仍未知；品質前檢並非證明上游cause已根治，列已知限制供後續監測，不再列為當前待跑本機bug。
