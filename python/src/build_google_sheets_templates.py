"""Build three Google Sheets KPI tracker templates as import-ready .xlsx files (google_sheets/).

Native Google Sheets cannot be created from the build environment (no Drive/Sheets connector), so each template is an .xlsx that imports into Google Sheets
(File > Import). Only functions that work in Google Sheets, Excel and LibreOffice are used (SUMIFS, IF, IFERROR, INDEX, COUNT, N). Sample rows are SYNTHETIC monthly
aggregates from the FULL cleaned dataset; delete the yellow sample rows to start a blank tracker. Targets and thresholds are illustrative, not IRCTC targets.
"""
import pandas as pd
from xlsxwriter.utility import xl_col_to_name as CL

import config as cfg
import kpi
import xl_common as xc

OUT_DIR = cfg.ROOT / "google_sheets"
FIRST, LAST = 5, 40                      # Excel rows of the input tables (36 month slots: 24 filled, 12 blank)
CLASSES = ["SL", "3A", "2A", "1A", "CC", "2S"]
BANNER = ("SYNTHETIC SAMPLE DATA from a sampled simulation (768 simulated runs of 19,708 scheduled, 3.9%). Not IRCTC or Indian Railways metrics. "
          "Compare months with per-run and capacity-normalised measures, not raw monthly totals. Targets and thresholds are illustrative.")


def head(b, ws, title, ncols):
    ws.write(0, 0, title, b.title)
    ws.merge_range(1, 0, 1, ncols - 1, BANNER, b.warn); ws.set_row(1, 44)


def instructions(b, ws, title, lines):
    ws.write(0, 0, title, b.title)
    ws.merge_range(1, 0, 1, 7, BANNER, b.warn); ws.set_row(1, 44)
    for i, t in enumerate(lines):
        ws.merge_range(3 + i, 0, 3 + i, 7, t, b.f(text_wrap=True)); ws.set_row(3 + i, 34)
    ws.set_column(0, 7, 18)


def write_inputs(b, ws, headers, df, keys, months_only_first=True, blank_to=LAST):
    """Yellow input table: header at row 4 (Excel), data from row 5."""
    inp = b.f(bg_color="#FFF2CC", border=1)
    for c, h in enumerate(headers):
        ws.write(3, c, h, b.hdr)
    for i, row in enumerate(df.itertuples(index=False)):
        for c, k in enumerate(keys):
            v = getattr(row, k)
            if isinstance(v, str):
                ws.write_string(FIRST - 1 + i, c, v, inp)
            else:
                ws.write_number(FIRST - 1 + i, c, float(v), inp)
    for i in range(len(df), blank_to - FIRST + 1):
        for c in range(len(keys)):
            ws.write_blank(FIRST - 1 + i, c, None, inp)
    ws.freeze_panes(4, 1); ws.set_column(0, len(headers), 15); ws.set_row(3, 44)


