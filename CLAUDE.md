# 13_投資 — 投資資料自動化

> 專案藍圖。給我自己看,也給接手的 AI Agent 看。
> 建立日期:2026-08-06

---

## 一、專案目標

**主線:自動化資料抓取與報表**

把投資相關的資料收集與整理流程交給程式與 AI Agent 處理,取代目前手動下載、手動貼 Excel 的作法。

具體想達成的:

1. **定期抓取**外部資料(股價、月營收、財報、配息等),存成結構化檔案。
2. **自動產出報表**(追蹤表 / 圖表 / 摘要),不必每次重新拉一次資料。
3. 過程可重複執行、可版控、可交接給下一個 Agent 接手。

> 這是**資料工程專案**,不是投資決策系統。程式只負責取得與呈現資料;買賣判斷由本人決定,Agent 不下單、不轉帳、不給個人化投資建議。

---

## 二、資料夾結構

### 現況(初始化時盤點)

```
13_投資/
├─ CLAUDE.md                       ← 本檔,專案藍圖
├─ .gitignore                      ← 版控白名單
│
├─ 方舟運算/                        ← 既有:20260617 手機截圖數張
├─ 投資/                           ← 既有:安聯大霸 DDO01-S.PDF、信貸洽談錄音(個人敏感)
├─ 大俠武林/                        ← 既有:課程訂閱 Excel 表 9 份(2024.05 版)
│                                     存股紀錄表、市值平衡表、ETF 定期定額 / 查閱表、
│                                     月領息目標張數表、金控自結 EPS、產業月曆、
│                                     總整理財報金控預估殖利率、暫離職場倒數計時器
│
├─ 台股3月營收 (可排序).xlsx
├─ 啟碁產品組合轉型與獲利分析.gdoc     ← Google 雲端捷徑檔(本機無內容)
├─ 股票損益報表與顏色標示.gsheet       ← 同上
└─ VGLT.gsheet                     ← 同上
```

### 程式結構(2026-08-06 建立)

```
13_投資/
├─ .github/workflows/
│  └─ fetch_prices.yml   # 排程每日抓收盤價(平日台北 18:00)
├─ scripts/
│  ├─ fetch_prices.py    # 抓上市+上櫃每日收盤價 → data/prices/
│  ├─ make_report.py     # 庫存 × 收盤價 → reports/ 持股摘要
│  └─ update_excel.py    # 回填收盤價到大俠武林 Excel(預設預演)
├─ data/
│  ├─ prices/            # 每日收盤價 csv(不進版控)
│  └─ holdings/          # 庫存與成本(不進版控,僅範例檔進版控)
│     └─ holdings.example.csv
├─ reports/              # 產出的報表(不進版控)
├─ backups/              # update_excel.py --apply 前的自動備份
└─ docs/
   └─ 方舟運算_操作流程.md
```

### 資料來源(全部免費、不需 API Key,已實測可用)

| 用途 | 端點 |
|---|---|
| 上市收盤價 | `openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL` |
| 上櫃收盤價 | `www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes` |
| 個股基本資料(產業別) | `openapi.twse.com.tw/v1/opendata/t187ap03_L` |
| 月營收 | `openapi.twse.com.tw/v1/opendata/t187ap05_L` |

已知特性,改程式時別踩回去:

- **兩市場更新時間不同步**。TPEx 常比 TWSE 早幾小時,同一次執行可能拿到不同交易日,
  所以依「市場 + 資料日期」分開存檔,不硬湊成同一天。
- **TPEx 回傳含 9,000+ 筆權證**。過濾規則:6 碼且前兩碼屬於
  `03~08`(上市權證)或 `70~73`(上櫃權證)。
  不可用「6 碼且非 0 開頭」這種粗規則 —— 會誤殺 `2887Z1` 特別股與 `910322` 等 DR。
- **TPEx 回應約 4MB,實測常中途斷線**,`fetch()` 的重試不是防禦性程式碼,是必要的。
- **大俠武林的 Excel 原本是 Google Sheets**,「即時股價」欄是 `GOOGLEFINANCE` 公式,
  下載成 xlsx 後才失效。在 Google 試算表裡本來就會自動更新,回填反而會把公式寫死。
- 那些 xlsx 含繪圖物件,openpyxl 儲存會重寫整個檔案並使其永久遺失,
  所以 `update_excel.py` 預設只預演,`--apply` 才寫入且一定先備份。

