# 介紹 Introduction

## 這個專案是什麼

OpenOnco 是一個**免費、開源的腫瘤科臨床決策支援資源**。核心使用情境：

> 醫師上傳一份病人資料（診斷、分期、生物標記、體能狀態、共病等）→ 系統回傳**兩套並列的治療計畫**（標準 standard + 積極 aggressive），每一項建議都附完整來源引用。當新資料進來（新的化驗值、醫師決策、更新的指引）時，計畫會刷新。

線上 Demo：**[openonco.info](https://openonco.info)**（瀏覽器內直接試用，用 Pyodide 在前端跑真正的 Python 引擎，病人資料不離開裝置）。**這是 `try.html` 展示頁專屬的特性,不是整個系統的保證**——Hospital Edition 與未來的 CQL/ELM 決策引擎（[ADR-0005](../docs/adr/0005-production-decision-engine-runs-server-side.md)）跑在伺服器端,正式部署場景以決策邏輯正確性為優先,而非前端零後端執行。

## 為什麼存在

替一位真實病人挑一個療程，通常是 **2–4 小時的桌上作業**：翻 NCCN PDF、對照 ESMO、重讀當地的烏克蘭衛生部（МОЗ）protocol、確認藥品給付、查腎／肝功能劑量調整、疊上支持性照護、記得疫苗與伺機性感染預防。每一個病人都要來一次。漏掉一個禁忌可能致命。

OpenOnco 把這些雜事自動化。醫師拿到的是一份**每項都已附引用的草擬計畫**，只需驗證與微調。整套邏輯模擬**經典的多學科腫瘤討論會（MDT）**——每個「虛擬專科」是一個版本化的規則模組，帶自己的來源與 `last_reviewed` 時間戳。

## 整體架構

```
病人資料（FHIR R4/R5 + mCODE）
        │
        ▼
┌──────────────────────────────────────────────┐
│  宣告式規則引擎  knowledge_base/engine/*.py      │
│  ─ 讀取版本化 YAML 知識庫                        │
│  ─ Algorithm 決策樹 → 選 default + alternative   │
│  ─ RedFlag 評估、禁忌、支持性照護、監測          │
│  ─ 生物標記可行性（CIViC ESCAT 分級）            │
│  ─ 臨床試驗第三軌（ClinicalTrials.gov）           │
└──────────────────────────────────────────────┘
        │
        ▼
  Render 層（單檔 A4 可列印 HTML，病人模式 / 醫師模式，UA / EN）
        │
        ├─▶ 靜態站台 openonco.info（Pyodide 瀏覽器內引擎）
        └─▶ Hospital Edition（FastAPI 後端 + React SPA，見下）
```

### 三大子系統

1. **知識庫 + 規則引擎**（`knowledge_base/`）——專案的核心。YAML 資料 + Pydantic schema 驗證 + 宣告式引擎。
2. **靜態站台**（`docs/` + `scripts/build_site.py`）——約 190 個病例 HTML，伺服器端建置，前端用 Pyodide 跑引擎。
3. **Hospital Edition**（`hospital/` + `frontend/`）——FastAPI 後端（病人登錄、時間軸事件、HIS 轉接、提醒引擎、會診、MTD）+ React/Vite/TypeScript SPA。283 個後端測試通過。

## 關鍵不變量（違反就是 bug）

| 不變量 | 出處 | 說明 |
|---|---|---|
| **LLM 不是臨床決策者** | CHARTER §8.3 | 臨床建議來自宣告式規則引擎讀版本化知識庫。LLM 只做：樣板程式、文件草稿、臨床文件抽取（需人工驗證）、翻譯（需臨床複核）。**不做**：挑療程、生成劑量、為選藥而詮釋生物標記。 |
| **臨床內容兩人審查** | CHARTER §6.1 | 任何影響臨床建議、位於 `knowledge_base/hosted/content/` 的改動，需三位臨床共同負責人其中兩位簽核。 |
| **病人資料零破壞性操作** | CHARTER §9.3 | 病人檔案不得洩入 git 歷史或公開產物。公開前需知情同意 + 去識別化 + 倫理審查。 |
| **來源預設 `referenced`** | SOURCE_INGESTION_SPEC §1.4 | 託管（hosting）需明確的 H1–H5 justification。 |
| **免費公共資源 → 非商業** | CHARTER §2 | 許多來源授權都依賴這一點。 |
| **可行性資料源 = CIViC（CC0）** | — | OncoKB 因 ToS 與 CHARTER §2 衝突已否決。引擎模組用 `actionability_*` 命名。 |

## 技術選型

- **Python 3.11+**（schema 層需 3.12，PEP 585）。
- 依賴：`pydantic`、`httpx`、`pyyaml`/`ruamel.yaml`、`pypdf`/`pdfplumber`、`pytesseract`。Hospital Edition 另需 `fastapi`、`sqlalchemy`、`alembic`、`python-jose`、`pydantic-settings`、`slowapi`（見 `pyproject.toml` 的 `hospital` extras）。
- **儲存 = YAML 檔 + git 歷史**，載入時用 Pydantic 驗證。實體數超過約 10K 時再遷移到 PostgreSQL。
- 沒有 Django、沒有 ORM（知識庫層）、沒有重框架。
- **FHIR R4/R5 + mCODE** 作為病人輸入資料模型。
- MVP 不用 SNOMED CT、不用 MedDRA（授權門檻）。改用 LOINC + ICD-10/O-3 + RxNorm + CTCAE v5.0。

## 真相來源階層（衝突時的優先順序）

1. `specs/CHARTER.md` — 專案治理 + 範疇
2. 其他 `specs/*.md` — 臨床、資料、schema、來源、參考案例
3. `CLAUDE.md`
4. `README.md`
5. `legacy/` 底下任何東西 — **非權威**，僅歷史參考

## 儲存庫佈局（頂層）

```
knowledge_base/
├── clients/        # SourceClient 實作（ctgov、pubmed、dailymed、openfda、cpic…）
├── engine/         # 規則引擎 + render + MDT（40 個模組）
├── schemas/        # Pydantic 實體 schema
├── validation/     # YAML 載入器 + 驗證器
├── ingestion/      # МОЗ 抽取器、civic_loader.py…
└── hosted/
    ├── content/    # 知識庫 YAML 資料
    └── civic/      # CIViC 每日快照（CC0）
docs/               # 建置站台（openonco.info）+ reviews/ + audits/
hospital/           # Hospital Edition FastAPI 後端
frontend/           # React/Vite/TypeScript SPA
scripts/            # build_site.py、稽核工具、遷移工具
specs/              # 24 份規格文件（英文為準，烏克蘭原文在 uk/）
tests/              # pytest 套件（118 + 20 hospital）
legacy/             # 退役的 autoresearch 管線（非權威）
```

延伸閱讀：`README.md`、`CLAUDE.md`、`specs/CHARTER.md`、`docs/reviews/fable-opinion.md`（策略優先順序判斷與分階段執行計畫）。
