"""Matplotlib charts (16) for the Phase 5 analysis. Every chart has a title, labelled axes with units, legends where several series appear, an interpretation line
computed from the data, and a footer stating that the data is synthetic and sampled. Design rules against misleading charts: bars and rates start at zero,
months are compared on per-run measures (never raw totals alone), no dual axes, uncertainty is shown where groups are small, rankings show their run counts."""
from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, PercentFormatter

from . import SYNTHETIC_NOTE
from . import statistics as st

BLUE, ORANGE, GREEN, RED, PURPLE, SKY, GREY = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#6b6b6b"
STATUS_COLOURS = {"Confirmed": GREEN, "RAC": SKY, "Waitlisted": ORANGE, "Cancelled": RED, "Mixed": PURPLE}
CLASS_ORDER = ["1A", "2A", "3A", "SL", "CC", "2S"]
SEASONS = ["Winter", "Summer", "Monsoon", "Post-Monsoon"]
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25, "axes.axisbelow": True, "figure.dpi": 100, "savefig.dpi": 130})


def _finish(fig, out_dir: Path, name: str, title: str, subtitle: str, interpretation: str, source: str, xlabel: str, ylabel: str, top: float = 0.90) -> dict:
    fig.suptitle(title, x=0.012, y=0.985, ha="left", fontsize=14, fontweight="bold")
    fig.text(0.012, 0.935, subtitle, ha="left", fontsize=9.5, color=GREY)
    wrapped = "\n".join(textwrap.wrap("Reading the chart: " + interpretation, 170))
    fig.text(0.012, 0.045, wrapped, ha="left", va="bottom", fontsize=9, color="#222")
    fig.text(0.012, 0.008, SYNTHETIC_NOTE, ha="left", fontsize=7.5, color=GREY, style="italic")
    fig.tight_layout(rect=[0, 0.11, 1, top])
    path = out_dir / f"{name}.png"
    fig.savefig(path); plt.close(fig)
    return dict(file=path.name, title=title, x_axis=xlabel, y_axis=ylabel, interpretation=interpretation, data_source=source)


def _months(ax, labels):
    ax.set_xticks(range(0, len(labels), 2)); ax.set_xticklabels(labels[::2], rotation=45, ha="right"); ax.set_xlabel("Journey month")


def _pct(ax, axis="y", dec=0):
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(PercentFormatter(1.0, decimals=dec))


