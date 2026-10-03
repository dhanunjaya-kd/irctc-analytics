# Excel Setup Instructions (Phase 3)

> **All data is synthetic.** The dataset is a **sampled simulation**: 768 simulated train runs over 24 months, compared with 19,708 scheduled runs in the modelled schedule (3.9%). It is not a representative full railway schedule, and no monthly total, occupancy rate or trend in these workbooks is an IRCTC or Indian Railways network-wide metric. Compare months with per-run and capacity-normalised measures (bookings per run, occupancy, waitlist pressure, cancellation rate).

## 1. What is in `excel/`, and what was verified

| File | What it is | How it was checked in the build environment |
|---|---|---|
| `IRCTC_Booking_Analytics_Workbook.xlsx` | Booking analytics: Dashboard (class filter), Monthly_Aggregates, Cancellation_Refund, Occupancy_Demand, KPI_Calc, Validation, Parameters, Data_* sheets (sample) | Every formula recalculated for real with LibreOffice 24.2; 24 of 24 Validation checks and 36 of 36 KPI reconciliations against the Python reference passed; no error values |
| `IRCTC_KPI_Pivot_Dashboard.xlsx` | Dashboard with 7 real PivotTables (PT_1 to PT_7), 2 charts below the KPI table and KPI cards | Pivots created with LibreOffice and compared cell by cell with pandas. **Not opened in Microsoft Excel here** (section 4 rebuilds them if Excel objects) |
| `IRCTC_Data_Cleaning_Exercises.xlsx` | 30 cleaning exercises, worked-solution formulas, answer key, validation checks | 29 of 29 formula counts equal the Python cleaner's independent detection; 11 of 11 checks pass |
| `power_query/*.pq` | Power Query M scripts | **Not executed** (no Power Query engine here); structure checked by a lint test only |
| `FORMULA_LIBRARY.md` | The formulas used, with examples | Each listed formula is used in a recalculated workbook, except where marked |

`XLOOKUP` is **not used** in any verified cell: LibreOffice 24.2 returns `#NAME?` for it, so it could not be checked. Use `INDEX`/`MATCH` (used throughout) or, in Excel 365, XLOOKUP as an exercise variant.

### Primary analytical areas of the main workbook

| Primary analytical area | Workbook tab (`excel/IRCTC_Booking_Analytics_Workbook.xlsx`) | Purpose |
|---|---|---|
| Dashboard | `Dashboard` | KPI cards with a travel-class filter, status mix by class, time-series charts |
| Monthly Aggregates | `Monthly_Aggregates` | 24 journey months from the full cleaned dataset (executive view) |
| Cancellation & Refund | `Cancellation_Refund` | Cancellation by lead time and class, refund events, monthly refunds |
| Occupancy & Demand | `Occupancy_Demand` | Occupancy, waitlist pressure and per-run demand by class and month |
| KPI Calculation | `KPI_Calc` | Every KPI as an Excel formula, reconciled with the Python reference |
| Validation | `Validation` | Formula checks and overall PASS/FAIL |

Support sheets (kept): `README`, `KPI_Definitions`, `Parameters` (documentation and parameters) and `Data_Bookings`, `Data_Passengers`, `Data_Cancellations`, `Data_ClassRuns`, `Data_Runs` (the analytical sample).

## 2. Before you start

