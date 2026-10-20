# 工程決策

## 2026-10-17

1. 以根目錄原始HTML為設計基準。保留原檔及 docs/baseline/original.html；index.html延伸其首頁、品牌圖、配色、卡片與圖示。未導入前端框架。
2. 使用Vanilla ES Modules與本機建置CSS，移除對Tailwind CDN執行期的依賴；服務介面集中切換Mock／HTTP。
3. 原型以正則直接產生「必備」清單、假下載和不受信任innerHTML不適用正式流程；由服務層回傳規則、來源與結構化對話，UI只呈現。
4. 文件必要性 requirement_type 與準備狀態 status 獨立；人工確認不表示正式核准，unknown不得當成不需要。
5. 不將醫療院所文件冒充官方可下載表單；只有經查核的官方URL可提供下載／範例入口。
6. Phase1閘門前只研究官方資料及建立前端Mock，不實作完整後端。外部API／部署無憑證時，記錄阻礙並持續其他工作。
7. 使用者已提供完整規格並要求自主持續實作，依此執行而不增加例行設計核准流程。
8. 依賴安全檢查發現舊版Tailwind建置鏈及Vite弱點。將原首頁用到的utility CSS固定為本機src/styles/generated.css，新功能使用app.css；移除Tailwind建置依賴，Vite更新6.4.4。npm audit為0，不再依賴CDN或遠端字型。保留tailwind.config.cjs及來源CSS作為原樣式產生紀錄，日常build只需要Vite。
9. 沙箱程序建立出現helper_unknown_error；透過自動審核允許的require_escalated執行專案限定建置與測試。Git使用每次命令的safe.directory參數處理沙箱／本機使用者擁有者差異，不修改全域Git信任設定。
10. 紙本送件地址與官方服務窗口由getSource('cardif-claims').submission提供；UI不自行拼接或推定送件資訊，也不提供代送功能。
11. 使用者於2026-10-17選擇「先完成其餘工作，金鑰稍後設定」。外部LLM adapter與離線HTTP驗證先完成，不建立、不沿用或使用真實金鑰；真實provider驗證保留BLOCKED。依此先完成可獨立的整合、安全、Docker及交付準備，不將Phase2整體或專案標記Completed。
12. 真實瀏覽器驗證發現原生fetch需綁定globalThis，以及Windows會將.mjs判為text/plain；分別由服務adapter與後端明確MIME處理，不略過瀏覽器安全規則。
13. 一般請求15秒、對話50秒、文件分析95秒，覆蓋後端對話45秒／分析90秒預算。OCR內部45秒為步驟間保守預算，單次模型執行無程序硬中止；目前使用單worker與單OCR鎖，並行忙碌明確503可重試。
14. 文件分析按鈕由有效檔案、PDF檢查及服務忙碌狀態共同控制；無效／過大／損毀檔案不可送出，精準錯誤保留至重新選檔。由Mock回歸先確認錯誤後修復，並補三尺寸與PDF恢復斷言。無障礙掃描先等待入口初始化完成及實際有限動畫結束，不排除axe規則。
15. 保留前版容器冷啟OCR超45秒及暖重試39checks成功的實測歷程，不放寬45／90秒限制。品質修復後最終映像首次完整60checks通過，也不抹除歷史限制。Health不代表模型readiness，展示前以合成文件smoke確認；初始化／推論分階段監測與啟動預載屬後續可靠性改善，目前不宣稱冷啟零失敗。
16. API回歸一次模糊圖回OCR_UNAVAILABLE，安全診斷後18次交替真HTTP未復現，底層原因保持未知。日誌僅例外類型與程式位置，沒有例外訊息、文件或區域變數。既有低品質判斷改為真正前置條件：不足頁跳過模型，以quality_precheck／uncertain明示未辨識，混合文件保留實際provider與逐頁提示；不因無辨識證據就判空白欄位或錯誤類型。
17. 清晰度閾值是工程條件，不是官方文件要求；品質finding的官方連結標為表單參考，位置標為人工提示區。信心是品質調整後的初步參考，並非文字純平均或整份文件完整率。新增清晰第1頁＋模糊第2頁合成PDF，防止提示錯指頁碼。

18. 使用者明確要求Cloudflare Quick Tunnel分享，授權本輪臨時公開展示。另啟專用loopback8002與獨立合成案件庫，精確公開origin、Secure cookie、單worker及no-proxy-headers；原8000保留。不變更帳號、DNS或安裝常駐服務。公開HTTPS23項及瀏覽器3/3通過後，P3-04／04C以臨時展示範圍DONE，不增加固定網域作為MVP門檻；真LLM仍BLOCKED，隧道存活限制明列。

