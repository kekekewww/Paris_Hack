# Cloudflare 展示部署

狀態：2026-10-30雲端展示驗收通過。[固定展示網址](https://paris-claim-demo.kevinyaungputra.workers.dev)／[完整驗收與限制](cloudflare-20261030/ACCEPTANCE.md)。此部署不依賴本機伺服器或Quick Tunnel。

使用者最初指定Vercel，核對後改討論Cloudflare完整部署，並要求沿用既有升級帳號。已以Wrangler與既有Dashboard核對指定帳號及Workers Paid；不另外開通方案，不操作其他網站。

## 最小部署設計

- Workers Static Assets供應既有Vite前端；同源`/api/v1`由Worker轉送至單一、具名Container，保留FastAPI、PyMuPDF／RapidOCR及202背景對話輪詢。前端不依賴本機隧道。
- Container磁碟為暫存；案件改由獨立SQLite Durable Object保存，與容器生命週期分離。保持owner hash隔離、建立後24小時TTL、每owner20案、參數化SQL與版本衝突保護。原檔不持久保存。
- Worker與案件儲存之間使用獨立的部署內部憑證；它不是模型key。模型key不存部署環境，而由本次分頁從`?key=...`讀取、立即移除網址參數，只經必要同源請求的`X-OpenRouter-Key`交給後端。
- `RUNTIME_LLM_KEYS=true`時不回退伺服器私有key；無key仍能使用官方文件庫、規則與文件分析。缺key／格式錯誤明確回報，不假稱模型成功；每請求固定已授權OpenRouter模型與原費用、來源及語意守門。
- 暫以一個Container、閒置自動休眠控制用量；Workers Paid基本方案沿用，執行與儲存用量仍依原方案計費。容器冷啟動、重啟中的工作失效等限制需如實記錄。

## 金鑰連結

部署成功後可使用`https://<展示網域>/?key=<你的短期OpenRouter金鑰>`。讀取後網址參數移除，不寫localStorage／sessionStorage／cookie或案件資料。重整後需再次使用含key的連結。初始主文件請求仍會經過瀏覽器與Cloudflare，Navigation Timing仍可能保留原始網址；不可將這些資料送到Analytics／RUM。不能宣稱URL金鑰從未出現在上游或瀏覽器診斷資料；此設計僅供使用者明確授權的短期限額Demo。

目前入口為`https://paris-claim-demo.kevinyaungputra.workers.dev/?key=<短期金鑰>`。本機已產生受使用者限定權限保護的`.local/secrets/cloudflare-demo-link.txt`供複製；此檔不入Git、Docker、靜態資產或驗收報告。一般網址可使用官方文件、規則及真OCR，AI需要本次分頁的合法key。

## 部署相容修正

2026-10-30首次真部署已上傳資產與映像，但帳號拒絕舊`default`容器排程，要求`durable_object`。此失敗保留於驗收紀錄；不能以dry-run成功宣稱正式部署成功。改採Wrangler 4.155.0與官方原生Durable Object Container API，映像從具名`images.base`啟動、`standard-1`規格及180秒閒置關閉；單一具名DO控制實際路由，無新增訂閱。新版排程不提供`max_instances`硬上限，因此單實例來自應用固定路由，並非平台配額保證。

## 必要驗收

- [x] 同源key擷取、清除、header白名單與跨訪客／背景工作隔離。
- [x] 全後端／前端回歸與三尺寸操作。
- [x] 持久儲存的owner隔離、TTL、20案限制、CAS及容器重啟後案件保留。
- [x] 實際Cloudflare建置、部署、官方來源、合成OCR與指定真模型請求。
- [x] 憑證／URL／DB／日誌／產物檢查，完成進度與可接續文件。

參考：[Containers](https://developers.cloudflare.com/containers/)、[磁碟與重啟限制](https://developers.cloudflare.com/containers/faq/)、[Workers方案](https://developers.cloudflare.com/workers/platform/pricing/)。

## 重現部署

1. `npm ci`，使用已認證的Cloudflare帳號；本專案鎖定Wrangler4.155.0，Docker引擎需可用。
2. PowerShell執行`$env:VITE_SERVICE_MODE='api'`後`npm run build`。靜態與容器前端必須同為API預設。
3. 核對`wrangler.jsonc`的帳號與全新Worker名稱。自己的fork應修改帳號ID／名稱；既有部署需保留DO綁定、class名稱及v1 migration以接續案件。
4. 透過`npx --no-install wrangler secret put CASE_STORE_TOKEN`的互動輸入設定獨立長隨機內部憑證，後續部署保持同一值。首次Worker尚未存在時可先deploy再設secret，配置未齊時後端會拒絕啟動。這不是模型API key。
5. `npx --no-install wrangler deploy`。新版排程於下一次冷啟選擇目前映像；等待超過3分鐘且沒有後端流量再檢查，部署不強制中止活躍對話。
6. 以合成資料驗證兩條流程、真模型、OCR與刪案；不可將金鑰貼入命令參數、GitHub或報告。

`GET /__internal/backend`只接受內部Bearer憑證，供維運讀取`running`、`boot_id`及`image_matches`；無憑證404、禁query，沒有停止／執行命令介面。這個RPC本身也是平台活動，休眠驗收期間不可輪詢。原生容器的root能力依Cloudflare平台規格，映像USER10001不當成完整權限隔離保證。
