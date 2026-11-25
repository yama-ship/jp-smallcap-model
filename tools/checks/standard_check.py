#!/usr/bin/env python3
"""Standard 契約後の接続確認(較正計画 第3-2節・第6節)。GitHub Actions で実行する。

出力するのは件数と割合だけ。銘柄コード・価格・財務の値は出さない(CHARTER 第8章)。
取得したデータはメモリの中だけで扱い、ファイルに保存しない。

確かめること:
1. 2017年の日付のデータが取れるか(株価四本値、バリュエーション指標、財務情報の件数)
2. 当事業年度終了日(CurFYEn)が 2017〜2018年の通期決算(CurPerType=FY)のレコードについて、
   開示書類種別(DocType)の会計基準・連結単体の区分ごとに:
   - 全件数、ShEq が埋まっている件数、ShEq・EqAR・TA がすべて埋まっている件数
   - 「一致」(|ShEq÷TA − EqAR| ≤ 0.0006)の件数と割合
   - EqAR が 1 を超える件数、EqAR が空の件数(オーナーの指示、2026-11-25)
   - 単体の区分では、ShEq と NCShEq のそれぞれが埋まっている件数
3. 2017〜2018年に3項目がそろうレコードが0件なら、ShEq が埋まっている通期決算のうち、
   CurFYEn がいちばん新しい年で 2 と同じことを数える
4. 合格の判定:比べた対象全体で「一致」が 95% 以上
"""

import collections
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.jquants.com/v2"
KEY = os.environ.get("JQUANTS_API_KEY", "")
TOL = 0.0006
PASS_SHARE = 0.95
SLEEP = 0.6  # Standard のレートリミット(120件/分)に余裕を持たせる
calls = 0


def get_all(path, params):
    global calls
    rows, params = [], dict(params)
    while True:
        url = API + path + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"x-api-key": KEY})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    body = json.load(r)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 4:
                    time.sleep(30)
                    continue
                print("http_error path=%s status=%d" % (path, e.code))
                sys.exit(1)
        calls += 1
        rows.extend(body.get("data", []))
        time.sleep(SLEEP)
        nxt = body.get("pagination_key")
        if not nxt:
            return rows
        params["pagination_key"] = nxt


def num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def group_of(doctype):
    """DocType から(会計基準, 連結/単体)を取り出す。例 FYFinancialStatements_Consolidated_JP"""
    parts = (doctype or "").split("_")
    if len(parts) >= 3:
        cons = {"Consolidated": "連結", "NonConsolidated": "単体"}.get(parts[1], parts[1])
        return parts[2], cons
    # 決算短信以外(業績予想の修正など)は、DocType の名前をそのまま区分にする
    return (doctype or "空"), "-"


def fetch_fins(start, end):
    """開示日 start〜end の財務情報をすべて取る(日付ごと)。"""
    rows, d = [], start
    while d <= end:
        rows.extend(get_all("/fins/summary", {"date": d.isoformat()}))
        d += dt.timedelta(days=1)
    return rows


def tally(records, label):
    stats = collections.defaultdict(collections.Counter)
    for r in records:
        g = group_of(r.get("DocType"))
        c = stats[g]
        sheq, eqar, ta, ncsheq = num(r.get("ShEq")), num(r.get("EqAR")), num(r.get("TA")), num(r.get("NCShEq"))
        c["全件数"] += 1
        c["ShEq あり"] += sheq is not None
        c["NCShEq あり"] += ncsheq is not None
        c["EqAR 空"] += eqar is None
        c["EqAR > 1"] += eqar is not None and eqar > 1
        if sheq is not None and eqar is not None and ta is not None and ta > 0:
            c["3項目そろう"] += 1
            c["一致"] += abs(sheq / ta - eqar) <= TOL
    print("## %s" % label)
    print("| 会計基準 | 連結/単体 | 全件数 | ShEq あり | NCShEq あり | 3項目そろう | 一致 | 一致の割合 | EqAR > 1 | EqAR 空 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    tot = collections.Counter()
    for g in sorted(stats):
        c = stats[g]
        tot.update(c)
        share = "%.4f" % (c["一致"] / c["3項目そろう"]) if c["3項目そろう"] else "-"
        print("| %s | %s | %d | %d | %d | %d | %d | %s | %d | %d |" % (
            g[0], g[1], c["全件数"], c["ShEq あり"], c["NCShEq あり"], c["3項目そろう"],
            c["一致"], share, c["EqAR > 1"], c["EqAR 空"]))
    share = tot["一致"] / tot["3項目そろう"] if tot["3項目そろう"] else None
    print("| 合計 | | %d | %d | %d | %d | %d | %s | %d | %d |" % (
        tot["全件数"], tot["ShEq あり"], tot["NCShEq あり"], tot["3項目そろう"], tot["一致"],
        "%.4f" % share if share is not None else "-", tot["EqAR > 1"], tot["EqAR 空"]))
    return tot, share


def main():
    if not KEY:
        print("secret_present=false")
        sys.exit(1)
    print("secret_present=true")

    # 1. 2017年の日付のデータが取れるか(2017-02-01 は水曜日の営業日)
    print("## 2017年の日付のデータ(2017-02-01)")
    for path in ["/equities/bars/daily", "/equities/valuation", "/fins/summary"]:
        n = len(get_all(path, {"date": "2017-02-01"}))
        print("- %s: %d 件" % (path, n))

    # 2. CurFYEn が 2017〜2018年の通期決算(開示は 2017-02-01〜2019-12-31 に収まる想定)
    rows = fetch_fins(dt.date(2017, 2, 1), dt.date(2019, 12, 31))
    fy = [r for r in rows if r.get("CurPerType") == "FY" and str(r.get("CurFYEn", ""))[:4] in ("2017", "2018")]
    tot, share = tally(fy, "CurFYEn が 2017〜2018年の通期決算")
    used = "2017〜2018年"

    # 3. 0件なら、ShEq がある直近の年で数える
    if tot["3項目そろう"] == 0:
        for year in range(2025, 2017, -1):
            rows = fetch_fins(dt.date(year, 1, 1), min(dt.date(year + 1, 12, 31), dt.date.today()))
            fy = [r for r in rows if r.get("CurPerType") == "FY" and str(r.get("CurFYEn", ""))[:4] == str(year)]
            if any(num(r.get("ShEq")) is not None for r in fy):
                tot, share = tally(fy, "ShEq が埋まっている直近の年:CurFYEn が %d 年の通期決算" % year)
                used = "%d年" % year
                break

    # 4. 判定
    print("## 判定")
    print("- 比べた対象: %s" % used)
    if share is None:
        print("- 結果: 判定できない(3項目がそろうレコードがない)")
    else:
        print("- 一致の割合: %.4f(合格の基準 %.2f 以上)" % (share, PASS_SHARE))
        print("- 結果: %s" % ("合格" if share >= PASS_SHARE else "不合格(計算に進まず、オーナーに報告する)"))
    print("- API の呼び出し回数: %d" % calls)


if __name__ == "__main__":
    main()
