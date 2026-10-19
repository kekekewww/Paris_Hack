# OpenRouter 免費路由整合驗收

> 最新連續追問修復已發布（2026-10-19），後端347／前端56、Mock87／API27、最終容器追問12／公開6通過。但本輪真模型回503限流，原公開完整腳本在模型verified斷言失敗；當前整體gate保持BLOCKED。以下OpenRouter成功與程序為前輪歷史，最新以[追問修復報告](ASSISTANT_FOLLOWUP.md)為準。

日期：2026-10-19（臺灣）。狀態：**原訂MVP驗收完成，已知限制保留**。使用者授權的`openrouter/free`已安全設定並啟用於[公開展示](https://retirement-trim-reported-jesus.trycloudflare.com/?service=api)。Phase 1／2／3原型閘門已完成；這不表示正式上線、持續可用或理賠核准。OpenAI／Gemini仍暫緩。

## 設定與資料邊界

金鑰只保存在本機`.local/secrets/.env.openrouter`，目前Windows使用者專屬ACL、Git／Docker排除及Vite env檔禁止供應保護；Vite一般與`@fs`路徑實GET403，後端路徑404，皆沒有洩漏金鑰。設定檔不隨專案交付，不在文件、前端、build參數、映像或日誌重述值。

啟動後端時由可信任程序讀取該檔並注入`LLM_PROVIDER=openai_compatible`、`LLM_BASE_URL=https://openrouter.ai/api/v1`、`LLM_MODEL=openrouter/free`、`LLM_API_KEY`及`LLM_TIMEOUT_SECONDS=35`；Python後端不自動讀env。`OPENROUTER_API_KEY`範本預留欄位不自動alias或啟用其他供應商。

OpenRouter只接收本次檢索的官方證據ID、標題與完整段落。模型只能回覆當次白名單內1–3個不重複ID，後端還原正文與全部官方來源／頁碼，拒絕額外鍵、文字或更新。使用者原話、案件、歷史對話及上傳原檔不外送；分類、條件及文件要求仍由本機規則和使用者確認。其他相容服務仍保留原逐字段落契約；公共API回覆格式不變。

## 免費與驗證限制

OpenRouter端點與模型固定，請求包含四項`provider.max_price=0`、`require_parameters=true`及`allow_fallbacks=false`，沒有付費模型清單或plugins。採`reasoning.effort=minimal`、`max_completion_tokens=1800`及35秒逾時。回覆還須有具體實際模型、明確有限數值`usage.cost=0`及合理token，再驗完整JSON、ID與還原引用。缺值不當零；錯誤不改用付費、本機或Mock假成功，不自動重送。

`llm_verified`只在同程序、同配置的真實預設transport成功並全部驗證後為true；重啟或觀察到配置變更清除。它不是readiness或持續可用承諾，health不呼叫模型。離線transport測試與其狀態模擬不算真API證據。

[官方免費路由說明](https://openrouter.ai/docs/guides/routing/routers/free-router)說明免費與容量限制；[官方價格護欄](https://openrouter.ai/docs/guides/routing/provider-selection#max-price)、[用量](https://openrouter.ai/docs/cookbook/administration/usage-accounting)及[推理預算](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)作為參數依據。金鑰實GET回報上限US$0.10，初次真推論HTTP200、費用0；這不取代完整網站驗收。

## 已觀察的失敗與修復

- 初次單段證據探測200，實際模型liquid/lfm-2.5-2.6b:free，完整JSON／段落／引用通過、cost0。
- 正式adapter第一輪遇到429，明確`LLM_RATE_LIMITED`，沒有fallback。後續相同設定曾實際200，不將其宣稱成已根治上游限流。
- 一次回覆未通過檢查；去敏感診斷確認dots-studio/dots-3-note-preview:free使用1800個completion tokens、finish_reason=length且content空。這符合官方所述推理耗盡可見輸出預算；沒有放寬引用或截斷驗證。
- 嘗試`reasoning.enabled=false`得到400／無適用endpoint。改試官方`reasoning.effort=minimal`，實際200、xingchen-agi/xing4.0-29b-a4b:free、178 completion tokens、2個逐字段落與來源通過、cost0；其後再以ID profile完成正式修復與重驗。
- `minimal`正式版仍有一次住院成功後的門診35秒逾時，以及桌面真UI收到503，均保留，不把離線測試當作網站通過。為減少模型複製正文與來源的負擔，進一步試驗只回證據ID，由後端還原正文／引用；同一個先前空白的dots模型在19.75秒、1505 completion tokens完成3個合法ID、cost0。此優化不變更前端/API回覆鍵值、1800 token或35秒預算，完整來源字句由後端控制。
- 原API／OCR三尺寸回歸27/27通過（2.2分鐘）。後端`minimal`版完整重驗265/265通過（45.19秒）；其前一輪有一項掃描PDF ONNX `bad allocation`，獨立該項1/1後再整套通過。沒有改OCR、放寬斷言或宣稱根因已修；ID profile的最終後端測試與真網站驗收另行記錄，不混用版本。

完整失敗與去敏感探測紀錄保存在`.local/openrouter-20261019/`，不保存原始模型內容、prompt或cookie。可分享的去敏感紀錄在[本輪證據](openrouter/test-summary.json)。

## 最終版本實測

| 驗證 | 結果與範圍 |
| --- | --- |
| OpenRouter離線安全／契約 | 103/103，0.93秒；ID profile先有5項RED，修復後通過；離線不當真API證據 |
| 最終全後端 | 293/293，49.01秒；既有Starlette/httpx deprecation warning 1項 |
| 前端單元 | 36/36；本輪前端產品原碼／CSS／Mock未修改 |
| 既有真API／OCR三尺寸 | 27/27，2.2分鐘；在ID profile前執行，API／OCR不變範圍，不冒稱在最終profile後重跑 |
| 最終本機真模型網站 | 首輪桌面與手機成功，平板上游429，**2pass／1fail，53.6秒**；平板獨立重驗**1pass，13.7秒**。保留原失敗，未合併成單次3/3 |
| 新Docker建置 | exit0，tag `cardif-claim-preparation:openrouter-20261019` |
| 新容器API／OCR | **56checks PASS**；真pdf_text／rapidocr／quality_precheck／mixed逐頁、隔離與刪除；smoke對話明示SKIPPED_PROVIDER_NOT_GROUNDED，由下列真live補驗，不冒稱60checks |
| 新容器真模型網站 | **1/1，18.2秒**；實際完整前端、模型及引用驗證 |
| 新容器重啟 | 真restart後同cookie案件完全一致，刪除及404；不保存cookie |
| 公開HTTPS真模型網站 | **1/1，27.8秒**；既有網址已啟用新provider |
| 公開HTTP安全 | **23checks PASS**；Secure／HttpOnly／Strict host-only cookie、no-store、CSP／nosniff、來源403、owner隔離／刪除、私有檔404及模型configured／verified true |
| 費用與私有檔 | 最後實GET key回報usage=0、limit_remaining=0.1；Vite一般與@fs403、後端404均未含金鑰。這是觀察結果，不保證未來服務可用性 |
| 獨立source覆核 | 最終ID profile無需修正的P0／P1／P2問題；不是正式安全認證 |

每個live測試只送一次真實上游模型請求；故障重試中的首個503為明確受控故障，解除後的200才是真實模型證據。流程涵蓋未預選radio、獨立建立、真PDF／canvas、人工確認、錯誤後案件與輸入保留、逐字官方引用、保守拒答、摘要下載、reload及清除；模型不得改寫案件／文件狀態。1440／768／390成功輪無溢出或非預期console／pageerror。因本輪未改畫面，延用[引導修正](GUIDED_CHOICE.md)與[介面減量](UI_SIMPLIFICATION.md)的三尺寸實拍與axe證據。

最終Docker image ID為`sha256:95758438118303dc1fd828cdec72a0d43c0011c593ad53239d44a2693565a6c7`；實際UID10001、唯讀root、capdropALL、no-new-privileges與私有路徑排除通過。runtime才注入key，build不含key。新source凍結後只有文件與忽略規則更新。

## 額外覆蓋與持續限制

額外三類service CLI在最終ID profile取得住院（liquid/lfm-2.5-2.6b:free）與門診（nvidia/nemotron-3.5-super-vl:free）的真成功，metadata皆cost0。接續重大疾病查詢遇429，獨立重驗仍429，**整組CLI仍FAIL／額外覆蓋受容量阻擋**，見[原輪](openrouter/live-service.json)與[重大疾病重驗](openrouter/live-service-critical_illness.json)。沒有標成三類真模型全通過；三類官方規則與API另有確定性測試證據。原訂gate要求的真模型引用、拒答、安全及整合已由上表實測完成。

免費router隨當下容量路由，429、503、逾時或不合規回覆仍可能發生。系統保留案件與可重試輸入，明確回錯，不自動付費或假成功。`llm_verified=true`保留過往成功語意，稍後限流不會把歷史抹除，也不能用它預測下一次一定成功。

OCR歷史冷啟45秒timeout、未明OCR_UNAVAILABLE與本輪掃描PDF的ONNX bad allocation仍列[已知限制](KNOWN_LIMITATIONS.md)。單項與最終293通過不代表根因已修；未修改OCR或放寬重要斷言。單worker／單副本、無正式會員登入、24小時展示案件TTL及臨時Quick Tunnel亦保留。OpenAI／Gemini暫緩為可選擴充，不阻擋具真OpenRouter的原訂MVP。

## 階段結案與保存

| 原訂驗收閘門 | 結論 |
| --- | --- |
| Phase 1 | 已完成；雙入口／Mock／響應式／互動／契約與既有設計保留，未被本輪變更回歸 |
| Phase 2 | 已完成；官方來源、規則、RAG、真LLM引用與安全拒答、實際PDF／OCR、案件隔離及前後端整合均有證據 |
| Phase 3 | 已完成原型範圍；回歸／基本安全、新Docker、臨時HTTPS、展示與文件齊備 |

公開8002 parent50120／listener64028與cloudflared36692保留，既有URL／DB不變。專用測試8003及容器／volume核對後清除，image及本機私有設定保留。[清理](openrouter/cleanup.json)、[公開HTTP](openrouter/public-http.json)、[容器smoke](openrouter/container-smoke.json)、[重啟保存](openrouter/container-persistence.json)與[最終費用／私有檔檢查](openrouter/final-status.json)均為去敏感結果。

原HTML與可恢復備份SHA256保持`59a6fd5053e9811560823b3f12637ef0c7bbe7f3aa2fd9a1abe1ea90fad1c8a1`。未提交金鑰、案件資料庫、cookie或原始上傳文件；舊報告保留當時版本歷史，不覆寫成今日重新執行。

最後真金鑰存在性[掃描](openrouter/leak-check.json)覆蓋340個原始碼、測試、文件及dist檔案，匹配0。文件本機連結與`git diff --check`通過；預設Mock與API的`--list`仍分別只列原87與27項，沒有混入需明確授權的live測試。這兩次清單檢查只證明測試分流，不當作重跑87／27的證據。
