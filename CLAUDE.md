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

### 卡住,需要本人決定

- [ ] **券商是哪一家?** 這是整條鏈的真正起點 —— 庫存與成本只能從券商取得,方舟運算沒有 API
- [ ] 券商有沒有提供對帳單 / 庫存匯出(csv、xlsx)?有的話完全不必截圖 OCR
- [ ] 主要是台股、美股,還是兩者都有?(決定要不要串美股報價)
- [ ] 是否真的需要寫回方舟 APP,還是有庫存紀錄與報表就夠?

### 方舟自動化(B 段)— 規劃完成,卡在環境

詳見 `docs/方舟自動化_詳細規劃.md`。關鍵決定:**不走社群的「截圖點像素」,改走 ADB + uiautomator**,
用元件文字定位而非像素座標,介面改版比較不會壞,也不需要 Computer Use 桌面權限。

- [ ] **你的手機是 Android 還是 iPhone?** Android 可直接 USB + ADB,完全不用裝模擬器
- [ ] 裝好模擬器(或接上手機)後跑 `py scripts/ark/probe_ark.py` 驗證 UI 樹可讀性
- [ ] 依驗證結果決定走 ADB 路線或視覺路線

### 下一步可做

- [ ] 月營收抓取與「創歷史新高 / 連續三月創高」篩選(取代 2021 年的舊 xlsx)
- [ ] 美股報價來源(目前 `fetch_prices.py` 只有台股,美股部位不計價)
- [ ] 排程每日自動執行 fetch_prices(Windows 工作排程器)
- [ ] 庫存快照歷史化:`data/holdings/history/YYYY-MM-DD_holdings.csv`

### 已完成

- [x] 決定資料來源 → TWSE / TPEx 官方 OpenAPI,免費不需 Key
- [x] 第一支抓取腳本 `scripts/fetch_prices.py`
- [x] 持股摘要報表 `scripts/make_report.py`
- [x] Excel 回填 `scripts/update_excel.py`(預設預演)
- [x] 理解方舟運算操作流程 → `docs/方舟運算_操作流程.md`

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
