# 台股上市＋上櫃每日收盤行情自動下載

使用 GitHub Actions，週一至週五 **台灣時間 18:30** 自動執行（GitHub 排程可能延遲，非精確保證）。手動執行可指定交易日期。另提供可續跑的多年歷史回補，以及週線、月線 OHLCV 彙整。

## 上傳與啟用

1. 解壓 ZIP，將**資料夾內全部內容（包含 `.github` 隱藏資料夾）**上傳到 GitHub Repository 根目錄。建議用電腦操作，手機 GitHub 網頁操作較不方便。
2. GitHub Repository → Settings → Actions → General → Workflow permissions → **Read and write permissions**（如可選）→ Save。
3. Repository → Actions → **Download Taiwan stock closing prices** → Run workflow，首次手動測試。
4. 查看 Actions 執行紀錄，以及 `data/twse/YYYY-MM-DD.csv`、`data/tpex/YYYY-MM-DD.csv`。`data/last_run.json` 記錄成功與錯誤。

## 歷史資料回補（2021 起）

到 Actions 手動執行 **Backfill Taiwan stock history**，輸入開始、結束日期。預設每次只嘗試 20 個尚未下載的平日，避免官方限流或 Actions 超時；同一區間可重複執行，程式會略過已存在的 `.csv` 或 `.csv.gz` 後接續處理。

也可在本機執行：

```bash
python backfill.py --start 2021-01-01 --end 2026-10-10 --max-days 20
python aggregate.py --start-year 2021 --end-year 2026
```

- 回補日線：`data/twse/YYYY-MM-DD.csv.gz`、`data/tpex/YYYY-MM-DD.csv.gz`
- 週線：`data/weekly/YYYY.csv.gz`
- 月線：`data/monthly/YYYY.csv.gz`
- 回補狀態：`data/backfill_state.json`

歷史資料使用 gzip 壓縮；每日既有的未壓縮 CSV 仍可並存與彙整。若某個舊平日兩市場都沒有資料，會記為可能休市日；只有單一市場失敗則保留錯誤，供下次重試。

## 儲存欄位

日線欄位為 `date,market,stock_id,name,open,high,low,close,volume,change,change_pct,change_status`；價格為新台幣，成交量以**股**為單位。週線與月線另有 `sessions`（該期實際交易日數）。CSV 使用 UTF-8 BOM，可由 Excel 開啟。

## 來源與限制

- 上市：臺灣證券交易所 TWSE `exchangeReport/MI_INDEX`。
- 上櫃：櫃買中心 TPEx `afterTrading/dailyQuotes`。
- 使用**公開行情介面**，若官方改版、限流、阻擋自動請求或延後公布，程式會報錯；未在本環境進行官方 API 線上實測，首次部署務必核對筆數與個股收盤價。
- 休市週末跳過；平日休市或資料未公布則記錄錯誤，不會造假或回填舊資料。
- 官方資料可能包含 ETF 等非普通股商品；此版本僅初步以數字證券代號篩選，**尚未建立精準的上市櫃普通股名單**。後續選股應加上商品分類過濾。
- 多年回補須分批執行；完成後應依 `backfill_state.json` 與檔案日期做完整性檢查，再計算 MACD(201/202)、ADX(300) 與月線指標。
- GitHub Actions 定時執行不需要 Render；未來可讓 Render 讀取資料庫或 GitHub CSV。
- 若 GitHub 禁用排程、權限不足或執行額度限制，工作流程不會自動成功。需檢查 Actions 日誌。
