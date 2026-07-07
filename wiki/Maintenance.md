# 維護 Maintenance

本頁是日常維護的操作指南：環境設定、跑測試、驗證知識庫、CI 門檻、以及多 agent 協作協定。

## 環境設定

```bash
# 核心 + 開發依賴
pip install -e ".[dev]"

# Hospital Edition 後端（FastAPI + async SQLAlchemy）
pip install -e ".[hospital,dev]"

# 資料抽取（PDF/OCR）
pip install -e ".[ingestion]"
```

> **已知環境陷阱**：某些映像檔的系統層 `cryptography`（apt 裝的 41.x）沒有 pip metadata，會讓 `python-jose` 匯入時崩潰。解法：`pip install --ignore-installed "cryptography>=42"`。這是環境問題，不是 repo 程式碼問題。

Python 版本：3.11+，但 schema 層需要 3.12（PEP 585）。Windows 上 `python` 常解析到 3.8，跑驗證器／測試請用 `C:/Python312/python.exe` 或 `py -V:3.12`。

## 跑測試

```bash
# 知識庫相關的核心測試
pytest tests/ --ignore=tests/hospital -q

# Hospital Edition 後端（DEVELOPMENT_PLAN.md 的 "Gate rule"）
pytest tests/hospital/ -q          # 應 283/291 全綠

# 前端
cd frontend && npm run typecheck && npm run test -- --run
```

> **已知的既有失敗（不是你造成的）**：完整套件跑下來會有約 17 個既有失敗，全部是知識庫內容漂移／bundle 大小門檻問題（例如 NSZU 給付比例掉到門檻以下、藥物 `last_verified` 過期、core bundle 超過 3.5MB、某些疾病缺紅旗五型矩陣）。這些與程式邏輯無關，詳見 `docs/reviews/preexisting-failures-2026-04-27.md`。改動前後比對失敗清單，只要沒有**新增**失敗就代表你的改動乾淨。

## 驗證知識庫

```bash
# schema + 參照完整性（CI 的主要門檻）
python scripts/audit_validator.py --human
# 應輸出：Clean — 0 schema errors, 0 ref errors, 0 contract errors

# prose-condition 止血檢查（Phase 0.2）
python scripts/check_prose_conditions.py
# 應輸出：654 prose conditions (baseline: 654, unchanged)

# 演算法路由回歸快照（Phase 2）
python scripts/build_routing_snapshot.py --check
```

## CI 門檻（`.github/workflows/validate-kb.yml`）

在觸及 `knowledge_base/**`、`specs/**`、`scripts/**`、`tests/**`、`pyproject.toml` 的 PR 上執行：

1. **Schema + 參照完整性**：`python scripts/audit_validator.py --human`
2. **Prose-condition 止血 ratchet**：`python scripts/check_prose_conditions.py` — 新演算法檔含任何散文 condition、或既有檔散文數增加，直接擋下。
3. **一組 pytest**：validator contracts、routing contracts、prose-condition 測試、routing snapshot、build-site 靜態資產等。
4. Lint（`ruff`，非阻擋）。

> CI 目前只擋得住「格式錯」（schema、參照、prose 成長）——**擋不住「臨床內容錯」**（劑量、regimen-biomarker 搭配、指引時效）。臨床正確性靠的是 CHARTER §6.1 的兩人審查，而那個機制目前沒有人在執行（見[技術債](Tech-Debt)）。

## 新增內容的工作流程

- **新增知識庫實體**：先看 `specs/KNOWLEDGE_SCHEMA_SPECIFICATION.md`。規格含糊 → 提出缺口、問人，不要自己發明欄位。
- **新增來源**：照 `specs/SOURCE_INGESTION_SPEC.md` §8 + §20。授權分類是門檻，不是形式。預設 `referenced`。
- **臨床內容**：每個事實主張都要 Source 引用（`CLINICAL_CONTENT_STANDARDS`）。影響臨床建議的改動需 CHARTER §6.1 兩人簽核。
- **優先改既有 spec 檔**。新 spec 文件要在 CHARTER 的文件清單註冊。

## 多 agent 協作協定（重要）

這個 repo 同時跑多個平行 Claude/Codex session。分支、工作樹、HEAD 可能在任兩個指令之間無預警改變。把 repo 狀態當成「對抗性可變」。

### 每次任務前的 pre-flight（強制）

```bash
git rev-parse --abbrev-ref HEAD    # 預期分支
git rev-parse HEAD                 # 預期 commit
git status --short                 # 預期乾淨（或已知的修改）
```

任一項與交辦不符 → **停下、回報、不要繼續**。狀態由協調 session 修正，agent 不自行修。

### 分支與 commit 紀律

- 一個工作流 = 一個具名功能分支（`feat/*`、`hotfix/*`）。**絕不直接 commit 到 `master`。**
- **絕不刪分支**、**絕不 force-push**，除非使用者明確指示。
- **`git add -A` 與 `git add .` 禁用**——一律用明確 pathspec（別的 agent 會留下未追蹤檔，`-A` 會吞掉）。
- 一個 agent = 一個邏輯 commit（或具名的小集合）。跨 agent 的複合 commit 禁止。
- pre-commit hook 會跑，**絕不用 `--no-verify`**。
- 平行 agent（背景批次、多 agent 執行）**必須**用 worktree 隔離。

### 停止條件（中止 + 回報，不要繼續）

HEAD 在非預期分支、工作樹被意外修改、預期 commit 不在當前分支、stash/cherry-pick/merge 衝突、出現陌生分支/tag、改動會落在交辦允許清單之外的檔案。

## 遠端執行環境

- 容器是隔離、短暫的；repo 在容器啟動時全新 clone，閒置一段時間後回收。**要保留的東西一定先 commit + push。**
- 對外 HTTPS 走預設 proxy（CA bundle 在 `/root/.ccr/ca-bundle.crt`）。TLS 失敗或收到 403/405/407，看 `/root/.ccr/README.md`，別關掉 TLS 驗證、別 unset `HTTPS_PROXY`。
- 已預裝 Chromium + Playwright（`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`）。不要跑 `playwright install`。

## 每日／定期自動作業

- `.github/workflows/civic-monthly-refresh.yml` — CIViC 每月抓取 + diff + 開 PR。
- `.github/workflows/claim-grounding-audit.yml` — 每週（週一 06:00 UTC）跑 claim-grounding 偵測（僅偵測模式，語意檢查要手動 dispatch，會產生 Claude API 費用）。
- 站台每日刷新（`chore(site): daily refresh`）自動 commit 到 master。
