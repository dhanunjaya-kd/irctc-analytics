"""Build excel/IRCTC_KPI_Pivot_Dashboard.xlsx: a dashboard whose analysis is driven by REAL PivotTables.

xlsxwriter cannot create PivotTables, so the fact sheets and KPI cards are written with xlsxwriter and the PivotTables and charts are then added
through LibreOffice (UNO DataPilot). The pivots were created and verified in LibreOffice and checked structurally with openpyxl; they have NOT been
opened in Microsoft Excel in this environment. excel/SETUP_INSTRUCTIONS.md gives the exact steps to rebuild them in Excel if needed.
"""
import numpy as np
import pandas as pd

import clean_data as cl
import config as cfg
import kpi
import lo_bridge as lb
import xl_common as xc
from build_excel_workbook import STATUSES, CLASSES

OUT = cfg.ROOT / "excel" / "IRCTC_KPI_Pivot_Dashboard.xlsx"
PIVOTS = [  # sheet, source sheet, source cols, row field, column field, [(data field, function)], title
    ("PT_1_Status_by_Class", "Fact_Passengers", "final_status", "travel_class", ["passengers"], "Passengers by travel class and final status"),
    ("PT_2_Monthly", "Fact_Passengers", None, "journey_month", ["passengers", "cancelled", "initial_wl", "fare_amount"], "Monthly passengers, cancellations, waiting-list demand and gross fare (sample)"),
    ("PT_3_Lead_Cancellation", "Fact_Passengers", None, "lead_bucket", ["passengers", "cancelled"], "Cancellation by booking lead time (sample)"),
    ("PT_4_Refunds", "Fact_Events", "cancellation_type", "journey_month", ["refund_amount"], "Refund amount by month and event type (sample)"),
    ("PT_5_Occupancy", "Fact_ClassRuns", None, "travel_class", ["total_seats", "booked_seats", "wl_final_pax"], "Seats, booked seats and waitlisted passengers by class (sample)"),
    ("PT_6_Route_Waitlist", "Fact_Passengers", None, "route_name", ["passengers", "initial_wl", "uncleared_wl"], "Waiting-list demand by route (sample)"),
    ("PT_7_Booking_Status", "Fact_Bookings", "booking_status", "travel_class", ["bookings"], "Bookings by class and roll-up status (Confirmed = all passengers; Mixed reported separately)"),
]
FACTS = {}


def facts():
    if FACTS:
        return FACTS
    T = cl.read_clean()
    S = kpi.select_sample(T)
    bk, ps, ev = S["bk"].copy(), S["ps"].copy(), S["ev"].copy()
    crf = kpi.class_runs_frame(S["ps"], S["cap"], S["bk"])
    tt = T["trains"].set_index("train_id")["train_type"]; cal = T["calendar"].set_index("calendar_date")["season"]
    ps["train_type"] = ps["train_id"].map(tt); ps["season"] = ps["journey_date"].map(cal)
    ps["passengers"] = 1; ps["cancelled"] = (ps.final_status == "Cancelled").astype(int); ps["initial_wl"] = (ps.initial_status == "Waitlisted").astype(int)
    ps["cleared_wl"] = ((ps.initial_status == "Waitlisted") & ps.final_status.isin(["Confirmed", "RAC"])).astype(int); ps["uncleared_wl"] = (ps.final_status == "Waitlisted").astype(int)
    bk["bookings"] = 1
    FACTS["Fact_Passengers"] = ps[["passenger_id", "journey_month", "travel_class", "route_name", "train_type", "season", "lead_bucket", "initial_status", "final_status",
                                   "passengers", "fare_amount", "initial_wl", "cleared_wl", "uncleared_wl", "cancelled"]].reset_index(drop=True)
    FACTS["Fact_Events"] = ev[["cancellation_id", "journey_month", "travel_class", "cancellation_type", "status_at_cancellation", "cancelled_passengers",
                               "original_fare_amount", "cancellation_charge", "refund_amount"]].reset_index(drop=True)
    FACTS["Fact_ClassRuns"] = crf[["run_class_key", "journey_month", "travel_class", "route_name", "total_seats", "confirmed_pax", "rac_pax", "wl_final_pax",
                                   "initial_wl_pax", "booked_seats", "occupancy"]].reset_index(drop=True)
    FACTS["Fact_Bookings"] = bk[["booking_id", "journey_month", "travel_class", "route_name", "lead_bucket", "booking_status", "num_passengers", "total_fare", "bookings"]].reset_index(drop=True)
    for _n in ("Fact_Passengers", "Fact_Events", "Fact_ClassRuns", "Fact_Bookings"):
        FACTS[_n]["data_origin"] = "SYNTHETIC"
    FACTS["_ref"] = kpi.compute_kpis(S["bk"], S["ps"], S["ev"], S["cap"], S["ops"])
    return FACTS


