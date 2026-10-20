# 續作狀態

更新：2026-10-20（臺灣）。**真實 OpenRouter 語意串接已部署並有成功證據；完整模型流程仍受免費限流與不合規輸出影響，整體 gate 保持 BLOCKED。**

- current_phase：Phase 2／3，語意對話實作完成，完整真模型驗收受阻。
- current_task：LLM-WAIT-20261020 DONE，模型300秒／後端310秒／前端330秒與背景查詢已測試、發布。SEMANTIC-IMPL DONE；SEMANTIC-LIVE／SEMANTIC-20261020 BLOCKED。P2-04／P2-09／P3-04／P3-04C／P3-GATE 仍 BLOCKED；LLM-WAIT-IMAGE BLOCKED（Docker引擎未啟動）。
- last_completed_task：長等待機制、owner隔離／同案防重／取消與過期／條件變更拒舊回覆、既有API相容與短等待狀態文案；本機全回歸與公開部署。詳見[長等待報告](docs/LLM_WAIT.md)。
- last_successful_test：本輪後端544/544（28.96秒，既有Starlette warning1）、前端69/69、三尺寸Mock87/87（2.8分鐘）、三尺寸真API／OCR27/27（2.0分鐘）、受控長等待桌面／手機4/4（22.3秒，虛擬超過126秒），公開啟動檢查15/15。真模型探測1次為限流FAIL，不混入PASS；[證據](docs/llm-wait-20261020/tests.json)。
- api_ocr_evidence：API/OCR27/27（4.1分鐘）在前映像2fa10dde通過；與最終映像前端、規則及OCR相同，只有外部語意cap不同，沒有宣稱27在最終映像再跑。完整版本差異與證據見[報告](docs/SEMANTIC_CONVERSATION.md)。
- real_llm_evidence：前輪提高預算前公開「你好→我出車禍了→沒有住院」三輪真200、非模擬及AI標示通過；改寫「摔車／留院三晚／沒有動刀」真模型成功、候選住院／無手術且不改案。前輪最終程序招呼亦真成功，每次成功均有嚴格零費用與用量驗證。這些是重啟前的歷史證據，本次未呼叫模型。
- failed_tests：本輪公開背景工作POST202後首次GET即failed LLM_RATE_LIMITED，整次6.946秒、未重試、測試案件已刪除，verified=false，[真探測](docs/llm-wait-20261020/public-job.json)。受控RED／離線RED保留。Docker build因dockerDesktopLinuxEngine pipe不存在失敗，未進build步驟。歷史完整live四次分別第4句限流／第1句INVALID／第1句限流／第2句限流，及截斷／引文驗證失敗仍保留，不冒稱根因全部修復。
- current_blockers：指定free路由的容量與輸出品質使完整新模型旅程尚無全程PASS；不改用付費模型、不靜默退Mock／本機，不削弱事實或來源驗證。有限防護不保證所有語意正確，仍須使用者確認類型與條件。
- provider_state：openai_compatible／openrouter/free；實際啟動log確認timeout300.0秒，預設／最高300秒、後端310秒、前端330秒／每3秒短查詢。語意cap4096、文件／generic cap1800及免費／來源驗證不變，無重試／付費fallback。當前configured=true／verified=false；重啟清除後唯一真探測因限流未成功，不以配置成功代替模型驗收。
- public_url：https://tulsa-ppc-message-builders.trycloudflare.com/?service=api 。boots-deaf-found-arrange與其他前輪網址已失效，勿當作仍可用。
- runtime_state：公開8002 parent15036／listener24720；cloudflared36124沿用，網址不變，均隱藏視窗。專用8004回歸程序39384／5072核對清理；5174／5176測試Vite已自清。操作前重新核對CIM與埠，不憑舊PID停止；無關8000／3137服務未操作。
- public_settings：沿用.local/quick-tunnel/cases.sqlite3、單worker／單副本、精確HTTPS origin、Secure／HttpOnly／Strict host-only cookie、no-access-log／no-proxy-headers、rate120；本次公開15項通過，[證據](docs/llm-wait-20261020/startup-smoke.json)。正式資產index-h9YV-k--.js，舊dist已備份；模型驗收spec僅適配新202／GET終態及330秒預算，provider／來源／確認等原業務斷言保留，未降標。
- docker_status：本輪新映像build因Docker Desktop Linux引擎未啟動而BLOCKED，沒有成功的新image。前輪cardif-claim-preparation:semantic-20261020／sha256:7c6afbc949395337cd7ead9bb082b7d6e470a8c31c22878d747a7b1bf32dca12保留，但不包含本輪長等待修正。這次部署與回歸是本機原生8002／8004，不冒稱容器已更新；引擎恢復後才可build及容器驗證。
- secret_state：沿用私有.local/secrets/.env.openrouter、目前使用者ACL、Git／Docker排除；Vite一般／@fs403、後端404。最終只讀key GET顯示usage0、剩餘限制0.1、當日免費請求27/1000；這不代替模型驗收。最終384檔實際key掃描零洩漏；沒有重述key、建立其他provider或提交真理賠。
- external_dependencies：OpenRouter免費容量；Docker Desktop Linux引擎尚未執行；OpenAI／Google AI Studio／Gemini仍依使用者決定暫緩，不再索取或建立。
- data_scope：最新授權允許必要當前描述與最多8則有限同案歷史、最多9則／6000字送OpenRouter；明顯個資盡力遮罩，非全面去識別。原始上傳檔、OCR／擷取全文、分析欄位、cookie、憑證與整案不自動附加。
- saved_evidence：[長等待報告](docs/LLM_WAIT.md)、docs/llm-wait-20261020去敏感JSON與2張受控等待圖；詳細log於.local/llm-wait-20261020與.local/async-message-jobs-20261020，受控UI結果於test-results-message-wait（不入Git）。[原語意報告](docs/SEMANTIC_CONVERSATION.md)及歷史證據保留；原HTML／備份未變。

## 下一個工作階段的三步

1. 讀規範與此狀態，核對8002／隧道／health及300秒設定，保留已部署背景查詢與官方規則隔離；重啟會清除未完成工作，記憶體工作只適用單worker／單副本。
2. 免費容量恢復後，以適配jobs的opt-in live spec重驗完整模型流程：LIVE_OPENROUTER=1、CLAIM_API_BASE_URL及Chrome路徑，desktop／單worker；維持202建立、真GET200 succeeded、provider／來源／確認／費用斷言，失敗保留，不能把設定或歷史verified當全程成功。INVALID重現時僅記安全診斷。
3. Docker Desktop Linux引擎恢復後，build cardif-claim-preparation:llm-wait-20261020，核對source／dist與容器流程；不要將舊semantic映像當成本輪。只有新完整模型成功才更新SEMANTIC-LIVE及P2／P3整體gate，不建立未要求排程或改付費模型。
