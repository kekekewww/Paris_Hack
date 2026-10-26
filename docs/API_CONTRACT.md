# 理賠準備服務 API 契約 v1

> 更新：2026-10-26。模型為 `deepseek/deepseek-v4.1-flash-1017`，固定 DeepSeek 官方供應商。語意請求包含必要當前訊息、有限歷史與已驗證的最小案件摘要／對話草稿；原始上傳檔與 OCR 不送。最新驗收狀態見 [組員回饋驗收](feedback-20261026/ACCEPTANCE.md) 與 [STATUS](../STATUS.md)；[前輪模型驗收](DEEPSEEK_SETUP.md) 與 free 路由結果保留為歷史。

本契約自 Phase 1 起固定前端與後端的資料語意。前端僅呼叫 `src/services/index.js` 匯出的服務；`MockClaimService` 與 `ApiClaimService` 使用相同的方法及回傳資料形狀。官方規則與下載網址來自 `data/official-sources.json`，不是由 UI 或 AI 自行拼接。

外部文件問答內部請求只包含本次必要遮罩query與公開官方證據，不帶對話歷史或使用者文件內容。模型只能挑證據ID，由後端根據已查核證據產生受控的切題回答／適用條件與引用；資料不足明示未知，不改官方需求。2026-10-26新增案件摘要、提案及分析定位欄位，定義如下。

## 服務選擇與展示邊界

### 2026-10-26 案件流程擴充

此節定義新版網站契約；後方未帶結構化流程的舊語意profile僅供向後相容，不能代替新版API驗收。

引導頁仍先選取類型，再獨立建立清單。選型符合當前有效伺服器提案時，提交`proposal_id`／`expected_revision`／`proposal_action:'accept'`，保留已驗證對話事實；改選其他類型則提交明確的類型／條件PATCH，不接受原類型提案。兩種操作皆保留版本與owner檢查。

- `Case.revision` 為非負整數，每次保存案件遞增，舊案件讀取時預設0。`Case.details` 為正式確認資料，`Case.dialogue_state.details/conditions/facts` 為對話草稿，不能直接覆寫正式條件或官方清單。
- `details` 包含 `insured_relation: unknown/self/spouse/parent/child/other`、可為null的 `diagnosis_name/surgery_name/surgery_date`、`visit_dates:{admission,discharge,visit,discharge_pending}`、`policy_products:[{code,version,verification_status:'unverified'}]` 與 `deferred_fields`。部分日期保留原始月日，不猜年份；出院未知獨立標記。使用者提供的商品碼不等於已核對投保或保障。
- `dialogue_state` 包含受限 `facts`、`conditions`、`details`、`deferred_fields`、`pending_question` 與伺服器保管的 `active_proposal`。待答問題為 `{field,kind:'fact'|'proposal',asked_at_revision,prompt,options:[{label,value}]}`。短答須綁定目前問題，否定提案不能當成否定住院事實。
- `AssistantResponse.response_type` 新增 `case_update_proposal`；新增可選 `pending_question`、`dialogue_state` 及 `proposal:{id,base_revision,changes:[{field,before,after}]}`。新訊息可保存草稿，但正式條件與文件清單在明確接受前不變。
- `PATCH /cases/{id}` 新增 `details`、`expected_revision`、`proposal_id`、`proposal_action:'accept'|'reject'`。提案操作必須帶原ID與revision，伺服器核對本案有效原提案及內容，不能以客戶端夾帶更新取代。過期／已用／跨案或版本不符回409 `STALE_PROPOSAL`，接受時內容不符回409 `INVALID_PROPOSAL`；拒絕夾帶修改回422 `INVALID_PROPOSAL`。未帶版本的舊手動PATCH仍會遞增revision，使舊提案失效。
- `Document.status` 新增 `manual_ready`（已人工核對並備妥），與 `precheck_passed`、`uploaded` 不同。文件PATCH新增 `analysis_id`；確認finding與人工備妥必須對應目前分析。未確認完不可標人工備妥；全部確認也不自動算備妥，須另外明確操作。分析結果、缺漏、覆核旗標不因人工備妥被改寫。過期分析回409 `STALE_ANALYSIS`、未核完回409 `UNCONFIRMED_FINDINGS`。
- `FileMetadata.sha256` 為可選64位小寫hex摘要，用於同分頁原檔與分析版本匹配。原檔僅受限記憶體暫存，不放SQLite／localStorage／sessionStorage；刪案與換檔清理。重新整理後需重選，不能用同檔名當成相同原檔。
- `Finding.bounding_box` 可為null，新增 `location_status:'label'|'unlocated'|'page'`；頂層 `Analysis.bounding_boxes` 只放有可靠定位的框。找不到欄位位置時顯示文字提醒，無原檔時不疊假定位框。confidence僅留內部品質與契約，不顯示成使用者百分比。

