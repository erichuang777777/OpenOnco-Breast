# 技術債 Tech-Debt

本頁列出已知的技術債與臨床治理缺口，附嚴重度與處理建議。依嚴重度排序。

## 🔴 高：核心引擎——顯示的決策邏輯大部分沒有真的在跑

- **問題**：180 個演算法檔中，654/675（97%）的 `condition:` 是英文散文，被引擎當字面 key 查找、永遠評估為 False，默默 fallthrough 到預設分支。99/180（55%）個檔案的 step 1 完全由散文組成——對每一個病人都直接落到 `default_indication`，跟畫面顯示的決策樹邏輯脫鉤。
- **為何嚴重**：`openonco.info` 是真實對外 Demo，這代表正在對真實使用者輸出「跟畫面顯示邏輯脫鉤」的建議。
- **現況**：已止血（CI ratchet 擋新增）、已分類（Phase 1 CSV）、已產出 74 份待審遷移文件（Phase 3）。**未修正存量**——因為 86%（554 筆）修正後會改變路由，屬 CHARTER §6.1 臨床內容，需兩人簽核，而目前零席 Co-Lead。
- **緩解**：render 層已加「此決策樹尚待臨床複核」透明度 badge。
- **處理建議**：招募 Clinical Co-Lead（見下），然後逐疾病走 Phase 5。工具已就緒。

## 🔴 高：臨床治理機制無人執行

- **問題**：`specs/CLINICAL_LEADS.md` 顯示 CHARTER §6.1 要求的三席 Clinical Co-Lead **全部「seat open」**。§6.2 的緊急路徑也要求至少 1 席——目前 0 席，代表**現在完全沒有 charter 認可的路徑可以合併任何「會改變臨床建議」的知識庫改動**。
- **連帶影響**：800+ 個臨床實體停在 `pending_clinical_signoff`。CI 只擋得住格式錯，擋不住內容錯（劑量、regimen-biomarker 搭配、指引時效）。
- **處理建議**：這是**人／組織問題，不是工程問題**。透過 `specs/CLINICAL_LEADS.md` 的公開申請流程招募腫瘤／血液／臨床藥理專科真人。AI agent 不能自行填補這個角色。

## 🟠 中：知識庫內容漂移（多個既有測試失敗）

- **問題**：藥物 `last_verified` 日期過期、NSZU 給付比例掉到門檻以下（47% vs 要求 50%）、12 個疾病缺紅旗五型覆蓋矩陣、`citation-verification-2026-04-27.md` 的 914 筆引用問題（缺試驗來源 352、缺法規來源 153、ESCAT/OncoKB 分級不一致 124、藥名不一致 285）未批次修復。
- **現況**：這些是有文件記錄的既有漂移（`docs/reviews/preexisting-failures-2026-04-27.md`），需臨床內容補完，不是程式邏輯問題。
- **處理建議**：分批走 §6.1 流程補完。屬 Co-Lead 到位後的工作。

## 🟠 中：資料正確性沒有自動化的臨床合理性檢查

- **問題**：`knowledge_base/validation/` 只做結構驗證（schema、參照完整性、UA 翻譯品質）——**沒有任何自動化檢查臨床合理性**（劑量對不對、regimen 跟 biomarker 搭不搭）。claim-grounding 語意檢查（用 Claude API）預設關閉，目前只覆蓋 6 筆 claim（真實分母 800+）。
- **處理建議**：評估擴大 claim-grounding 語意掃描範圍（會產生 Claude API 費用，文件估 $5-15/次），至少讓覆蓋率數字有意義。

## 🟠 中：Bundle 大小反覆撐爆門檻

- **問題**：core bundle 已達約 4.03MB，超過 3.5MB 門檻約 534KB。門檻已被手動調高兩次。每次知識庫擴充都撐爆，然後調高門檻，一直循環。
- **處理建議**：結構性解法——把更多疾病專屬內容（drugs/regimens/indications）徹底移出 core bundle，而不是繼續調高門檻。屬純工程，不需臨床審查。

## 🟡 低：Hospital Edition 與 spec 的架構矛盾

- **問題**：`specs/PATIENT_MODE_SPEC.md`／`specs/PORTAL_SPEC.md`（server-rendered Jinja2+HTMX，含病人可看 `/patient/{token}`）與 `DEVELOPMENT_PLAN.md`（React+Vite SPA）互相矛盾，且 `frontend/src/App.tsx` 完全沒有病人可看的 route——病人版計畫目前不存在於實際跑的 SPA。
- **現況**：`GET /api/v1/plan/{plan_id}` 已補（PR #5，原本前端呼叫一個不存在的端點）。
- **處理建議**：需先跟專案負責人定調前端架構方向（Jinja2 vs React），不建議自行選一個方向硬做。

## 🟡 低：兩套試驗來源快取／client 未整合

- **問題**：`CtgovClient`（BaseSourceClient 快取）與 `experimental_options.py` 手寫磁碟 JSON 快取兩條路並存。只有 ClinicalTrials.gov 一個試驗來源，缺 EU CTIS／WHO ICTRP／烏克蘭本國登記。
- **處理建議**：WHO ICTRP 第二來源範疇已釐清（`docs/reviews/who-ictrp-second-registry-scoping-2026-07-04.md`），需有網路權限的環境完成授權審查後再實作。

## 已知的環境／基礎設施注意事項

- 系統層 `cryptography` 套件衝突（見[維護](Maintenance)）。
- 完整測試套件約 17 個既有失敗，皆與內容漂移／bundle 門檻相關，非新增。
- 多 agent 平行 session 會讓 repo 狀態對抗性可變（見[維護](Maintenance)的協作協定）。

---

> 每一項技術債的判斷理由與證據，完整記錄在 `docs/reviews/fable-opinion.md`。
