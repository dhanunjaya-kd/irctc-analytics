"""Profile the cleaned dataset and write the data-quality report and supporting CSVs.

All numbers in the generated documents come from the actual pipeline run; nothing is typed in by hand.
"""
import numpy as np
import pandas as pd

import config as cfg
import dq_catalog as dq

PROFILE_START, PROFILE_END = "<!-- PROFILE:START -->", "<!-- PROFILE:END -->"


# ------------------------------------------------------------------ occupancy at train-class-run level
def class_run_occupancy(T):
    bk, ps, cap = T["bookings"], T["booking_passengers"], T["seat_capacity"]
    m = ps.merge(bk[["booking_id", "train_id", "journey_date", "travel_class"]], on="booking_id")
    cnt = m.groupby(["train_id", "journey_date", "travel_class", "final_status"]).size().unstack(fill_value=0)
    for s in ("Confirmed", "RAC", "Waitlisted", "Cancelled"):
        if s not in cnt:
            cnt[s] = 0
    occ = cap.merge(cnt.reset_index(), on=["train_id", "journey_date", "travel_class"], how="left").fillna(0)
    occ["seat_equivalents"] = occ["Confirmed"] + cfg.RAC_SEAT_WEIGHT * occ["RAC"]
    occ["occupancy"] = occ["seat_equivalents"] / occ["total_seats"]
    return occ


def dataset_profile(T):
    bk, ps, ev, cap, ops = T["bookings"], T["booking_passengers"], T["cancellations"], T["seat_capacity"], T["train_operations"]
    occ = class_run_occupancy(T)
    P = []

    def add(section, metric, value):
        P.append((section, metric, value))

    for t in ("stations", "routes", "trains", "train_stops", "calendar", "seat_capacity", "train_operations", "bookings",
              "booking_passengers", "cancellations"):
        add("Row counts", t, f"{len(T[t]):,}")
    add("Scale", "Simulated train runs", f"{len(ops):,} (about {len(ops) / 24:.0f} per calendar month, {len(ops) / len(T['trains']):.1f} per train)")
    add("Scale", "Train-class runs (capacity records)", f"{len(cap):,}")
    add("Scale", "Journey date range", f"{min(bk['journey_date'])} to {max(bk['journey_date'])}")
    add("Scale", "Passengers per booking (mean)", f"{len(ps) / len(bk):.2f}")
    add("Capacity", "Seats per train-class run (mean / min / max)", f"{cap['total_seats'].mean():.0f} / {cap['total_seats'].min()} / {cap['total_seats'].max()}")
    add("Capacity", "Total seat supply across all simulated class-runs", f"{cap['total_seats'].sum():,}")
    add("Occupancy", "Overall seat occupancy (sum of Confirmed + 0.5 x RAC over sum of seats)", f"{occ['seat_equivalents'].sum() / occ['total_seats'].sum():.1%}")
    add("Occupancy", "Class-run occupancy: median / p10 / p90", f"{occ['occupancy'].median():.1%} / {occ['occupancy'].quantile(.1):.1%} / {occ['occupancy'].quantile(.9):.1%}")
    add("Occupancy", "Class-runs at or above 95% occupancy", f"{(occ['occupancy'] >= .95).mean():.1%}")
    add("Occupancy", "Class-runs below 50% occupancy", f"{(occ['occupancy'] < .5).mean():.1%}")
    m_ = ps.merge(bk[["booking_id", "train_id", "journey_date", "travel_class"]], on="booking_id")
    wl_runs = m_[m_["initial_status"] == "Waitlisted"].groupby(["train_id", "journey_date", "travel_class"]).ngroups
    add("Occupancy", "Class-runs with at least one waitlisted passenger at booking time", f"{wl_runs / len(cap):.1%}")
    n = len(ps)
    for s in ("Confirmed", "RAC", "Waitlisted", "Cancelled"):
        add("Passenger final status", s, f"{(ps['final_status'] == s).sum():,} ({(ps['final_status'] == s).mean():.1%})")
    for s in ("Confirmed", "RAC", "Waitlisted"):
        add("Passenger initial status", s, f"{(ps['initial_status'] == s).sum():,} ({(ps['initial_status'] == s).mean():.1%})")
    wl = ps[ps["initial_status"] == "Waitlisted"]
    add("Waiting list", "Initially waitlisted passengers later Confirmed or RAC (clearance)", f"{wl['final_status'].isin(['Confirmed', 'RAC']).mean():.1%}")
    add("Waiting list", "Initially waitlisted passengers refunded by the system (uncleared)", f"{((wl['final_status'] == 'Waitlisted')).mean():.1%}")
    for s in ("Confirmed", "RAC", "Waitlisted", "Cancelled", "Mixed"):
        add("Booking status (roll-up)", s, f"{(bk['booking_status'] == s).sum():,} ({(bk['booking_status'] == s).mean():.1%})")
    add("Cancellations", "Events (Passenger / System)", f"{len(ev):,} ({(ev['cancellation_type'] == 'Passenger').sum():,} / {(ev['cancellation_type'] == 'System').sum():,})")
    multi = ev.groupby("booking_id").size()
    add("Cancellations", "Bookings with more than one event", f"{(multi > 1).sum():,}")
    gross, refund = bk["total_fare"].sum(), ev["refund_amount"].sum()
    add("Value (synthetic INR)", "Gross booking value", f"{gross:,.0f}")
    add("Value (synthetic INR)", "Refunds", f"{refund:,.0f} ({refund / gross:.1%} of gross)")
    add("Value (synthetic INR)", "Net booking value", f"{gross - refund:,.0f}")
    add("Value (synthetic INR)", "Cancellation charges retained", f"{ev['cancellation_charge'].sum():,.0f}")
    arr = ops["arrival_delay_min"].dropna()
    add("Operations", "On-time (arrival delay <= 15 min), runs with a recorded delay", f"{(arr <= cfg.ON_TIME_THRESHOLD_MIN).mean():.1%} of {len(arr):,}")
    add("Operations", "Runs with NULL arrival delay", f"{ops['arrival_delay_min'].isna().sum():,}")
    per_month = bk.groupby(pd.to_datetime(bk["journey_date"].astype(str)).dt.to_period("M")).size()
    add("Volume", "Bookings per journey month: min / median / max", f"{per_month.min():,} / {int(per_month.median()):,} / {per_month.max():,}")
    return P


