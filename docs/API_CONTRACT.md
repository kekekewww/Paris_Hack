# 理賠準備服務 API 契約 v1

本契約自 Phase 1 起固定前端與後端的資料語意。前端僅呼叫 `src/services/index.js` 匯出的服務；`MockClaimService` 與 `ApiClaimService` 使用相同的方法及回傳資料形狀。官方規則與下載網址來自 `data/official-sources.json`，不是由 UI 或 AI 自行拼接。

## 服務選擇與展示邊界

```js
import { createClaimService } from '/src/services/index.js';
const service = createClaimService({ mode: 'mock' });
// 部署環境：VITE_SERVICE_MODE=api（同源 /api/v1）
```

`createClaimService()` 預設使用 `VITE_SERVICE_MODE`，未設定則為 `mock`。`service.mode` 為 `mock` 或 `api`，供 UI 持續顯示服務來源。Mock 的對話與分析一律標示 `provider: 'mock'`、`is_simulated: true`。API adapter 不會在連線失敗後回退到模擬結果，也不會將模擬情境參數送交真正的 OCR endpoint。

Mock 建構參數為 `{ delay = 180, storage = sessionStorage, registry = officialRegistry }`。測試可注入 `delay: 0` 與實作 `getItem/setItem/removeItem` 的記憶體 storage。`simulateFailure(code?, message?)` 只令下一次服務呼叫失敗，重試可以恢復。Mock 案件僅保存在同一分頁的 sessionStorage，不存檔案 Blob、base64 或原文內容；請只使用合成展示資料。清除案件也會移除該案件的訊息及檢查結果。

API 建構參數為 `{ baseUrl = '/api/v1', timeout = 15000, messageTimeout = 50000, analysisTimeout = 95000, fetchImpl = fetch }`。一般讀寫為15秒、對話50秒、文件分析95秒；分別涵蓋後端對話45秒與分析90秒的處理預算，避免合法回覆尚在處理就被前端提早取消。瀏覽器原生fetch綁定至globalThis，保持Window／Worker呼叫語意。`baseUrl` 必須是以單一 `/` 開頭的同源相對路徑，禁止完整 URL、雙斜線及反斜線；檔案不會傳到任意網域。

## 方法與端點

所有端點皆包含 `/api/v1` 前綴。ID 路徑參數由 adapter 編碼。JSON request / response 使用 UTF-8。成功回傳直接是表列資料，沒有額外 `data` 包裝。

| 前端方法 | HTTP | 路徑 | Request | 回傳 |
| --- | --- | --- | --- | --- |
| `health()` | GET | `/health` | — | `{status, service_mode, llm_provider, ocr_provider, llm_configured?, llm_verified?}` |
| `getClaimTypes()` | GET | `/claim-types` | — | `ClaimType[]` |
| `createCase(input)` | POST | `/cases` | `CreateCase` JSON | `Case` |
| `getCase(id)` | GET | `/cases/{id}` | — | `Case` |
| `updateCase(id, updates)` | PATCH | `/cases/{id}` | `{claim_type_id?, conditions?}` | `Case` |
| `sendMessage(id, message, {document_id?})` | POST | `/cases/{id}/messages` | `{message, document_id?}` | `{case: Case, response: AssistantResponse}` |
| `getChecklist(id)` | GET | `/cases/{id}/checklist` | — | `Document[]` |
| `updateDocument(id, docId, updates)` | PATCH | `/cases/{id}/documents/{docId}` | `{status?, confirmed_findings?}` | `Case` |
| `analyzeDocument(id, docId, file, options?)` | POST | `/cases/{id}/documents/{docId}/analyze` | `multipart/form-data` 的 `file` | `Case` |
| `getSource(id)` | GET | `/sources/{id}` | — | `Source` |
| `deleteCase(id)` | DELETE | `/cases/{id}` | — | `{deleted: true, id}` |

建立案件時 HTTP 後端使用 201，其他成功回應使用 200。`deleteCase` 必須回傳 JSON；無此案件則 404。資料服務不提供任何正式理賠送件端點。

真實後端會以 `claim_session` 的 HttpOnly、SameSite=Strict cookie 識別匿名 owner；adapter 使用同源 cookie，不在 JSON 或 JavaScript 暴露 token。HTTPS 須配置 Secure cookie。不同 owner、已刪除或到期案件均回 `404 CASE_NOT_FOUND`。案件自建立起固定保留 24 小時，每 owner 最多 20 件，每案最多 100 回成功對話。API 回應 `Cache-Control: no-store`；跨來源需符合明確 allowlist，不能只更改前端 `baseUrl` 連外。

