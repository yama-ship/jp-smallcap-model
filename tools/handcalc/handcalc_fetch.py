#!/usr/bin/env python3
"""較正の手計算用に、選んだ銘柄・期間のデータだけを J-Quants API から一度取得する。

オーナーのパソコンで実行する(較正計画 第2-3節、data_spec 第6節の例外)。
Python 3.8 以上の標準ライブラリだけで動く。追加のインストールは要らない。

使い方は tools/handcalc/README.md を参照。

- API キーは、実行時に画面で入力する(表示されない)。環境変数 JQUANTS_API_KEY があればそれを使う。
  キーはファイルにも画面にも出さない。
- 取得したデータは、指定したフォルダにだけ CSV で保存する。画面には件数だけを出す。
- Git のリポジトリの中のフォルダには保存しない(市場データを Git に入れないため。CHARTER 第8章)。
"""

import argparse
import csv
import datetime as dt
import getpass
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.jquants.com/v2"
MANIFEST = "manifest.json"
DEFAULT_OUT = os.path.join(os.path.expanduser("~"), "jp-smallcap-calibration")
# 財務情報は、開示日が期間の始まりの12か月前から、終わりの3か月後までを残す(較正計画 第2-3節)
FINS_MONTHS_BEFORE = 12
FINS_MONTHS_AFTER = 3


def add_months(d, n):
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    last = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return dt.date(y, m, min(d.day, last))


def parse_item(text):
    try:
        code, start, end = text.split(":")
        s = dt.date.fromisoformat(start)
        e = dt.date.fromisoformat(end)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "銘柄コード:開始日:終了日 の形で書いてください(例 72030:2019-03-01:2019-08-31): " + text)
    if not code.isalnum() or s > e:
        raise argparse.ArgumentTypeError("銘柄コードか日付の順番が正しくありません: " + text)
    return code, s, e


def inside_git_repo(path):
    p = os.path.abspath(path)
    while True:
        if os.path.exists(os.path.join(p, ".git")):
            return True
        parent = os.path.dirname(p)
        if parent == p:
            return False
        p = parent


def get_all(path, params, key):
    """pagination_key がなくなるまで取得し、data の行をすべて返す。"""
    rows = []
    params = dict(params)
    while True:
        url = API + path + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"x-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.load(resp)
        except urllib.error.HTTPError as e:
            # キーやデータを表示しないよう、状態コードだけを出す
            sys.exit("取得に失敗しました(HTTP %d、%s)。API キーと契約プランを確かめてください。" % (e.code, path))
        rows.extend(body.get("data", []))
        nxt = body.get("pagination_key")
        time.sleep(1)  # レートリミットに余裕を持たせる
        if not nxt:
            return rows
        params["pagination_key"] = nxt


def write_csv(path, rows):
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def cmd_fetch(args):
    out = os.path.abspath(args.out)
    if inside_git_repo(out):
        sys.exit("このフォルダは Git のリポジトリの中にあります。リポジトリの外のフォルダを指定してください: " + out)
    os.makedirs(out, exist_ok=True)
    key = os.environ.get("JQUANTS_API_KEY") or getpass.getpass("J-Quants の API キー(入力しても表示されません): ")
    if not key:
        sys.exit("API キーが入力されませんでした。")

    manifest_path = os.path.join(out, MANIFEST)
    manifest = {"files": []}
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

    for code, start, end in args.item:
        bars = get_all("/equities/bars/daily",
                       {"code": code, "from": start.isoformat(), "to": end.isoformat()}, key)
        lo = add_months(start, -FINS_MONTHS_BEFORE).isoformat()
        hi = add_months(end, FINS_MONTHS_AFTER).isoformat()
        fins = [r for r in get_all("/fins/summary", {"code": code}, key)
                if lo <= str(r.get("DiscDate", "")) <= hi]
        names = ["%s_bars_%s_%s.csv" % (code, start, end), "%s_fins_%s_%s.csv" % (code, lo, hi)]
        write_csv(os.path.join(out, names[0]), bars)
        write_csv(os.path.join(out, names[1]), fins)
        for n in names:
            if n not in manifest["files"]:
                manifest["files"].append(n)
        print("%s: 株価 %d 行、財務情報 %d 行を保存しました" % (code, len(bars), len(fins)))

    manifest["fetched_at"] = dt.datetime.now().isoformat(timespec="seconds")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print("保存先: " + out)
    print("このフォルダの中身は、会話にもリポジトリにも入れないでください。")


def cmd_delete(args):
    out = os.path.abspath(args.out)
    manifest_path = os.path.join(out, MANIFEST)
    if not os.path.exists(manifest_path):
        sys.exit("このスクリプトで作ったフォルダではないようです(manifest.json がありません): " + out)
    with open(manifest_path, encoding="utf-8") as f:
        files = json.load(f)["files"]
    others = [n for n in os.listdir(out) if n not in files and n != MANIFEST]
    print("削除するフォルダ: " + out)
    if others:
        print("このスクリプトが作っていないファイルも入っています(手計算の表など): %d 個" % len(others))
        print("それらもまとめて削除します。残したいものがあれば、先に別の場所へ移してください。")
    if input("削除してよければ yes と入力してください: ").strip() != "yes":
        sys.exit("削除しませんでした。")
    shutil.rmtree(out)
    print("削除しました。削除した日を STATE.md に記録します(Claude に伝えてください): "
          + dt.date.today().isoformat())


def main():
    ap = argparse.ArgumentParser(description="較正の手計算用データの取得と削除")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="選んだ銘柄・期間のデータを取得する")
    f.add_argument("--out", default=DEFAULT_OUT, help="保存先のフォルダ(既定: %s)" % DEFAULT_OUT)
    f.add_argument("--item", type=parse_item, action="append", required=True,
                   help="銘柄コード:開始日:終了日(複数回書ける)")
    f.set_defaults(func=cmd_fetch)
    d = sub.add_parser("delete", help="較正の後で、保存先のフォルダごと削除する")
    d.add_argument("--out", default=DEFAULT_OUT, help="保存先のフォルダ(既定: %s)" % DEFAULT_OUT)
    d.set_defaults(func=cmd_delete)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
