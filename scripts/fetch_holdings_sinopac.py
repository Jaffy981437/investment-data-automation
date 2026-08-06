"""用永豐金證券 Shioaji API 查詢庫存與成本,輸出成統一格式的 csv。

驗證狀態
  已驗證:shioaji 1.7.2 的介面簽章與 StockPosition 欄位
          login(api_key, secret_key) / list_positions(account, unit=...)
          StockPosition: code, quantity, price, direction, last_price, pnl, yd_quantity
  未驗證:實際登入與查詢(手邊沒有已開通的永豐帳號)
第一次執行若對不上,加 --raw 把原始欄位貼回來,照實際結構修正。

前置作業(你自己做,我不能代勞):
  1. 到 https://ai.sinotrade.com.tw/ 申請開通 API,建立 API Key / Secret Key
  2. 安裝套件:py -m pip install shioaji
  3. 複製 .env.example 成 .env,填入 API Key 與 Secret Key

輸出:
  data/holdings/sinopac_YYYY-MM-DD.csv     當日快照
  data/holdings/holdings_latest.csv        合併檔(目前只有永豐,之後多券商會合併)

用法:
    py scripts/fetch_holdings_sinopac.py            # 查庫存並存檔
    py scripts/fetch_holdings_sinopac.py --raw      # 額外印出 API 原始欄位,供除錯
    py scripts/fetch_holdings_sinopac.py --dry-run  # 只登入與查詢,不寫檔
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ENV_FILE = BASE / ".env"
OUT_DIR = BASE / "data" / "holdings"
BROKER = "永豐"

FIELDS = ["date", "code", "name", "market", "shares", "avg_cost",
          "currency", "broker", "note"]


def load_env(path: Path) -> dict[str, str]:
    """讀 .env。刻意不用第三方套件,也刻意不把值印出來。"""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def to_dict(obj) -> dict:
    """把 Shioaji 回傳的物件轉成 dict,容忍不同版本的介面差異。"""
    for attr in ("model_dump", "dict", "_asdict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return dict(fn())
            except TypeError:
                pass
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    return {"raw": str(obj)}


def pick(d: dict, *names, default=""):
    """從多個可能的欄位名取值 —— 不同版本欄位名不一定相同。"""
    for n in names:
        if n in d and d[n] not in (None, ""):
            return d[n]
    return default


def load_names() -> dict[str, str]:
    """從收盤價檔補股票名稱 —— Shioaji 的 StockPosition 只有代號沒有名稱。"""
    path = BASE / "data" / "prices" / "latest.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["code"]: r["name"] for r in csv.DictReader(f)}


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="永豐 Shioaji 查庫存")
    ap.add_argument("--raw", action="store_true", help="印出 API 原始欄位,供對欄位用")
    ap.add_argument("--dry-run", action="store_true", help="不寫檔,只顯示結果")
    args = ap.parse_args()

    try:
        import shioaji as sj
    except ImportError:
        print("[x] 尚未安裝 shioaji。請執行:py -m pip install shioaji")
        return 1

    env = load_env(ENV_FILE)
    api_key = env.get("SINOPAC_API_KEY") or os.environ.get("SINOPAC_API_KEY")
    secret_key = env.get("SINOPAC_SECRET_KEY") or os.environ.get("SINOPAC_SECRET_KEY")

    if not api_key or not secret_key:
        print(f"[x] 找不到 API 金鑰。請複製 .env.example 成 .env 並填入:")
        print("    SINOPAC_API_KEY=...")
        print("    SINOPAC_SECRET_KEY=...")
        print(f"    (.env 路徑:{ENV_FILE})")
        return 1

    api = sj.Shioaji()
    try:
        print("登入永豐 API…")
        api.login(api_key=api_key, secret_key=secret_key)
        print(f"  [v] 登入成功,股票帳號:{getattr(api.stock_account, 'account_id', '(未取得)')}")

        # 一定要指定 unit=Share。預設是 Unit.Common(張),拿到的數字會差 1000 倍,
        # 而方舟運算與美股都以「股」為單位。
        positions = api.list_positions(api.stock_account, unit=sj.Unit.Share)
        print(f"  [v] 取得 {len(positions)} 檔庫存\n")

        if args.raw and positions:
            print("=== API 原始欄位(第一筆)===")
            for k, v in to_dict(positions[0]).items():
                print(f"   {k}: {v!r}")
            print()

        today = datetime.now().strftime("%Y-%m-%d")
        names = load_names()
        if not names:
            print("  [!] 找不到 data/prices/latest.csv,股票名稱會留空。")
            print("      先跑 py scripts/fetch_prices.py 就能補上名稱。\n")

        rows = []
        for pos in positions:
            d = to_dict(pos)
            # 欄位名以 shioaji 1.7.2 的 StockPosition 為準:
            # code / quantity / price / direction / last_price / pnl / yd_quantity
            code = str(pick(d, "code", "stock_id", "symbol"))
            shares = float(pick(d, "quantity", "yd_quantity", default=0) or 0)
            rows.append({
                "date": today,
                "code": code,
                "name": names.get(code, ""),
                "market": "TW",
                "shares": f"{shares:g}",
                "avg_cost": str(pick(d, "price", "avg_price", "cost")),
                "currency": "TWD",
                "broker": BROKER,
                "note": f"direction={pick(d, 'direction')}",
            })

        rows.sort(key=lambda r: r["code"])
        print(f"{'代號':<8}{'名稱':<12}{'股數':>12}{'成交均價':>12}")
        print("-" * 46)
        for r in rows:
            print(f"{r['code']:<8}{r['name']:<12}{r['shares']:>12}{r['avg_cost']:>12}")

        if args.dry_run:
            print("\n(--dry-run,未寫檔)")
            return 0

        snapshot = OUT_DIR / f"sinopac_{today}.csv"
        write_csv(snapshot, rows)
        write_csv(OUT_DIR / "holdings_latest.csv", rows)
        print(f"\n已存檔:{snapshot.relative_to(BASE)}")
        print(f"        {(OUT_DIR / 'holdings_latest.csv').relative_to(BASE)}")
        print("\n接著可跑:py scripts/make_report.py")
        return 0

    except Exception as exc:
        print(f"[x] 失敗:{type(exc).__name__}: {exc}")
        print("    若是欄位或介面對不上,請加 --raw 重跑,把輸出貼回來對欄位。")
        return 1
    finally:
        try:
            api.logout()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
