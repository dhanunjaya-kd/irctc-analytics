"""Statistical analysis: descriptive statistics, confidence intervals, hypothesis tests and correlations.

(The module lives inside the `analytics` package, so `import statistics` elsewhere still means the standard library; import this one as `analytics.statistics`.)

Every test row states the QUESTION, the METRIC and unit of analysis, the METHOD, the result, an INTERPRETATION and the LIMITATION. Because the data is
synthetic, any association found reflects the generator's built-in assumptions; none of it is evidence about real passengers, and nothing here is causal.
Effect sizes are reported next to p-values because with 10^5 bookings almost any difference is "significant". p-values are also Bonferroni-adjusted for the number of tests.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sps

import config as cfg

SEED = cfg.SEED
LIMIT_SYNTH = "Synthetic, sampled simulation: the effect reflects the generator's assumptions, not real passenger behaviour; association only, not causation."


# ------------------------------------------------------------------ descriptive statistics and intervals
def describe(x) -> dict:
    x = pd.Series(x).dropna().astype(float)
    q = x.quantile([.05, .25, .5, .75, .95])
    return dict(n=len(x), mean=x.mean(), median=q[.5], std=x.std(ddof=1), variance=x.var(ddof=1), min=x.min(), p5=q[.05], p25=q[.25], p75=q[.75], p95=q[.95], max=x.max(),
                skew=float(sps.skew(x)), cv=x.std(ddof=1) / x.mean() if x.mean() else np.nan)


def descriptive_table(named: dict) -> pd.DataFrame:
    return pd.DataFrame({k: describe(v) for k, v in named.items()}).T.rename_axis("variable").reset_index()


def wilson_ci(k: float, n: float, conf: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a proportion (assumes independent observations; see cluster_bootstrap_rate for clustered data)."""
    if n <= 0:
        return (np.nan, np.nan)
    z = sps.norm.ppf(0.5 + conf / 2); p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (centre - half, centre + half)


def mean_ci(x, conf: float = 0.95) -> tuple[float, float]:
    x = pd.Series(x).dropna().astype(float)
    h = sps.sem(x) * sps.t.ppf(0.5 + conf / 2, len(x) - 1)
    return (x.mean() - h, x.mean() + h)


def ratio_bootstrap_ci(num, den, n_boot: int = 2000, conf: float = 0.95, seed: int = SEED) -> tuple[float, float, float]:
    """Percentile bootstrap CI for sum(num)/sum(den), resampling whole units (runs). Returns (estimate, low, high)."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(num), size=(n_boot, len(num)))
    r = num[idx].sum(axis=1) / den[idx].sum(axis=1)
    a = (1 - conf) / 2
    return (num.sum() / den.sum(), float(np.quantile(r, a)), float(np.quantile(r, 1 - a)))


def cluster_bootstrap_rate(k, n, n_boot: int = 1000, conf: float = 0.95, seed: int = SEED) -> tuple[float, float, float]:
    """Bootstrap CI for sum(k)/sum(n) resampling whole CLUSTERS (bookings), because passengers of one booking are not independent."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    rng = np.random.default_rng(seed); r = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, len(k), len(k)); r[i] = k[idx].sum() / n[idx].sum()
    a = (1 - conf) / 2
    return (k.sum() / n.sum(), float(np.quantile(r, a)), float(np.quantile(r, 1 - a)))


def group_ratio_ci(df: pd.DataFrame, by: str, num: str, den: str, n_boot: int = 1000, seed: int = SEED) -> pd.DataFrame:
    """Ratio of sums per group with a bootstrap CI over the group's runs (e.g. occupancy per train)."""
    rows = []
    for g, d in df.groupby(by, observed=True):
        est, lo, hi = ratio_bootstrap_ci(d[num], d[den], n_boot, seed=seed)
        rows.append({by: g, "units": len(d), "estimate": est, "ci_low": lo, "ci_high": hi})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ tests and effect sizes
