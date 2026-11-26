#!/usr/bin/env python3
"""手計算の銘柄を選ぶ(較正計画 v0.5 第2-1節)。GitHub Actions で1回だけ実行する。

読むもの(calib-fetch が main で作ったキャッシュ):
  data/calendar/*/calendar.json.gz、data/master/*/<日付>.json.gz、
  data/bars/*/<日付>.json.gz、data/fins/*/<日付>.json.gz

出力するのは、条件ごとの候補の件数、選んだ銘柄コード、手計算の期間、判定に使った件数だけ。
価格・配当額などの中身は出さない(CHARTER 第8章)。銘柄コードと期間は、計画が実行記録に残すと定めている。

計画の文章を、次のように具体化している(PR で確認を受ける):
- 配当の権利落ち日(data_spec 第3節):財務情報の配当実績(Div1Q・Div2Q・Div3Q・DivFY)が正の値の
  レコードから、基準日を四半期末(CurFYSt の月から数えて 3・6・9 か月目の月末、期末は CurFYEn)とし、
  基準日が休業日なら直前の営業日に寄せ、その1営業日前を権利落ち日とする。
- 分割またぎ:配当の基準日より後、その配当実績が最初に開示された日(DiscDate)以前に、ExRT=1 の日がある。
- 企業行動の日:ExRT が 1・2・3 のどれか、または AdjFactor が 1 でない日。
- 無約定日:O・H・L・C・Vo・Va がそろって空の日。市場全体が止まった日は、その日の行の半分より多くが
  そろって空の日とし、数えない。
- 上場廃止:取得期間全体で、株価四本値が返る最後の営業日が共通の期間の中にある(取得期間の最終日を除く)。
- 対象銘柄(第3-1節、D-0030):照合期間の初日(休業日なら次の営業日)の上場銘柄一覧で、
  ProdCat=011、コードの5桁目が 0、Mkt が 0105 でない。
"""

import bisect
import calendar as calmod
import collections
import datetime as dt
import glob
import gzip
import json
import os
import random
import sys

DATA = sys.argv[1] if len(sys.argv) > 1 else "data"
SEED = 20261124
FETCH_START, FETCH_END = dt.date(2017, 2, 1), dt.date(2020, 6, 30)
REPRO_START, REPRO_END = dt.date(2018, 7, 1), dt.date(2020, 6, 30)
COMMON_START, COMMON_END = dt.date(2019, 3, 1), dt.date(2019, 8, 31)
BUSINESS_DAY = {"1", "2"}
PRICE_FIELDS = ["O", "H", "L", "C", "Vo", "Va"]
MARKET_STOP_SHARE = 0.5
MIN_TRADED_DAYS_DELIST = 20
DIV_FIELDS = [("Div1Q", 1), ("Div2Q", 2), ("Div3Q", 3), ("DivFY", 4)]


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def d(s):
    return dt.date.fromisoformat(str(s)[:10])


def num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def files(dataset):
    out = {}
    for p in glob.glob(os.path.join(DATA, dataset, "*", "*.json.gz")):
        name = os.path.basename(p)[:-len(".json.gz")]
        if name != "calendar":
            out[d(name)] = p
    return dict(sorted(out.items()))


def month_end(y, m):
    return dt.date(y, m, calmod.monthrange(y, m)[1])


def add_months(day, k):
    m0 = day.year * 12 + (day.month - 1) + k
    return m0 // 12, m0 % 12 + 1


class Calendar:
    def __init__(self):
        days = []
        for p in glob.glob(os.path.join(DATA, "calendar", "*", "calendar.json.gz")):
            days += [d(r["Date"]) for r in load(p) if str(r.get("HolDiv")) in BUSINESS_DAY]
        self.days = sorted(set(days))
        self.idx = {x: i for i, x in enumerate(self.days)}

    def on_or_before(self, x):
        i = bisect.bisect_right(self.days, x)
        return self.days[i - 1] if i else None

    def on_or_after(self, x):
        i = bisect.bisect_left(self.days, x)
        return self.days[i] if i < len(self.days) else None

    def prev(self, b):
        i = self.idx.get(b)
        return self.days[i - 1] if i else None

    def between(self, a, b):
        return [x for x in self.days if a <= x <= b]


