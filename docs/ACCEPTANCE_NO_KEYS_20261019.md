# 2026-10-19 無金鑰範圍完整驗收

**結論：本輪不含外部生成式 LLM 的完整驗收通過。** 使用者明確選擇「暫不建立金鑰」，三家真實憑證設定與真 LLM 串接維持 BLOCKED；不將本報告當成 Phase 2／3 整體閘門或整案完成。

本輪執行的是同一版前後端 `f41d74d71f6745e0fca78b1d48359a389ca75a1e`，未修改產品程式、測試、依賴或官方 registry。僅補上空白供應商欄位、修正過時文件並保存新證據。未建立／寫入真實金鑰、未改帳號或方案、未送出任何模型請求。

## 本輪實跑結果

| 範圍 | 結果與證明界線 |
| --- | --- |
| 後端完整 pytest | **190/190 PASS，69.07秒**；AI113、OCR28、API／規則／保存49，fail／error／skip均0；外部Adapter只用離線MockTransport |
| 前端單元 | **33/33 PASS**，0 fail／skip |
| 三尺寸 Mock | **75/75 PASS，1.6分鐘**，1440／768／390各25；雙入口、六條件／新案、文件狀態、重試、競態、焦點、列印事件、axe與非預期console檢查 |
| PDF | **2/2 PASS，7.4秒**；超頁／損毀拒絕、換檔恢復、實際canvas換頁與結果回焦 |
| 三尺寸真 API | **27/27 PASS，1.8分鐘**；每尺寸9項，真PDF／RapidOCR／品質前檢／mixed、來源問答、保存／隔離／條件、人工確認、摘要及錯誤恢復 |
| 官方表單受控故障 G | **1/1 PASS，4.1秒**；注入外部PDF載入失敗後，實際API案件與摘要仍可使用；不是官方站台當時故障的證據 |
| 公開 HTTPS | **HTTP22 checks PASS，瀏覽器3/3 PASS／36.4秒**；雙入口、真圖片OCR、PDF／mixed第2頁、摘要與保存；安全cookie、CSP、origin403、私有路徑404、owner隔離與刪除 |
| 容器真實運行 | **60 checks PASS，瀏覽器1/1 PASS／9.6秒**；本輪重用既有已建置映像，沒有宣稱重新build |
| 容器持續性 | 真正restart後同cookie讀回案件完全一致；DELETE後GET404。UID10001／唯讀rootfs／capdropALL／no-new-privileges，含新版介面且無私有開發檔 |
| 官方來源 | **11/11 GET HTTP200、可讀**；1HTML＋10PDF，型別、頁數、既有印載版本及主要規則檢查通過；首頁10/10完整PDF網址仍相同，兩份指南手術條件仍在第3頁 |
| 依賴安全 | pip-audit2.10.1真查PyPI **33/33、0known／0skip**；npm audit全88依賴各嚴重度0；pip check通過，runtime與constraints一致，依賴檔SHA未變 |
| 憑證隔離 | 隔離Vite build exit0／1.99秒；以4個合成值掃描207個產物檔，**0洩漏**。三家合成預留值不會啟用模型，runtime仍grounded_rules／configured=false／verified=false |

所有瀏覽器成功結果均保留實際狀態、安全與檔案斷言；真API業務結果未替換成Mock。合成案件皆清除，沒有真保戶資料或理賠送件。列印只測瀏覽器事件與print media，未操作實體印表機或系統存檔視窗。

本輪重新檢視桌面首頁、手機工作區及平板真品質預檢畫面，未見必要版面修復；三尺寸overflow、axe與非預期console／pageerror斷言通過。手機截圖含建立成功的短暫toast，不把它當成穩定版面或新的文字量測；減字前後量測仍以[先前UI驗收](UI_SIMPLIFICATION.md)為準。

## 可重現命令與運行隔離

