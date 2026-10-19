# 介面減量與操作層級驗收

日期：2026-10-19（臺灣）。**UX-20261019 已驗收並發布到原 Quick Tunnel。** 使用者切換模型後，自動審核與瀏覽器執行恢復；先前容量阻礙已解除。整案的真外部 LLM 仍依使用者決定稍後設定，不將本次介面驗收當成 Phase 2／3 全部通過。

## 設計與功能

依使用者提供的 [apple-design skill](https://github.com/emilkowalski/skills/blob/main/skills/apple-design/SKILL.md)，採用明確操作層級、相鄰操作、漸進揭露與克制動態。延續原 HTML 的品牌綠、薄荷底、雙入口、圓角及裝飾；維持 Vanilla ES Modules 與既有 API Contract，沒有新增 UI 或動畫依賴。

- 首頁用「描述我的狀況」「選擇理賠類型」直接命名操作。取得單一建議後，「確認並建立清單」接手主要操作。
- 先選理賠類型，再顯示三項常用條件；其餘條件可展開，手術／重大疾病相關條件會適時展開。切換類型保留當次草稿，新案件不沿用舊案條件。
- 工作區預設收合助手，只突出第一份未完成文件；有分析結果的文件使用單一「查看檢查結果」操作。所有文件完成後，摘要成為主要操作。
- 官方空白表單可直接開啟；來源、文件說明、自行備妥與案件管理可展開。重要的待確認、模擬、未執行 OCR 與人工覆核提示維持可見。
- 結果頁先呈現文件與問題，辨識細節及來源可展開；點框線會展開並聚焦對應提醒。人工確認不會抹除缺漏或變成核准。
- 服務模式、資料保存與展示工具集中於服務說明；Mock 仍明示模擬，grounded_rules 明示非生成式 LLM。
- 修復 skip-link 誤觸 hash router；列印暫時展開摘要條件，列印後恢復，重複 beforeprint 不覆蓋原狀態。

## 真實畫面與量測

以當時仍運行的舊版 dist 作 before、Vite 新版作 after，在 1440×1000、768×1024、390×844 各擷取五種狀態，共 30 張新截圖。等待入口 enabled、有限動畫結束、toast 消失才擷取。另由獨立代理檢視五組前後畫面，根代理重看穩定後三尺寸及真 API 的品質／mixed 結果；未見必須修復的版面問題。

同一 Mock 住院／疾病／無手術／實支實付案例的全頁可見 DOM 文字量如下，三尺寸相同：

| 狀態 | 舊版 | 新版 | 減量 |
| --- | ---: | ---: | ---: |
| 首頁 | 136 | 117 | 14.0% |
| 尚未選類型 | 375 | 102 | 72.8% |
| 選擇類型後的條件 | 376 | 156 | 58.5% |
| 文件工作區 | 814 | 442 | 45.7% |

排除空白、讀屏專用內容、收合 details 內容與短暫 toast；這是指定案例的可見文字量，不是所有情境或可用性研究。工作區實心綠按鈕由 10 個變為 1 個。各狀態三尺寸皆無橫向溢出。dialog 捲動位置不同，不將其文字量納入減量百分比。

[量測資料](ui-simplification/metrics.json) · [桌面首頁](ui-simplification/desktop-home.png) · [桌面工作區](ui-simplification/desktop-workspace.png) · [平板工作區](ui-simplification/tablet-workspace.png) · [手機工作區](ui-simplification/mobile-workspace.png)

## 最終實跑結果

| 驗證 | 結果 |
| --- | --- |
| 前端單元 | **33/33 PASS**，元件15／service18，root 重跑 exit0 |
| 三尺寸 Mock | **75/75 PASS，1.5 分鐘**，各25項；axe／console／pageerror 原斷言通過 |
| PDF | **2/2 PASS，9.4 秒**；超頁／損毀拒絕、有效檔恢復、canvas 換頁、單一結果操作與回焦 |
| 三尺寸真 API | **27/27 PASS，1.7 分鐘**，單 worker、專用8003與合成DB，真 PDF／RapidOCR／品質前檢／mixed、保存／隔離／摘要／故障恢復 |
| 外部表單受控失敗 G | **1/1 PASS，4.1 秒**；實際 API 案件與摘要不受注入的官方 PDF 載入失敗影響，不代表官方網站當時故障 |
| 正式建置 | **exit0，1.79 秒**；Mock／PDF／視覺 gate 通過後才更新 dist |
| 公開 HTTPS HTTP | **22 checks PASS**；新入口與 JS、安全 cookie／CSP／origin、私有路徑404、owner隔離與建立／刪除 |
| 公開 HTTPS 瀏覽器 | **3/3 PASS，46.8 秒**；兩入口、缺漏／清晰 PNG 真 OCR、PDF／mixed 第2頁、人工確認、保存與摘要；console／pageerror0、案件均清除 |
| 新版 Docker 交付 | image `b25049ed…` 建置exit0；容器真API／OCR **60 checks PASS**、新版瀏覽器 **1/1 PASS（11.9秒）**；UID10001／唯讀／capdropALL／無私有檔，驗收container／volume已清，映像保留 |
| 原始設計 | 原 HTML 與備份 SHA256 仍同為 `59a6fd5053e9811560823b3f12637ef0c7bbe7f3aa2fd9a1abe1ea90fad1c8a1` |

主要命令：`npm test`、`npm run build`；Playwright 直接以 `node node_modules/@playwright/test/cli.js test -c <config>` 執行，使用已安裝 Chromium executable。Mock 使用 playwright.config.js、PDF 使用 playwright.pdf.config.js、真 API 使用 playwright.api.config.js、G 使用 playwright.demo.config.js。真 API 對 8003，公開流程對本次精確 HTTPS origin；沒有把 API 成功結果替換成 Mock。

忽略版控的完整輸出保存在 `.local/ui-simplification/`：`mock-final-results`、`pdf-results`、`api-results`、`demo-results`、`public-results` 的 `.last-run.json` 均 passed／failedTests 空；`public-http.json` 保存 HTTP 檢查。前後圖及 metrics 在 before／after。事件 VM 4/4 與 --list 只作先前有限檢查，不替代上述真瀏覽器結果。

## 失敗歷程與界線

前一工作階段：自動審核服務對升權本機網路檢查及標準 Playwright browser_navigate 回報 `Selected model is at capacity`，動作未執行；沒有繞過審核、冒稱執行成功或發布未驗證 UI。當時只完成單元、隔離 build 與原始碼事件檢查；git add 亦因預設沙箱 index.lock 權限而未成功。使用者切換模型後，本輪已透過正常升權路徑恢復驗收。

本輪首個 Mock：72 pass／3 fail（1.6 分鐘）。首頁測試未等初始化完成即展開服務說明，footer 重繪後收合；補 enabled 等待後 targeted 3 fail（6.2 秒）揭露巢狀 summary 定位不唯一。改為精準「服務說明」定位後 targeted 3/3（4.7 秒），再完整75/75通過。只修測試 readiness／定位，未改產品或放寬聲明可見斷言。失敗 trace 留在 mock-results、mock-targeted-results，成功 targeted 在 mock-targeted-v2-results。

本輪未改後端規則、來源或依賴，沒有重跑先前190項後端測試／依賴掃描並冒稱新結果。列印已驗證瀏覽器 beforeprint／afterprint 及 print media；未操作作業系統實體印表機或存檔對話框。

展示網址：[理賠文件準備助手](https://retirement-trim-reported-jesus.trycloudflare.com/?service=api)。臨時網址需電腦與程序保持運行。`llm_verified=false`，真外部生成式模型驗證與整案閘門仍 BLOCKED；不再向使用者索取金鑰。
