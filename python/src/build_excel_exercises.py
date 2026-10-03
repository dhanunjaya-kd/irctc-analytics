"""Build excel/IRCTC_Data_Cleaning_Exercises.xlsx (deliverable 2: Excel data cleaning and validation exercises).

* Raw_* sheets: a defect-ENRICHED sample of the RAW extract (text as delivered, with every one of the 30 issue types present). Defect rates here are far higher than in
  the full raw data (about 1%) so that each exercise has examples; the sample is not a guide to real defect rates.
* Work_* sheets: worked-solution formulas that detect each issue (29 of 30 types; total_fare_invalid is left as a manual exercise).
* Answer_Key: expected counts from the cleaner's independent detection (clean_data.py) on exactly these rows, next to the Excel formula counts.
* Clean_*_Solution + Validation_Checks: the cleaned result and formula checks that a learner can point at their own cleaned sheets.
XLOOKUP is deliberately not used (not verifiable in the build environment); INDEX/MATCH and SUMPRODUCT lookups are used instead.
"""
import re

import numpy as np
import pandas as pd
from xlsxwriter.utility import xl_col_to_name as CL

import clean_data as cl
import config as cfg
import dq_catalog as dq
import xl_common as xc

OUT = cfg.ROOT / "excel" / "IRCTC_Data_Cleaning_Exercises.xlsx"
NUMERIC = {"Raw_Bookings": {0, 2, 4, 9, 11}, "Raw_Passengers": {0, 1, 2, 4, 7}, "Raw_Cancellations": {0, 1, 5, 6, 7, 8}, "Raw_Capacity": {0, 1, 4, 5, 6, 7, 8}, "Raw_Operations": {0, 1, 3, 4}}
PLAIN = re.compile(r"^-?\d+(\.\d+)?$")
HINTS = {
    "dup_booking_rows": ("Beginner", "COUNTIF (expanding range), Remove Duplicates", "Raw_Bookings"), "dup_passenger_rows": ("Beginner", "COUNTIF, Remove Duplicates", "Raw_Passengers"),
    "dup_cancellation_rows": ("Beginner", "COUNTIF, Remove Duplicates", "Raw_Cancellations"), "missing_total_fare": ("Beginner", "TRIM, IF, ISBLANK / LEN", "Raw_Bookings"),
    "total_fare_currency_format": ("Intermediate", "ISTEXT, SUBSTITUTE, VALUE, IFERROR", "Raw_Bookings"),
    "total_fare_invalid": ("Advanced (manual)", "SUMIFS over passengers, ISNUMBER, comparison; watch negative passenger fares and duplicate passenger rows", "Raw_Bookings + Raw_Passengers"),
    "negative_passenger_fare": ("Beginner", "ISNUMBER, IF", "Raw_Passengers"), "missing_route_id": ("Beginner", "TRIM, IF", "Raw_Bookings"),
    "num_passengers_invalid": ("Intermediate", "COUNTIFS on non-duplicate passenger rows, ISNUMBER", "Raw_Bookings"), "missing_age_band": ("Beginner", "TRIM, IF", "Raw_Passengers"),
    "station_code_format": ("Beginner", "TRIM, UPPER, EXACT, COUNTIF against Lookup_Stations", "Raw_Bookings"), "station_code_unknown": ("Beginner", "COUNTIF against Lookup_Stations", "Raw_Bookings"),
    "missing_booking_ts": ("Beginner", "TRIM, IF", "Raw_Bookings"), "journey_date_format": ("Intermediate", "MID, LEFT, RIGHT, VALUE, DATE", "Raw_Bookings"),
    "journey_date_impossible": ("Intermediate", "DATE round-trip: MONTH(DATE(y,m,d)) = m and DAY(DATE(y,m,d)) = d", "Raw_Bookings"),
    "booking_after_journey": ("Intermediate", "DATEVALUE, TIMEVALUE, INT", "Raw_Bookings"), "cancellation_before_booking": ("Advanced", "INDEX/MATCH to the booking timestamp, DATEVALUE, exclusion of already-rejected bookings", "Raw_Cancellations"),
    "booking_status_alias": ("Intermediate", "Lookup_Status via INDEX/SUMPRODUCT, EXACT", "Raw_Bookings"), "booking_status_invalid": ("Intermediate", "Lookup_Status lookup returning blank", "Raw_Bookings"),
    "passenger_status_alias": ("Intermediate", "Lookup_Status lookup on initial and final status, EXACT", "Raw_Passengers"),
    "passenger_final_status_invalid": ("Intermediate", "Lookup_Status lookup returning blank", "Raw_Passengers"), "passenger_initial_status_invalid": ("Intermediate", "Lookup_Status lookup; Cancelled is not a valid initial status", "Raw_Passengers"),
    "orphan_cancellation_rows": ("Beginner", "COUNTIF against Raw_Bookings", "Raw_Cancellations"), "orphan_passenger_rows": ("Beginner", "COUNTIF against Raw_Bookings", "Raw_Passengers"),
    "refund_exceeds_fare": ("Beginner", "IF, comparison", "Raw_Cancellations"), "capacity_total_mismatch": ("Intermediate", "INDEX/MATCH class standard, IF/AND", "Raw_Capacity"),
    "capacity_seats_per_coach_invalid": ("Intermediate", "INDEX/MATCH class standard, IF/AND", "Raw_Capacity"), "capacity_conflicting_duplicate": ("Advanced", "Composite key with &, COUNTIF, consistency test", "Raw_Capacity"),
    "missing_arrival_delay": ("Beginner", "TRIM, IF", "Raw_Operations"), "delay_out_of_range": ("Beginner", "ISNUMBER, OR", "Raw_Operations"),
}
MANUAL = {"total_fare_invalid"}