### 官方文件庫與FAQ

| 前端方法 | GET端點 | 回傳 |
| --- | --- | --- |
| `getLibrary({query?,category?})` | `/library?query=&category=all` | `{schema_version,checked_at,scope_note,categories,documents,total,query,category}` |
| `getFaq()` | `/faq` | `[{id,question,answer,sources,scope_note}]` |
| `getProduct(code)` | `/products/{code}` | `{requested_code,normalized_code,verification_status,product_name,versions,candidate_sources?,scope_note}` |

query最多200字、category最多80字；商品碼最多80字且只允許ASCII英數、底線、連字號或點。未知分類／查詢回空目錄，未知商品回未驗證且versions空，不假造成功。所有查詢只讀 `data/official-library.json` 的封存官方allowlist，不抓取使用者網址。

分類包含 `id/label/document_count/preparation_supported`；文件包含 `id/title/category_id/category_label/document_type/official_url/product_code/version/checked_at/verification_status/page_number/page_count/source_page_url/scope_note`，另可有 `asset_code/version_status/version_note`。`product_code:null` 或版本未確認不可用檔名推定。`candidate_sources` 只供相關條款核對，不是精確商品版本匹配。未支援險種僅供文件查詢，不能建立假準備清單。

目錄與FAQ採獨立載入／錯誤狀態，不阻斷既有兩條準備流程；Mock使用同一封存來源並維持模擬對話／OCR標示。

```js
import { createClaimService } from '/src/services/index.js';
const service = createClaimService({ mode: 'mock' });
// 部署環境：VITE_SERVICE_MODE=api（同源 /api/v1）
```

`createClaimService()` 預設使用 `VITE_SERVICE_MODE`，未設定則為 `mock`。`service.mode` 為 `mock` 或 `api`，供 UI 持續顯示服務來源。Mock 的對話與分析一律標示 `provider: 'mock'`、`is_simulated: true`。API adapter 不會在連線失敗後回退到模擬結果，也不會將模擬情境參數送交真正的 OCR endpoint。

Mock 建構參數為 `{ delay = 180, storage = sessionStorage, registry = officialRegistry }`。測試可注入 `delay: 0` 與實作 `getItem/setItem/removeItem` 的記憶體 storage。`simulateFailure(code?, message?)` 只令下一次服務呼叫失敗，重試可以恢復。Mock 案件僅保存在同一分頁的 sessionStorage，不存檔案 Blob、base64 或原文內容；請只使用合成展示資料。清除案件也會移除該案件的訊息及檢查結果。

API 建構參數為 `{ baseUrl = '/api/v1', timeout = 15000, messageTimeout = 330000, analysisTimeout = 95000, fetchImpl = fetch }`。一般讀寫15秒、對話整體330秒、文件分析95秒；後端對話310秒、模型最多300秒、分析90秒。`sendMessage` 提交背景工作後每3秒查詢一次結果，單次HTTP最多15秒且受剩餘整體期限約束，不重送模型請求。瀏覽器原生fetch綁定至globalThis，保持Window／Worker呼叫語意。`baseUrl` 必須是以單一 `/` 開頭的同源相對路徑，禁止完整 URL、雙斜線及反斜線；檔案不會傳到任意網域。

## 方法與端點

