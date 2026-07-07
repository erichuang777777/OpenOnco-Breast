# OpenOnco Wiki（zh-TW）— 原始碼與發布說明

這個資料夾是 OpenOnco GitHub Wiki 的**初始化內容**（繁體中文），已依 GitHub Wiki 慣例組織成一個完整、可直接 push 的 git repository。

## 為什麼放在主 repo 裡？

本工作環境的對外 git proxy 政策範圍**只涵蓋主 repo**（`erichuang777777/OpenOnco-Breast`），不涵蓋它的 `.wiki.git` 端點——直接 push 到 wiki 會被 egress policy 擋下（HTTP 403，非認證問題，不可繞過）。因此 wiki 內容以兩種形式保存在這裡，供你在本機一鍵發布：

1. **`*.md` 頁面原始檔**（可直接閱讀／審查／編輯）。
2. **`openonco-wiki.gitbundle`** — 一個自帶完整 git 歷史的 bundle，可原樣還原成 wiki repo 並 push。

## 頁面清單（GitHub Wiki 格式）

| 檔案 | Wiki 頁面 | 內容 |
|---|---|---|
| `Home.md` | 首頁 | 專案總覽 + 現況數字 + 導覽 |
| `Introduction.md` | 介紹 | 是什麼／為什麼／架構／關鍵不變量 |
| `Maintenance.md` | 維護 | 環境、測試、驗證、CI、多 agent 協定 |
| `Roadmap.md` | 路線圖 | 已完成里程碑 + 未來方向 |
| `Plan.md` | 開發計畫 | prose-condition 遷移 Phase 0-5 + Hospital Edition |
| `Tech-Debt.md` | 技術債 | 已知技術債與治理缺口（附嚴重度） |
| `_Sidebar.md` | 側欄 | 導覽 |
| `_Footer.md` | 頁尾 | 免責聲明 |

## 如何發布到 GitHub Wiki

前置：在 GitHub repo 的 **Settings → Features** 勾選 **Wikis**，並（如果 wiki 從未建立過）先在網頁上隨便建一頁以初始化 `.wiki.git` 端點。

### 方法 A：從 bundle 還原（保留提交歷史）

```bash
git clone OpenOnco-Breast.wiki.git   # 或先 clone 空 wiki
git clone wiki/openonco-wiki.gitbundle wiki-restored
cd wiki-restored
git remote add wiki https://github.com/erichuang777777/OpenOnco-Breast.wiki.git
git push wiki HEAD:master
```

### 方法 B：直接複製 markdown

```bash
git clone https://github.com/erichuang777777/OpenOnco-Breast.wiki.git
cp wiki/*.md OpenOnco-Breast.wiki/
cd OpenOnco-Breast.wiki
git add . && git commit -m "Initialize zh-TW wiki" && git push
```

> 發布後可安全刪除主 repo 的這個 `wiki/` 資料夾（它只是初始化用的來源）；或保留作為 wiki 內容的版本控管來源。

## 維護原則

- 這些頁面的數字（實體計數、prose-condition 654 筆、Co-Lead 席次等）是 2026-07 校準的快照。內容大幅變動時記得同步更新。
- 每一項的權威來源是 repo 內的 `specs/`、`docs/reviews/fable-opinion.md` 與各 audit 文件；wiki 是這些的 zh-TW 摘要與導覽，不是真相來源。
