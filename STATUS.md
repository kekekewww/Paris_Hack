# 續作狀態

更新：2026-10-23（臺灣）。**依使用者要求恢復伺服器與新Quick Tunnel，公開啟動15項全過。** 本次只重啟，產品程式／模型設定未變，沒有呼叫模型或OCR分析；652後端與目標2/2為前輪修正證據，未重跑。

- current_phase：Phase 3維護交付完成，展示服務保持運作。
- current_task：OPS-20261023 DONE；UNCERTAIN-20261020及原切換任務DONE保留，沒有新功能實作。OpenAI／Gemini仍依使用者決定暫緩。
- last_completed_task：核對8002及其隧道皆已停止，恢復隱藏程序、精確新origin／Secure cookie、原模型／300秒與案件庫，公開15項通過並更新連結。
- last_successful_test：本次首頁、JS/CSS、API、模型配置、OCR配置、安全cookie、私有路徑404、合成案規則／owner隔離／清除15/15 PASS；model_requests=0／ocr_analysis_requests=0，測試案已刪除。[本次證據](docs/restart-20261023/smoke.json)
- last_feature_tests：前輪全後端652/652（35.91秒）、相關五檔455／語意79、公開目標2/2（27.922秒、2真job）與最終映像224hash一致；本次重啟未重跑。[修正紀錄](docs/MODEL_REQUEST_FLOW.md)
- current_blockers：沒有本輪必要外部阻礙；初次瀏覽器自動審核因授權證據不足拒絕，補既有人類授權後同腳本／同目的地重審獲允許，沒有繞過。有限詞彙與語意驗證仍不能保證全面語言正確。
- final_live_evidence：本次只跑原句桌面／手機各一真UI工作，非模擬clarification、AI標示、成功messages2、無候選／updates／type／docs／PATCH、無肯定診斷、console／pageerror0、無橫溢、兩案DELETE200／GET404。上一輪完整PDF／官方問答／摘要15回覆三尺寸3/3另保留歷史，未重跑。
- failed_tests：首次付費Relace shared-pool429後固定DeepSeek；首輪三尺寸第4句INVALID、第二輪平板／手機第2句INVALID均prompt-only修復，validator未放寬；第三輪平板docQ合法但不切題，補必要遮罩query；第四輪3/3成功。首映像hash因native預設Mock／container API失敗，API重建後224檔一致。HTTP先跑於重啟未生成時verified失敗，原斷言後23過。誤用系統python缺httpx／pytest已改專案.venv，不算產品PASS。原FAIL均保留。
- current_failed_evidence：本次同句真HTTP200後於舊126行FAIL，3個合法不確定重述RED；初修覆核另2個肺癌附加負例RED。最終全652及UI2過，原FAIL與初修650／真after僅作階段證據，不冒稱最終source。無原始模型回覆日誌。
- provider_state：openai_compatible／deepseek/deepseek-v4.1-flash-1017；actual只接受原名或canonical deepseek/deepseek-v4.1-flash-20261017。paid only=["deepseek"]、low effort、無自動重試／fallback；單價cap每百萬token輸入US$0.30／輸出1.20，request/image固定費率0，回應cost有限0–US$0.05是事後檢查，不是退款或硬停。
- wait_state：模型300秒／後端310秒／網頁330秒；單POST202＋每3秒短GET，原owner隔離／容量／同案防重／刪除／TTL／shutdown／條件變更護欄保持。一般HTTP15秒、分析95秒不變。
- key_state：上一輪切換結束時官方GET /key 200，上限US$2、usage US$0.031929972、remaining US$1.968070028，到期2026-11-19T07:57:36.297Z（臺灣15:57）。僅回報當時快照，沒有變更額度或帳號；秘密只存私有.local/secrets/.env.openrouter，owner ACL／Git及Docker排除，無前端／argv／Git金鑰。
- final_checks：本次440檔實際新key／完整憑證格式掃描零命中，298個本地連結無缺漏，證據在docs/uncertain-dialogue-20261020/tests.json。原HTML與dist未更動；前輪432／279為歷史數字。
- public_url：https://develops-functionality-purchases-extreme.trycloudflare.com/?service=api 。先前Quick Tunnel網址不再作為當前連結；Quick Tunnel網址及存活無保證，電腦與程序需保持執行。
- runtime_state：公開8002 parent16576／listener20584、專案cloudflared25484；操作前重新核對CIM與埠。沿用.local/quick-tunnel/cases.sqlite3、精確新origin、安全cookie、單worker／rate120／no-access-log／no-proxy-headers，未動無關8000／3137或其隧道。當前安全log .local/restart-20261023/app.stderr.log。新host使用獨立cookie，沿用DB不表示舊host案件會自動出現在新host。
- restart_model_state：configured=true／verified=false；啟動log確認精確DeepSeek模型與timeout300.0。重啟重設verified是既有語意，本次未用模型呼叫重新建立，不把配置成功當真模型重驗。
- asset_state：API預設index-CecfFZZO.js，dist/index.html SHA256 367f009ea264cd3a33afee5eafa8051af12f5ad4587554a6f124c766c96e0fba；JS d96a9547ba73437d10262f92938fe7c29b0bd37ac337753d4de8839f8f9c5762。原dist已備份，舊assets保留給舊分頁。
- docker_state：最終cardif-claim-preparation:uncertain-safe-20261020／sha256:a54e187ac8158ef0e80c99b3f9fd156b38a9e941fa1bac464d65d07fa606a74f，實build及backend17＋dist207共224hash一致；.local空、無env/db。離線run --rm無網路／secret／模型，已清除。runtime安全／OCR／持久性為不變設定的上一輪證據，本次未重跑。
- data_scope：必要描述／最多8則有限歷史，合計最多9則／6000字；文件問答只用本次遮罩query（1–4000字）與公開官方證據，不帶history／完整案／原始上傳檔／OCR／分析欄位／cookie／key。遮罩非全面去識別。文件需求仍由官方規則決定，獨立確認才建立清單。
- design_state：原始HTML及備份SHA256皆59a6fd5053e9811560823b3f12637ef0c7bbe7f3aa2fd9a1abe1ea90fad1c8a1；版型／CSS／官方來源規則未變。Mock保留。前輪Mock87／API及OCR27／受控長等待4為不變部分歷史差異證據，不當作本輪重跑。
- known_limits：單worker／記憶體job，重啟會清除工作；有限語意／PII處理非全面正確性證明；歷史OCR底層例外根因未明，保留監測限制；不驗保單資格／金額，不正式核准或送件。[完整限制](docs/KNOWN_LIMITATIONS.md)
- saved_evidence：本次[重啟15項](docs/restart-20261023/smoke.json)，程序／隧道log在.local/restart-20261023；前輪[完整模型流程與修正](docs/MODEL_REQUEST_FLOW.md)及安全JSON保留，不改寫歷史驗收。

## 後續維護的三步

1. 需要再操作時先讀規範及此狀態、核對8002／隧道／health；重啟後verified必須由新真請求建立，不套用舊程序成功。
2. 使用合成資料觀察新模型容量／語意及OCR品質；有具體失敗先定位，維持現有強斷言、官方規則／費用界限與真實模式標示。
3. 到期前依使用者後續授權更換key；若需固定部署、其他provider或新功能另依明確需求處理。每次變更後更新測試／TASKS／STATUS／DECISIONS，不建立未要求排程。
