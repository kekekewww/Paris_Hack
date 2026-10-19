# 引導類型選擇與清單建立

日期：2026-10-19（臺灣）。狀態：**DONE（本次修正範圍）**。新版流程已發布至[臨時展示網址](https://retirement-trim-reported-jesus.trycloudflare.com/?service=api)，本機、公開流程與新版容器驗收均通過。使用者指出描述後的「可能相關類型」看似讓人選擇，卻只有立即建立清單的按鈕，意圖不清楚。

## 本次操作流程

1. 送出描述，取得服務提供的可能類型。
2. 以具名原生radio選擇一種類型；即使只有一個候選也不預選。
3. 使用者可改選。獨立按「建立文件清單」後，才送出目前類型及這次回覆的條件，進入工作區。

候選只使用服務回覆，不因介面需要而虛構額外相關類型；其他既有類型在「選擇其他類型」展開區。維持單一類型／單一清單，不新增多類合併或保障判定。服務提供的建議不代表個別保單適用、資格或給付。

## 狀態與相容性

- 選取只改前端草稿，不呼叫updateCase，不提早產生文件清單。引導描述時既有空白intake案件可保存對話，與已選類型清單分開。
- 新描述、新回覆、案件切換與重新載入不沿用舊候選選取。
- 建立前須有合法catalog類型且非busy；重試綁定案件、回覆、類型及條件快照，改選或新回覆會作廢舊重試。
- 保留原生radio鍵盤互動、可見焦點、展開區、手機點擊範圍及既有品牌樣式。
- 不改後端規則、Mock Service或API Contract，不建立金鑰、不啟用外部LLM。

## 驗收條件

以「車禍後住院三天，沒有手術。」重現舊問題。確認類型未預選，建立按鈕不可用；選取或改選仍留在引導頁，案件類型空、文件空；獨立建立後才依所選類型產生清單。另檢查重述／重新載入／錯誤重試、鍵盤及三尺寸、真API及公開展示。

## 實際驗證

| 驗證 | 本輪結果 | 範圍 |
| --- | --- | --- |
| 舊版RED | 單元18項中4項失敗；瀏覽器指定情境1項失敗 | 缺少radio、獨立建立與選取狀態，證據保留，沒有把預期失敗隱藏 |
| 前端單元 | 36/36 PASS，主代理重驗276.9毫秒 | components18及service18；TDD細節見[紀錄](guided-choice/unit-tdd.json) |
| 引導針對性瀏覽器 | 9/9 PASS，17.9秒 | 選取、追問、失敗重試、重新整理、惡意輸入及無障礙 |
| 完整Mock瀏覽器 | 87/87 PASS，1.9分鐘 | 1440／768／390各29項；首頁、工作區及引導選擇通過axe；非預期console／pageerror與橫向溢出斷言通過 |
| PDF專用回歸 | 2/2 PASS，7.3秒 | 合法、損毀、超頁與恢復，保留檔案及canvas斷言 |
| 正式前端建置 | PASS，2.00秒 | 新版已寫入dist，沿用既有公開服務 |
| 真實API三尺寸 | 27/27 PASS，1.9分鐘 | 每次選取／改選後實際GET仍為空類型及空文件，期間0 PATCH／analysis；獨立建立才1次正確PATCH，保留真OCR／PDF／安全／來源／摘要與刪除斷言 |
| G受控官方PDF故障 | 1/1 PASS，3.8秒 | 真案件與摘要仍可使用；不表示官方網站當時故障 |
| 公開HTTPS HTTP | 23 checks PASS | 新版bundle、真API、cookie／origin／私有路徑與合成案件隔離／刪除；[結果](guided-choice/public-http.json) |
| 公開HTTPS瀏覽器 | 3/3 PASS，51.6秒 | 新引導、直接選擇、真RapidOCR、文字／mixed PDF、人工覆核、摘要及reload，測試案件均刪除 |

新版容器實際build exit0，tag為cardif-claim-preparation:guided-20261019，image ID為`sha256:8380799888f4d4783df2815292e833c77ec77a281ad721bcf5de42fed50434f0`。60 checks PASS、cleanup=VERIFIED_DELETED；新引導瀏覽器1/1 PASS（11.3秒），真restart後同cookie案件完全一致、再刪除404。UID10001、唯讀、capdropALL、no-new-privileges及私有檔排除通過。專用8003測試程序、8004容器與volume已核對身分後清除，公開8002／隧道與映像保留。[測試總表](guided-choice/test-summary.json)、[容器metadata](guided-choice/container-runtime.json)、[smoke](guided-choice/container-smoke.json)、[重啟保存](guided-choice/container-persistence.json)及[清理](guided-choice/cleanup.json)保留實際結果。

新版增加四項三尺寸情境：選取與鍵盤改選不建立；新描述立即清選取；失敗後改選作廢舊重試；建立前reload清選取、建立後reload保留案件。既有重要斷言未放寬。純前端選取不寫入案件；建立前的空白intake僅保存對話。

本輪未改後端、服務層、官方規則、來源registry或依賴；前一輪[後端190項、官方來源與依賴驗收](ACCEPTANCE_NO_KEYS_20261019.md)是未變更範圍的歷史證據，沒有宣稱本輪重跑。真API以實際HTTP與合成文件驗證，Mock另列；未建立或使用外部模型金鑰。整體P2／P3閘門仍待真LLM。

獨立源碼與文件覆核未發現需修正問題，範圍限於本次引導互動及證據一致性。159個本地文件連結均存在、80個來源／測試／文件檔未檢出憑證格式，git diff空白檢查通過；這些基本檢查不等同正式資安認證。原HTML與基準備份實際SHA256皆為 `59a6fd5053e9811560823b3f12637ef0c7bbe7f3aa2fd9a1abe1ea90fad1c8a1`。

## 視覺與保存

以同一描述實際操作，等待有限動畫結束後擷取三尺寸；主代理目視桌面／平板未選取及手機已選取畫面通過，沒有橫向溢出或pageerror。[量測](guided-choice/visual-checks.json)保留逐尺寸結果。新版延續綠色／薄荷色、圓角與原生可見焦點，沒有引入框架或額外UI依賴。

| 桌面：未選取 | 平板：未選取 | 手機：已選取 |
| --- | --- | --- |
| [畫面](guided-choice/desktop-unselected.png) | [畫面](guided-choice/tablet-unselected.png) | [畫面](guided-choice/mobile-selected.png) |

完整RED、trace、測試輸出、修改前圖與六張穩定新版圖在 `.local/guided-choice-20261019/`；可分享截圖及去敏感JSON在本文件相鄰目錄。原始HTML及基準備份不更動；不提交案件DB、cookie或憑證。公開連結仍需電腦與隧道程序持續執行。
