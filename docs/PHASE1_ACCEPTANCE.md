# Phase 1 前端驗收報告

驗收日期：2026-10-17（臺灣）  
結果：**通過 Phase 1 前端驗收，可依專案計畫進入 Phase 2。**

此結論限於前端與 Mock Service。對話及 OCR 結果有明確模擬標示，不代表真實 LLM、OCR、FastAPI 或正式理賠送件已完成。

## 執行結果

| 檢查 | 結果 | 證據 |
| --- | --- | --- |
| Playwright 全套 | **63 / 63 通過，0 失敗，約 2.5 分鐘** | `tests/e2e.spec.js`；程序 exit code 0 |
| 桌面 1440 × 1000 | 21 / 21 通過 | project `desktop-1440` |
| 平板 768 × 1024 | 21 / 21 通過 | project `tablet-768` |
| 手機 390 × 844 | 21 / 21 通過 | project `mobile-390`；包含觸控／行動裝置設定 |
| 前端單元測試 | **20 / 20 通過，0 失敗、0 跳過** | 本輪執行 `npm test`，exit code 0 |
| 瀏覽器 JavaScript | 63 個案例均無 `pageerror` 或 console error | 每個案例收集並斷言錯誤陣列為空 |
| 自動無障礙檢查 | 三尺寸首頁及工作區均 0 違規 | axe 的 `wcag2a`、`wcag2aa`、`wcag21aa` 規則；未排除規則 |
| 橫向溢出 | 三尺寸主要流程通過 | 檢查主文件與開啟中的文件檢查 dialog 的 scrollWidth / clientWidth |
| 原始 HTML 保存 | 原始檔與備份 SHA256 一致 | `docs/baseline/original.html` 與根目錄原始 HTML |

原始檔及備份 SHA256：

```text
59A6FD5053E9811560823B3F12637EF0C7BBE7F3AA2FD9A1ABE1EA90FAD1C8A1
```

測試環境為 Windows、Node.js 22.17.0、npm 11.4.2、Vite 6.4.4、Playwright 1.56.1、axe Playwright 4.10.2。實際瀏覽器使用本機既有 Chromium headless shell build 1248。

本輪實際命令如下。此機 PowerShell 的 npm 參數轉送會誤吞額外 CLI 參數，因此完整套件直接呼叫 Playwright CLI：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH = 'C:\Users\kevin\AppData\Local\ms-playwright\chromium_headless_shell-1248\chrome-headless-shell-win64\chrome-headless-shell.exe'
node node_modules/@playwright/test/cli.js test
npm test
```

`playwright.config.js` 會啟動／重用 `http://127.0.0.1:5174` 的 `npm run dev`，使用 3 workers。本輪沒有開啟失敗重試。其他環境可安裝 Playwright 對應的 Chromium，或用同一環境變數指定可用執行檔；本機曾嘗試下載對應 build 1194，但因 CDN 速度過慢取消，未將下載視為成功。

## 每種尺寸均驗證的 21 個案例

1. 首頁兩個入口、官方入口及展示原型聲明。
2. AI 引導描述、確認類型、共用工作區、未完成摘要及返回修改。
3. 資訊不足先追問，補充後才提供類型確認。
4. 送出引導後返回首頁，延遲回覆不覆蓋目前畫面，hash 與畫面一致。
5. 快速選擇住院醫療，建立案件、查看摘要並下載實際檔案。
6. 快速選擇醫療門診，完成相同流程。
7. 快速選擇防癌或重大疾病，完成相同流程。
8. 上傳合成圖片、顯示缺漏情境、預覽、點選位置框線、人工確認、關閉後同步清單。
9. 完整情境顯示初步檢查結果，沒有核准／給付保證。
10. 分析途中關閉視窗，完成後仍更新原文件狀態，沒有 TypeError。
11. 重新選檔會清空舊結果；分析時禁止更換檔案／情境，完成後恢復。
12. 模糊情境顯示低信心與人工確認需求。
13. 不支援格式被拒絕，重新選擇有效檔案後能完成分析。
14. 超過 10 MB 的檔案被拒絕。
15. 模擬服務失敗有錯誤與重試，重試後能恢復對話。
16. 重新整理保留案件；清除案件後重新整理不再提供舊進度。
17. 文件自行備妥／條件不適用狀態可更新、保存並反映於摘要。
18. 工作區對話附官方來源，資格與給付問題保留不確定性。
19. 惡意 HTML 輸入以純文字顯示，不執行事件。
20. 助手收合／開啟、鍵盤 Enter 操作、Escape 關閉 dialog 並返回原操作焦點。
21. 首頁與工作區的 axe 自動無障礙檢查。

