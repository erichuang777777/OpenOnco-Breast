# 路線圖 Roadmap

本頁記錄已完成的里程碑與未來方向。進行中的細節分階段計畫見[開發計畫](Plan)，已知缺口見[技術債](Tech-Debt)。

## 已完成的里程碑

### 知識庫建置（2026-04 ～ 2026-05）
- 六份規格全部起草至 v0.1，命名鎖定為 OpenOnco。
- 知識庫擴充波次 GI-2、GI-3、PUL、HEME-1 完成。
- 規模成長至：92 疾病、664 適應症、594 紅旗、384 療程、180 演算法、475 生物標記可行性、444 來源。
- RedFlag 品質 phase 1-7 完成，臨床簽核收到。

### OncoKB → CIViC 樞紐（2026-04-27）
- OncoKB 因 ToS（禁止再散布、禁止「用於病人服務」、禁止 AI 訓練）與 CHARTER §2 衝突而**否決**。
- 改用 CIViC（CC0，無任何法律限制）作為**唯一的主要可行性來源**。
- 引擎模組更名 `oncokb_*` → `actionability_*`（供應商中立，保留未來再樞紐的彈性）。
- CIViC 每月刷新 CI、fusion-aware 變異比對、快照 client 落地。

### 臨床試驗管線修正（2026-07，PR #4 已合併）
- 修正 biomarker 誤用 ctgov `query.intr`（藥名欄位）→ 改用 `query.term`。
- 修正狀態過濾矛盾（`status="open"` 對齊下游過濾）。
- 支援多重陽性 biomarker 查詢、依 NCT ID 去重合併。
- 加上真正的分頁（`nextPageToken`），破解 25 筆上限。
- 新增病人年齡／性別對試驗收案條件的比對（`age_sex_screen`，快取後疊加，不污染跨病人快取）。
- WHO ICTRP 第二來源範疇釐清文件（未實作，因環境無法連外驗證授權）。

### 技術債止血與稽核工具（2026-07，PR #5 已合併）
- **Phase 0.1**：修正 Hospital Edition 的依賴宣告，讓 `pytest tests/hospital/` 能跑（283/283 通過）。
- **Phase 0.2**：prose-condition CI ratchet，擋住散文 condition 繼續增生。
- **Phase 0.3**：實作 `GET /api/v1/plan/{plan_id}` 並補上計畫持久化（原本前端呼叫一個不存在的端點）。
- **Phase 1**：`audit_prose_conditions.py` 把 654 筆散文 condition 分類（結構 × 信心）產出遷移佇列 CSV。
- **Phase 2**：路由回歸快照 harness（`build_routing_snapshot.py`）。
- **Phase 3**：554 筆會改變路由的 condition 依疾病分組成 74 份待審文件（`docs/audits/migration_drafts/`），**未套用任何臨床內容**。
- **治理透明度標示**：render 層對含未解散文 condition 的演算法加上「此決策樹尚待臨床複核」badge。

## 短期方向（可獨立執行，不需臨床審查）

- **Bundle 大小結構性拆分**：core bundle 已超過 3.5MB 門檻約 534KB，門檻已被調高兩次。把疾病專屬內容徹底移出 core，而不是繼續調高門檻。
- **claim-grounding 語意檢查擴大範圍**：目前預設關閉、只覆蓋 6 筆 claim（真實分母 800+）。評估是否值得花 Claude API 費用擴大掃描。
- **既有失敗清理**：藥物 `last_verified` 時效、NSZU 給付比例、12 個疾病的紅旗五型覆蓋。屬臨床內容補完。

## 中期方向（需臨床共同負責人到位）

- **Prose-condition 遷移 Phase 4-5**：目前完全沒有 charter 認可的管道可以合併「會改變路由」的臨床內容修正——因為三席 Clinical Co-Lead 全部空缺。這是**人的瓶頸**，不是工程問題。招募到 Co-Lead 後，`docs/audits/migration_drafts/` 的 74 份待審文件才能逐疾病走 CHARTER §6.1 流程落地。
- **CIViC actionability 樞紐 phase 2-5**：CLAUDE.md 標記為 pending。

## 長期方向

- **Hospital Edition 前端補完**：`specs/PORTAL_SPEC.md`（Jinja2+HTMX，含病人可看 `/patient/{token}`）與 `DEVELOPMENT_PLAN.md`（React SPA）互相矛盾，且 SPA 目前沒有病人可看的 route。需先定調前端架構方向。
- **儲存遷移**：實體數超過約 10K 時，從 YAML + git 遷移到 PostgreSQL。
- **第二試驗登記來源**：WHO ICTRP／EU CTIS，需有網路權限的環境完成授權審查（見 `docs/reviews/who-ictrp-second-registry-scoping-2026-07-04.md`）。

---

> 路線圖的優先順序判斷與理由，完整記錄在 `docs/reviews/fable-opinion.md`。
