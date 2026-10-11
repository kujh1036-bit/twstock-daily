# 台股上市＋上櫃每日收盤行情自動下載

使用 GitHub Actions，週一至週五 **台灣時間 18:30** 自動執行（GitHub 排程可能延遲，非精確保證）。手動執行可指定交易日期。

## 上傳與啟用

1. 解壓 ZIP，將**資料夾內全部內容（包含 `.github` 隱藏資料夾）**上傳到 GitHub Repository 根目錄。建議用電腦操作，手機 GitHub 網頁操作較不方便。
2. GitHub Repository → Settings → Actions → General → Workflow permissions → **Read and write permissions**（如可選）→ Save。
3. Repository → Actions → **Download Taiwan stock closing prices** → Run workflow，首次手動測試。
4. 查看 Actions 執行紀錄，以及 `data/twse/YYYY-MM-DD.csv`、`data/tpex/YYYY-MM-DD.csv`。`data/last_run.json` 記錄成功與錯誤。

## 儲存欄位

`date,market,stock_id,name,open,high,low,close,volume`；價格為新台幣，成交量以**股**為單位。使用 UTF-8 BOM CSV，可由 Excel 開啟。

## 來源與限制

- 上市：臺灣證券交易所 TWSE `exchangeReport/MI_INDEX`。
- 上櫃：櫃買中心 TPEx `afterTrading/dailyQuotes`。
- 使用**公開行情介面**，若官方改版、限流、阻擋自動請求或延後公布，程式會報錯；未在本環境進行官方 API 線上實測，首次部署務必核對筆數與個股收盤價。
- 休市週末跳過；平日休市或資料未公布則記錄錯誤，不會造假或回填舊資料。
- 官方資料可能包含 ETF 等非普通股商品；此版本僅初步以數字證券代號篩選，**尚未建立精準的上市櫃普通股名單**。後續選股應加上商品分類過濾。
- `data/` 是每日快照，不會自動補抓過往所有日期。若要算 MACD(201/202)、ADX(300)、月線指標，必須另外建立多年歷史資料回補與完整性檢查。
- GitHub Actions 定時執行不需要 Render；未來可讓 Render 讀取資料庫或 GitHub CSV。
- 若 GitHub 禁用排程、權限不足或執行額度限制，工作流程不會自動成功。需檢查 Actions 日誌。
