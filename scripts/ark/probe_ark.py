"""方舟運算 GUI 自動化 — 可行性驗證。

在寫任何自動化之前先跑這支。它只做「看」,不點任何按鈕、不改任何資料。

要回答的問題:方舟運算的畫面能不能用 adb 的 uiautomator 拿到「有文字的元件」?
  能   → 可以用「找 text='自選' 的節點」來定位,介面改版也不容易壞
  不能 → 得退回截圖 + 視覺判讀(社群那套),脆弱很多

前置:
  1. 裝好 MuMuPlayer 並在裡面裝好、登入「方舟運算」
     (或用實體 Android 手機接 USB 並開啟 USB 偵錯)
  2. 把方舟運算開在前景

用法:
    py scripts/ark/probe_ark.py
    py scripts/ark/probe_ark.py --port 16416     # 第二個模擬器實例
    py scripts/ark/probe_ark.py --serial XXXX    # 指定裝置(實體手機)
    py scripts/ark/probe_ark.py --save-xml       # 另存 UI 樹,供對元素用
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
OUT_DIR = BASE / "data" / "ark"

# MuMuPlayer 12 第一個實例是 16384,每多一個實例 +32
DEFAULT_PORT = 16384

ADB_CANDIDATES = [
    r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
    r"C:\Program Files\Netease\MuMuPlayerGlobal-12.0\shell\adb.exe",
    r"C:\Program Files (x86)\Netease\MuMu\emulator\nemu\vmonitor\bin\adb_server.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
]

# 方舟底部分頁與關鍵頁面的字,用來判斷 UI 樹有沒有抓到有意義的東西
ARK_KEYWORDS = ["自選", "策略", "運算", "布局自選", "調節庫存", "庫存", "編輯"]


def find_adb() -> str | None:
    found = shutil.which("adb")
    if found:
        return found
    for path in ADB_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def run(adb: str, *args: str, timeout: int = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run([adb, *args], capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "(逾時)"
    out = (proc.stdout or b"").decode("utf-8", "replace")
    err = (proc.stderr or b"").decode("utf-8", "replace")
    return proc.returncode, (out + err).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="方舟運算 adb 可行性驗證")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"模擬器 adb 埠(預設 {DEFAULT_PORT})")
    ap.add_argument("--serial", help="指定裝置序號;實體手機用 adb devices 查")
    ap.add_argument("--save-xml", action="store_true", help="把 UI 樹另存到 data/ark/")
    args = ap.parse_args()

    print("=" * 68)
    print("方舟運算 — adb 可行性驗證(唯讀,不會點任何東西)")
    print("=" * 68)

    adb = find_adb()
    if not adb:
        print("\n[x] 找不到 adb。")
        print("    裝好 MuMuPlayer 後,adb 通常在:")
        print(r"      C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe")
        print("    或另外安裝 Android SDK Platform Tools 並加入 PATH。")
        return 1
    print(f"\n[v] adb: {adb}")
    print(f"    {run(adb, 'version')[1].splitlines()[0]}")

    # --- 連線 ---
    if not args.serial:
        target = f"127.0.0.1:{args.port}"
        print(f"\n連線 {target} …")
        code, out = run(adb, "connect", target)
        print(f"    {out}")
        if "connected" not in out.lower():
            print("\n[x] 連不上。檢查:")
            print("    - 模擬器有沒有開著")
            print("    - 埠號對不對(MuMuPlayer 多開時每個實例 +32:16384/16416/16448…)")
            print("    - 模擬器設定裡的 ADB 偵錯是否開啟")
            return 1
        serial = target
    else:
        serial = args.serial

    code, out = run(adb, "devices")
    print(f"\n裝置清單:\n{out}")
    if serial not in out or "device" not in out:
        print(f"\n[x] {serial} 不在清單中或狀態不是 device。")
        return 1

    dev = ["-s", serial]

    # --- 找方舟的 package ---
    print("\n尋找方舟運算的 package name …")
    code, pkgs = run(adb, *dev, "shell", "pm", "list", "packages")
    candidates = [p.replace("package:", "").strip() for p in pkgs.splitlines()
                  if re.search(r"ark|fangzhou|方舟", p, re.I)]
    if candidates:
        for c in candidates:
            print(f"    可能是:{c}")
    else:
        print("    沒找到含 ark 的 package。等一下用前景 App 判斷。")

    code, cur = run(adb, *dev, "shell", "dumpsys", "window", "|", "findstr", "mCurrentFocus")
    if not cur.strip():
        code, cur = run(adb, *dev, "shell", "dumpsys", "activity", "activities")
        cur = "\n".join(l for l in cur.splitlines() if "mResumedActivity" in l)
    print(f"\n目前前景 App:\n    {cur.strip()[:300] or '(讀不到)'}")

    # --- dump UI 樹 ---
    print("\n抓取 UI 元素樹 …")
    code, out = run(adb, *dev, "shell", "uiautomator", "dump", "/sdcard/ark_ui.xml", timeout=60)
    print(f"    {out}")
    if "dumped" not in out.lower() and "UI hierchary" not in out:
        print("\n[!] dump 失敗。可能原因:畫面正在動畫中、或 App 阻擋 uiautomator。")
        print("    讓畫面靜止後重試一次;仍失敗代表要走截圖視覺路線。")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    local_xml = OUT_DIR / "ark_ui.xml"
    code, out = run(adb, *dev, "pull", "/sdcard/ark_ui.xml", str(local_xml), timeout=60)
    if not local_xml.exists():
        print(f"[x] 取回 XML 失敗:{out}")
        return 1

    # --- 分析 ---
    try:
        root = ET.parse(local_xml).getroot()
    except ET.ParseError as exc:
        print(f"[x] XML 解析失敗:{exc}")
        return 1

    nodes = list(root.iter("node"))
    with_text = [n for n in nodes if (n.get("text") or "").strip()]
    with_id = [n for n in nodes if (n.get("resource-id") or "").strip()]
    with_desc = [n for n in nodes if (n.get("content-desc") or "").strip()]
    clickable = [n for n in nodes if n.get("clickable") == "true"]

    print("\n" + "=" * 68)
    print("分析結果")
    print("=" * 68)
    print(f"  總節點數        : {len(nodes)}")
    print(f"  有 text 的      : {len(with_text)}")
    print(f"  有 resource-id  : {len(with_id)}")
    print(f"  有 content-desc : {len(with_desc)}")
    print(f"  可點擊的        : {len(clickable)}")

    texts = [(n.get("text") or "").strip() for n in with_text]
    if texts:
        print(f"\n  畫面上讀到的文字(前 30 個):")
        for t in texts[:30]:
            print(f"     · {t}")

    hits = [k for k in ARK_KEYWORDS if any(k in t for t in texts)]
    print(f"\n  命中方舟關鍵字:{hits or '(無)'}")

    # --- 判讀 ---
    print("\n" + "=" * 68)
    if len(with_text) >= 5 and hits:
        print("✅ 結論:可以走 ADB + UI 樹路線")
        print("   畫面元件帶得出文字,可以用『找 text=自選 的節點』來定位,")
        print("   不必猜像素座標,介面改版也比較不會壞。")
        verdict = "adb"
    elif len(with_text) >= 5 or len(with_id) >= 5:
        print("⚠️  結論:部分可用")
        print("   拿得到一些節點但沒命中方舟關鍵字。可能不在方舟畫面,")
        print("   或部分頁面是自繪的。請確認方舟開在前景後重跑;")
        print("   若仍如此,採混合方案:能用節點的用節點,其餘用截圖定位。")
        verdict = "partial"
    else:
        print("❌ 結論:UI 樹幾乎是空的")
        print("   方舟可能是 Flutter / React Native 這類自繪框架。")
        print("   要退回截圖 + 視覺判讀路線(社群那套),穩定度較低。")
        verdict = "visual"
    print("=" * 68)

    if args.save_xml:
        print(f"\nUI 樹已存:{local_xml.relative_to(BASE)}")
    else:
        print(f"\nUI 樹暫存於:{local_xml.relative_to(BASE)}")
    print(f"判讀結果:{verdict}")
    print("\n把上面整段輸出貼回對話,我依結果決定下一步怎麼寫。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