所有端點皆包含 `/api/v1` 前綴。ID 路徑參數由 adapter 編碼。JSON request / response 使用 UTF-8。成功回傳直接是表列資料，沒有額外 `data` 包裝。

| 前端方法 | HTTP | 路徑 | Request | 回傳 |
| --- | --- | --- | --- | --- |
| `health()` | GET | `/health` | — | `{status, service_mode, llm_provider, ocr_provider, llm_configured?, llm_verified?}` |
| `getClaimTypes()` | GET | `/claim-types` | — | `ClaimType[]` |
| `createCase(input)` | POST | `/cases` | `CreateCase` JSON | `Case` |
| `getCase(id)` | GET | `/cases/{id}` | — | `Case` |
| `updateCase(id, updates)` | PATCH | `/cases/{id}` | `{claim_type_id?, conditions?, details?, expected_revision?, proposal_id?, proposal_action?}` | `Case` |
| `sendMessage(id, message, {document_id?})` | POST＋GET | `/cases/{id}/message-jobs` → `/cases/{id}/message-jobs/{job_id}` | `{message, document_id?}` | 提交202，查詢工作直到成功，方法仍回 `{case: Case, response: AssistantResponse}` |
| 同步相容端點 | POST | `/cases/{id}/messages` | `{message, document_id?}` | `{case: Case, response: AssistantResponse}`；代理可能提早中止，網站不使用此長請求 |
| `getChecklist(id)` | GET | `/cases/{id}/checklist` | — | `Document[]` |
| `updateDocument(id, docId, updates)` | PATCH | `/cases/{id}/documents/{docId}` | `{status?, confirmed_findings?, analysis_id?}` | `Case` |
| `analyzeDocument(id, docId, file, options?)` | POST | `/cases/{id}/documents/{docId}/analyze` | `multipart/form-data` 的 `file` | `Case` |
| `getSource(id)` | GET | `/sources/{id}` | — | `Source` |
| `deleteCase(id)` | DELETE | `/cases/{id}` | — | `{deleted: true, id}` |

建立案件時 HTTP 後端使用201，提交對話工作使用202，其他成功回應使用200。`deleteCase` 必須回傳 JSON；無此案件則404。資料服務不提供任何正式理賠送件端點。

### 背景對話工作

提交只回 `{id: UUID4, status: 'pending'}`，不將工作編號當成模型成功。查詢結果格式：

```ts
type MessageJob =
  | { id: string; status: 'pending' }
  | { id: string; status: 'succeeded'; result: { case: Case; response: AssistantResponse } }
  | { id: string; status: 'failed'; error: { code: string; message: string; status: number } };
```

查詢HTTP200可能表示工作失敗；adapter必須把`failed.error`轉為既有`ServiceError`，不能把pending或failed當成成功。只有成功且通過原有模型、引用與回覆驗證，才保存一組使用者／助手訊息。工作編號不可跨owner或案件使用，未知／過期工作404；刪除或到期案件仍是`CASE_NOT_FOUND`。

同案同時只允許一個對話工作，重複送出409 `MESSAGE_JOB_ACTIVE`；容量滿429 `MESSAGE_JOB_LIMIT`，均不新增模型請求。同一程序最多16項運算、128項工作紀錄，完成紀錄最多保留15分鐘，容量滿可提前清除最舊的完成紀錄；原訊息仍依案件保留規則保存。伺服器重啟會清除工作狀態，前端重新整理不會自動恢復未完成的查詢。刪案取消本機工作且禁止晚回覆重建案件，無法保證供應商端已停止生成。等待時若案件類型或條件改變，工作失敗409 `MESSAGE_CASE_CHANGED`，須由使用者重新送出以取得符合新情境的回覆。

模型等待及處理與HTTP請求生命週期分離，網站每3秒發出一個短GET；不使用Quick Tunnel不支援的SSE，也不重送POST。同步相容端點保留給直接HTTP客戶端，經過代理時仍可能受到代理自身期限影響。[長等待與驗收](LLM_WAIT.md)

