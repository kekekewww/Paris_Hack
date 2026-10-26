# 2026-10-26 官方文件目錄查核

本次只讀法國巴黎人壽公開官方網站；不使用金鑰、案件庫、LLM 或公開展示服務。

- 產品檔案：`data/official-library.json`；只讀查詢模組：`backend/app/library.py`。
- 302 個官方入口：287 個可讀 PDF 網址（253 條款、34 理賠／服務 PDF）與 15 個 HTML 分類／服務頁。以完整官方 URL 去重；不同 URL 的相同文件可能仍各保留入口，不將網址筆數誤當成不同契約數量。
- 官方 a321 條款總索引實際 253 條連結：投資型 195、人壽 22、傷害 11、健康 14、其他 11。253/253 實際 HTTPS GET 200、PDF 可開啟、頁數及第1頁可讀，0 失敗。179 份首頁有日期證據；其中178份可採用版本標示，1份日期晚於查核日而待確認。另74份未有可採用版本標示。後兩類主 `version:null`，不同原因分開標示。
- a314 主頁所連 33 個有 PDF 副檔名的理賠／服務網址皆 GET200/PDF有效；另實查無 PDF 副檔名的 `/claim_union_agreement`，共 34 個 PDF 網址。15 個 HTML 入口亦實讀 GET200。
- 8 則 FAQ 由已核對 a314 及 PDF 內容整理，每則含可解析 `source_ids` 與實際官方出處；PDF 來源頁碼目前皆第1頁。
- 所有 URL 限 HTTPS `life.cardif.com.tw`，官方來源清單及研究讀取的每一轉址皆檢查主機、port、userinfo。執行期查詢只讀封存資料，沒有任意 URL 抓取。

## 兩個完整代碼的查核界限

`IHI_C_1131001`、`IHO_1131001`：未在已實查官方頁、PDF 文字或 metadata 找到完整代碼的官方對照，故均為 `unverified`、`product_name:null`、`versions:[]`。不能把附件使用的代碼、檔名或日期相近視為完整對照成功。

可供參考且獨立標示的 `candidate_sources`：

- IHI：法商法國巴黎人壽住院醫療保險（甲、乙、丙型），官方 a321 的 `IHI_VIE.pdf`，4 頁；第1頁載113年10月1日逕修，頁內函號11304207572。`asset_code` 為公開檔名，不是已核對的商品完整碼。
- IHO：法商法國巴黎人壽住院醫療暨門診給付健康保險附約，官方 `VIE_IHO.pdf`，4 頁；第1頁同載113年10月1日逕修及11304207572函。不同條款分別保留來源與版本，不混成同商品。

官方索引目前可讀的公開條款，不代表完整歷史保單版本，也不證明某位保戶投保的是該條款。未支援險種一律只供文件查詢，不產生準備清單，不判保障、資格、金額或送件結果。

## 證據檔

- `library-products-index-verified.json`：253 筆原始來源、GET 狀態、SHA256、頁數、首頁全文、metadata 及版次證據。
- `library-products-verification.json`：IHI/IHO 特定條款實查與完整碼搜尋結果。
- `library-claims-verification.json`、`library-pages-verification.json`：34 個理賠 PDF 與 HTML 查核。
- `library-claims-*.txt`、`library-page-*.html`：公開原文證據。
- `library-build-summary.json`：實際分類數量。
- `library-red.txt`：新增查詢模組缺少時的15項失敗。
- `library-green.txt`：15項單元測試通過。
- `library-future-version-red.txt`、`library-document-type-red.txt`：來源獨立審查所見兩項資料缺陷之實際RED。
- `library-regression-final.txt`：最終17項目錄測試＋6項官方規則回歸共23 PASS。

TDD 研究修正：最初測試假設完整 IHI 碼已在官方存在，研究證據否定此假設後改測：`IHI_VIE` 檔名可大小寫搜尋，完整未驗碼不被臆造。這不是放寬完整碼驗證；完整碼查無依據時必須繼續未驗證。

獨立審查修正：`COIAUTO_Provision` 官方首頁載115年12月31日（晚於2026-10-26查核日），同頁又列115年1至8月歷程。未判定官方誤植或自行更正年份；主版次與日期改null，`version_status:requires_confirmation`，保留原文 `version_evidence`，`version_note` 提醒向官方確認。身故／完全失能應備文件及安心陪伴分別改 `pdf_requirements`／`pdf_guide`，避免誤作空白表單。

全專案最終整合與瀏覽器驗收由主代理執行；本子任務沒有為通過測試呼叫真模型或既有案件。
