# 原始介面盤點與延伸原則

檢查日期：2026-10-17（臺灣）  
原始檔：`法國巴黎人壽_理賠申請系統.html`  
範圍：完整閱讀 1–1598 行 HTML、內嵌 CSS、Tailwind 設定與 JavaScript；未修改原始檔。瀏覽器基準執行與截圖由主 Agent 另行記錄。

## 1. 專案起點

初始根目錄包含 `AGENTS.md`、`PROJECT_PLAN.md` 與團隊製作的單一 HTML；沒有套件設定或既有自動化測試。Git 指令回報此目錄尚非 Git repository。

原型使用 Vanilla HTML/CSS/JavaScript，Tailwind Play CDN 與 Google Fonts 為外部依賴。三張相同的品牌 Logo 以 base64 PNG 直接嵌入頁首。其餘圖示都是內嵌 SVG，沒有圖片素材下載依賴。原始檔共 164,323 bytes。

既有畫面已具備完整、可辨識的設計方向，應沿用原始布局、色彩、元件造型與裝飾。優先分離 ES Modules 與 CSS，不需要導入新的 UI 框架。

## 2. 設計基準

### 色彩

| 用途 | 原始值 | 出處與應用 |
| --- | --- | --- |
| 主品牌綠 | `#00875A` | `brand.DEFAULT`；標題強調、對話、圖示、主要操作 |
| 深品牌綠 | `#006B46` | `brand.dark`；主要按鈕 hover |
| 首頁主要按鈕 | `#007048` / `#005A38` | 首頁實心按鈕與 hover |
| 輕品牌底色 | `#E8F6EF` | `brand.light`；AI 圖示、微型容器 |
| 品牌淺綠 | `#8FE0BA` | `brand.accent`；輸入框、點綴、scrollbar hover |
| 主畫布 | `#F8FAF9` | body 背景 |
| 側欄底色 | `#EDF8F2` | 待辦清單外容器、範例 modal 頁首 |
| 卡片底色 | `#FFFFFF` | 文件、對話、待辦、modal |
| 綠色邊線 | `#CFEFE0` / `#E1F3EA` | 容器、卡片、捲軸 |
| 中性邊線 | `#E5EAE7` | 首頁快速搜尋卡片、文件卡片 |
| 次要綠底 | `#EBF7F0` / `#F2FAF5` | 導覽膠囊、hover、狀態 |
| 頁尾底色 | `#F4F9F6` | 免責提醒橫幅；上框 `#DDF0E6` |
| 主文 | `#1F2937` | body 與灰階文字 |
| 提醒色 | amber 系列 | `amber-50` 底、`amber-200` 框、`amber-800` 文；範例按鈕 `#FFF9EB` / `#B45309` |

應將重複色碼整理為 CSS Custom Properties；保留目前的綠色層次，勿改成其他品牌色或深色網站。

### 字體與層次

- 字體為 `Noto Sans TC`，fallback `sans-serif`。Google Fonts 僅載入 300、400、500、600、700，而首頁另使用 `font-extrabold`，可能由瀏覽器合成 800 字重。
- 首頁主標題：手機 30px、sm 36px、md 38px；工作頁主標題到 40px。
- 首頁雙卡標題：24px → 28px → 31px；粗體、較緊字距、短行距。
- 文件卡標題為 16px；待辦標題 13.5px；一般內文為 14–16px；輔助文字 10–12px。
- 文字以灰黑與中灰為主，品牌綠用於重點，amber 用於需注意事項。

### 空間、圓角與陰影

| 元素 | 原始規格 |
| --- | --- |
| 首頁內容 | `max-w-5xl`；雙卡區 `max-w-4xl`；桌面雙欄、手機單欄 |
| 工作區 | 最大 1520px；水平 padding 16 / 24 / 32px；gap 24px |
| 側欄 | 288px，sm 352px（自訂 `spacing.88 = 22rem`） |
| 首頁雙卡 | 24px 圓角；padding 32 / 40px；卡片間距 24 / 32px |
| 側欄外框 | 28px 圓角；padding 16 / 20px |
| 文件／待辦／對話 | 12 / 16px 圓角；綠色細框、輕微陰影 |
| 輸入框／主操作 | `rounded-full`；綠色邊線；實心或描邊膠囊 |
| 小操作 | 8 / 12px 圓角；有背景、細框與小 SVG |
| 浮層 | 24px 圓角；背景黑色 60% + blur；白色內容面板 |
| 陰影 | 以 `rgba(0,135,90,0.03–0.18)` 柔和綠影為主；首頁 CTA 到 0.32 |

### 裝飾與動態

- 左下有固定鳥形品牌水印（opacity 0.12）與 360px 淡綠 radial glow；右上有 400px 淡綠光暈。全部不可攔截指標事件。
- hover 主要使用陰影加深、品牌色／淡綠底變化、圖示 scale 1.05 或 1.1；CTA 輕微右移。
- active 使用 scale 0.95；一般 transition 200–300ms；裝飾 500ms。
- 側欄收合使用 width / transform 350ms，`cubic-bezier(0.4,0,0.2,1)`；opacity 250ms。
- toast 300ms 進退、顯示約 3 秒。
- modal 使用 `animate-in fade-in zoom-in-95` class，但原型未引入對應動畫外掛或自訂 keyframes，不能視為動畫已生效。
- 原型沒有 `prefers-reduced-motion` 規則。

