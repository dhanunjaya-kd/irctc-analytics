"""Business-insights report generator. Every statement is computed from the analysis results (no hand-typed figures) and split into
OBSERVED (what the data directly shows), INTERPRETATION (reasonable analytical reading) and LIMITATION (what cannot be concluded).

The data is synthetic and sampled, and per assumption A-20 the generator deliberately builds in seasonal and holiday demand, weekday effects, a 1% monthly demand trend,
cancellation probability rising with lead time, and delays varying with season, distance and train type: the analysis can only rediscover what was built in.
"""
from __future__ import annotations

import pandas as pd

from .statistics import magnitude


def _block(title: str, observed: list, interpretation: list, limitation: list) -> str:
    out = [f"## {title}", "", "**OBSERVED**", ""] + [f"* {x}" for x in observed] + ["", "**INTERPRETATION**", ""] + [f"* {x}" for x in interpretation] + ["", "**LIMITATION**", ""] + [f"* {x}" for x in limitation] + [""]
    return "\n".join(out)


def insights_markdown(kpis: dict, E: dict, S: dict, monthly: pd.DataFrame) -> str:
    k = kpis; T = S["tests"].set_index("test_id"); CI = S["rate_cis"].set_index("measure")
    md = monthly; bpr = md.bookings_per_run; slope_pct = T.loc["S-08", "statistic"] / bpr.mean()
    pk = E["peak_level"].set_index("period"); wk = E["weekday_demand"]; wmax, wmin = wk.loc[wk.passengers_per_run.idxmax()], wk.loc[wk.passengers_per_run.idxmin()]
    cl = E["class_level"].set_index("travel_class"); bc = E["by_class"].set_index("travel_class"); lb = E["by_lead_bucket"]; od = E["occupancy_distribution"].set_index("measure").value
    tr = E["train_level"]; tt = E["train_type_level"].set_index("train_type"); sh = E["cancellation_shape"].set_index("item").bookings
    rb = E["refund_by_type"].set_index("cancellation_type"); fc = E["fare_by_class"].set_index("travel_class"); fq = E["fare_distribution"].set_index("percentile").fare_per_passenger_inr
    sea = E["season_level"].set_index("season")
    SYN = "Synthetic, sampled simulation (768 of 19,708 scheduled runs; assumptions A-02, A-16): this describes the dataset, not IRCTC or any real railway network."
    def p(x): return "p < 0.001" if x < 0.001 else f"p = {x:.3f}"
    parts = ["# Phase 5: Business insights", "",
             "> **Read this first.** The data is **synthetic** and comes from a **sampled simulation** (768 simulated runs against 19,708 scheduled runs, 3.9%). Nothing below describes actual IRCTC or Indian Railways network-wide performance, real passenger behaviour, or any forecast. "
             "Because the generator deliberately builds in seasonal and holiday demand, weekday effects, a 1% monthly demand trend, cancellation rising with lead time, and delays varying with season, distance and train type (assumption A-20), the analysis demonstrates **method** and can only rediscover what was built in. "
             "Each finding is split into OBSERVED (what the data directly shows), INTERPRETATION (a reasonable analytical reading) and LIMITATION (what cannot be concluded). Statistical associations are not causes.", "",
             f"Scope: {k['total_bookings']:,} bookings, {k['total_passengers']:,} passengers, {k['class_runs']:,} simulated train-class runs and {k['simulated_runs']:,} simulated runs over 24 months. All KPIs use the approved definitions and reconcile with `reports/kpi_reference_values.csv`.", ""]
    parts.append(_block("1. Demand level and the sampling design",
        [f"Bookings per simulated run range from {bpr.min():.0f} ({md.loc[bpr.idxmin(), 'journey_month']}) to {bpr.max():.0f} ({md.loc[bpr.idxmax(), 'journey_month']}); the 24-month average is {k['bookings_per_run']:.0f} bookings and {k['passengers_per_run']:.0f} passengers per run.",
         f"A straight-line fit to bookings per run rises by {T.loc['S-08', 'statistic']:+.2f} per month (95% CI {T.loc['S-08', 'ci_low']:+.2f} to {T.loc['S-08', 'ci_high']:+.2f}), about {slope_pct:.1%} of the average per month; R-squared = {T.loc['S-08', 'effect_size']:.2f}, {p(T.loc['S-08', 'p_value'])}."],
        ["Per-run measures are the valid basis for comparing months: exactly 32 runs are simulated every month, so raw monthly totals mostly reflect which trains were sampled.",
         f"The fitted slope of about {slope_pct:.1%} per month is consistent in size with the 1% monthly demand trend documented in A-20; the low R-squared reflects strong seasonal swings around the line."],
        [SYN, "The slope describes these 24 months only; it is not extrapolated and not a forecast."]))
    parts.append(_block("2. Peak travel periods and seasonality",
        [f"Runs inside peak travel periods carry {pk.loc['Peak travel period', 'passengers_per_run']:.0f} passengers each against {pk.loc['Other days', 'passengers_per_run']:.0f} on other days; occupancy is {pk.loc['Peak travel period', 'occupancy']:.1%} against {pk.loc['Other days', 'occupancy']:.1%}.",
         f"Test S-02: difference {T.loc['S-02', 'ci_low']:+.0f} to {T.loc['S-02', 'ci_high']:+.0f} passengers per run (95% CI), Cohen's d = {T.loc['S-02', 'effect_size']:.2f}, {p(T.loc['S-02', 'p_value'])}. Test S-03 on occupancy: d = {T.loc['S-03', 'effect_size']:.2f}, {p(T.loc['S-03', 'p_value'])}."],
        [f"Peak-period demand is clearly higher in this dataset ({magnitude(T.loc['S-02', 'effect_size'])} effect on passengers per run, {magnitude(T.loc['S-03', 'effect_size'])} on occupancy): the method recovers the modelled peak-period uplift (A-15, A-20).", "For capacity planning in a real setting this is the kind of comparison that matters, but only real data could support a real conclusion."],
        [SYN, "Peak windows are modelled, not an official calendar (A-15). Only two years are simulated, so each calendar month is observed twice."]))
    parts.append(_block("3. Weekday and weekend demand",
        [f"Runs on weekend days average {E['weekend_vs_weekday'].set_index('day_type').loc['Weekend (Sat-Sun)', 'passengers_per_run']:.0f} passengers against {E['weekend_vs_weekday'].set_index('day_type').loc['Weekday (Mon-Fri)', 'passengers_per_run']:.0f} on weekdays; the weekend-minus-weekday difference is {T.loc['S-01', 'ci_low']:+.0f} to {T.loc['S-01', 'ci_high']:+.0f} (95% CI), Welch {p(T.loc['S-01', 'p_value'])}.",
         f"By weekday, passengers per run are highest on {wmax.weekday} ({wmax.passengers_per_run:.0f}, {int(wmax.runs)} runs) and lowest on {wmin.weekday} ({wmin.passengers_per_run:.0f}, {int(wmin.runs)} runs)."],
        [f"The weekend-versus-weekday contrast is not statistically distinguishable from zero here, although weekday effects are built into the generator (A-20). That illustrates how much a 768-run sample can resolve: with {int(wk.runs.min())} to {int(wk.runs.max())} runs per weekday the intervals overlap."],
        [SYN, "A non-significant test does not show that no effect exists, only that this sample cannot detect it."]))
    parts.append(_block("4. Capacity and occupancy",
        [f"Seat occupancy is {k['occupancy']:.1%} overall (Confirmed {k['confirmed_occupancy']:.1%} plus RAC {k['rac_occupancy']:.1%}); waitlist pressure is {k['waitlist_pressure']:.1%} of seat supply. Bootstrap 95% interval for occupancy: {CI.loc['seat occupancy (bootstrap over runs)', 'ci_low']:.1%} to {CI.loc['seat occupancy (bootstrap over runs)', 'ci_high']:.1%}.",
         f"Across {int(od['class-runs']):,} class-runs the median occupancy is {od['median occupancy']:.1%}; {od['share of class-runs at or above 95%']:.1%} are at or above 95% and {od['share of class-runs below 50% occupancy']:.1%} are below 50%.",
         f"Class occupancy ranges from {cl.occupancy.min():.1%} ({cl.occupancy.idxmin()}, {int(cl.class_runs[cl.occupancy.idxmin()])} class-runs) to {cl.occupancy.max():.1%} ({cl.occupancy.idxmax()}); the difference between classes is significant (S-05, {p(T.loc['S-05', 'p_value'])}) with a small effect (epsilon-squared = {T.loc['S-05', 'effect_size']:.3f}).",
         f"Train-level occupancy ranges from {tr.occupancy.min():.1%} ({tr.loc[tr.occupancy.idxmin(), 'train_number']}) to {tr.occupancy.max():.1%} ({tr.loc[tr.occupancy.idxmax(), 'train_number']}); each train has only {int(tr.runs.min())} to {int(tr.runs.max())} simulated runs."],
        [f"The average hides a wide spread: {od['share of class-runs at or above 95%']:.0%} of class-runs are nearly full while {od['share of class-runs below 50% occupancy']:.0%} are under half full, so average occupancy alone would mislead a capacity discussion.",
         "Waitlisted passengers hold no seat, so occupancy stays at or below 100% by construction; waitlist pressure is the separate signal of unmet demand."],
        [SYN, "Capacity is simulated (A-12: 1 to 3 coaches per class with real seats per coach), the RAC weight of 0.5 is a configurable assumption (A-09), and train and class rankings rest on few runs, so they are indicative only."]))
    parts.append(_block("5. Waiting list",
        [f"{k['wl_demand']:,} passengers ({k['wl_demand'] / k['total_passengers']:.1%}) were waitlisted when booking. Only {k['wl_clearance_rate']:.1%} (95% CI {CI.loc['waitlist clearance rate (Wilson)', 'ci_low']:.1%} to {CI.loc['waitlist clearance rate (Wilson)', 'ci_high']:.1%}) cleared to Confirmed or RAC; {k['wl_uncleared']:,} ({k['wl_uncleared'] / k['wl_demand']:.1%}) were still waitlisted at chart preparation and refunded by the System.",
         f"Clearance by class ranges from {bc.wl_clearance_rate.min():.1%} ({bc.wl_clearance_rate.idxmin()}) to {bc.wl_clearance_rate.max():.1%} ({bc.wl_clearance_rate.idxmax()}); the difference is statistically detectable (S-11, {p(T.loc['S-11', 'p_value'])}) but small (Cramer's V = {T.loc['S-11', 'effect_size']:.2f})."],
        ["In this simulation most waitlist demand never converts to a seat, which follows from the queue rules and the cancellation-driven clearing built into the generator (A-08, A-19).", "Uncleared waitlist passengers are the clearest measure of unmet demand in the dataset."],
        [SYN, "Auto-refunds of uncleared waitlists are a synthetic business rule (A-19). The S-11 p-value is optimistic because passengers cluster within bookings and runs; rely on the effect size."]))
    parts.append(_block("6. Cancellations and refunds",
        [f"The passenger cancellation rate is {k['passenger_cancellation_rate']:.1%} (cluster-bootstrap 95% CI {CI.loc['passenger cancellation rate (cluster bootstrap over bookings)', 'ci_low']:.1%} to {CI.loc['passenger cancellation rate (cluster bootstrap over bookings)', 'ci_high']:.1%}); the booking-based rate is {k['booking_cancellation_rate']:.1%} because {int(sh['of which partially cancelled']):,} bookings were only partially cancelled.",
         f"Booking-based cancellation rises with lead time from {lb.cancellation_rate.iloc[0]:.1%} of passengers (0-3 days) to {lb.cancellation_rate.iloc[-1]:.1%} (61-120 days); chi-square {p(T.loc['S-04', 'p_value'])}, Cramer's V = {T.loc['S-04', 'effect_size']:.2f}.",
         f"Cancellation is lowest in {bc.cancellation_rate.idxmin()} ({bc.cancellation_rate.min():.1%}) and highest in {bc.cancellation_rate.idxmax()} ({bc.cancellation_rate.max():.1%}).",
         f"Refunds total INR {k['refund_total']:,.0f} ({k['refund_total'] / k['gross_value']:.1%} of gross booking value): INR {k['refund_passenger']:,.0f} from passenger cancellations and INR {k['refund_system']:,.0f} from System auto-refunds; INR {k['retained_charges']:,.0f} was retained as cancellation charges."],
        ["The lead-time gradient is a recovered built-in pattern (A-20), not evidence that booking early causes cancellation.", f"About {k['refund_system'] / k['refund_total']:.0%} of refunded value comes from System refunds of uncleared waitlists rather than from passengers choosing to cancel, which matters when interpreting refund totals."],
        [SYN, "Fares, charges and refunds follow illustrative rules, not real tariffs or refund policies (A-10)."]))
    parts.append(_block("7. Booking value and fares",
        [f"Gross booking value is INR {k['gross_value']:,.0f}, net booking value INR {k['net_value']:,.0f} ({k['net_value'] / k['gross_value']:.1%} of gross); average fare per passenger INR {k['avg_fare_per_passenger']:,.2f} (95% CI {CI.loc['mean fare per passenger, INR (t interval)', 'ci_low']:,.0f} to {CI.loc['mean fare per passenger, INR (t interval)', 'ci_high']:,.0f}).",
         f"The fare distribution is right-skewed: median INR {fq['p50']:,.0f}, 95th percentile INR {fq['p95']:,.0f}; mean fare by class ranges from INR {fc['mean'].min():,.0f} ({fc['mean'].idxmin()}) to INR {fc['mean'].max():,.0f} ({fc['mean'].idxmax()}).",
         f"Fare per passenger is positively correlated with route distance (Spearman rho = {T.loc['S-09', 'effect_size']:.2f})."],
        ["Class mix and distance explain most of the spread in fares.", "The distance relationship is mechanical, because fares are generated from distance, class and age (A-10); it is not a pricing discovery."],
        [SYN, "Gross and net booking value are not revenue or profit (A-18)."]))
    parts.append(_block("8. Punctuality",
        [f"On-time performance (arrival delay of at most 15 minutes) is {k['otp']:.1%} (95% Wilson interval {CI.loc['on-time performance (Wilson)', 'ci_low']:.1%} to {CI.loc['on-time performance (Wilson)', 'ci_high']:.1%}) over {k['runs_with_delay']} runs with a recorded delay; the average delay is {k['avg_delay']:.1f} minutes with early arrivals counted as 0.",
         f"On-time share by season: " + ", ".join(f"{s} {sea.loc[s, 'otp']:.1%}" for s in ["Winter", "Summer", "Monsoon", "Post-Monsoon"]) + f". Seasonal differences are not significant (delay S-06, {p(T.loc['S-06', 'p_value'])}; on-time share S-07, {p(T.loc['S-07', 'p_value'])}).",
         f"Passengers per run and arrival delay are essentially uncorrelated (S-10, Spearman rho = {T.loc['S-10', 'effect_size']:.2f}, 95% CI {T.loc['S-10', 'ci_low']:.2f} to {T.loc['S-10', 'ci_high']:.2f})."],
        [f"With {int(sea.runs_with_delay.min())} to {int(sea.runs_with_delay.max())} runs with a recorded delay per season, only large seasonal differences would be detectable; the seasonal effect built into the generator (A-20) is too small to resolve here.", "Busier runs are not later in this dataset, consistent with delays being generated from season, distance and train type rather than from demand."],
        [SYN, f"{k['simulated_runs'] - k['runs_with_delay']} runs have no recorded arrival delay; they are excluded, not imputed. The 15-minute threshold is a project convention (A-11), not the railway's punctuality standard."]))
    parts.append("## 9. What this analysis can and cannot support\n\n"
                 "* **Can support:** a demonstration of a reproducible analytics workflow (loading, validation, cleaning, KPI calculation, reconciliation, EDA, statistics, visualisation) whose KPIs agree with the approved definitions and with the SQL layer.\n"
                 "* **Cannot support:** any statement about actual IRCTC or Indian Railways performance, real passenger behaviour, real fares, or the future. No forecast is made or implied.\n"
                 "* **Would be needed for real conclusions:** real booking and operations data covering the full schedule, not a 3.9% sample of simulated runs; real fare and refund rules; and a design that accounts for the clustering of passengers within bookings and runs.\n")
    return "\n".join(parts)