真實後端會以 `claim_session` 的 HttpOnly、SameSite=Strict cookie 識別匿名 owner；adapter 使用同源 cookie，不在 JSON 或 JavaScript 暴露 token。HTTPS 須配置 Secure cookie。不同 owner、已刪除或到期案件均回 `404 CASE_NOT_FOUND`。案件自建立起固定保留 24 小時，每 owner 最多 20 件，每案最多 100 回成功對話。API 回應 `Cache-Control: no-store`；跨來源需符合明確 allowlist，不能只更改前端 `baseUrl` 連外。

真實health的 `llm_configured` 只代表外部模式必填設定齊備，health本身不發送模型請求。OpenRouter只在本程序、同配置使用真實預設transport，且實際模型、費用、token一致性及當次cap（語意4096／證據1800）、`finish_reason=stop`、語意／事實引文或官方證據、最終回覆與引用全部驗證後，`llm_verified` 才為true。free費用必須恰0；指定DeepSeek付費profile只接受原1017或官方canonical 20261017完整model ID，cost有限且在0–US$0.05間，並固定DeepSeek供應商及單價cap。[模型設定](DEEPSEEK_SETUP.md)。重啟、停用或觀察到配置變更會清除，不靠旗標或離線fixture設true；它表示同程序歷史真成功，不保證即時容量。其他未實測的相容服務保持未驗證。預設grounded_rules不是生成式模型，兩旗標皆false，每則仍依provider／is_simulated標示。

## 案件與條件

```ts
type ClaimTypeId = 'inpatient' | 'outpatient' | 'critical_illness';
type ClaimType = { id: ClaimTypeId; title: string; description: string };
type Conditions = {
  cause: 'unknown' | 'accident' | 'illness';
  surgery: 'unknown' | 'yes' | 'no';
  receipt_type: 'unknown' | 'actual' | 'daily';
  payment_method: 'unknown' | 'remittance' | 'other';
  first_claim: 'unknown' | 'yes' | 'no'; // 首次申請，非首次診斷
  diagnosis_has_surgery_details: 'unknown' | 'yes' | 'no';
  pathology_required_for_condition?: 'unknown' | 'yes' | 'no';
  insurer_requested_medical_authorization?: 'unknown' | 'yes' | 'no';
  insurer_requested_nhi_request?: 'unknown' | 'yes' | 'no';
};
type CreateCase = {
  entry_path: 'guided' | 'direct';
  claim_type_id?: ClaimTypeId | null;
  conditions?: Partial<Conditions>;
  details?: Partial<CaseDetails>;
};
type CaseDetails = {
  insured_relation: 'unknown' | 'self' | 'spouse' | 'parent' | 'child' | 'other';
  diagnosis_name: string | null;
  surgery_name: string | null;
  surgery_date: string | null;
  visit_dates: {admission: string | null; discharge: string | null; visit: string | null; discharge_pending: boolean};
  policy_products: {code: string; version: string | null; verification_status: 'unverified'}[];
  deferred_fields: string[];
};
type PendingQuestion = {
  field: string; kind: 'fact' | 'proposal'; asked_at_revision: number;
  prompt: string; options: {label: string; value: string}[];
};
type Proposal = {id: string; base_revision: number; changes: {field: string; before: unknown; after: unknown}[]};
type DialogueState = {
  facts: Record<string, string>; conditions: Record<string, string>;
  details: CaseDetails; deferred_fields: string[];
  pending_question: PendingQuestion | null;
  active_proposal: (Proposal & {updates: object}) | null; // 由伺服器保存與驗證，客戶端不可取代
};
type Case = {
  id: string;
  entry_path: 'guided' | 'direct';
  claim_type_id: ClaimTypeId | null;
  conditions: Conditions;
  details: CaseDetails;
  dialogue_state: DialogueState;
  revision: number;
  documents: Document[];
  messages: Message[];
  created_at: string; // ISO 8601 UTC
  updated_at: string;
};
```