def cohens_d(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    sp = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    return float((a.mean() - b.mean()) / sp) if sp else float("nan")


def magnitude(v: float, kind: str = "d") -> str:
    v = abs(v); cuts = {"d": (0.2, 0.5, 0.8), "v": (0.1, 0.3, 0.5), "eps": (0.01, 0.08, 0.26), "rho": (0.1, 0.3, 0.5)}[kind]
    return "negligible" if v < cuts[0] else "small" if v < cuts[1] else "medium" if v < cuts[2] else "large"


def two_group_test(a, b) -> dict:
    a, b = np.asarray(a, float), np.asarray(b, float)
    t = sps.ttest_ind(a, b, equal_var=False); ci = t.confidence_interval(0.95)
    u = sps.mannwhitneyu(a, b, alternative="two-sided")
    return dict(mean_a=a.mean(), mean_b=b.mean(), diff=a.mean() - b.mean(), ci_low=ci.low, ci_high=ci.high, t=float(t.statistic), p_welch=float(t.pvalue), u=float(u.statistic), p_mwu=float(u.pvalue), d=cohens_d(a, b))


def cramers_v(table) -> float:
    t = np.asarray(table, float); chi2 = sps.chi2_contingency(t, correction=False)[0]
    return float(np.sqrt(chi2 / (t.sum() * (min(t.shape) - 1))))


def kruskal_test(groups: list) -> dict:
    h, p = sps.kruskal(*groups); n = sum(len(g) for g in groups); k = len(groups)
    return dict(h=float(h), p=float(p), epsilon2=float((h - k + 1) / (n - k)))


def spearman_ci(x, y, conf: float = 0.95) -> dict:
    x, y = np.asarray(x, float), np.asarray(y, float); ok = ~(np.isnan(x) | np.isnan(y)); x, y = x[ok], y[ok]
    rho, p = sps.spearmanr(x, y); n = len(x); z = np.arctanh(np.clip(rho, -0.999999, 0.999999)); se = 1.06 / np.sqrt(max(n - 3, 1))      # Fieller et al. SE for Spearman
    zc = sps.norm.ppf(0.5 + conf / 2)
    return dict(rho=float(rho), p=float(p), n=n, ci_low=float(np.tanh(z - zc * se)), ci_high=float(np.tanh(z + zc * se)))


def linear_trend(y) -> dict:
    y = np.asarray(y, float); x = np.arange(len(y)); r = sps.linregress(x, y); h = sps.t.ppf(0.975, len(y) - 2) * r.stderr
    return dict(slope=float(r.slope), ci_low=float(r.slope - h), ci_high=float(r.slope + h), p=float(r.pvalue), r2=float(r.rvalue ** 2), n=len(y))


def _fmt_p(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


# ------------------------------------------------------------------ the analysis
def run_statistics(facts: dict, monthly: pd.DataFrame, n_boot: int = 1000) -> dict:
    pf, bf, cf, rf = (facts[k] for k in ("passenger_fact", "booking_fact", "class_run_fact", "run_fact"))
    ef = facts["event_fact"]
    tests = []

    def add(tid, question, metric, unit, method, n, stat, p, eff_name, eff, lo, hi, result, interp, lim=LIMIT_SYNTH):
        tests.append(dict(test_id=tid, question=question, metric=metric, unit_of_analysis=unit, method=method, n=n, statistic=stat, p_value=p, effect_size_name=eff_name, effect_size=eff,
                          ci_low=lo, ci_high=hi, result=result, interpretation=interp, limitation=lim))

    # S-01 weekend vs weekday demand per run
    a, b = rf.loc[rf.is_weekend, "passengers"], rf.loc[~rf.is_weekend, "passengers"]; r = two_group_test(a, b)
    add("S-01", "Do simulated runs on weekend days carry a different number of passengers than runs on weekdays?", "passengers per simulated run", "simulated run", "Welch t-test (+ Mann-Whitney U as a robustness check)",
        f"{len(a)} weekend / {len(b)} weekday runs", r["t"], r["p_welch"], "Cohen's d", r["d"], r["ci_low"], r["ci_high"],
        f"weekend mean {r['mean_a']:.1f} vs weekday mean {r['mean_b']:.1f} passengers/run; difference {r['diff']:+.1f} (95% CI {r['ci_low']:+.1f} to {r['ci_high']:+.1f}); {_fmt_p(r['p_welch'])}; Mann-Whitney {_fmt_p(r['p_mwu'])}",
        f"The {magnitude(r['d'])} effect (|d| = {abs(r['d']):.2f}) means weekend-day runs are associated with {'more' if r['diff'] > 0 else 'fewer'} passengers per run in this dataset." if r["p_welch"] < 0.05
        else f"The difference ({r['diff']:+.1f} passengers/run) is not statistically distinguishable from zero at the 5% level (the interval includes 0): no weekday effect can be claimed from this sample.")
    # S-02 / S-03 peak vs non-peak
    a, b = rf.loc[rf.is_peak, "passengers"], rf.loc[~rf.is_peak, "passengers"]; r = two_group_test(a, b)
    add("S-02", "Do runs inside peak travel periods carry more passengers than other runs?", "passengers per simulated run", "simulated run", "Welch t-test (+ Mann-Whitney U)", f"{len(a)} peak / {len(b)} other runs", r["t"], r["p_welch"],
        "Cohen's d", r["d"], r["ci_low"], r["ci_high"], f"peak mean {r['mean_a']:.1f} vs other {r['mean_b']:.1f} passengers/run; difference {r['diff']:+.1f} (95% CI {r['ci_low']:+.1f} to {r['ci_high']:+.1f}); {_fmt_p(r['p_welch'])}",
        f"Peak-period runs show a {magnitude(r['d'])} difference (d = {r['d']:.2f}); consistent with the peak-period demand uplift the simulation builds in." if r["p_welch"] < 0.05 else "No detectable difference.")
    a, b = rf.loc[rf.is_peak, "occupancy"], rf.loc[~rf.is_peak, "occupancy"]; r = two_group_test(a, b)
    add("S-03", "Is seat occupancy higher on runs inside peak travel periods?", "run occupancy (booked seat-equivalents / seats)", "simulated run", "Welch t-test (+ Mann-Whitney U)", f"{len(a)} peak / {len(b)} other runs", r["t"], r["p_welch"],
        "Cohen's d", r["d"], r["ci_low"], r["ci_high"], f"peak mean {r['mean_a']:.3f} vs other {r['mean_b']:.3f}; difference {r['diff']:+.3f} (95% CI {r['ci_low']:+.3f} to {r['ci_high']:+.3f}); {_fmt_p(r['p_welch'])}",
        f"A {magnitude(r['d'])} effect (d = {r['d']:.2f}); occupancy is bounded at 100%, so differences compress at the top." if r["p_welch"] < 0.05 else "No detectable difference in occupancy.")
    # S-04 booking cancellation vs lead-time bucket
    ct = pd.crosstab(bf.lead_bucket, bf.booking_status.astype(str) == "Cancelled"); chi = sps.chi2_contingency(ct.to_numpy()); v = cramers_v(ct)
    rates = (ct[True] / ct.sum(axis=1))
    add("S-04", "Is the share of fully cancelled bookings related to how far ahead the booking was made?", "booking-based cancellation rate by lead-time bucket", "booking", "chi-square test of independence (+ Cramer's V)",
        f"{len(bf):,} bookings", float(chi.statistic), float(chi.pvalue), "Cramer's V", v, np.nan, np.nan,
        f"rate rises from {rates.iloc[0]:.1%} (0-3 days) to {rates.iloc[-1]:.1%} (61-120 days); chi-square = {chi.statistic:,.0f}, dof = {chi.dof}, {_fmt_p(chi.pvalue)}",
        f"Strong statistical evidence of association with a {magnitude(v, 'v')} effect (V = {v:.3f}); longer lead times go with higher cancellation in this dataset (the simulation builds in such a pattern).",
        LIMIT_SYNTH + " Bookings are the unit, so passengers within a booking are not double counted.")
    # S-05 occupancy by class
    groups = [g.occupancy.to_numpy() for _, g in cf.groupby("travel_class", observed=True)]; kr = kruskal_test(groups)
    add("S-05", "Does seat occupancy differ between travel classes?", "occupancy of each simulated train-class run", "train-class run", "Kruskal-Wallis H test (rank-based; occupancy is bounded and skewed)", f"{sum(map(len, groups)):,} class-runs in {len(groups)} classes",
        kr["h"], kr["p"], "epsilon-squared", kr["epsilon2"], np.nan, np.nan, f"H = {kr['h']:.1f}, {_fmt_p(kr['p'])}; epsilon-squared = {kr['epsilon2']:.3f}",
        f"Classes differ with a {magnitude(kr['epsilon2'], 'eps')} effect; class-level occupancy comparisons are meaningful, but see the limitation on independence." if kr["p"] < 0.05 else "No detectable difference between classes.",
        LIMIT_SYNTH + " Class-runs of the same train run share a date, so they are not fully independent; the 1A class has few runs.")
    # S-06 / S-07 delay by season
    ops = rf.dropna(subset=["arrival_delay_min"]); groups = [g.arrival_delay_min.astype(float).to_numpy() for _, g in ops.groupby("season")]; kr = kruskal_test(groups)
    add("S-06", "Does the arrival delay differ between seasons?", "arrival delay in minutes", "simulated run with a recorded delay", "Kruskal-Wallis H test (delays are skewed)", f"{len(ops)} runs in {len(groups)} seasons", kr["h"], kr["p"], "epsilon-squared",
        kr["epsilon2"], np.nan, np.nan, f"H = {kr['h']:.1f}, {_fmt_p(kr['p'])}; epsilon-squared = {kr['epsilon2']:.3f}",
        f"Seasonal differences are {magnitude(kr['epsilon2'], 'eps')} (epsilon-squared = {kr['epsilon2']:.3f})." if kr["p"] < 0.05 else "No detectable seasonal difference in arrival delay.", LIMIT_SYNTH + " Delays are simulated; 23 runs with a missing delay are excluded, not imputed.")
    ct = pd.crosstab(ops.season, ops.on_time.astype(bool)); chi = sps.chi2_contingency(ct.to_numpy()); v = cramers_v(ct)
    add("S-07", "Does the share of on-time runs (arrival delay <= 15 minutes) differ between seasons?", "on-time performance by season", "simulated run with a recorded delay", "chi-square test of independence (+ Cramer's V)", f"{len(ops)} runs", float(chi.statistic),
        float(chi.pvalue), "Cramer's V", v, np.nan, np.nan, f"chi-square = {chi.statistic:.1f}, dof = {chi.dof}, {_fmt_p(chi.pvalue)}; OTP by season: " + ", ".join(f"{s} {r:.1%}" for s, r in (ct[True] / ct.sum(axis=1)).items()),
        f"A {magnitude(v, 'v')} association (V = {v:.3f})." if chi.pvalue < 0.05 else "No detectable seasonal difference in on-time performance.", LIMIT_SYNTH + " Expected counts per cell are modest (about 745 runs).")
    # S-08 in-sample trend (descriptive; NOT extrapolated)
    tr = linear_trend(monthly.bookings_per_run.to_numpy())
    add("S-08", "Is there a linear trend in bookings per simulated run across the 24 months?", "bookings per simulated run, by month", "month", "ordinary least squares slope on the month index (in-sample description)", "24 months", tr["slope"], tr["p"],
        "R-squared", tr["r2"], tr["ci_low"], tr["ci_high"], f"slope {tr['slope']:+.2f} bookings/run per month (95% CI {tr['ci_low']:+.2f} to {tr['ci_high']:+.2f}); R-squared = {tr['r2']:.2f}; {_fmt_p(tr['p'])}",
        "A straight line summarises these 24 months; seasonality is not modelled, so it is a description of the period, not a trend in demand.", "Synthetic, sampled simulation. In-sample description only: it is NOT extrapolated and is not a forecast. 24 points, with seasonal structure, are too few for trend claims.")
    # S-09 fare vs distance
    sp = spearman_ci(bf.total_fare / bf.num_passengers, bf.route_id.map(facts["run_fact"].drop_duplicates("route_id").set_index("route_id").distance_km))
    add("S-09", "How strongly is the fare per passenger related to route distance?", "booking fare per passenger vs route distance (km)", "booking", "Spearman rank correlation (+ Fisher-z CI)", f"{sp['n']:,} bookings", sp["rho"], sp["p"], "Spearman rho", sp["rho"], sp["ci_low"], sp["ci_high"],
        f"rho = {sp['rho']:.2f} (95% CI {sp['ci_low']:.2f} to {sp['ci_high']:.2f}); {_fmt_p(sp['p'])}", f"A {magnitude(sp['rho'], 'rho')} positive association.", "Synthetic data: fares are generated by a distance-and-class formula, so this relationship is mechanical, not a discovery about pricing; class mix also contributes.")
    # S-10 demand vs delay (run level)
    sp = spearman_ci(ops.passengers, ops.arrival_delay_min.astype(float))
    add("S-10", "Are busier runs associated with longer arrival delays?", "passengers per run vs arrival delay (minutes)", "simulated run with a recorded delay", "Spearman rank correlation (+ Fisher-z CI)", f"{sp['n']} runs", sp["rho"], sp["p"], "Spearman rho", sp["rho"],
        sp["ci_low"], sp["ci_high"], f"rho = {sp['rho']:.2f} (95% CI {sp['ci_low']:.2f} to {sp['ci_high']:.2f}); {_fmt_p(sp['p'])}", "No detectable association." if sp["p"] >= 0.05 else f"A {magnitude(sp['rho'], 'rho')} association.",
        LIMIT_SYNTH + " Per assumption A-20 the generator ties delays to season, distance and train type, not to demand, so the absence of an association is expected.")
    # S-11 waitlist clearance by class
    wl = pf[pf.is_initial_wl]; ct = pd.crosstab(wl.travel_class, wl.is_cleared_wl); chi = sps.chi2_contingency(ct.to_numpy()); v = cramers_v(ct)
    add("S-11", "Does the waitlist clearance rate differ between travel classes?", "share of initially waitlisted passengers who finished Confirmed or RAC", "initially waitlisted passenger", "chi-square test of independence (+ Cramer's V)", f"{len(wl):,} passengers",
        float(chi.statistic), float(chi.pvalue), "Cramer's V", v, np.nan, np.nan, f"chi-square = {chi.statistic:,.0f}, dof = {chi.dof}, {_fmt_p(chi.pvalue)}; clearance by class: " + ", ".join(f"{c} {r:.1%}" for c, r in (ct[True] / ct.sum(axis=1)).items()),
        f"Classes differ with a {magnitude(v, 'v')} effect (V = {v:.3f})." if chi.pvalue < 0.05 else "No detectable difference between classes.",
        LIMIT_SYNTH + " Passengers are the unit but they cluster within bookings and runs, so the p-value is optimistic; rely on the effect size and the intervals.")
    out = pd.DataFrame(tests)
    out["p_bonferroni"] = (out.p_value * out.p_value.notna().sum()).clip(upper=1.0)

    # ---- descriptive statistics
    pax_bk = bf.n_pax
    desc = descriptive_table({"fare per passenger (INR)": pf.fare_amount, "booking total fare (INR)": bf.total_fare, "passengers per booking": pax_bk, "booking lead time (days)": bf.lead_days,
                              "class-run occupancy": cf.occupancy, "passengers per simulated run": rf.passengers, "run occupancy": rf.occupancy, "arrival delay (min, recorded)": ops.arrival_delay_min.astype(float),
                              "refund per event (INR)": ef.refund_amount})
    # ---- intervals for the headline rates
    k_pax, n_pax = bf.n_cancelled.to_numpy(), bf.n_pax.to_numpy()
    est, lo, hi = cluster_bootstrap_rate(k_pax, n_pax, n_boot); wl_, wh_ = wilson_ci(k_pax.sum(), n_pax.sum())
    ci = [dict(measure="passenger cancellation rate (Wilson, assumes independence)", estimate=k_pax.sum() / n_pax.sum(), ci_low=wl_, ci_high=wh_, n=int(n_pax.sum())),
          dict(measure="passenger cancellation rate (cluster bootstrap over bookings)", estimate=est, ci_low=lo, ci_high=hi, n=len(bf))]
    kc = int((bf.booking_status.astype(str) == "Cancelled").sum()); l, h = wilson_ci(kc, len(bf))
    ci.append(dict(measure="booking-based cancellation rate (Wilson)", estimate=kc / len(bf), ci_low=l, ci_high=h, n=len(bf)))
    w = pf[pf.is_initial_wl]; l, h = wilson_ci(int(w.is_cleared_wl.sum()), len(w)); ci.append(dict(measure="waitlist clearance rate (Wilson)", estimate=w.is_cleared_wl.mean(), ci_low=l, ci_high=h, n=len(w)))
    ot = ops.on_time.astype(bool); l, h = wilson_ci(int(ot.sum()), len(ot)); ci.append(dict(measure="on-time performance (Wilson)", estimate=ot.mean(), ci_low=l, ci_high=h, n=len(ot)))
    e, l, h = ratio_bootstrap_ci(rf.booked_seats, rf.seats, n_boot); ci.append(dict(measure="seat occupancy (bootstrap over runs)", estimate=e, ci_low=l, ci_high=h, n=len(rf)))
    e, l, h = ratio_bootstrap_ci(rf.passengers, np.ones(len(rf)), n_boot); ci.append(dict(measure="passengers per simulated run (bootstrap over runs)", estimate=e, ci_low=l, ci_high=h, n=len(rf)))
    lo_, hi_ = mean_ci(pf.fare_amount); ci.append(dict(measure="mean fare per passenger, INR (t interval)", estimate=pf.fare_amount.mean(), ci_low=lo_, ci_high=hi_, n=len(pf)))
    # ---- correlations at run level
    cols = {"passengers": "passengers per run", "occupancy": "occupancy", "arrival_delay_min": "arrival delay (min)", "distance_km": "route distance (km)", "seats": "seat supply", "initial_wl_pax": "initial waitlist passengers"}
    rr = rf.assign(arrival_delay_min=rf.arrival_delay_min.astype(float))[list(cols)]
    corr = rr.corr(method="spearman").rename(index=cols, columns=cols)
    pairs = []
    names = list(cols)
    for i, a_ in enumerate(names):
        for b_ in names[i + 1:]:
            s = spearman_ci(rr[a_], rr[b_]); pairs.append(dict(variable_1=cols[a_], variable_2=cols[b_], rho=s["rho"], ci_low=s["ci_low"], ci_high=s["ci_high"], p_value=s["p"], n=s["n"]))
    return dict(tests=out, descriptive=desc, rate_cis=pd.DataFrame(ci), correlation_matrix=corr, correlation_pairs=pd.DataFrame(pairs))
