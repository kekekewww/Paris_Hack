# 模型供應商設定狀態

更新日期：2026-10-19（臺灣）。使用者最新決定為**暫不建立金鑰**，並要求先不完成真實 LLM 串接。本輪沒有建立、複製或寫入真實金鑰，也沒有向三家模型服務送出請求。

## 目前設定

| 服務 | 後端預留欄位 | 目前狀態 |
| --- | --- | --- |
| OpenAI API | `OPENAI_API_KEY` | 空白；安全建立與保存待使用者稍後安排 |
| Google AI Studio／Gemini API | `GEMINI_API_KEY` | 空白；未建立、未保存，沒有 Gemini 原生 Adapter |
| OpenRouter | `OPENROUTER_API_KEY`、`OPENROUTER_MODEL=openrouter/free` | 金鑰空白；模型名稱只記錄後續意向，未啟用或驗證 |

這些欄位只預留於 [.env.example](../.env.example)，不會自動複製到真正 env 檔、不會自動對應 `LLM_API_KEY`，現有程式也不讀取它們。所有服務維持 `LLM_PROVIDER=grounded_rules`；`LLM_API_KEY`、`LLM_MODEL` 仍空白。公開 health 明示 `llm_configured=false`、`llm_verified=false`。

不得把「欄位存在」「key 已保存」「key 可用」「模型串接通過」當成相同結果。三家的真正憑證設定、參數相容性、引用、錯誤與配額處理仍未驗收；目前只有單一可選 `openai_compatible` Adapter 的離線測試，不能據此聲稱三家皆可直接使用。

## 安全保存原則

金鑰只交由後端秘密環境或秘密儲存服務管理，不放進前端、`VITE_` 變數、聊天、Git、Docker build args、映像或日誌。未來保存前需確認專案／供應商及目的地，確認檔案未追蹤、未經 symlink 指向外部；只能回報存在狀態，不回報內容。現有 `.gitignore` 排除 `.env`、`.env.local`、`.local/`，Docker context 則採執行必要檔案白名單。

OpenAI 建立流程仍應透過 OpenAI Developers 的安全選擇及本機目的地確認表單；目前依使用者決定不啟動。Google 與 OpenRouter 不在本輪進行帳號、方案、權限或金鑰變更。

Google 官方文件支援以 `GEMINI_API_KEY` 作為後端環境變數，並要求避免前端暴露與提交金鑰。本專案只預留單一名稱，避免與另一別名的優先順序混用。[Google 官方金鑰文件](https://ai.google.dev/gemini-api/docs/api-key)

使用者指定的 `openrouter/free` 是在可用免費模型間路由的模型名稱，實際模型可能改變；不能當成固定模型或穩定容量承諾。日後需驗證實際回傳模型、所需結構化輸出與限制；不自動改用付費路由或其他模型。[OpenRouter 官方 Free Models Router](https://openrouter.ai/docs/guides/routing/routers/free-router)

## 後續解除條件

使用者之後安排安全金鑰設定，再分別驗證三家的實際請求、支援參數、證據引用、失敗恢復及資料邊界。目前不發送模型探測請求、不透過查詢金鑰資訊宣稱有效，也不以 Mock 或本機規則代替真實 LLM。完整無金鑰驗收另見 [本輪報告](ACCEPTANCE_NO_KEYS_20261019.md)。
