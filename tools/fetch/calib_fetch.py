#!/usr/bin/env python3
"""較正用の市場データを J-Quants API から取得する(較正計画 第1節、data_spec 第6節・第9節)。

GitHub Actions の中で、1つのデータの種類 × 1つの期間(ふつうは1年分)を取得し、
指定したフォルダに保存する。保存したフォルダは、ワークフローが Actions のキャッシュに入れる。

ログに出すのは、件数・ハッシュ値・リクエスト数・かかった時間だけ。データの中身は出さない(CHARTER 第8章)。

データの種類:
- calendar  : 取引カレンダー(期間を1回で取る)
- master    : 上場銘柄一覧(営業日ごと)
- bars      : 株価四本値(営業日ごと)
- valuation : バリュエーション指標(営業日ごと)
- fins      : 財務情報(開示日ごと。休業日の開示も拾うため、暦日すべて)
"""

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.jquants.com/v2"
# 較正計画 第1-2節の「取得する全期間」。この外の日付には触れない
RANGE_START = dt.date(2017, 2, 1)
RANGE_END = dt.date(2020, 6, 30)
SLEEP = 0.55  # Standard のレートリミット(120件/分)に余裕を持たせる
ENDPOINTS = {
    "master": "/equities/master",
    "bars": "/equities/bars/daily",
    "valuation": "/equities/valuation",
    "fins": "/fins/summary",
}
BUSINESS_DAY = {"1", "2"}  # 休日区分:1 営業日、2 東証半日立会日

stats = {"requests": 0, "retries_429": 0}


def get_all(path, params, key):
    rows, params = [], dict(params)
    while True:
        url = API + path + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"x-api-key": key})
        for attempt in range(10):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    body = json.load(r)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 9:
                    stats["retries_429"] += 1
                    wait = int(e.headers.get("Retry-After") or 30)
                    time.sleep(max(wait, 5))
                    continue
                print("http_error path=%s status=%d" % (path, e.code))
                sys.exit(1)
            except urllib.error.URLError:
                if attempt < 9:
                    time.sleep(10)
                    continue
                print("network_error path=%s" % path)
                sys.exit(1)
        stats["requests"] += 1
        rows.extend(body.get("data", []))
        time.sleep(SLEEP)
        nxt = body.get("pagination_key")
        if not nxt:
            return rows
        params["pagination_key"] = nxt


def save(path, rows):
    """行を決まった並びの JSON にして gzip で保存し、中身(展開後)の SHA-256 を返す。"""
    data = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with open(path, "wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as g:
            g.write(data)
    return hashlib.sha256(data).hexdigest()


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, choices=["calendar"] + list(ENDPOINTS))
    ap.add_argument("--start", required=True, type=dt.date.fromisoformat)
    ap.add_argument("--end", required=True, type=dt.date.fromisoformat)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    if not (RANGE_START <= a.start <= a.end <= RANGE_END):
        sys.exit("期間が較正計画の取得期間(%s〜%s)の外です" % (RANGE_START, RANGE_END))
    key = os.environ.get("JQUANTS_API_KEY", "")
    if not key:
        sys.exit("secret_present=false")
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()

    cal = get_all("/markets/calendar", {"from": a.start.isoformat(), "to": a.end.isoformat()}, key)
    if a.dataset == "calendar":
        h = save(os.path.join(a.out, "calendar.json.gz"), cal)
        print("MANIFEST calendar %s_%s rows=%d sha256=%s" % (a.start, a.end, len(cal), h))
        days, total_rows = [], len(cal)
    else:
        if a.dataset == "fins":
            days = list(daterange(a.start, a.end))
        else:
            days = sorted(dt.date.fromisoformat(r["Date"]) for r in cal if str(r.get("HolDiv")) in BUSINESS_DAY)
        total_rows = 0
        for d in days:
            rows = get_all(ENDPOINTS[a.dataset], {"date": d.isoformat()}, key)
            h = save(os.path.join(a.out, "%s.json.gz" % d.isoformat()), rows)
            total_rows += len(rows)
            print("MANIFEST %s %s rows=%d sha256=%s" % (a.dataset, d, len(rows), h))

    size = sum(os.path.getsize(os.path.join(a.out, f)) for f in os.listdir(a.out))
    print("SUMMARY dataset=%s start=%s end=%s dates=%d rows=%d requests=%d retries_429=%d bytes=%d seconds=%.0f" % (
        a.dataset, a.start, a.end, len(days), total_rows, stats["requests"], stats["retries_429"],
        size, time.time() - t0))


if __name__ == "__main__":
    main()