def select_sample(raw, log, seed=cfg.SEED + 7, per_code=6, n_random=500):
    rng = np.random.default_rng(seed)
    bk, ps, ev, cap, ops = raw["bookings"], raw["booking_passengers"], raw["cancellations"], raw["seat_capacity"], raw["train_operations"]
    bid_of_pid = ps.drop_duplicates("passenger_id").set_index("passenger_id")["booking_id"]
    bid_of_cid = ev.drop_duplicates("cancellation_id").set_index("cancellation_id")["booking_id"]
    bids, orphan_p, orphan_e, cap_keys, ops_ids = set(), set(), set(), set(), set()
    for code, meta in dq.CATALOG.items():
        keys = [str(k) for k in log.loc[log.issue_code == code, "record_key"]]
        if not keys:
            continue
        pick = [keys[i] for i in rng.choice(len(keys), size=min(per_code + (2 if meta["table"] in ("seat_capacity", "train_operations") else 0), len(keys)), replace=False)]
        t = meta["table"]
        if code == "orphan_passenger_rows":
            orphan_p |= set(pick)
        elif code == "orphan_cancellation_rows":
            orphan_e |= set(pick)
        elif t == "bookings":
            bids |= set(pick)
        elif t == "booking_passengers":
            bids |= {bid_of_pid[k] for k in pick}
        elif t == "cancellations":
            bids |= {bid_of_cid[k] for k in pick}
        elif t == "seat_capacity":
            cap_keys |= set(pick)
        else:
            ops_ids |= set(pick)
    allb = bk["booking_id"].unique()
    bids |= set(rng.choice(allb, size=n_random, replace=False))
    sb = bk[bk.booking_id.isin(bids)]
    sp = ps[ps.booking_id.isin(bids) | ps.passenger_id.isin(orphan_p)]
    se = ev[ev.booking_id.isin(bids) | ev.cancellation_id.isin(orphan_e)]
    crow = cap[cap.capacity_id.isin(cap_keys)]
    kc = ["train_id", "journey_date", "travel_class"]
    kset = set(map(tuple, crow[kc].values))
    extra = cap[[tuple(x) in kset for x in cap[kc].values]]
    rand_cap = cap.iloc[np.sort(rng.choice(len(cap), size=60, replace=False))]
    scap = pd.concat([extra, rand_cap]).drop_duplicates("capacity_id").sort_values("capacity_id", key=lambda s: s.astype(int))
    sops = pd.concat([ops[ops.operation_id.isin(ops_ids)], ops.iloc[np.sort(rng.choice(len(ops), size=40, replace=False))]]).drop_duplicates("operation_id").sort_values("operation_id", key=lambda s: s.astype(int))
    sub = dict(raw)
    sub.update(bookings=sb.reset_index(drop=True), booking_passengers=sp.reset_index(drop=True), cancellations=se.reset_index(drop=True),
               seat_capacity=scap.reset_index(drop=True), train_operations=sops.reset_index(drop=True))
    return sub


def load():
    raw = cl.read_raw()
    log = pd.read_csv(cfg.DQ_DIR / "injection_log.csv")
    sub = select_sample(raw, log)
    cleaned, res = cl.clean(raw=sub)
    ids = dict(bookings=set(sub["bookings"].booking_id.astype(int)), booking_passengers=set(sub["booking_passengers"].passenger_id.astype(int)),
               cancellations=set(sub["cancellations"].cancellation_id.astype(int)), seat_capacity=set(sub["seat_capacity"].capacity_id.astype(int)),
               train_operations=set(sub["train_operations"].operation_id.astype(int)))
    injected = {c: int(log[(log.issue_code == c) & log.record_key.isin(ids[dq.CATALOG[c]["table"]])].shape[0]) for c in dq.ORDER}
    return sub, cleaned, res, injected


def status_lookup(x, nlk):
    A, B = f"Lookup_Status!$A$2:$A${nlk}", f"Lookup_Status!$B$2:$B${nlk}"
    return f'IF(SUMPRODUCT(--({A}=LOWER(TRIM({x}))))=0,"",INDEX({B},SUMPRODUCT(({A}=LOWER(TRIM({x})))*(ROW({A})-1))))'