```powershell
.venv/Scripts/python.exe -m pytest backend/tests -q --tb=short --basetemp=.local/acceptance-no-keys-20261019/backend/pytest-temp-run1 --junitxml=.local/acceptance-no-keys-20261019/backend/junit.xml
npm test
node node_modules/@playwright/test/cli.js test -c playwright.config.js --reporter=line
node node_modules/@playwright/test/cli.js test -c playwright.pdf.config.js --reporter=line
node node_modules/@playwright/test/cli.js test -c playwright.api.config.js --reporter=line
node node_modules/@playwright/test/cli.js test -c playwright.demo.config.js --reporter=line
.venv/Scripts/python.exe scripts/smoke_api.py --base-url http://127.0.0.1:8004 --include-ocr
```

完整精確命令、output參數與原始log在 `.local/acceptance-no-keys-20261019/`。瀏覽器使用既有Chromium executable；Mock沿用5174。真API使用單worker的獨立8003、專用合成SQLite、rate1000、精確本機origin；測試子程序移除真金鑰環境。pytest、API／公開OCR、容器OCR依序執行，未以並行資源競爭取代功能驗證。

容器映像為 `cardif-claim-preparation:ux-20261019`／`sha256:b25049ed997c4d2167562056356dbed1d464cb8112918740d3cde3fc3c3130af`，產品及Docker輸入未改，故重用既有映像；新的容器 `paris-claim-no-keys-20261019`、volume `paris_claim_no_keys_20261019` 只綁loopback8004。完成並核對識別後已清除此容器／volume與8003測試程序，保留映像、公開8002及隧道；未操作其他8000／3137服務。

## 保存的證據

- [測試數與範圍摘要](evidence/acceptance-no-keys-20261019/test-summary.json)
- [來源摘要](evidence/acceptance-no-keys-20261019/sources-summary.json)、[逐來源HTTP與檢查](evidence/acceptance-no-keys-20261019/source-check-results.json)、[引用頁碼](evidence/acceptance-no-keys-20261019/page-relevance-results.json)
- [依賴覆蓋與輸入核對](evidence/acceptance-no-keys-20261019/dependency-verification.json)、[PyPI結果](evidence/acceptance-no-keys-20261019/pip-audit-runtime.json)、[npm結果](evidence/acceptance-no-keys-20261019/npm-audit.json)
- [建置隔離](evidence/acceptance-no-keys-20261019/build-key-isolation.json)、[預留值不啟用模型](evidence/acceptance-no-keys-20261019/runtime-key-isolation.json)
- [公開HTTP](evidence/acceptance-no-keys-20261019/public-http.json)、[容器runtime](evidence/acceptance-no-keys-20261019/container-runtime.json)、[容器smoke](evidence/acceptance-no-keys-20261019/container-smoke.json)、[重啟與清除](evidence/acceptance-no-keys-20261019/container-persistence.json)

完整JUnit、Playwright log／截圖／狀態及掃描stdout保留於忽略版控的 `.local/acceptance-no-keys-20261019/`；沒有提交cookie、DB、原始官方PDF或任何金鑰。原HTML及備份SHA256仍相同：`59a6fd5053e9811560823b3f12637ef0c7bbe7f3aa2fd9a1abe1ea90fad1c8a1`。

## 失敗、限制與未完成項目

本輪功能測試首輪全部通過，未改測試或放寬斷言。依賴掃描初次在預設沙箱因DNS解析失敗exit1，未算通過；保留sandbox原始輸出，正常升權網路重跑後兩掃描均exit0。pytest有1項既有Starlette／httpx棄用警告，沒有為消除警告改動依賴。

漏洞掃描只覆蓋當時資料庫已知套件漏洞；未掃基底OS或驗證wheel下載hash，不等於正式資安認證。官方來源沒有10/17完整body hash，故本輪檢查相符不等於逐位元相同。既有冷啟OCR逾時、單worker限制與未明上游例外仍見[已知限制](KNOWN_LIMITATIONS.md)，不因本輪通過而宣稱根治。

三家真實金鑰均未建立／保存或驗證，Gemini／OpenRouter相容性及模型回覆未測；[供應商狀態](PROVIDER_SETUP.md)逐項列明。P2-04、P2-09與P3-GATE維持BLOCKED，待使用者稍後安排，不再詢問金鑰。設定存在與離線測試不構成真模型完成。

公開展示：[理賠文件準備助手](https://retirement-trim-reported-jesus.trycloudflare.com/?service=api)。結束前health再次為ok，llm_verified=false；臨時網址仍需電腦與程序保持運行。
