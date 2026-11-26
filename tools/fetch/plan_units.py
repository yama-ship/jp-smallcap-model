#!/usr/bin/env python3
"""取得の単位(データの種類 × 年)を作り、GitHub Actions の matrix 用の JSON を出す。

キャッシュのキーには、その単位の期間をそのまま入れる。期間の一部だけを取った単位(試運転など)が、
全期間の単位と取り違えられないようにするため。
"""
import datetime as dt
import json
import sys

DATASETS = ["calendar", "master", "bars", "valuation", "fins"]
VERSION = "calib-v1"


def units(start, end):
    out = []
    for ds in DATASETS:
        for y in range(start.year, end.year + 1):
            s = max(start, dt.date(y, 1, 1))
            e = min(end, dt.date(y, 12, 31))
            out.append({"dataset": ds, "start": s.isoformat(), "end": e.isoformat(),
                        "key": "%s-%s-%s-%s" % (VERSION, ds, s.isoformat(), e.isoformat()),
                        "path": "data/%s/%s_%s" % (ds, s.isoformat(), e.isoformat())})
    return out


if __name__ == "__main__":
    s, e = dt.date.fromisoformat(sys.argv[1]), dt.date.fromisoformat(sys.argv[2])
    if s > e:
        sys.exit("start が end より後です")
    print(json.dumps({"include": units(s, e)}, separators=(",", ":")))