def build(b: xc.Book):
    sub, cleaned, res, injected = load()
    wb = b.wb
    NBK, NPS, NEV, NCAP, NOPS = (len(sub[k]) + 1 for k in ("bookings", "booking_passengers", "cancellations", "seat_capacity", "train_operations"))
    stations = sub["stations"]; NST = len(stations) + 1
    lk = sorted(dq.STATUS_LOOKUP.items()); NLK = len(lk) + 1
    order = ["README", "Exercises", "Answer_Key", "Validation_Checks", "Lookup_Stations", "Lookup_Status", "Lookup_Class", "Raw_Bookings", "Raw_Passengers", "Raw_Cancellations",
             "Raw_Capacity", "Raw_Operations", "Work_Bookings", "Work_Passengers", "Work_Cancellations", "Work_Capacity", "Work_Operations", "Clean_Bookings_Solution", "Clean_Passengers_Solution"]
    W = {n: wb.add_worksheet(n) for n in order}
    for n in order:
        W[n].set_tab_color({"R": "#7F7F7F", "W": "#2E75B6", "C": "#548235", "L": "#BF8F00"}.get(n[0], "#1F3864") if n.startswith(("Raw", "Work", "Clean", "Lookup")) else "#1F3864")
    calc = b.f(bg_color="#EAF1FB"); txt = b.f(); hdr = b.hdr

    # ---- lookups
    ws = W["Lookup_Stations"]; ws.write(0, 0, "station_code", hdr); ws.write(0, 1, "station_id", hdr)
    for i, r in enumerate(stations.itertuples()):
        ws.write_string(i + 1, 0, r.station_code); ws.write_number(i + 1, 1, int(r.station_id))
    ws = W["Lookup_Status"]; ws.write(0, 0, "variant (trimmed, lower case)", hdr); ws.write(0, 1, "canonical status", hdr)
    for i, (k, v) in enumerate(lk):
        ws.write_string(i + 1, 0, k); ws.write_string(i + 1, 1, v)
    ws.set_column(0, 1, 30)
    ws = W["Lookup_Class"]; ws.write(0, 0, "travel_class", hdr); ws.write(0, 1, "standard seats per coach", hdr)
    for i, (k, v) in enumerate(cfg.CLASS_SEATS.items()):
        ws.write_string(i + 1, 0, k); ws.write_number(i + 1, 1, v)
    ws.set_column(0, 1, 26)
    for _n in ("Lookup_Stations", "Lookup_Status", "Lookup_Class"):
        xc.side_label(b, W[_n], 0, 3, "SYNTHETIC reference data.")

    # ---- raw sheets (text as delivered; plain numbers become numbers, as an Excel CSV import would do)
    def raw_sheet(name, df):
        ws = W[name]
        for c, h in enumerate(df.columns):
            ws.write(0, c, h, hdr)
        for r, row in enumerate(df.itertuples(index=False), start=1):
            for c, v in enumerate(row):
                if v == "":
                    continue
                if c in NUMERIC[name] and PLAIN.match(v):
                    ws.write_number(r, c, float(v))
                else:
                    ws.write_string(r, c, v)
        ws.freeze_panes(1, 1); ws.set_column(0, len(df.columns), 17); ws.autofilter(0, 0, len(df), len(df.columns) - 1)
    raw_sheet("Raw_Bookings", sub["bookings"]); raw_sheet("Raw_Passengers", sub["booking_passengers"]); raw_sheet("Raw_Cancellations", sub["cancellations"])
    raw_sheet("Raw_Capacity", sub["seat_capacity"]); raw_sheet("Raw_Operations", sub["train_operations"])

    # ---- worked-solution formulas
    S = lambda x: status_lookup(x, NLK)
    specs = {
        "Work_Bookings": ("Raw_Bookings", NBK, [
            ("id", "=Raw_Bookings!A{e}"), ("dup", "=IF(COUNTIF(Raw_Bookings!$A$2:A{e},Raw_Bookings!A{e})>1,1,0)"), ("jd_text", '=Raw_Bookings!D{e}&""'),
            ("pat", '=IF(AND(LEN([jd_text])=10,MID([jd_text],5,1)="-",MID([jd_text],8,1)="-"),"ISO",IF(AND(LEN([jd_text])=10,MID([jd_text],3,1)="-",MID([jd_text],6,1)="-"),"DMY","OTHER"))'),
            ("y", '=IF([pat]="ISO",VALUE(LEFT([jd_text],4)),IF([pat]="DMY",VALUE(RIGHT([jd_text],4)),0))'), ("m", '=IF([pat]="ISO",VALUE(MID([jd_text],6,2)),IF([pat]="DMY",VALUE(MID([jd_text],4,2)),0))'),
            ("d", '=IF([pat]="ISO",VALUE(RIGHT([jd_text],2)),IF([pat]="DMY",VALUE(LEFT([jd_text],2)),0))'),
            ("valid", '=IF(AND([pat]<>"OTHER",[m]>=1,[m]<=12,[d]>=1,[d]<=31),IF(AND(MONTH(DATE([y],[m],[d]))=[m],DAY(DATE([y],[m],[d]))=[d]),1,0),0)'),
            ("jd_clean", '=IF([valid]=1,DATE([y],[m],[d]),"")'), ("f_date_format", '=IF(AND([pat]="DMY",[valid]=1),1,0)'), ("f_date_impossible", "=IF([valid]=0,1,0)"),
            ("ts_missing", '=IF(TRIM(Raw_Bookings!I{e}&"")="",1,0)'), ("ts_value", '=IF([ts_missing]=1,"",DATEVALUE(LEFT(Raw_Bookings!I{e},10))+TIMEVALUE(MID(Raw_Bookings!I{e},12,8)))'),
            ("f_after", "=IF(AND([ts_missing]=0,[valid]=1),IF(INT([ts_value])>[jd_clean],1,0),0)"),
            ("board_norm", "=UPPER(TRIM(Raw_Bookings!F{e}))"), ("dest_norm", "=UPPER(TRIM(Raw_Bookings!G{e}))"),
            ("board_known", "=IF(COUNTIF(Lookup_Stations!$A$2:$A$@NST,[board_norm])>0,1,0)"), ("dest_known", "=IF(COUNTIF(Lookup_Stations!$A$2:$A$@NST,[dest_norm])>0,1,0)"),
            ("f_station_format", "=IF(OR(AND([board_known]=1,NOT(EXACT(Raw_Bookings!F{e},[board_norm]))),AND([dest_known]=1,NOT(EXACT(Raw_Bookings!G{e},[dest_norm])))),1,0)"),
            ("f_station_unknown", "=IF(OR([board_known]=0,[dest_known]=0),1,0)"), ("f_route_missing", '=IF(TRIM(Raw_Bookings!E{e}&"")="",1,0)'),
            ("status_norm", "=" + S("Raw_Bookings!K{e}")), ("f_status_alias", '=IF(AND([status_norm]<>"",NOT(EXACT(Raw_Bookings!K{e},[status_norm]))),1,0)'),
            ("f_status_invalid", '=IF([status_norm]="",1,0)'), ("f_total_missing", '=IF(TRIM(Raw_Bookings!L{e}&"")="",1,0)'),
            ("total_is_text", "=IF(AND(ISTEXT(Raw_Bookings!L{e}),[f_total_missing]=0),1,0)"),
            ("total_parsed", '=IF([total_is_text]=1,IFERROR(VALUE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(UPPER(Raw_Bookings!L{e}),"RS.",""),"\u20b9",""),",","")," ",""),"INR","")),""),"")'),
            ("f_total_currency", "=IF(AND([total_is_text]=1,ISNUMBER([total_parsed])),1,0)"),
            ("f_numpax_invalid", "=IF([dup]=1,0,IF(NOT(ISNUMBER(Raw_Bookings!J{e})),1,IF(Raw_Bookings!J{e}<>COUNTIFS(@WP_bid,Raw_Bookings!A{e},@WP_dup,0),1,0)))")]),
        "Work_Passengers": ("Raw_Passengers", NPS, [
            ("id", "=Raw_Passengers!A{e}"), ("bid", "=Raw_Passengers!B{e}"), ("dup", "=IF(COUNTIF(Raw_Passengers!$A$2:A{e},Raw_Passengers!A{e})>1,1,0)"),
            ("orphan", "=IF(COUNTIF(Raw_Bookings!$A$2:$A$@NBK,Raw_Passengers!B{e})=0,1,0)"),
            ("f_neg_fare", "=IF(OR([dup]=1,[orphan]=1),0,IF(NOT(ISNUMBER(Raw_Passengers!E{e})),1,IF(Raw_Passengers!E{e}<=0,1,0)))"),
            ("f_age_missing", '=IF(AND([dup]=0,[orphan]=0,TRIM(Raw_Passengers!D{e}&"")=""),1,0)'),
            ("init_norm", "=" + S("Raw_Passengers!F{e}")), ("final_norm", "=" + S("Raw_Passengers!G{e}")),
            ("init_bad", '=IF(OR([init_norm]="",[init_norm]="Cancelled",[init_norm]="Mixed"),1,0)'), ("final_bad", '=IF(OR([final_norm]="",[final_norm]="Mixed"),1,0)'),
            ("f_status_alias", "=IF(AND([dup]=0,[orphan]=0),IF(OR(AND([init_bad]=0,NOT(EXACT(Raw_Passengers!F{e},[init_norm]))),AND([final_bad]=0,NOT(EXACT(Raw_Passengers!G{e},[final_norm])))),1,0),0)"),
            ("f_init_invalid", "=IF(AND([dup]=0,[orphan]=0,[init_bad]=1),1,0)"), ("f_final_invalid", "=IF(AND([dup]=0,[orphan]=0,[final_bad]=1),1,0)")]),
        "Work_Cancellations": ("Raw_Cancellations", NEV, [
            ("id", "=Raw_Cancellations!A{e}"), ("dup", "=IF(COUNTIF(Raw_Cancellations!$A$2:A{e},Raw_Cancellations!A{e})>1,1,0)"),
            ("orphan", "=IF(COUNTIF(Raw_Bookings!$A$2:$A$@NBK,Raw_Cancellations!B{e})=0,1,0)"),
            ("f_refund_exceeds", "=IF(OR([dup]=1,[orphan]=1),0,IF(Raw_Cancellations!I{e}>Raw_Cancellations!G{e}+0.005,1,0))"),
            ("ts_value", '=IFERROR(DATEVALUE(LEFT(Raw_Cancellations!C{e},10))+TIMEVALUE(MID(Raw_Cancellations!C{e},12,8)),"")'),
            ("bmatch", "=IFERROR(MATCH(Raw_Cancellations!B{e},@WB_id,0),0)"), ("booking_ts", '=IF([bmatch]=0,"",INDEX(@WB_ts_value,[bmatch]))'),
            ("booking_rejected", "=IF([bmatch]=0,0,IF(OR(INDEX(@WB_ts_missing,[bmatch])=1,INDEX(@WB_f_date_impossible,[bmatch])=1,INDEX(@WB_f_after,[bmatch])=1,COUNTIFS(@WP_bid,Raw_Cancellations!B{e},@WP_f_init_invalid,1)>0),1,0))"),
            ("f_before", "=IF(OR([dup]=1,[orphan]=1,[booking_rejected]=1),0,IF(AND(ISNUMBER([ts_value]),ISNUMBER([booking_ts])),IF([ts_value]<[booking_ts],1,0),0))")]),
        "Work_Capacity": ("Raw_Capacity", NCAP, [
            ("id", "=Raw_Capacity!A{e}"), ("key", '=Raw_Capacity!B{e}&"|"&Raw_Capacity!C{e}&"|"&Raw_Capacity!D{e}'),
            ("std", "=INDEX(Lookup_Class!$B$2:$B$7,MATCH(Raw_Capacity!D{e},Lookup_Class!$A$2:$A$7,0))"),
            ("consistent", "=IF(AND(Raw_Capacity!F{e}=[std],Raw_Capacity!G{e}=Raw_Capacity!E{e}*Raw_Capacity!F{e}),1,0)"),
            ("f_conflict", "=IF(AND(COUNTIF(@WK_key,[key])>1,[consistent]=0),1,0)"),
            ("f_total_mismatch", "=IF(AND([f_conflict]=0,Raw_Capacity!F{e}=[std],Raw_Capacity!G{e}<>Raw_Capacity!E{e}*Raw_Capacity!F{e}),1,0)"),
            ("f_spc_invalid", "=IF(AND([f_conflict]=0,Raw_Capacity!F{e}<>[std],Raw_Capacity!G{e}=Raw_Capacity!E{e}*[std]),1,0)")]),
        "Work_Operations": ("Raw_Operations", NOPS, [
            ("id", "=Raw_Operations!A{e}"), ("f_missing", '=IF(TRIM(Raw_Operations!E{e}&"")="",1,0)'),
            ("f_range", "=IF(ISNUMBER(Raw_Operations!E{e}),IF(OR(Raw_Operations!E{e}<-60,Raw_Operations!E{e}>1440),1,0),0)")]),
    }
    prefix = {"Work_Bookings": "WB", "Work_Passengers": "WP", "Work_Capacity": "WK", "Work_Cancellations": "WC", "Work_Operations": "WO"}
    letters = {s: {n: CL(i) for i, (n, _) in enumerate(sp[2])} for s, sp in specs.items()}
    repl = {"@NBK": str(NBK), "@NST": str(NST)}
    for s, sp in specs.items():
        for n, L in letters[s].items():
            repl[f"@{prefix[s]}_{n}"] = f"{s}!${L}$2:${L}${sp[1]}"
    for s, (rawname, n_last, cols) in specs.items():
        ws = W[s]
        for c, (n, _) in enumerate(cols):
            ws.write(0, c, n + (" (flag)" if n.startswith("f_") else ""), hdr)
        for r in range(2, n_last + 1):
            for c, (n, tmpl) in enumerate(cols):
                f = tmpl
                for k in sorted(repl, key=len, reverse=True):
                    f = f.replace(k, repl[k])
                f = f.replace("{e}", str(r))
                f = re.sub(r"\[(\w+)\]", lambda m: f"{letters[s][m.group(1)]}{r}", f)
                b.formula(ws, r - 1, c, f, calc)
        ws.freeze_panes(1, 1); ws.set_column(0, len(cols), 15)
        xc.side_label(b, ws, 0, len(cols) + 1, "SYNTHETIC DATA (defect-enriched sample of the raw extract). Not real data.")
    sums = lambda s, n: f"=SUM({s}!${letters[s][n]}$2:${letters[s][n]}${specs[s][1]})"
    KEYMAP = {"dup_booking_rows": sums("Work_Bookings", "dup"), "dup_passenger_rows": sums("Work_Passengers", "dup"), "dup_cancellation_rows": sums("Work_Cancellations", "dup"),
              "missing_total_fare": sums("Work_Bookings", "f_total_missing"), "total_fare_currency_format": sums("Work_Bookings", "f_total_currency"),
              "negative_passenger_fare": sums("Work_Passengers", "f_neg_fare"), "missing_route_id": sums("Work_Bookings", "f_route_missing"), "num_passengers_invalid": sums("Work_Bookings", "f_numpax_invalid"),
              "missing_age_band": sums("Work_Passengers", "f_age_missing"), "station_code_format": sums("Work_Bookings", "f_station_format"), "station_code_unknown": sums("Work_Bookings", "f_station_unknown"),
              "missing_booking_ts": sums("Work_Bookings", "ts_missing"), "journey_date_format": sums("Work_Bookings", "f_date_format"), "journey_date_impossible": sums("Work_Bookings", "f_date_impossible"),
              "booking_after_journey": sums("Work_Bookings", "f_after"), "cancellation_before_booking": sums("Work_Cancellations", "f_before"), "booking_status_alias": sums("Work_Bookings", "f_status_alias"),
              "booking_status_invalid": sums("Work_Bookings", "f_status_invalid"), "passenger_status_alias": sums("Work_Passengers", "f_status_alias"),
              "passenger_final_status_invalid": sums("Work_Passengers", "f_final_invalid"), "passenger_initial_status_invalid": sums("Work_Passengers", "f_init_invalid"),
              "orphan_cancellation_rows": sums("Work_Cancellations", "orphan"), "orphan_passenger_rows": sums("Work_Passengers", "orphan"), "refund_exceeds_fare": sums("Work_Cancellations", "f_refund_exceeds"),
              "capacity_total_mismatch": sums("Work_Capacity", "f_total_mismatch"), "capacity_seats_per_coach_invalid": sums("Work_Capacity", "f_spc_invalid"),
              "capacity_conflicting_duplicate": sums("Work_Capacity", "f_conflict"), "missing_arrival_delay": sums("Work_Operations", "f_missing"), "delay_out_of_range": sums("Work_Operations", "f_range")}

    # ---- answer key
    ws = W["Answer_Key"]
    ws.write(0, 0, "Answer key: expected issue counts in THIS sample versus your Excel formulas", b.title)
    ws.merge_range(1, 0, 1, 8, "Expected = the cleaner's independent detection (python/src/clean_data.py) on exactly these rows. Injected = rows recorded in the injection log for this sample. Excel = the worked-solution formula count. SYNTHETIC DATA. The sample is deliberately enriched with defects and is not a guide to real defect rates.", b.note); ws.set_row(1, 44)
    for c, h in enumerate(["Issue code", "Table", "Issue type", "Expected (independent detection)", "Injected in sample (log)", "Excel formula count", "Result", "Outcome", "Cleaning rule"]):
        ws.write(3, c, h, hdr)
    for i, code in enumerate(dq.ORDER):
        x = 4 + i; m = dq.CATALOG[code]
        ws.write_string(x, 0, code); ws.write_string(x, 1, m["table"]); ws.write_string(x, 2, m["title"])
        ws.write_number(x, 3, res.issues[code]["detected"]); ws.write_number(x, 4, injected[code])
        if code in MANUAL:
            ws.write_string(x, 5, "manual exercise"); ws.write_string(x, 6, "MANUAL", b.f(bold=True, font_color="#7F6000"))
        else:
            b.formula(ws, x, 5, KEYMAP[code], calc); b.formula(ws, x, 6, f'=IF(F{x + 1}=D{x + 1},"PASS","FAIL")', b.f(bold=True))
        ws.write_string(x, 7, m["outcome"]); ws.write_string(x, 8, m["rule"])
    last = 4 + len(dq.ORDER)
    ws.write_string(last + 1, 2, "Summary", b.f(bold=True))
    b.formula(ws, last + 1, 3, f'=IF(COUNTIF(G5:G{last},"FAIL")=0,"ALL FORMULA COUNTS MATCH ("&COUNTIF(G5:G{last},"PASS")&" of {len(dq.ORDER) - len(MANUAL)}; {len(MANUAL)} manual)","FAILURES: "&COUNTIF(G5:G{last},"FAIL"))', b.f(bold=True))
    ws.conditional_format(4, 6, last - 1, 6, {"type": "cell", "criteria": "==", "value": '"PASS"', "format": b.f(bg_color="#C6EFCE", font_color="#006100")})
    ws.conditional_format(4, 6, last - 1, 6, {"type": "cell", "criteria": "==", "value": '"FAIL"', "format": b.f(bg_color="#FFC7CE", font_color="#9C0006")})
    ws.set_column(0, 0, 34); ws.set_column(1, 1, 20); ws.set_column(2, 2, 36); ws.set_column(3, 6, 16); ws.set_column(7, 7, 11); ws.set_column(8, 8, 90); ws.set_row(3, 42)

    # ---- solution sheets + validation checks
    cb, cp = cleaned["bookings"], cleaned["booking_passengers"]
    NCB, NCP = len(cb) + 1, len(cp) + 1
    ws = W["Clean_Bookings_Solution"]
    cols = ["booking_id", "booking_reference", "train_id", "journey_date", "route_id", "boarding_station_id", "destination_station_id", "travel_class", "booking_ts", "num_passengers", "booking_status", "total_fare"]
    for c, h in enumerate(cols):
        ws.write(0, c, h, hdr)
    for r, row in enumerate(cb[cols].itertuples(index=False), start=1):
        for c, v in enumerate(row):
            if cols[c] == "journey_date":
                ws.write_datetime(r, c, pd.Timestamp(v).to_pydatetime(), b.f(num_format="yyyy-mm-dd"))
            elif cols[c] == "booking_ts":
                ws.write_datetime(r, c, pd.Timestamp(v).to_pydatetime(), b.f(num_format="yyyy-mm-dd hh:mm"))
            elif isinstance(v, str):
                ws.write_string(r, c, v)
            else:
                ws.write_number(r, c, float(v))
    ws.freeze_panes(1, 1); ws.set_column(0, len(cols), 17)
    xc.side_label(b, ws, 0, len(cols) + 1, "SYNTHETIC DATA (cleaned solution for the defect-enriched sample). Not real data.")
    ws = W["Clean_Passengers_Solution"]
    pcols = ["passenger_id", "booking_id", "passenger_seq", "age_band", "fare_amount", "initial_status", "final_status", "cancellation_id"]
    for c, h in enumerate(pcols):
        ws.write(0, c, h, hdr)
    for r, row in enumerate(cp[pcols].itertuples(index=False), start=1):
        for c, v in enumerate(row):
            if pd.isna(v):
                continue
            ws.write_string(r, c, v) if isinstance(v, str) else ws.write_number(r, c, float(v))
    ws.freeze_panes(1, 1); ws.set_column(0, len(pcols), 17)
    xc.side_label(b, ws, 0, len(pcols) + 1, "SYNTHETIC DATA (cleaned solution for the defect-enriched sample). Not real data.")
    CB = lambda col: f"Clean_Bookings_Solution!${col}$2:${col}${NCB}"
    CP = lambda col: f"Clean_Passengers_Solution!${col}$2:${col}${NCP}"
    checks = [
        ("No duplicate booking_id in the cleaned bookings", f"=SUMPRODUCT(--(COUNTIF({CB('A')},{CB('A')})>1))=0"),
        ("No duplicate passenger_id in the cleaned passengers", f"=SUMPRODUCT(--(COUNTIF({CP('A')},{CP('A')})>1))=0"),
        ("Every booking_status is Confirmed, RAC, Waitlisted, Cancelled or Mixed", f'=SUMPRODUCT(--(({CB("K")}<>"Confirmed")*({CB("K")}<>"RAC")*({CB("K")}<>"Waitlisted")*({CB("K")}<>"Cancelled")*({CB("K")}<>"Mixed")))=0'),
        ("BR-03: num_passengers equals the passenger rows of each booking", f"=SUMPRODUCT(--({CB('J')}<>COUNTIF({CP('B')},{CB('A')})))=0"),
        ("BR-03: total_fare equals the sum of the passengers' fares", f"=SUMPRODUCT(--(ABS({CB('L')}-SUMIF({CP('B')},{CB('A')},{CP('E')}))>0.005))=0"),
        ("No passenger without a booking", f"=SUMPRODUCT(--(COUNTIF({CB('A')},{CP('B')})=0))=0"),
        ("All fares are positive", f"=AND(MIN({CB('L')})>0,MIN({CP('E')})>0)"),
        ("Journey dates are inside 2024-09-01 to 2026-08-31", f"=AND(MIN({CB('D')})>=DATE(2024,9,1),MAX({CB('D')})<=DATE(2026,8,31))"),
        ("BR-04: every booking timestamp is on or before its journey date", f"=SUMPRODUCT(--(INT({CB('I')})>{CB('D')}))=0"),
        ("BR-06: boarding and destination stations differ", f"=SUMPRODUCT(--({CB('F')}={CB('G')}))=0"),
        ("BR-01: passenger statuses are in the allowed domains", f'=SUMPRODUCT(--(({CP("G")}<>"Confirmed")*({CP("G")}<>"RAC")*({CP("G")}<>"Waitlisted")*({CP("G")}<>"Cancelled")))=0'),
    ]
    ws = W["Validation_Checks"]
    ws.write(0, 0, "Validation checks on the cleaned tables", b.title)
    ws.merge_range(1, 0, 1, 3, "SYNTHETIC DATA. These formulas read Clean_Bookings_Solution and Clean_Passengers_Solution. Paste your own cleaned tables over those sheets (same columns) and every check should read PASS.", b.note); ws.set_row(1, 32)
    for c, h in enumerate(["#", "Check", "Result"]):
        ws.write(3, c, h, hdr)
    for i, (lab, f) in enumerate(checks):
        ws.write_number(4 + i, 0, i + 1); ws.write_string(4 + i, 1, lab); b.formula(ws, 4 + i, 2, f'=IF({f[1:]},"PASS","FAIL")', b.f(bold=True))
    e = 4 + len(checks)
    ws.write_string(e + 1, 1, "OVERALL", b.f(bold=True)); b.formula(ws, e + 1, 2, f'=IF(COUNTIF(C5:C{e},"FAIL")=0,"ALL {len(checks)} CHECKS PASS","FAILURES: "&COUNTIF(C5:C{e},"FAIL"))', b.f(bold=True))
    ws.conditional_format(4, 2, e + 1, 2, {"type": "text", "criteria": "containing", "value": "FAIL", "format": b.f(bg_color="#FFC7CE", font_color="#9C0006")})
    ws.conditional_format(4, 2, e + 1, 2, {"type": "text", "criteria": "containing", "value": "PASS", "format": b.f(bg_color="#C6EFCE", font_color="#006100")})
    ws.set_column(0, 0, 5); ws.set_column(1, 1, 86); ws.set_column(2, 2, 26)

    # ---- exercises + README
    ws = W["Exercises"]
    ws.write(0, 0, "Data cleaning exercises", b.title)
    ws.merge_range(1, 0, 1, 7, xc.SYNTHETIC_BANNER, b.warn); ws.set_row(1, 44)
    for c, h in enumerate(["#", "Level", "Issue code", "Sheet", "Problem to find", "Cleaning rule to apply", "Suggested functions", "Expected count in this sample"]):
        ws.write(2, c, h, hdr)
    for i, code in enumerate(dq.ORDER):
        m, (lvl, fn, sheet) = dq.CATALOG[code], HINTS[code]
        x = 3 + i
        ws.write_number(x, 0, i + 1); ws.write_string(x, 1, lvl); ws.write_string(x, 2, code); ws.write_string(x, 3, sheet)
        ws.write_string(x, 4, m["issue"], b.f(text_wrap=True)); ws.write_string(x, 5, m["rule"], b.f(text_wrap=True)); ws.write_string(x, 6, fn, b.f(text_wrap=True))
        ws.write_number(x, 7, res.issues[code]["detected"]); ws.set_row(x, 44)
    ws.set_column(0, 0, 4); ws.set_column(1, 1, 16); ws.set_column(2, 2, 32); ws.set_column(3, 3, 24); ws.set_column(4, 6, 48); ws.set_column(7, 7, 14); ws.freeze_panes(3, 3)
    ws.autofilter(2, 0, 2 + len(dq.ORDER), 7)
    ws = W["README"]
    ws.write(0, 0, "Data cleaning and validation exercises (Phase 3)", b.title)
    ws.merge_range(1, 0, 1, 6, "Independent portfolio project. Not an official IRCTC or Indian Railways system. All data is synthetic.", b.f(bold=True))
    ws.merge_range(2, 0, 2, 6, xc.SYNTHETIC_BANNER, b.warn); ws.set_row(2, 44)
    steps = [f"Sample: {len(sub['bookings']):,} raw booking rows, {len(sub['booking_passengers']):,} passenger rows, {len(sub['cancellations']):,} cancellation rows, {len(sub['seat_capacity'])} capacity rows, {len(sub['train_operations'])} operations rows, taken from data/raw/synthetic (never edited). It is enriched so that every one of the 30 issue types appears; real defect rates in the full raw extract are about 1% or less.",
             "Raw_* sheets hold the extract as delivered. Plain numbers are stored as numbers (as an Excel CSV import would); currency text such as '\u20b91,250.00', DD-MM-YYYY dates and alias statuses stay text.",
             "Exercises: work through the list (Beginner to Advanced). Try each on the Raw_* sheets first, then compare with the Work_* sheets, which hold one flag column per issue.",
             "Answer_Key: expected counts (independent detection by the Python cleaner) beside the Excel formula counts. All formula counts should match; total_fare_invalid is a manual exercise.",
             "Clean_*_Solution: the cleaned result for these rows. Validation_Checks: formula checks (duplicates, statuses, BR-03 sums, BR-04 dates, orphans). Paste your own cleaned tables there to test them.",
             "Cleaning rules never invent data: unrecoverable records are rejected with their whole booking family; missing age band becomes 'Unknown' and missing delays stay blank. See docs/data_quality_report.md.",
             "XLOOKUP is not used: it could not be verified in the build environment. The worked solution uses INDEX/MATCH and SUMPRODUCT lookups that work in every Excel version and in Google Sheets. In Excel 365 you may practise the same lookups with XLOOKUP."]
    for i, t in enumerate(steps):
        ws.merge_range(4 + i, 0, 4 + i, 6, t, b.f(text_wrap=True)); ws.set_row(4 + i, 46)
    ws.set_column(0, 6, 20)
    W["README"].activate()


def main():
    import time
    t0 = time.time()
    xc.two_pass(build, OUT, cfg.ROOT / "reports" / "phase3_work")
    print("built", OUT.name, "%.0fs" % (time.time() - t0), "%.1f MB" % (OUT.stat().st_size / 1e6))


if __name__ == "__main__":
    main()