摘要測試會讀取下載檔案，確認含所選類別、官方入口與非核准聲明，不只檢查下載事件。三個競態案例使用 Playwright Clock 控制延遲，避免以固定等待或機器速度掩蓋問題。

## 設計延續與視覺證據

完整原型盤點見 [PROTOTYPE_AUDIT.md](PROTOTYPE_AUDIT.md)。原始的品牌綠 `#00875A`、薄荷背景、白色大圓角卡片、膠囊按鈕、綠色線型圖示、頁首 Logo、雙入口卡片、免責頁尾與鳥形水印均得到延續。小字標籤改用既有深綠 `#006B46`，改善淡綠底色上的文字對比。

已實際檢視桌面工作區／OCR 畫面、手機工作區／摘要與 390px OCR 畫面。桌面保留案件導覽、文件與助手三區；手機改成單欄，沒有維持固定桌面側欄寬度。文件 dialog 可內部捲動，操作及框線未造成橫向裁切。

可保存的基準與階段截圖：

- [原始桌面首頁](baseline/desktop-home.png)、[原始手機首頁](baseline/mobile-home.png)。
- [原始桌面引導](baseline/desktop-assistant.png)、[原始手機引導](baseline/mobile-assistant.png)。
- [Phase 1 桌面工作區](baseline/phase1-desktop-workspace.png)。
- [Phase 1 手機工作區](baseline/phase1-mobile-workspace.png)、[手機摘要](baseline/phase1-mobile-summary.png)。

本輪自動化額外在 `test-results/` 產生三尺寸各自的 `landing.png`、`guided-workspace.png` 與 `ocr-findings.png`；HTML 報告在 `playwright-report/index.html`。這兩個目錄為執行產物、受 `.gitignore` 排除，後續測試可能覆寫。

## 已發現並修正的失敗

| 發現 | 修復與回歸證據 |
| --- | --- |
| 初次初始化 render 覆寫已輸入內容 | 初始化期間控制入口／初始畫面，避免草稿遺失；雙路徑及追問在三尺寸通過 |
| 淡綠底的小字品牌綠對比約 4.18／4.34，低於 4.5 | 小字標籤沿用深品牌綠；全尺寸 axe 通過 |
| axe 在 200ms 漸入動畫途中採樣，暫時得到 4.43 對比 | 測試等待實際有限動畫 finished 後掃描；沒有固定 sleep、隱藏元素或排除規則 |
| 分析後立即關閉視窗，背景清單停在尚未準備 | 先有失敗案例，再修正非同步結果與清單同步；三尺寸回歸通過 |
| 延遲引導回覆令首頁 hash 與畫面不一致 | 先重現後修正回覆更新條件；三尺寸 Clock 回歸通過 |
| 換新檔仍保留舊分析與可確認按鈕 | 選檔失效舊結果，分析期間鎖定輸入；三尺寸回歸通過 |
| OCR 測試原本誤選隱藏的 select option | 將斷言限制於分析結果區；仍檢查實際文字、位置框線與人工確認 |
| 追問測試原本誤把初始說明當回覆 | 改等待引導對話 log 中的實際追問，再輸入下一則訊息 |

早期完整執行曾為 33 / 48、之後為 53 / 54；上述失敗均保留於開發紀錄，未以跳過或弱化斷言宣告完成。最後一輪為 **63 / 63 全數通過**。

## 契約、來源與階段限制

- [API_CONTRACT.md](API_CONTRACT.md) 已定義版本端點、案件／條件、文件必要性與準備狀態、結構化對話、分析位置、來源及錯誤語意；Mock 與 HTTP adapter 使用相同介面。
- [OFFICIAL_SOURCES.md](OFFICIAL_SOURCES.md) 記錄已查核官方頁面與 PDF、版本及歧義；資料索引為 `data/official-sources.json`。前端沒有依文件名稱拼湊官方 URL。
- 本輪瀏覽器流程明確使用 `?service=mock`。HTTP adapter 的 Request／Response 合約單元測試不算真實 FastAPI、LLM 或 OCR 整合驗收；Phase 2 必須另以實際請求驗證。
- 上傳測試使用合成 PNG，只驗證前端預覽、驗證及模擬情境，不宣稱從圖片辨識到欄位。Mock 不解析 PDF 頁數；真正後端須硬性執行最多 10 頁與處理時間限制。PDF 原生預覽亦受瀏覽器能力影響。
- Mock 資料位於同分頁 sessionStorage，不保存原始 Blob；重新整理需重新選檔以恢復預覽。案件可刪除。
- axe 結果只涵蓋列出的首頁／工作區與規則集；鍵盤測試涵蓋核心操作，並非完整人工無障礙認證。
- 本階段沒有正式送出理賠，也未完成外部部署。下一階段應依相同契約建立 FastAPI、規則／RAG、Provider 與真實 OCR，保留 Mock 供測試展示。