建立時缺少的條件均為 `unknown`，不是 `false`。`updateCase` 合併提供的條件後重新計算清單；既有文件的分析資料按 document ID 保留。不會根據 `receipt_type` 編造官方沒有的收據要求。選項的適用性仍須查閱保單；尚未蒐集到的匯款方式、首次申請、病況或承辦人通知條件維持待確認。

尚未確認類別的引導案件沒有清單。AI 提供的是 `proposed_case_updates`，只有使用者確認並呼叫 `updateCase` 才會變更案件類別或條件；前端禁止解析自由文字決定狀態。

## 文件清單

```ts
type DocumentStatus = 'not_started' | 'uploaded' | 'processing'
  | 'precheck_passed' | 'needs_attention' | 'manual_ready' | 'not_applicable';
type Document = {
  id: string;
  title: string;
  description: string;
  requirement_type: 'required' | 'conditional' | 'optional' | 'unknown';
  condition: object;                    // 官方規則的結構化條件
  applicability: boolean | null;        // null 表示目前資訊不足
  requirement_explanation: string;
  review_required: boolean;
  source_id: string;
  official_url: string;
  download_url: string | null;
  example_url: string | null;
  source_references: Source[];
  status: DocumentStatus;
  analysis: Analysis | null;
  confirmed_findings: string[];
  file: {name: string; type: string; size: number; sha256?: string | null} | null;
};
```

`requirement_type` 與 `status` 分開管理。條件已知不成立時可由規則標為 `not_applicable`，未知時保留 `conditional` 與人工確認提示。必要文件不能由使用者標為不適用。

文件 PATCH 允許 `status: 'not_started' | 'uploaded' | 'not_applicable' | 'manual_ready'`；`uploaded` 表示使用者自行備妥，沒有宣稱做過 OCR；若目前分析仍有疑點，嘗試標記自行備妥會維持 `needs_attention`。分析狀態由分析端點產生，不能手動標為通過。重設為 `not_started` 會清除該文件的分析與檔案中繼資料。`confirmed_findings` 只能使用目前分析已存在的 finding ID；確認疑點不會清除疑點、提高信心或變成核准。確認須帶目前analysis_id；所有提醒確認後，另明確提交manual_ready才記為人工備妥，保留原分析結果。

布林型官方條件使用 `yes/no/unknown` 選項映射；例如 `surgery` 對應 `had_surgery`。官方規則仍標 `review_required` 時，即使某一條件不成立也保留人工確認，不自動免附（例如非首次癌症申請仍可能依病況要求病理資料）。

## 對話

```ts
type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  response?: AssistantResponse;
};
type AssistantResponse = {
  response_type: 'clarification' | 'claim_suggestion' | 'case_update_proposal' | 'answer' | 'uncertain';
  message: string;
  suggested_claim_types: ClaimType[];
  missing_information: string[];
  source_references: Source[];
  proposed_case_updates: {claim_type_id?: ClaimTypeId | null; conditions?: Partial<Conditions>; details?: Partial<CaseDetails>};
  requires_human_review: boolean;
  provider: string;
  is_simulated: boolean;
  pending_question?: PendingQuestion | null;
  dialogue_state?: DialogueState | null;
  proposal?: Proposal | null;
};
```

訊息長度為1–4000字。每次成功對話在 `case.messages` 保存一組user與assistant訊息；失敗不以規則／Mock代替模型成功，也不當作案件確認。`document_id` 指定文件上下文；不存在的文件回404。Mock仍清楚標示模擬來源，不能作為真實語意驗證。

明確使用官方OpenRouter端點及 `openrouter/free` 或已授權的 `deepseek/deepseek-v4.1-flash-1017` 設定時，後端使用語意引導與一般補充分流，沒有新環境開關。有依據的文件問答保留官方證據ID分流；安全、資格、給付金額與正式核准等限制可由規則處理。每則回覆依實際provider／is_simulated標示，不因health已驗證就一律標AI。

