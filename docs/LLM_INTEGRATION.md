# LLM Adapter 與實際驗證狀態

> 最新配置依使用者授權改用DeepSeek V4.1 Flash 1017與新key，固定DeepSeek官方供應商。真語意及官方證據探測已成功，[最新設定與驗收](DEEPSEEK_SETUP.md)記錄公開流程結果。原free限流、INVALID與歷史成功保留於[語意紀錄](SEMANTIC_CONVERSATION.md)，不混稱目前程序。

更新日期：2026-10-20（臺灣）。最新授權允許使用付費 `deepseek/deepseek-v4.1-flash-1017`，取代之前只能free的限制。必要當前描述與有限同案歷史可送模型，原始上傳檔／OCR不送，官方需求仍由規則決定。OpenAI／Gemini暫緩；不因此開放其他模型或自動備援。

## 對話分工與公開契約

| 分流 | 模型與伺服器的工作 |
| --- | --- |
| OpenRouter 語意對話 | 處理引導與一般補充的語意提案；傳送必要的當前訊息與有限歷史，輸出經伺服器結構與證據驗證 |
| 有依據的文件問答 | 依本次必要遮罩query，從本次官方證據選取 `evidence_ids`；完整段落與引用由伺服器重建 |
| 本機與安全處理 | 明確選用 `grounded_rules` 時執行本機規則；資格、給付金額、正式核准、提示注入等限制可由規則直接處理，清楚標示實際 provider |
| Mock | 供展示與離線回歸，有 `provider: mock`、`is_simulated: true`；不能代替外部模型結果 |

模型不決定官方文件要求、保單保障、資格、金額或核准。類型／條件只作 `proposed_case_updates`；使用者確認並透過既有 `updateCase` 建立清單後，才寫入案件類型與條件。成功對話本身仍會依原契約保存訊息。前端不解析模型自由文字改動案件或文件狀態。

對外仍使用既有 `AssistantResponse`，每則回覆以自己的 `provider`／`is_simulated` 標示來源。模型內部 JSON 不直接交給前端，也沒有送件或修改案件的工具。錯誤明確回傳，不以本機、Mock 或另一個模型的成功回覆掩蓋外部失敗。[API 契約](API_CONTRACT.md)

## 啟用與費用界線

不新增語意模式環境開關。後端明確設定 `LLM_PROVIDER=openai_compatible`、canonical OpenRouter端點與已授權模型，執行語意或官方證據分流；預設grounded_rules仍可獨立執行，不冒充生成式模型。

金鑰保存在私有 `.local/secrets/.env.openrouter`，啟動時明確映射至 canonical `LLM_API_KEY`；應用不掃描其他 env 檔、不沿用其他供應商金鑰。秘密值不放入前端、Git、Docker build args、映像或日誌。[供應商設定](PROVIDER_SETUP.md)

| 變數 | OpenRouter 設定 | 限制 |
| --- | --- | --- |
| `LLM_PROVIDER` | `openai_compatible` | 明確設定才啟用外部模式 |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | 只接受這個 canonical 官方端點 |
| `LLM_API_KEY` | 後端啟動環境安全注入 | 文件與範本不提供秘密值 |
| `LLM_MODEL` | `deepseek/deepseek-v4.1-flash-1017` | 僅新增這個paid requested ID；原openrouter/free亦保留，其他模型／auto拒絕 |
| `LLM_TIMEOUT_SECONDS` | `300` | OpenRouter 預設／最多300秒，包含等待與讀取完整回覆 |

所有OpenRouter分流保留JSON object／非串流／不儲存請求。DeepSeek依官方catalog支援使用low effort，free維持minimal；語意4096／官方證據1800 token，300／310／330秒與原schema保持。[長等待說明](LLM_WAIT.md)。當前paid provider設定如下：

~~~json
{
  "provider": {
    "only": ["deepseek"],
    "require_parameters": true,
    "allow_fallbacks": false,
    "max_price": {
      "prompt": 0.3,
      "completion": 1.2,
      "request": 0,
      "image": 0
    }
  }
}
~~~