def profile_markdown(P):
    lines, section = [], None
    for sec, metric, val in P:
        if sec != section:
            lines += ["", f"**{sec}**", "", "| Metric | Value |", "|---|---|"]
            section = sec
        lines.append(f"| {metric} | {val} |")
    return "\n".join(lines).strip()


def inject_profile_into(doc_path, P):
    text = doc_path.read_text(encoding="utf-8")
    a, b = text.index(PROFILE_START), text.index(PROFILE_END)
    doc_path.write_text(text[:a + len(PROFILE_START)] + "\n\n" + profile_markdown(P) + "\n\n" + text[b:], encoding="utf-8")


# ------------------------------------------------------------------ data-quality outputs
def issue_frame(res, inj_log):
    inj_counts = inj_log.groupby("issue_code").size()
    rows = []
    for code in dq.ORDER:
        c, r = dq.CATALOG[code], res.issues[code]
        rows.append(dict(issue_code=code, table=c["table"], issue_type=c["title"], what_was_found=c["issue"],
                         cleaning_rule=c["rule"], affected_records=r["detected"], corrected=r["corrected"],
                         retained_flagged=r["retained"], rejected=r["rejected"], injected_records=int(inj_counts.get(code, 0)),
                         detection_matches_injection=bool(int(inj_counts.get(code, 0)) == r["detected"])))
    return pd.DataFrame(rows)


