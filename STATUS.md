# 續作狀態

- current_phase：Phase 2 — Backend & AI
- current_task：P2-01至08 FastAPI／規則／RAG／OCR／HTTP整合
- last_completed_task：P1-10；Phase1全部通過，見docs/PHASE1_ACCEPTANCE.md
- last_successful_test：63/63 Playwright，三尺寸各21/21，axe0、console0；20/20單元、build、npm audit 0。
- current_blockers：真實LLM尚未配置／授權金鑰與外部呼叫；Docker CLI存在但engine未運行；其他後端工作持續。
- external_dependencies：後續真實LLM需要後端金鑰；正式HTTPS展示需要部署環境、憑證與授權，尚未驗證。
- last_changes：完整Mock/HTTP adapter、雙流程、條件清單、上傳預覽與模擬分析、人工確認、送件摘要與下載。原型SHA256與備份一致。Vite6.4.4，移除CDN及遠端字型。
- Git：已初始化；b0e4e01保存原型基準，實作分支implementation/claim-preparation。不推送遠端。
- next_actions：
  1. 完成FastAPI、Pydantic、SQLite與官方規則，執行實際HTTP。
  2. 完成來源RAG、安全降級及真正PDF／圖片OCR合成文件測試。
  3. 串接HTTP adapter與PDF預覽，執行整合與安全驗收；記錄外部依賴。