語意模式送出必要的當前訊息，加最多8則符合條件的歷史，合計最多9則／6000字；歷史只取role／content，再由伺服器加上本次dialogue的turn索引。當前訊息為1–4000字，超長拒絕，遮罩後完整保留。歷史user每則最多1000字、assistant最多600字，先遮罩再取完整句段後綴；無安全完整句段則排除。保留最後安全引導回覆，以及「有／沒有／是／不是」短答所需的前一個結構化 `clarification` 問句；必要問句須完整保留遮罩後內容；預算排掉或縮減問句時，短答也排除。帶 `document_id`、`answer`、`uncertain`及不明配對的輪次不納入，合格舊格式獨立user可保留。

網站使用的語意v2內部user JSON為 `{dialogue:[{turn,role,content}],confirmed_case:{claim_type_id,conditions,details},dialogue_state,workflow_version:2,revision,pending_questions}`；turn從1起算。confirmed_case只含已確認類型、本頁Conditions定義的九項準備條件及最小details；dialogue_state附已驗草稿、略過欄位與待答問題，剔除active_proposal。pending_questions依user turn綁定當時的待答問題，避免把「沒有」套用到其他欄位。6000字只限制dialogue，結構化摘要另外計入請求。未帶dialogue_state的舊相容profile仍只送類型及cause／surgery。語意分支不帶官方evidence；文件問答另走證據ID分支。原始上傳檔、OCR／抽取全文、分析欄位、cookie、金鑰及完整案件物件不附加。明顯識別資料與憑證採盡力遮罩／拒絕，不是全面去識別；必要對話與診斷／日期等摘要仍可能包含就醫資訊。

v2模型輸出根鍵限 `{facts,question,message,condition_facts?,details?}`；舊相容profile限前三項。facts固定cause／inpatient／outpatient／emergency／critical_diagnosis／surgery六欄，每欄固定 `{value,turn,quote}`：cause為unknown／accident／illness，其餘為unknown／yes／no；unknown需turn=null且quote空字串，已知值需user turn逐字引文及來源語境／領域合理性／直接矛盾檢查。condition_facts及details每個新欄位亦須帶 `{value,turn,quote}`，另驗最新更正、欄位事件關聯與日期；不是任意Case資料。question採允許的追問enum，message為1–500字短對話，不得含URL、文件要求、金額、資格核准、處置指示或與facts矛盾。伺服器依已驗狀態決定實際下一題與受控訊息，不直接顯示模型自由文字。這是有限防護，不宣稱完整語意查核。

模型請求的 `max_completion_tokens` 僅OpenRouter語意分支為4096；官方證據及一般相容profile維持1800。completion metadata不得超過當次cap，`finish_reason=length`即使零費用仍拒絕。整體deadline300秒、JSON schema／1–500字message／6000字輸入保持，不自動重試、換模型或備援。

`sendMessage` 的輸入仍為message及可選document_id；回傳包裝仍為 `{case,response}`，但Case及AssistantResponse已新增本頁定義的v2欄位，不能沿用「所有回應欄位不變」的舊假設。前端不傳內部facts、history或cap物件。伺服器對應registry候選與canonical引用；新案件有可支持候選才產生 `proposed_case_updates`，使用者獨立選類型並確認後才寫入。已選類型案件可回 `case_update_proposal` 與結構化差異；只有使用者明確接受且伺服器確認提案版本／內容未變，才更新案件。模型不能決定官方文件要求、建立清單或直接改案件；官方來源、規則與清單由伺服器決定。上傳或對話中的指令不得覆寫規則。[目前請求流程](MODEL_REQUEST_FLOW.md)及[最新驗收](feedback-20261026/ACCEPTANCE.md)另行記錄；舊profile驗收保留為歷史。

## 上傳與初步分析

接受 PDF、JPG、PNG；前後端均須檢查 MIME、副檔名、內容 magic bytes、非空及大小上限 10 MB。真正後端另須限制頁數（最多 10 頁）及處理時間，解析失敗應回結構化錯誤，不能沿用模擬成功。前端可使用暫時 object URL 預覽，離開／替換時須釋放；服務不得保存原始檔案。

