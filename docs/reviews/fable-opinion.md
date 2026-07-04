# fable-opinion.md — OpenOnco 建置優先順序、判斷理由、與交接執行計畫

**作者**：Claude（本次 session 使用 Fable/Sonnet 模型），2026-07-04。
**目的**：把「從醫師可信賴使用角度優化 OpenOnco」這個任務的調查結果、判斷
理由、已完成的工作，以及尚待執行的詳細計畫，寫成一份可以直接交給其他
（可能能力較小的）模型接手開發的文件。**所有數字、檔案路徑、函式名稱
都是本次 session 實際讀程式碼/跑腳本得到的，不是猜測。**

如果你是接手這份工作的模型：**請先讀完整份文件再開始動手**，特別是
「絕對不能做的事」那一節——這個專案有明確的臨床治理紅線，跨過去會造成
真正的傷害（對病人建議錯誤的治療），不是普通軟體 bug。

---

## 目錄

1. [任務背景與調查方法](#1-任務背景與調查方法)
2. [三個發現與判斷理由](#2-三個發現與判斷理由)
3. [今天已經完成的工作](#3-今天已經完成的工作)
4. [絕對不能做的事（紅線）](#4-絕對不能做的事紅線)
5. [詳細執行計畫：Phase 1-5（prose-condition 遷移）](#5-詳細執行計畫phase-1-5prose-condition-遷移)
6. [其他待辦（優先權較低）](#6-其他待辦優先權較低)
7. [驗證方式總表](#7-驗證方式總表)

---

## 1. 任務背景與調查方法

使用者的請求：「站在醫師使用角度，維護以及資料的正確性，幫我把這個
專案建立起來」——這不是單一功能請求，是要求對整個專案做體檢、排序、
分階段執行。

調查方法：派出 3 個平行 Explore agent（只讀，不改檔案）分別調查：
- **醫師使用面**：`docs/reviews/physician-platform-review-2026-06-13.md`、
  `docs/reviews/openonco-state-audit-2026-05-17.md`、`hospital/`、
  `frontend/`、`specs/PATIENT_MODE_SPEC.md`、`specs/PORTAL_SPEC.md`
- **資料治理面**：`specs/CLINICAL_LEADS.md`、
  `specs/CLINICAL_CONTENT_STANDARDS.md`、
  `docs/reviews/citation-verification-2026-04-27.md`、
  `knowledge_base/validation/`、`.github/workflows/`
- **引擎正確性面**：`knowledge_base/engine/redflag_eval.py`、
  `knowledge_base/hosted/content/algorithms/*.yaml`（180 個檔案全部重新
  掃描一次，不是引用舊稽核數字）

加上 1 個 Plan agent，專門設計「prose-condition 遷移策略」的分階段計畫
（因為這是最複雜、風險最高、需要謹慎設計的一塊）。

之後又直接讀了關鍵原始碼（`redflag_eval.py`、`algorithm.py` schema、
`plan.py` API、`db/models.py`）驗證 agent 回報的內容，並實際跑
`pytest`/腳本驗證數字。**所有下面引用的數字都是可重現的**——重新跑
`python scripts/check_prose_conditions.py` 或 `pytest tests/hospital/`
會得到同樣的結果。

---

## 2. 三個發現與判斷理由

### 發現 A（最高優先）：核心規則引擎——顯示的決策邏輯大部分沒有真的在跑

**這是什麼**：`knowledge_base/engine/redflag_eval.py` 裡的 `_eval_clause`
函式（約第 161-202 行）把 Algorithm YAML 的 `condition:` 欄位當成病人
findings dict 的**字面 key** 去查找：

```python
finding_key = clause.get("finding") or clause.get("condition")
actual = _resolve_finding(findings, finding_key)
result = bool(actual)
```

當 `condition:` 寫的是一句英文散文（例如
`"HCV RNA positive AND indolent presentation"`）而不是真正的 finding
key，查找永遠 miss，`bool(None)` → `False`，這個 step 就默默 fallthrough
到 `if_false`/預設分支——但畫面上看起來像是「這個條件真的被評估過」。

**規模（今天實測，非引用舊數字）**：

```bash
python3 scripts/check_prose_conditions.py --write-baseline
# → Baseline written: docs/audits/prose_condition_baseline.json
#   (654/675 prose conditions across 180 files)
```

依「這句散文旁邊有沒有真正在運作的 sibling clause」分類（Plan agent
逐檔案分析得出）：

| 分類 | 數量 | 現在的行為 | 修正後行為 |
|---|---|---|---|
| DEAD（`any_of` 裡有真正運作的 sibling clause） | 93（~14%） | 已經對，不受影響 | **不變** |
| SOLE_ANY（`any_of` 整組都是散文） | 252 | 恆 False → 掉到下一步/預設 | 路由會變 |
| SOLE_ALL（`all_of` 整組都是散文） | 221 | 恆 False（AND 必敗）→ `if_false` 恆觸發 | 路由會變 |
| MIXED_ALL（`all_of` 混了散文和真 clause） | 76 | 散文讓整個 AND 歸零 | 路由會變 |

**判斷理由**：
1. `openonco.info` 是**真實對外的 Live Demo**（見 README.md 第 9 行：
   "**Live demo:** [openonco.info](https://openonco.info)"）——這不是
   測試資料算錯，是正在對真實使用者輸出跟畫面顯示邏輯脫鉤的建議。
2. 99/180（55%）個 algorithm 檔案的 step 1 完全由散文組成——這些演算法
   對「每一個病人」都直接落到 `default_indication`。
3. 引擎已經有 `all_of`/`any_of`/`none_of` 結構化布林文法在正式使用中
   （其他正確的 YAML 就是這樣寫的）。**所以修法是資料遷移，不是引擎
   程式碼改動**——這件事本身降低了修復的技術風險，但沒有降低治理風險
   （見下面第 4 節）。
4. 2026-05-17 稽核時是 376/443（85%），今天是 654/675（97%）——**問題在
   擴大，不是在縮小**。新加的 algorithm 檔案複製同樣的錯誤寫法。這代表
   「先止血再治療」的順序是對的：先擋新增，再處理舊的存量。

### 發現 B：醫師使用面——已建但有落差，部分是「假的」

- `hospital/` Hospital Edition 相當程度已實作（不只是 spec）：
  `hospital/decision/services/patient_service.py`（338 行）、
  `hospital/decision/services/guideline_service.py`（411 行）、
  `hospital/main.py`（254 行）都是真程式碼，對應測試齊全
  （`tests/hospital/*`，283 個測試）。
- **但今天發現 `pytest tests/hospital/` 完全跑不起來**——
  `sqlalchemy`、`fastapi`、`alembic`、`python-jose`、
  `pydantic_settings`、`slowapi` 從未被宣告在 `pyproject.toml` 或任何
  requirements 檔案裡。`DEVELOPMENT_PLAN.md`（repo 根目錄）明訂這是
  「Gate rule（non-negotiable）」——沒有這關，整個 Hospital Edition 的
  階段推進機制形同虛設。**（今天已修復，見第 3 節）**
- `GET /api/v1/plan/{plan_id}` 前端（`frontend/src/pages/ClinicPage.tsx`
  第 55 行）會呼叫，但後端原本不存在——重新載入病人計畫原本是假的。
  **（今天已修復，見第 3 節）**
- `specs/PATIENT_MODE_SPEC.md`/`specs/PORTAL_SPEC.md`（2026-06-03，
  server-rendered Jinja2+HTMX，含病人可看 `/patient/{token}` 頁面）跟
  `DEVELOPMENT_PLAN.md`（2026-06-04，React+Vite SPA）**互相矛盾**，且
  `frontend/src/App.tsx` 裡完全沒有病人可看的 route——病人版計畫目前不
  存在於實際跑的 SPA 裡。**（尚未處理，見第 6 節）**

### 發現 C：資料治理——CI 只擋得住「格式錯」，擋不住「內容錯」

- `docs/reviews/citation-verification-2026-04-27.md`：914 筆發現（缺
  臨床試驗來源 352、缺法規來源 153、ESCAT/OncoKB 分級不一致 124、藥名
  不一致 285），沒有證據顯示已批次修復。
- `knowledge_base/validation/`（只有 `__init__.py`、`loader.py`、
  `ua_quality.py` 三個檔案）只做結構驗證（schema、參照完整性、UA
  翻譯品質）——**沒有任何自動化檢查臨床合理性**。
- claim-grounding 的語意檢查（`docs/kb-claim-grounding-report.md`，用
  Claude API）預設關閉（`.github/workflows/claim-grounding-audit.yml`
  需要手動 `workflow_dispatch` + `semantic: true`），目前只覆蓋 6 筆
  claim（真實分母該是 800+）。
- **`specs/CLINICAL_LEADS.md` 顯示 CHARTER §6.1 要求的三席 Clinical
  Co-Lead 全部「seat open」。§6.2 的緊急路徑也要求至少 1 席——目前 0
  席，代表現在完全沒有 charter 認可的路徑可以合併任何「會改變路由」
  的臨床內容修正**，標準流程或緊急流程都不行。這是**人的瓶頸**，不是
  工程問題，我（或任何 AI agent）都無法用程式解決。

**判斷理由**：這是我把「引擎正確性」排在「治理補完」前面的原因——
即使有 Co-Lead，CI 現在也只擋得住格式錯誤；即使把散文 condition 全部
轉成結構化寫法，沒有臨床審查一樣不能合併。兩邊要同時往前推，但
**工程能做的部分（Phase 0-2，見下）跟需要人的部分（Phase 3-5）要
分開排程**，不要互相卡住。

---

## 3. 今天已經完成的工作

以下已經寫好、測試通過、commit、push 到
`claude/clinical-trials-decision-support-fn6gdr` 分支（PR #4，草稿）。
**接手的模型不需要重做這些**，可以直接依賴。

### 3.1 臨床試驗搜尋管線修正（PR #4 的原始範疇）
- `knowledge_base/clients/ctgov_client.py`：biomarker 查詢從誤用
  `query.intr`（藥名欄位）改成正確的 `query.term`；加上 `status="open"`
  跟下游過濾對齊；加上真正的分頁（`nextPageToken`），修正
  `pageSize` 被硬性限制在 25 筆的問題。
- `knowledge_base/engine/experimental_options.py`：支援多重陽性
  biomarker 查詢並依 NCT ID 去重合併；新增 `_apply_patient_screen`
  ——病人年齡/性別跟試驗收案條件的比對，**在快取讀取之後才做**（因為
  `ExperimentalOption` 快取是跨病人共用的，不能把單一病人的比對結果
  烤進共用快取）。
- `knowledge_base/engine/trial_outlook.py`：新增
  `detect_age_sex_screen()` 函式。
- 對應測試：`tests/test_ctgov_pagination.py`（新增）、
  `tests/test_experimental_options.py`、`tests/test_trial_outlook.py`
  （擴充）。全部通過。
- `docs/reviews/who-ictrp-second-registry-scoping-2026-07-04.md`：WHO
  ICTRP 第二個試驗來源的範疇釐清文件——**沒有做任何程式碼改動**，因為
  這個 session 環境連不到 `who.int`/`clinicaltrialsregister.eu`
  （proxy 回 403），無法完成 `SOURCE_INGESTION_SPEC.md` §8 要求的
  「識別授權條款」這一步。列出了未來有網路權限的 session 要做的具體
  下一步。

### 3.2 Phase 0（今天完成，三個 commit）

**Commit `428867237`：修 Hospital Edition 依賴宣告**
- 在 `pyproject.toml` 新增 `[project.optional-dependencies].hospital`
  群組：`fastapi`、`uvicorn[standard]`、`sqlalchemy`、`aiosqlite`、
  `asyncpg`、`alembic`、`python-jose[cryptography]`、
  `pydantic-settings`、`slowapi`。
- `dev` 群組加上 `pytest-asyncio`（`pyproject.toml` 已經設定
  `asyncio_mode = "auto"` 但外掛本身沒宣告）。
- 驗證：`pytest tests/hospital/` 從完全跑不起來（`ModuleNotFoundError:
  No module named 'sqlalchemy'`）變成 **283/283 通過**。
- **注意**：如果你在一個新環境跑這個 repo，可能會撞到系統層級的
  `cryptography` 套件衝突（apt 裝的 `cryptography==41.0.7` 沒有
  pip metadata，`pip install` 拒絕覆蓋）。解法：
  `pip install --ignore-installed "cryptography>=42"`。這是環境問題，
  不是這個 repo 的程式碼問題，不需要為此再改任何檔案。

**Commit `49621846b`：加上 prose-condition 的 CI 止血機制**
- 新檔案 `scripts/check_prose_conditions.py`：
  - `count_conditions(algo_root)` 遞迴走訪每個 algorithm YAML 的
    `decision_tree[].evaluate`（處理 `all_of`/`any_of`/`none_of` 巢狀
    結構），對每個含 `condition:` 的 clause 呼叫
    `knowledge_base.engine.redflag_eval._looks_like_prose_condition`
    判斷是不是散文。回傳 `{filename: {"total": N, "prose": M}}`。
  - `write_baseline()` / `check_against_baseline()`：拿目前狀態跟
    `docs/audits/prose_condition_baseline.json`（已 commit）比對。
  - **規則**：新的 algorithm 檔案含任何散文 condition → CI 失敗；既有
    檔案的散文數量**增加** → CI 失敗。既有的 654 筆先 grandfather（
    不擋），只擋新增。
- CI 已接入 `.github/workflows/validate-kb.yml`（新增一個 step，在
  `audit_validator.py` 之後、pytest 之前）。
- 測試：`tests/test_check_prose_conditions.py`（12 個測試，含一個守門
  測試 `test_committed_baseline_matches_current_repo_state`，確保
  baseline 檔案沒有偷偷跟 repo 狀態脫鉤）。全部通過。

**Commit `24577447f`：實作 `GET /api/v1/plan/{plan_id}`**
- 問題根源比表面看起來大：不只是缺一個 GET handler，
  `POST /plan`（`create_plan`）跟 `POST /plan/{id}/revise`
  （`revise_plan`）**原本就沒有把產生的 Plan 存到資料庫任何地方**——
  `hospital/db/models.py` 裡有 `Plan` 這張表（`plan_id` 為主鍵，
  `plan_json`、`mrn`、`version`、`supersedes`/`superseded_by`、
  `status` 等欄位），但從來沒人 `db.add()` 過一筆進去。
- `hospital/decision/services/plan_service.py` 新增兩個函式：
  - `persist_plan(db, response, *, mrn, created_by, supersedes=None)`：
    把 `PlanResponse`（不是原始引擎 `PlanResult`——選這個是因為
    `PlanResponse.model_dump_json()` / `model_validate_json()` 可以
    完美 round-trip，不用另外設計序列化格式）存進 `plans` 表。
    **不在函式內 commit**——跟著這個 repo 既有的慣例（見
    `audit_service.log_action` 的註解：「Caller commits the session」），
    讓這筆寫入跟同一個 request 裡的 audit log 屬於同一個 transaction，
    由 `hospital/db/session.py::get_db` 在 request 結束時一次 commit。
  - `get_stored_plan(db, plan_id) -> tuple[PlanResponse, str] | None`：
    查表、反序列化，回傳 `(response, mrn)`——mrn 額外回傳是因為
    `PlanResponse` schema 本身沒有 mrn 欄位，但呼叫端（GET endpoint）
    需要 mrn 才能寫 audit log。
- `hospital/decision/api/plan.py` 新增 `GET /{plan_id}`：查不到回 404
  （`{"error": "PLAN_NOT_FOUND", ...}`），查到的話寫一筆
  `audit_service.PLAN_VIEW`（新常數，`"plan.view"`）audit log——因為
  `DEVELOPMENT_PLAN.md` 的「Locked design decisions」明訂跨醫師存取
  病人資料是允許的，但**每次跨醫師存取都必須寫一筆 AuditLog**，這個
  規則同樣適用於「看別的醫師產生的 Plan」。
- **實測抓到的真 bug**：一開始的寫法是先把 `prior.superseded_by`
  改掉，再 `db.add()` 新的 Plan row——這樣在 SQLite FK enforcement 開
  著的情況下會噴 `FOREIGN KEY constraint failed`，因為
  `superseded_by` 是指向 `plans.plan_id` 的外鍵，指向的那筆
  （新 plan）還沒真的存在。修法：**先 `db.add()` 新 row 並
  `await db.flush()`，再改 `prior.superseded_by`**。這個 bug 是寫
  測試（`test_supersedes_marks_prior_plan_superseded`）時實際跑出來
  抓到的，不是憑空想到的邊界案例。
- 測試：`tests/hospital/test_api_plan_retrieval.py`（8 個測試，涵蓋
  正常建立/查詢、404、未登入 401、沒有 patient_id 時的優雅降級、
  revise 之後兩個版本都能各自查到）。全部通過，加上原本的
  `tests/hospital/` 全部 291 個測試（283 + 8 新增）都通過。

---

## 4. 絕對不能做的事（紅線）

這節是寫給接手的模型看的，請務必遵守：

1. **不要合併任何會改變 Algorithm 路由邏輯的 PR**（也就是發現 A 裡
   SOLE_ANY / SOLE_ALL / MIXED_ALL 這 86%、~549 筆散文 condition 的
   修正）。`specs/CHARTER.md` §8.3 明確禁止 LLM「詮釋 biomarker 來做
   治療選擇」或「選擇臨床建議」——幫一個原本不會動的 gate 挑正確的
   finding-key/門檻值，一旦它開始真的驅動輸出，實質上就是這件事。
2. **不要把任何 `reviewer_signoffs` 標記為完成**，也不要把「看起來
   合理的對應」當成審查通過。`knowledge_base/schemas/algorithm.py`
   裡 `Algorithm.reviewer_signoffs: list[ReviewerSignoff]` 這個欄位
   只有真人 Clinical Co-Lead 可以填。
3. **不要自己去 `specs/CLINICAL_LEADS.md` 幫自己或任何 AI 加一席
   Co-Lead**——那個角色明確要求「Sub-specialty depth in
   oncology/hematology/clinical pharmacology」的真人。
4. **可以做、且不需要臨床審查的事**：
   - 純工具/CI/腳本（像今天的 `check_prose_conditions.py`）
   - 純技術債（依賴宣告、缺失的 API endpoint、測試覆蓋率）
   - **產出稽核文件**（像本文件、像 Phase 1 要做的分類 CSV）——這些
     是分析，不是修改臨床內容
   - **產出「草稿、不可合併」的 PR**（Phase 3）——把遷移建議準備好，
     放著等真人 Co-Lead 來審，但不要按下 merge。
5. 如果不確定一個改動算不算「clinical content」：檢查它有沒有動到
   `knowledge_base/hosted/content/{indications,regimens,redflags,
   contraindications,supportive_care,algorithms}/` 底下的檔案。動到
   就是，先假設需要審查，不要自己判斷「這個應該沒關係」。

---

## 5. 詳細執行計畫：Phase 1-5（prose-condition 遷移）

Phase 0（止血）已經做完（見第 3.2 節）。以下是 Plan agent 設計、我
驗證過的後續階段，**照順序做，每個 Phase 都有明確退出條件**。

### Phase 1 — 建立分類/優先順序工具（產出稽核文件，不需臨床審查）

**要做的事**：寫 `scripts/audit_prose_conditions.py`（注意：跟 Phase 0
的 `check_prose_conditions.py` 是不同檔案，一個是 CI 用的簡單止血
工具，這個是給人看的完整稽核報告）。

**輸入**：`knowledge_base/hosted/content/algorithms/*.yaml`（180 個
檔案）。可以重用 Phase 0 那個腳本裡的 `_iter_clauses()` 遞迴走訪邏輯
（`scripts/check_prose_conditions.py` 裡已經寫好，直接 import 或抄
過來）。

**輸出**：`docs/audits/algorithm_condition_migration_queue.csv`，
每一條散文 condition 一列，欄位建議：

| 欄位 | 說明 |
|---|---|
| `file` | 檔名 |
| `step` | 在 decision_tree 裡的 step 編號 |
| `clause_path` | 在巢狀 all_of/any_of 裡的位置（例如 `any_of[0]`、`all_of[1].any_of[2]`） |
| `condition_text` | 原始散文字串 |
| `structural_class` | `DEAD` / `SOLE_ANY` / `SOLE_ALL` / `MIXED_ALL`（見下方分類邏輯） |
| `confidence` | `HIGH_CONFIDENCE_RENAME` / `NEEDS_NEW_FINDING` / `NEEDS_CLINICAL_JUDGMENT` |
| `proposed_clause` | 對 HIGH_CONFIDENCE_RENAME 才填，自動產生的建議結構化寫法 |
| `candidate_finding_keys` | 比對到的候選 finding key（可能多個） |

**分類邏輯**：
- `DEAD`：這句散文所在的 `any_of` 裡，還有其他 sibling clause 是
  `{finding: ...}` 或 `{red_flag: ...}`（真正會動的），代表這句散文
  存在與否都不影響 `any_of` 的結果。
- `SOLE_ANY` / `SOLE_ALL`：整個 `any_of`/`all_of` 裡全部都是散文
  `condition:`，沒有任何真正的 sibling。
- `MIXED_ALL`：`all_of` 裡混了散文跟真正的 clause——散文會讓整個
  AND 歸零，所以這個 all_of 恆為 False。

**confidence 分級**（比對真實 finding-key 命名空間）：
- 比對來源：sibling clause 裡的 `finding:`/`value:` 欄位名稱、
  RedFlag YAML（`knowledge_base/hosted/content/redflags/*.yaml`）的
  `trigger.*.finding` 欄位、`BIO-*` biomarker ID（
  `knowledge_base/hosted/content/biomarkers/*.yaml` 的 `id:` 欄位）、
  `knowledge_base/engine/redflag_eval.py` 裡的 `FINDING_ALIASES` dict
  （約第 131-140 行附近）。
- `HIGH_CONFIDENCE_RENAME`：散文字串的核心關鍵字（去掉
  mutation/positive/negative 這類修飾詞後）能對應到剛好一個候選
  finding key。**注意**：這只代表「機械式改名的信心高」，**絕對不
  代表「可以自動合併」**——名稱對得上不代表沒有偷偷漏掉一個臨床限定詞
  （例如範例裡 `"HCV RNA positive AND indolent presentation"` 這句，
  HCV 那半句對得上 `bio_hcv_rna.yaml`，但 "indolent presentation"
  完全沒有候選 key，門檻值/正負向也只有臨床醫師能確認）。
- `NEEDS_NEW_FINDING`：完全找不到候選 key，代表這個臨床概念目前
  KB 裡沒有對應的 biomarker/RedFlag/questionnaire 欄位。**範例**：
  `algo_aitl_2l.yaml` 裡的
  `"AITL-typical epigenetic mutations documented (TET2/DNMT3A/IDH2)"`
  ——`bio_idh2_r140q.yaml`/`bio_idh2_r172k.yaml` 存在，但**完全沒有
  `bio_tet2_*` 或 `bio_dnmt3a_*` 檔案**，這條需要先有人新增 biomarker
  內容，不是改名就能解決。
- `NEEDS_CLINICAL_JUDGMENT`：字面上抓不到候選 key，且內容本身就是
  模糊的臨床判斷（例如 "significant comorbidity burden"），需要臨床
  醫師定義門檻/操作型定義，不是資料比對能解決的。

**退出條件**：全部 654（或當時的實際數字）筆散文都有一列，且能重新
跑。這個腳本之後每個 Phase 都要重跑一次，追蹤 backlog 縮小的進度。

**重要**：這份 CSV 是稽核文件（跟 `docs/reviews/*.md` 同性質），
**可以在沒有臨床審查下 commit**，但檔頭要清楚標註「未套用、未審查」。

### Phase 2 — DEAD 分類（100 筆）：**「可證明零行為變更」這個假設已知不成立，改成待審**

**2026-07-04 更新（重要，讀完再動手）**：這一節原本寫「可證明零行為
變更、我可以獨立完成」——**這個假設已經被證明是錯的**，而且是實際套用
後才發現的，不是紙上談兵。過程與根本原因完整記錄在
`docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md`，這裡只
摘要結論：

- `scripts/audit_prose_conditions.py`（Phase 1）已經寫好並可重跑，
  正確標出 100 筆 DEAD-class（`any_of` 裡有 working sibling）。
- `scripts/build_routing_snapshot.py`（Phase 2 快照工具）已經寫好、
  可重跑，用兩種通用樣板（"empty" 全空、"all_true" 把樹上每個真正
  finding key 設 True）快照 180×2=360 筆路由結果。
- **實際套用 100 筆 DEAD 移除後，快照顯示 0 diff（360 筆全部沒變），
  但既有測試套件裡 `test_esophageal_1l_algorithm.py::
  test_escc_cps_positive_chemo_sparing_routes_to_ipi_nivo` 卻真的
  紅了。** 根本原因：`tests/test_esophageal_1l_algorithm.py` 的病人
  fixture 直接把散文原文當 key 塞值（`{"ESCC CPS >=1": True}`），這是
  一個已知的 workaround 寫法（`openonco-state-audit-2026-05-17.md`
  就提過）。我的快照工具的兩種通用樣板都沒有這種「散文字串剛好被當
  key 用」的情況，所以沒測到；只有專案自己既有、手寫的測試套件抓到。
- **結論：光靠 routing snapshot diff 為零，不足以證明這類改動安全**
  ——「DEAD = 同 any_of 有 working sibling」只在一般情況下成立，
  但擋不住「有人直接拿散文字串當 finding key」這種已存在於本 repo 的
  用法。
- 套用的 100 筆已經**全數復原**（`git checkout --`），目前
  `knowledge_base/hosted/content/algorithms/` 沒有任何改動。
- 使用者的決定（2026-07-04）：**把 DEAD-class 清理降級成跟 Phase 3
  一樣的待審模式**——只產出候選清單 + 完整既有測試套件跑過的結果，
  不自動套用到真實 YAML。

**如果你是接手的模型，要真的套用這 100 筆之前，至少要做到**：
1. 不能只看 routing snapshot diff——`scripts/build_routing_snapshot.py`
   的兩種通用樣板不夠。
2. 每一筆候選的散文原文，要對照**整個測試套件 + `examples/*.json`**
   逐字搜尋，確認沒有任何 fixture 把這句原文當成 finding key 在用
   （像 ESCC CPS 這樣）。有的話，這筆就不是真的 DEAD，要轉去 Phase 3
   走臨床審查流程。
3. 每套用一個檔案（甚至每移除一個 clause）就跑一次**完整**既有測試
   套件，任何一個既有測試變紅就整批擋下、立刻復原，不要事後才發現。
4. 即使 (1)-(3) 都過了，套用到 `knowledge_base/hosted/content/` 底下
   仍然是 CHARTER §6.1 管轄範圍——是否要為「可證明安全」的清理開一個
   例外，是專案負責人的決定，不是工程判斷。

`scripts/apply_dead_condition_cleanup.py` 的原始工具還在，dry-run
可以重跑（100/100 驗證通過、0 skip），但**不要在補上上述驗證之前
再次用它寫入真實檔案**。

**建議（不是強制）**：即使工具說「沒有變化」，這批 PR 仍建議找另一位
工程師/維護者看一眼再合併——這不是臨床審查，是一般的技術複核，因為
「工具說沒變」這種話本身也值得再確認一次。

### Phase 3 — 把「會改變路由」的 86%（~549 筆）包裝成待審 PR

**這是硬性停損點：這個 Phase 只產出 PR，絕對不能合併。**

對每個疾病（不是每個檔案）批次產出一個**草稿 PR**（GitHub draft PR，
或如果沒有 push 權限就存成本地分支/patch 檔案），內容包含：
1. 現在的 YAML 原文（該 Algorithm 檔案）。
2. Phase 1 CSV 裡對應列的建議結構化改寫（`proposed_clause` 欄位）。
3. **Phase 2 快照工具算出的非零路由差異**——明確列出「合成病人樣板 X
   原本會走到 indication A，改了以後會走到 indication B，因為
   condition Y 從『恆 False』變成『可能為 True』」。這是給臨床審查者
   看的，讓他們知道「這個改動實際上會讓誰的治療方案不一樣」，而不是
   只丟一個 YAML diff 給他們自己想。
4. 對每一條 Phase 1 標記 `NEEDS_NEW_FINDING` 或
   `NEEDS_CLINICAL_JUDGMENT` 的 clause，**明確用一段文字標註**「這條
   工具解不出來，需要：(a) 新增 biomarker/RedFlag/問卷欄位 XXX，
   或 (b) 臨床醫師定義門檻值/操作型定義」。不要留空，不要假裝
   已經處理。
5. 繼承原本 Algorithm 的 `sources:` 欄位（來源不變，只是把邏輯寫法
   改成引擎看得懂的形式）。

**優先順序**：先做 Phase 1 CSV 裡「這個檔案 step 1 整段都是散文」
的檔案（今天測出來是 99/180，55%），因為這些對每個病人都直接 fallthrough，
影響面最大。

### Phase 4 — 誠實地把「人」的瓶頸講清楚

這不是工程任務。零席 Co-Lead 代表連 §6.2 的緊急路徑（需要至少 1 席）
都用不了。**接手的模型如果做到這一步，應該停下來跟專案負責人回報**：
Phase 3 的草稿 PR 已經準備好等審查，但目前沒有人可以審查，需要
`specs/CLINICAL_LEADS.md` 的申請流程真的有人填。不要試圖繞過這個
限制。

### Phase 5 — 一旦有 ≥1-2 席 Co-Lead 到位

依疾病逐一把 Phase 3 的草稿走完 CHARTER §6.1 流程——每個 PR 已經自帶
路由差異、來源、技術測試。單一疾病「完成」的定義：
`Algorithm.reviewer_signoffs` 填妥兩個真人審查者、快照基準更新為新的
已審查路由、`docs/audits/prose_condition_baseline.json` 對該檔案的
散文數歸零、依 CHARTER §6.1 第 7 步留下 changelog 紀錄。

全域「完成」的定義：全庫散文數量歸零、Phase 0 的 CI 擋新增機制永久
保留、快照安全網變成所有未來 `decision_tree` 修改的標準 CI 要求。

---

## 6. 其他待辦（優先權較低）

這些不在 Phase 0-5 的主線裡，但值得記錄：

1. **治理透明度（技術性小改動，不需臨床審查）**：在 render 出去的
   Plan / 網站上，針對尚未有 Co-Lead 簽核、或含有散文 condition 尚未
   修正的 Algorithm，加上明確的「此決策樹尚待臨床複核」標示。這是
   誠實揭露現況，不是修 bug，也不涉及臨床內容變更。可以參考
   `knowledge_base/engine/render.py` 現有的 badge/警語渲染模式（例如
   `_render_trial_outlook` 附近的寫法）。
2. **病人可看 UI 落差**：`specs/PATIENT_MODE_SPEC.md`/
   `specs/PORTAL_SPEC.md`（Jinja2+HTMX，含 `/patient/{token}`）跟
   `DEVELOPMENT_PLAN.md`（React SPA）互相矛盾，且
   `frontend/src/App.tsx` 完全沒有病人可看的 route。這需要先跟專案
   負責人確認要走哪個架構方向，不建議接手模型自己選一個方向硬做。
3. **Bundle 大小結構性拆分**：核心 bundle 目前 4.03MB，超過 3.5MB
   門檻 534KB，且門檻已經被調高過兩次（`tests/test_engine_bundle_
   optimization.py`）。跟疾病專屬內容進一步移出 core bundle 有關，
   屬於效能/架構問題，不涉及臨床內容。
4. **claim-grounding 語意檢查擴大範圍**：目前預設關閉、只覆蓋 6 筆
   claim（真實分母該是 800+）。`.github/workflows/claim-grounding-
   audit.yml` 已存在，可以評估是否該讓它掃描更多欄位（即使還是
   opt-in），至少讓覆蓋率數字有意義。這個涉及呼叫 Claude API 產生費用
   （文件裡估計 $5-15/次），需要專案負責人決定要不要花這筆錢。

---

## 7. 驗證方式總表

| 階段 | 驗證指令 | 通過標準 |
|---|---|---|
| Phase 0.1（hospital 依賴） | `pytest tests/hospital/ -q` | 283/283 通過（今天已驗證） |
| Phase 0.2（prose ratchet） | `python scripts/check_prose_conditions.py` | 輸出 `... (unchanged)` 或 `(improved)`，不是 `FAILED` |
| Phase 0.3（plan GET） | `pytest tests/hospital/test_api_plan_retrieval.py -q` | 8/8 通過（今天已驗證） |
| Phase 1（稽核 CSV） | 人工抽查 CSV 裡 10-15 筆分類是否合理 | 分類邏輯站得住腳，沒有明顯誤判 |
| Phase 2（DEAD 候選，僅稽核不套用） | `pytest tests/test_algorithm_routing_snapshot.py tests/test_esophageal_1l_algorithm.py tests/test_algorithm_regimen_routing_contracts.py -q` | 全綠（今天已驗證，77 個測試通過）；**套用前**還要對每筆候選做 `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` 列的 4 項額外驗證 |
| Phase 3（草稿 PR） | 人工審閱路由差異報告的可讀性 | 每個 PR 的差異報告讓一個沒讀過程式碼的臨床醫師也看得懂「誰的治療方案會變」 |
| 全域 | `python scripts/audit_validator.py --human` | 0 schema/ref/contract errors（跟今天一樣，這個沒有被這次改動動到） |

---

## 附錄：今天驗證過的關鍵指令（照抄可重現）

```bash
# 確認 hospital 測試能跑
pip install -e ".[hospital,dev]"
pip install --ignore-installed "cryptography>=42"  # 如果撞到系統套件衝突
pytest tests/hospital/ -q   # 應該 283 passed (今天新增 8 個之後是 291)

# 確認 prose-condition 基準線
python3 scripts/check_prose_conditions.py --write-baseline
python3 scripts/check_prose_conditions.py   # 應該 "654 prose conditions (baseline: 654, unchanged)"

# 確認臨床試驗管線測試
pytest tests/test_experimental_options.py tests/test_trial_outlook.py \
  tests/test_ctgov_pagination.py tests/test_ctgov_ua_facilities.py \
  tests/test_src_ctgov_entity.py -q   # 應該 119 passed, 3 skipped

# KB 結構驗證（今天沒動到，應該維持乾淨）
python scripts/audit_validator.py --human
```
