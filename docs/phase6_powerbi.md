# Phase 6 — Power BI portfolio milestone

**Synthetic sampled simulation:** 768 simulated runs sampled from 19,708 scheduled runs. Not actual IRCTC or Indian Railways results; no forecasts.

## Current deliverable

The supported entry point is [IRCTC_Portfolio.pbip](../power_bi/portfolio_dashboard/IRCTC_Portfolio.pbip), with its report and semantic-model folders. [Setup guide](../power_bi/README.md) · [Screenshot gallery](../power_bi/screenshots/README.md) · [PDF export](../power_bi/screenshots/IRCTC_Portfolio.pdf).

The previous `IRCTC_Analytics` generated report had rendering problems and is not the supported deliverable. The current project uses a separate report and copied semantic model. The working report is preserved; this release does not regenerate it.

## Evidence and outstanding checks

| Check | Evidence / status |
|---|---|
| Six pages open with populated visuals | Observed in user-provided Desktop screenshots and the exported PDF |
| Table dimension and measure columns | Visible in the latest screenshots, including train delay and KPI comparison columns |
| Financial units | Cards show 612.97 gross, 107.08 refunds and 505.88 net in INR million; raw INR remains in the validation table |
| Live reconciliation summary | Desktop evidence shows 31 reference KPIs and 31 passing KPIs |
| Model row-count checks | All 11 statuses visible as PASS |
| Imported reference checks | 110 marked passed; this is not the earlier Python run's 111-check validation suite |
| Screenshot publication | Confirmed successful push to main at `b287162` |
| Rendering-error recurrence | No error dialog visible in the supplied final views; repeat-session stability is not independently established |
| Refresh completion | Explicit successful completion record still needed |
| Slicer and cross-filter interactions | Controls and filtered earlier screenshot observed; complete interaction checklist not recorded |
| Save, close and reopen | Latest screenshot shows a saved project; successful reopen after final refresh still needs explicit confirmation |
| Fresh-clone setup | Not yet verified; configure DataFolder before refresh on another path |
| Official KPI CSV export | No new native Power BI reconciliation CSV has been supplied; historical interpreter outputs must not be relabelled as Desktop execution |
| Synced slicers / drill-through / report-page tooltips | Not implemented; not claimed in this milestone |

Screenshots show the visible portion of scrollable tables. The 31-pass card is runtime evidence of the summary, not an export of every KPI comparison row. JSON/source validation does not establish calculation correctness in Desktop.

## Report pages

| Page | Main analysis |
|---|---|
| Overview | Executive KPIs, demand per run, class occupancy, monthly scorecard and final passenger status |
| Demand & capacity | Bookings per run, seat supply versus passenger records, class capacity table and season/class heatmap |
| Booking value | Gross/net trends, passenger/system refunds and monthly reconciliation in INR million |
| Train & route performance | Dense-ranked routes/trains, detailed train scorecard, occupancy/cancellation scatter |
| Waitlist & cancellations | Clearance trend, final-status composition, waitlist outcomes and class cancellation rates |
| KPI validation | Reference/calculated KPI comparisons and expected/actual model row counts |

## Model and calculation scope

The current source inventory is 17 tables, 17 relationships and 70 measures: the original 65 plus five INR-million display measures. Fifteen CSV partitions are included; the remaining tables are model-defined. There are six pages and 85 visual containers including non-chart items.

- Occupancy = `(confirmed + 0.5 × RAC passengers) / seat supply`; RAC weighting is a simulation assumption.
- Waitlisted passengers hold no seat. Waitlist pressure is a separate measure.
- Passenger cancellation rate differs from booking cancellation rate.
- Clearance refers to initially waitlisted passengers finishing Confirmed/RAC. Final waitlisted totals and initial-waitlist cohorts are not interchangeable.
- On-time performance uses arrival delay ≤15 minutes and excludes missing delays.
- Train-run measures have no class grain; their response to class filtering differs from passenger/class-run measures.
- Booking value is not revenue/profit. Display scaling occurs once; raw financial measures feed reconciliation.
- Rankings include ties; compare simulated-run counts before interpreting rankings. Scatter plots show association, not causation.

## Automated evidence

The targeted repair/upgrade/polish packages passed their focused source and installer checks (10, 9 and 6 tests respectively). These cover structural edits, fields, layout, backups and preservation; they do not execute the Power BI engine.

Earlier Windows Python analytics independently reported 31 tests passed, 111/111 validations, 31/31 KPI reconciliations and 960/960 monthly reconciliations. Those results belong to the Python milestone. Later regenerated Python outputs remain outside this Power BI release.

The release preparation command checks the current report/model inventory, required CSV headers and row counts against the imported row-count reference. Its generated [file manifest](powerbi_release_files.csv) records source hashes for the proposed commit; it is not Desktop runtime evidence.

## Before calling the milestone fully validated

1. Complete refresh with no pending model/query changes.
2. Test a month, class and train-type selection, one chart selection and hover details; clear filters before checking baseline totals.
3. Inspect the KPI summary and all row-count statuses after refresh.
4. Save, close and reopen successfully; record the date and result.
5. Test a fresh clone after setting its DataFolder parameter. Do not claim this based on the separate MarketEdge project.

Tableau is a separate pending milestone. Its local directory currently contains specifications, calculated-field files and wireframes; no validated workbook has been established.