`analyzeDocument(..., {scenario})` 的 scenario 僅供 Mock，預設 `missing`，其他為 `complete`、`blurred`。Mock 不辨識實際文件內容；三種情境必須在 UI 清楚標示。缺漏與模糊回 `needs_attention`，完整情境回 `precheck_passed`，其意義僅是未發現指定缺漏。

```ts
type BoundingBox = {page_number: number; x: number; y: number; width: number; height: number};
type Finding = {
  id: string; field: string; field_name: string; severity: string;
  message: string; suggestion: string; confidence: number;
  page_number: number; bounding_box: BoundingBox | null;
  location_status: 'label' | 'unlocated' | 'page';
  source_id: string; requires_human_review: boolean;
};
type Analysis = {
  analysis_id: string; document_id: string;
  analysis_status: 'completed' | 'uncertain';
  provider: string; is_simulated: boolean;
  scenario?: 'missing' | 'complete' | 'blurred'; // Mock 專用
  extracted_fields: {field: string; value: string; confidence: number; page_number: number}[];
  findings: Finding[];
  confidence: number; page_number: number;
  bounding_boxes: BoundingBox[];
  requires_human_review: boolean;
  disclaimer: string;
};
```

頁碼從 1 開始；座標以每頁左上角為 `(0,0)`，寬高與位置皆為 0–1 正規化比例。低信心或不可辨識不能標為通過。簽名區只能標疑似缺漏，不能驗證真偽。

真實 OCR 的 `extracted_fields.value` 是辨識狀態標記，不回傳姓名、證號、保單號碼、日期或其他欄位原文：辨識到內容時為「已辨識內容（隱私遮罩）」，否則為「未可靠辨識內容」。`document_type` 僅描述是否可辨識申請書標題，不代表驗真。請由欄位 ID、信心、頁碼與 findings 判讀指定檢查結果，再對照暫時預覽人工確認；不能從遮罩字串推定格式已正確。原始上傳檔、欄位原值與抽取全文不持久保存。

低品質影像先做真實影像清晰度預檢。全部頁面因品質不足而跳過 OCR 時，`provider='quality_precheck'`、`is_simulated=false`、`analysis_status='uncertain'`、`extracted_fields=[]`，只提供 `image_quality` 人工確認 finding；不回傳已辨識欄位、空白欄位或文件類型結論。其形狀仍是相同的 Analysis，不新增品質量測欄位。UI 必須明示未執行 OCR。混合文件若有文字層／清晰掃描頁，provider 按實際執行的 `pdf_text`／`rapidocr` 回傳，但有品質不足頁時整體仍 uncertain。清晰度閾值是工程預檢條件，不是官方理賠文件要求；官方連結僅供表單參考。

品質提示的page_number必須是實際跳過頁，location_status為page；無可靠欄位定位時bounding_box可為null，不能當作精確缺漏框。頂層bounding_boxes僅含可靠label定位，UI以finding自身ID及bounding_box配對，不以過濾後的陣列索引猜測。`confidence` 是保守調整後的內部品質參考，品質不足時上限0.49，並非校準正確率、文字純平均或整份文件完整率；全部品質預檢時為0，UI不呈現信心百分比。

## 官方來源

`Source` 至少包含 `source_id`、`title`、`official_url`、`document_type`、`related_claim_types`、`page_number`、`version_or_updated_at`、`checked_at`、`verification_status`；版本未知保留 null。來源 URL 必須是經查核的官方 HTTPS URL。`getSource('cardif-claims')` 額外提供 `submission`，包含 `postal:{address,recipient,steps}`、`official_online_entry:{url,label,verification_status,details}` 與 `support:{phone,hours}`，供準備摘要呈現官方送件方式；助手不代替使用者送件。

## 錯誤與狀態

後端錯誤固定回傳 `{ "error": { "code": "...", "message": "繁體中文訊息" } }`。Adapter 轉為 `ServiceError`，保留 `code`、`message`、`status`；UI 顯示訊息並可重試，不能把錯誤偽裝成完成。

