# 組員測試完整修正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 完成使用者2026-10-26核准的全部測試回饋，提供可靠且簡潔的理賠準備流程。

**Architecture:** 沿用Vanilla ES Modules、Service adapters及FastAPI，擴充有版本的案件／提案狀態。官方文件規則仍在後端；產品與FAQ索引獨立於三類準備清單。模型只處理受驗證語意／證據，人工備妥與OCR結果分離。

**Tech Stack:** 現有Vite／Playwright、FastAPI／Pydantic／SQLite／PyMuPDF／RapidOCR／httpx，維持目前指定DeepSeek與期限，無需新框架。

**Spec:** `docs/TEAM_REVIEW_20261026.md`；使用者已核准「完整修改」，不重複索取實作授權。

## Global Constraints

- 延續原HTML品牌、繁體中文臺灣、克制文字與響應式390／768／1440。
- 官方來源可追溯，未知商品與版本不可推定投保、保障、資格或金額。
- 不提交憑證、不保存原始醫療檔、不記原始模型prompt；只用合成資料測試。
- 真模型仍指定已授權DeepSeek；300／310／330秒與費用／來源／用量護欄保留，不自動換模型。
- Mock保留且明示；不得以離線／Mock成功冒稱真模型、OCR或公開驗收通過。
- 現有implementation分支與工作目錄接續，不改其他服務；各代理限定檔案責任，root統一提交與發布。

## Review Focus

- 多義短答／拒絕提案不應誤改住院事實；以單題、多題、確認／取消負例驗證。
- 長模型運算期間案件更新、舊提案重放與新分析競爭，必須拒絕過期寫入。
- 未知年分／出院日、保單假碼與不存在版本，保留待確認而不猜測。
- 原檔快取跨案／跨分析不可錯配，關閉重開可預覽，重整／刪案釋放敏感資料。
- 手動備妥不偽造OCR通過，重要缺漏與官方條件反例不能為PASS而移除。

### Task 1: 案件與對話閉環

**Files:** backend/app/models.py, main.py, store.py, message_jobs.py, ai/semantic_dialogue.py, dialogue_privacy.py, providers.py, conversation.py；對應backend/tests。

**Interfaces:** Case新增revision、details與dialogue_state；AssistantResponse新增pending_question／proposal；UpdateCase支援expected_revision／proposal_id與接受／拒絕；DocumentStatus新增manual_ready、DocumentUpdate以analysis_id防舊分析。保持舊payload可用。

- [x] 先新增短答、媽媽情境追問、工作區差異／拒絕、未知商品日期、人工備妥與stale測試，確認RED。
- [x] 實作一次一問、未知可略過、原文支持的最小案件資訊與提案確認，保留官方rules及安全邊界。
- [x] 跑相關pytest至GREEN並保留重要負例；記錄契約及完整測試結果。

### Task 2: 切題文件回答

**Files:** backend/app/ai/openai_compatible.py, retrieval.py；文件回答相關測試。

**Interfaces:** 只送必要query與官方證據；由可驗證證據組成切題回答與適用條件，不引入自由無依據結論。

- [x] 新增不同具體問題、證據不足與惡意證據測試RED。
- [x] 實作受控回答／證據結構，保留model／usage／cost／token及官方白名單驗證。
- [x] 執行相關pytest GREEN；root後續做真請求驗收。

### Task 3: OCR欄位與位置

**Files:** backend/app/ocr/analyzer.py、新form_profiles.py；OCR測試與新增合成文件。

**Interfaces:** 可用nullable bounding_box及location_status表達無可靠定位；保留內部confidence與requires_human_review，不把人工備妥寫回OCR結果。

- [x] 以官方版本及合成中央留白／已填／條件不適用／多頁／混合PDF取得RED。
- [x] 補指定欄位及勾選與混合辨識；無定位時只給文字提醒，未知版型保守處理。
- [x] 真OCR測試GREEN並列支援欄位／版本及限制。

### Task 4: 官方分類庫、商品版本與FAQ

**Files:** data/official-library.json、backend/app/library.py、backend/tests/test_library.py；root整合main.py與test_library_api.py。

**Interfaces:** GET /api/v1/library?query=&category=all；GET /api/v1/faq；GET /api/v1/products/{code}。所有查詢只讀已查核allowlist索引，不向user URL發請求。

- [x] 新增分類／搜尋／假碼／來源／API端點測試RED。
- [x] 實查官方分類與IHI_C_1131001／IHO_1131001版本，建立可追溯索引；未知如實列不足，不造313筆。
- [x] 索引與API測試GREEN、實際URL可用性及來源記錄完成。

### Task 5: 前端與Mock全流程

**Files:** src/、前端tests、必要入口小調整；維持原baseline可恢復。

**Interfaces:** 使用Task1/4契約，Mock同語意；File只限同分頁受限記憶體快取，按case/doc/analysis/fingerprint隔離。

- [x] 新增提案／備妥／排序／來源去重／預覽恢復／分類FAQ行為RED。
- [x] 完成差異卡、快速短答、兩軸狀態、manual_ready、進度摘要、連結與排序、清單篩選、文件庫及FAQ。
- [x] 三尺寸Mock、API、PDF、鍵盤與視覺檢查GREEN；無信心％與假精確框。

### Task 6: 整合、審查與交付

**Files:** docs/API_CONTRACT.md、README.md、TASKS.md、STATUS.md、DECISIONS.md、獨立驗收報告；必要公開／容器配置。

- [x] 獨立審查各變更，修復發現；完整backend與frontend單元、核心Mock／真API／OCR回歸。
- [x] 真指定模型測試報告對話、短答、更正、官方問答與未知資料，保留成功／失敗及費用證據。
- [x] 建置API預設dist，核對秘密未入產物，重啟本專案與HTTPS展示，執行公開檢查及三尺寸視覺。
- [x] Docker可用時重建／檢查；真實外部阻礙記錄，完成進度、契約與可接續紀錄，統一提交。

驗收完成：見[最終報告](../../feedback-20261026/ACCEPTANCE.md)，各輪失敗與差異範圍如實保留。