def build_all(facts: dict, monthly: pd.DataFrame, E: dict, S: dict, out_dir: Path) -> list[dict]:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()
    pf, bf, cf, rf = (facts[k] for k in ("passenger_fact", "booking_fact", "class_run_fact", "run_fact"))
    m = monthly.copy(); x = np.arange(len(m)); ml = list(m.journey_month); cat = []
    SRC = "data/processed/cleaned (full dataset), Phase 5 cleaning pipeline"

    # 01 monthly demand
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7.4), sharex=True, gridspec_kw=dict(height_ratios=[2, 1]))
    a1.plot(x, m.bookings_per_run, marker="o", color=BLUE, lw=2); a1.set_ylim(0, m.bookings_per_run.max() * 1.15); a1.set_ylabel("Bookings per simulated run"); a1.set_title("Bookings per simulated run (primary measure)", loc="left", fontsize=10)
    a1.axhline(m.total_bookings.sum() / m.simulated_runs.sum(), color=GREY, ls="--", lw=1, label=f"24-month average {m.total_bookings.sum() / m.simulated_runs.sum():.0f}"); a1.legend(loc="upper left", frameon=False)
    a2.bar(x, m.total_bookings, color=SKY); a2.set_ylabel("Bookings (raw total)"); a2.set_title("Raw monthly bookings: 32 runs are simulated every month by design", loc="left", fontsize=10); a2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:.0f}k")); _months(a2, ml)
    hi, lo = m.loc[m.bookings_per_run.idxmax()], m.loc[m.bookings_per_run.idxmin()]
    cat.append(_finish(fig, out_dir, "01_monthly_demand_trend", "Monthly booking demand", "Bookings per simulated run, and raw bookings per month (24 months, Sep 2024 to Aug 2026)",
                       f"Demand per run ranges from {lo.bookings_per_run:.0f} ({lo.journey_month}) to {hi.bookings_per_run:.0f} ({hi.journey_month}). Compare months on the top panel: the raw totals below mostly reflect which 32 runs were sampled.", SRC, "Journey month", "Bookings (per run / raw)"))
    # 02 passenger trend by final status per run
    fig, ax = plt.subplots(figsize=(11, 6.2))
    stat = pf.groupby(["journey_month", "final_status"], observed=True).size().unstack(fill_value=0).reindex(ml)
    bottom = np.zeros(len(m))
    for s in ["Confirmed", "RAC", "Waitlisted", "Cancelled"]:
        v = stat[s].to_numpy() / m.simulated_runs.to_numpy(); ax.bar(x, v, bottom=bottom, color=STATUS_COLOURS[s], label=s, width=0.8); bottom += v
    ax.set_ylabel("Passengers per simulated run"); ax.legend(ncol=4, loc="upper left", frameon=False, title="Final status"); ax.set_ylim(0, bottom.max() * 1.18); _months(ax, ml)
    mx = m.loc[m.passengers_per_run.idxmax()]
    cat.append(_finish(fig, out_dir, "02_passenger_trend", "Passenger volume per simulated run, by final status", "Stacked passengers per simulated run for each journey month",
                       f"Passengers per run peak at {mx.passengers_per_run:.0f} in {mx.journey_month}. Confirmed passengers are the largest block every month; Cancelled and Waitlisted passengers hold no seat at departure.", SRC, "Journey month", "Passengers per simulated run"))
    # 03 cancellation trend
    fig, ax = plt.subplots(figsize=(11, 6.2))
    ci = np.array([st.wilson_ci(k, n) for k, n in zip(m.cancelled_passengers, m.total_passengers)])
    ax.fill_between(x, ci[:, 0], ci[:, 1], color=BLUE, alpha=0.2, label="95% interval (passenger-based, assumes independence)")
    ax.plot(x, m.passenger_cancellation_rate, marker="o", color=BLUE, lw=2, label="Passenger cancellation rate (cancelled / total passengers)")
    ax.plot(x, m.booking_cancellation_rate, marker="s", color=ORANGE, lw=2, label="Booking-based cancellation rate (fully cancelled / bookings)")
    ax.set_ylim(0, max(m.passenger_cancellation_rate.max(), m.booking_cancellation_rate.max()) * 1.4); _pct(ax); ax.set_ylabel("Cancellation rate"); ax.legend(loc="upper left", frameon=False, fontsize=8.5); _months(ax, ml)
    cat.append(_finish(fig, out_dir, "03_cancellation_trend", "Cancellation rate by journey month", "Two approved definitions with different denominators: passengers and bookings",
                       f"Both rates move together around {m.passenger_cancellation_rate.mean():.1%} (passenger-based, range {m.passenger_cancellation_rate.min():.1%} to {m.passenger_cancellation_rate.max():.1%}). The booking-based rate is lower because partially cancelled bookings are not counted as cancelled.", SRC, "Journey month", "Cancellation rate (share)"))
    # 04 waitlist trend
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7.4), sharex=True)
    a1.plot(x, m.wl_demand / m.total_passengers, marker="o", color=ORANGE, lw=2); a1.set_ylim(0, (m.wl_demand / m.total_passengers).max() * 1.4); _pct(a1); a1.set_ylabel("Share of all passengers"); a1.set_title("Initial waitlist demand: passengers waitlisted at booking time", loc="left", fontsize=10)
    a2.plot(x, m.wl_clearance_rate, marker="o", color=GREEN, lw=2, label="Cleared to Confirmed or RAC"); a2.plot(x, m.wl_uncleared / m.wl_demand, marker="s", color=RED, lw=2, label="Uncleared (refunded by the System)")
    a2.set_ylim(0, 1); _pct(a2); a2.set_ylabel("Share of initial waitlist demand"); a2.legend(loc="center right", frameon=False); a2.set_title("What happened to waitlisted passengers (the rest cancelled while waiting)", loc="left", fontsize=10); _months(a2, ml)
    cat.append(_finish(fig, out_dir, "04_waitlist_trend", "Waitlist demand, clearance and uncleared waitlist", "Denominators: all passengers (top); initially waitlisted passengers (bottom)",
                       f"About {k_ if (k_ := (m.wl_demand.sum() / m.total_passengers.sum())) else 0:.1%} of passengers start waitlisted; only {m.wl_cleared.sum() / m.wl_demand.sum():.1%} clear to a seat, and {m.wl_uncleared.sum() / m.wl_demand.sum():.1%} are still waitlisted at chart preparation and refunded.", SRC, "Journey month", "Share of passengers / of waitlist demand"))
    # 05 occupancy trend
    fig, ax = plt.subplots(figsize=(11, 6.2))
    ax.plot(x, m.occupancy, marker="o", color=BLUE, lw=2.2, label="Seat occupancy (Confirmed + 0.5 x RAC)"); ax.plot(x, m.confirmed_occupancy, marker=".", color=GREEN, lw=1.6, label="Confirmed passengers only")
    ax.plot(x, m.waitlist_pressure, marker="s", color=ORANGE, lw=1.6, label="Waitlist pressure (uncleared waitlisted / seats; holds no seat)")
    ax.axhline(1.0, color=RED, ls=":", lw=1); ax.text(0.2, 1.01, "100% of seat supply", color=RED, fontsize=8); ax.set_ylim(0, 1.1); _pct(ax); ax.set_ylabel("Share of seat supply"); ax.legend(loc="lower left", frameon=False, fontsize=8.5); _months(ax, ml)
    cat.append(_finish(fig, out_dir, "05_occupancy_trend", "Seat occupancy and waitlist pressure by journey month", "Capacity-normalised: passengers per available seat of the same simulated train-class runs",
                       f"Occupancy averages {m.booked_seats.sum() / m.seat_supply.sum():.1%} and ranges {m.occupancy.min():.1%} to {m.occupancy.max():.1%}; it never exceeds 100% because waitlisted passengers are excluded and shown separately as pressure.", SRC, "Journey month", "Share of seat supply"))
    # 06 gross, refund, net
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 6.2))
    for col, lab, c in (("gross_value", "Gross booking value", BLUE), ("net_value", "Net booking value", GREEN), ("refund_total", "Refunds", RED)):
        a1.plot(x, m[col] / 1e6, marker="o", ms=3.5, lw=2, color=c, label=lab); a2.plot(x, m[col] / m.simulated_runs / 1e3, marker="o", ms=3.5, lw=2, color=c, label=lab)
    for a, t, yl in ((a1, "Monthly totals", "INR million"), (a2, "Per simulated run", "INR thousand per run")):
        a.set_ylim(0, None); a.set_title(t, loc="left", fontsize=10); a.set_ylabel(yl); _months(a, ml)
    a1.legend(loc="upper left", frameon=False, fontsize=8.5)
    cat.append(_finish(fig, out_dir, "06_value_trend_gross_refund_net", "Gross, refund and net booking value (INR)", "Booking value is not revenue or profit; per-run view removes the sampling effect",
                       f"Refunds are {m.refund_total.sum() / m.gross_value.sum():.1%} of gross booking value overall, so net is {m.net_value.sum() / m.gross_value.sum():.1%} of gross. Month-to-month swings in totals follow demand per run and the mix of sampled trains.", SRC, "Journey month", "INR (million; thousand per run)"))
    # 07 train performance
    tr = E["train_level"].sort_values("occupancy"); sel = pd.concat([tr.head(8), tr.tail(8)])
    fig, ax = plt.subplots(figsize=(11, 7.2)); y = np.arange(len(sel))
    cols = [RED if i < 8 else GREEN for i in range(len(sel))]
    ax.barh(y, sel.occupancy, color=cols, alpha=0.85); ax.errorbar(sel.occupancy, y, xerr=[sel.occupancy - sel.occ_ci_low, sel.occ_ci_high - sel.occupancy], fmt="none", ecolor="#222", capsize=3, lw=1)
    ax.set_yticks(y); ax.set_yticklabels([f"{r.train_number}  {r.train_name[:34]} ({int(r.runs)} runs)" for r in sel.itertuples()], fontsize=8.5)
    ax.axvline(m.booked_seats.sum() / m.seat_supply.sum(), color=GREY, ls="--", lw=1, label="all-train occupancy"); ax.bar(0, 0, color=RED, alpha=0.85, label="8 lowest-occupancy trains"); ax.bar(0, 0, color=GREEN, alpha=0.85, label="8 highest-occupancy trains"); ax.set_xlim(0, 1.05); _pct(ax, "x"); ax.set_xlabel("Seat occupancy (bars: estimate; whiskers: 95% bootstrap interval over the train's simulated runs)"); ax.grid(axis="y", alpha=0); ax.legend(loc="lower right", frameon=False, fontsize=8.5)
    cat.append(_finish(fig, out_dir, "07_train_performance", "Train performance: the 8 lowest and 8 highest seat occupancy", "Each train has only 9 to 20 simulated runs, so intervals are wide",
                       f"Occupancy ranges from {tr.occupancy.min():.1%} to {tr.occupancy.max():.1%} across {len(tr)} trains. Intervals of neighbouring trains overlap, so the exact ranking is indicative only; the gap between the two ends is large.", SRC, "Seat occupancy", "Train (number, name, simulated runs)", top=0.87))
    # 08 route performance
    rt = E["route_level"].sort_values("passengers_per_run", ascending=False).head(15).iloc[::-1]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 7), sharey=True); y = np.arange(len(rt))
    a1.barh(y, rt.passengers_per_run, color=BLUE, alpha=0.85); a1.set_xlabel("Passengers per simulated run"); a1.set_yticks(y); a1.set_yticklabels([f"{r.route_name[:30]} ({int(r.runs)} runs)" for r in rt.itertuples()], fontsize=8.5)
    a2.barh(y, rt.occupancy, color=GREEN, alpha=0.85); a2.errorbar(rt.occupancy, y, xerr=[rt.occupancy - rt.occ_ci_low, rt.occ_ci_high - rt.occupancy], fmt="none", ecolor="#222", capsize=3, lw=1); a2.set_xlim(0, 1.05); _pct(a2, "x"); a2.set_xlabel("Seat occupancy (95% bootstrap interval)")
    for a in (a1, a2):
        a.grid(axis="y", alpha=0)
    cat.append(_finish(fig, out_dir, "08_route_performance", "Route performance: the 15 routes with the most passengers per simulated run", "Demand per run (left) and seat occupancy (right); run counts in the labels",
                       f"Busiest routes carry {rt.passengers_per_run.max():.0f} passengers per run, versus {E['route_level'].passengers_per_run.median():.0f} for the median route. High demand per run does not always mean high occupancy: routes also differ in seats per run.", SRC, "Passengers per run / occupancy", "Route (simulated runs)", top=0.87))
    # 09 class performance
    cl = E["class_level"].set_index("travel_class").reindex(CLASS_ORDER); bc = E["by_class"].set_index("travel_class").reindex(CLASS_ORDER)
    fig, axes = plt.subplots(1, 3, figsize=(13, 5.8)); xc = np.arange(len(CLASS_ORDER))
    axes[0].bar(xc, cl.occupancy, color=BLUE); axes[0].errorbar(xc, cl.occupancy, yerr=[cl.occupancy - cl.occ_ci_low, cl.occ_ci_high - cl.occupancy], fmt="none", ecolor="#222", capsize=3); axes[0].set_title("Seat occupancy", loc="left", fontsize=10); axes[0].set_ylim(0, 1.0)
    axes[1].bar(xc, cl.waitlist_pressure, color=ORANGE); axes[1].set_title("Waitlist pressure (uncleared / seats)", loc="left", fontsize=10)
    axes[2].bar(xc, bc.cancellation_rate, color=RED); axes[2].errorbar(xc, bc.cancellation_rate, yerr=[bc.cancellation_rate - bc.cancel_ci_low, bc.cancel_ci_high - bc.cancellation_rate], fmt="none", ecolor="#222", capsize=3); axes[2].set_title("Passenger cancellation rate", loc="left", fontsize=10)
    for a, v in zip(axes, (cl.occupancy, cl.waitlist_pressure, bc.cancellation_rate)):
        a.set_xticks(xc); a.set_xticklabels([f"{c}\nn={int(cl.class_runs[c])}" for c in CLASS_ORDER], fontsize=8.5); a.set_xlabel("Travel class (n = simulated class-runs)", fontsize=9); _pct(a); a.set_ylabel("Share"); a.set_ylim(0, max(1.0 if a is axes[0] else 0, v.max() * 1.25))
        for i, val in enumerate(v):
            a.text(i, a.get_ylim()[1] * 0.015, f"{val:.0%}" if a is axes[0] else f"{val:.1%}", ha="center", va="bottom", fontsize=8.5, color="white", fontweight="bold")
    best, worst = cl.occupancy.idxmax(), cl.occupancy.idxmin()
    cat.append(_finish(fig, out_dir, "09_class_performance", "Class performance: occupancy, waitlist pressure and cancellation by travel class", "Whiskers: 95% intervals (bootstrap over class-runs; Wilson for rates)",
                       f"Occupancy is highest in {best} ({cl.occupancy[best]:.1%}) and lowest in {worst} ({cl.occupancy[worst]:.1%}); cancellation is lowest in {bc.cancellation_rate.idxmin()} ({bc.cancellation_rate.min():.1%}). Classes differ in the number of simulated class-runs (labels).", SRC, "Travel class", "Share (of seats / of passengers)", top=0.86))
    # 10 status distribution
    fs = E["final_status_by_class"].set_index("travel_class").reindex(CLASS_ORDER); bs = E["booking_status_mix"].set_index("booking_status")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 6), gridspec_kw=dict(width_ratios=[1.4, 1])); left = np.zeros(len(CLASS_ORDER))
    for s in ["Confirmed", "RAC", "Waitlisted", "Cancelled"]:
        a1.barh(np.arange(len(CLASS_ORDER)), fs[s], left=left, color=STATUS_COLOURS[s], label=s)
        for i, v in enumerate(fs[s]):
            if v > 0.045:
                a1.text(left[i] + v / 2, i, f"{v:.0%}", ha="center", va="center", fontsize=8, color="white" if s in ("Confirmed", "Cancelled") else "black")
        left += fs[s].to_numpy()
    a1.set_yticks(np.arange(len(CLASS_ORDER))); a1.set_yticklabels(CLASS_ORDER); a1.invert_yaxis(); a1.set_xlim(0, 1); _pct(a1, "x"); a1.set_xlabel("Share of passengers (final status)"); a1.set_ylabel("Travel class"); a1.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.12), frameon=False, fontsize=8.5); a1.grid(axis="y", alpha=0)
    a2.bar(np.arange(len(bs)), bs.share, color=[STATUS_COLOURS[s] for s in bs.index]); a2.set_xticks(np.arange(len(bs))); a2.set_xticklabels(bs.index); _pct(a2); a2.set_ylabel("Share of bookings"); a2.set_xlabel("Booking status (roll-up of its passengers)")
    for i, v in enumerate(bs.share):
        a2.text(i, v, f"{v:.1%}", ha="center", va="bottom", fontsize=8.5)
    a2.set_ylim(0, bs.share.max() * 1.15)
    cat.append(_finish(fig, out_dir, "10_status_distribution", "Status distribution: passengers by class and bookings overall", "Final status at chart preparation; Mixed = the passengers of one booking ended with different statuses",
                       f"{bs.loc['Confirmed', 'share']:.1%} of bookings end fully Confirmed and {bs.loc['Mixed', 'share']:.1%} Mixed. Share of passengers who end Confirmed varies by class from {fs.Confirmed.min():.0%} to {fs.Confirmed.max():.0%}.", SRC, "Share", "Travel class / booking status", top=0.85))
    # 11 fare distribution
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 6.2), gridspec_kw=dict(width_ratios=[1.2, 1]))
    a1.hist(pf.fare_amount, bins=50, color=BLUE, alpha=0.85); med, p95 = pf.fare_amount.median(), pf.fare_amount.quantile(.95)
    a1.axvline(med, color=GREEN, lw=2, label=f"median INR {med:,.0f}"); a1.axvline(pf.fare_amount.mean(), color=ORANGE, lw=2, ls="--", label=f"mean INR {pf.fare_amount.mean():,.0f}"); a1.axvline(p95, color=RED, lw=1.5, ls=":", label=f"95th percentile INR {p95:,.0f}")
    a1.set_xlabel("Fare per passenger (INR)"); a1.set_ylabel("Passengers"); a1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:.0f}k")); a1.legend(frameon=False, fontsize=8.5)
    data = [pf.loc[pf.travel_class == c, "fare_amount"] for c in CLASS_ORDER]
    a2.boxplot(data, tick_labels=CLASS_ORDER, whis=(5, 95), showfliers=False, patch_artist=True, boxprops=dict(facecolor=SKY, alpha=0.7), medianprops=dict(color=RED, lw=2)); a2.set_xlabel("Travel class (box: quartiles; whiskers: 5th-95th percentile)"); a2.set_ylabel("Fare per passenger (INR)")
    cat.append(_finish(fig, out_dir, "11_fare_distribution", "Fare per passenger: distribution overall and by class", "405,200 passengers; INR; fares come from an illustrative synthetic formula",
                       f"The distribution is right-skewed: mean INR {pf.fare_amount.mean():,.0f} sits above the median INR {med:,.0f}, because premium classes and long routes pull the tail. Class explains much of the spread.", SRC, "Fare per passenger (INR) / class", "Passengers / fare (INR)"))
    # 12 weekday vs weekend
    wk = rf.groupby("weekday", observed=True); labs = list(wk.groups); wd = E["weekday_demand"]
    cip = [st.ratio_bootstrap_ci(g.passengers, np.ones(len(g)), 800) for _, g in wk]; cio = [st.ratio_bootstrap_ci(g.booked_seats, g.seats, 800) for _, g in wk]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 6)); xc = np.arange(len(labs)); colr = [ORANGE if d in ("Saturday", "Sunday") else BLUE for d in labs]
    for a, ci_, ttl, yl in ((a1, cip, "Passengers per simulated run", "Passengers per run"), (a2, cio, "Seat occupancy", "Share of seat supply")):
        est = np.array([c[0] for c in ci_]); a.bar(xc, est, color=colr); a.errorbar(xc, est, yerr=[est - [c[1] for c in ci_], [c[2] for c in ci_] - est], fmt="none", ecolor="#222", capsize=3)
        a.set_xticks(xc); a.set_xticklabels([f"{d[:3]}\n({n} runs)" for d, n in zip(labs, wd.runs)], fontsize=8.5); a.set_title(ttl, loc="left", fontsize=10); a.set_ylabel(yl); a.set_xlabel("Journey weekday (orange = weekend)")
    _pct(a2); a1.set_ylim(0, None); a2.set_ylim(0, 1)
    s1 = S["tests"].set_index("test_id").loc["S-01"]
    cat.append(_finish(fig, out_dir, "12_weekday_weekend_comparison", "Weekday and weekend comparison", "Passengers per simulated run and seat occupancy by journey weekday, with 95% bootstrap intervals over runs",
                       f"Weekend-day runs average {E['weekend_vs_weekday'].set_index('day_type').loc['Weekend (Sat-Sun)', 'passengers_per_run']:.0f} passengers vs {E['weekend_vs_weekday'].set_index('day_type').loc['Weekday (Mon-Fri)', 'passengers_per_run']:.0f} on weekdays, but intervals overlap widely: the gap is not statistically distinguishable from zero (test S-01, Welch p = {s1.p_value:.3f}; Mann-Whitney p is larger).", SRC, "Journey weekday", "Passengers per run / occupancy"))
    # 13 lead time vs cancellation
    lb = E["by_lead_bucket"]; ct = bf.groupby("lead_bucket", observed=True).agg(n=("booking_id", "size"), c=("booking_status", lambda s: (s.astype(str) == "Cancelled").sum())).reset_index(); bci = np.array([st.wilson_ci(c, n) for c, n in zip(ct.c, ct.n)]); br = ct.c / ct.n
    fig, ax = plt.subplots(figsize=(11, 6.2)); xb = np.arange(len(lb)); w = 0.38
    ax.bar(xb - w / 2, lb.cancellation_rate, w, color=BLUE, label="Passenger cancellation rate"); ax.errorbar(xb - w / 2, lb.cancellation_rate, yerr=[lb.cancellation_rate - lb.cancel_ci_low, lb.cancel_ci_high - lb.cancellation_rate], fmt="none", ecolor="#222", capsize=3)
    ax.bar(xb + w / 2, br, w, color=ORANGE, label="Booking-based cancellation rate"); ax.errorbar(xb + w / 2, br, yerr=[br - bci[:, 0], bci[:, 1] - br], fmt="none", ecolor="#222", capsize=3)
    ax.set_xticks(xb); ax.set_xticklabels([f"{b}\n({n:,} bookings)" for b, n in zip(lb.lead_bucket, ct.n)], fontsize=8.5); _pct(ax); ax.set_ylim(0, None); ax.set_xlabel("How far ahead the booking was made (lead time)"); ax.set_ylabel("Cancellation rate"); ax.legend(loc="upper left", frameon=False)
    s4 = S["tests"].set_index("test_id").loc["S-04"]
    cat.append(_finish(fig, out_dir, "13_lead_time_vs_cancellation", "Cancellation rate by booking lead time", "Both approved definitions, with 95% Wilson intervals",
                       f"Cancellation rises with lead time: booking-based {br.iloc[0]:.1%} (0-3 days) to {br.iloc[-1]:.1%} (61-120 days); chi-square test {'p < 0.001' if s4.p_value < 0.001 else f'p = {s4.p_value:.3f}'}, Cramer's V = {s4.effect_size:.2f} (small-to-moderate). This is an association in synthetic data built with such a pattern, not evidence that early booking causes cancellation.", SRC, "Lead-time bucket", "Cancellation rate (share)"))
    # 14 occupancy distribution
    fig, ax = plt.subplots(figsize=(11, 6.2)); od = cf.occupancy
    ax.hist(od, bins=np.linspace(0, 1, 21), color=BLUE, alpha=0.85, edgecolor="white"); ax.axvline(od.median(), color=GREEN, lw=2, label=f"median {od.median():.1%}"); ax.axvline(od.mean(), color=ORANGE, lw=2, ls="--", label=f"mean {od.mean():.1%}")
    ax.set_xlim(0, 1); _pct(ax, "x"); ax.set_xlabel("Seat occupancy of a simulated train-class run"); ax.set_ylabel("Number of train-class runs"); ax.legend(frameon=False)
    cat.append(_finish(fig, out_dir, "14_occupancy_distribution", "Distribution of seat occupancy across simulated train-class runs", f"{len(cf):,} train-class runs; bin width 5 percentage points",
                       f"{(od >= .95).mean():.1%} of class-runs are at or above 95% occupancy while {(od < .5).mean():.1%} are below 50%: the average ({od.mean():.1%}) hides a wide spread between full and under-used runs.", SRC, "Occupancy", "Number of class-runs"))
    # 15 correlation heatmap
    cm = S["correlation_matrix"]; fig, ax = plt.subplots(figsize=(8.8, 7))
    im = ax.imshow(cm.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1); ax.set_xticks(range(len(cm))); ax.set_xticklabels(cm.columns, rotation=40, ha="right", fontsize=8.5); ax.set_yticks(range(len(cm))); ax.set_yticklabels(cm.index, fontsize=8.5); ax.grid(False)
    for i in range(len(cm)):
        for j in range(len(cm)):
            ax.text(j, i, f"{cm.iat[i, j]:.2f}", ha="center", va="center", fontsize=9, color="white" if abs(cm.iat[i, j]) > 0.6 else "black")
    fig.colorbar(im, ax=ax, shrink=0.8, label="Spearman rank correlation")
    cp = S["correlation_pairs"]; top = cp.loc[cp.rho.abs().idxmax()]; dl = cp[(cp.variable_1.str.contains("delay")) | (cp.variable_2.str.contains("delay"))].rho.abs().max()
    cat.append(_finish(fig, out_dir, "15_correlation_heatmap", "Correlation between run-level measures (Spearman)", f"{len(rf)} simulated runs; arrival delay uses the {rf.arrival_delay_min.notna().sum()} runs with a recorded value",
                       f"The strongest pair is {top.variable_1} / {top.variable_2} (rho = {top.rho:.2f}); several links are mechanical (occupancy is built from passengers and seats). Arrival delay is essentially uncorrelated with demand (|rho| <= {dl:.2f}). Correlation is not causation.", SRC, "Measure", "Measure", top=0.87))
    # 16 delay / OTP by season
    ops = rf.dropna(subset=["arrival_delay_min"]).copy(); ops["d"] = ops.arrival_delay_min.astype(float); ops["ot"] = ops.on_time.astype(bool)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 6)); xs = np.arange(4)
    otp = [ops.loc[ops.season == s, "ot"] for s in SEASONS]; est = np.array([o.mean() for o in otp]); ci = np.array([st.wilson_ci(int(o.sum()), len(o)) for o in otp])
    a1.bar(xs, est, color=BLUE); a1.errorbar(xs, est, yerr=[est - ci[:, 0], ci[:, 1] - est], fmt="none", ecolor="#222", capsize=3); a1.set_xticks(xs); a1.set_xticklabels([f"{s}\n({len(o)} runs)" for s, o in zip(SEASONS, otp)], fontsize=8.5)
    _pct(a1); a1.set_ylim(0, 1); a1.set_ylabel("On-time performance (arrival delay <= 15 min)"); a1.set_xlabel("Season of journey"); a1.set_title("On-time share, 95% Wilson interval", loc="left", fontsize=10)
    a2.boxplot([ops.loc[ops.season == s, "d"] for s in SEASONS], tick_labels=SEASONS, whis=(5, 95), showfliers=False, patch_artist=True, boxprops=dict(facecolor=SKY, alpha=0.7), medianprops=dict(color=RED, lw=2))
    a2.axhline(15, color=GREY, ls="--", lw=1, label="15-minute on-time threshold"); a2.set_ylabel("Arrival delay (minutes)"); a2.set_xlabel("Season of journey (box: quartiles; whiskers: 5th-95th percentile)"); a2.set_title("Arrival delay distribution", loc="left", fontsize=10); a2.legend(frameon=False, fontsize=8.5)
    s6, s7 = S["tests"].set_index("test_id").loc["S-06"], S["tests"].set_index("test_id").loc["S-07"]
    cat.append(_finish(fig, out_dir, "16_delay_and_otp_by_season", "Punctuality by season", "Runs with a recorded arrival delay only (missing delays are excluded, never imputed)",
                       f"Overall on-time performance is {ops.ot.mean():.1%}. Seasonal differences are small: delay p = {s6.p_value:.2f} (Kruskal-Wallis), on-time share p = {s7.p_value:.2f} (chi-square), neither significant; with {min(len(o) for o in otp)} to {max(len(o) for o in otp)} runs per season, only large differences would be detectable.", SRC, "Season", "On-time share / delay (minutes)"))
    return cat
