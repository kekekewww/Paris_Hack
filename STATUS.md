# 續作狀態

更新日期：2026-10-19（臺灣）。**原訂MVP的Phase 1、2、3已完成驗收。OpenRouter免費路由已啟用於公開展示；金鑰安全保存，最後實GET的使用量為0。** 免費容量、OCR歷史例外及臨時隧道限制仍明列，這不是正式保險送件系統。

- current_phase：Phase 3交付完成；原訂MVP DONE。
- current_task：OPENROUTER-20261019 DONE，P2-04／P2-09／P3-GATE DONE。OpenAI／Gemini為暫緩的可選外部依賴。
- last_completed_task：真OpenRouter設定、證據ID安全profile、本機／容器／公開整合、重啟保存、清理與完整文件。
- last_successful_test：最終OpenRouter103、全後端293（49.01秒）、前端36；API／OCR27（ID profile前、不變範圍）。本機live首次2pass／1fail（53.6秒，平板上游429），平板唯一重驗1pass（13.7秒）；容器56checks真OCR及live1（18.2秒）、restart同案；公開live1（27.8秒）與HTTP23checks。沒有合併成一次全過。[完整結果](docs/openrouter/test-summary.json)。
- public_url：https://retirement-trim-reported-jesus.trycloudflare.com/?service=api 。既有網址保留，已實際驗證新provider。
- runtime_state：公開8002 parent50120／listener64028，cloudflared36692，Vite5174／27888保留。測試8003 parent51792／child57912及專用Docker容器／volume核對後清除；未操作無關8000／3137。[清理紀錄](docs/openrouter/cleanup.json)。操作前重新查CIM，不沿用舊PID直接停止。
- public_settings：單worker、專用合成DB.local/quick-tunnel/cases.sqlite3、精確HTTPS origin、Secure／HttpOnly／Strict host-only cookie、no-access-log／no-proxy-headers、rate120。原始上傳文件不持久保存。
- provider_state：openai_compatible、官方OpenRouter端點、openrouter/free、35秒、minimal reasoning、1800 completion tokens、四項max_price0／require_parameters true／allow_fallbacks false。目前公開configured／verified true；verified僅同程序配置過往成功，不是即時readiness，重啟後false直到真請求通過。
- secret_state：金鑰只在.local/secrets/.env.openrouter，Windows目前使用者專屬ACL，Git／Docker排除。Vite一般與@fs路徑403、後端與公開404均實測，無金鑰值進文件／前端／映像／命令列。可信任launcher在.local/openrouter-20261019/start-server.py，使用原URL、8002、原DB及--secure重啟；不需再次建立金鑰。
- docker_status：cardif-claim-preparation:openrouter-20261019，image ID sha256:95758438118303dc1fd828cdec72a0d43c0011c593ad53239d44a2693565a6c7；build exit0、UID10001／唯讀／capdropALL／no-new-privileges、私有檔排除。image保留，專用測試container／volume已清。
- visual_scope：本輪未改前端畫面／CSS／Mock／規則與來源資料，延續前輪三尺寸實拍、axe與原設計。新live測試檢查1440／768／390的完整問答、PDF／canvas、錯誤保留、摘要、reload與橫向溢出；成功輪非預期console／pageerror0。不保存含對話的trace或cookie。
- unchanged_scope：來源11實GET及依賴Python33／npm88零known為同日先前證據；未改依賴，不冒稱重跑。Mock87／PDF2／G1及原始視覺屬前輪引導版本證據；前端產品原碼本輪未改。
- original_design：原HTML／docs/baseline/original.html SHA256均59a6fd5053e9811560823b3f12637ef0c7bbe7f3aa2fd9a1abe1ea90fad1c8a1，Vanilla與既有品牌保留。
- current_blockers：原訂MVP無未完成gate。額外三類service CLI中住院／門診真成功，重大疾病查詢在原輪及單項重驗均LLM_RATE_LIMITED，整組仍FAIL保留，不宣稱三類全過；不是三類官方規則缺失，後者已測。免費供應商容量為外部持續限制。
- operating_constraints：單worker／單副本；臨時網址依賴本機與隧道持續執行。歷史OCR冷啟timeout、未明OCR_UNAVAILABLE及本輪ONNX bad allocation仍保留；精準單項與最終293通過不表示根因已修。僅合成展示，簽名／保障／核准人工確認。
- saved_evidence：去敏感公開資料在docs/openrouter；本輪完整測試／RED／失敗輸出在.local/openrouter-20261019，不保存原始模型內容、prompt或cookie。[本輪報告](docs/OPENROUTER_ACCEPTANCE.md)為目前結果；舊報告保留版本歷史。

## 下一個工作階段的三步

1. 讀取規範與本紀錄，核對公開health與程序；若重啟，以既有私有設定啟動，verified先false屬預期，不重複索取憑證。
2. 用合成展示文件走一次需要的demo；遇免費429／逾時保留案件後稍候手動重試，不使用付費或Mock冒充成功。
3. 只有使用者擴充需求時再處理多保單、附件候選資料或其他provider；正式上線前另規劃登入、資料治理、穩定網域與跨程序一致性。這些不是未完成的原訂MVP gate。
