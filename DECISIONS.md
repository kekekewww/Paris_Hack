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