**注意**:`.gdoc` / `.gsheet` 只是 Google 雲端的捷徑檔(189 bytes),本機讀不到內容。要程式處理這些資料,得先另存為 xlsx/csv,或改用 Google Sheets API。

---

## 三、工作慣例

- 語言:一律繁體中文(台灣用語)。
- Python 一律用 `py` 啟動(本機沒設 `python` 別名)。
- 動工前先提規劃,確認後再執行。
- 敏感資料(API Key、帳密、.env)一律不進版控、不上傳。
- 大型二進位檔(xlsx / pdf / jpg / aac)不進版控,原始檔留在 Google Drive 本身即可。

### 版控策略

`.gitignore` 採**白名單模式**:預設忽略全部,只放行 `.md` / `.py` / `.csv` / `.json` / `.yml` / `.txt` 等文字檔。

理由:

1. 這是 Google Drive 同步資料夾,repo 越小越不容易出事。
2. Excel、PDF、錄音、截圖做 diff 沒有意義,只會讓 repo 肥大。
3. 新增檔案時預設不會被 git 看到,較不會誤把敏感檔加進版控。

**要納入新的副檔名時**,在 `.gitignore` 的白名單區塊加一行 `!*.副檔名`。

> **Google Drive 同步提醒**:`.git` 目錄會被 Google Drive 一起同步。請避免在多台電腦同時對這個 repo 操作 git,否則可能造成 repo 損壞。若日後要多機協作,建議把程式碼搬到 Google Drive 之外的資料夾。

---

## 四、待辦 Backlog

### 卡住,需要本人操作(程式已備妥,等環境)

