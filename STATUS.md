# 續作狀態

更新：2026-10-20（臺灣）。**指定DeepSeek模型與新OpenRouter金鑰已啟用並通過驗收；Phase 1、2、3原型gate均DONE。** 不代表正式保險服務、固定部署或所有可能語意已全面驗證。

- current_phase：Phase 3交付完成，展示服務保持運作。
- current_task：DEEPSEEK-20261020／SEMANTIC-LIVE／P2-09／P3-GATE DONE；沒有待修的必要本輪任務。OpenAI／Gemini依使用者決定暫緩，屬可選外部依賴。
- last_completed_task：新key／指定模型、官方DeepSeek路由、獨立事實及提問優先提示、文件問題query修復、同版部署／容器與全流程驗收、證據及續作紀錄。
- last_successful_test：後端632/632（65.48秒，既有Starlette warning1）、相關AI489/489（5.67秒）、前端69/69。公開桌面1440／平板768／手機390單次3/3（116.253秒），15個真模型回覆；HTTPS23全過。[本輪報告](docs/DEEPSEEK_SETUP.md)
- current_blockers：沒有本輪必要阻礙。前輪free容量與Docker未開已由新授權及引擎恢復取代；OpenAI／Gemini不再索取金鑰。正式商用安全、固定網域與常駐運維不屬原型gate。
- final_live_evidence：四輪語意／每輪真provider非模擬及AI短標、候選前不寫案、獨立確認、官方規則／完整來源及頁碼、申請書欄位／簽名完整段落、受控故障恢復、真PDF文字／canvas、人工覆核、摘要下載／reload、三案DELETE後404皆過；console／pageerror零，page/dialog無水平溢出。原斷言及retries0保持。
- failed_tests：首次付費Relace shared-pool429後固定DeepSeek；首輪三尺寸第4句INVALID、第二輪平板／手機第2句INVALID均prompt-only修復，validator未放寬；第三輪平板docQ合法但不切題，補必要遮罩query；第四輪3/3成功。首映像hash因native預設Mock／container API失敗，API重建後224檔一致。HTTP先跑於重啟未生成時verified失敗，原斷言後23過。誤用系統python缺httpx／pytest已改專案.venv，不算產品PASS。原FAIL均保留。
- provider_state：openai_compatible／deepseek/deepseek-v4.1-flash-1017；actual只接受原名或canonical deepseek/deepseek-v4.1-flash-20261017。paid only=["deepseek"]、low effort、無自動重試／fallback；單價cap每百萬token輸入US$0.30／輸出1.20，request/image固定費率0，回應cost有限0–US$0.05是事後檢查，不是退款或硬停。
- wait_state：模型300秒／後端310秒／網頁330秒；單POST202＋每3秒短GET，原owner隔離／容量／同案防重／刪除／TTL／shutdown／條件變更護欄保持。一般HTTP15秒、分析95秒不變。
- key_state：最終官方GET /key 200，上限US$2、usage US$0.031929972、remaining US$1.968070028，到期2026-11-19T07:57:36.297Z（臺灣15:57）。僅回報當時快照，沒有變更額度或帳號；秘密只存私有.local/secrets/.env.openrouter，owner ACL／Git及Docker排除，無前端／argv／Git金鑰。
- final_checks：432檔實際新key與完整憑證格式掃描零命中，279文件連結無缺漏；原HTML與備份hash一致。安全證據僅檔案數／flags，不保存秘密值或對話。
- public_url：https://tulsa-ppc-message-builders.trycloudflare.com/?service=api 。Chrome已確認不帶query根網址也預設API；Quick Tunnel網址及存活無保證，電腦與程序需保持執行。
- runtime_state：8002 parent43912／listener41608、cloudflared36124；操作前重新核對CIM與埠。沿用.local/quick-tunnel/cases.sqlite3、精確origin、安全Secure/HttpOnly/Strict host-only cookie、單worker／單副本、rate120、no-access-log／no-proxy-headers。未動無關8000／3137，測試8005已清理。
- asset_state：API預設index-CecfFZZO.js，dist/index.html SHA256 367f009ea264cd3a33afee5eafa8051af12f5ad4587554a6f124c766c96e0fba；JS d96a9547ba73437d10262f92938fe7c29b0bd37ac337753d4de8839f8f9c5762。原dist已備份，舊assets保留給舊分頁。
- docker_state：engine29.8.1；最終cardif-claim-preparation:deepseek-query-20261020／sha256:3ea3b760219cb1095fa56a64f0d73f3b953ca53ace9606ebc3c35712882af700。backend17＋dist207共224hash一致；真文件問答1（2.031秒）／canonical來源／案不變、restart exactcase／舊job404／verified重設、安全runtime／cleanup全過。首映像OCR56／5秒過；最終delta未重跑不變OCR，沒有冒稱。
- data_scope：必要描述／最多8則有限歷史，合計最多9則／6000字；文件問答只用本次遮罩query（1–4000字）與公開官方證據，不帶history／完整案／原始上傳檔／OCR／分析欄位／cookie／key。遮罩非全面去識別。文件需求仍由官方規則決定，獨立確認才建立清單。
- design_state：原始HTML及備份SHA256皆59a6fd5053e9811560823b3f12637ef0c7bbe7f3aa2fd9a1abe1ea90fad1c8a1；版型／CSS／官方來源規則未變。Mock保留。前輪Mock87／API及OCR27／受控長等待4為不變部分歷史差異證據，不當作本輪重跑。
- known_limits：單worker／記憶體job，重啟會清除工作；有限語意／PII處理非全面正確性證明；歷史OCR底層例外根因未明，保留監測限制；不驗保單資格／金額，不正式核准或送件。[完整限制](docs/KNOWN_LIMITATIONS.md)
- saved_evidence：[DeepSeek完整報告](docs/DEEPSEEK_SETUP.md)、docs/deepseek-20261020去敏感JSON；全部失敗／測試／容器log在.local/deepseek-20261020及.local/paid-openrouter-20261021（忽略Git），真對話trace／video／截圖停用。

## 後續維護的三步

1. 需要再操作時先讀規範及此狀態、核對8002／隧道／health；重啟後verified必須由新真請求建立，不套用舊程序成功。
2. 使用合成資料觀察新模型容量／語意及OCR品質；有具體失敗先定位，維持現有強斷言、官方規則／費用界限與真實模式標示。
3. 到期前依使用者後續授權更換key；若需固定部署、其他provider或新功能另依明確需求處理。每次變更後更新測試／TASKS／STATUS／DECISIONS，不建立未要求排程。
