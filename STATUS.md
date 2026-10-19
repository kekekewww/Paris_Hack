# 續作狀態

更新：2026-10-20（臺灣）。**真實 OpenRouter 語意串接已部署並有成功證據；完整模型流程仍受免費限流與不合規輸出影響，整體 gate 保持 BLOCKED。**

- current_phase：Phase 2／3，語意對話實作完成，完整真模型驗收受阻。
- current_task：SEMANTIC-IMPL DONE；SEMANTIC-LIVE／SEMANTIC-20261020 BLOCKED。P2-04／P2-09／P3-04／P3-04C／P3-GATE 仍 BLOCKED。
- last_completed_task：真模型招呼、描述、追問與工作區一般補充分流；有界對話及明顯個資遮罩；事實引文／否定／未知檢查；確認才改案；官方需求仍由規則決定；介面隱私告知；部署與紀錄。
- last_successful_test：最終後端477/477（108.76秒，既有Starlette warning1），前端58/58，Mock87/87（3.9分鐘），最終容器雙模式追問12/12（3分鐘），最終公開HTTPS原23/23；三尺寸兩模式目視12圖／6context，console與pageerror0。
- api_ocr_evidence：API/OCR27/27（4.1分鐘）在前映像2fa10dde通過；與最終映像前端、規則及OCR相同，只有外部語意cap不同，沒有宣稱27在最終映像再跑。完整版本差異與證據見[報告](docs/SEMANTIC_CONVERSATION.md)。
- real_llm_evidence：提高預算前公開「你好→我出車禍了→沒有住院」三輪真200、非模擬及AI標示通過；改寫「摔車／留院三晚／沒有動刀」真模型成功、候選住院／無手術且不改案。最終新程序招呼也真成功，建立本程序verified；每次成功均有嚴格零費用與用量驗證。
- failed_tests：完整公開live四次分別第4句限流（54.7秒）、第1句INVALID（19秒）、第1句限流（6.1秒）、最終第2句限流（39.5秒），每輪1 fail及network console1，未改200/provider/引用等斷言。早期私有probe有INVALID／35秒timeout；工作區probe有1800截斷，4096重驗仍因事實引文不合被拒。不是整輪成功，也未證明所有INVALID根因修復。
- current_blockers：指定free路由的容量與輸出品質使完整新模型旅程尚無全程PASS；不改用付費模型、不靜默退Mock／本機，不削弱事實或來源驗證。有限防護不保證所有語意正確，仍須使用者確認類型與條件。
- provider_state：openai_compatible／openrouter/free；語意cap4096，文件／generic cap1800，metadata依當次cap驗證；35秒、免費零價格、無重試／付費fallback均保持。當前程序configured=true／verified=true；verified源自本輪真招呼，只是同程序歷史成功，不是即時容量保證，重啟會清除。
- public_url：https://boots-deaf-found-arrange.trycloudflare.com/?service=api 。前輪retirement-trim網址已停止，勿當作仍可用。
- runtime_state：公開8002 parent9252／listener52212；cloudflared53936指向8002。Vite5174保留。操作前重新核對CIM與埠，不憑舊PID停止；無關8000／3137服務未操作。
- public_settings：沿用.local/quick-tunnel/cases.sqlite3、單worker／單副本、精確新HTTPS origin、Secure／HttpOnly／Strict host-only cookie、no-access-log／no-proxy-headers、rate120；最終原23項已實驗通過。
- docker_status：最終cardif-claim-preparation:semantic-20261020，image sha256:7c6afbc949395337cd7ead9bb082b7d6e470a8c31c22878d747a7b1bf32dca12；UID10001、唯讀、capdropALL及no-new-privileges。adapter／語意／隱私／正式dist已逐檔比對一致。專用paris-semantic-20261020容器與volume已核對清理，image保留，[清理證據](docs/semantic-conversation/cleanup.json)。
- secret_state：沿用私有.local/secrets/.env.openrouter、目前使用者ACL、Git／Docker排除；Vite一般／@fs403、後端404。最終只讀key GET顯示usage0、剩餘限制0.1、當日免費請求27/1000；這不代替模型驗收。最終384檔實際key掃描零洩漏；沒有重述key、建立其他provider或提交真理賠。
- external_dependencies：OpenRouter免費容量；OpenAI／Google AI Studio／Gemini仍依使用者決定暫緩，不再索取或建立。
- data_scope：最新授權允許必要當前描述與最多8則有限同案歷史、最多9則／6000字送OpenRouter；明顯個資盡力遮罩，非全面去識別。原始上傳檔、OCR／擷取全文、分析欄位、cookie、憑證與整案不自動附加。
- saved_evidence：[完整報告](docs/SEMANTIC_CONVERSATION.md)、docs/semantic-conversation去敏感JSON及6張API視覺圖；原始合成測試日誌／RED-GREEN保存在.local/openrouter-conversation-20261020與.local/semantic-20261020（不入Git）。原HTML／備份SHA256仍相同。

## 下一個工作階段的三步

1. 讀規範、TASKS與此狀態；核對程序／source hash／health，保留已部署語意功能與官方規則隔離，不重做已過且未變更的UI／OCR。
2. 免費容量恢復後，以原opt-in live spec重驗完整對話與文件流程。明確設定LIVE_OPENROUTER=1、CLAIM_API_BASE_URL及已安裝Chrome路徑；先跑desktop／單worker，保持真200、provider、引用、確認、費用等斷言，失敗保留，禁止把設定或歷史verified當全程成功。
3. 若INVALID重現，用合成情境記錄安全的schema flags／驗證位置，區分截斷、來源語境與自然措辭；不記原始敏感prompt、不盲改護欄。只有新完整成功後才更新SEMANTIC-LIVE與P2／P3整體gate；不要建立未要求的排程、其他模型或付費路由。