1. Copy the data you need next to the workbooks. The workbooks are self-contained (data is embedded); Power Query reads `data\processed\cleaned\` and `data\processed\derived\`. Regenerate them with `python python/src/pipeline.py` and `python python/src/build_phase3.py` if the folders are empty.
2. Open a workbook and click **Enable Editing**. Check **Formulas > Calculation Options > Automatic**. Press **F9** to recalculate.
3. Yellow cells are inputs, blue cells are formulas. Do not overwrite blue cells.

## 3. Power Query: load the cleaned tables (exact steps)

Create the queries in this order (Data > Get Data > From Other Sources > **Blank Query**, then Home > **Advanced Editor**, paste the file contents, click Done, then rename the query exactly as shown in the first comment line of each file):

| Order | File | Query name | Load setting |
|---|---|---|---|
| 1 | `00a_DataFolder.pq` | `DataFolder` | Connection only. **Edit the path** to your `data\processed\cleaned\` folder, with trailing backslash |
| 2 | `00b_RawFolder.pq` | `RawFolder` | Connection only. Edit the path to `data\raw\synthetic\` |
| 3 | `00c_RacWeight.pq` | `RacWeight` | Connection only (0.5, a configurable simulation assumption) |
| 4 | `01_fnLoadCsv.pq` | `fnLoadCsv` | Function (connection only) |
| 5 | `02_Bookings.pq` | `Bookings` | Connection only |
| 6 | `03_Passengers.pq` | `Passengers` | Connection only |
| 7 | `03b_PassengersFact.pq` | `PassengersFact` | Connection only |
| 8 | `04a_Cancellations.pq`, `04b_SeatCapacity.pq`, `04c_TrainOperations.pq` | `Cancellations`, `SeatCapacity`, `TrainOperations` | Connection only |
| 9 | `05_MonthlyKpis.pq` | `MonthlyKpis` | **Load to a worksheet table** (Close & Load To > Table) |
| 10 | `06_OccupancyClassRuns.pq` | `OccupancyClassRuns` | Load to a table or the Data Model |
| 11 | `08_StatusLookup.pq`, then `07_CleanRawBookings.pq` | `StatusLookup`, `CleanRawBookingsPreview` | Load `CleanRawBookingsPreview` to a table (reads the RAW extract; it is only read, never modified) |

**Check the result.** `MonthlyKpis` must have 24 rows; `total_bookings` must sum to **201,182**, `total_passengers` to **405,200** and `gross_value` to **612,966,953** (see `reports/kpi_reference_values.csv`). If not, check `DataFolder` and that the files are the cleaned tables.

Notes: the first refresh may show a **Formula.Firewall** or privacy-level prompt; choose "Ignore privacy levels for this file" for local files. `06_OccupancyClassRuns.pq` finds the derived folder by replacing `cleaned` with `derived` in `DataFolder`.

## 4. Rebuild the PivotTables in Excel (if the supplied pivots do not open)

Insert > PivotTable > **From Table/Range**, choose the source sheet's full range (Ctrl+A on the data), place on a new worksheet, then set the fields:

| Pivot | Source sheet | Rows | Columns | Values (Sum of) |
|---|---|---|---|---|
| PT_1 Status by class | `Fact_Passengers` | travel_class | final_status | passengers |
| PT_2 Monthly | `Fact_Passengers` | journey_month | Σ Values (as columns) | passengers, cancelled, initial_wl, fare_amount |
| PT_3 Lead time | `Fact_Passengers` | lead_bucket | Σ Values | passengers, cancelled |
| PT_4 Refunds | `Fact_Events` | journey_month | cancellation_type | refund_amount |
| PT_5 Occupancy | `Fact_ClassRuns` | travel_class | Σ Values | total_seats, booked_seats, wl_final_pax |
| PT_6 Route waitlist | `Fact_Passengers` | route_name | Σ Values | passengers, initial_wl, uncleared_wl |
| PT_7 Booking status | `Fact_Bookings` | travel_class | booking_status | bookings |

Ratios are not pivot fields. Beside a pivot, use a formula such as `=C6/B6` (cancelled / passengers), or right-click the pivot > Value Field Settings, or Analyze > Fields, Items & Sets > Calculated Field, for example `=cancelled/passengers` (a ratio of sums). **Confirmed** in PT_7 means every passenger is Confirmed; **Mixed** is reported separately.

## 5. Slicers and timelines (cannot be created programmatically here)

1. Click inside PT_1. PivotTable Analyze > **Insert Slicer** > tick `travel_class` and `final_status` > OK.
2. Select a slicer > Slicer tab > **Report Connections** > tick every pivot you want it to drive. Pivots on the same source sheet share a cache, so one slicer can control PT_1, PT_2, PT_3 and PT_6.
3. For a month filter, use a slicer on `journey_month` (text). A Timeline needs a real date field, which the fact sheets do not carry.
4. Add slicers to the **Dashboard** sheet by cutting and pasting them there.

## 6. Dropdowns, formats and charts

* The class filter on `Dashboard!C5` is a data-validation list (All, SL, 3A, 2A, 1A, CC, 2S). Edit it under Data > Data Validation. The cards use a wildcard criterion (`*` for All) inside COUNTIFS/SUMIFS.
* Change the RAC weight on `Parameters!B2` (0 to 1) and the on-time threshold on `Parameters!B3`; every dependent cell updates.
* To extend a chart, right-click it > Select Data > edit the series range.

## 7. Google Sheets

See [../google_sheets/SETUP_INSTRUCTIONS.md](../google_sheets/SETUP_INSTRUCTIONS.md).

## 8. Known limitations

* Verified with LibreOffice 24.2, not with Microsoft Excel or Google Sheets; small rendering differences are possible.
* PivotTables were authored by LibreOffice. Multi-measure pivots list the measures down the rows; drag **Σ Values** from Rows to Columns in Excel for side-by-side.
* Power Query scripts were not executed. Report any error text and the failing step name.
* Detailed rows are a **balanced, run-complete analytical sample** (48 of 768 simulated runs): balanced by journey month only (2 runs per month), with every booking of each sampled run. It has no Premium train runs and no 1A class-runs (the 1A filter shows zeros), and its KPIs differ from the full dataset (for example occupancy 70.4% versus 73.5%). Do not generalise its results. The Monthly_Aggregates sheet uses the full dataset.
* No forecasts are presented in this phase.
