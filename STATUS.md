# 續作狀態

更新：2026-10-26（臺灣）。**使用者核准的組員回饋完整修改已完成，Phase 3原型維護驗收通過。**

- current_phase：Phase 3／本輪修正 DONE。
- current_task：GH-20261026 DONE；最終程式碼已上傳指定GitHub，後續依組員新回饋維護。
- source_repository：https://github.com/kekekewww/Paris_Hack ，預設分支main；產品程式碼基準7f19bd60876abb79ec7f2fb0e1b4102fdbb66f05，後續交付紀錄提交只更新文件。
- last_completed_task：推送最終產品至main並以遠端SHA核對；保留本機implementation/claim-preparation分支，沒有force push或更改公開設定。
- last_successful_test：本次上傳前全後端878（112.81秒、1既有警告）／前端126（0失敗）通過；前輪三尺寸Mock87、指定真模型3、完整真API30與摘要9／標題3／引導3及OCR53＋8為既有功能證據，本次上傳未重跑模型或瀏覽器。
- current_blockers：本輪MVP無必要外部阻礙。OpenAI／Gemini依使用者決定暫緩，不阻擋此版；兩完整商品碼精確對照仍unverified，不當成投保或保障證明。
- public_url：https://worm-flying-speeches-tales.trycloudflare.com/?service=api
- runtime：backend127.0.0.1:8002／PID83932；cloudflared PID90084。停止前一律重新核對CIM與埠，不能只憑這份PID。
- runtime_settings：沿用.local/quick-tunnel/cases.sqlite3，精確origin、Secure／HttpOnly／Strict cookie、單worker／rate120／no-access-log／no-proxy-headers。8026與8028測試埠已清除。
- model：deepseek/deepseek-v4.1-flash-1017，固定DeepSeek官方供應商與low；300秒／後端310／網頁330，無自動重試／換模型；付費metadata、來源、用量與事實守門保留。最新公開health configured=true／verified=true，同程序最終真流程3/3。
- privacy：必要對話及已驗最小案件摘要外送；文件問答只送必要query與官方證據。不外送上傳原檔／OCR／完整案件；遮罩並非全面去識別。
- docker：cardif-claim-preparation:feedback-20261026／sha256:76cd3ee95f948eba0e2152e35ce0bf4a350d0109bffa37fe43ee8e9aac92de2a，230hash一致、31HTTP、安全與持久性通過；先前19真OCR相關來源不變。專用容器／volume已清除，無關容器未操作。
- design：原HTML與備份SHA256皆59a6fd5053e9811560823b3f12637ef0c7bbe7f3aa2fd9a1abe1ea90fad1c8a1；品牌與Vanilla架構延續，Mock保留。
- saved_evidence：[完整驗收](docs/feedback-20261026/ACCEPTANCE.md)、[可機讀結果](docs/feedback-20261026/tests.json)、[模型流程](docs/MODEL_REQUEST_FLOW.md)、[限制](docs/KNOWN_LIMITATIONS.md)。原失敗在.local/fixes-20261026，無原始模型回覆日誌。

## 下次工作的三步

1. 先讀AGENTS／PROJECT_PLAN／TASKS／STATUS／DECISIONS，核對Git及服務；重啟後verified會重設，不能沿用此成功宣稱新程序已真驗。
2. 依組員新的實測情境新增最小回歸；保留未知、否定、獨立選型／提案與官方來源，不承諾全面語言或手寫正確。
3. 若需固定部署或更多保單版本，另確認實際部署環境／官方精確來源；金鑰到期與餘額以當時唯讀查核為準，不在對話貼key。

前輪重啟與模型歷史見docs/restart-20261023、docs/DEEPSEEK_SETUP.md及Git既有紀錄；本輪結果與前輪分開，不改寫歷史。
