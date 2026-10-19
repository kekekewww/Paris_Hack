# 本機最終驗收與外部依賴

> 最新OpenRouter交付（2026-10-19）：真實免費路由已啟用，原訂MVP的P2／P3整體gate已通過。最終後端293、本機三尺寸成功證據（原2pass1fail＋平板重驗1pass）、容器56checks真OCR／live1／restart及公開live1／HTTP23均完成。免費限流與額外CLI未通過仍保留，完整結果以[OpenRouter驗收](OPENROUTER_ACCEPTANCE.md)為準。以下舊版「未驗證／BLOCKED」為當時歷史，已由新授權與實測取代。

> 最新引導修正（2026-10-19）：先以具名radio選類型、再獨立建立清單，已發布。單元36、三尺寸Mock87、PDF2、真API27、G1、公開HTTP23／browser3（51.6秒）及新版容器60checks／引導browser1（11.3秒）與真restart均通過。[完整報告](GUIDED_CHOICE.md)含新版映像、截圖與去敏感結果；下方先前輪次保留為歷史，不混稱目前版本。外部LLM仍未驗證。

> 最新續驗：使用者暫不建立金鑰；2026-10-19已完成[無金鑰完整驗收](ACCEPTANCE_NO_KEYS_20261019.md)，後端190／前端33／Mock75／API27／PDF2及公開、容器、來源與依賴重掃皆通過。三家實際金鑰與真模型整合未執行，P2／P3整體gate仍BLOCKED；下方歷史各輪數字不混用。

> 2026-10-19 介面簡化已完成並發布：單元33/33、三尺寸Mock75/75、PDF2/2、真API27/27、故障恢復G1/1；公開HTTP22與瀏覽器3/3通過。三尺寸視覺、無障礙與console檢查通過，詳見[新版驗收](UI_SIMPLIFICATION.md)。下方10/17數字與映像均保留為當時版本歷史；整案仍待真外部LLM。

更新日期：2026-10-17（臺灣）。**可展示的本機原型已通過必要本機驗收；目前沒有待執行的必要本機測試。本輪另已通過Quick Tunnel臨時公開HTTPS驗證；Phase 2／3整體與整案仍因真外部LLM依賴維持BLOCKED，未宣稱全部完成。**

使用者已選擇「先完成其餘工作，金鑰稍後設定」。不再次要求金鑰，不建立或沿用未授權憑證，不以Mock、本機規則或離線transport當作真模型請求完成。

## 階段與任務結論

| 範圍 | 結論 | 證據／依賴 |
| --- | --- | --- |
| Phase 1 | DONE | 原63/63與20/20通過；最終source freeze後Mock63/63、前端24/24，延續原HTML設計 |
| Phase 2本機核心／OCR／HTTP | DONE | 後端190/190、品質6/6、最新真API27/27；P2-06／08本機範圍結案 |
| 真外部LLM與Phase 2整體 | BLOCKED | P2-04尚無真provider請求證據，P2-09不自動完成；llm_verified=false |
| Phase 3本機交付 | DONE | P3-01／02／03／04B／05／06本機範圍完成；最終image及一般展示服務皆新版60checks PASS |
| 公開HTTPS／Phase 3整體 | 臨時展示DONE／整體BLOCKED | 使用者本輪授權Quick Tunnel，HTTP23＋桌面3/3通過；Phase3整體仍依真LLM gate |
| 整案Completed | 未標記 | 本機DONE不擴張為外部gate已通過；不提供正式理賠送件或核准 |

## 最終本機實測

| 驗證 | 最終結果 | 範圍 |
| --- | --- | --- |
| 後端整套 | **190/190 PASS、31.90秒** | core49＋AI113＋OCR28；LLM transport為離線邊界，非外部模型驗證 |
| OCR個別套件 | **28/28、29.44秒** | 含安全log1項、低品質4guard、mixed逐頁位置；舊23項是歷史 |
| 前端單元 | **24/24 PASS** | 上傳狀態、品質／mixed／provider與信心標示；TDD與回歸 |
| 最後前端build | **PASS、1.76秒** | 品質前檢、mixed page2及最新標示已納入 |
| 新品質／mixed三尺寸 | **6/6、28秒、exit0** | 純預檢未OCR／無欄位、mixed實際文字擷取、page2標記與對應提醒 |
| 最新真實API完整套件 | **27/27、1.9分鐘、exit0** | 1440／768／390各9/9，console0；真RapidOCR、pdf_text、品質前檢、遮罩、canvas、限制、來源、隔離與刪除 |
| source freeze後Mock | **63/63、1.4分鐘、exit0** | 三尺寸各21/21，axe0、console／pageerror0；沒有用舊63項代替此輪 |
| PDF專用回歸 | **2/2、11.3秒、exit0** | 嚴格disabled、損毀／超頁拒絕、合法恢復、canvas與多頁切換 |
| G受控官方文件故障 | **1/1、13.6秒、exit0** | PDF注入ERR_FAILED；真案件JSON未變、工作區及摘要下載仍可用，未攔截本機API |
| 最終Docker build | **PASS、9.3秒、exit0** | 包含安全log、品質前檢、mixed頁碼與UI；完整digest見下方 |
| 最終Docker新版smoke | **60checks PASS、exit0、cleanup=true** | 等HTTPready後首次完整新版執行通過，未發生該輪冷啟timeout |
| 一般展示服務smoke | **60checks PASS、cleanup=true** | RATE120、grounded_rules、1worker，實際本機HTTP及模型預熱完成 |
| 依賴與設計保留 | **通過** | Python33/33零known／零skip、npm88依賴零known、pip check一致；源碼無token，原HTML／備份SHA再次相同 |

