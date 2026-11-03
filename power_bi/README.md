# Power BI portfolio

The supported project is **[portfolio_dashboard/IRCTC_Portfolio.pbip](portfolio_dashboard/IRCTC_Portfolio.pbip)**.

[Screenshot gallery](screenshots/README.md) · [PDF export](screenshots/IRCTC_Portfolio.pdf) · [Verification evidence](../docs/phase6_powerbi.md)

## Open on Windows

1. Install Power BI Desktop with PBIP support. Keep the report and semantic-model folders together; do not move the `.pbip` file alone.
2. Open `power_bi/portfolio_dashboard/IRCTC_Portfolio.pbip`.
3. If the repository is not at `C:\Projects\irctc-analytics`, set the **DataFolder** parameter to the absolute path of this clone's `power_bi\data` folder. Use **Transform data**, then **Manage Parameters** in the Power Query Editor. Apply the change.
4. Refresh the model. Data caches are deliberately not included in Git.
5. Check the six pages and the KPI validation page. With filters cleared, the expected sample totals are 201,182 bookings, 405,200 passengers and 768 simulated runs. Inspect 31 KPI passes and all 11 row-count statuses.
6. Test month, class and train-type slicers and chart interactions. Save, close and reopen before recording a successful local verification.

If the initial refresh cannot find CSV files, correct `DataFolder`; do not regenerate or replace the report definitions. The parameter deliberately remains configurable. Fresh-clone execution has not yet been recorded for this IRCTC report.

## Included source

- `portfolio_dashboard/IRCTC_Portfolio.pbip`
- `portfolio_dashboard/IRCTC_Portfolio.Report/`
- `portfolio_dashboard/IRCTC_Portfolio.SemanticModel/`
- `portfolio_dashboard/build_portfolio_report.py` with `portfolio_repairs.py`, `portfolio_design.py` and `portfolio_polish.py`
- The 15 model-referenced CSV files in `data/`
- Actual Desktop PDF/PNG exports in `screenshots/`

The model has 17 tables and 17 relationships. Its 70 measures comprise the original 65 measures plus five numeric INR-million display measures. The six-page report has 85 visual containers, including headings, notes, slicers, cards, tables and charts; this is a source inventory, not a count of 85 analytical charts.

The generator can reproduce report definitions into a new folder using `--out NEW_FOLDER`. It does not copy data/model files and must not be used to overwrite a Desktop-edited report. The original `IRCTC_Analytics` report and single-card diagnostic project are local historical material, not release entry points.

## Interpretation and feature scope

All data is synthetic: 768 simulated runs sampled from 19,708 scheduled runs. Booking values are not revenue/profit. Occupancy uses confirmed passengers plus 0.5 × RAC passengers divided by seat supply. Train-run measures have no class grain. On-time means ≤15 minutes, excluding missing delays.

Month, class and train-type slicers are local to each analytical page. Hover fields are configured for selected visuals. Synced slicers, drill-through and report-page tooltips are not implemented. No forecasting is included.

Microsoft documentation: [Power BI projects](https://learn.microsoft.com/power-bi/developer/projects/projects-overview). Source checks and screenshot evidence are distinct from Desktop runtime validation.
