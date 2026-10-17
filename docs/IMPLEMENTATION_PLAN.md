# 理賠文件準備助手 Implementation Plan

> 依AGENTS.md持續實作；各功能先以可重現測試定義驗收，通過後才更新DONE。

**Goal:** 延續原型完成雙入口、來源可追溯、可操作的文件準備體驗。
**Architecture:** 原始首頁＋ES Modules UI；統一MockClaimService／ApiClaimService；Phase1驗收後才建立FastAPI、規則、RAG及OCR。
**Tech Stack:** Vanilla HTML/CSS/JS、Tailwind建置、Node test、Playwright、FastAPI、pytest。
**Spec:** ../PROJECT_PLAN.md、../AGENTS.md。

## Global Constraints

- 繁體中文（臺灣）；保留原始設計，不更換前端框架。
- 三尺寸390／768／1440驗收；核心功能可鍵盤操作，支援減少動態效果。
- 官方來源唯一依據；文件及上傳為不受信任資料；不提交理賠。
- 每一階段驗收後自動續作；沒有真實執行不可宣稱外部API完成。

## Review Focus

- 資訊不足／否定描述：追問，不擅自認定類型。
- 重新整理／儲存失敗：還原非敏感進度，檔案不長存。
- 上傳惡意格式／過大／模糊：拒絕或人工確認，不報通過。
- 官方表單不可用／API失敗：明示錯誤並提供重試與官方主頁。
- 鍵盤／小螢幕：焦點可見、對話框可關閉、無橫向裁切。

## Task 1 — 基準與契約

- [x] 完整閱讀原型，保留副本、截圖與盤點。
- [ ] tests/services.test.js先定義案件隔離、條件清單、狀態與分析的驗收。
- [ ] src/services/{mock,api}.js提供health/getClaimTypes/createCase/getCase/updateCase/sendMessage/getChecklist/updateDocument/analyzeDocument/getSource/deleteCase。
- [ ] docs/API_CONTRACT.md定義snake_case模型、錯誤及multipart。
- [ ] 執行node --test tests/services.test.js。

## Task 2 — 雙流程與工作區

- [ ] tests/e2e.spec.js先定義兩入口到摘要、上傳、重試、還原測試。
- [ ] index.html保留原首頁；src/app.js負責路由與事件；src/components.js負責安全呈現；src/styles/app.css延續tokens。
- [ ] 服務提供狀態，UI不內嵌理賠規則；原始檔保持不動。
- [ ] npm run build、npm test、npm run test:e2e；三尺寸視覺檢查與console。
- [ ] 通過全部Phase1驗收才開後端。

## Task 3 — 後端與AI

- [ ] backend/tests先建立契約、安全、來源規則、實際合成文件測試。
- [ ] backend/app依契約實作FastAPI、SQLite、來源、規則、RAG、provider與OCR。
- [ ] HTTP adapter接上實際API；不可默默降成Mock。缺LLM金鑰要清楚顯示規則模式與未驗證狀態。
- [ ] pytest及真實HTTP+Playwright整合；記錄Phase2閘門。

## Task 4 — 整合交付

- [ ] 閘門通過後補八情境、Docker／Compose、部署設定、README、架構、限制及驗收報告。
- [ ] 真實部署只在有授權與憑證時執行；任何阻礙持久化。
- [ ] 更新TASKS／STATUS／DECISIONS並保存可回復Git里程碑。