def build_base(b: xc.Book):
    F = facts(); wb = b.wb
    order = ["README", "Dashboard"] + [p[0] for p in PIVOTS] + ["Fact_Passengers", "Fact_Events", "Fact_ClassRuns", "Fact_Bookings"]
    W = {n: wb.add_worksheet(n) for n in order}
    W["README"].set_tab_color("#1F3864"); W["Dashboard"].set_tab_color("#2E75B6")
    for p in PIVOTS:
        W[p[0]].set_tab_color("#548235")
    for name in ("Fact_Passengers", "Fact_Events", "Fact_ClassRuns", "Fact_Bookings"):
        df, ws = F[name], W[name]
        for c, h in enumerate(df.columns):
            ws.write(0, c, h, b.hdr)
        for c, h in enumerate(df.columns):
            col = df[h]
            if pd.api.types.is_numeric_dtype(col):
                ws.write_column(1, c, [float(v) for v in col])
            else:
                ws.write_column(1, c, [str(v) for v in col])
        ws.freeze_panes(1, 0); ws.set_column(0, len(df.columns), 16); ws.autofilter(0, 0, len(df), len(df.columns) - 1)
        xc.side_label(b, ws, 0, len(df.columns) + 1, "SYNTHETIC DATA. " + xc.SAMPLE_LABEL)
    ws = W["README"]
    ws.write(0, 0, "PivotTable-based KPI dashboard (Phase 3)", b.title)
    ws.merge_range(1, 0, 1, 7, "Independent portfolio project. Not an official IRCTC or Indian Railways system.", b.f(bold=True))
    ws.merge_range(2, 0, 2, 7, xc.SYNTHETIC_BANNER, b.warn); ws.set_row(2, 44)
    ws.merge_range(3, 0, 3, 7, xc.SAMPLE_LABEL + " The pivots summarise this analytical sample, not the full dataset. " + xc.PER_RUN_NOTE, b.note); ws.set_row(3, 44)
    lines = ["Sheets PT_1 to PT_7 hold real PivotTables built on the Fact_* sheets. Refresh: Data > Refresh All (or right-click a pivot > Refresh).",
             "Fact_* columns 'passengers', 'cancelled', 'initial_wl', 'cleared_wl', 'uncleared_wl' and 'bookings' are 0/1 flags so that pivot SUMs give the KPI numerators in docs/KPI_definitions.md.",
             "Ratios (cancellation rate, occupancy, waitlist pressure) are computed on the Dashboard sheet as plain formulas: numerator / denominator, ratio of sums, with the denominator shown.",
             "Layout note: pivots with several measures (PT_2, PT_3, PT_5, PT_6) list the measures down the rows (the LibreOffice default). In Excel, drag the Σ Values field from Rows to Columns for the side-by-side layout.",
             "Cancellation Rate is passenger-based (denominator: total passengers). PT_7 shows Confirmed (every passenger confirmed) and Mixed bookings as separate columns.",
             "The pivots were generated with LibreOffice and verified there; they were not opened in Excel in the build environment. If Excel reports a problem, rebuild them using excel/SETUP_INSTRUCTIONS.md (section 3).",
             "Slicers and timelines cannot be created programmatically here: add them with PivotTable Analyze > Insert Slicer (excel/SETUP_INSTRUCTIONS.md, section 4)."]
    for i, t in enumerate(lines):
        ws.merge_range(5 + i, 0, 5 + i, 7, t, b.f(text_wrap=True)); ws.set_row(5 + i, 32)
    ws.set_column(0, 7, 20)
    d = W["Dashboard"]
    d.write(0, 0, "KPI dashboard (PivotTable-based, synthetic sampled simulation)", b.title)
    d.merge_range(1, 0, 1, 7, xc.SYNTHETIC_BANNER, b.warn); d.set_row(1, 44)
    d.merge_range(2, 0, 2, 7, xc.SAMPLE_LABEL, b.note); d.set_row(2, 44)
    for c, h in enumerate(["KPI (analytical sample)", "Value", "Numerator", "Denominator (documented)"]):
        d.write(3, c, h, b.hdr)
    FP = lambda col, n=len(F["Fact_Passengers"]) + 1: f"Fact_Passengers!${col}$2:${col}${n}"
    cols = {c: chr(65 + i) for i, c in enumerate(F["Fact_Passengers"].columns)}
    FE = lambda col: f"Fact_Events!${col}$2:${col}${len(F['Fact_Events']) + 1}"
    FC = lambda col: f"Fact_ClassRuns!${col}$2:${col}${len(F['Fact_ClassRuns']) + 1}"
    FB = lambda col: f"Fact_Bookings!${col}$2:${col}${len(F['Fact_Bookings']) + 1}"
    money, pct, integer = b.f(num_format="#,##0", bold=True, bg_color="#EAF1FB"), b.f(num_format="0.0%", bold=True, bg_color="#EAF1FB"), b.f(num_format="#,##0", bold=True, bg_color="#EAF1FB")
    cards = [("Total passengers", None, f"=SUM({FP(cols['passengers'])})", None, "count"), ("Total bookings", None, f"=SUM({FB('I')})", None, "count"),
             ("Fully confirmed bookings (every passenger Confirmed)", None, f'=COUNTIF({FB("F")},"Confirmed")', None, "count"), ("Mixed-status bookings (reported separately)", None, f'=COUNTIF({FB("F")},"Mixed")', None, "count"),
             ("Cancellation rate (passenger-based)", "rate", f"=SUM({FP(cols['cancelled'])})", f"=SUM({FP(cols['passengers'])})", "Total passengers, all final statuses"),
             ("Waiting-list demand (initially waitlisted passengers)", None, f"=SUM({FP(cols['initial_wl'])})", None, "count"),
             ("Waitlist clearance rate", "rate", f"=SUM({FP(cols['cleared_wl'])})", f"=SUM({FP(cols['initial_wl'])})", "Initially waitlisted passengers"),
             ("Uncleared waitlist passengers", None, f"=SUM({FP(cols['uncleared_wl'])})", None, "count"),
             ("Seat occupancy %", "rate", f"=SUM({FC('J')})", f"=SUM({FC('E')})", "Available seats, same train-class runs"),
             ("Waitlist pressure % (not part of occupancy)", "rate", f"=SUM({FC('H')})", f"=SUM({FC('E')})", "Available seats"),
             ("Gross booking value (INR)", None, f"=SUM({FP(cols['fare_amount'])})", None, "n/a"), ("Refund amount (INR)", None, f"=SUM({FE('I')})", None, "n/a"),
             ("Average fare per passenger (INR)", "rate2", f"=SUM({FP(cols['fare_amount'])})", f"=SUM({FP(cols['passengers'])})", "Total passengers")]
    for i, (lab, kind, num, den, note) in enumerate(cards):
        x = 4 + i; d.write_string(x, 0, lab)
        if kind in ("rate", "rate2"):
            b.formula(d, x, 2, num, b.f(num_format="#,##0.00")); b.formula(d, x, 3, den, b.f(num_format="#,##0.00"))
            b.formula(d, x, 1, f'=IF(D{x + 1}=0,"",C{x + 1}/D{x + 1})', pct if kind == "rate" else money); d.write_string(x, 4, note)
        else:
            b.formula(d, x, 1, num, money if "INR" in lab else integer); d.write_string(x, 4, note if note != "count" else "")
    d.write(4 + len(cards) + 1, 0, "Net booking value (INR)"); b.formula(d, 4 + len(cards) + 1, 1, f"=B15-B16", money)
    d.set_column(0, 0, 54); d.set_column(1, 3, 16); d.set_column(4, 4, 38)
    d.write(4 + len(cards) + 3, 0, "Pivot tables are on sheets PT_1 to PT_7; charts below the table are driven by PT_1 and PT_4.", b.note)
    W["Dashboard"].activate()


