"""Synthetic data generator.

Produces the ten source tables as a clean, internally consistent "truth" dataset. Nothing here is IRCTC data.
All rows carry data_origin = 'SYNTHETIC'.

Design (see docs/data_sources.md):
  * The network (stations, routes, trains, stops) is generated first.
  * Train RUNS are sampled: about one run per train per month (RUNS_PER_TRAIN_MONTH), because ~200k bookings
    cannot fill a full daily schedule at realistic seat counts (decision D-01).
  * Capacity is modelled separately from bookings (coaches x real seats per coach).
  * Demand is generated relative to capacity; each train-class run is then simulated as a time-ordered booking
    queue (Confirmed -> RAC -> Waitlisted), with cancellations promoting the queue. Occupancy is therefore an
    outcome of the capacity model, not forced to match anything.
"""
import heapq
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

import config as cfg

EPOCH = date(1970, 1, 1)

# city, synthetic code, state, region, lat, lon, hub weight   (place names are geographic labels only)
CITIES = [
    ("Delhi", "DEL", "Delhi", "North", 28.61, 77.21, 10), ("Jaipur", "JAI", "Rajasthan", "North", 26.91, 75.79, 4),
    ("Lucknow", "LUC", "Uttar Pradesh", "North", 26.85, 80.95, 4), ("Chandigarh", "CHA", "Chandigarh", "North", 30.73, 76.78, 2),
    ("Amritsar", "AMR", "Punjab", "North", 31.63, 74.87, 2), ("Dehradun", "DEH", "Uttarakhand", "North", 30.32, 78.03, 2),
    ("Varanasi", "VAR", "Uttar Pradesh", "North", 25.32, 82.97, 3), ("Jodhpur", "JOD", "Rajasthan", "North", 26.24, 73.02, 2),
    ("Mumbai", "MUM", "Maharashtra", "West", 19.08, 72.88, 10), ("Pune", "PUN", "Maharashtra", "West", 18.52, 73.86, 5),
    ("Ahmedabad", "AHM", "Gujarat", "West", 23.02, 72.57, 5), ("Surat", "SUR", "Gujarat", "West", 21.17, 72.83, 3),
    ("Madgaon", "MAD", "Goa", "West", 15.27, 73.96, 2), ("Nagpur", "NAG", "Maharashtra", "Central", 21.15, 79.09, 3),
    ("Bhopal", "BHO", "Madhya Pradesh", "Central", 23.26, 77.41, 3), ("Indore", "IND", "Madhya Pradesh", "Central", 22.72, 75.86, 3),
    ("Raipur", "RAI", "Chhattisgarh", "Central", 21.25, 81.63, 2), ("Chennai", "CHE", "Tamil Nadu", "South", 13.08, 80.27, 8),
    ("Bengaluru", "BEN", "Karnataka", "South", 12.97, 77.59, 8), ("Hyderabad", "HYD", "Telangana", "South", 17.39, 78.49, 7),
    ("Kochi", "KOC", "Kerala", "South", 9.93, 76.27, 3), ("Thiruvananthapuram", "THI", "Kerala", "South", 8.52, 76.94, 2),
    ("Coimbatore", "COI", "Tamil Nadu", "South", 11.02, 76.96, 2), ("Visakhapatnam", "VIS", "Andhra Pradesh", "South", 17.69, 83.22, 3),
    ("Vijayawada", "VIJ", "Andhra Pradesh", "South", 16.51, 80.65, 3), ("Madurai", "MAU", "Tamil Nadu", "South", 9.93, 78.12, 2),
    ("Kolkata", "KOL", "West Bengal", "East", 22.57, 88.36, 8), ("Bhubaneswar", "BHU", "Odisha", "East", 20.30, 85.82, 3),
    ("Patna", "PAT", "Bihar", "East", 25.59, 85.14, 4), ("Ranchi", "RAN", "Jharkhand", "East", 23.34, 85.31, 2),
    ("Guwahati", "GUW", "Assam", "Northeast", 26.14, 91.74, 3), ("Dibrugarh", "DIB", "Assam", "Northeast", 27.48, 94.91, 2),
]
HOUR_WEIGHTS = np.array([1, 1, 1, 1, 1, 2, 3, 5, 7, 7, 6, 5, 5, 5, 5, 5, 6, 6, 7, 8, 8, 6, 3, 2], float)
HOUR_WEIGHTS /= HOUR_WEIGHTS.sum()


