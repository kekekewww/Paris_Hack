# 官方理賠來源與規則查核

查核日：2026-10-17（臺灣）。資料入口：[法國巴黎人壽理賠程序介紹](https://life.cardif.com.tw/zh/a314)。

本文件記錄已實際讀取的官方公開頁面與 PDF，供前端 Mock 資料及後端規則共用。機器可讀資料為 [official-sources.json](../data/official-sources.json)。此研究沒有登入保戶帳號，也未向保險公司送出申請。

## 查核方式與可靠性

1. 開啟官方 `a314` 頁面，從下載列表取得完整網址，未猜測檔案路徑。
2. 逐一透過 web 工具讀取頁面與 PDF，確認內容類型、標題、頁數及相關段落。
3. 用官網條列與 PDF 內文交叉確認；單獨的 PDF 表格文字會失去欄位位置，因此未靠表格文字推定未明條件。
4. 版本只記文件明載內容；未標日期者為 `null`，URL 中的 `t=` 不視為版本或更新日期。
5. 查核結果是當日可讀紀錄，執行時仍需處理連結失效；無法取用時提供官方入口並標為待確認。

本機直接下載遭網路沙箱拒絕；web PDF screenshot 的回傳未提供可見影像像素。上述限制沒有被當作視覺查核通過。規則以可讀內文與官網交叉支持，並明列歧義。

## 已驗證來源

| source_id | 官方來源 | 頁數 | 文件明載版本 |
|---|---|---:|---|
| `cardif-claims` | [理賠程序介紹](https://life.cardif.com.tw/zh/a314) | — | 未標明 |
| `cardif-application` | [保險金申請書](https://life.cardif.com.tw/documents/418719/461809/CLAIM-1.1.1.pdf/550abb13-7752-46bb-9463-24669b6fec0e?t=1704248030890) | 4 | VIE_Claim.2024.01 |
| `cardif-general-documents` | [申請一般理賠應檢附文件](https://life.cardif.com.tw/documents/418719/461809/CLAIM-1.1.3.pdf/0d5f2ed7-bb48-4dd6-a026-b645bcac9942?t=1528974663896) | 1 | 未標明 |
| `cardif-outpatient-guide` | [健康險門診保險金申請注意須知](https://life.cardif.com.tw/documents/418719/461809/CLAIM-3.4.pdf/10e161ca-d75d-46c0-b771-fd6e35b8d9ca?t=1762833872536) | 1 | 未標明 |
| `cardif-inpatient-guide` | [住院醫療日額申請注意須知](https://life.cardif.com.tw/documents/418719/461809/CLAIM-3.5.pdf/55bf978e-ba97-4707-b114-3343d6979c40?t=1762833879421) | 3 | 未標明 |
| `cardif-critical-guide` | [重大疾病或防癌險申請須知](https://life.cardif.com.tw/documents/418719/461809/CLAIM-3.6.pdf/8c75510e-8c21-4f18-a013-f3d38bed38cc?t=1762833885720) | 3 | 未標明 |
| `cardif-general-example` | [保險金申請書（一般）填寫範例](https://life.cardif.com.tw/documents/418719/461809/CLAIM-2.1.2.pdf/ae0d8b89-4c59-452d-b973-31a82f9dfda8?t=1704247966933) | 1 | VIE_Claim.2024.01 |
| `cardif-outpatient-example` | [保險金申請書（門診）填寫範例](https://life.cardif.com.tw/documents/418719/461809/CLAIM-2.1.3.pdf/b3daf10f-977e-426b-8b3b-95fe7dc05242?t=1704247988685) | 1 | VIE_Claim.2024.01 |
| `cardif-medical-authorization` | [病歷資料調閱授權書](https://life.cardif.com.tw/documents/418719/461809/CLAIM-1.2.pdf/6ee6c77f-8fc7-4330-a0de-1458b0012b90?t=1509676532538) | 2 | 103.09（文件印載） |
| `cardif-accident-consent` | [調查同意書（意外事故填寫）](https://life.cardif.com.tw/documents/418719/461809/CLAIM-1.3.pdf/fac5596b-2002-4a40-a9d3-a68429b75b1c?t=1509676535867) | 1 | 未標明 |
| `cardif-nhi-request` | [全民健康保險保險人提供資料申請書](https://life.cardif.com.tw/documents/418719/461809/CLAIM-1.4.pdf/a8ffeac8-e25e-4b29-b8eb-2b280008a09f?t=1706146308458) | 1 | 未標明 |

以上網址均由官方頁面取得，且成功讀取內容；不是依命名規律組合的 URL。頁碼皆使用人類閱讀的 1 起算方式。

## 三個優先類別的準備規則

| 類別 | 基本文件 | 需依情況判斷的項目 |
|---|---|---|
| 住院醫療 | 保險金申請書、診斷書或住院證明 | 病理按病況；手術證明依手術與診斷書記載情形；匯款時附存摺影本 |
| 醫療門診 | 保險金申請書、診斷書或住院證明、門診收據 | 收據正副本有下述來源差異；匯款時附存摺影本 |
| 防癌或重大疾病 | 保險金申請書、診斷書或住院證明 | 首次申請涉及病理或相關檢驗；手術文件依診斷書記載；其餘按病況及保單確認 |

基本清單由 [官網分類條列](https://life.cardif.com.tw/zh/a314) 與 [一般理賠文件注意事項](https://life.cardif.com.tw/documents/418719/461809/CLAIM-1.1.3.pdf/0d5f2ed7-bb48-4dd6-a026-b645bcac9942?t=1528974663896) 支持。這是文件準備分類，不代表已確認個別保單有相關保障。

- 診斷書：需正本，或原醫療院所加蓋紅章的副本。普通影印本不符合指南要求；醫療院所文件沒有官方空白下載表單，不可自行提供假下載連結。[住院須知第 3 頁](https://life.cardif.com.tw/documents/418719/461809/CLAIM-3.5.pdf/55bf978e-ba97-4707-b114-3343d6979c40?t=1762833879421)
- 手術證明：有手術且診斷書缺少手術部位、方式時另附；已記載或沒有手術，依指南可免另附。一般文件另提醒手術保險申請涉及費用明細或手術紀錄，不能由助手推斷所有手術給付類型皆相同。[住院須知第 3 頁](https://life.cardif.com.tw/documents/418719/461809/CLAIM-3.5.pdf/55bf978e-ba97-4707-b114-3343d6979c40?t=1762833879421)、[重大疾病須知第 3 頁](https://life.cardif.com.tw/documents/418719/461809/CLAIM-3.6.pdf/8c75510e-8c21-4f18-a013-f3d38bed38cc?t=1762833885720)
- 病歷授權、健保資料申請：官網說明可能依病灶或審核需要要求。指南有填寫教學，不等於每個人都需提供，應以承辦人通知為條件。[官網注意事項](https://life.cardif.com.tw/zh/a314)
- 意外調查同意書：官網標示供意外事故填寫。適用與填寫欄位保留人工確認，避免對全部住院案件一律要求。[官方調查同意書](https://life.cardif.com.tw/documents/418719/461809/CLAIM-1.3.pdf/fac5596b-2002-4a40-a9d3-a68429b75b1c?t=1509676535867)

## 必須保留的歧義

### 門診收據正副本

官網分類列收據正本，但 [申請書第 1 頁](https://life.cardif.com.tw/documents/418719/461809/CLAIM-1.1.1.pdf/550abb13-7752-46bb-9463-24669b6fec0e?t=1704248030890) 記載原收據需作其他用途時可用副本。UI 應同時說明原則及例外，讓使用者向官方確認個案；不能只用 OCR 偵測「影本」就宣告文件不合格。

### 病理報告與首次申請

官網住院類標為依病況，防癌類簡表直接列出病理報告；一般文件第 1 頁的注意事項進一步提及首次癌症或重大疾病申請應附病理或相關檢驗。條件不明時顯示待確認，不把每次住院都判成缺少病理，也不因非首次就保證不需提供。[一般文件第 1 頁](https://life.cardif.com.tw/documents/418719/461809/CLAIM-1.1.3.pdf/0d5f2ed7-bb48-4dd6-a026-b645bcac9942?t=1528974663896)

### 同意書填寫範圍

官網注意事項、指南教學及表單可見欄位並不完全相同。只提供已驗證表單及出處，不代替承辦人決定授權範圍，也不把特定欄位空白判成法律上無效。[官方病歷授權書](https://life.cardif.com.tw/documents/418719/461809/CLAIM-1.2.pdf/6ee6c77f-8fc7-4330-a0de-1458b0012b90?t=1509676532538)

## 官方送件指引

郵寄流程為確認投保險種、備妥適用文件，列印填妥申請書後一併寄至「台北市信義區信義路五段7號79樓」，收件人「法商法國巴黎人壽保險（股）台灣分公司 理賠部 收」。程序及填寫問題可於官網所列上班時間 09:00–18:00 洽 0800-012-899。[官方程序頁](https://life.cardif.com.tw/zh/a314)

官方另提供理賠聯盟鏈／保險理賠醫起通，入口為官網連結的 [巴黎線上 My Cardif](https://my.cardif.com.tw/)。有本人身分、會員、險種、合作機構與原件繳回等條件；助手只能引導查看官方資格說明，不保證任何使用者均可線上申請，也不代送件。[官方服務說明](https://life.cardif.com.tw/zh/a314)

## JSON 使用約定

- `source_id` 連到來源索引；每條規則另有 `page_number`、`review_required` 及補充來源。
- `required` 是該類別的準備要求；`conditional` 必須檢查條件；`unknown` 應呈現人工確認。
- 條件的 `unknown: "review"` 表示缺資料不得當成 false；多條件的 `all` 必須全數符合。
- `review_required` 保留規則本身的歧義。條件尚未確認時，即使此值為 false，仍須請使用者補充。
- `download_source_id: null` 表示應向醫療院所或本人取得資料，沒有可宣稱的官方空白表單。
- 知識段落是簡要改寫，不是完整官方文件，不能當作保單條款或資格判定。

