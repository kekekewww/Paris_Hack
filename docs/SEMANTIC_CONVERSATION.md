# OpenRouter 語意對話整合

更新：2026-10-20。狀態：已取得真實語意理解成功；完整模型流程仍在重驗，保留所有失敗。

依使用者最新要求，普通招呼、情況描述與追問須真正使用 `openrouter/free` 理解同案對話。文件需求、官方來源與條件清單維持伺服器規則，候選類型仍須使用者選取及確認才寫入案件。

必要當前描述及有限對話會送至 OpenRouter；不送上傳原檔、OCR 結果、憑證或整份案件。前端持續區分「AI回覆」、「規則引導」與「模擬」，外部錯誤不得靜默改用模擬回答。

驗收將包含使用者提供的「你好 → 我出車禍了 → 沒有住院」、補充門診後才提供候選、官方清單與確認分離，以及真 API／瀏覽器、否定及未知、安全、失敗恢復與既有功能回歸。成功及失敗證據將分別記錄於本頁。

## 實作範圍

1. OpenRouter 模式的一般描述與追問真正發出模型請求，不再因本機分類結果提早回傳。已進工作區的一般補充也走模型；明確資格、金額、核准及注入要求保留本機安全回覆並標示來源。
2. 模型只提出事故／就醫／手術等語意事實、使用者引文及短追問。伺服器驗證值、原始對話依據、否定與未知，再產生允許的類型提案；沒有模型修改清單或送件的工具。
3. 官方文件問答保留既有證據 ID 模式，伺服器還原完整已查核段落與引用。模型不生成官方文件需求或 URL。
4. 公開 API schema 不變。選取類型只改本機選取狀態，獨立點擊「建立文件清單」後才透過 PATCH 寫案；對話失敗不產生假成功訊息或更動清單。
5. 固定 `openrouter/free`、零價格限制、無付費 fallback、無自動重試；保留原逾時、大小及實際 model／cost／token 驗證。`llm_verified` 只代表同程序同配置歷史真成功，不能作即時容量保證。

## 驗收歷程（持續更新）

- 前端 TDD：新說明／隱私分支先 3 fail，修正後完整 58/58 通過；root 再驗 58/58，約2.41秒。
- Mock 三尺寸完整回歸：首次 87 項因缺少原鎖定的 Chromium 執行檔而無法啟動，沒有產品斷言成功。改用已安裝 Chrome，保持同一測試與斷言，87/87 通過（3.9分鐘）。未下載或改動依賴。
- 獨立 source review 發現自然回覆與未知事實不一致、引用截去否定，以及短答失去前置問題三項風險；修復與重驗中，不把初版單元綠燈當成完成。

- 最終第一版完整後端 471/471（91.65秒、既有 Starlette warning1）；前版466也過，但自然措辭增補後以471為準。語意預算修正後另重驗，不挪用此數字。
- 公開網站原完整模型測試：第一次前三輪皆真200／非模擬／AI標示，第三輪已建立本程序 `llm_verified=true`；第四輪補充門診遇 `LLM_RATE_LIMITED`，整輪1 fail（54.7秒）。第二次第一輪 `INVALID_LLM_RESPONSE`（19秒），第三次第一輪 `LLM_RATE_LIMITED`（6.1秒）；三次都有相應network console error1，沒有未處理 page exception 的成功證據替代。
- 原完整公開 HTTPS 23 項未放寬且已通過；同程序 verified 來自本輪實際三句，不是前輪狀態或設定旗標。
- 合成改寫「摔車之後被留院觀察三個晚上，沒有動刀」真模型成功，產生住院候選／無手術且案件未更動；實際模型 `nvidia/nemotron-3-super-120b-a12b:free`，cost0、prompt657／completion950／total1607。另一次最終招呼也真成功，cost0、629／660／1289。
- 工作區真探測：`dots-studio/dots-3-note-preview:free` 回 cost0、499／1800／2299，但 finish_reason=length，正確拒為 INVALID；不能當作完整工作區模型成功。基於此實測，只提高新語意 profile 的生成預算至4096，保留文件 profile1800、實際 cap 驗證、35秒與零費用檢查，修正後重驗。
- 首版語意容器 `sha256:2fa10dde372ab661cea5ecb10b5e862000fdf45b79f4889f594f36fa013cd9b7` 已通過 API/OCR 27/27（4.1分鐘）及雙模式追問 12/12（1.6分鐘）；後者是明確規則／Mock回歸，不冒充外部模型。UI與規則/OCR沒有因語意預算調整而改動。
- 真 configured API 與容器 Mock 兩模式、三尺寸目視12張圖／6個context皆通過，consoleerror／pageerror0；視覺檢查沒有呼叫模型或分析端點，6案均刪除。原HTML／備份SHA256均維持 `59a6fd5053e9811560823b3f12637ef0c7bbe7f3aa2fd9a1abe1ea90fad1c8a1`。

