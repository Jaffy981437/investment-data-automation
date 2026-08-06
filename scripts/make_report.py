"""用庫存 csv × 收盤價 csv,產生持股市值與損益的 Markdown 摘要。

輸入:
    data/holdings/holdings_latest.csv   實際庫存(沒有的話退回範例檔,並明確標示)
    data/prices/latest.csv              由 fetch_prices.py 產生

輸出:
    reports/YYYY-MM-DD_持股摘要.md

美股目前沒有報價來源(fetch_prices.py 只抓台股),美股部位會列出但不計價,
不會拿舊價或猜測價格充數。

用法:
    py scripts/make_report.py
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
HOLDINGS = BASE / "data" / "holdings" / "holdings_latest.csv"
HOLDINGS_EXAMPLE = BASE / "data" / "holdings" / "holdings.example.csv"
PRICES = BASE / "data" / "prices" / "latest.csv"
REPORT_DIR = BASE / "reports"


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def as_float(value, default=None):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def fmt(value, digits=2, dash="—"):
    if value is None:
        return dash
    return f"{value:,.{digits}f}"


def main() -> int:
    if not PRICES.exists():
        print(f"[x] 找不到 {PRICES.relative_to(BASE)},請先執行:py scripts/fetch_prices.py")
        return 1

    using_example = False
    if HOLDINGS.exists():
        holdings_path = HOLDINGS
    elif HOLDINGS_EXAMPLE.exists():
        holdings_path = HOLDINGS_EXAMPLE
        using_example = True
        print(f"[!] 找不到 {HOLDINGS.relative_to(BASE)},改用範例檔示範格式。")
        print("    要看真實數字,請把實際庫存存成 holdings_latest.csv(欄位同範例檔)。")
    else:
        print("[x] 找不到任何庫存檔。")
        return 1

    holdings = read_csv(holdings_path)
    prices = {r["code"]: r for r in read_csv(PRICES)}
    price_dates = sorted({r["date"] for r in prices.values() if r.get("date")})

    rows, missing = [], []
    total_cost = total_value = 0.0
    for h in holdings:
        code = (h.get("code") or "").strip()
        shares = as_float(h.get("shares"), 0.0) or 0.0
        avg_cost = as_float(h.get("avg_cost"))
        market = (h.get("market") or "").strip().upper()
        cost = shares * avg_cost if avg_cost is not None else None

        quote = prices.get(code)
        close = as_float(quote.get("close")) if quote else None

        value = pnl = pnl_pct = None
        if close is not None:
            value = shares * close
            if cost:
                pnl = value - cost
                pnl_pct = pnl / cost * 100
        else:
            missing.append((code, h.get("name", ""), market))

        # 只把有報價的台股計入合計,避免不同幣別直接相加
        if market == "TW" and value is not None and cost is not None:
            total_value += value
            total_cost += cost

        rows.append({
            "code": code,
            "name": (h.get("name") or "").strip(),
            "market": market,
            "shares": shares,
            "avg_cost": avg_cost,
            "close": close,
            "cost": cost,
            "value": value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "price_date": quote.get("date") if quote else None,
        })

    rows.sort(key=lambda r: (r["value"] is None, -(r["value"] or 0)))

    today = datetime.now().strftime("%Y-%m-%d")
    out = []
    out.append(f"# 持股摘要 {today}\n")
    if using_example:
        out.append("> ⚠️ **本報表使用範例庫存檔,數字不是真實部位。**\n")
    out.append(f"- 產生時間:{datetime.now():%Y-%m-%d %H:%M:%S}")
    out.append(f"- 庫存來源:`{holdings_path.relative_to(BASE)}`")
    out.append(f"- 報價資料日期:{', '.join(price_dates) or '未知'}\n")

    out.append("| 代號 | 名稱 | 市場 | 股數 | 成交均價 | 收盤價 | 成本 | 市值 | 損益 | 報酬率 |")
    out.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        pct = f"{r['pnl_pct']:+.2f}%" if r["pnl_pct"] is not None else "—"
        pnl = f"{r['pnl']:+,.0f}" if r["pnl"] is not None else "—"
        out.append(
            f"| {r['code']} | {r['name']} | {r['market']} | {fmt(r['shares'], 5)} | "
            f"{fmt(r['avg_cost'])} | {fmt(r['close'])} | {fmt(r['cost'], 0)} | "
            f"{fmt(r['value'], 0)} | {pnl} | {pct} |"
        )

    out.append("")
    if total_cost:
        total_pnl = total_value - total_cost
        out.append("## 台股合計(僅含有報價的台股部位)\n")
        out.append(f"- 總成本:{total_cost:,.0f} 元")
        out.append(f"- 總市值:{total_value:,.0f} 元")
        out.append(f"- 損益:{total_pnl:+,.0f} 元({total_pnl / total_cost * 100:+.2f}%)")
        out.append("")

    if missing:
        out.append("## 查無報價\n")
        for code, name, market in missing:
            reason = "美股報價尚未串接" if market == "US" else "台股報價檔中查無此代號"
            out.append(f"- `{code}` {name} — {reason}")
        out.append("")

    out.append("---\n")
    out.append("報價為官方收盤資料,非即時價;僅供資料整理與紀錄,不構成投資建議。")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"{today}_持股摘要.md"
    report_path.write_text("\n".join(out), encoding="utf-8")

    print(f"已產生:{report_path.relative_to(BASE)}")
    print(f"  持股 {len(rows)} 檔,其中 {len(missing)} 檔查無報價")
    if total_cost:
        print(f"  台股合計:成本 {total_cost:,.0f} / 市值 {total_value:,.0f} "
              f"({(total_value - total_cost) / total_cost * 100:+.2f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