## 2026-10-19

19. 依使用者明確回饋與提供的apple-design skill，延伸既有品牌而非換成Apple外觀：減少重複介紹、次要細節用原生details、預設收合助手、第一份未完成文件突出、官方空白表單保留直接入口。Mock／未OCR／待確認／非核准仍可見，工程模式集中服務說明。維持Vanilla與API契約，不新增動畫或UI依賴。
20. 本輪自動審核因Selected model is at capacity未能執行瀏覽器檢查。所有可獨立程式／單元／隔離build先完成；新版只輸出.local/ui-simplification/dist，未覆寫公開dist。沒有把舊截圖、--list或記憶體DOM測試當成新視覺／E2E通過；待審核恢復再驗收與發布。
21. 使用者切換模型後已恢復真瀏覽器驗收。以仍在運行的舊dist作before、Vite新版作after，等初始化／toast穩定才擷取；文字量排除收合內容與讀屏專用文字，不將不同捲動位置的dialog納入減字百分比。Mock75／PDF2與三尺寸目視通過後才更新正式dist；真API27、G1及公開HTTP22／瀏覽器3亦通過。首頁測試只修readiness與巢狀summary精準定位，保留所有聲明斷言及失敗證據。外部LLM依原決定稍後配置。
22. 使用者要求規劃OpenAI、Google AI Studio與OpenRouter（openrouter/free）安全設定，但在憑證選擇中明確回覆「暫不建立金鑰」。本輪不建立／寫入secret、不開金鑰表單、不切換LLM_PROVIDER、不呼叫模型。僅以空白後端欄位記錄未來需求，沒有自動alias到現有LLM_API_KEY，Gemini／OpenRouter未宣稱已串接；繼續完整無key驗收，金鑰任務與整體LLMgate保留BLOCKED。
23. 無key完整重驗以f41d74d產品版本執行：後端190、前端33、Mock75、API27、PDF2、G1、公開HTTP22／browser3、容器60／browser1與restart保存皆過；來源11及依賴重掃亦通過。只更新.env.example預留欄位及文件，不增加SDK或串接邏輯；既有映像產品未變，重用映像驗收而不無謂重build。合成key canary隔離build207檔零洩漏，runtime保持grounded_rules。實際金鑰、供應商參數、模型回覆與整體P2／P3gate仍未完成，結果不混稱。
24. 依使用者回饋，將guided候選的「確認並建立清單」拆為具名原生radio選型與獨立「建立文件清單」。即使單一建議也不預選；選取僅前端狀態，不呼叫updateCase。其他既有類型放於可展開區，與真正建議分開，不虛構相關性；維持單一類型／單一清單及既有API契約。重述／新回覆清選取，busy與重試採案件／回覆／選取快照防舊狀態，沿用品牌與克制排版。
25. 本次引導修正在原產品先取得單元及瀏覽器RED，再完成獨立選型及快照隔離；source freeze後單元36／Mock87／API27及公開HTTP23／browser3均過，才以新版原始碼建立guided-20261019映像並實測60checks／新引導／restart。前輪後端190、來源與依賴保持歷史證據，不因UI更新冒稱重跑。正式dist與展示連結已更新；測試程序／容器／volume核對身分清除，公開服務保留；金鑰與真LLM仍依使用者決定暫緩。
26. 使用者最新提供並授權使用OpenRouter金鑰，指定openrouter/free；此授權取代該供應商先前暫緩，OpenAI／Gemini仍暫緩。金鑰只保存在.local/secrets/.env.openrouter，ACL限制目前Windows使用者，Git及Docker排除且Vite禁止供應env檔，不在紀錄重述值。沿用httpx與evidence-only資料邊界，固定免費router、零價格限制及無付費fallback；實際回覆須驗model、usage.cost及來源內容後才算真驗證。初次真請求已200／cost0，不因單次探測就宣稱網站整合或整體gate完成。

27. 免費路由實測曾429、推理耗盡1800 token產生空content及35秒逾時；不放寬引用或付費fallback。先以minimal reasoning降低負擔，再將OpenRouter內部回覆限為當次retrieval白名單的1–3個唯一證據ID，由後端還原全部原文／引用；generic相容服務原契約不變。TDD先5fail後103pass／全293pass，真實模型與網站驗證另行取得，不以離線state模擬代替。
28. 最終原型gate依真模型、本機響應式、既有API／實際OCR、新容器與公開HTTPS逐項驗收後結案；三尺寸首次2pass1fail與平板重驗分開記錄，額外重大疾病CLI受429仍保留FAIL。一次上游容量失敗不改為假成功，也不擴張成所有功能未完成。OpenAI／Gemini屬使用者暫緩的可選provider，不阻擋已具真OpenRouter的原訂MVP。
29. llm_verified為單程序／同配置歷史真成功證據，不是即時readiness；只在metadata、ID、最終response全驗過且預設真transport後成立，配置觀察變更／重啟清除。公開版原URL與DB保留，僅核對後重啟8002，8003及專用Docker測試資源清除。歷史OCR bad allocation無證明根因修復，持續列限制。