### 響應式策略

現有 class 使用 Tailwind 預設 `sm`、`md`、`lg`，沒有另訂 breakpoint：640、768、1024px。首頁雙卡與文件 grid 在 `md` 才改雙欄，字型與 padding 多用 `sm` 切換。

工作區外層在所有尺寸都保留橫向 flex，側欄保持 288 / 352px，沒有手機單欄或 drawer 規則。`body { overflow-x:hidden }` 可能掩蓋裁切；此為程式結構推論，應以 390px 實測確認。延伸實作必須保留桌面側欄造型，手機改單欄／抽屜。

## 3. HTML 區塊盤點

| 區塊 | 原始定位 | 內容 |
| --- | --- | --- |
| 首頁 `#viewTriage` | 95–207 | sticky 白色頁首與品牌 Logo；雙入口卡片；用途主標；免責頁尾 |
| 引導頁 `#viewAssistant` | 212–380 | Logo 旁提供快速搜尋捷徑；左側個人資訊空卡、待辦清單；中央歡迎與 AI 對話；底部輸入與附件選單 |
| 搜尋頁 `#viewSearch` | 385–517 | Logo 旁提供 AI 捷徑；左側同步待辦；中央搜尋、推薦 tags、文件 grid |
| 範例 modal `#exampleModal` | 522–561 | 淡綠標頭、文件說明、關閉與「下載空白檔案」 |
| toast | 564 | 固定畫面下方的膠囊提示 |
| 背景裝飾 | 567–574 | 鳥形水印與光暈 |
| 應用邏輯 | 579–1595 | 全域狀態、固定文件、文字指引、localStorage、三頁路由、模板渲染 |

## 4. 現有互動與實際能力

| 操作 | 原型實作 | 判定 |
| --- | --- | --- |
| 首頁雙入口、頁首捷徑、Logo 返回 | `switchView()` 隱藏／顯示 3 視圖、更新標題與 URL hash | 可操作 |
| 瀏覽器上一頁／下一頁 | `hashchange` 監聽 triage / assistant / search | 可操作 |
| AI 輸入 | 新增使用者訊息，600ms 後以正則判斷手術／住院／意外 | 有固定模擬邏輯；沒有 AI 模型／追問 |
| AI 文件生成 | 固定 3 項基本文件，另依正則加入手術／住院／意外文件 | 可操作，但官方規則未經來源核對 |
| 兩頁待辦同步 | 同一 `todoItems` 陣列；新增、刪除、完成切換；同步 badge / 文件庫 | 可操作 |
| 手動新增待辦 | 顯示表單、Enter 新增、取消、空值 alert | 可操作 |
| 清空重設 | 瀏覽器 confirm 後清空待辦、對話、localStorage | 可操作 |
| 側欄收合 | transform / opacity / width 切換並換 SVG | 可操作；沒有 ARIA expanded |
| 文件搜尋 | title / desc 子字串即時搜尋；Enter 與 tag 篩選 | 可操作 |
| 搜尋無結果 | 顯示空狀態與關鍵字 | 可操作 |
| 文件加入／移除 | 依名稱去重、切換加入狀態、toast | 可操作 |
| 查看填寫範例 | 固定文字指引 modal | 可操作；不是官方 PDF 範例 |
| 查看檔案 | `triggerAction('viewDoc')` 只顯示「正在開啟」toast | 未開檔 |
| 下載檔案 | `triggerAction('download')` 只顯示「正在下載」toast | 未下載 |
| 附件選單 | 加號旋轉、選單開關、外部點擊關閉 | 可操作 |
| 上傳本機檔案 | 原生 picker；accept 含 PDF / JPEG / PNG / DOC / DOCX；只顯示首個檔名 | 未保存附件／預覽／分析；無驗證 |
| 匯入雲端 | 只顯示「模組已就緒」toast | 未串接 |
| 重新整理保留狀態 | 保存 todo / chat / 草稿 / filter；URL hash 恢復 view | 部分可操作；無版本／資料型別驗證 |

原型的互動函式與資料直接放在同一 script；沒有 Promise service、API adapter、統一錯誤物件或 API Contract。`completed` boolean 同時承擔文件準備含義，尚無獨立的文件必要性與六種準備狀態。

## 5. 風險與優先修正