# ------------------------------------------------------------------------------------------------ template 1
def build_kpi_tracker(b):
    mo = pd.read_csv(kpi.DERIVED_DIR / "monthly_kpis.csv")
    mo["confirmed_pax"] = mo["confirmed_pax"]; mo["rac_pax"] = mo["rac_pax"]
    keys = ["journey_month", "simulated_runs", "total_bookings", "total_passengers", "confirmed_bookings", "mixed_bookings", "cancelled_bookings", "cancelled_passengers",
            "wl_demand", "wl_cleared", "wl_uncleared", "confirmed_pax", "rac_pax", "seat_supply", "gross_value", "refund_total", "runs_with_delay", "on_time_runs", "delay_sum_pos"]
    W = {n: b.wb.add_worksheet(n) for n in ["Instructions", "Inputs_Monthly", "KPI_Tracker", "Targets", "Charts", "Settings"]}
    instructions(b, W["Instructions"], "KPI Tracker template (Google Sheets)", [
        "1. Import: Google Sheets > File > Import > Upload > choose this .xlsx > 'Replace spreadsheet' or 'Insert new sheet(s)'. Formulas, formatting and drop-downs import; re-check the charts (Insert > Chart) if they look different.",
        "2. Inputs_Monthly (yellow): one row per journey month. Enter counts only; every KPI is calculated on KPI_Tracker. Fill months contiguously from the first row (the Targets sheet reads the last filled month).",
        "3. Denominators (docs/KPI_definitions.md): passenger cancellation rate = cancelled passengers / total passengers; booking cancellation rate = cancelled bookings / total bookings; clearance = cleared / initially waitlisted; occupancy = (confirmed + RAC weight x RAC) / seats; waitlist pressure = uncleared waitlist / seats; on-time = on-time runs / runs with a recorded delay.",
        "4. Fully confirmed bookings mean EVERY passenger is Confirmed. Mixed-status bookings are reported separately.",
        "5. Targets: edit the yellow targets and tolerances. Status shows On target, Watch or Off target for the last filled month. Targets are illustrative.",
        "6. Sample rows are synthetic and come from a sampled simulation (32 simulated runs per month). Because of that, compare months on per-run and normalised measures, not on raw totals."])
    ws = W["Settings"]; head(b, ws, "Settings", 4)
    ws.write(2, 0, "RAC seat weight (configurable simulation assumption, not an official rule)"); ws.write_number(2, 1, cfg.RAC_SEAT_WEIGHT, b.f(bg_color="#FFF2CC", border=1))
    ws.write(3, 0, "On-time threshold in minutes (informational; on-time run counts are entered as inputs)"); ws.write_number(3, 1, cfg.ON_TIME_THRESHOLD_MIN)
    ws.data_validation(2, 1, 2, 1, {"validate": "decimal", "criteria": "between", "minimum": 0, "maximum": 1}); ws.set_column(0, 0, 80)
    RAC = "Settings!$B$3"
    ws = W["Inputs_Monthly"]; head(b, ws, "Inputs: monthly counts (sample rows are synthetic)", 19)
    write_inputs(b, ws, ["Journey month", "Simulated runs", "Total bookings", "Total passengers", "Fully confirmed bookings", "Mixed-status bookings", "Cancelled bookings (all passengers cancelled)", "Cancelled passengers",
                         "Waiting-list demand (initial WL passengers)", "WL passengers later Confirmed or RAC", "Uncleared WL passengers", "Confirmed passengers", "RAC passengers", "Available seats", "Gross booking value (INR)",
                         "Refund amount (INR)", "Runs with recorded delay", "On-time runs", "Sum of max(delay,0) minutes"], mo, keys)
    ws = W["KPI_Tracker"]; head(b, ws, "KPI Tracker (formulas; do not overwrite)", 19)
    hd = ["Journey month", "Bookings per simulated run", "Passengers per simulated run", "Cancellation rate (passenger-based)", "Booking cancellation rate (companion)", "Fully confirmed share of bookings", "Mixed-status share of bookings",
          "Waiting-list demand share of passengers", "Waitlist clearance rate", "Waitlist pressure %", "Seat occupancy %", "Gross booking value", "Refund amount", "Net booking value", "Average fare per passenger",
          "On-time performance %", "Average delay (min)", "Bookings growth vs prior month", "Bookings-per-run growth vs prior month"]
    for c, h in enumerate(hd):
        ws.write(3, c, h, b.hdr)
    I = lambda col, e: f"Inputs_Monthly!${col}{e}"
    pct, num, mon = b.f(num_format="0.0%", bg_color="#EAF1FB"), b.f(num_format="#,##0.00", bg_color="#EAF1FB"), b.f(num_format="#,##0", bg_color="#EAF1FB")
    for e in range(FIRST, LAST + 1):
        x = e - 1
        b.formula(ws, x, 0, f'=IF({I("A", e)}="","",{I("A", e)})', b.f(bg_color="#EAF1FB"))
        g = lambda den, num, f: f'=IF(N({I(den, e)})=0,"",{num}/{I(den, e)})'
        b.formula(ws, x, 1, f'=IF(N({I("B", e)})=0,"",{I("C", e)}/{I("B", e)})', num); b.formula(ws, x, 2, f'=IF(N({I("B", e)})=0,"",{I("D", e)}/{I("B", e)})', num)
        b.formula(ws, x, 3, f'=IF(N({I("D", e)})=0,"",{I("H", e)}/{I("D", e)})', pct); b.formula(ws, x, 4, f'=IF(N({I("C", e)})=0,"",{I("G", e)}/{I("C", e)})', pct)
        b.formula(ws, x, 5, f'=IF(N({I("C", e)})=0,"",{I("E", e)}/{I("C", e)})', pct); b.formula(ws, x, 6, f'=IF(N({I("C", e)})=0,"",{I("F", e)}/{I("C", e)})', pct)
        b.formula(ws, x, 7, f'=IF(N({I("D", e)})=0,"",{I("I", e)}/{I("D", e)})', pct); b.formula(ws, x, 8, f'=IF(N({I("I", e)})=0,"",{I("J", e)}/{I("I", e)})', pct)
        b.formula(ws, x, 9, f'=IF(N({I("N", e)})=0,"",{I("K", e)}/{I("N", e)})', pct); b.formula(ws, x, 10, f'=IF(N({I("N", e)})=0,"",({I("L", e)}+{RAC}*{I("M", e)})/{I("N", e)})', pct)
        b.formula(ws, x, 11, f'=IF(N({I("O", e)})=0,"",{I("O", e)})', mon); b.formula(ws, x, 12, f'=IF(N({I("O", e)})=0,"",{I("P", e)})', mon)
        b.formula(ws, x, 13, f'=IF(N({I("O", e)})=0,"",{I("O", e)}-{I("P", e)})', mon); b.formula(ws, x, 14, f'=IF(N({I("D", e)})=0,"",{I("O", e)}/{I("D", e)})', num)
        b.formula(ws, x, 15, f'=IF(N({I("Q", e)})=0,"",{I("R", e)}/{I("Q", e)})', pct); b.formula(ws, x, 16, f'=IF(N({I("Q", e)})=0,"",{I("S", e)}/{I("Q", e)})', num)
        if e == FIRST:
            ws.write_string(x, 17, ""); ws.write_string(x, 18, "")
        else:
            b.formula(ws, x, 17, f'=IF(OR(N({I("C", e)})=0,N({I("C", e - 1)})=0),"",{I("C", e)}/{I("C", e - 1)}-1)', pct)
            b.formula(ws, x, 18, f'=IF(OR(B{e}="",B{e - 1}=""),"",B{e}/B{e - 1}-1)', pct)
    ws.freeze_panes(4, 1); ws.set_column(0, 18, 15); ws.set_row(3, 58)
    ws = W["Targets"]; head(b, ws, "Targets and status for the last filled month (illustrative targets)", 8)
    for c, h in enumerate(["KPI", "Direction", "Target (editable)", "Watch tolerance (editable)", "Latest value", "Status"]):
        ws.write(3, c, h, b.hdr)
    tg = [("Cancellation rate (passenger-based)", "Lower is better", 0.15, 0.03, "D", "0.0%"), ("Waitlist clearance rate", "Higher is better", 0.20, 0.05, "I", "0.0%"),
          ("Waitlist pressure %", "Lower is better", 0.05, 0.02, "J", "0.0%"), ("Seat occupancy %", "Higher is better", 0.75, 0.05, "K", "0.0%"),
          ("On-time performance %", "Higher is better", 0.80, 0.05, "P", "0.0%"), ("Average delay (min)", "Lower is better", 20, 5, "Q", "0.0")]
    for i, (k, d, t, tol, col, nf) in enumerate(tg):
        x = 4 + i; e = x + 1
        ws.write_string(x, 0, k); ws.write_string(x, 1, d, b.f(bg_color="#FFF2CC", border=1)); ws.write_number(x, 2, t, b.f(bg_color="#FFF2CC", border=1, num_format=nf)); ws.write_number(x, 3, tol, b.f(bg_color="#FFF2CC", border=1, num_format=nf))
        ws.data_validation(x, 1, x, 1, {"validate": "list", "source": ["Higher is better", "Lower is better"]})
        b.formula(ws, x, 4, f'=IF(COUNT(Inputs_Monthly!$B${FIRST}:$B${LAST})=0,"",INDEX(KPI_Tracker!${col}${FIRST}:${col}${LAST},COUNT(Inputs_Monthly!$B${FIRST}:$B${LAST})))', b.f(num_format=nf, bg_color="#EAF1FB"))
        b.formula(ws, x, 5, f'=IF(E{e}="","",IF(B{e}="Higher is better",IF(E{e}>=C{e},"On target",IF(E{e}>=C{e}-D{e},"Watch","Off target")),IF(E{e}<=C{e},"On target",IF(E{e}<=C{e}+D{e},"Watch","Off target"))))', b.f(bold=True))
    for txt, colr, fc in (("On target", "#C6EFCE", "#006100"), ("Watch", "#FFEB9C", "#7F6000"), ("Off target", "#FFC7CE", "#9C0006")):
        ws.conditional_format(4, 5, 9, 5, {"type": "cell", "criteria": "==", "value": f'"{txt}"', "format": b.f(bg_color=colr, font_color=fc)})
    ws.set_column(0, 0, 40); ws.set_column(1, 5, 22)
    ws = W["Charts"]; head(b, ws, "Charts (ranges cover the 24 sample months; extend the series when you add months)", 12)
    for (name, cols, r0, colr) in [("Bookings per simulated run", [("B", "#2E75B6")], 3, None), ("Seat occupancy % and waitlist pressure %", [("K", "#548235"), ("J", "#C00000")], 20, None),
                                   ("On-time performance %", [("P", "#7F6000")], 37, None)]:
        ch = b.wb.add_chart({"type": "line"})
        for col, colr in cols:
            ch.add_series({"name": f"=KPI_Tracker!${col}$4", "categories": f"=KPI_Tracker!$A${FIRST}:$A${FIRST + 23}", "values": f"=KPI_Tracker!${col}${FIRST}:${col}${FIRST + 23}", "line": {"color": colr}})
        ch.set_title({"name": name + " (synthetic)", "name_font": {"size": 10}}); ch.set_size({"width": 620, "height": 300}); ch.set_x_axis({"num_font": {"rotation": -45, "size": 8}}); ch.set_legend({"position": "bottom"})
        ws.insert_chart(r0 - 1, 0, ch)
    W["Instructions"].activate()


