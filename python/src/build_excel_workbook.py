"""Build excel/IRCTC_Booking_Analytics_Workbook.xlsx (deliverables 1, 4 and 5, plus the formula-driven dashboard).

Data strategy: monthly aggregates (from the FULL cleaned dataset) for executive reporting; a run-complete SAMPLE of detailed booking and
passenger records (48 of 768 simulated runs) for row-level formulas; focused datasets for cancellation, occupancy and operations.
Every KPI uses docs/KPI_definitions.md. Excel results are reconciled against the Python reference (kpi.py) in the tests.
"""
import numpy as np
import pandas as pd
from xlsxwriter.utility import xl_col_to_name as CL

import clean_data as cl
import config as cfg
import kpi
import xl_common as xc

OUT = cfg.ROOT / "excel" / "IRCTC_Booking_Analytics_Workbook.xlsx"
CLASSES = ["SL", "3A", "2A", "1A", "CC", "2S"]
STATUSES = ["Confirmed", "RAC", "Waitlisted", "Cancelled"]

KPI_DEFS = {
    "total_bookings": ("Bookings, all statuses", "count"),
    "total_passengers": ("Passengers on all bookings, all final statuses", "count"),
    "confirmed_bookings": ("Bookings where EVERY passenger finished Confirmed (roll-up status Confirmed)", "count"),
    "mixed_bookings": ("Bookings whose passengers ended in different statuses (reported separately)", "count"),
    "cancelled_bookings": ("Bookings where every passenger was cancelled by the passenger", "count"),
    "cancelled_passengers": ("Passengers with final status Cancelled", "count"),
    "passenger_cancellation_rate": ("Cancelled passengers / Total Passengers", "Total Passengers (all four final statuses)"),
    "booking_cancellation_rate": ("Companion: Cancelled Booking Count / Total Bookings", "Total Bookings"),
    "gross_value": ("Sum of total_fare over all bookings, before refunds. Not revenue or profit", "n/a"),
    "refund_passenger": ("Refunds from Passenger cancellation events", "n/a"),
    "refund_system": ("Refunds from System auto-refund events (uncleared waitlist)", "n/a"),
    "refund_total": ("All refund events", "n/a"),
    "retained_charges": ("Cancellation charges retained", "n/a"),
    "net_value": ("Gross Booking Value minus Refund Amount. Not revenue or profit", "n/a"),
    "avg_fare_per_passenger": ("Gross Booking Value / Total Passengers", "Total Passengers"),
    "avg_fare_per_booking": ("Secondary: Gross Booking Value / Total Bookings", "Total Bookings"),
    "wl_demand": ("Waiting-List Demand: passengers with initial status Waitlisted (whatever happened later)", "count"),
    "wl_cleared": ("Initially waitlisted passengers who finished Confirmed or RAC", "count"),
    "wl_clearance_rate": ("Waitlist Clearance Rate = cleared / Waiting-List Demand", "Initially waitlisted passengers"),
    "wl_uncleared": ("Uncleared Waitlist Passengers: final status Waitlisted, refunded by System events", "count"),
    "confirmed_pax": ("Passengers with final status Confirmed", "count"),
    "rac_pax": ("Passengers with final status RAC", "count"),
    "seat_supply": ("Available Seats: SUM(total_seats), capacity not unsold seats", "n/a"),
    "booked_seats": ("Confirmed + RAC weight (0.5) x RAC passengers, final statuses", "n/a"),
    "occupancy": ("Seat Occupancy % = Booked Seats / Available Seats, matched per train-class run", "Available Seats (same train, date, class)"),
    "confirmed_occupancy": ("Confirmed Occupancy % = Confirmed passengers / Available Seats", "Available Seats"),
    "waitlist_pressure": ("Waitlist Pressure % = Uncleared waitlist passengers / Available Seats. Not part of occupancy", "Available Seats"),
    "simulated_runs": ("Simulated train runs", "count"),
    "bookings_per_run": ("Bookings per Simulated Run (sample-safe volume measure)", "Simulated runs"),
    "passengers_per_run": ("Passengers per Simulated Run", "Simulated runs"),
    "runs_with_delay": ("Runs with a recorded (non-NULL) arrival delay", "count"),
    "on_time_runs": ("Runs with arrival delay <= 15 minutes", "count"),
    "otp": ("On-Time Performance % = on-time runs / runs with a recorded arrival delay", "Runs with a recorded arrival delay"),
    "delay_sum_pos": ("Sum of max(arrival delay, 0) over runs with a recorded delay", "n/a"),
    "avg_delay": ("Average Delay = mean of max(arrival delay, 0), early = 0", "Runs with a recorded arrival delay"),
    "delayed_runs": ("Delayed Train Runs: arrival delay > 15 minutes (runs, not distinct trains)", "n/a"),
}
TOL = {"count": 0.0, "INR": 0.005, "share": 0.00005}
CALC_KEYS = ["total_bookings", "total_passengers", "confirmed_bookings", "mixed_bookings", "cancelled_bookings", "cancelled_passengers",
             "passenger_cancellation_rate", "booking_cancellation_rate", "gross_value", "refund_passenger", "refund_system", "refund_total",
             "retained_charges", "net_value", "avg_fare_per_passenger", "avg_fare_per_booking", "wl_demand", "wl_cleared", "wl_clearance_rate",
             "wl_uncleared", "confirmed_pax", "rac_pax", "seat_supply", "booked_seats", "occupancy", "confirmed_occupancy", "waitlist_pressure",
             "simulated_runs", "bookings_per_run", "passengers_per_run", "runs_with_delay", "on_time_runs", "otp", "delay_sum_pos", "avg_delay",
             "delayed_runs"]
UNIT = {k: u for k, _, u, *_ in kpi.KPI_SPEC for k in [k]}
for k in CALC_KEYS:
    UNIT.setdefault(k, "count")


def scheduled_runs(T):
    days = pd.date_range(cfg.JOURNEY_START, cfg.JOURNEY_END)
    return int(sum(sum(rd[d.weekday()] == "Y" for d in days) for rd in T["trains"]["run_days"]))


def load():
    T = cl.read_clean()
    bk, ps, ev, cap, ops = kpi._prep(T)
    S = kpi.select_sample(T)
    ref_full = kpi.compute_kpis(bk, ps, ev, cap, ops)
    ref_smp = kpi.compute_kpis(S["bk"], S["ps"], S["ev"], S["cap"], S["ops"])
    monthly = pd.read_csv(kpi.DERIVED_DIR / "monthly_kpis.csv")
    crf_all = kpi.class_runs_frame(S["ps"], S["cap"], S["bk"])
    return dict(T=T, S=S, ref_full=ref_full, ref_smp=ref_smp, monthly=monthly, crf=crf_all, sched=scheduled_runs(T))


def put(b, ws, r, c, v, kind, fm):
    if v is None or (isinstance(v, float) and np.isnan(v)) or (not isinstance(v, str) and pd.isna(v)):
        return
    if kind == "date":
        ws.write_datetime(r, c, pd.Timestamp(v).to_pydatetime(), fm["date"])
    elif kind == "datetime":
        ws.write_datetime(r, c, pd.Timestamp(v).to_pydatetime(), fm["datetime"])
    elif kind == "money":
        ws.write_number(r, c, float(v), fm["money"])
    elif kind == "int":
        ws.write_number(r, c, int(v), fm["int"])
    else:
        ws.write_string(r, c, str(v), fm["text"])


