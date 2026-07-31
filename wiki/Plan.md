# 開發計畫 Plan

本頁是進行中的分階段執行計畫。最權威的完整版本在 repo 內的 `docs/reviews/fable-opinion.md`（含每階段檔案層級的細節，寫給接手的模型／工程師照著做）。本頁是 zh-TW 摘要。

## 主線：prose-condition 遷移（Phase 0–5）

### 背景問題

`knowledge_base/engine/redflag_eval.py::_eval_clause` 把 Algorithm YAML 的 `condition:` 欄位當成病人 findings dict 的**字面 key** 去查找。當 `condition:` 寫的是英文散文（例如 `"HCV RNA positive AND indolent presentation"`）而非真正的 finding key，查找永遠 miss，`bool(None)` → `False`，這個 step 就默默 fallthrough 到預設分支——但畫面上看起來像是「這個條件被評估過」。

**規模**：180 個演算法檔中，675 個 `condition:` 有 **654（97%）是散文、永遠評估為 False**。99/180（55%）個檔案的 step 1 完全由散文組成——這些演算法對「每一個病人」都直接落到 `default_indication`。

**修法方向**：引擎已支援 `all_of`/`any_of`/`none_of` 結構化布林文法。所以修法是**資料遷移**（把散文改寫成結構化 clause），**不需要改引擎程式碼**。

### 各階段狀態

| 階段 | 內容 | 狀態 |
|---|---|---|
| **Phase 0** | 止血：修 hospital 依賴、prose-condition CI ratchet、補 plan GET 端點 | ✅ 完成（PR #4/#5） |
| **Phase 1** | `audit_prose_conditions.py` 分類 654 筆 → 遷移佇列 CSV | ✅ 完成 |
| **Phase 2** | 路由回歸快照 harness | ✅ 完成 |
| **Phase 3** | 554 筆會改變路由的 condition 依疾病分組成待審文件 | ✅ 完成（74 份，未套用） |
| **Phase 4** | 誠實揭露「人的瓶頸」——招募 Clinical Co-Lead | ⏳ 待人 |
| **Phase 5** | Co-Lead 到位後逐疾病走 §6.1 流程落地 | 🔒 阻擋中 |

### Phase 2 的重要教訓（DEAD-class 事件）

Phase 1 把 100 筆 condition 分類為 `DEAD`（`any_of` 裡有真正運作的 sibling，理論上刪掉不影響結果）。工具實際套用後，**路由快照顯示 0 diff，但既有測試 `test_esophageal_1l_algorithm.py` 卻紅了**——因為某個病人 fixture 直接把散文原文當 finding key 塞值（`{"ESCC CPS >=1": True}`，一個已知的 workaround）。

**結論：光靠路由快照 diff 為零，不足以證明這類改動安全。** 100 筆全數復原，DEAD-class 清理**降級為與 Phase 3 相同的待審模式**（只產候選清單，不自動套用）。完整事件記錄在 `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md`。

### 硬性紅線（給接手者）

1. **不合併任何會改變演算法路由的臨床內容 PR**（CHARTER §8.3）。
2. **不把任何 `reviewer_signoffs` 標記為完成**，不把「看起來合理的對應」當審查通過。
3. **不自己加一席 Co-Lead**——那個角色要真人腫瘤／血液／臨床藥理專科。
4. 可以做且不需臨床審查的：純工具／CI／腳本、純技術債（依賴、缺失端點、測試）、產出稽核文件、產出「草稿、不可合併」的 PR。

## 平行線：Hospital Edition（`DEVELOPMENT_PLAN.md`）

FastAPI 後端 + React SPA，分 B0–B8 後端階段 + F0–F7 前端階段 + E0/E1 E2E。

**鎖定的設計決策**：
- 跨醫師存取病人資料允許（EMR parity），但每次存取必須寫 AuditLog。
- HIS crawler 只在此 repo 定義 stub 介面，爬蟲在另一個 repo。
- 醫師通知用 PWA Web Push（VAPID）+ app 內提醒徽章。
- OpenOnco 建議必須醫師明確點「查詢循證建議」，絕不自動帶入（CHARTER §8.3）。
- 資料庫 SQLite（MVP）／PostgreSQL（正式），一行 config 切換。

**Gate rule（不可協商）**：進入 Phase N+1 前，`pytest tests/hospital/` 必須全綠。

**已知落差**：`GET /api/v1/plan/{plan_id}` 已補（PR #5）；但 spec 之間對前端架構有矛盾（見[技術債](Tech-Debt)），病人可看 UI 尚未存在於 SPA。

## 建議的執行順序

1. **先做無需臨床審查的短期項目**：bundle 拆分、既有失敗清理、claim-grounding 擴大評估。
2. **同時推動 Co-Lead 招募**（Phase 4）——這是解鎖 554 筆待審遷移的唯一路徑，越早開始越好。
3. **Co-Lead 到位後**，依 `docs/audits/migration_drafts/README.md` 的嚴重度排序（step-1 全散文的疾病優先），逐疾病走 Phase 5。

---

> 完整、可執行、檔案層級的計畫細節：`docs/reviews/fable-opinion.md`。