| 優先度 | 發現 | 證據／影響 | 延伸方式 |
| --- | --- | --- | --- |
| P0 | 使用者內容可進入 `innerHTML` | `showToast(msg)` 第 1524–1527 行直接插入 msg；新增待辦 title 與選擇檔名會流入此處，可被 HTML 解讀 | 動態文字使用 `textContent` 或建立安全 DOM；測試惡意字串 |
| P0 | 未核對的內容被稱為官方規定 | `officialDocs` / `sampleGuideData` 沒有 source_id / URL；包含「影本不受理」「必備」「須親簽」等確定語句 | 先核對官方來源；不完整處標「待確認」；避免照搬原型保險規範 |
| P0 | 假下載／查看訊息 | `triggerAction()` 僅 toast 卻宣稱開始下載／開啟 | 改成真實官方 anchor，找不到文件時提供明確狀態 |
| P1 | AI 未確認便新增文件 | `analyzeAndGenerateAiResponse()` 不論輸入內容固定加入 3 項文件；不理解其他問題 | 由 Mock Service 回傳結構化追問、候選理賠與確認步驟 |
| P1 | 工作區手機裁切風險 | 固定寬左欄 + 橫向 flex + overflow hidden | 實測 390 / 768 / 1440，手機單欄與 AI drawer |
| P1 | 文件狀態不足 | 僅 completed，沒有 required / conditional / unknown 或 processing / needs_attention | 定義獨立 requirement_type / preparation_status，服務統一管理 |
| P1 | modal 鍵盤／輔助科技資訊不足 | 無 dialog role、aria-modal、焦點移入／返回、Escape 或 focus trap | 使用原生 dialog 或等價完整語意；保留外觀 |
| P1 | 輸入與圖示按鈕缺標籤 | 依賴 placeholder / title，Logo 使用可點 div | 增 label / aria-label、將 Logo 改 anchor/button、加入 focus-visible |
| P1 | 附件沒有格式／大小限制 | accept 含不在計畫內的 DOC / DOCX，沒有 size / signature 驗證 | 只接受 PDF/JPG/PNG；前端與 service 驗證；顯示恢復操作 |
| P1 | 儲存完整對話且無保存策略 | localStorage 無到期／提醒；可能包含使用者醫療描述 | 使用合成展示資料、說明本機保存、提供刪除／到期；避免 raw file 持久化 |
| P2 | localStorage 型別驗證不足 | 僅檢查頂層是否 array；後續直接使用 `aiReason.replace` 等 | 版本化儲存格式、驗證與安全復原 |
| P2 | view 欄位沒有實際讀回 | saved.currentView 有保存，但初始化只採 currentView / hash | 明確 hash 優先，再採已驗證儲存 view |
| P2 | 複製的待辦 renderer | assistant / search 兩套近乎重複模板 | 共用 render component 與事件 delegation |
| P2 | inline handler 的動態字串 | 使用 HTML escaping 組入 JavaScript 單引號字串；HTML entity 解析後仍可影響 handler | 改 data-id + addEventListener，避免以文字生成程式 |
| P2 | CDN 可用性與字型依賴 | Tailwind 與字型需外網；樣式依賴執行時編譯 | 本地 CSS / build；保留 fallback 字體與原始 tokens |
| P2 | 動畫與小字 | 沒有 reduced motion；部分控制項文字 10px、點擊目標 16px | 動態降級與可用的觸控區，不全面放大或改版 |

## 6. Phase 1 缺口

1. 建立由 Mock Service 驅動的案件、條件、訊息、文件、OCR、來源等模型；保留 HTTP adapter 的可替換介面。
2. AI 入口增加逐步追問、候選類型與人工確認；錯誤與重試可重現。
3. 快速入口增加住院醫療／醫療門診／防癌或重大疾病分類；僅詢問影響文件需求的條件。
4. 雙入口匯入同一文件工作區；左欄改為案件摘要／進度，中央文件清單，右欄可收合 AI。
5. 文件清單增加必要性、用途、官方來源、版本／核對日期、準備狀態、展開說明。
6. 將原型下載／預覽 toast 改成可使用的官方來源連結；沒有確認到的官方 PDF 不創造 URL。
7. 增加真實前端檔案選擇／拖放、驗證、圖片／PDF 預覽、處理中進度、Mock OCR 結果與 normalized bounding boxes。
8. 增加 findings 列表、點選框線對應詳情、人工確認／待處理操作，以及低信心／分析失敗狀態。
9. 增加送件前摘要、缺漏清單、官方送件指引、列印或下載摘要，並可返回修改。
10. 完成桌面、平板、手機布局；鍵盤、dialog、live region、focus、reduced motion。
11. 建立 API Contract、自動化 Playwright、服務測試、桌面與手機視覺證據；記錄 console / network / 無效連結問題。

## 7. 建議落地順序

先保存原始檔與桌面／手機截圖，再擷取 CSS tokens 與原始 Logo。以同樣白色 sticky 頁首、雙入口卡片、薄荷側欄、圓角文件卡片與 footer 延伸 `index.html`，不更換品牌與排版語言。

第一個可驗收單位應是「雙入口 → 由服務建立案件 → 共用工作區」，接續「文件管理 → 上傳預覽與 Mock OCR → 準備摘要」。每一單位同時補上錯誤／空白／載入回饋，最後以 390、768、1440px 驗證兩條完整路徑。

這份盤點只記錄已讀取的原型實作與結構推論，不把尚未執行的瀏覽器測試視為通過。
