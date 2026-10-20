# DeepSeek 模型與金鑰切換

> 後續維護：使用者另回報不確定重大疾病措辭被語意規則誤擋，已修正並發布；新增全後端652與公開目標2/2通過，見[完整模型流程及本次修復](MODEL_REQUEST_FLOW.md)。本頁632／三尺寸3/3／原映像為切換當時的歷史證據，不代替後續修正驗收。

更新：2026-10-20（臺灣）。使用者提供新OpenRouter key，指定 `deepseek/deepseek-v4.1-flash-1017`，此授權取代之前只能使用free的限制。秘密值不在本文、前端、Git、argv、映像或日誌；只更新既有私有後端設定，沒有建立或變更帳號／金鑰額度。

**指定模型已部署並通過原型驗收。** 最終後端632、前端69、公開真模型三尺寸3/3（116.253秒、15個真回覆）、HTTPS23，以及最終容器真模型／224檔一致／重啟／安全與清理全部通過。Phase 2／3當前原型gate結案，舊失敗保留；不將此結果擴張為正式保險服務驗收。

| 項目 | 實際配置與驗證 |
| --- | --- |
| 模型 | requested精確為deepseek/deepseek-v4.1-flash-1017，回傳僅接受原名或官方canonical deepseek/deepseek-v4.1-flash-20261017 |
| 服務 | https://openrouter.ai/api/v1；paid only=["deepseek"]固定官方供應商，require_parameters=true／allow_fallbacks=false |
| Key限制 | 官方GET /key回上限US$2、初始usage0／remaining2，到期2026-11-19T07:57:36.297Z（臺灣15:57）；不是由本程式新設額度 |
| 思考 | 官方catalog supported_efforts為max／high／low／none，paid使用low；free仍minimal |
| 單價及費用 | max_price prompt0.3／completion1.2美元／百萬token；request／image固定費率0。實際cost有限、0–US$0.05，token必須一致且不得超過當次cap |
| 期限 | 模型300秒、後端310秒、網頁總等待330秒，短POST202＋每3秒GET查詢，不重送模型請求 |
| 資料與規則 | 必要當前描述／有限歷史送模型；上傳原檔／OCR不送。文件需求仍依官方規則，使用者獨立確認才建立清單 |