def _epoch_days(d):
    return (d - EPOCH).days


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ============================================================ stations, routes, trains, stops
def build_stations():
    rows = []
    for i, (city, code, state, region, _, _, _) in enumerate(CITIES, start=1):
        rows.append(dict(station_id=i, station_code=code, station_name=f"{city} Central", city=city,
                         state=state, region=region, data_origin="SYNTHETIC"))
    return pd.DataFrame(rows)


def build_network(rng):
    n = len(CITIES)
    w = np.array([c[6] for c in CITIES], float)
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                D[i, j] = round(_haversine(CITIES[i][4], CITIES[i][5], CITIES[j][4], CITIES[j][5]) * cfg.RAIL_CIRCUITY)
    ok = (D >= cfg.MIN_ROUTE_KM) & (D <= cfg.MAX_ROUTE_KM)

    # corridors (undirected pairs) covering every station
    corridors, covered = [], set()
    for i in rng.permutation(n):
        i = int(i)
        if i in covered:
            continue
        unc = [j for j in range(n) if j != i and j not in covered and ok[i, j]]
        pool = unc if unc else [j for j in range(n) if j != i and ok[i, j]]
        p = w[pool] / w[pool].sum()
        j = int(rng.choice(pool, p=p))
        corridors.append((min(i, j), max(i, j)))
        covered |= {i, j}
    corridors = sorted(set(corridors))
    while len(corridors) < 20:
        cand = [(i, j) for i in range(n) for j in range(i + 1, n) if ok[i, j] and (i, j) not in corridors]
        pw = np.array([w[i] * w[j] for i, j in cand], float)
        corridors.append(cand[int(rng.choice(len(cand), p=pw / pw.sum()))])
    corridors = sorted(corridors)
    k_double = max(0, cfg.N_TARGET_TRAIN_PAIRS - len(corridors))
    by_weight = sorted(corridors, key=lambda c: -w[c[0]] * w[c[1]])
    doubled = set(by_weight[:k_double])

    # routes: both directions of every corridor
    routes, route_id = [], {}
    for (i, j) in corridors:
        for a, b in ((i, j), (j, i)):
            rid = len(routes) + 1
            route_id[(a, b)] = rid
            routes.append(dict(route_id=rid, origin_station_id=a + 1, destination_station_id=b + 1,
                               route_name=f"{CITIES[a][0]} to {CITIES[b][0]}", distance_km=float(D[a, b]),
                               data_origin="SYNTHETIC"))

    trains, stops, meta = [], [], {}
    seq_no = 1000
    type_p = ["Premium", "Superfast", "Express"]
    for (i, j) in corridors:
        n_pairs = 2 if (i, j) in doubled else 1
        for k in range(n_pairs):
            ttype = str(rng.choice(type_p, p=[0.15, 0.40, 0.45]))
            for a, b in ((i, j), (j, i)):
                seq_no += 1
                tid = len(trains) + 1
                rid = route_id[(a, b)]
                dist = float(D[a, b])
                nm = f"{CITIES[a][0]}\u2013{CITIES[b][0]} {ttype}" + (f" {k + 1}" if n_pairs > 1 else "")
                nd = int(rng.choice([1, 2, 3, 5, 7], p=[0.20, 0.20, 0.25, 0.15, 0.20]))
                days = set(int(x) for x in rng.choice(7, size=nd, replace=False))
                run_days = "".join("Y" if d in days else "N" for d in range(7))
                trains.append(dict(train_id=tid, train_number=f"S{seq_no}", train_name=nm, train_type=ttype,
                                   route_id=rid, run_days=run_days, data_origin="SYNTHETIC"))
                # intermediate stops
                cands = [(D[a, s], s) for s in range(n) if s not in (a, b)
                         and D[a, s] + D[s, b] <= 1.12 * dist and 0.12 * dist <= D[a, s] <= 0.88 * dist]
                kmax = 2 if ttype == "Premium" else 4
                kk = min(len(cands), int(rng.integers(0, kmax + 1)))
                chosen = sorted([cands[int(x)] for x in rng.choice(len(cands), size=kk, replace=False)]) if kk else []
                seq_stations = [(0.0, a)] + chosen + [(dist, b)]
                # make distances strictly increasing
                fixed, last = [], -1
                for dd, s in seq_stations:
                    dd = max(dd, last + 1)
                    fixed.append((dd, s))
                    last = dd
                speed = {"Premium": 68, "Superfast": 58, "Express": 50}[ttype]
                dep0 = int(rng.integers(5 * 4, 23 * 4)) * 15        # minutes after midnight, 15-min grid
                t = dep0
                halts = 0
                for sq, (dd, s) in enumerate(fixed, start=1):
                    is_first, is_last = sq == 1, sq == len(fixed)
                    arr_min = dep0 + dd / speed * 60 + halts
                    halt = 0 if (is_first or is_last) else int(rng.integers(3, 9))
                    dep_min = arr_min + halt
                    stops.append(dict(
                        train_id=tid, stop_sequence=sq, station_id=s + 1,
                        arrival_time=None if is_first else _hhmm(arr_min),
                        departure_time=None if is_last else _hhmm(dep0 if is_first else dep_min),
                        day_offset=int((dep0 if is_first else arr_min) // 1440),
                        distance_from_origin_km=float(dd), data_origin="SYNTHETIC"))
                    halts += halt
                meta[tid] = dict(dist=dist, dep_sec=dep0 * 60, ttype=ttype, origin=a, dest=b, route_id=rid,
                                 corridor_w=math.sqrt(w[a] * w[b]))
    return pd.DataFrame(routes), pd.DataFrame(trains), pd.DataFrame(stops), meta


def _hhmm(minutes):
    m = int(round(minutes)) % 1440
    return f"{m // 60:02d}:{m % 60:02d}:00"


# ============================================================ calendar
def build_calendar():
    days = pd.date_range(cfg.CALENDAR_START, cfg.CALENDAR_END, freq="D")
    df = pd.DataFrame({"calendar_date": days})
    d = df["calendar_date"].dt
    df["year"] = d.year.astype("int16")
    df["quarter"] = d.quarter.astype("int16")
    df["month_number"] = d.month.astype("int16")
    df["month_name"] = d.month_name()
    df["week_of_year"] = d.isocalendar().week.astype("int16")
    df["day_of_month"] = d.day.astype("int16")
    df["day_of_week_number"] = (d.dayofweek + 1).astype("int16")
    df["day_name"] = d.day_name()
    df["is_weekend"] = d.dayofweek >= 5
    df["season"] = df["month_number"].map(cfg.SEASON_BY_MONTH)
    df["fiscal_year"] = np.where(df["month_number"] >= 4, df["year"] + 1, df["year"]).astype("int16")
    hol = [cfg.FIXED_HOLIDAYS.get((m, dd)) for m, dd in zip(df["month_number"], df["day_of_month"])]
    df["holiday_name"] = hol
    df["is_holiday"] = df["holiday_name"].notna()
    df["peak_period_name"] = None
    for name, s, e in cfg.PEAK_WINDOWS:
        m = (df["calendar_date"] >= pd.Timestamp(s)) & (df["calendar_date"] <= pd.Timestamp(e))
        df.loc[m, "peak_period_name"] = name
    df["is_peak_travel_period"] = df["peak_period_name"].notna()
    df["calendar_date"] = df["calendar_date"].dt.date
    df["data_origin"] = "SYNTHETIC"
    return df[["calendar_date", "year", "quarter", "month_number", "month_name", "week_of_year", "day_of_month",
               "day_of_week_number", "day_name", "is_weekend", "season", "fiscal_year", "is_holiday", "holiday_name",
               "is_peak_travel_period", "peak_period_name", "data_origin"]]


# ============================================================ runs and capacity
def _class_set(ttype, dist, rng):
    if ttype == "Premium":
        return ["1A", "2A", "3A"] if dist > 700 else ["CC", "2A"]
    if dist > 700:
        return ["2A", "3A", "SL"] if rng.random() < 0.5 else ["3A", "SL", "2S"]
    return ["CC", "2S", "SL"] if rng.random() < 0.5 else ["CC", "2S"]


def build_runs_and_capacity(rng, trains, meta, cal):
    cal_idx = cal.set_index("calendar_date")
    months = pd.period_range(cfg.JOURNEY_START, cfg.JOURNEY_END, freq="M")
    pop = {t: float(rng.lognormal(0, 0.25)) for t in trains["train_id"]}
    mean_w = np.mean([m["corridor_w"] for m in meta.values()])
    static = {}
    for tr in trains.itertuples(index=False):
        m = meta[tr.train_id]
        classes = _class_set(tr.train_type, m["dist"], rng)
        static[tr.train_id] = dict(
            classes=classes,
            base={c: int(rng.integers(cfg.COACH_RANGE[c][0], cfg.COACH_RANGE[c][1] + 1)) for c in classes},
            allowed={i for i, ch in enumerate(tr.run_days) if ch == "Y"},
            corridor_f=float(np.clip((m["corridor_w"] / mean_w) ** 0.8, 0.7, 1.4)))
    runs, cap = [], []
    train_ids = list(trains["train_id"])
    for per in months:
        first, last = per.start_time.date(), per.end_time.date()
        month_dates = [first + timedelta(days=k) for k in range((last - first).days + 1)]
        month_dates = [d for d in month_dates if cfg.JOURNEY_START <= d <= cfg.JOURNEY_END]
        # exactly RUNS_PER_MONTH runs per month, spread across trains (a train with no scheduled day is skipped)
        picked = [int(x) for x in rng.permutation(train_ids)]
        n_done = 0
        for tid in picked:
            if n_done >= cfg.RUNS_PER_MONTH:
                break
            st = static[tid]
            dates = [d for d in month_dates if d.weekday() in st["allowed"]]
            if not dates:
                continue
            d = dates[int(rng.integers(0, len(dates)))]
            n_done += 1
            crow = cal_idx.loc[d]
            mi = (d.year - cfg.JOURNEY_START.year) * 12 + d.month - cfg.JOURNEY_START.month
            mult = (pop[tid] * st["corridor_f"] * cfg.WEEKDAY_DEMAND[d.weekday()]
                    * cfg.SEASON_DEMAND[crow["season"]] * (cfg.PEAK_PERIOD_MULT if crow["is_peak_travel_period"] else 1.0)
                    * (cfg.HOLIDAY_MULT if crow["is_holiday"] else 1.0) * (1 + cfg.MONTHLY_TREND * mi))
            runs.append(dict(train_id=tid, run_date=d, demand_mult=mult))
            for c in st["classes"]:
                coaches = st["base"][c] + int(rng.choice([-1, 0, 1], p=[0.10, 0.80, 0.10]))
                coaches = max(int(np.clip(coaches, cfg.COACH_RANGE[c][0], cfg.COACH_RANGE[c][1] + 1)), 1)
                total = coaches * cfg.CLASS_SEATS[c]
                rac_b = int(round(cfg.RAC_BERTH_SHARE * total)) if c in cfg.RAC_CLASSES else 0
                ratio = (cfg.DEMAND_MEDIAN * mult * cfg.CLASS_DEMAND[c] * float(rng.lognormal(0, cfg.DEMAND_SIGMA)))
                cap.append(dict(train_id=tid, journey_date=d, travel_class=c, coaches_attached=coaches,
                                seats_per_coach=cfg.CLASS_SEATS[c], total_seats=total, rac_berths=rac_b,
                                wl_limit=int(round(cfg.WL_LIMIT_SHARE * total)), data_origin="SYNTHETIC", _ratio=ratio))
    runs = pd.DataFrame(runs)
    cap = pd.DataFrame(cap)
    cap.insert(0, "capacity_id", np.arange(1, len(cap) + 1, dtype="int64"))
    return runs, cap


# ============================================================ booking simulation
def _adult_fare(cls, dist, ttype):
    return cfg.FARE_RESERVATION[cls] + cfg.FARE_RATE_PER_KM[cls] * dist * cfg.FARE_TYPE_MULT[ttype]


def simulate_bookings(rng, cap, meta, trains):
    ttype_of = dict(zip(trains["train_id"], trains["train_type"]))
    P_book, P_seq, P_age, P_fare, P_init, P_final, P_canc = [], [], [], [], [], [], []
    B_train, B_date, B_class, B_ts, B_n, B_fare, B_first = [], [], [], [], [], [], []
    E_book, E_ts, E_type, E_status, E_n, E_orig, E_charge, E_refund = [], [], [], [], [], [], [], []
    AGE_FIX = {0: "Child", 1: "Adult", 2: "Senior"}

    for cr in cap.itertuples(index=False):
        m = meta[cr.train_id]
        C, rac_b, wl_lim = cr.total_seats, cr.rac_berths, cr.wl_limit
        conf_lim, rac_lim = C - rac_b, 2 * rac_b
        rac_on = rac_b > 0
        cls = cr.travel_class
        adult_fare = _adult_fare(cls, m["dist"], ttype_of[cr.train_id])
        jmid = _epoch_days(cr.journey_date) * 86400
        dep_epoch = jmid + m["dep_sec"]
        chart = dep_epoch - cfg.CHART_PREP_HOURS * 3600

        req = cr[-1] * C                           # requested passengers = demand ratio (last column) x seats
        mm = int(req / 1.9) + 8
        sizes = rng.choice(cfg.PAX_VALUES, size=mm, p=cfg.PAX_PROBS)
        cum = np.cumsum(sizes)
        k = min(int(np.searchsorted(cum, req)) + 1, mm)
        sizes = sizes[:k]
        lb = rng.choice(len(cfg.LEAD_BUCKETS), size=k, p=cfg.LEAD_PROBS)
        lo = np.array([cfg.LEAD_BUCKETS[x][0] for x in lb])
        hi = np.array([cfg.LEAD_BUCKETS[x][1] for x in lb])
        lead = rng.integers(lo, hi + 1)
        tod = rng.choice(24, size=k, p=HOUR_WEIGHTS) * 3600 + rng.integers(0, 3600, size=k)
        ts = jmid - lead * 86400 + tod
        while True:                                # bookings must close before chart preparation
            late = ts > chart - 60
            if not late.any():
                break
            ts = np.where(late, ts - 86400, ts)
        u_cancel = rng.random(k)
        u_part = rng.random(k)
        u_time = rng.beta(1.6, 1.2, size=k)
        u_sel = rng.random((k, 6))
        age_draw = rng.choice(3, size=(k, 6), p=cfg.AGE_PROBS)
        lead_eff = (jmid - (ts - tod)) // 86400    # lead time in days after any shift

        conf_used = 0
        rac_q, wl_q = [], []
        heap = [(int(ts[j]), 0, j, "B", j) for j in range(k)]
        heapq.heapify(heap)
        seq = k
        bk_state = {}                              # j -> (first_pid, n, gid, partial?)

        def rebalance():
            nonlocal conf_used
            while conf_used < conf_lim and (rac_q or wl_q):
                if rac_q:
                    p = rac_q.pop(0)
                else:
                    p = wl_q.pop(0)
                P_final[p] = "Confirmed"
                conf_used += 1
            while rac_on and len(rac_q) < rac_lim and wl_q:
                p = wl_q.pop(0)
                P_final[p] = "RAC"
                rac_q.append(p)

        def cancel_event(g, t_evt, ctype, status):
            F = sum(P_fare[p] for p in g)
            gid = P_book[g[0]]
            if ctype == "System" or status == "Waitlisted":
                charge = min(F, cfg.WL_CLERKAGE * len(g))
            else:
                hrs = (dep_epoch - t_evt) / 3600.0
                flat = cfg.CANCEL_FLAT_FEE[cls] * len(g)
                pct = 0.0 if hrs >= 48 else (cfg.CANCEL_PCT_12_48H if hrs >= 12 else cfg.CANCEL_PCT_4_12H)
                charge = min(F, max(pct * F, flat))
            charge = round(charge, 2)
            E_book.append(gid); E_ts.append(int(t_evt)); E_type.append(ctype); E_status.append(status)
            E_n.append(len(g)); E_orig.append(round(F, 2)); E_charge.append(charge); E_refund.append(round(F - charge, 2))
            eid = len(E_book) - 1
            for p in g:
                P_canc[p] = eid

        while heap:
            t, kind, _, typ, j = heapq.heappop(heap)
            if typ == "B":
                n = int(sizes[j])
                free = (conf_lim - conf_used) + ((rac_lim - len(rac_q)) if rac_on else 0) + (wl_lim - len(wl_q))
                if n > free:
                    continue                       # booking refused (waiting list full) - not in the dataset
                gid = len(B_train)
                B_train.append(cr.train_id); B_date.append(cr.journey_date); B_class.append(cls)
                B_ts.append(int(t)); B_n.append(n); B_first.append(len(P_book))
                first = len(P_book)
                tot = 0.0
                any_wl = any_rac = False
                for s in range(n):
                    pid = len(P_book)
                    age = AGE_FIX[int(age_draw[j, s])]
                    if s == 0 and age == "Child":
                        age = "Adult"
                    fare = float(round(adult_fare * cfg.FARE_AGE_FACTOR[age]))
                    if conf_used < conf_lim:
                        st = "Confirmed"; conf_used += 1
                    elif rac_on and len(rac_q) < rac_lim:
                        st = "RAC"; rac_q.append(pid); any_rac = True
                    else:
                        st = "Waitlisted"; wl_q.append(pid); any_wl = True
                    P_book.append(gid); P_seq.append(s + 1); P_age.append(age); P_fare.append(fare)
                    P_init.append(st); P_final.append(st); P_canc.append(-1)
                    tot += fare
                B_fare.append(round(tot, 2))
                # cancellation plan
                le = float(lead_eff[j])
                p_c = (cfg.CANCEL_BASE + cfg.CANCEL_LEAD_SLOPE * min(le, 90.0) / 90.0) * cfg.CANCEL_CLASS_MULT[cls]
                if any_wl:
                    p_c *= cfg.CANCEL_WL_MULT
                elif any_rac:
                    p_c *= cfg.CANCEL_RAC_MULT
                window = (chart - 60) - t - 600
                if u_cancel[j] < p_c and window > 0:
                    t_c = int(t + 600 + u_time[j] * window)
                    partial = (n >= 2) and (u_part[j] < cfg.PARTIAL_CANCEL_PROB)
                    seq += 1
                    heapq.heappush(heap, (t_c, 1, seq, "C", j))
                    bk_state[j] = (first, n, gid, partial)
            else:                                   # cancellation event for booking j
                first, n, gid, partial = bk_state[j]
                active = [p for p in range(first, first + n) if P_final[p] != "Cancelled"]
                if not active:
                    continue
                if partial and len(active) >= 2:
                    kc = 1 + int(u_sel[j, 0] * (len(active) - 1))
                    order = np.argsort(u_sel[j, :len(active)])
                    chosen = [active[int(i)] for i in order[:kc]]
                    st0 = P_final[chosen[0]]
                    g = [p for p in chosen if P_final[p] == st0]
                    for p in g:
                        _release(p, P_final, rac_q, wl_q)
                        if P_final[p] == "Confirmed":
                            conf_used -= 1
                        P_final[p] = "Cancelled"
                    cancel_event(g, t, "Passenger", st0)
                    rebalance()
                else:
                    step = 0
                    for st in ("Waitlisted", "RAC", "Confirmed"):
                        g = [p for p in range(first, first + n) if P_final[p] == st]
                        if not g:
                            continue
                        for p in g:
                            _release(p, P_final, rac_q, wl_q)
                            if st == "Confirmed":
                                conf_used -= 1
                            P_final[p] = "Cancelled"
                        cancel_event(g, t + step, "Passenger", st)
                        step += 1
                        rebalance()
        # chart preparation: uncleared waiting list is refunded by the system (one event per booking)
        by_bk = {}
        for p in wl_q:
            by_bk.setdefault(P_book[p], []).append(p)
        for gid, g in sorted(by_bk.items()):
            cancel_event(g, chart, "System", "Waitlisted")

    return dict(P_book=P_book, P_seq=P_seq, P_age=P_age, P_fare=P_fare, P_init=P_init, P_final=P_final, P_canc=P_canc,
                B_train=B_train, B_date=B_date, B_class=B_class, B_ts=B_ts, B_n=B_n, B_fare=B_fare,
                E_book=E_book, E_ts=E_ts, E_type=E_type, E_status=E_status, E_n=E_n, E_orig=E_orig,
                E_charge=E_charge, E_refund=E_refund)


def _release(p, P_final, rac_q, wl_q):
    st = P_final[p]
    if st == "RAC":
        rac_q.remove(p)
    elif st == "Waitlisted":
        wl_q.remove(p)


# ============================================================ operations (delays, simulated)
def build_operations(rng, runs, trains, meta, stations, cal):
    cal_idx = cal.set_index("calendar_date")
    region = dict(zip(stations["station_id"], stations["region"]))
    ttype = dict(zip(trains["train_id"], trains["train_type"]))
    tf = {t: float(rng.lognormal(0, 0.35)) for t in trains["train_id"]}
    rows = []
    for r in runs.itertuples(index=False):
        m = meta[r.train_id]
        season = cal_idx.loc[r.run_date, "season"]
        sf = cfg.SEASON_DELAY_MULT[season]
        if season == "Winter" and ({region[m["origin"] + 1], region[m["dest"] + 1]} & {"North", "East"}):
            sf = 1.6
        df = float(np.clip(0.6 + m["dist"] / 2000.0, 0.6, 1.6))
        p_late = float(np.clip(cfg.LATE_BASE_PROB * tf[r.train_id] * sf * df * cfg.TYPE_DELAY_MULT[ttype[r.train_id]], 0.03, 0.9))
        if rng.random() < p_late:
            arr = int(min(round(rng.lognormal(math.log(cfg.LATE_MEDIAN_MIN), cfg.LATE_SIGMA)), 900))
            dep = int(round(arr * rng.uniform(0.15, 0.70)))
        else:
            arr = int(np.clip(round(rng.normal(-4, 6)), -30, 15))
            dep = int(np.clip(round(rng.normal(0, 4)), -10, 15))
        rows.append(dict(train_id=r.train_id, run_date=r.run_date, departure_delay_min=dep, arrival_delay_min=arr,
                         data_origin="SYNTHETIC"))
    ops = pd.DataFrame(rows)
    ops.insert(0, "operation_id", np.arange(1, len(ops) + 1, dtype="int64"))
    return ops


# ============================================================ assemble
def generate(seed=cfg.SEED, verbose=True):
    rng = np.random.default_rng(seed)
    stations = build_stations()
    routes, trains, stops, meta = build_network(rng)
    cal = build_calendar()
    runs, cap = build_runs_and_capacity(rng, trains, meta, cal)
    sim = simulate_bookings(rng, cap, meta, trains)
    ops = build_operations(rng, runs, trains, meta, stations, cal)
    cap = cap.drop(columns="_ratio")

    # ---- bookings
    bk = pd.DataFrame(dict(_gid=np.arange(len(sim["B_train"])), train_id=sim["B_train"], journey_date=sim["B_date"],
                           travel_class=sim["B_class"], _ts=sim["B_ts"], num_passengers=sim["B_n"],
                           total_fare=sim["B_fare"]))
    bk = bk.sort_values(["_ts", "_gid"], kind="mergesort").reset_index(drop=True)
    bk.insert(0, "booking_id", np.arange(1, len(bk) + 1, dtype="int64") + 1_000_000)
    gid2bid = dict(zip(bk["_gid"], bk["booking_id"]))
    st_of = dict(zip(stations["station_id"], stations["station_id"]))
    tr = trains.set_index("train_id")
    rt = routes.set_index("route_id")
    bk["route_id"] = bk["train_id"].map(tr["route_id"])
    bk["boarding_station_id"] = bk["route_id"].map(rt["origin_station_id"])
    bk["destination_station_id"] = bk["route_id"].map(rt["destination_station_id"])
    bk["booking_ts"] = pd.to_datetime(bk["_ts"], unit="s")
    bk["booking_reference"] = ["SB" + f"{(int(b) * 2654435761) % 10**9:09d}" for b in bk["booking_id"]]
    bk["data_origin"] = "SYNTHETIC"

    # ---- passengers
    ps = pd.DataFrame(dict(_gid=sim["P_book"], passenger_seq=sim["P_seq"], age_band=sim["P_age"],
                           fare_amount=sim["P_fare"], initial_status=sim["P_init"], final_status=sim["P_final"],
                           _eid=sim["P_canc"]))
    ps["booking_id"] = ps["_gid"].map(gid2bid)

    # ---- cancellation events
    ev = pd.DataFrame(dict(_gid=sim["E_book"], _ts=sim["E_ts"], cancellation_type=sim["E_type"],
                           status_at_cancellation=sim["E_status"], cancelled_passengers=sim["E_n"],
                           original_fare_amount=sim["E_orig"], cancellation_charge=sim["E_charge"],
                           refund_amount=sim["E_refund"]))
    ev["_eid"] = np.arange(len(ev))
    ev["booking_id"] = ev["_gid"].map(gid2bid)
    ev["cancellation_ts"] = pd.to_datetime(ev["_ts"], unit="s")
    ev = ev.sort_values(["_ts", "_eid"], kind="mergesort").reset_index(drop=True)
    ev.insert(0, "cancellation_id", np.arange(1, len(ev) + 1, dtype="int64"))
    eid2cid = dict(zip(ev["_eid"], ev["cancellation_id"]))
    ev["data_origin"] = "SYNTHETIC"

    ps["cancellation_id"] = ps["_eid"].map(eid2cid).astype("Int64")
    ps = ps.sort_values(["booking_id", "passenger_seq"]).reset_index(drop=True)
    ps.insert(0, "passenger_id", np.arange(1, len(ps) + 1, dtype="int64"))
    ps["data_origin"] = "SYNTHETIC"

    # ---- booking-level status roll-up (derived from passenger final statuses)
    grp = ps.groupby("booking_id")["final_status"]
    roll = grp.first().where(grp.nunique() == 1, "Mixed")
    bk["booking_status"] = bk["booking_id"].map(roll)

    bookings = bk[["booking_id", "booking_reference", "train_id", "journey_date", "route_id", "boarding_station_id",
                   "destination_station_id", "travel_class", "booking_ts", "num_passengers", "booking_status",
                   "total_fare", "data_origin"]]
    passengers = ps[["passenger_id", "booking_id", "passenger_seq", "age_band", "fare_amount", "initial_status",
                     "final_status", "cancellation_id", "data_origin"]]
    cancellations = ev[["cancellation_id", "booking_id", "cancellation_ts", "cancellation_type", "status_at_cancellation",
                        "cancelled_passengers", "original_fare_amount", "cancellation_charge", "refund_amount",
                        "data_origin"]]
    seat_capacity = cap[["capacity_id", "train_id", "journey_date", "travel_class", "coaches_attached", "seats_per_coach",
                         "total_seats", "rac_berths", "wl_limit", "data_origin"]]
    tables = dict(stations=stations, routes=routes, trains=trains, train_stops=stops, calendar=cal,
                  seat_capacity=seat_capacity, train_operations=ops, bookings=bookings,
                  booking_passengers=passengers, cancellations=cancellations)
    if verbose:
        print({k: len(v) for k, v in tables.items()})
    return tables


def write_tables(tables, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)


if __name__ == "__main__":
    t = generate()
    write_tables(t, cfg.INTERIM_DIR)
    print("written to", cfg.INTERIM_DIR)