真實 health 的 `llm_configured` 只代表外部模式必填設定齊備；health 本身不發送模型請求。OpenRouter免費路由只有在本後端程序、同一配置使用真實預設transport，且模型、明確零費用、token、逐字證據及引用全部驗證成功後，`llm_verified` 才為 true。重新啟動、停用或觀察到配置變更會清除，不靠環境旗標或離線fixture設為 true；它表示本程序曾驗證成功，不保證目前容量或持續可用。其他尚未實測的相容服務保持未驗證。預設 `grounded_rules` 不使用生成式模型，兩個旗標均為 false。對話與分析仍以每次回應的 `provider`／`is_simulated` 為準。

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
};
type Case = {
  id: string;
  entry_path: 'guided' | 'direct';
  claim_type_id: ClaimTypeId | null;
  conditions: Conditions;
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
  | 'precheck_passed' | 'needs_attention' | 'not_applicable';
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
  file: {name: string; type: string; size: number} | null;
};
```

`requirement_type` 與 `status` 分開管理。條件已知不成立時可由規則標為 `not_applicable`，未知時保留 `conditional` 與人工確認提示。必要文件不能由使用者標為不適用。

文件 PATCH 允許 `status: 'not_started' | 'uploaded' | 'not_applicable'`；`uploaded` 表示使用者自行備妥，沒有宣稱做過 OCR；若目前分析仍有疑點，嘗試標記自行備妥會維持 `needs_attention`。分析狀態由分析端點產生，不能手動標為通過。重設為 `not_started` 會清除該文件的分析與檔案中繼資料。`confirmed_findings` 只能使用目前分析已存在的 finding ID；確認疑點不會清除疑點、提高信心或變成核准。

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
  response_type: 'clarification' | 'claim_suggestion' | 'answer' | 'uncertain';
  message: string;
  suggested_claim_types: ClaimType[];
  missing_information: string[];
  source_references: Source[];
  proposed_case_updates: {claim_type_id?: ClaimTypeId; conditions?: Partial<Conditions>};
  requires_human_review: boolean;
  provider: string;
  is_simulated: boolean;
};
```

訊息長度為 1–4000 字。每次成功對話在 `case.messages` 保存一組 user 與 assistant 訊息。`document_id` 指定文件上下文；不存在的文件回 404。Mock 對「不知道是否住院」、「沒有住院」等描述不推定住院類別。給付金額、資格、正式核准或沒有官方依據的問題須回覆不確定與官方確認方式。上傳／對話中的指令不得覆寫規則或變更檢查結果。

## 上傳與初步分析

接受 PDF、JPG、PNG；前後端均須檢查 MIME、副檔名、內容 magic bytes、非空及大小上限 10 MB。真正後端另須限制頁數（最多 10 頁）及處理時間，解析失敗應回結構化錯誤，不能沿用模擬成功。前端可使用暫時 object URL 預覽，離開／替換時須釋放；服務不得保存原始檔案。

`analyzeDocument(..., {scenario})` 的 scenario 僅供 Mock，預設 `missing`，其他為 `complete`、`blurred`。Mock 不辨識實際文件內容；三種情境必須在 UI 清楚標示。缺漏與模糊回 `needs_attention`，完整情境回 `precheck_passed`，其意義僅是未發現指定缺漏。

```ts
type BoundingBox = {page_number: number; x: number; y: number; width: number; height: number};
type Finding = {
  id: string; field: string; field_name: string; severity: string;
  message: string; suggestion: string; confidence: number;
  page_number: number; bounding_box: BoundingBox;
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

品質提示的 page_number 與 bounding_box.page_number 必須是實際跳過頁；位置為人工提示區，不是模型定位。`confidence` 是保守調整後的初步參考，品質不足時上限 0.49，並非校準正確率、文字純平均或整份文件完整率；全部品質預檢時為 0，UI 不呈現成模型辨識信心。

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
| 429 | `RATE_LIMITED` / `CASE_LIMIT` / `MESSAGE_LIMIT` | 每 IP／每分鐘配額、owner 案件或案件對話上限；RATE_LIMITED 附 Retry-After |
| 409 | `CASE_EXISTS` | 案件 ID 衝突 |
| 503 | `OCR_BUSY` / `OCR_TIMEOUT` / `OCR_UNAVAILABLE` | OCR 單工容量、處理預算或模型不可用 |
| 503 | `LLM_NOT_CONFIGURED` / `INVALID_LLM_CONFIG` | 外部模型未配置或設定不合法 |
| 503 | `LLM_TIMEOUT` / `LLM_PROVIDER_ERROR` / `INVALID_LLM_RESPONSE` | 真模型請求逾時、失敗或回覆不符證據邊界 |
| 502 / 503 | `INVALID_AI_RESPONSE` / `INVALID_PROVIDER_RESPONSE` | 結構、引用或非模擬檢查未通過 |
| 503 | `PROVIDER_UNAVAILABLE` / `INVALID_REGISTRY` / `FRONTEND_UNAVAILABLE` | 服務、官方索引或前端產物不可用 |
| 500 | `INTERNAL_ERROR` | 未預期服務錯誤，不回傳原始內容或堆疊 |
| 503 | `SIMULATED_FAILURE` / `STORAGE_UNAVAILABLE` | Mock 故障演示或瀏覽器儲存失敗 |
| 0 | `NETWORK_ERROR` / `TIMEOUT` / `INVALID_RESPONSE` | HTTP adapter 網路、逾時、非 JSON 回覆 |

API 整合驗收必須以真實 HTTP request 另行驗證，單元測試中的 fetch test server 只證明 adapter 合約，不代表 FastAPI、LLM 或 OCR 已完成。