| HTTP | code | 情況 |
| --- | --- | --- |
| 404 | `CASE_NOT_FOUND` / `DOCUMENT_NOT_FOUND` / `SOURCE_NOT_FOUND` | 查無案件、文件、來源 |
| 422 | `VALIDATION_ERROR` | 無效類別、條件、情境或訊息 |
| 422 | `INVALID_DOCUMENT_STATUS` / `REQUIRED_DOCUMENT` / `INVALID_FINDING` | 不允許的手動狀態或不存在的疑點 |
| 422 | `EMPTY_FILE` / `INVALID_FILE` / `DOCUMENT_NOT_APPLICABLE` | 空檔、格式內容不符或文件不適用 |
| 422 | `ENCRYPTED_PDF` / `INVALID_SOURCE` | 加密 PDF 或來源不符安全規則 |
| 413 | `FILE_TOO_LARGE` / `TOO_MANY_PAGES` / `IMAGE_TOO_LARGE` | 大小、頁數或解碼後像素限制 |
| 415 | `UNSUPPORTED_FILE_TYPE` | 非 PDF/JPG/PNG |
| 403 | `ORIGIN_NOT_ALLOWED` | Origin 或跨站來源不允許 |
| 431 | `HEADERS_TOO_LARGE` | 請求標頭超過 16 KB |
| 429 | `RATE_LIMITED` / `CASE_LIMIT` / `MESSAGE_LIMIT` / `MESSAGE_JOB_LIMIT` | 每 IP／每分鐘配額、owner 案件、案件對話或程序工作容量上限；RATE_LIMITED 附 Retry-After |
| 409 | `CASE_EXISTS` / `MESSAGE_JOB_ACTIVE` / `MESSAGE_CASE_CHANGED` / `MESSAGE_JOB_CANCELLED` | 案件ID衝突、已有對話、等待途中情境改變或工作已取消 |
| 409 | `STALE_PROPOSAL` / `INVALID_PROPOSAL` / `STALE_ANALYSIS` / `UNCONFIRMED_FINDINGS` | 提案版本／內容不符、分析已換版或尚未逐項核對；取消提案夾帶修改另回422 `INVALID_PROPOSAL` |
| 404 | `MESSAGE_JOB_NOT_FOUND` | 工作不屬於目前owner／案件、已過期或被清除 |
| 503 | `MESSAGE_JOB_UNAVAILABLE` / `MESSAGE_JOB_FAILED` | 服務關閉或工作未預期失敗，隱藏內部例外 |
| 503 | `OCR_BUSY` / `OCR_TIMEOUT` / `OCR_UNAVAILABLE` | OCR 單工容量、處理預算或模型不可用 |
| 503 | `LLM_NOT_CONFIGURED` / `INVALID_LLM_CONFIG` | 外部模型未配置或設定不合法 |
| 503 | `LLM_RATE_LIMITED` | OpenRouter回429；明確顯示稍後重試，不自動重試、換模型或轉Mock |
| 503 | `LLM_TIMEOUT` / `LLM_PROVIDER_ERROR` / `INVALID_LLM_RESPONSE` | 真模型請求逾時、失敗或語意／事實引文／官方證據驗證不符 |
| 502 / 503 | `INVALID_AI_RESPONSE` / `INVALID_PROVIDER_RESPONSE` | 結構、引用或非模擬檢查未通過 |
| 503 | `PROVIDER_UNAVAILABLE` / `INVALID_REGISTRY` / `FRONTEND_UNAVAILABLE` | 服務、官方索引或前端產物不可用 |
| 500 | `INTERNAL_ERROR` | 未預期服務錯誤，不回傳原始內容或堆疊 |
| 503 | `SIMULATED_FAILURE` / `STORAGE_UNAVAILABLE` | Mock 故障演示或瀏覽器儲存失敗 |
| 0 | `NETWORK_ERROR` / `TIMEOUT` / `INVALID_RESPONSE` | HTTP adapter 網路、逾時、非 JSON 回覆 |

API 整合驗收必須以真實 HTTP request 另行驗證，單元測試中的 fetch test server 只證明 adapter 合約，不代表 FastAPI、LLM 或 OCR 已完成。