本機API細節、trace及三尺寸視覺證據見[API整合驗收](API_INTEGRATION_ACCEPTANCE.md)；原設計與Phase1見[盤點](PROTOTYPE_AUDIT.md)及[原驗收](PHASE1_ACCEPTANCE.md)。G是受控故障，不能當作官方網站當時真的失效或可用性查核。

## 最終映像與目前可展示服務

最終image：

```text
sha256:a7e45621b8284cebe41c57cd0b0cf99d5887d55e4f71dc364effd929be72b7cc
```

新版 `scripts/smoke_api.py --include-ocr` 為60checks；舊39checks均為舊版歷史，沒有混用。最終容器實測：

| 項目 | 結果 |
| --- | --- |
| 缺漏文字PDF | provider=pdf_text、4 findings、非模擬、仍人工確認 |
| 清晰PNG | provider=rapidocr、2 findings、非模擬、仍人工確認 |
| 模糊PNG | provider=quality_precheck、1品質提醒、0欄位，明示未OCR、uncertain |
| mixed PDF | provider=pdf_text、6個遮罩欄位、第2頁品質提醒與box，整體uncertain |
| 權限 | UID/GID10001、rootfs唯讀、capdropALL、no-new-privileges；source不可寫、volume可寫 |
| 隔離與持續性 | owner隔離、同cookie重啟後case完全一致；DELETE後GET404，cleanup確認成功 |
| 私有內容與靜態資產 | image無.env／.venv／demo／tests／docs／.git等；私有HTTP路徑404，worker為javascript／nosniff |
| 清理 | 只清本次專用container／volume，image保留；未影響其他容器 |

