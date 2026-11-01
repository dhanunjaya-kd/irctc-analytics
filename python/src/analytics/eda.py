"""Structured exploratory data analysis (EDA) on the full cleaned dataset: A demand, B passenger behaviour, C operations, D financial, E temporal.

Everything is computed from the cleaned fact tables. Comparisons use PER-RUN and capacity-normalised measures because only 32 runs per month are simulated
(768 of 19,708 scheduled runs): raw monthly totals reflect the sampling design. The data is synthetic; nothing here describes real IRCTC behaviour.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .cleaning import STATUS_ORDER, BOOKING_STATUS_ORDER, WEEKDAYS
from . import statistics as st

MIN_RUNS = 9      # every train has 9 to 20 simulated runs; groups below this are not ranked


def _share(s: pd.Series) -> pd.Series:
    return s / s.sum()


def _otp(rf: pd.DataFrame, by) -> pd.DataFrame:
    d = rf.dropna(subset=["on_time"]).assign(ot=lambda x: x.on_time.astype(bool))
    return d.groupby(by, observed=True).agg(runs_with_delay=("ot", "size"), otp=("ot", "mean"), avg_delay=("delay_positive", "mean")).reset_index()


def _rate_by(pf: pd.DataFrame, col: str) -> pd.DataFrame:
    g = pf.groupby(col, observed=True).agg(passengers=("passenger_id", "size"), cancelled=("is_cancelled", "sum"), initial_wl=("is_initial_wl", "sum"), cleared_wl=("is_cleared_wl", "sum"), uncleared_wl=("is_uncleared_wl", "sum"),
                                           confirmed=("final_status", lambda s: (s == "Confirmed").sum()), rac=("final_status", lambda s: (s == "RAC").sum())).reset_index()
    g["cancellation_rate"] = g.cancelled / g.passengers
    ci = [st.wilson_ci(k, n) for k, n in zip(g.cancelled, g.passengers)]
    g["cancel_ci_low"], g["cancel_ci_high"] = [c[0] for c in ci], [c[1] for c in ci]
    g["initial_wl_share"] = g.initial_wl / g.passengers
    g["wl_clearance_rate"] = g.cleared_wl / g.initial_wl.replace(0, np.nan)
    g["uncleared_share_of_wl_demand"] = g.uncleared_wl / g.initial_wl.replace(0, np.nan)
    return g


def run_eda(facts: dict, monthly: pd.DataFrame) -> dict:
    pf, bf, ef, cf, rf = (facts[k] for k in ("passenger_fact", "booking_fact", "event_fact", "class_run_fact", "run_fact"))
    E = {}
    # ------------------------------------------------ A. booking demand
    E["monthly_demand"] = monthly[["journey_month", "total_bookings", "total_passengers", "simulated_runs", "bookings_per_run", "passengers_per_run", "bookings_growth", "bookings_per_run_growth"]].copy()
    agg = dict(runs=("operation_id", "size"), bookings=("bookings", "sum"), passengers=("passengers", "sum"), booked=("booked_seats", "sum"), seats=("seats", "sum"))
    wk = rf.groupby("weekday", observed=True).agg(**agg).reset_index()
    wk["bookings_per_run"], wk["passengers_per_run"], wk["occupancy"] = wk.bookings / wk.runs, wk.passengers / wk.runs, wk.booked / wk.seats
    E["weekday_demand"] = wk
    we = rf.assign(day_type=np.where(rf.is_weekend, "Weekend (Sat-Sun)", "Weekday (Mon-Fri)")).groupby("day_type").agg(**agg).reset_index()
    we["passengers_per_run"], we["bookings_per_run"], we["occupancy"] = we.passengers / we.runs, we.bookings / we.runs, we.booked / we.seats
    E["weekend_vs_weekday"] = we
    bs = bf.booking_status.astype(str).value_counts().reindex(BOOKING_STATUS_ORDER).rename("bookings").to_frame(); bs["share"] = _share(bs.bookings)
    E["booking_status_mix"] = bs.reset_index(names="booking_status")
    mix = pd.DataFrame({"initial": pf.initial_status.astype(str).value_counts(), "final": pf.final_status.astype(str).value_counts()}).reindex(STATUS_ORDER).fillna(0).astype(int)
    mix["initial_share"], mix["final_share"] = _share(mix.initial), _share(mix.final)
    E["passenger_status_mix"] = mix.reset_index(names="status")
    fs = pd.crosstab(pf.travel_class, pf.final_status.astype(str), normalize="index").reindex(columns=STATUS_ORDER).reset_index()
    E["final_status_by_class"] = fs
    # ------------------------------------------------ B. passenger behaviour
    ppb = bf.n_pax.value_counts().sort_index().rename("bookings").to_frame(); ppb["share"] = _share(ppb.bookings); E["passengers_per_booking"] = ppb.reset_index(names="passengers_in_booking")
    E["status_transition"] = pd.crosstab(pf.initial_status, pf.final_status).reset_index()
    E["by_class"] = _rate_by(pf, "travel_class"); E["by_age_band"] = _rate_by(pf, "age_band"); E["by_lead_bucket"] = _rate_by(pf, "lead_bucket")
    anyc = bf[bf.n_cancelled > 0]
    E["cancellation_shape"] = pd.DataFrame([dict(item="bookings with at least one cancelled passenger", bookings=len(anyc)), dict(item="of which every passenger cancelled (fully cancelled)", bookings=int((anyc.n_cancelled == anyc.n_pax).sum())),
                                            dict(item="of which partially cancelled", bookings=int((anyc.n_cancelled < anyc.n_pax).sum())), dict(item="bookings with 2+ passengers", bookings=int((bf.n_pax >= 2).sum())),
                                            dict(item="mixed-status bookings", bookings=int(bf.is_mixed.sum()))])
    mm = bf.assign(multi=bf.n_pax.clip(upper=6)).groupby("multi").agg(bookings=("booking_id", "size"), mixed=("is_mixed", "sum")).reset_index(); mm["mixed_share"] = mm.mixed / mm.bookings
    E["mixed_by_party_size"] = mm
    rac = pf.groupby("travel_class", observed=True).agg(passengers=("passenger_id", "size"), initial_rac=("initial_status", lambda s: (s == "RAC").sum()), final_rac=("final_status", lambda s: (s == "RAC").sum())).reset_index()
    rac["final_rac_share"] = rac.final_rac / rac.passengers; E["rac_by_class"] = rac
    # ------------------------------------------------ C. operations
    trn = rf.groupby(["train_id", "train_number", "train_name", "train_type", "route_name"], observed=True).agg(runs=("operation_id", "size"), passengers=("passengers", "sum"), booked=("booked_seats", "sum"), seats=("seats", "sum")).reset_index()
    trn["passengers_per_run"], trn["occupancy"] = trn.passengers / trn.runs, trn.booked / trn.seats
    ci = st.group_ratio_ci(rf, "train_id", "booked_seats", "seats", 500).rename(columns={"ci_low": "occ_ci_low", "ci_high": "occ_ci_high"})[["train_id", "occ_ci_low", "occ_ci_high"]]
    E["train_level"] = trn.merge(ci, on="train_id").merge(_otp(rf, "train_id"), on="train_id", how="left").drop(columns=["booked", "seats"])
    rt = rf.groupby("route_name").agg(runs=("operation_id", "size"), trains=("train_id", "nunique"), passengers=("passengers", "sum"), booked=("booked_seats", "sum"), seats=("seats", "sum")).reset_index()
    rt["passengers_per_run"], rt["occupancy"] = rt.passengers / rt.runs, rt.booked / rt.seats
    ci = st.group_ratio_ci(rf, "route_name", "booked_seats", "seats", 500).rename(columns={"ci_low": "occ_ci_low", "ci_high": "occ_ci_high"})[["route_name", "occ_ci_low", "occ_ci_high"]]
    E["route_level"] = rt.merge(ci, on="route_name").merge(_otp(rf, "route_name"), on="route_name", how="left").drop(columns=["booked", "seats"])
    cl = cf.groupby("travel_class", observed=True).agg(class_runs=("capacity_id", "size"), seats=("total_seats", "sum"), passengers=("passengers", "sum"), booked=("booked_seats", "sum"), confirmed=("confirmed_pax", "sum"),
                                                       wl_final=("wl_final_pax", "sum")).reset_index()
    cl["occupancy"], cl["confirmed_occupancy"], cl["waitlist_pressure"], cl["demand_per_seat"] = cl.booked / cl.seats, cl.confirmed / cl.seats, cl.wl_final / cl.seats, cl.passengers / cl.seats
    ci = st.group_ratio_ci(cf, "travel_class", "booked_seats", "total_seats", 500).rename(columns={"ci_low": "occ_ci_low", "ci_high": "occ_ci_high"})[["travel_class", "occ_ci_low", "occ_ci_high"]]
    E["class_level"] = cl.merge(ci, on="travel_class").drop(columns=["booked", "confirmed", "wl_final"])
    tt = rf.groupby("train_type", observed=True).agg(runs=("operation_id", "size"), passengers=("passengers", "sum"), booked=("booked_seats", "sum"), seats=("seats", "sum")).reset_index()
    tt["passengers_per_run"], tt["occupancy"] = tt.passengers / tt.runs, tt.booked / tt.seats
    E["train_type_level"] = tt.merge(_otp(rf, "train_type"), on="train_type", how="left").drop(columns=["booked", "seats"])
    od = cf.occupancy
    E["occupancy_distribution"] = pd.DataFrame([dict(measure="class-runs", value=len(od)), dict(measure="mean occupancy", value=od.mean()), dict(measure="median occupancy", value=od.median()), dict(measure="5th percentile", value=od.quantile(.05)),
                                                dict(measure="25th percentile", value=od.quantile(.25)), dict(measure="75th percentile", value=od.quantile(.75)), dict(measure="95th percentile", value=od.quantile(.95)),
                                                dict(measure="share of class-runs below 50% occupancy", value=(od < .5).mean()), dict(measure="share of class-runs at or above 95%", value=(od >= .95).mean()),
                                                dict(measure="share of class-runs with any uncleared waitlist", value=(cf.wl_final_pax > 0).mean())])
    # ------------------------------------------------ D. financial
    mv = monthly[["journey_month", "gross_value", "refund_total", "refund_passenger", "refund_system", "retained_charges", "net_value", "simulated_runs", "total_passengers", "avg_fare_per_passenger"]].copy()
    mv["gross_per_run"], mv["refund_per_run"], mv["net_per_run"] = mv.gross_value / mv.simulated_runs, mv.refund_total / mv.simulated_runs, mv.net_value / mv.simulated_runs
    mv["refund_share_of_gross"] = mv.refund_total / mv.gross_value
    E["monthly_value"] = mv
    E["fare_by_class"] = pd.concat([pd.DataFrame([st.describe(g.fare_amount)]).assign(travel_class=c) for c, g in pf.groupby("travel_class", observed=True)]).set_index("travel_class").reset_index()
    E["fare_by_age"] = pd.concat([pd.DataFrame([st.describe(g.fare_amount)]).assign(age_band=c) for c, g in pf.groupby("age_band", observed=True)]).set_index("age_band").reset_index()
    rt_ = ef.groupby(ef.cancellation_type.astype(str)).agg(events=("cancellation_id", "size"), passengers=("cancelled_passengers", "sum"), original=("original_fare_amount", "sum"), charge=("cancellation_charge", "sum"), refund=("refund_amount", "sum")).reset_index()
    rt_["charge_share"] = rt_.charge / rt_.original; E["refund_by_type"] = rt_
    E["fare_distribution"] = pd.DataFrame([dict(percentile=f"p{q}", fare_per_passenger_inr=pf.fare_amount.quantile(q / 100)) for q in (1, 5, 25, 50, 75, 95, 99)])
    # ------------------------------------------------ E. temporal
    E["mom_changes"] = monthly[["journey_month", "total_bookings", "bookings_growth", "bookings_per_run", "bookings_per_run_growth", "occupancy", "passenger_cancellation_rate"]].copy()
    sea = rf.groupby("season").agg(runs=("operation_id", "size"), passengers=("passengers", "sum"), booked=("booked_seats", "sum"), seats=("seats", "sum")).reset_index()
    sea["passengers_per_run"], sea["occupancy"] = sea.passengers / sea.runs, sea.booked / sea.seats; E["season_level"] = sea.merge(_otp(rf, "season"), on="season", how="left").drop(columns=["booked", "seats"])
    pk = rf.assign(period=np.where(rf.is_peak, "Peak travel period", "Other days")).groupby("period").agg(runs=("operation_id", "size"), passengers=("passengers", "sum"), booked=("booked_seats", "sum"), seats=("seats", "sum")).reset_index()
    pk["passengers_per_run"], pk["occupancy"] = pk.passengers / pk.runs, pk.booked / pk.seats; E["peak_level"] = pk.drop(columns=["booked", "seats"])
    cm = rf.assign(month_number=rf.run_date.dt.month).groupby("month_number").agg(runs=("operation_id", "size"), passengers=("passengers", "sum"), booked=("booked_seats", "sum"), seats=("seats", "sum")).reset_index()
    cm["passengers_per_run"], cm["occupancy"] = cm.passengers / cm.runs, cm.booked / cm.seats; E["calendar_month_level"] = cm.drop(columns=["booked", "seats"])
    return E


# ------------------------------------------------------------------ markdown rendering
def md_table(df: pd.DataFrame, fmt: dict | None = None, max_rows: int | None = None) -> str:
    fmt = fmt or {}
    d = df.head(max_rows) if max_rows else df
    def cell(c, v):
        if pd.isna(v):
            return ""
        if c in fmt:
            return fmt[c].format(v)
        if isinstance(v, (float, np.floating)):
            return f"{v:,.4f}" if abs(v) < 10 else f"{v:,.1f}"
        if isinstance(v, (int, np.integer)):
            return f"{v:,}"
        return str(v)
    head = "| " + " | ".join(map(str, d.columns)) + " |"; sep = "|" + "|".join("---" for _ in d.columns) + "|"
    body = ["| " + " | ".join(cell(c, v) for c, v in zip(d.columns, row)) + " |" for row in d.itertuples(index=False)]
    return "\n".join([head, sep, *body])


def eda_markdown(E: dict, kpis: dict, stats: dict) -> str:
    pct, p1 = "{:.1%}", "{:.3f}"
    md = E["monthly_demand"]; hi, lo = md.loc[md.bookings_per_run.idxmax()], md.loc[md.bookings_per_run.idxmin()]
    we = E["weekend_vs_weekday"].set_index("day_type"); bs = E["booking_status_mix"].set_index("booking_status"); ps = E["passenger_status_mix"].set_index("status")
    cls = E["by_class"].set_index("travel_class"); sh = E["cancellation_shape"].set_index("item").bookings; mm = E["mixed_by_party_size"]
    wlc = E["by_class"]; od = E["occupancy_distribution"].set_index("measure").value
    tr = E["train_level"]; rt = E["route_level"]; cl = E["class_level"]; mv = E["monthly_value"]; fq = E["fare_distribution"].set_index("percentile").fare_per_passenger_inr
    sea = E["season_level"].set_index("season"); pk = E["peak_level"].set_index("period"); mom = E["mom_changes"]
    tops = tr.sort_values("occupancy", ascending=False)
    k = kpis
    L = ["# Phase 5: Exploratory data analysis summary", "",
         "> **Synthetic data, sampled simulation.** 768 simulated train runs (32 per month) compared with 19,708 scheduled runs in the modelled schedule (3.9%). These results describe this dataset only: they are not IRCTC or Indian Railways network-wide figures, and nothing here is a forecast. Months are compared with per-run and capacity-normalised measures because raw monthly totals reflect the sampling design. Associations are not causes.",
         "", f"**Dataset analysed (full cleaned data):** {k['total_bookings']:,} bookings, {k['total_passengers']:,} passengers, {int(sh['bookings with at least one cancelled passenger']):,} bookings with a cancellation, {k['class_runs']:,} simulated train-class runs, {k['simulated_runs']:,} simulated runs, 24 months (2024-09 to 2026-08).", "",
         "## A. Booking demand", "", "### Monthly demand (per simulated run)", "",
         md_table(md, {"bookings_growth": pct, "bookings_per_run_growth": pct, "bookings_per_run": "{:,.1f}", "passengers_per_run": "{:,.1f}"}), "",
         f"**Observed:** bookings per simulated run range from {lo.bookings_per_run:,.1f} ({lo.journey_month}) to {hi.bookings_per_run:,.1f} ({hi.journey_month}). Raw monthly totals are shown only for completeness: with a fixed 32 runs per month they mostly reflect which trains were sampled.", "",
         "### Weekday and weekend", "", md_table(E["weekday_demand"][["weekday", "runs", "bookings_per_run", "passengers_per_run", "occupancy"]], {"occupancy": p1}), "",
         md_table(E["weekend_vs_weekday"][["day_type", "runs", "passengers_per_run", "occupancy"]], {"occupancy": p1}), "",
         f"**Observed:** weekend-day runs average {we.loc['Weekend (Sat-Sun)', 'passengers_per_run']:,.1f} passengers per run against {we.loc['Weekday (Mon-Fri)', 'passengers_per_run']:,.1f} on weekdays (occupancy {we.loc['Weekend (Sat-Sun)', 'occupancy']:.1%} vs {we.loc['Weekday (Mon-Fri)', 'occupancy']:.1%}); see test S-01 for whether the gap is distinguishable from zero.", "",
         "### Status mix", "", md_table(E["booking_status_mix"], {"share": pct}), "", md_table(E["passenger_status_mix"], {"initial_share": pct, "final_share": pct}), "",
         f"**Observed:** {bs.loc['Confirmed', 'share']:.1%} of bookings finished fully Confirmed, {bs.loc['Cancelled', 'share']:.1%} fully Cancelled and {bs.loc['Mixed', 'share']:.1%} Mixed. By passenger, {ps.loc['Confirmed', 'final_share']:.1%} finished Confirmed, {ps.loc['RAC', 'final_share']:.1%} RAC, {ps.loc['Waitlisted', 'final_share']:.1%} Waitlisted and {ps.loc['Cancelled', 'final_share']:.1%} Cancelled; {ps.loc['Waitlisted', 'initial_share']:.1%} were waitlisted when booking.", "",
         "## B. Passenger behaviour", "", "### Cancellation, waitlist and RAC by class (passenger-based)", "",
         md_table(wlc[["travel_class", "passengers", "cancellation_rate", "cancel_ci_low", "cancel_ci_high", "initial_wl_share", "wl_clearance_rate", "uncleared_share_of_wl_demand"]],
                  {c: pct for c in ("cancellation_rate", "cancel_ci_low", "cancel_ci_high", "initial_wl_share", "wl_clearance_rate", "uncleared_share_of_wl_demand")}), "",
         f"**Observed:** the passenger cancellation rate is {k['passenger_cancellation_rate']:.1%} overall, from {cls.cancellation_rate.min():.1%} ({cls.cancellation_rate.idxmin()}) to {cls.cancellation_rate.max():.1%} ({cls.cancellation_rate.idxmax()}). Of {k['wl_demand']:,} passengers waitlisted at booking, {k['wl_clearance_rate']:.1%} cleared to Confirmed or RAC and {k['wl_uncleared']:,} were refunded by the System as uncleared.", "",
         "### Cancellation by lead time and age band", "", md_table(E["by_lead_bucket"][["lead_bucket", "passengers", "cancellation_rate", "cancel_ci_low", "cancel_ci_high"]], {c: pct for c in ("cancellation_rate", "cancel_ci_low", "cancel_ci_high")}), "",
         md_table(E["by_age_band"][["age_band", "passengers", "cancellation_rate"]], {"cancellation_rate": pct}), "",
         "### Booking shape: party size, partial cancellation, mixed status", "", md_table(E["passengers_per_booking"], {"share": pct}), "", md_table(E["cancellation_shape"]), "", md_table(mm, {"mixed_share": pct}), "",
         f"**Observed:** {int(sh['of which partially cancelled']):,} bookings were partially cancelled; mixed-status bookings ({k['mixed_bookings']:,}) can only occur with two or more passengers, where they are {k['mixed_bookings'] / int(sh['bookings with 2+ passengers']):.1%} of such bookings.", "",
         "## C. Operations", "", "### Class performance (capacity utilisation and demand per available seat)", "",
         md_table(cl, {"occupancy": p1, "confirmed_occupancy": p1, "waitlist_pressure": p1, "demand_per_seat": p1, "occ_ci_low": p1, "occ_ci_high": p1}), "",
         f"**Observed:** seat occupancy is {k['occupancy']:.1%} overall (Confirmed {k['confirmed_occupancy']:.1%} + RAC {k['rac_occupancy']:.1%} of seat supply); waitlist pressure is {k['waitlist_pressure']:.1%}. `demand_per_seat` (all requested passengers per seat, {k['demand_per_seat']:.2f}) is an exploratory measure, not an approved KPI.", "",
         "### Class-run occupancy distribution", "", md_table(E["occupancy_distribution"], {"value": "{:,.3f}"}), "",
         f"**Observed:** the median class-run is {od['median occupancy']:.1%} occupied; {od['share of class-runs at or above 95%']:.1%} of class-runs are at or above 95% and {od['share of class-runs below 50% occupancy']:.1%} are below 50%.", "",
         "### Train level (every train has 9 to 20 simulated runs)", "", "Highest occupancy:", "", md_table(tops.head(8)[["train_number", "train_name", "runs", "passengers_per_run", "occupancy", "occ_ci_low", "occ_ci_high", "otp"]], {"occupancy": p1, "occ_ci_low": p1, "occ_ci_high": p1, "otp": pct}), "",
         "Lowest occupancy:", "", md_table(tops.tail(5)[["train_number", "train_name", "runs", "passengers_per_run", "occupancy", "occ_ci_low", "occ_ci_high", "otp"]], {"occupancy": p1, "occ_ci_low": p1, "occ_ci_high": p1, "otp": pct}), "",
         "### Route level and train type", "", md_table(rt.sort_values("passengers_per_run", ascending=False).head(8)[["route_name", "runs", "trains", "passengers_per_run", "occupancy", "otp"]], {"occupancy": p1, "otp": pct}), "",
         md_table(E["train_type_level"][["train_type", "runs", "passengers_per_run", "occupancy", "otp", "avg_delay"]], {"occupancy": p1, "otp": pct, "avg_delay": "{:.1f}"}), "",
         f"**Observed:** highest-occupancy train {tops.iloc[0].train_number} ({tops.iloc[0].occupancy:.1%}, {int(tops.iloc[0].runs)} runs) and lowest {tops.iloc[-1].train_number} ({tops.iloc[-1].occupancy:.1%}, {int(tops.iloc[-1].runs)} runs). Train-level intervals are wide because each train has only 9 to 20 simulated runs; rankings are indicative, not definitive.", "",
         "## D. Financial analysis (INR; booking value, not revenue or profit)", "", md_table(mv[["journey_month", "gross_value", "refund_total", "net_value", "gross_per_run", "refund_share_of_gross", "avg_fare_per_passenger"]],
                                                                                           {"gross_value": "{:,.0f}", "refund_total": "{:,.0f}", "net_value": "{:,.0f}", "gross_per_run": "{:,.0f}", "refund_share_of_gross": pct, "avg_fare_per_passenger": "{:,.1f}"}), "",
         md_table(E["refund_by_type"], {"original": "{:,.0f}", "charge": "{:,.0f}", "refund": "{:,.0f}", "charge_share": pct}), "",
         md_table(E["fare_by_class"][["travel_class", "n", "mean", "median", "std", "p5", "p95"]], {"n": "{:,.0f}", "mean": "{:,.0f}", "median": "{:,.0f}", "std": "{:,.0f}", "p5": "{:,.0f}", "p95": "{:,.0f}"}), "",
         f"**Observed:** gross booking value INR {k['gross_value']:,.0f}; refunds INR {k['refund_total']:,.0f} ({k['refund_total'] / k['gross_value']:.1%} of gross; Passenger events INR {k['refund_passenger']:,.0f}, System auto-refunds INR {k['refund_system']:,.0f}); net booking value INR {k['net_value']:,.0f}; retained charges INR {k['retained_charges']:,.0f}. Average fare per passenger INR {k['avg_fare_per_passenger']:,.2f}; the fare distribution is right-skewed (median INR {fq['p50']:,.0f}, 95th percentile INR {fq['p95']:,.0f}, 99th INR {fq['p99']:,.0f}). Fares come from an illustrative synthetic formula (distance, class, age).", "",
         "## E. Temporal analysis (only the 24 simulated months)", "",
         md_table(mom, {"bookings_growth": pct, "bookings_per_run_growth": pct, "bookings_per_run": "{:,.1f}", "occupancy": pct, "passenger_cancellation_rate": pct}), "",
         md_table(E["season_level"], {"occupancy": p1, "otp": pct, "avg_delay": "{:.1f}", "passengers_per_run": "{:,.1f}"}), "", md_table(E["peak_level"], {"occupancy": p1, "passengers_per_run": "{:,.1f}"}), "",
         md_table(E["calendar_month_level"], {"occupancy": p1, "passengers_per_run": "{:,.1f}"}), "",
         f"**Observed:** month-over-month change in bookings per run ranges from {mom.bookings_per_run_growth.min():+.1%} to {mom.bookings_per_run_growth.max():+.1%}. Peak-travel-period runs average {pk.loc['Peak travel period', 'passengers_per_run']:,.1f} passengers vs {pk.loc['Other days', 'passengers_per_run']:,.1f} on other days (occupancy {pk.loc['Peak travel period', 'occupancy']:.1%} vs {pk.loc['Other days', 'occupancy']:.1%}). With only two observations of each calendar month, seasonal patterns here describe these two simulated years, not a stable seasonal cycle.", "",
         "## Statistical highlights", "", "Full results (question, metric, method, effect size, interpretation, limitation): `reports/phase5_statistical_results.csv` and notebook 04.", "",
         md_table(stats["tests"][["test_id", "metric", "result"]]), "",
         "## Limitations", "", "* Synthetic, sampled simulation (768 of 19,708 scheduled runs): findings illustrate method and the simulation's built-in behaviour; they say nothing about real passengers or the real network.",
         "* Passengers cluster within bookings and runs; intervals that assume independence (Wilson) are narrower than cluster-aware ones.", "* No forecasts are produced; the trend slope in S-08 describes the 24 simulated months only."]
    return "\n".join(L) + "\n"