prompt／completion單位是美元／百萬token，request／image分別為固定每請求／每張圖費率。paid只允許回傳1017或canonical 20261017完整model ID，cost為有限數字且在0–US$0.05間；這是回應後驗證，不能退款或取代key總額限制。新key官方GET確認上限US$2、到期2026-11-19。原free profile不帶only、四項單價皆0且回覆cost恰0。不自動重試、不換模型、無Mock或供應商fallback。[官方路由設定](https://openrouter.ai/docs/guides/routing/provider-selection)

## 語意模式的資料範圍

- 當前訊息須為非空字串1–4000字，超長拒絕；遮罩後完整保留。另取最多8則符合條件的歷史，加上當前訊息最多9則，所有content合計不超過6000字；歷史只取role／content，再為本次dialogue加上1起算的turn索引，不附加其他訊息欄位。
- 歷史user每則最多1000字、assistant最多600字，先遮罩再取完整句段後綴。句界包括句號、分號、問驚號、換行，以及逗號後明確更正／請問／本次／這次／目前等起點；無安全完整句段可保留時排除，不任意切字反轉否定。
- 保留最後安全引導回覆，以及「有／沒有／是／不是」短答必要的前一個結構化 `clarification` 問句。必要問句必須完整保留遮罩後內容；若則數或字數上限排掉或縮減它，對應短答一併排除，不能只憑相同turn索引就當作語境完整。
- 排除有 `document_id`、`answer`、`uncertain` 或不明配對的輪次；舊格式的合格獨立user可保留。不將文件問答或分析內容混入語意歷史，仍不能承諾記得整案或所有舊對話。
- 語意wire只包含 `dialogue` 與 `confirmed_case`；後者僅有已確認 `claim_type_id`（可為null）及 `conditions.cause`／`conditions.surgery`，不帶官方evidence。官方證據屬另外的文件問答分支，不能由模型或使用者自行新增來源。
- 原始上傳檔、OCR／抽取全文、分析欄位、cookie、金鑰及完整案件物件不自動附加。對話或上傳內容不能指定外部目的地或改變官方規範。
- 輸入會對明顯身分識別碼、電話／email、姓名／地址、帳號／保單及憑證標記等做盡力遮罩，包含相應全形識別格式；這不是全面去識別或匿名保證。使用者自行輸入的事故、就醫或其他未匹配個人資訊仍可能在必要對話中外送，展示只用合成資料。

`store:false` 等參數不代表供應商資料保留政策已通過驗收。服務使用既有 `httpx.AsyncClient`，不新增供應商 SDK，禁止重新導向且忽略 proxy 環境設定；本機 URL 驗證也不等同正式網路出口政策。

## 模型輸出與伺服器驗證

語意wire的user JSON固定為 `{dialogue:[{turn,role,content}],confirmed_case:{claim_type_id,conditions:{cause,surgery}}}`，turn由本次對話1起算。模型只可回 `{facts,question,message}`，不得新增其他根鍵。

`facts` 固定六欄：`cause`、`inpatient`、`outpatient`、`emergency`、`critical_diagnosis`、`surgery`。每欄固定 `{value,turn,quote}`；cause值為 `unknown|accident|illness`，其餘為 `unknown|yes|no`。unknown須為turn=null、quote空字串；已知值須指向允許的user turn，quote為該turn內容的原文子字串，並通過完整來源語境、有限領域合理性及直接矛盾檢查。assistant說法不能當成使用者事實；這些防護不是完整語意正確性證明。

`question` 限 `describe_event`、`care_setting`、`inpatient`、`outpatient`、`emergency`、`outpatient_or_emergency`、`critical_diagnosis`、`medical_records`、`confirm_claim`、`scope`。`message` 為1–500字繁中短對話，不允網址、文件要求、給付金額、資格／核准、醫療處置指示或與facts矛盾的敘述。

伺服器依通過驗證的事實對應registry候選與canonical引用；新案件只有可支持候選時才產生 `proposed_case_updates`，仍須使用者確認。已選類型的案件只回 `clarification` 提醒確認後調整，`proposed_case_updates` 為空，不由模型覆寫案件條件或狀態。完整公開形狀仍以 [API契約](API_CONTRACT.md) 為準。

支援的文件問答保留較窄的 `{"evidence_ids":["id"]}` 輸出：只允許本次1至3個不重複 ID。伺服器重建完整 canonical 官方段落與來源／頁碼／URL；未知 ID、重複、超量、自由文字、網址、工具呼叫、截斷或拒答等不當作成功。一般非 OpenRouter 相容設定仍保留原有完整段落比對，但未因此取得新的供應商實測證據。

OpenRouter文件問答輸入為 `{query,evidence:[{id,title,text}]}`。query只取當前必要問題，復用 `prepare_dialogue([], message)` 的1–4000字驗證、明顯個資遮罩及遮罩後長度檢查，不附加歷史／case／檔案／OCR。query與證據均視為不可信資料。這補足先前只傳證據、模型不知題目的相關性缺口，不擴大模型對官方規則或輸出內容的權限。

JSON mode 本身不能保證事實、規範或提案正確；內部結構與最終 `validate_assistant_response` 都須通過才回成功。[OpenRouter Chat API](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion)

## 真實模型、用量與 health

OpenRouter回應必須提供具體實際 `model`，paid僅接受已授權兩個精確ID；三項token須為有效正整數且總數相符，completion不得超過當次cap（語意4096／證據1800），`finish_reason` 必須為 `stop`。`usage.cost` 須為有限數字：free恰0、paid為0–US$0.05；缺失、錯型或超限拒絕。`length` 即使費用合法也拒絕。模型與用量保留於後端去敏感驗證紀錄，不加入案件回覆。OpenRouter自動回usage，不需已棄用的 `usage.include`。[官方Usage Accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)

`provider_status()` 不呼叫模型、不公開金鑰／模型／網址。`llm_configured` 只表示設定齊備；`llm_verified=true` 只表示同程序、同配置曾以預設真transport通過HTTP、模型、所選profile費用、內容及最終回覆驗證。重啟、停用或配置變更會清除。離線transport、本機回覆與環境旗標不能建立真成功；歷史成功不能證明即時readiness。

## 錯誤與真實驗收要求

| HTTP | code | 行為 |
| --- | --- | --- |
| 503 | `LLM_NOT_CONFIGURED`／`INVALID_LLM_CONFIG` | 必要設定缺少或不合法 |
| 503 | `LLM_TIMEOUT` | 單次及整體預算逾時 |
| 503 | `LLM_RATE_LIMITED` | 外部供應商回429，明確顯示稍後重試 |
| 503 | `LLM_PROVIDER_ERROR` | 網路、其他 HTTP 錯誤或重新導向 |
| 503 | `INVALID_LLM_RESPONSE` | 語意／證據、模型、用量、費用或最終輸出驗證失敗 |

OpenRouter預設／最多300秒，後端310秒、網頁整體330秒；其他相容端點預設20／最多60秒。回應上限64KiB。供應商原始錯誤body、完整prompt、Authorization與原始模型回覆不寫入日誌或回傳使用者；拒絕診斷僅白名單stage／程式行號／欄位enum。每次失敗明確回報，不自動重試、換模型或以Mock／規則假成功。

## 舊free語意版本驗收（歷史）

以下35秒、零費用、限流與未完成gate為舊版本記錄；現行模型與驗收見[DeepSeek報告](DEEPSEEK_SETUP.md)。

本輪早期兩次真實探測未通過：一次回 `INVALID_LLM_RESPONSE`，另一次於35秒回 `LLM_TIMEOUT`；這兩次未取得可核對的schema／模型用量元資料，仍保留為失敗。

提高預算前程序的公開live曾完成「你好 → 我出車禍了 → 沒有住院」前三輪200、`provider=openai_compatible`、`is_simulated=false`及正確AI標示，所有前置斷言通過；該程序verified由本輪真intake建立。另有NVIDIA獨立改述cost0及問候診斷成功。三次完整live依序為第四輪 `LLM_RATE_LIMITED`、第一輪 `INVALID_LLM_RESPONSE`（未復現）、第一輪 `LLM_RATE_LIMITED`，皆保留失敗。該程序的原完整公開HTTP23項未改斷言且通過；重啟後的新程序須重新驗證，不能沿用先前verified。

另外一次工作區「…」診斷明確觀察到cost0、completion=1800、`finish_reason=length`，因此被Adapter拒絕。這項證據只定位該次截斷，不證明其他無效回覆或限流都由預算不足造成。提高4096後另一次工作區真探測已有stop／cost0，仍因事實來源驗證未過而回INVALID；其急診／門診提案與明確否定事實亦未符合預期，沒有放寬guard讓它通過。新上限不代表所有語意、截斷或容量問題已解決。

提高語意預算前的後端471項／1警告（91.65秒）、前端58／Mock87結果保留。修正後AI離線400項於5.29秒通過，涵蓋semantic4096接受／4097拒絕、evidence1801拒絕及語意後文件請求仍1800；完整後端477項於108.76秒通過（1項既有Starlette警告），新映像7c6afbc9…建置成功。這些不是新live成功證據；新程序公開重驗、Docker與最終gate以 [主報告](SEMANTIC_CONVERSATION.md) 為準。自然短回覆已支援同義表述，仍須通過事實一致性與禁止內容檢查；JSON schema、零費用與其餘免費護欄未變。

語意4096版本部署後，最終新程序公開live首輪200、真provider、非模擬與AI標示斷言通過，第二輪回 `LLM_RATE_LIMITED`，整次1項失敗（39.5秒，另1項網路console錯誤）。這次問候提供新程序真實成功證據，不能補成完整流程通過；公開HTTP與同程序verified的最終結果以主報告為準。所有真實請求已停止，剩餘完整流程受免費容量阻擋。

前三輪真實引導及獨立探測已提供部分語意證據；仍須完成後續引導、確認後寫案、文件問答與錯誤恢復等完整流程，不能把提高預算當作已解決所有無效回覆或容量問題。離線 [HTTPX MockTransport](https://www.python-httpx.org/advanced/transports/#mock-transports) 只能驗證程式邊界；本文件不把部分成功當成整體通過，後續重試、發版與最終gate見 [本輪語意對話紀錄](SEMANTIC_CONVERSATION.md)。

## 保留的驗收歷史

- [OpenRouter 接通驗收](OPENROUTER_ACCEPTANCE.md)：相關後端103項、完整後端293項；本機首輪2通過／平板1限流失敗，平板獨立重驗1通過。容器真 OCR smoke 56項、重啟保存與真模型瀏覽器1項、公開 HTTP 23項與真模型瀏覽器1項皆屬當輪結果。當輪多次cost0，金鑰資訊GET當時限制US$0.10／usage0；重大疾病額外CLI兩輪429未完成，未宣稱三類模型皆通過。
- [逐輪追問修復](ASSISTANT_FOLLOWUP.md)：原公開版「你好 → 我出車禍了 → 沒有住院」三句都是 `grounded_rules`，由舊 Adapter 的非 `answer` 早退分流造成未呼叫模型。該輪完成規則追問、否定、Mock 一致性、舊訊息及逐則來源標示；後端347／前端56、Mock87／API27、容器追問12／公開6通過，但真模型重驗限流、原公開完整腳本未過。當時不新增語意或對話外送的邊界已由本輪新授權部分取代。
- [無金鑰驗收](ACCEPTANCE_NO_KEYS_20261019.md) 的後端190／AI113及更早AI101是歷史離線證據，不改寫為真實模型成功。

固定部署、商業級保險服務及額外模型覆蓋不屬於上述原型驗收；新語意分流的完成範圍仍以本輪報告為準。