- [ ] **申請開通永豐 Shioaji API**(https://ai.sinotrade.com.tw/,線上申辦)
      → 開通後填 `.env`,即可實測 `scripts/fetch_holdings_sinopac.py`
- [ ] **安裝 adb(platform-tools)並開啟 Android USB 偵錯**
      → 本機目前查無 `adb` 指令,`scripts/ark/probe_ark.py` 無從跑起

> 券商相關的決策已在 2026-08-06 完成,詳見 `docs/庫存自動化_規劃.md`:
> 5 家券商(永豐、新光、富邦、土銀、Firstrade)已盤點,永豐走 API、富邦暫不納入、其餘走網頁 DOM。

### 方舟自動化(B 段)— 規劃完成,卡在環境

詳見 `docs/方舟自動化_詳細規劃.md`。關鍵決定:**不走社群的「截圖點像素」,改走 ADB + uiautomator**,
用元件文字定位而非像素座標,介面改版比較不會壞,也不需要 Computer Use 桌面權限。

手機系統已確認:**Android、iPhone 都有 → 走 Android + USB/ADB,不必裝模擬器**。
範圍已收斂成只做「庫存」同步,不動布局自選。

- [ ] 裝好 adb、接上手機後跑 `py scripts/ark/probe_ark.py` 驗證 UI 樹可讀性
- [ ] 依驗證結果決定走 ADB 路線或視覺路線

### 下一步可做

- [ ] 月營收抓取與「創歷史新高 / 連續三月創高」篩選(取代 2021 年的舊 xlsx)
- [ ] 美股報價來源(目前 `fetch_prices.py` 只有台股,美股部位不計價)
- [ ] 庫存快照歷史化:`data/holdings/history/YYYY-MM-DD_holdings.csv`

### 已完成

- [x] 決定資料來源 → TWSE / TPEx 官方 OpenAPI,免費不需 Key
- [x] 第一支抓取腳本 `scripts/fetch_prices.py`
- [x] 持股摘要報表 `scripts/make_report.py`
- [x] Excel 回填 `scripts/update_excel.py`(預設預演)
- [x] 理解方舟運算操作流程 → `docs/方舟運算_操作流程.md`
- [x] **排程每日自動執行 fetch_prices** → 改用 GitHub Actions,不用 Windows 工作排程器
      (原規劃是工作排程器,但那需要電腦開著;GitHub Actions 免費且不必顧機器)
- [x] 推上 GitHub → https://github.com/Jaffy981437/investment-data-automation(Public)

### 已評估,結論是不做

- **用 Google Sheets API 讀寫既有 `.gsheet`**:那些表用的是 `GOOGLEFINANCE` 公式,
  在 Google 試算表裡本來就會自動更新股價,再串 API 灌價格是多餘的。
  真正值得串 API 的是「把庫存與成本寫進去」,等券商來源確定後再評估。

---

## 五、進度紀錄

### 2026-08-06 — 專案初始化

- 盤點資料夾現況(3 個子資料夾 + 4 個根目錄檔案,皆為既有手動整理的資料)。
- 確認專案方向:自動化資料抓取與報表。
- 建立 `CLAUDE.md`(本檔)、`.gitignore`(白名單模式)。
- `git init`,建立初始 commit。
- 尚未寫任何程式,資料來源與標的清單待決定。

### 2026-08-06 — 開工:第一支腳本 + 方舟運算流程理解

**環境**:Python 3.12.0,pandas / openpyxl / requests / lxml / bs4 / matplotlib 皆已安裝。

**完成**:

1. `scripts/fetch_prices.py` — 抓上市 1,377 檔 + 上櫃 1,012 檔收盤價,實測可跑。
2. `scripts/make_report.py` — 產出持股市值 / 損益 Markdown 摘要。
   美股目前無報價來源,會明確標示「查無報價」而不是拿舊價充數。
3. `scripts/update_excel.py` — 回填收盤價到大俠武林 Excel,預設預演。
4. `docs/方舟運算_操作流程.md` — 整理 LINE 社群記錄的完整操作流程與風險評估。
5. `.gitignore` 補強:排除 `data/`、`reports/`、`方舟運算/`(社群對話含大量他人個資)。

**關鍵發現**:

- **方舟運算是手機 APP,沒有 API**。Windows 要靠 MuMuPlayer 模擬器 + GUI 自動化。
- **資料流方向與直覺相反**:庫存是從券商流「進」方舟,不是從方舟抓出來。
  所以「透過方舟抓取庫存和成本」實務上得改成「從券商取得,再寫進方舟」。
- 大俠武林 Excel 的股價欄是 `GOOGLEFINANCE` 公式(原本是 Google Sheets)。

**待本人決定**:券商是哪一家、有無庫存匯出功能。這是庫存自動化的唯一起點。

### 2026-08-21 — 上 GitHub + 排程自動化

**完成**:

1. **repo 推上 GitHub**:https://github.com/Jaffy981437/investment-data-automation(**Public**)
   - 推送前確認過 tracked 檔案無敏感資料(只有 `.env.example`,無真實金鑰)
   - 白名單 `.gitignore` 有效運作,`data/`、`reports/`、`方舟運算/` 都沒被帶上去
2. **GitHub Actions 排程** `.github/workflows/fetch_prices.yml`
   - 平日台北時間 18:00 執行(`cron: "0 10 * * 1-5"`,UTC+8 換算)
   - 只裝 `requests`(fetch_prices.py 唯一依賴,不需 pandas/shioaji)
   - 抓到的 csv **不 commit 回 repo**,改用 `upload-artifact` 保留 90 天可下載
   - 有 `workflow_dispatch`,可在 GitHub 網頁手動觸發
   - 已手動觸發驗證通過(23 秒完成,2330/0050/0056/00919 收盤價正確)

**工具安裝踩雷紀錄**(下次不用重踩):

- `winget install --id GitHub.cli` 在這台機器**必定失敗**,exit code 1603,
  日誌只有一句 "Install server not responding"。**用系統管理員身分執行也一樣失敗**,
  所以不是權限問題,是 winget 安裝服務本身的問題。
- **解法:用免安裝版**。下載官方 zip 解壓到 `C:\Users\user\tools\gh\bin\gh.exe`,
  再把該目錄加進使用者 PATH。已完成,`gh` 現在全域可用。
- `gh repo create --source=.` 在這個 worktree 會誤判「不是 git repo」
  (疑似中文路徑 + git worktree 結構),**改成先建空 repo、再手動 `git remote add` 即可**。

**待注意**:

- 本次是從 worktree 分支 `claude/project-initialization-kickoff-a76afa` 推到遠端 `main`。
  主工作目錄的本機 `main` 分支目前**落後遠端**,下次在主目錄工作前要先 `git pull`。
- GitHub Actions 排程不保證準點(官方說明可能延遲數分鐘至數十分鐘),非設定錯誤。

**產出的研究報告**(非程式,存在 `reports/`,不進版控):

- `reports/投資Anthropic.html` — Anthropic 美股曝險研究,15 章節單檔 HTML。
  內容:六家持有 Anthropic 的美股、兩種占比排序、進場時機與估值階梯、IPO 時程推算、
  上市後四個傳導管道、AWS 獲利原理、雲端規模排名、GOOGL/GOOG 股別差異。
  **含免責聲明與利益揭露,非投資建議。**關鍵推估值待 Anthropic 公開版 S-1 出爐後需更新。