30. 使用者三句公開重現全為grounded_rules固定分類追問，OpenRouter既有baseline早退使其不送模型；前輪真連通涵蓋有依據文件問答，沒有實作所有訊息生成式對話。本輪只修負向／未知事實追問及新舊intake顯示，逐則標示來源與折疊揭露混合分流，不擴私密資料外送或LLM schema。急診只可作待保單／官方確認的導航候選，非官方保障結論。
31. 限定source review發現的否定／未確診／本次重設回歸均先RED後修，最終後端347、前端56及三尺寸對話／Mock／API通過。舊Mock固定generic文案測試調整為新clarification與更強空案／無提案／無更新斷言，84pass3fail與最終87pass分開保存。
32. 新程序真模型請求受429，原完整公開腳本仍要求verified=true而失敗。自動審核拒絕降為布林型別檢查後未執行被拒命令，維持原標準並記BLOCKED；前輪成功不充當本輪成功。對話bug修復DONE／當前真模型整體重驗BLOCKED分開記錄，免費上游恢復才可結當前gate。

## 2026-10-20

33. 使用者明確要求對話與追問真正使用 OpenRouter `openrouter/free` 理解描述，此授權取代第 30 點僅限本機引導的實作範圍。必要當前描述與有限同案對話可送模型，畫面將說明外送範圍；上傳原檔、OCR 結果、憑證與整份案件不送模型。不另索取已獲授權的確認。
34. 模型回傳受限的語意事實與短追問，伺服器驗證並決定合法候選；官方文件、來源、條件規則與案件更新仍由伺服器控制，使用者獨立確認才建立清單。保留免費零價格護欄、真傳輸與 metadata 驗證；失敗明確回報，不以規則或 Mock 代替真模型成功。
35. 真模型招呼回覆的 JSON／facts 合法，但自然措辭被過窄字詞檢查拒絕；先以自然招呼、確認與「呢／還是」問句取得 5 個 RED，再修正同義表達。未知卻肯定住院／確診、醫療指示與否定引文反轉的實質負例保持有效。之後公開三句真引導與合成留院改寫均通過；不能將後續限流或未重現 INVALID 隱藏為成功。
36. 新工作區語意真探測遇 `finish_reason=length`，實際免費模型使用滿 1800 completion tokens，故調整新語意 profile 的生成上限為 4096；舊文件證據 profile 仍 1800。metadata 必須依當次請求上限驗證，不接受截斷、非零費用、超限或不一致用量。整體 35 秒／最多40秒預算不變，不加入重試或付費 fallback；提高生成預算不是免費容量或所有格式錯誤已修復的證明，仍需真實重驗。
37. 使用者要求重新啟動，先核對專案8002與隧道均未執行，再以既有私有launcher載入OpenRouter設定、沿用案件庫及正式dist，取得新Quick Tunnel origin後精確設定Secure cookie與允許來源。公開啟動檢查15項通過，合成案件已清除；未呼叫模型或OCR分析、未修改原完整驗收腳本。重啟後verified=false如實記錄，前輪真模型證據仍為歷史，完整模型及P2／P3整體gate保持BLOCKED。本輪僅重啟，不修改產品程式或啟動Vite。
38. 使用者指出思考模型需100–300秒，將OpenRouter預設／最高期限改300秒（一般相容服務20／60秒不變），後端310、前端330秒。Cloudflare單次代理等待125秒且Quick Tunnel不支援SSE，故採一次POST202與每3秒短GET，不加自動重試或備援。同步相容端點也共用16項執行／128項保留容量；worker鎖外處理，成功前重讀案件，類型／條件改變拒舊回覆、刪案禁止晚寫，TTL／shutdown清理。來源、免費費用及token護欄保留。後端544／前端69／Mock87／API及OCR27／受控長等待4／公開啟動15通過後發布並沿用網址。唯一真探測為限流FAIL，configured=true／verified=false如實保留；不冒稱完整模型成功。Docker新build因引擎未開受阻，舊映像清楚標歷史；本機原生服務已更新。[完整紀錄](docs/LLM_WAIT.md)
