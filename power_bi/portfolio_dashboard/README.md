# Current IRCTC Portfolio report

Open **IRCTC_Portfolio.pbip**. Keep its `.Report` and `.SemanticModel` folders together.

See the [Power BI setup guide](../README.md), [six-page gallery](../screenshots/README.md) and [milestone evidence](../../docs/phase6_powerbi.md).

This is the current six-page Desktop report: Overview; Demand & capacity; Booking value; Train & route performance; Waitlist & cancellations; KPI validation. The project contains 17 tables, 17 relationships, 70 measures and 85 visual containers. Counts are source inventory; not all measures or interactions have independently recorded runtime tests.

User-provided Desktop screenshots and an exported PDF show the populated pages, formatted tables/charts, financial cards and live reconciliation summary. They show 31 KPI passes and all 11 table row-count checks passing. The 110 imported reference checks are separate from the earlier Python run's 111 validations.

**Synthetic data only:** 768 simulated runs sampled from 19,708 scheduled runs. No actual IRCTC results, network-wide estimates or forecasts. Booking value is not revenue or profit.

## Portability

The `DataFolder` parameter currently points to `C:\Projects\irctc-analytics\power_bi\data`. Configure it for another clone location, refresh, test the slicers, then save and reopen. Caches are not shipped. Fresh-clone verification remains unrecorded.

## Reproduction and scope

`build_portfolio_report.py` depends on `portfolio_repairs.py`, `portfolio_design.py` and `portfolio_polish.py`. Its `--out NEW_FOLDER` mode generates report definitions only and refuses to overwrite an existing folder. The current Desktop-saved report is the release source; rerunning older phase generators is not part of setup.

The original 65 DAX expressions were preserved through the visual repairs. Five numeric display measures scale financial values to INR million once. Raw INR measures remain in reconciliation.

Slicers are local per page. Some hover fields are configured. Synced slicers, drill-through and report-page tooltips are not implemented. Final refresh, full interaction and save/reopen verification need an explicit record; a rendered screenshot alone is insufficient.