def in_universe(rec):
    code = str(rec.get("Code", ""))
    return rec.get("ProdCat") == "011" and code[-1:] == "0" and rec.get("Mkt") != "0105"


def universe_on(master_files, cal, day, cache={}):
    b = cal.on_or_after(day)
    if b not in cache:
        p = master_files.get(b)
        cache[b] = {str(r.get("Code")) for r in load(p) if in_universe(r)} if p else set()
    return b, cache[b]


def window(event):
    """出来事の月の2か月前の月初から、3か月後の月末まで(取得期間で切り詰める)。"""
    y0, m0 = add_months(event, -2)
    y1, m1 = add_months(event, 3)
    return max(dt.date(y0, m0, 1), FETCH_START), min(month_end(y1, m1), FETCH_END)


def scan_bars(bar_files, common_days):
    """株価四本値を日付ごとに読み、銘柄ごとの集計だけを残す。"""
    last_seen = {}
    actions = collections.defaultdict(list)       # code -> [(date, ExRT, AdjFactor!=1)]
    common_present = collections.Counter()
    common_null = collections.defaultdict(list)   # code -> [date]
    common_traded = collections.Counter()
    null_share = {}
    common = set(common_days)
    for day, p in bar_files.items():
        rows = load(p)
        nulls = 0
        for r in rows:
            code = str(r.get("Code"))
            last_seen[code] = day
            exrt = str(r.get("ExRT") or "")
            adj = num(r.get("AdjFactor"))
            if exrt in ("1", "2", "3") or (adj is not None and adj != 1):
                actions[code].append((day, exrt, adj is not None and adj != 1))
            is_null = all(r.get(k) is None or r.get(k) == "" for k in PRICE_FIELDS)
            nulls += is_null
            if day in common:
                common_present[code] += 1
                if is_null:
                    common_null[code].append(day)
                else:
                    common_traded[code] += 1
        if day in common:
            null_share[day] = nulls / len(rows) if rows else 0.0
    return last_seen, actions, common_present, common_null, common_traded, null_share


def scan_dividends(fin_files, cal):
    """銘柄ごとの配当(基準日、権利落ち日、最初の開示日)を集める。"""
    first_disc = {}
    for day, p in fin_files.items():
        for r in load(p):
            code = str(r.get("Code"))
            try:
                fy_st, fy_en = d(r.get("CurFYSt")), d(r.get("CurFYEn"))
            except ValueError:
                continue
            disc = d(r.get("DiscDate") or day.isoformat())
            for field, q in DIV_FIELDS:
                v = num(r.get(field))
                if v is None or v <= 0:
                    continue
                base = fy_en if q == 4 else month_end(*add_months(fy_st, 3 * q - 1))
                key = (code, base)
                if key not in first_disc or disc < first_disc[key]:
                    first_disc[key] = disc
    divs = collections.defaultdict(list)
    for (code, base), disc in first_disc.items():
        b = cal.on_or_before(base)
        ex = cal.prev(b) if b else None
        if ex:
            divs[code].append({"base": base, "ex": ex, "disc": disc})
    return divs