# ------------------------------------------------------------------------------------------------ template 2
def build_cancellation_tracker(b):
    mo = pd.read_csv(kpi.DERIVED_DIR / "monthly_kpis.csv")
    lead = pd.read_csv(kpi.DERIVED_DIR / "cancellation_by_lead_and_class.csv").groupby("lead_bucket", observed=True)[["passengers", "cancelled_pax"]].sum().reindex(kpi.LEAD_LABELS).reset_index()
    keys = ["journey_month", "total_bookings", "total_passengers", "cancelled_bookings", "cancelled_passengers", "wl_uncleared", "gross_value", "refund_passenger", "refund_system", "retained_charges"]
    W = {n: b.wb.add_worksheet(n) for n in ["Instructions", "Inputs_Monthly", "Analysis", "Lead_Time", "Thresholds"]}
    instructions(b, W["Instructions"], "Cancellation and Refund Tracker template (Google Sheets)", [
        "1. Import the .xlsx (File > Import). Enter monthly counts and amounts on Inputs_Monthly (yellow); Analysis and the alert flags are formulas.",
        "2. Cancellation Rate is passenger-based (denominator: total passengers). The booking-based rate (denominator: total bookings) is the companion. System auto-refunds of uncleared waitlisted passengers are NOT passenger cancellations and are tracked separately.",
        "3. Refund % of gross = (passenger-event refunds + system-event refunds) / gross booking value. Charges as % of (refunds + charges) shows how much of the refundable fare was retained.",
        "4. Thresholds (editable, illustrative) drive the ALERT / OK flags. Lead_Time takes passengers and cancelled passengers per booking lead-time bucket.",
        "5. Sample rows are synthetic and come from a sampled simulation; the cancellation-versus-lead-time pattern was built into the generator, so it shows how to analyse such a pattern, not a real-world finding."])
    ws = W["Thresholds"]; head(b, ws, "Alert thresholds (illustrative, editable)", 4)
    for i, (k, v, nf) in enumerate([("Passenger cancellation rate alert above", 0.15, "0.0%"), ("Refund % of gross alert above", 0.20, "0.0%"), ("System share of refunds alert above", 0.60, "0.0%")]):
        ws.write_string(3 + i, 0, k); ws.write_number(3 + i, 1, v, b.f(bg_color="#FFF2CC", border=1, num_format=nf))
    ws.set_column(0, 0, 46); ws.set_column(1, 1, 14)
    ws = W["Inputs_Monthly"]; head(b, ws, "Inputs: monthly cancellation and refund data (sample rows are synthetic)", 10)
    write_inputs(b, ws, ["Journey month", "Total bookings", "Total passengers", "Cancelled bookings (all passengers cancelled)", "Cancelled passengers", "Uncleared WL passengers (system refunded)", "Gross booking value (INR)",
                         "Refunds: Passenger events (INR)", "Refunds: System events (INR)", "Cancellation charges retained (INR)"], mo, keys)
    ws = W["Analysis"]; head(b, ws, "Analysis (formulas; do not overwrite)", 11)
    hd = ["Journey month", "Cancellation rate (passenger-based)", "Booking cancellation rate (companion)", "Refund amount (INR)", "Net booking value (INR)", "Refund % of gross", "System share of refunds", "Charges % of (refunds + charges)",
          "Uncleared WL as % of passengers", "Passenger-rate alert", "Refund-rate alert"]
    for c, h in enumerate(hd):
        ws.write(3, c, h, b.hdr)
    I = lambda col, e: f"Inputs_Monthly!${col}{e}"
    pct, mon = b.f(num_format="0.0%", bg_color="#EAF1FB"), b.f(num_format="#,##0", bg_color="#EAF1FB")
    for e in range(FIRST, LAST + 1):
        x = e - 1
        b.formula(ws, x, 0, f'=IF({I("A", e)}="","",{I("A", e)})', b.f(bg_color="#EAF1FB"))
        b.formula(ws, x, 1, f'=IF(N({I("C", e)})=0,"",{I("E", e)}/{I("C", e)})', pct); b.formula(ws, x, 2, f'=IF(N({I("B", e)})=0,"",{I("D", e)}/{I("B", e)})', pct)
        b.formula(ws, x, 3, f'=IF(N({I("G", e)})=0,"",{I("H", e)}+{I("I", e)})', mon); b.formula(ws, x, 4, f'=IF(N({I("G", e)})=0,"",{I("G", e)}-D{e})', mon)
        b.formula(ws, x, 5, f'=IF(N({I("G", e)})=0,"",D{e}/{I("G", e)})', pct); b.formula(ws, x, 6, f'=IF(N(D{e})=0,"",{I("I", e)}/D{e})', pct)
        b.formula(ws, x, 7, f'=IF(D{e}="","",IF(D{e}+N({I("J", e)})=0,"",{I("J", e)}/(D{e}+{I("J", e)})))', pct); b.formula(ws, x, 8, f'=IF(N({I("C", e)})=0,"",{I("F", e)}/{I("C", e)})', pct)
        b.formula(ws, x, 9, f'=IF(B{e}="","",IF(B{e}>Thresholds!$B$4,"ALERT","OK"))', b.f(bold=True)); b.formula(ws, x, 10, f'=IF(F{e}="","",IF(F{e}>Thresholds!$B$5,"ALERT","OK"))', b.f(bold=True))
    for col in (9, 10):
        ws.conditional_format(FIRST - 1, col, LAST - 1, col, {"type": "cell", "criteria": "==", "value": '"ALERT"', "format": b.f(bg_color="#FFC7CE", font_color="#9C0006")})
        ws.conditional_format(FIRST - 1, col, LAST - 1, col, {"type": "cell", "criteria": "==", "value": '"OK"', "format": b.f(bg_color="#C6EFCE", font_color="#006100")})
    ws.freeze_panes(4, 1); ws.set_column(0, 10, 16); ws.set_row(3, 58)
    ch = b.wb.add_chart({"type": "column", "subtype": "stacked"})
    ch.add_series({"name": "Passenger events", "categories": f"=Inputs_Monthly!$A${FIRST}:$A${FIRST + 23}", "values": f"=Inputs_Monthly!$H${FIRST}:$H${FIRST + 23}", "fill": {"color": "#2E75B6"}})
    ch.add_series({"name": "System auto-refunds", "categories": f"=Inputs_Monthly!$A${FIRST}:$A${FIRST + 23}", "values": f"=Inputs_Monthly!$I${FIRST}:$I${FIRST + 23}", "fill": {"color": "#ED7D31"}})
    ch.set_title({"name": "Refunds by event type, INR (synthetic)", "name_font": {"size": 10}}); ch.set_size({"width": 640, "height": 300}); ch.set_x_axis({"num_font": {"rotation": -45, "size": 8}}); ch.set_legend({"position": "bottom"})
    ws.insert_chart(LAST + 1, 0, ch)
    ws = W["Lead_Time"]; head(b, ws, "Cancellation by booking lead time (sample rows are synthetic)", 5)
    for c, h in enumerate(["Lead bucket", "Passengers", "Cancelled passengers", "Cancellation rate (passenger-based)"]):
        ws.write(3, c, h, b.hdr)
    for i, r in enumerate(lead.itertuples()):
        x = 4 + i; e = x + 1
        ws.write_string(x, 0, r.lead_bucket, b.f(bg_color="#FFF2CC", border=1)); ws.write_number(x, 1, float(r.passengers), b.f(bg_color="#FFF2CC", border=1)); ws.write_number(x, 2, float(r.cancelled_pax), b.f(bg_color="#FFF2CC", border=1))
        b.formula(ws, x, 3, f'=IF(N(B{e})=0,"",C{e}/B{e})', pct)
    ws.set_column(0, 3, 24); ws.set_row(3, 40)
    ch = b.wb.add_chart({"type": "column"})
    ch.add_series({"name": "Cancellation rate", "categories": "=Lead_Time!$A$5:$A$9", "values": "=Lead_Time!$D$5:$D$9", "fill": {"color": "#C00000"}, "data_labels": {"value": True, "num_format": "0.0%"}})
    ch.set_title({"name": "Passenger cancellation rate by lead time (synthetic)", "name_font": {"size": 10}}); ch.set_legend({"none": True}); ch.set_y_axis({"num_format": "0%"}); ch.set_size({"width": 520, "height": 280})
    ws.insert_chart(10, 0, ch)
    W["Instructions"].activate()