def write_dq_outputs(res, inj_log, validation, out_dir=cfg.DQ_DIR):
    out_dir.mkdir(parents=True, exist_ok=True)
    iss = issue_frame(res, inj_log)
    iss.to_csv(out_dir / "issue_summary.csv", index=False)
    mv = pd.DataFrame([dict(table=t, **v) for t, v in res.movement.items()])
    mv.to_csv(out_dir / "row_movement.csv", index=False)
    casc = pd.DataFrame([dict(reason=k, **v) for k, v in res.cascade.items()])
    casc.to_csv(out_dir / "family_rejection_cascade.csv", index=False)
    pd.DataFrame(validation).to_csv(out_dir / "validation_checks.csv", index=False)
    return iss, mv, casc


def _md_table(df, cols, headers=None):
    headers = headers or cols
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append(f"{v:,}" if isinstance(v, (int, np.integer)) else str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def write_dq_report(res, inj_log, validation, doc_path, profile):
    iss = issue_frame(res, inj_log)
    mv = pd.DataFrame([dict(table=t, **v) for t, v in res.movement.items()])
    n_ok = int(iss["detection_matches_injection"].sum())
    n_pass = sum(v["passed"] for v in validation)
    tables_order = ["bookings", "booking_passengers", "cancellations", "seat_capacity", "train_operations"]
    total_corrected = int(iss["corrected"].sum()); total_retained = int(iss["retained_flagged"].sum()); total_rejected = int(iss["rejected"].sum())
    b_raw, b_clean = res.movement["bookings"]["raw_rows"], res.movement["bookings"]["clean_rows"]
    fam = sum(v["bookings"] for v in res.cascade.values())
    L = []
    L += ["# Data Quality Report \u2014 Phase 2", "",
          "> **All data in this project is synthetic.** The raw extract was produced by `python/src/generate_synthetic_data.py` and then "
          "deliberately corrupted by `python/src/inject_quality_issues.py` at documented rates. The issue counts below describe those "
          "controlled defects. They say nothing about the data quality of IRCTC or Indian Railways.", "",
          "This report is generated by `python/src/build_reports.py` from the actual pipeline run.", "",
          "## 1. What was done", "",
          "1. **Generate** a clean, internally consistent synthetic dataset (the *truth*), kept outside the repository history in `data/interim/synthetic_truth/`.",
          "2. **Inject** " + str(len(iss)) + " types of controlled defects into the transactional and operational tables, giving the *raw* extract in `data/raw/synthetic/`. "
          "Each affected booking family carries at most one defect type, so expected counts are exact. Reference tables (stations, routes, trains, train stops, calendar) are not corrupted.",
          "3. **Clean** the raw extract with `python/src/clean_data.py`. Detection reads only the raw text; it never reads the injection log. Raw files are never modified.",
          "4. **Validate** the cleaned tables (`python/src/validate_data.py`): keys, foreign keys, domains, business rules BR-01 to BR-17, size requirements.",
          "5. **Reconcile** what the cleaner detected against what was injected.", "",
          "## 2. Headline results", "",
          f"- Raw bookings: **{b_raw:,}** rows. Cleaned bookings: **{b_clean:,}** ({b_raw - b_clean:,} rows removed: "
          f"{res.movement['bookings']['duplicates']:,} duplicate copies and {res.movement['bookings']['family_rejected']:,} rejected bookings).",
          f"- Record-level outcomes across all issue types: **{total_corrected:,} corrected**, **{total_retained:,} retained and flagged**, **{total_rejected:,} rejected** (duplicate copies, orphans and unrecoverable records).",
          f"- Booking families rejected because a value could not be recovered without inventing it: **{fam:,}** bookings ({fam / (b_raw - res.movement['bookings']['duplicates']):.2%} of distinct raw bookings).",
          f"- Detection versus injection: **{n_ok} of {len(iss)}** issue types matched the injected count exactly.",
          f"- Validation on the cleaned data: **{n_pass} of {len(validation)}** checks passed.", "",
          "## 3. Issues, cleaning rules and outcomes", "",
          "*Outcome meanings.* **Corrected**: record kept, value repaired by a documented rule that recovers it exactly. "
          "**Retained/flagged**: record kept, value left NULL or `Unknown` because repairing it would mean inventing data. "
          "**Rejected**: record removed (duplicate copy, orphan row, or a booking family that cannot be trusted).", ""]
    for t in tables_order:
        sub = iss[iss["table"] == t]
        L += [f"### {t}", "", _md_table(sub, ["issue_type", "affected_records", "cleaning_rule", "corrected", "retained_flagged", "rejected"],
                                          ["Issue type", "Affected records", "Cleaning rule", "Corrected", "Retained / flagged", "Rejected"]), ""]
    L += ["## 4. Booking-family rejection and cascade", "",
          "When a booking cannot be trusted and no rule recovers it, the whole family (booking, passengers, cancellation events) is removed so the cleaned tables never hold half a booking. "
          "Each rejected family is attributed to the **first root cause** detected: for example, a booking whose timestamp was corrupted to a date after the journey also makes its cancellation events look "
          "\"before booking\", but that is one defect, not two.", ""]
    if res.cascade:
        casc = pd.DataFrame([dict(reason=dq.CATALOG[k]["title"] if k in dq.CATALOG else k, **v) for k, v in res.cascade.items()])
        L += [_md_table(casc, ["reason", "bookings", "passengers", "cancellations"],
                        ["Root cause", "Bookings rejected", "Passenger rows removed", "Cancellation rows removed"]), ""]
    L += ["## 5. Row movement from raw to cleaned", "",
          _md_table(mv[mv["table"].isin(tables_order)], ["table", "raw_rows", "duplicates", "orphans", "family_rejected", "other", "clean_rows"],
                    ["Table", "Raw rows", "Duplicate copies removed", "Orphan rows removed", "Removed with rejected family", "Other", "Cleaned rows"]), "",
          "Reference tables (stations, routes, trains, train_stops, calendar) pass through unchanged.", "",
          "## 6. Detection versus injection", "",
          f"The cleaner found exactly the defects that were injected for {n_ok} of {len(iss)} issue types.", "",
          _md_table(iss, ["issue_code", "injected_records", "affected_records", "detection_matches_injection"],
                    ["Issue code", "Injected", "Detected", "Match"]), "",
          "### Unexpected conditions (each should be 0)", "",
          "| Condition | Count |", "|---|---|"]
    for k, v in res.anomalies.items():
        L.append(f"| {k} | {v:,} |")
    L += ["", "## 7. Validation of the cleaned data", "",
          f"{n_pass} of {len(validation)} checks passed. Full list: `reports/data_quality/validation_checks.csv` and `reports/phase2_validation.txt`.", "",
          "## 8. Effect on analysis and limitations", "",
          "- **Rates are illustrative.** Defect rates (roughly 0.05% to 1% per type) were chosen to exercise every cleaning rule. They are not a claim about real reservation systems.",
          "- **Corrected values are exact only because the truth is known.** The correction rules (roll-up, sum of passenger fares, route lookup) are deterministic, and the test suite confirms cleaned values equal the truth for every retained booking. Real data would not offer that guarantee.",
          "- **Two fields are left incomplete on purpose.** `age_band = 'Unknown'` and NULL `arrival_delay_min` are retained rather than imputed; KPIs exclude NULL delays from their denominators.",
          "- **Rejections remove a small share of bookings** (see section 2). Rejected families leave gaps in the booking queues, so a few waitlisted or RAC passengers appear to have been promoted without a visible cancellation.",
          "- **Reference data was not corrupted.** Duplicate stations, wrong route geometry and similar reference-data defects are not exercised in this phase.", ""]
    doc_path.write_text("\n".join(L), encoding="utf-8")