0.05美元是回覆後的接受檢查，不能退款或保證供應商硬停；預防端依單價cap、輸入／輸出界限與供應商key總額限制。其他模型、auto router、無費用metadata、非零free費用、非有限／超限paid費用、截斷、來源或事實不符均拒絕。[官方模型](https://openrouter.ai/deepseek/deepseek-v4.1-flash-1017)、[供應商](https://openrouter.ai/provider/deepseek)、[路由單位](https://openrouter.ai/docs/guides/routing/provider-selection#max-price)

## 問題定位與修正

首次新付費profile的合成招呼仍429；一次帶安全分類的診斷確認provider_name=Relace、limit_source=upstream_provider_shared_pool，key仍有額度且帳戶有可用credits，不是新金鑰無效或欠款。沒有記錄原始錯誤、prompt或帳戶餘額明細到版本控制。依官方provider目錄確認DeepSeek slug為deepseek，故只在paid分支加入only=["deepseek"]，保留同一模型及既有單價cap，不做自動重試、跨供應商或模型fallback。free分支未加only、零費用護欄不變。

TDD先45失敗／12通過（57新案例），paid low effort與供應商限定各先1個預期RED。其後兩次語意真失敗作提示修正的RED，新增8項正負案例，沒有放寬驗證器。安全診斷先16項RED、未知module邊界另1項RED，最終相關AI484/484、全後端627/627（48.26秒，既有Starlette warning1）。前端沒有免費模型／cost0假設，產品UI無需變更；完整前端69/69通過。後續文件相關性修正與最終數字見下方驗收紀錄。

## 真實探測

修正供應商後兩次真請求均HTTP200、provider=DeepSeek、model=指定1017：

| Profile | 回覆 | 費用USD | Prompt／Completion／Total | 耗時秒 |
| --- | --- | --- | --- | --- |
| 語意招呼 | clarification、非模擬 | 0.0005049 | 523／290／813 | 2.391 |
| 官方證據問答 | answer、非模擬、3引用 | 0.0002508 | 344／123／467 | 1.453 |

合計0.0007557美元。使用預設真HTTP transport，觀察wrapper只讀取去敏感provider metadata；回覆仍經完整模型、用量、費用、語意／官方證據驗證。不把這兩次獨立探測當作網站完整流程成功。

公開網站：[理賠準備助手](https://tulsa-ppc-message-builders.trycloudflare.com/?service=api)。指定模型的真成功與失敗均記錄；下列各輪是修正後的必要重驗，不是程式自動重試。

## 公開流程與失敗修復

| 輪次 | 結果 | 定位與處理 |
| --- | --- | --- |
| 第一輪，76.98秒 | 桌面／平板／手機皆第4句INVALID | 模型從「只有急診」推成outpatient=no。提示補六項事實獨立性；同上下文真請求後為unknown並PASS，費用US$0.000834；原驗證器保持拒絕錯誤推論 |
| 第二輪，71.324秒 | 桌面完整PASS，平板／手機第2句INVALID | 只描述車禍卻選outpatient_or_emergency，當時住院仍unknown。提示補提問優先表；同上下文真請求改care_setting並PASS，費用US$0.000706236 |
| 第三輪，109.936秒 | 桌面／手機完整PASS，平板文件回答品質FAIL | 三尺寸四輪語意均過；平板選合法證據卻沒回答申請書欄位／簽名。不是INVALID或API失敗；定位證據請求未附當前問題，補必要遮罩query與針對具體條件的提示 |
| 第四輪，116.253秒 | 桌面1440／平板768／手機390全部PASS，3/3 | 同一最終source／公開程序、單worker、retries0；15個真模型回覆，全部原業務、來源、欄位／簽名品質及安全斷言保留 |

第三輪共15個真模型階段，每尺寸四次語意＋一次文件問答。三尺寸真PDF text、canvas有內容、人工覆核、頁面及dialog無水平溢出、console／pageerror零、案件DELETE後404皆通過。平板失敗後未執行的摘要／重載不計PASS。所有輪次的細節在本機 `.local/deepseek-20261020/public-live*.log`，不含真個資；不保存真模型對話截圖、trace或video。

文件問答修復只增加 `{query,evidence}` 的當前必要問題，復用 `prepare_dialogue([], message)` 的1–4000字、先遮罩與遮罩後長度檢查，不附history／case／上傳檔／OCR。模型仍只回原1–3個evidence_ids，伺服器驗證並重建canonical全文與引用。新增5個測試，有效RED4fail／1pass後全過；最終AI489/489（5.67秒）、全後端632/632（65.48秒，既有warning1），generic原profile及所有模型／費用／來源限制保持。唯讀review未發現阻擋問題，沒有硬塞驗收ID或更改檢索器與官方資料。

第四輪每尺寸四輪語意＋一次官方證據回答皆真 `openai_compatible`／非模擬及AI標示；候選前不改類型／文件／PATCH、獨立確認才建立清單、官方條件與來源／頁碼一致、錯誤不改案、真PDF文字／canvas／人工覆核、摘要下載／重載與清除全部通過。console／pageerror零，page／dialog溢出差≤1像素。受控503是刻意阻斷的前端錯誤恢復測試，不送模型，不能當作真上游故障或模型請求。三個測試案件DELETE200後GET404，沒有真理賠送件。

公開23項HTTPS套件保留 `llm_verified=true` 斷言並通過；最初在重啟後尚未生成時提早執行，該斷言曾FAIL，未降為僅檢查boolean。隨真模型成功再執行才PASS。health仍只代表同程序曾成功，不能取代全流程。

## 容器與服務模式

Docker Desktop引擎已恢復，先前引擎未啟動的阻礙已解除。首映像真模型1/1（4.031秒）、HTTP／真OCR56項（5.0秒）、重啟持久性、安全及清理通過；hash核對則FAIL，定位原生dist預設Mock、容器預設API。原生dist備份後以 `VITE_SERVICE_MODE=api` 重建，Chrome無query根網址也實際發出API health請求；無模型工作、無console錯誤。

修正模式後的中間映像 `cardif-claim-preparation:deepseek-final-20261020` 實際image ID為 `sha256:8f592c8e7400ad91bae737de92b04edc09c7ee4fd629571549a442e5f8703846`。backend17＋dist207共224檔SHA256全與host同路徑一致，host額外舊assets保留給舊分頁；真模型1/1（4.016秒）、重啟同cookie／案件完整、舊job404／verified重設、安全runtime／health及資源清理皆過。此映像不含下段query修正，未冒稱最終source。首映像56項及不變OCR程式是後續差異驗證依據。

最終含query修正的 `cardif-claim-preparation:deepseek-query-20261020` 實際image ID為 `sha256:3ea3b760219cb1095fa56a64f0d73f3b953ca53ace9606ebc3c35712882af700`。同樣224檔hash一致，真申請書問答1/1（2.031秒），完整官方段落及對應source/page、非模擬、人工作業提醒、零updates、準備狀態不變、兩則訊息及verified均過；重啟持久性、安全runtime、清除案件／舊工作404與資源清理全過。只做這一次模型請求，未重跑不變的OCR。兩輪專用容器／volume已清理，8005無listener，image保留。

## 最終結果

最終唯讀GET /key為200：上限US$2、已使用 **US$0.031929972**、剩餘限制 **US$1.968070028**，到期2026-11-19T07:57:36.297Z。這是測試結束時供應商回報的快照，不是未來費用保證，沒有變更額度或帳號。明確價格／token／單請求事後cost檢查仍保留。

原始HTML與備份SHA256皆 `59a6fd5053e9811560823b3f12637ef0c7bbe7f3aa2fd9a1abe1ea90fad1c8a1`，設計語言、官方規則、來源及OCR未變。前輪Mock87／API及OCR27／受控長等待4屬不變部分的歷史差異證據，沒有宣稱本輪重跑；本輪另有真模型3/3及首映像OCR56。OpenAI與Gemini仍依使用者決定暫緩，不阻擋已實作的原型。

最終432檔實際新key及完整OpenRouter憑證格式掃描皆零命中，279個本地文件連結無缺漏；私有檔owner-only ACL／Git忽略／Docker白名單排除及後端404已核對。沒有將真實對話、cookie、帳戶總餘額或秘密值納入版本控制。[掃描](deepseek-20261020/leak-check.json)、[連結](deepseek-20261020/links.json)

去敏感證據：[測試摘要](deepseek-20261020/tests.json)、[最終公開流程](deepseek-20261020/public-final.json)、[前三輪失敗](deepseek-20261020/public-attempts.json)、[真模型與費用](deepseek-20261020/live-official-provider.json)、[最終key快照](deepseek-20261020/provider-final.json)、[公開23項](deepseek-20261020/public-http.json)、[容器真問答](deepseek-20261020/container-query-live.json)、[224檔hash](deepseek-20261020/container-query-artifacts.json)、[重啟](deepseek-20261020/container-query-persistence.json)、[安全runtime](deepseek-20261020/container-query-runtime.json)。其餘安全診斷及掃描同目錄保存，不保存原始對話、cookie或秘密值。

展示程序保持執行、網址不變；Quick Tunnel無固定網址或存活保證。單worker／單副本、工作僅記憶體保存、有限語意驗證／個資遮罩、歷史OCR底層例外原因未明等限制仍見[已知限制](KNOWN_LIMITATIONS.md)。原型不判資格／金額、不正式核准或送件。
