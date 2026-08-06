"""抓取台股每日收盤價(上市 TWSE + 上櫃 TPEx),存成 csv。

資料來源皆為官方 OpenAPI,免費、不需 API Key:
  - TWSE 上市:https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
  - TPEx 上櫃:https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes

兩個市場的更新時間不同(TPEx 較早,TWSE 常常晚幾小時),所以同一次執行
可能拿到不同日期的資料。腳本不猜測、不對齊日期,一律以 API 回傳的 Date
欄為準,並依各市場的實際資料日期分開存檔。

預設會濾掉權證(代號 6 碼且非 0 開頭,例如 70xxxx「宏捷科統一5C購01」),
上櫃光權證就有 9,000 多筆,留著只是雜訊。要保留請加 --all。

用法:
    py scripts/fetch_prices.py
    py scripts/fetch_prices.py --all      # 不濾權證
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT_DIR = BASE / "data" / "prices"

TWSE_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMEOUT = 60

FIELDS = [
    "date", "code", "name", "market",
    "open", "high", "low", "close", "change",
    "volume", "amount",
]


def roc_to_iso(roc: str) -> str:
    """民國日期字串 1150805 -> 2026-08-05。轉不了就原樣回傳。"""
    roc = (roc or "").strip()
    if len(roc) == 7 and roc.isdigit():
        return f"{int(roc[:3]) + 1911:04d}-{roc[3:5]}-{roc[5:7]}"
    return roc


def to_num(value) -> str:
    """把 API 的數字字串正規化;無成交('--'、'')回空字串。"""
    s = str(value or "").strip().replace(",", "").replace("+", "")
    if s in ("", "--", "---", "-", "null", "None"):
        return ""
    try:
        return str(float(s))
    except ValueError:
        return ""


# 權證 / 牛熊證的 6 碼代號前綴。上市權證 03xxxx~08xxxx,上櫃權證 70xxxx~73xxxx。
# 不能用「6 碼且非 0 開頭」這種粗規則:那會誤殺 2887Z1(台新新光己特,特別股)
# 與 910322(康師傅-DR)這類 6 碼的正常標的。
WARRANT_PREFIXES = frozenset({"03", "04", "05", "06", "07", "08", "70", "71", "72", "73"})


def is_warrant(code: str) -> bool:
    """判斷是否為權證 / 牛熊證。ETF(00xxxx)與 ETN(02xxxx)不受影響。"""
    return len(code) == 6 and code[:2] in WARRANT_PREFIXES


def fetch(url: str, retries: int = 3) -> list[dict]:
    """抓 JSON,失敗重試。

    TPEx 那支回應有 4MB,實測常在傳輸中途斷掉(ChunkedEncodingError),
    所以重試不是防禦性程式碼,是必要的。
    """
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                print(f"      第 {attempt} 次失敗({type(exc).__name__}),{attempt * 3} 秒後重試…")
                time.sleep(attempt * 3)
    raise last_exc  # type: ignore[misc]


def parse_twse(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        code = (r.get("Code") or "").strip()
        if not code:
            continue
        out.append({
            "date": roc_to_iso(r.get("Date")),
            "code": code,
            "name": (r.get("Name") or "").strip(),
            "market": "TWSE",
            "open": to_num(r.get("OpeningPrice")),
            "high": to_num(r.get("HighestPrice")),
            "low": to_num(r.get("LowestPrice")),
            "close": to_num(r.get("ClosingPrice")),
            "change": to_num(r.get("Change")),
            "volume": to_num(r.get("TradeVolume")),
            "amount": to_num(r.get("TradeValue")),
        })
    return out


def parse_tpex(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        code = (r.get("SecuritiesCompanyCode") or "").strip()
        if not code:
            continue
        out.append({
            "date": roc_to_iso(r.get("Date")),
            "code": code,
            "name": (r.get("CompanyName") or "").strip(),
            "market": "TPEx",
            "open": to_num(r.get("Open")),
            "high": to_num(r.get("High")),
            "low": to_num(r.get("Low")),
            "close": to_num(r.get("Close")),
            "change": to_num(r.get("Change")),
            "volume": to_num(r.get("TradingShares")),
            "amount": to_num(r.get("TransactionAmount")),
        })
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig:Excel 直接點開不會中文亂碼
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser_cli = argparse.ArgumentParser(description="抓取台股每日收盤價")
    parser_cli.add_argument("--all", action="store_true", help="不過濾權證,保留全部標的")
    args = parser_cli.parse_args()

    print(f"執行時間:{datetime.now():%Y-%m-%d %H:%M:%S}")

    rows: list[dict] = []
    for label, url, parser in (
        ("上市 TWSE", TWSE_URL, parse_twse),
        ("上櫃 TPEx", TPEX_URL, parse_tpex),
    ):
        try:
            raw = fetch(url)
        except Exception as exc:
            print(f"  [x] {label} 抓取失敗:{type(exc).__name__}: {exc}")
            continue

        parsed = parser(raw)
        dropped = 0
        if not args.all:
            kept = [r for r in parsed if not is_warrant(r["code"])]
            dropped = len(parsed) - len(kept)
            parsed = kept

        dates = sorted({r["date"] for r in parsed if r["date"]})
        note = f",濾掉權證 {dropped:,} 筆" if dropped else ""
        print(f"  [v] {label}:{len(parsed):>6,} 檔,資料日期 {', '.join(dates) or '未知'}{note}")
        rows.extend(parsed)

    if not rows:
        print("兩個來源都沒抓到資料,中止。")
        return 1

    rows.sort(key=lambda r: (r["market"], r["code"]))

    # 兩個市場的資料日期常常不同步,依「市場 + 實際資料日期」分開存,
    # 避免把不同交易日的價格混在同一個檔名底下。
    print()
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["date"], r["market"]), []).append(r)
    for (date, market), grp in sorted(groups.items()):
        path = OUT_DIR / f"{date}_{market}.csv"
        write_csv(path, grp)
        print(f"已存檔:{path.relative_to(BASE)}  ({len(grp):,} 檔)")

    write_csv(OUT_DIR / "latest.csv", rows)
    print(f"已存檔:{(OUT_DIR / 'latest.csv').relative_to(BASE)}  (合併 {len(rows):,} 檔,每列自帶 date 欄)")

    dates_seen = sorted({r["date"] for r in rows if r["date"]})
    if len(dates_seen) > 1:
        print(f"\n[!] 注意:兩個市場資料日期不一致 {dates_seen}。")
        print("    通常是 TWSE 當日資料尚未發布,晚點重跑即可補上。")

    # 抽樣核對,方便一眼確認資料合理
    sample = {r["code"]: r for r in rows if r["code"] in ("2330", "0050", "0056", "00919")}
    if sample:
        print("\n抽樣核對:")
        for code in ("2330", "0050", "0056", "00919"):
            if code in sample:
                r = sample[code]
                print(f"  {code} {r['name']:<12} 收盤 {r['close']:>10}  漲跌 {r['change']:>8}  ({r['date']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