def main():
    cal = Calendar()
    master_files, bar_files, fin_files = files("master"), files("bars"), files("fins")
    print("## 読んだファイル")
    print("- 営業日 %d、上場銘柄一覧 %d、株価四本値 %d、財務情報 %d" % (
        len(cal.days), len(master_files), len(bar_files), len(fin_files)))

    common_days = cal.between(COMMON_START, COMMON_END)
    last_day = max(bar_files)
    last_seen, actions, present, nulls, traded, null_share = scan_bars(bar_files, common_days)
    stop_days = {x for x, s in null_share.items() if s > MARKET_STOP_SHARE}
    divs = scan_dividends(fin_files, cal)
    print("- 共通の期間の営業日 %d、市場全体が止まったとみなした日 %d" % (len(common_days), len(stop_days)))

    def has_action(code, a, b):
        return any(a <= x[0] <= b for x in actions.get(code, []))

    def has_ex(code, a, b):
        return any(a <= v["ex"] <= b for v in divs.get(code, []))

    def null_days(code):
        return [x for x in nulls.get(code, []) if x not in stop_days]

    def delisted_in_common(code):
        ls = last_seen.get(code)
        return ls is not None and COMMON_START <= ls <= COMMON_END and ls < last_day

    def full_presence(code):
        return present.get(code, 0) == len(common_days)

    u_day, u_common = universe_on(master_files, cal, COMMON_START)
    print("- 共通の期間の初日 %s の対象銘柄 %d" % (u_day, len(u_common)))

    cand = {}
    cand[1] = sorted(c for c in u_common if has_ex(c, COMMON_START, COMMON_END)
                     and full_presence(c) and not has_action(c, COMMON_START, COMMON_END)
                     and not null_days(c) and not delisted_in_common(c))

    # 条件2:分割またぎ(再現の期間)
    split_events, straddle = {}, {}
    for code, acts in actions.items():
        for day, exrt, _ in sorted(acts):
            if exrt != "1" or not (REPRO_START <= day <= REPRO_END):
                continue
            if not any(v["base"] < day <= v["disc"] for v in divs.get(code, [])):
                continue
            ws, we = window(day)
            _, u = universe_on(master_files, cal, ws)
            if code in u:
                straddle[code] = (day, ws, we)
                break
    cand[2] = sorted(straddle)
    cond2_fallback = False
    if not cand[2]:
        cond2_fallback = True
        for code, acts in actions.items():
            for day, exrt, _ in sorted(acts):
                if exrt == "1" and COMMON_START <= day <= COMMON_END:
                    ws, we = window(day)
                    _, u = universe_on(master_files, cal, ws)
                    if code in u:
                        straddle[code] = (day, ws, we)
                        break
        cand[2] = sorted(straddle)

    cand[3] = sorted(c for c in u_common if null_days(c))
    cand[4] = sorted(c for c in u_common if delisted_in_common(c) and traded.get(c, 0) >= MIN_TRADED_DAYS_DELIST)
    cand[5] = sorted(c for c in u_common if full_presence(c) and not has_action(c, COMMON_START, COMMON_END)
                     and not null_days(c) and not has_ex(c, COMMON_START, COMMON_END)
                     and not delisted_in_common(c))

    rights = {}
    for code, acts in actions.items():
        for day, exrt, _ in sorted(acts):
            if exrt == "3" and REPRO_START <= day <= REPRO_END:
                ws, we = window(day)
                _, u = universe_on(master_files, cal, ws)
                if code in u:
                    rights[code] = (day, ws, we)
                    break
    cand[6] = sorted(rights)

    names = {1: "配当", 2: "分割(分割またぎ)", 3: "無約定日", 4: "上場廃止", 5: "通常", 6: "ライツイシュー"}
    print("## 条件ごとの候補の件数(選ぶ前)")
    for k in range(1, 7):
        extra = "(代わりの候補:共通の期間の ExRT=1)" if k == 2 and cond2_fallback else ""
        print("- 条件%d %s: %d%s" % (k, names[k], len(cand[k]), extra))

    rng = random.Random(SEED)
    chosen = set()
    print("## 選んだ銘柄(種 %d、条件1から6の順に choice を1回ずつ)" % SEED)
    print("| 条件 | 銘柄コード | 手計算の期間 | 候補(選んだ銘柄を除いた数) | 備考 |")
    print("|---|---|---|---|---|")
    for k in range(1, 7):
        pool = [c for c in cand[k] if c not in chosen]
        if not pool:
            print("| %d %s | 該当なし | - | 0 | |" % (k, names[k]))
            continue
        c = rng.choice(pool)
        chosen.add(c)
        note = ""
        if k in (2, 6):
            ev, ws, we = (straddle if k == 2 else rights)[c]
            period = "%s〜%s" % (ws, we)
            note = "出来事の日 %s" % ev
            if k == 2:
                note += "、分割またぎを確かめられなかった(代わりの候補)" if cond2_fallback else "、分割またぎ"
        else:
            period = "%s〜%s" % (COMMON_START, COMMON_END)
        print("| %d %s | %s | %s | %d | %s |" % (k, names[k], c, period, len(pool), note))


if __name__ == "__main__":
    main()