完整命令、權限與重啟證據見[容器報告](CONTAINER_ACCEPTANCE.md)。目前[一般展示服務](http://127.0.0.1:8000/?service=api)以RATE_LIMIT_REQUESTS=120、grounded_rules、單worker執行；啟動session35483／PID63012，已通過新版60checks、模型預熱及案件清理。Vite5174／原型5173預覽已停。跨工作階段需重新確認process存活，不把此紀錄當作永久運行保證。

## 品質、頁碼及信心語意

低品質頁先經Pillow實際量測，保守skip模型。全部skip回 `quality_precheck`、`is_simulated=false`、`uncertain`、空 `extracted_fields`，只給image_quality提醒，不捏造空欄位或文件類型。mixed按真正執行的pdf_text／rapidocr回provider，整體仍uncertain；品質finding與box精確對應第2頁，切頁／點框後對應提醒實際可見。

品質提醒連結只標「官方表單參考」，框線為人工提示區，工程threshold不說成官方理賠要求。UI最新用語為**「初步檢查參考信心」**；原「已辨識文字平均信心」不精確，因score含保守cap .49，並非純平均，也不是整檔正確率、完整度或給付機率。純預檢明示未執行OCR、沒有文字信心。

新增第9份 `demo/documents/application-mixed-quality.pdf`（298861bytes），原8份hash未變。DEMO／限制已同步，官方來源索引及依賴版本未改。所有輸入為合成資料，沒有真保戶文件或真實理賠提交。

## 失敗與修復歷程完整保留

| 歷程 | 實際失敗 | 後續與結論 |
| --- | --- | --- |
| API早期整合 | 原生fetch Illegal invocation、Windows worker MIME為text/plain；桌面曾4pass／5fail | 修正fetch綁定、.mjs MIME及觀測方式；未移除瀏覽器安全或真OCR斷言；完整歷程見API報告 |
| 後端首次185項 | **184pass／1 OCR_TIMEOUT、131.13秒**；`test_real_chinese_image_and_scan_ocr[application-clear.png-image/png]`，與Docker build同時 | 獨立序列185/185、106.93秒；其後品質版190/190、31.90秒；不武斷宣稱並行資源即根因 |
| Mock首次63項 | **58pass／5fail、2.2分鐘**；3尺寸超大檔錯誤被覆蓋、2尺寸axe readiness | syncUploadButton控制有效檔／fileChecking／busy；等待入口enabled及實際動畫，無刪WCAG規則；targeted9/9、38.9秒→PDF2→Mock63/63、2.3分鐘→source freeze63/63、1.4分鐘 |
| API中間失敗輪 | **26pass／1fail、4.8分鐘**；tablet blur真503 OCR_UNAVAILABLE，非timeout／busy；desktop／mobile同輪200 | 先前也曾27/27、5.6分鐘；失敗trace／PNG保留。privacy-safe診斷後18/18輪替HTTP未復現，原上游例外原因仍未知 |
| 品質改善後 | Pillow量測不足先skip模型、mixed頁2位置RED→GREEN、安全log及UI語意修復 | OCR28、UI24、品質6及最新完整API27全部通過。品質前置處理並非證明上游cause已根治；列known limitation需監測，不再列為當前待跑本機bug |
| 舊容器啟動時差 | 立即smoke NETWORK_ERROR、0checks | 未計作通過；加入等待HTTPready流程 |
| 舊06078810…冷PNG | HTTPready後45秒OCR_TIMEOUT，前33checks及cleanup成功，但整輪失敗 | 模型載入後同完整腳本39PASS，未提高預算或fake；該39為歷史，不代替新版60 |
| 最終a7e45621… | 等HTTPready後首次新版60PASS，無該輪首次timeout | 舊失敗不抹除，也不保證所有資源條件下永不逾時；一般展示服務亦60PASS |

診斷只記例外class與traceback basename／function／line，不記raw錯誤訊息、原始文件或敏感prompt。後端45秒預算與有意義斷言未放寬；保守品質處理改進有新增TDD與真API證據，清晰／缺漏圖及掃描PDF仍嚴格要求實際RapidOCR。

早期image識別與39項證據保留為歷史：`sha256:08fbfd35c858fc44d46b35d46e6daee1f921a8518a8d8aed2dee1bd3d3a0e115`、`sha256:0607881000e8525ff7aa6a595134a0155d60fff69c97a3315bfb303392a993ea`。目前最終產物以a7e45621…及新版60項為準。

## 已知邊界與外部BLOCKED

- `grounded_rules` 是真本機官方檢索與規則，不是生成式LLM。openai_compatible client及離線測試完成，但未執行真provider請求；`llm_configured`只表示設定齊全，`llm_verified=false`。見[LLM整合](LLM_INTEGRATION.md)。
- 單worker／單app副本；程序內lock／rate不能外推為多程序一致性與並行容量。正式擴充需資料庫版本／CAS及協調。
- Health不是模型readiness；45秒包含匯入、初始化／圖最佳化與推論，無分階段計時或程序硬中止。清晰圖片冷啟timeout仍可能發生，展示前以合成smoke確認；歷史未明模型例外若再發生，依privacy-safe診斷，不宣稱根治。
- OCR／品質檢查只協助準備，簽名及真實性一律人工覆核；原檔不持久保存，結構化結果仍敏感。信心不代表核准或整檔準確率。
- Python33/33零known／零skip、npm88依賴零known及pip check通過不等於正式安全認證、基底OS掃描或零風險。原始證據見[依賴查核](DEPENDENCY_AUDIT.md)。
- 原始HTML及備份最終SHA256相同：`59A6FD5053E9811560823B3F12637EF0C7BBE7F3AA2FD9A1ABE1EA90FAD1C8A1`。官方來源有查核日期，不保證執行期網址永遠可用；助手無理賠送件、資格判定或給付計算。

| 外部項目 | 狀態 | 解除條件 |
| --- | --- | --- |
| P2-04真外部LLM | BLOCKED | 使用者稍後安全配置後端key／模型／受信服務並授權真請求，完成來源及失敗恢復實測 |
| P2-09整體gate | BLOCKED | 真provider通過後，包含該provider的整合實測與Phase2全部閘門 |
| P3-04C公開HTTPS | DONE（臨時展示） | 已透過Quick Tunnel驗證；固定網址／常駐部署不在本輪範圍 |
| P3-04與P3-GATE | 部署DONE／整體BLOCKED | 臨時HTTPS部署已驗證，整案仍待真LLM及其整合閘門 |

## 後續三步

1. 安全配置後端key與明確模型後，執行真provider request、引用與失敗恢復驗證；依使用者決定稍後安排，現在不反覆索取。
2. 以真provider完成整合實測及P2整體gate；現有無key本機範圍已全部驗收，無待執行的本機測試。
3. 本輪Quick Tunnel臨時HTTPS已驗證並保持執行；重啟需新網址與origin複驗。P3整體gate仍等待P2真LLM及其整合驗收。

## 後續：Quick Tunnel臨時公開HTTPS

使用者於同日要求Quick Tunnel分享。實際公開HTTPS HTTP **23 checks PASS**、桌面Playwright **3/3 PASS（39.2秒）**，涵蓋兩入口、真RapidOCR、PDF／mixed頁2、人工確認與摘要；console／pageerror0，測試案件已清除。Secure／HttpOnly／Strict host-only cookie、origin403、owner隔離404、私有路徑404、實際worker／WASM MIME皆驗過。此結果解除臨時HTTPS展示範圍的部署阻礙，不代表外部LLM或固定常駐服務完成。網址、程序、隔離設定及第一輪驗證腳本路徑修正見[Quick Tunnel紀錄](QUICK_TUNNEL.md)。