# ------------------------------------------------------------------------------------------------ template 3
def build_occupancy_tracker(b):
    mc = pd.read_csv(kpi.DERIVED_DIR / "monthly_class_occupancy.csv")
    months = sorted(mc["journey_month"].unique())
    keys = ["journey_month", "travel_class", "class_runs", "seats", "confirmed_pax", "rac_pax", "wl_final_pax", "initial_wl_pax", "passengers"]
    W = {n: b.wb.add_worksheet(n) for n in ["Instructions", "Settings", "Inputs_Class_Month", "Analysis", "By_Class", "Month_x_Class"]}
    instructions(b, W["Instructions"], "Occupancy and Waitlist Tracker template (Google Sheets)", [
        "1. Import the .xlsx (File > Import). Enter one row per journey month and travel class on Inputs_Class_Month (yellow). Everything else is formulas.",
        "2. Seat occupancy % = (confirmed passengers + RAC weight x RAC passengers) / available seats, on final statuses, matched per train-class run. The RAC weight (0.5) is a configurable simulation assumption on Settings, not an official rule.",
        "3. Waitlisted passengers hold no seat: they are reported as waitlist pressure % (uncleared waitlist passengers / available seats) and are never part of occupancy. Confirmed, RAC and waitlisted passengers stay in separate columns.",
        "4. By_Class and Month_x_Class summarise with SUMIFS as ratio of sums (never an average of percentages). The heat map on Month_x_Class shades occupancy.",
        "5. Sample rows are synthetic, from a sampled simulation with simulated capacity. Occupancy here is whole-journey per train-class run; intermediate-segment occupancy is out of scope."])
    ws = W["Settings"]; head(b, ws, "Settings", 3)
    ws.write(2, 0, "RAC seat weight (configurable simulation assumption)"); ws.write_number(2, 1, cfg.RAC_SEAT_WEIGHT, b.f(bg_color="#FFF2CC", border=1)); ws.set_column(0, 0, 60)
    ws.data_validation(2, 1, 2, 1, {"validate": "decimal", "criteria": "between", "minimum": 0, "maximum": 1})
    RAC = "Settings!$B$3"; LASTC = 4 + len(mc) + 60
    ws = W["Inputs_Class_Month"]; head(b, ws, "Inputs: month x class (sample rows are synthetic)", 9)
    inp = b.f(bg_color="#FFF2CC", border=1)
    for c, h in enumerate(["Journey month", "Travel class", "Class-runs", "Available seats", "Confirmed passengers", "RAC passengers", "Uncleared WL passengers", "Initially waitlisted passengers", "Total passengers"]):
        ws.write(3, c, h, b.hdr)
    for i, r in enumerate(mc.itertuples(index=False)):
        for c, k in enumerate(keys):
            v = getattr(r, k)
            ws.write_string(4 + i, c, v, inp) if isinstance(v, str) else ws.write_number(4 + i, c, float(v), inp)
    for i in range(len(mc), LASTC - 4):
        for c in range(9):
            ws.write_blank(4 + i, c, None, inp)
    ws.data_validation(4, 1, LASTC - 1, 1, {"validate": "list", "source": CLASSES}); ws.freeze_panes(4, 2); ws.set_column(0, 8, 16); ws.set_row(3, 44)
    IN = lambda col: f"Inputs_Class_Month!${col}$5:${col}${LASTC}"
    ws = W["Analysis"]; head(b, ws, "Row-level analysis (formulas; do not overwrite)", 9)
    for c, h in enumerate(["Journey month", "Travel class", "Booked seats (seat-equivalents)", "Seat occupancy %", "Confirmed occupancy %", "RAC occupancy %", "Waitlist pressure %", "Passengers per class-run", "Initial WL per class-run"]):
        ws.write(3, c, h, b.hdr)
    pct, num = b.f(num_format="0.0%", bg_color="#EAF1FB"), b.f(num_format="#,##0.00", bg_color="#EAF1FB")
    for e in range(5, LASTC + 1):
        x = e - 1; I = lambda col: f"Inputs_Class_Month!${col}{e}"
        b.formula(ws, x, 0, f'=IF({I("A")}="","",{I("A")})', b.f(bg_color="#EAF1FB")); b.formula(ws, x, 1, f'=IF({I("B")}="","",{I("B")})', b.f(bg_color="#EAF1FB"))
        b.formula(ws, x, 2, f'=IF(N({I("D")})=0,"",{I("E")}+{RAC}*{I("F")})', num); b.formula(ws, x, 3, f'=IF(N({I("D")})=0,"",C{e}/{I("D")})', pct)
        b.formula(ws, x, 4, f'=IF(N({I("D")})=0,"",{I("E")}/{I("D")})', pct); b.formula(ws, x, 5, f'=IF(N({I("D")})=0,"",{RAC}*{I("F")}/{I("D")})', pct)
        b.formula(ws, x, 6, f'=IF(N({I("D")})=0,"",{I("G")}/{I("D")})', pct); b.formula(ws, x, 7, f'=IF(N({I("C")})=0,"",{I("I")}/{I("C")})', num); b.formula(ws, x, 8, f'=IF(N({I("C")})=0,"",{I("H")}/{I("C")})', num)
    ws.freeze_panes(4, 2); ws.set_column(0, 8, 17); ws.set_row(3, 44)
    ws = W["By_Class"]; head(b, ws, "Summary by travel class (ratio of sums)", 8)
    for c, h in enumerate(["Class", "Class-runs", "Available seats", "Booked seats", "Seat occupancy %", "Confirmed occupancy %", "RAC occupancy %", "Waitlist pressure %"]):
        ws.write(3, c, h, b.hdr)
    for i, cl_ in enumerate(CLASSES + ["All classes"]):
        x = 4 + i; e = x + 1
        crit = f',{IN("B")},A{e}' if cl_ != "All classes" else ""
        sm = lambda col: (f"SUMIFS({IN(col)}{crit})" if crit else f"SUM({IN(col)})")
        ws.write_string(x, 0, cl_, b.f(bold=cl_ == "All classes"))
        b.formula(ws, x, 1, "=" + sm("C"), b.f(num_format="#,##0", bg_color="#EAF1FB")); b.formula(ws, x, 2, "=" + sm("D"), b.f(num_format="#,##0", bg_color="#EAF1FB"))
        b.formula(ws, x, 3, f"={sm('E')}+{RAC}*{sm('F')}", num); b.formula(ws, x, 4, f'=IF(C{e}=0,"",D{e}/C{e})', pct)
        b.formula(ws, x, 5, f'=IF(C{e}=0,"",{sm("E")}/C{e})', pct); b.formula(ws, x, 6, f'=IF(C{e}=0,"",{RAC}*{sm("F")}/C{e})', pct); b.formula(ws, x, 7, f'=IF(C{e}=0,"",{sm("G")}/C{e})', pct)
    ws.set_column(0, 7, 18); ws.set_row(3, 40)
    ch = b.wb.add_chart({"type": "column"})
    ch.add_series({"name": "Seat occupancy %", "categories": "=By_Class!$A$5:$A$10", "values": "=By_Class!$E$5:$E$10", "fill": {"color": "#548235"}, "data_labels": {"value": True, "num_format": "0%"}})
    ch.add_series({"name": "Waitlist pressure %", "categories": "=By_Class!$A$5:$A$10", "values": "=By_Class!$H$5:$H$10", "fill": {"color": "#C00000"}})
    ch.set_title({"name": "Occupancy and waitlist pressure by class (synthetic, simulated capacity)", "name_font": {"size": 10}}); ch.set_y_axis({"num_format": "0%"}); ch.set_size({"width": 560, "height": 290}); ch.set_legend({"position": "bottom"})
    ws.insert_chart(12, 0, ch)
    ws = W["Month_x_Class"]; head(b, ws, "Seat occupancy % heat map: month x class (ratio of sums)", 8)
    ws.write(3, 0, "Journey month", b.hdr)
    for j, c_ in enumerate(CLASSES):
        ws.write_string(3, 1 + j, c_, b.hdr)
    ws.write(3, 7, "All classes", b.hdr)
    for i, m in enumerate(months):
        x = 4 + i; e = x + 1
        ws.write_string(x, 0, m)
        for j in range(len(CLASSES)):
            cc = CL(1 + j)
            b.formula(ws, x, 1 + j, f'=IF(SUMIFS({IN("D")},{IN("A")},$A{e},{IN("B")},{cc}$4)=0,"",(SUMIFS({IN("E")},{IN("A")},$A{e},{IN("B")},{cc}$4)+{RAC}*SUMIFS({IN("F")},{IN("A")},$A{e},{IN("B")},{cc}$4))/SUMIFS({IN("D")},{IN("A")},$A{e},{IN("B")},{cc}$4))', pct)
        b.formula(ws, x, 7, f'=IF(SUMIFS({IN("D")},{IN("A")},$A{e})=0,"",(SUMIFS({IN("E")},{IN("A")},$A{e})+{RAC}*SUMIFS({IN("F")},{IN("A")},$A{e}))/SUMIFS({IN("D")},{IN("A")},$A{e}))', pct)
    ws.conditional_format(4, 1, 3 + len(months), 7, {"type": "3_color_scale", "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"})
    ws.set_column(0, 7, 14)
    W["Instructions"].activate()


def main():
    import time
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for fn, name in [(build_kpi_tracker, "KPI_Tracker_Template.xlsx"), (build_cancellation_tracker, "Cancellation_Refund_Tracker_Template.xlsx"), (build_occupancy_tracker, "Occupancy_Waitlist_Tracker_Template.xlsx")]:
        t0 = time.time(); xc.two_pass(fn, OUT_DIR / name, cfg.ROOT / "reports" / "phase3_work")
        print("built", name, "%.0fs" % (time.time() - t0), "%.0f KB" % ((OUT_DIR / name).stat().st_size / 1024), flush=True)


if __name__ == "__main__":
    main()