def add_pivots(base, final):
    from com.sun.star.awt import Rectangle
    from com.sun.star.sheet.DataPilotFieldOrientation import ROW, COLUMN, DATA
    from com.sun.star.sheet.GeneralFunction import SUM
    from com.sun.star.table import CellAddress
    F = facts(); info = {}; chart_log = []
    with lb.office() as desktop:
        doc = lb.load(desktop, base)
        sheets = doc.Sheets
        for sname, src, colf, rowf, datas, title in PIVOTS:
            df = F[src]
            src_sheet = sheets.getByName(src)
            ps = sheets.getByName(sname)
            desc = ps.DataPilotTables.createDataPilotDescriptor()
            desc.SourceRange = src_sheet.getCellRangeByPosition(0, 0, len(df.columns) - 1, len(df)).RangeAddress
            fields = desc.DataPilotFields
            fields.getByName(rowf).Orientation = ROW
            if colf:
                fields.getByName(colf).Orientation = COLUMN
            for dcol in datas:
                fld = fields.getByName(dcol); fld.Orientation = DATA; fld.Function = SUM
            if len(datas) > 1:                      # measures across the columns (as Excel does), not stacked down the rows
                for i in range(fields.Count):
                    f_ = fields.getByIndex(i)
                    if f_.getPropertyValue("IsDataLayoutField"):
                        f_.Orientation = COLUMN
            ps.getCellByPosition(0, 0).String = title
            ps.getCellByPosition(0, 1).String = "SYNTHETIC DATA. Analytical sample: 48 of 768 simulated runs (balanced by journey month, run-complete). Sampled simulation: 768 of 19,708 scheduled runs; not IRCTC network-wide."
            ps.DataPilotTables.insertNewByName(sname.replace("PT_", "Pivot_"), CellAddress(ps.RangeAddress.Sheet, 0, 2), desc)
            tbl = ps.DataPilotTables.getByIndex(0)
            if len(datas) > 1:                      # move the "Data" layout field to the columns on the live table, then refresh
                tf = tbl.DataPilotFields
                for i in range(tf.Count):
                    f_ = tf.getByIndex(i)
                    if f_.getPropertyValue("IsDataLayoutField"):
                        f_.Orientation = COLUMN
                tbl.refresh()
            out = tbl.OutputRange
            info[sname] = (out.StartRow, out.StartColumn, out.EndRow, out.EndColumn)
        # ratios beside pivots (plain formulas referencing pivot cells)
        def find_row(sheet, text, col=0, start=0, end=80):
            for r in range(start, end):
                if sheet.getCellByPosition(col, r).String == text:
                    return r
            return None
        try:
            dash = sheets.getByName("Dashboard")
            base = dash.getCellByPosition(0, 22).Position          # first free row below the KPI table and its notes
            for sname, chart_name, x, y in [("PT_1_Status_by_Class", "chart_status", base.X + 200, base.Y), ("PT_4_Refunds", "chart_refunds", base.X + 16700, base.Y)]:
                ps = sheets.getByName(sname); r0, c0, r1, c1 = info[sname]
                hdr = find_row(ps, "travel_class" if "PT_1" in sname else "journey_month", 0, r0, r1 + 1)
                rng = ps.getCellRangeByPosition(0, hdr, c1 - 1, r1 - 1).RangeAddress
                rect = Rectangle(); rect.X, rect.Y, rect.Width, rect.Height = x, y, 16000, 8500
                dash.Charts.addNewByName(chart_name, rect, (rng,), True, True)
                emb = dash.Charts.getByName(chart_name).EmbeddedObject
                emb.HasMainTitle = True
                emb.HasLegend = True
                emb.Title.String = "Passengers by class and final status (analytical sample, synthetic)" if "PT_1" in sname else "Refund amount by month and event type, INR (analytical sample, synthetic)"
                try:
                    emb.Diagram.Stacked = True
                except Exception as e:
                    chart_log.append(f"{chart_name}: stacking not set ({type(e).__name__})")
                chart_log.append(f"{chart_name}: created from {sname} rows {hdr + 1}-{r1}")
        except Exception as e:
            chart_log.append(f"charts failed: {type(e).__name__}: {str(e)[:120]}")
        doc.calculateAll()
        lb.save_xlsx(doc, final)
        doc.close(True)
    return info, chart_log


def main():
    import time
    t0 = time.time()
    work = cfg.ROOT / "reports" / "phase3_work"; work.mkdir(parents=True, exist_ok=True)
    base = work / "pivot_base.xlsx"
    b = xc.Book(base); build_base(b); b.close()
    info, log = add_pivots(base, OUT)
    print("pivot output ranges (row0,col0,row1,col1):", info)
    print("chart log:", log)
    print("built", OUT.name, "%.0fs" % (time.time() - t0), "%.1f MB" % (OUT.stat().st_size / 1e6))


if __name__ == "__main__":
    main()