目前展示網址：[理賠準備助手](https://boots-deaf-found-arrange.trycloudflare.com/?service=api)。前輪 Quick Tunnel 已停止，新隧道對應單程序8002、原案件庫、安全cookie與精確origin；本機與隧道須持續運作。

## 最終部署與結果

語意預算修正先5個RED，再400/400相關AI測試通過。完整後端 **477/477**（108.76秒，既有Starlette warning1），最終映像 **7c6afbc949395337cd7ead9bb082b7d6e470a8c31c22878d747a7b1bf32dca12** 已建置。語意cap4096，文件／generic cap1800，均驗證用量不得超過當次請求；finish stop、零費用及35秒限制維持。

最終公開新程序第一輪取得真模型200、非模擬、AI標示，第二輪遇 `LLM_RATE_LIMITED`；完整live仍1 fail（39.5秒），network console error1。原完整公開HTTPS **23/23 PASS**，其中verified由新程序本輪真招呼建立；這只是同程序歷史成功，不代表免費容量穩定，也不等於完整對話旅程通過。[完整HTTP證據](semantic-conversation/public-http-final.json)

最終容器兩模式三尺寸追問 **12/12**（3分鐘）通過，不含外部模型。API/OCR **27/27** 的前映像2fa10dde與最終映像前端、規則及OCR相同，只有外部語意cap不同，沒有冒稱這27項在最終映像又跑過。最終adapter／語意／隱私模組與dist的SHA256已比對映像完全相同。[版本比對](semantic-conversation/source-image-hashes-final.json)

提高預算後的工作區真探測有 stop、cost0，但事實引文／語境不符而被拒為INVALID；沒有因模型輸出不可靠就接受錯誤門診或改動既有案件。它不是成功驗收，也不能由提高token預算推論所有錯誤已修。[工作區失敗](semantic-conversation/semantic-probe-budget-workspace.json)

最終只讀key檢查顯示usage0、餘額限制0.1，當日免費請求27/1000；Vite私有一般路徑及@fs403、原生後端私有路徑404且秘密值不在回應。這是用量／保護證據，不代替真模型成功。[去敏感用量](semantic-conversation/final-key-status.json)

**實作與部署完成，完整模型驗收BLOCKED；P2／P3整體gate尚未通過。** 保留所有失敗、不改免費路由、不加入付費或Mock fallback、不放寬200／provider／引用／費用／確認的必要斷言。免費容量恢復後，以原live spec續驗；若INVALID重現，先記去敏感驗證階段與合成情境，不記原始敏感對話，不盲目削弱安全檢查。

公開8002與同一Cloudflare隧道保留，案件庫未替換。測試容器／volume清理與本輪彙整見[續作狀態](../STATUS.md)。完整命令與未遮蔽合成測試日誌保存在本機`.local/openrouter-conversation-20261020/`（不入Git），可分享的去敏感證據在本頁相鄰`semantic-conversation/`。

最終獨立code review確認生成上限只作用於對應profile、無用戶控制或驗證越權，免費與逾時護欄保持；沒有把原live失敗改判。實際key掃描384檔零洩漏，本機文件連結檢查通過。[掃描](semantic-conversation/leak-check-final.json)／[連結](semantic-conversation/links.json)／[測試彙整](semantic-conversation/tests.json)／[清理](semantic-conversation/cleanup.json)。

## 續驗指令

原測試維持單worker、retries0、trace／影片／失敗DOM快照關閉；下列指令會真正使用後端既有免費金鑰，不載入或印出秘密。只在容量恢復或有新的診斷證據後續驗，不連續盲重跑。

```powershell
$env:LIVE_OPENROUTER='1'
$env:CLAIM_API_BASE_URL='https://boots-deaf-found-arrange.trycloudflare.com'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='C:/Program Files/Google/Chrome/Application/chrome.exe'
node node_modules/playwright/cli.js test -c playwright.openrouter.config.js --project=openrouter-desktop-1440
```

本輪完整後端命令為 `.venv/Scripts/python.exe -m pytest backend/tests -q`；前端為 `npm test`。Mock、API與追問各使用 `playwright.config.js`、`playwright.api.config.js`、`playwright.followup.config.js`；API／追問基底需另啟明確 `grounded_rules` 的專用測試服務，不能把要求本機規則的測試套用到已啟用模型的公開服務，再放寬provider斷言。