def build(b: xc.Book):
    D = load()
    S, mo = D["S"], D["monthly"]
    fm = dict(date=b.f(num_format="yyyy-mm-dd"), datetime=b.f(num_format="yyyy-mm-dd hh:mm"), money=b.f(num_format="#,##0.00"),
              int=b.f(num_format="#,##0"), text=b.f(), pct=b.f(num_format="0.0%"), pct2=b.f(num_format="0.00%"), num1=b.f(num_format="#,##0.0"),
              num2=b.f(num_format="#,##0.00"), calc=b.f(bg_color="#EAF1FB"), inp=b.f(bg_color="#FFF2CC", border=1), bold=b.f(bold=True))
    fmc = dict(int=b.f(num_format="#,##0", bg_color="#EAF1FB"), pct=b.f(num_format="0.0%", bg_color="#EAF1FB"), money=b.f(num_format="#,##0.00", bg_color="#EAF1FB"),
               num2=b.f(num_format="#,##0.00", bg_color="#EAF1FB"), text=b.f(bg_color="#EAF1FB"))
    wb = b.wb
    names = ["README", "KPI_Definitions", "Dashboard", "Monthly_Aggregates", "Cancellation_Refund", "Occupancy_Demand", "KPI_Calc", "Validation",
             "Parameters", "Data_Bookings", "Data_Passengers", "Data_Cancellations", "Data_ClassRuns", "Data_Runs"]
    W = {n: wb.add_worksheet(n) for n in names}
    for n, color in [("README", "#1F3864"), ("Dashboard", "#2E75B6"), ("Cancellation_Refund", "#2E75B6"), ("Occupancy_Demand", "#2E75B6"), ("Monthly_Aggregates", "#548235"),
                     ("KPI_Calc", "#BF8F00"), ("Validation", "#BF8F00")]:
        W[n].set_tab_color(color)

    bk, ps, ev, crf, ops = S["bk"].reset_index(drop=True), S["ps"].reset_index(drop=True), S["ev"].reset_index(drop=True), D["crf"].reset_index(drop=True), S["ops"].reset_index(drop=True)
    NB, NP, NE, NC, NR = len(bk) + 1, len(ps) + 1, len(ev) + 1, len(crf) + 1, len(ops) + 1     # last Excel row of each data sheet

    def label_data_sheet(ws, nrows, ncols):
        ws.write(0, ncols, "data_origin", b.hdr); ws.write_column(1, ncols, ["SYNTHETIC"] * nrows); ws.set_column(ncols, ncols, 14)
        xc.side_label(b, ws, 0, ncols + 2, "SYNTHETIC DATA. " + xc.SAMPLE_LABEL)

    # ------------------------------------------------------------------ Parameters
    ws = W["Parameters"]
    ws.write(0, 0, "Parameters and lookup lists", b.title)
    rows = [("RAC seat weight (configurable simulation assumption, not an official rule)", cfg.RAC_SEAT_WEIGHT), ("On-time threshold (minutes, project convention)", cfg.ON_TIME_THRESHOLD_MIN),
            ("Scheduled runs in the modelled schedule (journey window)", D["sched"]), ("Simulated runs in the full cleaned dataset", len(D["T"]["train_operations"]))]
    for i, (lab, v) in enumerate(rows):
        ws.write(1 + i, 0, lab); ws.write_number(1 + i, 1, v, fm["inp"])
    ws.write(5, 0, "Simulated share of scheduled runs"); b.formula(ws, 5, 1, "=B5/B4", fm["pct"])
    ws.write(6, 0, "Simulated runs in this workbook's sample"); b.formula(ws, 6, 1, f"=COUNTA(Data_Runs!$A$2:$A${NR})", fm["int"])
    ws.write(8, 0, "Lead bucket lower bound (days)", b.hdr); ws.write(8, 1, "Bucket label", b.hdr)
    for i, (lo, lab) in enumerate(zip([0, 4, 15, 31, 61], kpi.LEAD_LABELS)):
        ws.write_number(9 + i, 0, lo); ws.write_string(9 + i, 1, lab)
    ws.write(8, 3, "Travel class", b.hdr)
    for i, c in enumerate(CLASSES):
        ws.write_string(9 + i, 3, c)
    ws.data_validation("B2", {"validate": "decimal", "criteria": "between", "minimum": 0, "maximum": 1, "error_title": "RAC weight", "error_message": "Enter a value between 0 and 1"})
    ws.data_validation("B3", {"validate": "integer", "criteria": ">=", "value": 0})
    ws.set_column(0, 0, 70); ws.set_column(1, 1, 16); ws.set_column(3, 3, 14)
    xc.side_label(b, ws, 0, 3, "SYNTHETIC DATA. " + xc.SAMPLE_LABEL)
    RACW, OTPT = "Parameters!$B$2", "Parameters!$B$3"

    # ------------------------------------------------------------------ data sheets
    ws = W["Data_Bookings"]
    hd = ["booking_id", "booking_reference", "train_id", "journey_date", "route_name", "travel_class", "booking_ts", "num_passengers", "booking_status", "total_fare",
          "run_class_key", "journey_month (formula)", "lead_days (formula)", "lead_bucket (formula)", "lead_bucket_source (validation)", "journey_month_source (validation)"]
    for c, h in enumerate(hd):
        ws.write(0, c, h, b.hdr)
    for i, r in bk.iterrows():
        x = i + 1
        put(b, ws, x, 0, r.booking_id, "int", fm); put(b, ws, x, 1, r.booking_reference, "text", fm); put(b, ws, x, 2, r.train_id, "int", fm)
        put(b, ws, x, 3, r.journey_date, "date", fm); put(b, ws, x, 4, r.route_name, "text", fm); put(b, ws, x, 5, r.travel_class, "text", fm)
        put(b, ws, x, 6, r.booking_ts, "datetime", fm); put(b, ws, x, 7, r.num_passengers, "int", fm); put(b, ws, x, 8, r.booking_status, "text", fm)
        put(b, ws, x, 9, r.total_fare, "money", fm); put(b, ws, x, 10, r.run_class_key, "text", fm)
        b.formula(ws, x, 11, f'=TEXT(D{x + 1},"yyyy-mm")', fmc["text"]); b.formula(ws, x, 12, f"=D{x + 1}-INT(G{x + 1})", fmc["int"])
        b.formula(ws, x, 13, f"=LOOKUP(M{x + 1},Parameters!$A$10:$A$14,Parameters!$B$10:$B$14)", fmc["text"])
        put(b, ws, x, 14, r.lead_bucket, "text", fm); put(b, ws, x, 15, r.journey_month, "text", fm)
    ws.freeze_panes(1, 1); label_data_sheet(ws, NB - 1, len(hd)); ws.autofilter(0, 0, NB - 1, len(hd)); ws.set_column(0, 15, 16); ws.set_column(4, 4, 26)

    ws = W["Data_Passengers"]
    hd = ["passenger_id", "booking_id", "journey_month", "travel_class", "route_name", "lead_bucket", "run_class_key", "initial_status", "final_status", "fare_amount",
          "cancellation_id", "seat_equivalent (formula)"]
    for c, h in enumerate(hd):
        ws.write(0, c, h, b.hdr)
    for i, r in ps.iterrows():
        x = i + 1
        put(b, ws, x, 0, r.passenger_id, "int", fm); put(b, ws, x, 1, r.booking_id, "int", fm); put(b, ws, x, 2, r.journey_month, "text", fm)
        put(b, ws, x, 3, r.travel_class, "text", fm); put(b, ws, x, 4, r.route_name, "text", fm); put(b, ws, x, 5, r.lead_bucket, "text", fm)
        put(b, ws, x, 6, r.run_class_key, "text", fm); put(b, ws, x, 7, r.initial_status, "text", fm); put(b, ws, x, 8, r.final_status, "text", fm)
        put(b, ws, x, 9, r.fare_amount, "money", fm); put(b, ws, x, 10, r.cancellation_id, "int", fm)
        b.formula(ws, x, 11, f'=IF(I{x + 1}="Confirmed",1,IF(I{x + 1}="RAC",{RACW},0))', fmc["num2"])
    ws.freeze_panes(1, 1); label_data_sheet(ws, NP - 1, len(hd)); ws.autofilter(0, 0, NP - 1, len(hd)); ws.set_column(0, 11, 16); ws.set_column(4, 4, 26); ws.set_column(6, 6, 24)
    ws.write_comment(0, 2, "Joined from Data_Bookings (journey month, class, route, lead bucket) so that SUMIFS/COUNTIFS stay fast. The cleaning workbook demonstrates INDEX/MATCH joins.")

    ws = W["Data_Cancellations"]
    hd = ["cancellation_id", "booking_id", "journey_month", "travel_class", "cancellation_ts", "cancellation_type", "status_at_cancellation", "cancelled_passengers",
          "original_fare_amount", "cancellation_charge", "refund_amount", "check: original - charge - refund (formula, must be 0)"]
    for c, h in enumerate(hd):
        ws.write(0, c, h, b.hdr)
    for i, r in ev.iterrows():
        x = i + 1
        put(b, ws, x, 0, r.cancellation_id, "int", fm); put(b, ws, x, 1, r.booking_id, "int", fm); put(b, ws, x, 2, r.journey_month, "text", fm)
        put(b, ws, x, 3, r.travel_class, "text", fm); put(b, ws, x, 4, r.cancellation_ts, "datetime", fm); put(b, ws, x, 5, r.cancellation_type, "text", fm)
        put(b, ws, x, 6, r.status_at_cancellation, "text", fm); put(b, ws, x, 7, r.cancelled_passengers, "int", fm); put(b, ws, x, 8, r.original_fare_amount, "money", fm)
        put(b, ws, x, 9, r.cancellation_charge, "money", fm); put(b, ws, x, 10, r.refund_amount, "money", fm)
        b.formula(ws, x, 11, f"=ROUND(I{x + 1}-J{x + 1}-K{x + 1},2)", fmc["num2"])
    ws.freeze_panes(1, 1); label_data_sheet(ws, NE - 1, len(hd)); ws.autofilter(0, 0, NE - 1, len(hd)); ws.set_column(0, 11, 17)

    ws = W["Data_ClassRuns"]
    hd = ["run_class_key", "train_id", "journey_date", "journey_month", "travel_class", "route_name", "coaches_attached", "seats_per_coach", "total_seats", "rac_berths", "wl_limit",
          "confirmed_pax (formula)", "rac_pax (formula)", "wl_final_pax (formula)", "cancelled_pax (formula)", "initial_wl_pax (formula)", "passengers (formula)",
          "bookings (formula)", "booked_seats (formula)", "occupancy (formula)", "confirmed_occupancy (formula)", "waitlist_pressure (formula)"]
    for c, h in enumerate(hd):
        ws.write(0, c, h, b.hdr)
    pk, pi_, pf = f"Data_Passengers!$G$2:$G${NP}", f"Data_Passengers!$H$2:$H${NP}", f"Data_Passengers!$I$2:$I${NP}"
    for i, r in crf.iterrows():
        x, e = i + 1, i + 2
        put(b, ws, x, 0, r.run_class_key, "text", fm); put(b, ws, x, 1, r.train_id, "int", fm); put(b, ws, x, 2, r.journey_date, "date", fm)
        put(b, ws, x, 3, r.journey_month, "text", fm); put(b, ws, x, 4, r.travel_class, "text", fm); put(b, ws, x, 5, r.route_name, "text", fm)
        for c, k in zip(range(6, 11), ["coaches_attached", "seats_per_coach", "total_seats", "rac_berths", "wl_limit"]):
            put(b, ws, x, c, r[k], "int", fm)
        for c, st in zip(range(11, 15), ["Confirmed", "RAC", "Waitlisted", "Cancelled"]):
            b.formula(ws, x, c, f'=COUNTIFS({pk},$A{e},{pf},"{st}")', fmc["int"])
        b.formula(ws, x, 15, f'=COUNTIFS({pk},$A{e},{pi_},"Waitlisted")', fmc["int"])
        b.formula(ws, x, 16, f"=SUM(L{e}:O{e})", fmc["int"])
        b.formula(ws, x, 17, f"=COUNTIFS(Data_Bookings!$K$2:$K${NB},$A{e})", fmc["int"])
        b.formula(ws, x, 18, f"=L{e}+{RACW}*M{e}", fmc["num2"]); b.formula(ws, x, 19, f"=S{e}/I{e}", fmc["pct"])
        b.formula(ws, x, 20, f"=L{e}/I{e}", fmc["pct"]); b.formula(ws, x, 21, f"=N{e}/I{e}", fmc["pct"])
    ws.freeze_panes(1, 1); label_data_sheet(ws, NC - 1, len(hd)); ws.autofilter(0, 0, NC - 1, len(hd)); ws.set_column(0, 21, 15); ws.set_column(0, 0, 26); ws.set_column(5, 5, 26)
    ws.conditional_format(1, 19, NC - 1, 19, {"type": "data_bar", "bar_color": "#63BE7B", "min_type": "num", "min_value": 0, "max_type": "num", "max_value": 1})

    ws = W["Data_Runs"]
    hd = ["operation_id", "train_id", "train_number", "train_type", "route_name", "run_date", "journey_month", "departure_delay_min", "arrival_delay_min (blank = missing)",
          "has_delay (formula)", "on_time (formula)", "delay_positive (formula)", "delayed (formula)"]
    for c, h in enumerate(hd):
        ws.write(0, c, h, b.hdr)
    for i, r in ops.iterrows():
        x, e = i + 1, i + 2
        put(b, ws, x, 0, r.operation_id, "int", fm); put(b, ws, x, 1, r.train_id, "int", fm); put(b, ws, x, 2, r.train_number, "text", fm)
        put(b, ws, x, 3, r.train_type, "text", fm); put(b, ws, x, 4, r.route_name, "text", fm); put(b, ws, x, 5, r.run_date, "date", fm)
        put(b, ws, x, 6, r.journey_month, "text", fm); put(b, ws, x, 7, r.departure_delay_min, "int", fm)
        if not pd.isna(r.arrival_delay_min):
            ws.write_number(x, 8, float(r.arrival_delay_min))
        b.formula(ws, x, 9, f"=IF(ISNUMBER(I{e}),1,0)", fmc["int"]); b.formula(ws, x, 10, f'=IF(ISNUMBER(I{e}),IF(I{e}<={OTPT},1,0),"")', fmc["int"])
        b.formula(ws, x, 11, f'=IF(ISNUMBER(I{e}),MAX(I{e},0),"")', fmc["int"]); b.formula(ws, x, 12, f'=IF(ISNUMBER(I{e}),IF(I{e}>{OTPT},1,0),"")', fmc["int"])
    ws.freeze_panes(1, 1); label_data_sheet(ws, NR - 1, len(hd)); ws.autofilter(0, 0, NR - 1, len(hd)); ws.set_column(0, 12, 17); ws.set_column(4, 4, 26)

    # ------------------------------------------------------------------ Monthly_Aggregates (FULL cleaned dataset)
    ws = W["Monthly_Aggregates"]
    ws.write(0, 0, "Monthly aggregates by journey month (full cleaned dataset, executive view)", b.title)
    ws.merge_range(1, 0, 1, 14, xc.SYNTHETIC_BANNER, b.warn); ws.merge_range(2, 0, 2, 14, xc.PER_RUN_NOTE, b.note); ws.set_row(1, 32); ws.set_row(2, 28)
    vals = ["journey_month", "simulated_runs", "class_runs", "total_bookings", "total_passengers", "confirmed_bookings", "mixed_bookings", "cancelled_bookings",
            "cancelled_passengers", "wl_demand", "wl_cleared", "wl_uncleared", "confirmed_pax", "rac_pax", "seat_supply", "gross_value", "refund_passenger", "refund_system",
            "retained_charges", "runs_with_delay", "on_time_runs", "delay_sum_pos", "delayed_runs"]
    L = {k: CL(i) for i, k in enumerate(vals)}
    calc = [("passenger_cancellation_rate", "IF({E}=0,\"\",{cancelled_passengers}/{total_passengers})", "pct"), ("booking_cancellation_rate", "IF({total_bookings}=0,\"\",{cancelled_bookings}/{total_bookings})", "pct"),
            ("refund_total", "{refund_passenger}+{refund_system}", "money"), ("net_value", "{gross_value}-{refund_total}", "money"),
            ("avg_fare_per_passenger", "IF({total_passengers}=0,\"\",{gross_value}/{total_passengers})", "money"), ("wl_clearance_rate", "IF({wl_demand}=0,\"\",{wl_cleared}/{wl_demand})", "pct"),
            ("booked_seats", f"{{confirmed_pax}}+{RACW}*{{rac_pax}}", "num2"), ("occupancy", "IF({seat_supply}=0,\"\",{booked_seats}/{seat_supply})", "pct"),
            ("waitlist_pressure", "IF({seat_supply}=0,\"\",{wl_uncleared}/{seat_supply})", "pct"), ("bookings_per_run", "IF({simulated_runs}=0,\"\",{total_bookings}/{simulated_runs})", "num1"),
            ("passengers_per_run", "IF({simulated_runs}=0,\"\",{total_passengers}/{simulated_runs})", "num1"), ("otp", "IF({runs_with_delay}=0,\"\",{on_time_runs}/{runs_with_delay})", "pct"),
            ("avg_delay", "IF({runs_with_delay}=0,\"\",{delay_sum_pos}/{runs_with_delay})", "num1")]
    for j, (k, _, _) in enumerate(calc):
        L[k] = CL(len(vals) + j)
    L["E"] = L["total_passengers"]
    L["bookings_growth"] = CL(len(vals) + len(calc)); L["bpr_growth"] = CL(len(vals) + len(calc) + 1)
    HR, F0 = 4, 5
    n = len(mo); FL = F0 + n - 1; TR = FL + 1
    heads = vals + [k for k, _, _ in calc] + ["bookings_growth", "bookings_per_run_growth"]
    for c, h in enumerate(heads):
        ws.write(HR, c, h + (" (formula)" if c >= len(vals) else ""), b.hdr)
    fmts = dict(pct=fmc["pct"], money=fmc["money"], num2=fmc["num2"], num1=b.f(num_format="#,##0.0", bg_color="#EAF1FB"))
    def sub(t, row):
        out = t
        for k, colname in L.items():
            out = out.replace("{" + k + "}", f"{colname}{row + 1}")
        return out
    for i, r in mo.iterrows():
        x = F0 + i
        ws.write_string(x, 0, r.journey_month)
        for c, k in enumerate(vals[1:], start=1):
            ws.write_number(x, c, float(r[k]), fm["money"] if k in ("gross_value", "refund_passenger", "refund_system", "retained_charges", "delay_sum_pos", "seat_supply") and k != "seat_supply" else fm["int"])
        for j, (k, t, f) in enumerate(calc):
            b.formula(ws, x, len(vals) + j, "=" + sub(t, x), fmts[f])
        gcol = len(vals) + len(calc)
        if i == 0:
            ws.write_string(x, gcol, ""); ws.write_string(x, gcol + 1, "")
        else:
            b.formula(ws, x, gcol, f'=IF(N({L["total_bookings"]}{x})=0,"",{L["total_bookings"]}{x + 1}/{L["total_bookings"]}{x}-1)', fmc["pct"])
            b.formula(ws, x, gcol + 1, f'=IF(N({L["bookings_per_run"]}{x})=0,"",{L["bookings_per_run"]}{x + 1}/{L["bookings_per_run"]}{x}-1)', fmc["pct"])
    ws.write_string(TR, 0, "TOTAL / ratio of sums", b.f(bold=True, top=1))
    for c, k in enumerate(vals[1:], start=1):
        b.formula(ws, TR, c, f"=SUM({CL(c)}{F0 + 1}:{CL(c)}{FL + 1})", b.f(bold=True, top=1, num_format="#,##0.00" if k in ("gross_value", "refund_passenger", "refund_system", "retained_charges", "delay_sum_pos") else "#,##0"))
    for j, (k, t, f) in enumerate(calc):
        b.formula(ws, TR, len(vals) + j, "=" + sub(t, TR), b.f(bold=True, top=1, num_format={"pct": "0.0%", "money": "#,##0.00", "num2": "#,##0.00", "num1": "#,##0.0"}[f]))
    ws.freeze_panes(F0, 1); ws.set_column(0, 0, 22); ws.set_column(1, len(heads), 14); ws.set_row(HR, 45)
    M_RANGE = lambda key: f"Monthly_Aggregates!${L[key]}${F0 + 1}:${L[key]}${FL + 1}"
    TOTALCELL = lambda key: f"Monthly_Aggregates!${L[key]}${TR + 1}"
    ws.write(TR + 2, 0, "Growth columns compare each month with the previous month. Because 32 runs are simulated every month, growth in raw bookings mainly reflects demand per run and which trains were sampled, not network growth. Read 'bookings_per_run_growth' alongside it.", b.note)

    # ------------------------------------------------------------------ KPI_Calc
    ws = W["KPI_Calc"]
    ws.write(0, 0, "KPI reconciliation: Excel formulas on the sample versus the Python reference", b.title)
    ws.merge_range(1, 0, 1, 9, "SYNTHETIC DATA. Excel column = formulas on the analytical sample sheets (48 of 768 simulated runs; balanced by journey month, run-complete). Python (same sample) = independent reference on the same rows. Python (full dataset) = all 768 simulated runs, shown so the sample can be compared with the full dataset; sample results should not be generalised.", b.note)
    ws.set_row(1, 44)
    heads = ["KPI", "Excel value (formula)", "Python (same sample)", "|Difference|", "Tolerance", "Status", "Python (full dataset)", "Unit", "Definition", "Denominator"]
    for c, h in enumerate(heads):
        ws.write(3, c, h, b.hdr)
    rowof = {k: 4 + i for i, k in enumerate(CALC_KEYS)}
    A = lambda k: f"$B${rowof[k] + 1}"
    r_ = lambda sheet, col, last: f"{sheet}!${col}$2:${col}${last}"
    BKS, BKF, BKC = r_("Data_Bookings", "I", NB), r_("Data_Bookings", "J", NB), r_("Data_Bookings", "F", NB)
    PSI, PSF, PSS = r_("Data_Passengers", "H", NP), r_("Data_Passengers", "I", NP), r_("Data_Passengers", "L", NP)
    EVK, EVT, EVC = r_("Data_Cancellations", "K", NE), r_("Data_Cancellations", "F", NE), r_("Data_Cancellations", "J", NE)
    CRS = r_("Data_ClassRuns", "I", NC)
    FRM = {
        "total_bookings": f"=COUNTA({r_('Data_Bookings', 'A', NB)})", "total_passengers": f"=COUNTA({r_('Data_Passengers', 'A', NP)})",
        "confirmed_bookings": f'=COUNTIF({BKS},"Confirmed")', "mixed_bookings": f'=COUNTIF({BKS},"Mixed")', "cancelled_bookings": f'=COUNTIF({BKS},"Cancelled")',
        "cancelled_passengers": f'=COUNTIF({PSF},"Cancelled")', "passenger_cancellation_rate": f'=IF({A("total_passengers")}=0,"",{A("cancelled_passengers")}/{A("total_passengers")})',
        "booking_cancellation_rate": f'=IF({A("total_bookings")}=0,"",{A("cancelled_bookings")}/{A("total_bookings")})', "gross_value": f"=SUM({BKF})",
        "refund_passenger": f'=SUMIFS({EVK},{EVT},"Passenger")', "refund_system": f'=SUMIFS({EVK},{EVT},"System")', "refund_total": f"=SUM({EVK})",
        "retained_charges": f"=SUM({EVC})", "net_value": f"={A('gross_value')}-{A('refund_total')}",
        "avg_fare_per_passenger": f'=IF({A("total_passengers")}=0,"",{A("gross_value")}/{A("total_passengers")})', "avg_fare_per_booking": f'=IF({A("total_bookings")}=0,"",{A("gross_value")}/{A("total_bookings")})',
        "wl_demand": f'=COUNTIF({PSI},"Waitlisted")', "wl_cleared": f'=COUNTIFS({PSI},"Waitlisted",{PSF},"Confirmed")+COUNTIFS({PSI},"Waitlisted",{PSF},"RAC")',
        "wl_clearance_rate": f'=IF({A("wl_demand")}=0,"",{A("wl_cleared")}/{A("wl_demand")})', "wl_uncleared": f'=COUNTIF({PSF},"Waitlisted")',
        "confirmed_pax": f'=COUNTIF({PSF},"Confirmed")', "rac_pax": f'=COUNTIF({PSF},"RAC")', "seat_supply": f"=SUM({CRS})", "booked_seats": f"=SUM({PSS})",
        "occupancy": f'=IF({A("seat_supply")}=0,"",{A("booked_seats")}/{A("seat_supply")})', "confirmed_occupancy": f'=IF({A("seat_supply")}=0,"",{A("confirmed_pax")}/{A("seat_supply")})',
        "waitlist_pressure": f'=IF({A("seat_supply")}=0,"",{A("wl_uncleared")}/{A("seat_supply")})', "simulated_runs": f"=COUNTA({r_('Data_Runs', 'A', NR)})",
        "bookings_per_run": f'=IF({A("simulated_runs")}=0,"",{A("total_bookings")}/{A("simulated_runs")})', "passengers_per_run": f'=IF({A("simulated_runs")}=0,"",{A("total_passengers")}/{A("simulated_runs")})',
        "runs_with_delay": f"=SUM({r_('Data_Runs', 'J', NR)})", "on_time_runs": f"=SUM({r_('Data_Runs', 'K', NR)})", "otp": f'=IF({A("runs_with_delay")}=0,"",{A("on_time_runs")}/{A("runs_with_delay")})',
        "delay_sum_pos": f"=SUM({r_('Data_Runs', 'L', NR)})", "avg_delay": f'=IF({A("runs_with_delay")}=0,"",{A("delay_sum_pos")}/{A("runs_with_delay")})', "delayed_runs": f"=SUM({r_('Data_Runs', 'M', NR)})"}
    kfmt = lambda u: {"share": "0.00%", "INR": "#,##0.00", "count": "#,##0", "seat-equivalents": "#,##0.00", "minutes": "#,##0.00", "bookings/run": "#,##0.00", "passengers/run": "#,##0.00"}.get(u, "#,##0.00")
    for k in CALC_KEYS:
        x = rowof[k]; u = UNIT.get(k, "count")
        ws.write_string(x, 0, k)
        b.formula(ws, x, 1, FRM[k], b.f(num_format=kfmt(u), bg_color="#EAF1FB"))
        ws.write_number(x, 2, float(D["ref_smp"][k]), b.f(num_format=kfmt(u)))
        b.formula(ws, x, 3, f'=IF(ISNUMBER(B{x + 1}),ABS(B{x + 1}-C{x + 1}),"")', b.f(num_format="0.000000"))
        tol = TOL.get(u, 0.0001 if u in ("seat-equivalents", "minutes", "bookings/run", "passengers/run") else 0.0)
        ws.write_number(x, 4, tol, b.f(num_format="0.00000"))
        b.formula(ws, x, 5, f'=IF(D{x + 1}<=E{x + 1},"PASS","FAIL")', b.f(bold=True))
        ws.write_number(x, 6, float(D["ref_full"][k]), b.f(num_format=kfmt(u)))
        ws.write_string(x, 7, u); ws.write_string(x, 8, KPI_DEFS[k][0]); ws.write_string(x, 9, KPI_DEFS[k][1])
    last = 4 + len(CALC_KEYS)
    ws.conditional_format(4, 5, last - 1, 5, {"type": "cell", "criteria": "==", "value": '"PASS"', "format": b.f(bg_color="#C6EFCE", font_color="#006100")})
    ws.conditional_format(4, 5, last - 1, 5, {"type": "cell", "criteria": "==", "value": '"FAIL"', "format": b.f(bg_color="#FFC7CE", font_color="#9C0006")})
    ws.set_column(0, 0, 30); ws.set_column(1, 6, 16); ws.set_column(7, 7, 16); ws.set_column(8, 8, 80); ws.set_column(9, 9, 42); ws.freeze_panes(4, 1)
    ws.write(last + 1, 0, "Tolerance follows docs/KPI_definitions.md section 1.8: counts exact, currency 2 decimals, ratios 4 decimals.", b.note)
    KC = lambda k: f"KPI_Calc!$B${rowof[k] + 1}"

    # ------------------------------------------------------------------ Dashboard
    ws = W["Dashboard"]
    ws.write(0, 0, "IRCTC-inspired Booking Analytics: KPI Dashboard (synthetic sampled simulation)", b.title)
    ws.merge_range(1, 0, 1, 13, xc.SYNTHETIC_BANNER, b.warn); ws.set_row(1, 32)
    ws.merge_range(2, 0, 2, 13, "Cards below use the balanced, run-complete analytical sample (48 of 768 simulated runs; balanced by journey month only) and respond to the class filter. Time-series charts use the FULL cleaned dataset (Monthly_Aggregates). " + xc.PER_RUN_NOTE, b.note); ws.set_row(2, 42)
    ws.write(4, 1, "Travel class filter (cards):", b.f(bold=True)); ws.write_string(4, 2, "All", fm["inp"]); ws.write_string(4, 3, "The analytical sample has no 1A class-runs and no Premium trains: choosing 1A shows zeros or blanks.", b.f(italic=True, font_color="#595959"))
    ws.data_validation(4, 2, 4, 2, {"validate": "list", "source": ["All"] + CLASSES, "input_title": "Travel class", "input_message": "Choose All or one class"})
    ws.write(5, 1, "Filter criterion used by formulas"); b.formula(ws, 5, 2, '=IF(C5="All","*",C5)', fmc["text"])
    for c, h in enumerate(["KPI (analytical sample)", "Value", "Numerator", "Denominator (documented)"], start=1):
        ws.write(7, c, h, b.hdr)
    cr = "$C$6"
    bcls, pcls = r_("Data_Bookings", "F", NB), r_("Data_Passengers", "D", NP)
    ccls, kcls = r_("Data_Cancellations", "D", NE), r_("Data_ClassRuns", "E", NC)
    cards = [
        ("Total bookings", f"=COUNTIFS({bcls},{cr})", None, None, "count", "int"),
        ("Total passengers", f"=COUNTIFS({pcls},{cr})", None, None, "count", "int"),
        ("Fully confirmed bookings (all passengers Confirmed)", f'=COUNTIFS({bcls},{cr},{BKS},"Confirmed")', None, None, "count", "int"),
        ("Mixed-status bookings (reported separately)", f'=COUNTIFS({bcls},{cr},{BKS},"Mixed")', None, None, "count", "int"),
        ("Cancellation rate (passenger-based)", None, f'=COUNTIFS({pcls},{cr},{PSF},"Cancelled")', f"=COUNTIFS({pcls},{cr})", "Total passengers, all final statuses", "pct"),
        ("Booking cancellation rate (companion)", None, f'=COUNTIFS({bcls},{cr},{BKS},"Cancelled")', f"=COUNTIFS({bcls},{cr})", "Total bookings", "pct"),
        ("Waiting-list demand (initially waitlisted passengers)", f'=COUNTIFS({pcls},{cr},{PSI},"Waitlisted")', None, None, "count", "int"),
        ("Waitlist clearance rate", None, f'=COUNTIFS({pcls},{cr},{PSI},"Waitlisted",{PSF},"Confirmed")+COUNTIFS({pcls},{cr},{PSI},"Waitlisted",{PSF},"RAC")', f'=COUNTIFS({pcls},{cr},{PSI},"Waitlisted")', "Initially waitlisted passengers", "pct"),
        ("Uncleared waitlist passengers (refunded by system)", f'=COUNTIFS({pcls},{cr},{PSF},"Waitlisted")', None, None, "count", "int"),
        ("Seat occupancy %", None, f"=SUMIFS({PSS},{pcls},{cr})", f"=SUMIFS({CRS},{kcls},{cr})", "Available seats, same train-class runs", "pct"),
        ("Waitlist pressure % (not part of occupancy)", None, f'=COUNTIFS({pcls},{cr},{PSF},"Waitlisted")', f"=SUMIFS({CRS},{kcls},{cr})", "Available seats", "pct"),
        ("Gross booking value (INR, before refunds)", f"=SUMIFS({BKF},{bcls},{cr})", None, None, "n/a", "money"),
        ("Refund amount (INR)", f"=SUMIFS({EVK},{ccls},{cr})", None, None, "n/a", "money"),
        ("Net booking value (INR)", "NET", None, None, "Gross minus refunds", "money"),
        ("Average fare per passenger (INR)", None, f"=SUMIFS({BKF},{bcls},{cr})", f"=COUNTIFS({pcls},{cr})", "Total passengers", "money"),
    ]
    for i, (lab, val, num, den, dtxt, f) in enumerate(cards):
        x = 8 + i
        ws.write_string(x, 1, lab)
        cf = {"int": b.f(num_format="#,##0", bold=True, font_size=12, bg_color="#EAF1FB"), "pct": b.f(num_format="0.0%", bold=True, font_size=12, bg_color="#EAF1FB"),
              "money": b.f(num_format="#,##0", bold=True, font_size=12, bg_color="#EAF1FB")}[f]
        if val == "NET":
            b.formula(ws, x, 2, f"=C{9 + 11}-C{9 + 12}", cf)
        elif val:
            b.formula(ws, x, 2, val, cf)
        else:
            b.formula(ws, x, 3, num, fmc["num2"]); b.formula(ws, x, 4, den, fmc["num2"]); b.formula(ws, x, 2, f'=IF(E{x + 1}=0,"",D{x + 1}/E{x + 1})', cf)
        if not val or val == "NET":
            ws.write_string(x, 5 if False else 5, dtxt)
        else:
            ws.write_string(x, 5, "")
    # fix header positions for the cards table: KPI in B, value in C, numerator D, denominator E, note F
    ws.write(7, 1, "KPI (analytical sample)", b.hdr); ws.write(7, 2, "Value", b.hdr); ws.write(7, 3, "Numerator", b.hdr); ws.write(7, 4, "Denominator", b.hdr); ws.write(7, 5, "Denominator definition", b.hdr)
    x0 = 8 + len(cards) + 2
    ws.write(x0 - 1, 1, "Passenger final status by travel class (sample), chart source", b.f(bold=True))
    ws.write(x0, 1, "Class", b.hdr)
    for j, s in enumerate(STATUSES):
        ws.write(x0, 2 + j, s, b.hdr)
    for i, c in enumerate(CLASSES):
        ws.write_string(x0 + 1 + i, 1, c)
        for j, s in enumerate(STATUSES):
            b.formula(ws, x0 + 1 + i, 2 + j, f'=COUNTIFS({r_("Data_Passengers", "D", NP)},$B{x0 + 2 + i},{PSF},"{s}")', fmc["int"])
    ws.set_column(0, 0, 3); ws.set_column(1, 1, 52); ws.set_column(2, 4, 16); ws.set_column(5, 5, 38); ws.set_column(6, 14, 10)
    ws.conditional_format(8, 2, 8 + len(cards) - 1, 2, {"type": "no_blanks", "format": b.f(font_color="#1F3864")})
    # charts
    ch = wb.add_chart({"type": "line"})
    ch.add_series({"name": "Bookings per simulated run", "categories": M_RANGE("journey_month"), "values": M_RANGE("bookings_per_run"), "line": {"color": "#2E75B6"}})
    ch.set_title({"name": "Bookings per simulated run by journey month (sampled simulation)", "name_font": {"size": 10}}); ch.set_legend({"none": True}); ch.set_size({"width": 560, "height": 260})
    ch.set_x_axis({"num_font": {"rotation": -45, "size": 8}}); ch.set_y_axis({"name": "bookings per run"}); ws.insert_chart(3 + 5, 7, ch)
    ch = wb.add_chart({"type": "line"})
    ch.add_series({"name": "Seat occupancy %", "categories": M_RANGE("journey_month"), "values": M_RANGE("occupancy"), "line": {"color": "#548235"}})
    ch.add_series({"name": "Waitlist pressure %", "categories": M_RANGE("journey_month"), "values": M_RANGE("waitlist_pressure"), "line": {"color": "#C00000"}})
    ch.set_title({"name": "Occupancy and waitlist pressure by month (full dataset, synthetic, simulated capacity)", "name_font": {"size": 10}}); ch.set_size({"width": 560, "height": 260})
    ch.set_x_axis({"num_font": {"rotation": -45, "size": 8}}); ch.set_y_axis({"num_format": "0%"}); ch.set_legend({"position": "bottom"}); ws.insert_chart(3 + 5 + 14, 7, ch)
    ch = wb.add_chart({"type": "column", "subtype": "stacked"})
    for j, (s, colr) in enumerate(zip(STATUSES, ["#548235", "#BF8F00", "#C00000", "#7F7F7F"])):
        ch.add_series({"name": s, "categories": f"=Dashboard!$B${x0 + 2}:$B${x0 + 1 + len(CLASSES)}", "values": f"=Dashboard!${CL(2 + j)}${x0 + 2}:${CL(2 + j)}${x0 + 1 + len(CLASSES)}", "fill": {"color": colr}})
    ch.set_title({"name": "Passenger final status by class (analytical sample, synthetic)", "name_font": {"size": 10}}); ch.set_size({"width": 560, "height": 260}); ch.set_legend({"position": "bottom"}); ws.insert_chart(3 + 5 + 28, 7, ch)
    ch = wb.add_chart({"type": "column", "subtype": "stacked"})
    ch.add_series({"name": "Passenger cancellations", "categories": M_RANGE("journey_month"), "values": M_RANGE("refund_passenger"), "fill": {"color": "#2E75B6"}})
    ch.add_series({"name": "System auto-refunds (uncleared waitlist)", "categories": M_RANGE("journey_month"), "values": M_RANGE("refund_system"), "fill": {"color": "#ED7D31"}})
    ch.set_title({"name": "Refunds by event type, INR (full dataset, synthetic)", "name_font": {"size": 10}}); ch.set_size({"width": 560, "height": 260})
    ch.set_x_axis({"num_font": {"rotation": -45, "size": 8}}); ch.set_legend({"position": "bottom"}); ws.insert_chart(3 + 5 + 42, 7, ch)

    # ------------------------------------------------------------------ Cancellation_Refund
    ws = W["Cancellation_Refund"]
    ws.write(0, 0, "Cancellation and refund analysis", b.title)
    ws.merge_range(1, 0, 1, 9, xc.SYNTHETIC_BANNER, b.warn); ws.set_row(1, 32)
    ws.merge_range(2, 0, 2, 9, "Tables 1 to 3 use the analytical sample (48 runs, balanced by journey month). Table 4 uses the full cleaned dataset. Cancellation Rate is passenger-based (denominator: total passengers); booking-based rate is the companion. System auto-refunds are not passenger cancellations. Findings describe the synthetic data only; the cancellation-versus-lead-time pattern was built into the generator.", b.note); ws.set_row(2, 44)
    ws.write(4, 0, "1. Cancellation by booking lead time (sample)", b.f(bold=True, font_size=11))
    for c, h in enumerate(["Lead bucket", "Passengers", "Cancelled passengers", "Passenger cancellation rate", "Bookings", "Cancelled bookings", "Booking cancellation rate"]):
        ws.write(5, c, h, b.hdr)
    pb, bb = r_("Data_Passengers", "F", NP), r_("Data_Bookings", "N", NB)
    for i, lab in enumerate(kpi.LEAD_LABELS):
        x = 6 + i; e = x + 1
        ws.write_string(x, 0, lab)
        b.formula(ws, x, 1, f"=COUNTIFS({pb},A{e})", fmc["int"]); b.formula(ws, x, 2, f'=COUNTIFS({pb},A{e},{PSF},"Cancelled")', fmc["int"])
        b.formula(ws, x, 3, f'=IF(B{e}=0,"",C{e}/B{e})', fmc["pct"]); b.formula(ws, x, 4, f"=COUNTIFS({bb},A{e})", fmc["int"])
        b.formula(ws, x, 5, f'=COUNTIFS({bb},A{e},{BKS},"Cancelled")', fmc["int"]); b.formula(ws, x, 6, f'=IF(E{e}=0,"",F{e}/E{e})', fmc["pct"])
    ws.write_string(11, 0, "All buckets", b.f(bold=True, top=1))
    for c in (1, 2, 4, 5):
        b.formula(ws, 11, c, f"=SUM({CL(c)}7:{CL(c)}11)", b.f(bold=True, top=1, num_format="#,##0"))
    b.formula(ws, 11, 3, '=IF(B12=0,"",C12/B12)', b.f(bold=True, top=1, num_format="0.0%")); b.formula(ws, 11, 6, '=IF(E12=0,"",F12/E12)', b.f(bold=True, top=1, num_format="0.0%"))
    ws.write(14, 0, "2. Cancellation and refunds by travel class (sample)", b.f(bold=True, font_size=11))
    for c, h in enumerate(["Class", "Passengers", "Cancelled passengers", "Passenger cancellation rate", "Uncleared waitlist passengers", "Refunds: Passenger events", "Refunds: System events", "Charges retained", "Charges as % of (refunds + charges)"]):
        ws.write(15, c, h, b.hdr)
    for i, cl_ in enumerate(CLASSES):
        x = 16 + i; e = x + 1
        ws.write_string(x, 0, cl_)
        b.formula(ws, x, 1, f"=COUNTIFS({pcls},A{e})", fmc["int"]); b.formula(ws, x, 2, f'=COUNTIFS({pcls},A{e},{PSF},"Cancelled")', fmc["int"])
        b.formula(ws, x, 3, f'=IF(B{e}=0,"",C{e}/B{e})', fmc["pct"]); b.formula(ws, x, 4, f'=COUNTIFS({pcls},A{e},{PSF},"Waitlisted")', fmc["int"])
        b.formula(ws, x, 5, f'=SUMIFS({EVK},{ccls},A{e},{EVT},"Passenger")', fmc["money"]); b.formula(ws, x, 6, f'=SUMIFS({EVK},{ccls},A{e},{EVT},"System")', fmc["money"])
        b.formula(ws, x, 7, f"=SUMIFS({EVC},{ccls},A{e})", fmc["money"]); b.formula(ws, x, 8, f'=IF(F{e}+G{e}+H{e}=0,"",H{e}/(F{e}+G{e}+H{e}))', fmc["pct"])
    ws.write_string(22, 0, "All classes", b.f(bold=True, top=1))
    for c in (1, 2, 4, 5, 6, 7):
        b.formula(ws, 22, c, f"=SUM({CL(c)}17:{CL(c)}22)", b.f(bold=True, top=1, num_format="#,##0.00" if c >= 5 else "#,##0"))
    b.formula(ws, 22, 3, '=IF(B23=0,"",C23/B23)', b.f(bold=True, top=1, num_format="0.0%")); b.formula(ws, 22, 8, '=IF(F23+G23+H23=0,"",H23/(F23+G23+H23))', b.f(bold=True, top=1, num_format="0.0%"))
    ws.write(25, 0, "3. Refund events by type and status at cancellation (sample)", b.f(bold=True, font_size=11))
    for c, h in enumerate(["Event type", "Status at cancellation", "Events", "Passengers covered", "Original fare (INR)", "Charge retained (INR)", "Refund (INR)", "Charge % of original fare"]):
        ws.write(26, c, h, b.hdr)
    ecT, ecS, ecN, ecP, ecO = EVT, r_("Data_Cancellations", "G", NE), r_("Data_Cancellations", "A", NE), r_("Data_Cancellations", "H", NE), r_("Data_Cancellations", "I", NE)
    for i, (t, s) in enumerate([("Passenger", "Confirmed"), ("Passenger", "RAC"), ("Passenger", "Waitlisted"), ("System", "Waitlisted")]):
        x = 27 + i; e = x + 1
        ws.write_string(x, 0, t); ws.write_string(x, 1, s)
        b.formula(ws, x, 2, f"=COUNTIFS({ecT},A{e},{ecS},B{e})", fmc["int"]); b.formula(ws, x, 3, f"=SUMIFS({ecP},{ecT},A{e},{ecS},B{e})", fmc["int"])
        b.formula(ws, x, 4, f"=SUMIFS({ecO},{ecT},A{e},{ecS},B{e})", fmc["money"]); b.formula(ws, x, 5, f"=SUMIFS({EVC},{ecT},A{e},{ecS},B{e})", fmc["money"])
        b.formula(ws, x, 6, f"=SUMIFS({EVK},{ecT},A{e},{ecS},B{e})", fmc["money"]); b.formula(ws, x, 7, f'=IF(E{e}=0,"",F{e}/E{e})', fmc["pct"])
    ws.write_string(31, 0, "All events", b.f(bold=True, top=1)); ws.write_string(31, 1, "", b.f(top=1))
    for c in (2, 3, 4, 5, 6):
        b.formula(ws, 31, c, f"=SUM({CL(c)}28:{CL(c)}31)", b.f(bold=True, top=1, num_format="#,##0.00" if c >= 4 else "#,##0"))
    b.formula(ws, 31, 7, '=IF(E32=0,"",F32/E32)', b.f(bold=True, top=1, num_format="0.0%"))
    ws.write(34, 0, "4. Monthly refunds (full cleaned dataset, executive view)", b.f(bold=True, font_size=11))
    for c, h in enumerate(["Journey month", "Gross booking value", "Refunds: Passenger events", "Refunds: System events", "Refund amount", "Net booking value", "Refund % of gross", "System share of refunds", "Charges retained"]):
        ws.write(35, c, h, b.hdr)
    for i in range(n):
        x = 36 + i; e = x + 1; m = F0 + i + 1
        b.formula(ws, x, 0, f"=Monthly_Aggregates!A{m}", fmc["text"]); b.formula(ws, x, 1, f"=Monthly_Aggregates!{L['gross_value']}{m}", fmc["money"])
        b.formula(ws, x, 2, f"=Monthly_Aggregates!{L['refund_passenger']}{m}", fmc["money"]); b.formula(ws, x, 3, f"=Monthly_Aggregates!{L['refund_system']}{m}", fmc["money"])
        b.formula(ws, x, 4, f"=C{e}+D{e}", fmc["money"]); b.formula(ws, x, 5, f"=B{e}-E{e}", fmc["money"]); b.formula(ws, x, 6, f'=IF(B{e}=0,"",E{e}/B{e})', fmc["pct"])
        b.formula(ws, x, 7, f'=IF(E{e}=0,"",D{e}/E{e})', fmc["pct"]); b.formula(ws, x, 8, f"=Monthly_Aggregates!{L['retained_charges']}{m}", fmc["money"])
    ws.set_column(0, 0, 24); ws.set_column(1, 8, 20); ws.set_row(5, 42); ws.set_row(15, 42); ws.set_row(26, 30); ws.set_row(35, 30)
    ch = wb.add_chart({"type": "column"})
    ch.add_series({"name": "Passenger cancellation rate", "categories": "=Cancellation_Refund!$A$7:$A$11", "values": "=Cancellation_Refund!$D$7:$D$11", "fill": {"color": "#C00000"}, "data_labels": {"value": True, "num_format": "0.0%"}})
    ch.set_title({"name": "Passenger cancellation rate by lead time (analytical sample, synthetic)", "name_font": {"size": 10}}); ch.set_legend({"none": True}); ch.set_y_axis({"num_format": "0%"}); ch.set_size({"width": 520, "height": 270})
    ws.insert_chart(4, 10, ch)
    ch = wb.add_chart({"type": "column", "subtype": "stacked"})
    ch.add_series({"name": "Passenger events", "categories": "=Cancellation_Refund!$A$37:$A$60", "values": "=Cancellation_Refund!$C$37:$C$60", "fill": {"color": "#2E75B6"}})
    ch.add_series({"name": "System auto-refunds", "categories": "=Cancellation_Refund!$A$37:$A$60", "values": "=Cancellation_Refund!$D$37:$D$60", "fill": {"color": "#ED7D31"}})
    ch.set_title({"name": "Monthly refunds by event type, INR (full dataset, synthetic)", "name_font": {"size": 10}}); ch.set_x_axis({"num_font": {"rotation": -45, "size": 8}}); ch.set_size({"width": 520, "height": 270}); ch.set_legend({"position": "bottom"})
    ws.insert_chart(20, 10, ch)

    # ------------------------------------------------------------------ Occupancy_Demand
    ws = W["Occupancy_Demand"]
    ws.write(0, 0, "Train occupancy and demand analysis", b.title)
    ws.merge_range(1, 0, 1, 10, xc.SYNTHETIC_BANNER, b.warn); ws.set_row(1, 32)
    ws.merge_range(2, 0, 2, 10, "Occupancy = (Confirmed + 0.5 x RAC passengers) / available seats, per train-class run, on final statuses. Waitlisted passengers hold no seat and appear as waitlist pressure. The RAC weight is a configurable simulation assumption. Whole-journey occupancy only; intermediate-segment occupancy is out of scope. " + xc.PER_RUN_NOTE, b.note); ws.set_row(2, 56)
    ws.write(4, 0, "1. Occupancy and demand by travel class (sample class-runs)", b.f(bold=True, font_size=11))
    for c, h in enumerate(["Class", "Class-runs", "Seats (capacity)", "Booked seats", "Occupancy %", "Confirmed occupancy %", "RAC occupancy %", "Waitlist pressure %", "Initially waitlisted passengers", "Bookings per class-run", "Passengers per class-run"]):
        ws.write(5, c, h, b.hdr)
    cc = lambda col: r_("Data_ClassRuns", col, NC)
    for i, c_ in enumerate(CLASSES):
        x = 6 + i; e = x + 1
        ws.write_string(x, 0, c_)
        b.formula(ws, x, 1, f"=COUNTIF({cc('E')},A{e})", fmc["int"]); b.formula(ws, x, 2, f"=SUMIFS({cc('I')},{cc('E')},A{e})", fmc["int"])
        b.formula(ws, x, 3, f"=SUMIFS({cc('S')},{cc('E')},A{e})", fmc["num2"]); b.formula(ws, x, 4, f'=IF(C{e}=0,"",D{e}/C{e})', fmc["pct"])
        b.formula(ws, x, 5, f'=IF(C{e}=0,"",SUMIFS({cc("L")},{cc("E")},A{e})/C{e})', fmc["pct"]); b.formula(ws, x, 6, f'=IF(C{e}=0,"",{RACW}*SUMIFS({cc("M")},{cc("E")},A{e})/C{e})', fmc["pct"])
        b.formula(ws, x, 7, f'=IF(C{e}=0,"",SUMIFS({cc("N")},{cc("E")},A{e})/C{e})', fmc["pct"]); b.formula(ws, x, 8, f"=SUMIFS({cc('P')},{cc('E')},A{e})", fmc["int"])
        b.formula(ws, x, 9, f'=IF(B{e}=0,"",SUMIFS({cc("R")},{cc("E")},A{e})/B{e})', fmc["num2"]); b.formula(ws, x, 10, f'=IF(B{e}=0,"",SUMIFS({cc("Q")},{cc("E")},A{e})/B{e})', fmc["num2"])
    ws.write_string(12, 0, "All classes", b.f(bold=True, top=1))
    for c in (1, 2, 3, 8):
        b.formula(ws, 12, c, f"=SUM({CL(c)}7:{CL(c)}12)", b.f(bold=True, top=1, num_format="#,##0.00" if c == 3 else "#,##0"))
    b.formula(ws, 12, 4, '=IF(C13=0,"",D13/C13)', b.f(bold=True, top=1, num_format="0.0%"))
    b.formula(ws, 12, 5, f'=IF(C13=0,"",SUM({cc("L")})/C13)', b.f(bold=True, top=1, num_format="0.0%")); b.formula(ws, 12, 6, f'=IF(C13=0,"",{RACW}*SUM({cc("M")})/C13)', b.f(bold=True, top=1, num_format="0.0%"))
    b.formula(ws, 12, 7, f'=IF(C13=0,"",SUM({cc("N")})/C13)', b.f(bold=True, top=1, num_format="0.0%"))
    b.formula(ws, 12, 9, f'=IF(B13=0,"",SUM({cc("R")})/B13)', b.f(bold=True, top=1, num_format="#,##0.00")); b.formula(ws, 12, 10, f'=IF(B13=0,"",SUM({cc("Q")})/B13)', b.f(bold=True, top=1, num_format="#,##0.00"))
    ws.conditional_format(6, 4, 11, 4, {"type": "3_color_scale", "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"})
    ws.write(15, 0, "2. Distribution of class-run occupancy (sample)", b.f(bold=True, font_size=11))
    for c, h in enumerate(["Occupancy band", "Class-runs", "Share of class-runs"]):
        ws.write(16, c, h, b.hdr)
    bands = [("Below 50%", f'=COUNTIF({cc("T")},"<0.5")'), ("50% to below 75%", f'=COUNTIFS({cc("T")},">=0.5",{cc("T")},"<0.75")'),
             ("75% to below 95%", f'=COUNTIFS({cc("T")},">=0.75",{cc("T")},"<0.95")'), ("95% and above", f'=COUNTIF({cc("T")},">=0.95")')]
    for i, (lab, fml) in enumerate(bands):
        x = 17 + i
        ws.write_string(x, 0, lab); b.formula(ws, x, 1, fml, fmc["int"]); b.formula(ws, x, 2, f'=IF(SUM($B$18:$B$21)=0,"",B{x + 1}/SUM($B$18:$B$21))', fmc["pct"])
    ws.write(23, 0, "3. Per-run and capacity-normalised demand by month (full cleaned dataset)", b.f(bold=True, font_size=11))
    for c, h in enumerate(["Journey month", "Simulated runs", "Bookings per run", "Passengers per run", "Occupancy %", "Waitlist pressure %", "Waiting-list demand per run", "Passenger cancellation rate"]):
        ws.write(24, c, h, b.hdr)
    for i in range(n):
        x = 25 + i; m = F0 + i + 1
        b.formula(ws, x, 0, f"=Monthly_Aggregates!A{m}", fmc["text"]); b.formula(ws, x, 1, f"=Monthly_Aggregates!{L['simulated_runs']}{m}", fmc["int"])
        b.formula(ws, x, 2, f"=Monthly_Aggregates!{L['bookings_per_run']}{m}", fmc["num2"]); b.formula(ws, x, 3, f"=Monthly_Aggregates!{L['passengers_per_run']}{m}", fmc["num2"])
        b.formula(ws, x, 4, f"=Monthly_Aggregates!{L['occupancy']}{m}", fmc["pct"]); b.formula(ws, x, 5, f"=Monthly_Aggregates!{L['waitlist_pressure']}{m}", fmc["pct"])
        b.formula(ws, x, 6, f"=Monthly_Aggregates!{L['wl_demand']}{m}/Monthly_Aggregates!{L['simulated_runs']}{m}", fmc["num2"]); b.formula(ws, x, 7, f"=Monthly_Aggregates!{L['passenger_cancellation_rate']}{m}", fmc["pct"])
    ws.set_column(0, 0, 24); ws.set_column(1, 10, 17); ws.set_row(5, 42); ws.set_row(24, 30)
    ch = wb.add_chart({"type": "column"})
    ch.add_series({"name": "Occupancy %", "categories": "=Occupancy_Demand!$A$7:$A$12", "values": "=Occupancy_Demand!$E$7:$E$12", "fill": {"color": "#548235"}, "data_labels": {"value": True, "num_format": "0%"}})
    ch.add_series({"name": "Waitlist pressure %", "categories": "=Occupancy_Demand!$A$7:$A$12", "values": "=Occupancy_Demand!$H$7:$H$12", "fill": {"color": "#C00000"}})
    ch.set_title({"name": "Occupancy and waitlist pressure by class (analytical sample, synthetic, simulated capacity)", "name_font": {"size": 10}}); ch.set_y_axis({"num_format": "0%"}); ch.set_size({"width": 520, "height": 270}); ch.set_legend({"position": "bottom"})
    ws.insert_chart(4, 12, ch)
    ch = wb.add_chart({"type": "line"})
    ch.add_series({"name": "Passengers per simulated run", "categories": "=Occupancy_Demand!$A$26:$A$49", "values": "=Occupancy_Demand!$D$26:$D$49", "line": {"color": "#2E75B6"}})
    ch.set_title({"name": "Passengers per simulated run by month (full dataset, synthetic)", "name_font": {"size": 10}}); ch.set_x_axis({"num_font": {"rotation": -45, "size": 8}}); ch.set_legend({"none": True}); ch.set_size({"width": 520, "height": 270})
    ws.insert_chart(19, 12, ch)

    # ------------------------------------------------------------------ Validation
    ws = W["Validation"]
    ws.write(0, 0, "Workbook validation checks (formulas; all must read PASS)", b.title)
    xc.side_label(b, ws, 1, 0, "SYNTHETIC DATA. " + xc.SAMPLE_LABEL)
    for c, h in enumerate(["#", "Check", "Result (formula)"]):
        ws.write(2, c, h, b.hdr)
    refF = D["ref_full"]
    ratio_tot = TOTALCELL("occupancy")
    checks = [
        ("Data_Bookings rows equal the expected sample size", f"=COUNTA({r_('Data_Bookings', 'A', NB)})={len(bk)}"),
        ("Data_Passengers rows equal the expected sample size", f"=COUNTA({r_('Data_Passengers', 'A', NP)})={len(ps)}"),
        ("Data_Cancellations rows equal the expected sample size", f"=COUNTA({r_('Data_Cancellations', 'A', NE)})={len(ev)}"),
        ("Data_ClassRuns rows equal the expected sample size", f"=COUNTA({r_('Data_ClassRuns', 'A', NC)})={len(crf)}"),
        ("Data_Runs rows equal the expected sample size", f"=COUNTA({r_('Data_Runs', 'A', NR)})={len(ops)}"),
        ("BR-03: SUM(num_passengers) equals the number of passenger rows", f"=SUM({r_('Data_Bookings', 'H', NB)})=COUNTA({r_('Data_Passengers', 'A', NP)})"),
        ("BR-03: SUM(passenger fare) equals SUM(booking total_fare)", f"=ABS(SUM({r_('Data_Passengers', 'J', NP)})-SUM({BKF}))<0.005"),
        ("The four final statuses add up to total passengers", f'=COUNTIF({PSF},"Confirmed")+COUNTIF({PSF},"RAC")+COUNTIF({PSF},"Waitlisted")+COUNTIF({PSF},"Cancelled")=COUNTA({r_("Data_Passengers", "A", NP)})'),
        ("BR-11: original fare - charge - refund = 0 for every event", f"=SUMPRODUCT(ABS({r_('Data_Cancellations', 'L', NE)}))=0"),
        ("BR-08: no class-run occupancy above 100%", f"=MAX({cc('T')})<=1"),
        ("BR-08: confirmed passengers never exceed seats minus RAC berths", f"=SUMPRODUCT(--({cc('L')}>{cc('I')}-{cc('J')}))=0"),
        ("BR-09: total_seats = coaches x seats per coach for every class-run", f"=SUMPRODUCT(--({cc('I')}<>{cc('G')}*{cc('H')}))=0"),
        ("Every passenger belongs to a class-run in the sample", f"=SUM({cc('Q')})=COUNTA({r_('Data_Passengers', 'A', NP)})"),
        ("Lead-bucket formula agrees with the source bucket on every booking", f"=SUMPRODUCT(--({r_('Data_Bookings', 'N', NB)}<>{r_('Data_Bookings', 'O', NB)}))=0"),
        ("Journey-month formula agrees with the source month on every booking", f"=SUMPRODUCT(--({r_('Data_Bookings', 'L', NB)}<>{r_('Data_Bookings', 'P', NB)}))=0"),
        ("KPI_Calc: every Excel KPI equals the Python reference within tolerance", f'=COUNTIF(KPI_Calc!$F$5:$F${4 + len(CALC_KEYS)},"FAIL")=0'),
        ("KPI_Calc: no error values", f"=SUMPRODUCT(--ISERROR(KPI_Calc!$B$5:$B${4 + len(CALC_KEYS)}))=0"),
        ("Sample: gross - refunds = net booking value", f"=ABS({KC('gross_value')}-{KC('refund_total')}-{KC('net_value')})<0.005"),
        ("Monthly totals: bookings and passengers equal the full-dataset reference", f"=AND({TOTALCELL('total_bookings')}={int(refF['total_bookings'])},{TOTALCELL('total_passengers')}={int(refF['total_passengers'])})"),
        ("Monthly totals: gross booking value equals the full-dataset reference", f"=ABS({TOTALCELL('gross_value')}-{refF['gross_value']:.2f})<0.005"),
        ("Monthly totals: occupancy (ratio of sums) equals the full-dataset reference", f"=ABS({ratio_tot}-{refF['occupancy']:.10f})<0.00005"),
        ("Monthly totals: simulated runs equal 768 (32 runs x 24 months)", f"={TOTALCELL('simulated_runs')}={int(refF['simulated_runs'])}"),
        ("Dashboard (filter = All) agrees with KPI_Calc for bookings, passengers and occupancy", f'=IF(Dashboard!$C$5="All",AND(Dashboard!$C$9={KC("total_bookings")},Dashboard!$C$10={KC("total_passengers")},ABS(Dashboard!$C$18-{KC("occupancy")})<0.00005),TRUE)'),
        ("Sampling disclosure present on README and Dashboard", '=AND(ISNUMBER(SEARCH("19,708",README!$A$4)),ISNUMBER(SEARCH("19,708",Dashboard!$A$2)))'),
    ]
    for i, (lab, fml) in enumerate(checks):
        x = 3 + i
        ws.write_number(x, 0, i + 1); ws.write_string(x, 1, lab); b.formula(ws, x, 2, f'=IF({fml[1:]},"PASS","FAIL")', b.f(bold=True))
    endr = 3 + len(checks)
    ws.write_string(endr + 1, 1, "OVERALL", b.f(bold=True)); b.formula(ws, endr + 1, 2, f'=IF(COUNTIF(C4:C{endr},"FAIL")=0,"ALL {len(checks)} CHECKS PASS","FAILURES: "&COUNTIF(C4:C{endr},"FAIL"))', b.f(bold=True, font_size=12))
    ws.conditional_format(3, 2, endr + 1, 2, {"type": "text", "criteria": "containing", "value": "FAIL", "format": b.f(bg_color="#FFC7CE", font_color="#9C0006")})
    ws.conditional_format(3, 2, endr + 1, 2, {"type": "text", "criteria": "containing", "value": "PASS", "format": b.f(bg_color="#C6EFCE", font_color="#006100")})
    ws.set_column(0, 0, 5); ws.set_column(1, 1, 88); ws.set_column(2, 2, 24)

    # ------------------------------------------------------------------ KPI_Definitions + README
    ws = W["KPI_Definitions"]
    ws.write(0, 0, "KPI definitions used in this workbook (single source: docs/KPI_definitions.md)", b.title)
    xc.side_label(b, ws, 1, 0, xc.SYNTHETIC_BANNER)
    for c, h in enumerate(["KPI key", "KPI", "Definition", "Denominator", "Unit"]):
        ws.write(2, c, h, b.hdr)
    names_ = {k: nm for k, nm, *_ in kpi.KPI_SPEC}
    for i, k in enumerate(CALC_KEYS):
        ws.write_string(3 + i, 0, k); ws.write_string(3 + i, 1, names_.get(k, k.replace("_", " ").title())); ws.write_string(3 + i, 2, KPI_DEFS[k][0]); ws.write_string(3 + i, 3, KPI_DEFS[k][1]); ws.write_string(3 + i, 4, UNIT.get(k, "count"))
    ws.set_column(0, 0, 28); ws.set_column(1, 1, 52); ws.set_column(2, 2, 90); ws.set_column(3, 3, 46); ws.set_column(4, 4, 16)

    ws = W["README"]
    ws.write(0, 0, "IRCTC-inspired Booking Analytics Workbook (Phase 3)", b.title)
    ws.merge_range(1, 0, 1, 6, "Independent portfolio project. Not an official IRCTC or Indian Railways system, and not affiliated with either.", b.f(bold=True))
    ws.write(2, 0, "")
    ws.merge_range(3, 0, 3, 6, xc.SYNTHETIC_BANNER, b.warn); ws.set_row(3, 44)
    ws.merge_range(4, 0, 4, 6, xc.PER_RUN_NOTE + " No monthly total, occupancy rate or trend in this workbook is a network-wide IRCTC metric, and no forecasts are presented.", b.note); ws.set_row(4, 44)
    ws.merge_range(5, 0, 5, 6, xc.SAMPLE_LABEL, b.note); ws.set_row(5, 44)
    sec = b.f(bold=True, font_size=12, font_color="#1F3864")
    ws.write(7, 0, "Six primary analytical areas", sec)
    primary = [("Primary analytical area", "Workbook tab", "Purpose"),
               ("Dashboard", "Dashboard", "KPI cards with a travel-class filter (analytical sample), passenger status by class, and time-series charts (full dataset). Formula-driven; the PivotTable dashboard is a separate workbook."),
               ("Monthly Aggregates", "Monthly_Aggregates", "Executive view: 24 journey months from the FULL cleaned dataset (counts as values, every ratio a formula, totals use ratio of sums)."),
               ("Cancellation & Refund", "Cancellation_Refund", "Cancellation by lead time and class, refund events by type, monthly refunds. Passenger-based cancellation rate with booking-based companion."),
               ("Occupancy & Demand", "Occupancy_Demand", "Occupancy, waitlist pressure and per-run demand by class and month; occupancy distribution."),
               ("KPI Calculation", "KPI_Calc", "Every KPI as an Excel formula on the analytical sample, next to the Python reference and the full-dataset value, with tolerance and PASS/FAIL."),
               ("Validation", "Validation", "Formula checks (row counts, BR-03, BR-08, BR-09, BR-11, reconciliation, sampling disclosure). Overall result at the bottom.")]
    for i, (a_, tab, t) in enumerate(primary):
        h = i == 0
        ws.write_string(8 + i, 0, a_, b.hdr if h else b.f(bold=True)); ws.write_string(8 + i, 1, tab, b.hdr if h else b.f(bold=True, font_color="#1F3864"))
        ws.merge_range(8 + i, 2, 8 + i, 6, t, b.hdr if h else b.f(text_wrap=True)); ws.set_row(8 + i, 30)
    ws.write(16, 0, "Support sheets (kept)", sec)
    support = [("Support sheet", "Role", "Purpose"), ("README", "Documentation", "This sheet."), ("KPI_Definitions", "Documentation", "Definition and denominator of every KPI."),
               ("Parameters", "Parameters", "RAC weight (0.5), on-time threshold (15), lead-bucket table, schedule versus simulated run counts."),
               ("Data_Bookings ... Data_Runs", "Analytical sample data", f"Detailed rows of the analytical sample: 48 of 768 simulated runs (2 per month, run-complete), {len(bk):,} bookings and {len(ps):,} passengers. Helper columns are formulas (shaded blue); every row carries data_origin = SYNTHETIC.")]
    for i, (a_, role, t) in enumerate(support):
        h = i == 0
        ws.write_string(17 + i, 0, a_, b.hdr if h else b.f(bold=True)); ws.write_string(17 + i, 1, role, b.hdr if h else b.f(font_color="#1F3864"))
        ws.merge_range(17 + i, 2, 17 + i, 6, t, b.hdr if h else b.f(text_wrap=True)); ws.set_row(17 + i, 30)
    ws.merge_range(23, 0, 23, 6, "How to refresh: the Data_* sheets are static extracts of data/sample/excel and data/processed/derived. Regenerate them with python/src/build_phase3.py. Do not overwrite data/raw or data/processed/cleaned: the original data is preserved.", b.note); ws.set_row(23, 32)
    ws.merge_range(24, 0, 24, 6, "Colour legend: yellow = editable input; blue = formula; white = static data. Functions used: SUMIFS, COUNTIFS, COUNTIF, SUMPRODUCT, LOOKUP, INDEX, TEXT, IF. XLOOKUP is deliberately not used in verified cells.", b.note); ws.set_row(24, 32)
    ws.set_column(0, 0, 30); ws.set_column(1, 1, 24); ws.set_column(2, 6, 22)
    W["Dashboard"].activate()


def main():
    import time
    t0 = time.time()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    xc.two_pass(build, OUT, cfg.ROOT / "reports" / "phase3_work")
    print("built", OUT.name, "%.0fs" % (time.time() - t0), "%.1f MB" % (OUT.stat().st_size / 1e6))


if __name__ == "__main__":
    main()
