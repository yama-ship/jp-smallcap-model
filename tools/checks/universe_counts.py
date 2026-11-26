#!/usr/bin/env python3
"""上場銘柄一覧(キャッシュに置いた master)から、区分ごとの件数を数える(較正計画 第3-1節の対象銘柄の定義のため)。

出力するのは件数だけ。銘柄コードや会社名は出さない(CHARTER 第8章)。

数えること:
1. 決めた日付ごとに、商品区分(ProdCat)× 市場区分(Mkt)の件数
2. 同じ日付の株価四本値の行数と、上場銘柄一覧にない銘柄の行数
3. 内国株券(ProdCat=011)のうち、銘柄コードの5桁目が 0 でないもの(普通株以外の種類株の可能性)の件数
4. 取得期間全体で、ProdCat ごとの銘柄の数(重複なし)
"""
import collections
import glob
import gzip
import json
import os
import sys

DATA = sys.argv[1] if len(sys.argv) > 1 else "data"
SAMPLE_DATES = ["2017-02-01", "2018-06-29", "2019-03-01", "2020-06-30"]


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def find(dataset, date):
    hits = glob.glob(os.path.join(DATA, dataset, "*", date + ".json.gz"))
    return hits[0] if hits else None


def main():
    for d in SAMPLE_DATES:
        mp = find("master", d)
        if not mp:
            print("## %s: 上場銘柄一覧のファイルがない" % d)
            continue
        master = load(mp)
        print("## %s" % d)
        c = collections.Counter((r.get("ProdCat", ""), r.get("Mkt", "")) for r in master)
        print("| 商品区分 ProdCat | 市場区分 Mkt | 件数 |")
        print("|---|---|---|")
        for (p, m), n in sorted(c.items()):
            print("| %s | %s | %d |" % (p, m, n))
        print("- 上場銘柄一覧の合計: %d" % len(master))
        dom = [r for r in master if r.get("ProdCat") == "011"]
        print("- 内国株券(011)のうち、コードの5桁目が 0 でないもの: %d" % sum(1 for r in dom if str(r.get("Code", ""))[-1:] != "0"))
        bp = find("bars", d)
        if bp:
            bars = load(bp)
            codes = {r.get("Code") for r in master}
            pc = {r.get("Code"): r.get("ProdCat", "") for r in master}
            print("- 株価四本値の行数: %d、うち上場銘柄一覧にないもの: %d" % (len(bars), sum(1 for r in bars if r.get("Code") not in codes)))
            bc = collections.Counter(pc.get(r.get("Code"), "一覧になし") for r in bars)
            print("- 株価四本値の行数(商品区分ごと): " + "、".join("%s=%d" % kv for kv in sorted(bc.items())))
        else:
            print("- 株価四本値のファイルがない")

    print("## 取得期間全体(上場銘柄一覧のすべての日付)")
    seen = collections.defaultdict(set)
    files = sorted(glob.glob(os.path.join(DATA, "master", "*", "*.json.gz")))
    for p in files:
        for r in load(p):
            seen[r.get("ProdCat", "")].add(r.get("Code"))
    print("- 日付の数: %d" % len(files))
    for k in sorted(seen):
        print("- ProdCat %s: %d 銘柄(重複なし)" % (k, len(seen[k])))


if __name__ == "__main__":
    main()
