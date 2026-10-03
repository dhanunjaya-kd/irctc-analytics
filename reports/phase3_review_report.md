# Phase 3 Final Review Report

**Project:** IRCTC-inspired Data Analytics Platform (independent portfolio project; all data synthetic)
**Scope:** read-only review audit of Phase 3 (Excel and Google Sheets). No workbook, template or data file was modified during the audit.
**Evidence:** `reports/phase3_audit_results.txt` (raw outputs), `python/tests/audit_phase3.py` (re-runnable), `reports/phase3_validation.txt` (Phase 3 tests).
**Verdict:** Phase 3 is functionally complete and numerically verified, but it is **not ready for final approval**: one requirement cannot be recovered, and the audit found one layout defect, one sample-design gap and several labelling and coverage gaps. All are listed below with corrections, none applied yet.

## Status after the final correction pass

**Fixed:** O-2 (pivot dashboard charts moved below the KPI table, legends added); sample wording (the 48-run sample is now labelled a balanced, run-complete analytical sample, balanced by journey month only, and never called representative); O-6 (synthetic and sampling labels added to the sample, fact, support, work and solution sheets; `data_origin` column added to the `Data_*` and `Fact_*` sheets); O-8 (consistency-matrix rows 14 and 15); O-9 (growth zero-denominator guard); O-10 (formula-library wording); six primary analytical areas formalised in the BRD, plan, README sheet and setup instructions (O-1 handled by that formalisation).

**Not changed (outside the correction pass):** O-3 sample design (no Premium or 1A runs; now clearly labelled), O-4 route and train-operations views, O-5 pivot-fed cards and PivotCharts, O-7 main-workbook legend labels in LibreOffice, and all checks that need Microsoft Excel, Google Sheets or Power Query.

The findings below describe the state before this pass.

---

## 1. The original six required sheets

**Searched:** 57 current project text files, the Phase 1 ZIP (9 text files), the Phase 2 delta ZIP (20), the saved transcript and journal (`/mnt/transcripts`), and the uploads folder (empty).

**Found (the only traces):**

| File | Text |
|---|---|
| `docs/BRD.md`, acceptance criterion AC-6 | "Excel workbook has the six required sheets and the required functions; unsupported items come with exact instructions" |
| `docs/project_plan.md` Phase 3 row, as delivered in Phase 1 and Phase 2 (overwritten by my Phase 3 update; preserved in the Phase 1 ZIP and the transcript) | "Workbook (6 required sheets)" |

**Result: the original six sheet names, their order, their specifications and the list of "required functions" cannot be recovered.** They are not in the BRD, plan, earlier documents, transcripts or uploads; the original prompt text is not stored. I have not invented them. AC-6 stays **open** until you supply or confirm them.

Other Excel-related requirement text that *is* recoverable: BRD O-9 (deliver Excel and Google Sheets analysis), Q10 (monthly gross, refund and net value; Excel listed as a place), the plan's feasibility row (formulas, data validation, conditional formatting and charts; PivotTables and Power Query as instructions if not generatable), and your Phase 3 message (8 deliverables, data strategy, sampling rules).

### Proposed mapping of the 14 sheets to six analytical areas (a proposal, not the original names)

| Analytical area | Sheets in `excel/IRCTC_Booking_Analytics_Workbook.xlsx` |
|---|---|
| A. Documentation and definitions | `README`, `KPI_Definitions`, `Parameters` |
| B. Data (run-complete sample) | `Data_Bookings`, `Data_Passengers`, `Data_Cancellations`, `Data_ClassRuns`, `Data_Runs` |
| C. KPI calculation and aggregation | `KPI_Calc`, `Monthly_Aggregates` |
| D. Analysis | `Cancellation_Refund`, `Occupancy_Demand` |
| E. Dashboard | `Dashboard` |
| F. Validation | `Validation` |

**Action for you:** send the original six names and specs, or confirm this mapping. If the original list contained items such as a separate cleaned-data sheet or pivot-analysis sheet, those would need to be added or mapped.

---

## 2. Deliverable check (hash-verified against the ZIP)

All present on disk, in `irctc-analytics-phase3-delta.zip` (61 entries, integrity OK, 0 entries differing from disk):

| # | Deliverable | Path |
|---|---|---|
| 1 | Booking analytics workbook | `excel/IRCTC_Booking_Analytics_Workbook.xlsx` |
| 2 | Cleaning and validation exercises | `excel/IRCTC_Data_Cleaning_Exercises.xlsx` |
| 3 | PivotTable KPI dashboard | `excel/IRCTC_KPI_Pivot_Dashboard.xlsx` |
| 4 | Cancellation and refund analysis | sheet `Cancellation_Refund` in deliverable 1 |
| 5 | Train occupancy and demand analysis | sheet `Occupancy_Demand` in deliverable 1 |
| 6 | Google Sheets KPI trackers | `google_sheets/KPI_Tracker_Template.xlsx`, `Cancellation_Refund_Tracker_Template.xlsx`, `Occupancy_Waitlist_Tracker_Template.xlsx` |
| 7 | Formulas and Power Query M | `excel/FORMULA_LIBRARY.md`, `excel/power_query/*.pq` (14 files) |
| 8 | Manual setup instructions | `excel/SETUP_INSTRUCTIONS.md`, `google_sheets/SETUP_INSTRUCTIONS.md` |

Deliverables 4 and 5 are sheets, not standalone workbooks (confirm this packaging is acceptable). Correction to my earlier wording: there are **six** `.xlsx` files (3 Excel, 3 Google Sheets templates), not nine.

---

## 3. What was verified, and by what

### Executed in LibreOffice 24.2 (real recalculation or rendering)
* All 6 workbooks open; 0 formula-error cells after a forced full recalculation; **stored values equal fresh recalculation (0 differing cells)**.
* Main workbook: 24 of 24 Validation checks; 36 of 36 KPI rows (Excel formula vs independent Python); class-filter scenario (SL) matches Python on 15 cards; tampering with data is detected.
* Exercises: 29 of 29 formula counts equal the cleaner's independent detection; 11 of 11 validation checks; a changed raw value flips the matching check to FAIL.
* Cross-workbook consistency: main vs pivot cards 14 of 14 identical; main monthly vs Google KPI tracker 264 of 264 cells; vs Google cancellation tracker 96 of 96; full-dataset occupancy 0.7348903805 in both main and Google; monthly totals equal `reports/kpi_reference_values.csv`.
* Pivot values equal pandas (status by class, refunds by month, booking status).
* Visual rendering of the main Dashboard, Occupancy_Demand, pivot Dashboard and Answer_Key (this found defects O-2 and O-7).

### Static checks (no Office application)
* Every XML part of all 6 files is well-formed; 105,453 formulas; 0 `#REF!`; 0 references to missing sheets; max formula length 464 and nesting 9; no function newer than Excel 2007.
* Pivot structure consistent: 4 caches, 7 tables, source ranges exist, record counts equal source rows (23,565 / 2,259 / 143 / 11,652).
* Tests: Phase 3 **22 of 22**; Phase 2 regression **24 of 24** (72/72 checks, 30/30 detection); Phase 1 **15 of 15**; 20 original data files unchanged (SHA-256 manifest).

### Still requires Microsoft Excel
* Open without a repair prompt, especially the LibreOffice-authored pivot workbook and its charts; Refresh All; slicers (manual steps provided).
* Formula results and locale behaviour: `TEXT(date,"yyyy-mm")` format codes depend on the Excel language; `DATEVALUE` on ISO text.
* Data-bar, colour-scale and drop-down rendering; chart legends and styling.

### Still requires Google Sheets
* Import fidelity of formulas, drop-downs, conditional formats and charts for the 3 templates (charts may need re-creating).

### Still requires a Power Query engine
* Execution of all 14 `.pq` scripts (only structure was linted).

---

## 4. Sampling and synthetic labelling

**Visible where it matters:** banner with "768 simulated runs vs 19,708 scheduled (3.9%), not IRCTC network-wide" on the main README, Dashboard, Monthly_Aggregates, Cancellation_Refund and Occupancy_Demand; the pivot README and Dashboard; the exercises README; **every sheet of all 3 Google templates**. Docs stating the figure: README, assumptions, data_sources, project_plan, KPI_consistency_matrix, both setup files. The sample CSVs (`data/sample/excel/*.csv`) carry `data_origin = SYNTHETIC`; derived CSVs carry `DERIVED`.

**Gaps (see O-3, O-6):**
* No on-sheet synthetic/sampling label on 9 of 14 main sheets (`KPI_Definitions`, `KPI_Calc`, `Validation`, `Parameters`, all five `Data_*`), 11 of 13 pivot-workbook sheets (`PT_1` to `PT_7`, four `Fact_*`), and 13 of 19 exercise sheets (the five `Raw_*` do carry a `data_origin` column).
* The `Data_*` and `Fact_*` sheets have no `data_origin` column although the project rule is to label synthetic data in columns.
* One main chart title (occupancy and waitlist pressure by month) says neither "synthetic" nor "sampled".

**The 48-run sample is labelled as a sample, but it is not representative.** It is stratified by month only (2 of 32 runs each month):

| Measure | Full | Sample |
|---|---|---|
| Premium train runs | 29 runs (3.8%) | **0** |
| 1A class-runs | 29 (1.3%) | **0** |
| Trains / routes covered | 52 / 40 | 32 / 29 |
| Weekday share, largest gaps | | Wed -7.0 pp, Mon +6.5 pp, Thu +6.4 pp |
| Occupancy | 73.5% | 70.4% (-4.2%) |
| Passenger cancellation rate | 13.8% | 13.1% (-4.9%) |
| Waitlist clearance | 19.2% | 18.1% (-5.9%) |
| Average fare per passenger | ₹1,513 | ₹1,430 (-5.5%) |
| On-time performance | 74.8% | 78.3% (+4.7%) |

With the dashboard filter set to **1A**, every card shows 0 or blank with no explanatory message (no error values).

---

## 5. KPI definitions and formulas

Denominators in the workbooks match `docs/KPI_definitions.md` for every KPI that appears in Excel (passenger-based cancellation rate with booking-based companion; initial-status waiting-list demand, clearance and uncleared; fully confirmed bookings with mixed reported separately; occupancy on passenger counts; OTP and average delay on runs with a recorded delay; average fare on passengers). Excel, pivot dashboard, Google templates and Python agree numerically (section 3). SQL, Power BI and Tableau do not exist yet, so consistency with them is **specified, not demonstrated** (`docs/KPI_consistency_matrix.md`).

Exceptions: KPI 15 (Route-Level Demand) is not in the main workbook, and the monthly growth formula has no zero-denominator guard (O-4, O-8, O-9).

---

## 6. Outstanding issues

| ID | Severity | Issue | Evidence | File(s) | Recommended correction |
|---|---|---|---|---|---|
| O-1 | **High (blocks AC-6)** | Original six required sheets cannot be recovered | Section 1 | `docs/BRD.md`, `docs/project_plan.md` | You supply or confirm names and specs; then map or add sheets and re-validate |
| O-2 | **High** | Pivot dashboard charts sit on top of the KPI table and banner; neither chart has a legend | Rendered image; drawing anchors A2:E15 and A16:E32 over table A4:E20; no `<c:legend>` | `excel/IRCTC_KPI_Pivot_Dashboard.xlsx`; source `python/src/build_excel_pivot.py` (chart rectangle X=9000, Y=800 and 9800; legend) | Move charts to the right of column F or below row 22, enable legends, rebuild, re-render and re-test |
| O-3 | **Medium-high** | Sample is month-stratified only: no Premium or 1A runs, weekday skew, partial route and train coverage; 1A filter shows silent zeros | Section 4 | `python/src/kpi.py` (`select_sample`), `data/sample/excel/*.csv`, main and pivot workbooks | Stratify by month x class x train type (for example 3 runs per month with forced Premium and 1A coverage), re-run tests; add a "no 1A class-runs in sample" message; state remaining non-representativeness |
| O-4 | **Medium** | No route-level or train-level view in Excel; `route_summary.csv`, `train_runs.csv`, `refund_events_summary.csv` are not used by any workbook or M script; no dedicated train-operations analysis beyond monthly OTP and delay | Coverage audit | main workbook; `data/processed/derived/` | Add route and train-operations sheets (with simulated-run counts beside each figure, since trains have 9 to 20 runs) and matching `.pq` scripts, or confirm out of scope |
| O-5 | **Medium** | "PivotTable-based" dashboard: KPI cards are ordinary formulas on the fact sheets, and the 2 charts are plain charts on pivot output, not PivotCharts | Static audit | `excel/IRCTC_KPI_Pivot_Dashboard.xlsx` | Add GETPIVOTDATA cards and PivotCharts (needs Excel to verify), or rename and document as "pivot tables plus formula KPI cards" |
| O-6 | **Medium-low** | On-sheet label gaps and no `data_origin` column on sample sheets | Section 4 | `build_excel_workbook.py`, `build_excel_pivot.py`, `build_excel_exercises.py` | Add a one-line banner and a `data_origin` column to `Data_*`, `Fact_*`, `PT_*`, `KPI_Calc`, `Validation`, `Work_*`; fix the chart title |
| O-7 | Low | Chart series names stored as literal text; LibreOffice legends show the workbook title instead of the series name (Excel expected to be fine) | Rendered images; chart XML | `build_excel_workbook.py`, `build_google_sheets_templates.py` | Name series from cells (`=Sheet!$B$4`) for portability to Excel, Sheets and LibreOffice |
| O-8 | Low | `KPI_consistency_matrix.md` overstates coverage for KPI 14 (pivot column) and KPI 15 (Excel column) | Static review | `docs/KPI_consistency_matrix.md` | Correct the two rows (or add the coverage via O-4) |
| O-9 | Low | Monthly growth formula has no zero-denominator guard (KPI rule: NULL) | Formula review; no month is 0 today | `python/src/build_excel_workbook.py` | Guard with `IF(prev=0,"",...)` |
| O-10 | Low | `FORMULA_LIBRARY.md` does not name about 20 basic functions used (COUNT, COUNTA, EXACT, IFERROR, ISTEXT, LEN, NOT, OR, SEARCH, SUMIF, TIMEVALUE ...) | Static audit | `excel/FORMULA_LIBRARY.md` | Make it exhaustive or reword as illustrative |
| O-11 | Low | Cosmetic: counts shown as 2-decimal numbers in numerator and denominator columns; raw axis numbers; multi-measure pivots list measures down rows (documented) | Rendered images | main and pivot workbooks | Number formats; optional |
| O-12 | Info | Deliverables 4 and 5 are sheets inside one workbook | Section 2 | main workbook | Confirm, or split into standalone files |

## 7. Missing or partial requirements

1. **Six required sheets and "required functions" (BRD AC-6):** unknown, cannot be assessed (O-1).
2. **Representative sample (your data strategy):** not met for class, train type and weekday (O-3).
3. **Focused analytical datasets in Excel for train operations (and route views):** datasets exist but are not used in any workbook (O-4).
4. **PivotTable-driven dashboard:** partially met (O-5).
5. **Excel, Google Sheets and Power Query execution checks:** cannot be performed here (section 3).
6. **SQL, Power BI and Tableau KPI consistency:** not applicable until Phases 4, 6 and 7.

## 8. Recommended correction round (proposed; not started)

Fix O-2, O-3, O-6, O-7, O-8, O-9, O-10 and, if you want it in Phase 3, O-4 and O-5. Then re-run `python python/src/build_phase3.py`, `python python/tests/test_phase3_excel.py`, the Phase 1 and 2 regressions and `python python/tests/audit_phase3.py`, re-render the dashboards, and issue a new delta ZIP. Changing the sample changes the sample-based values in the main and pivot workbooks, so the validation results would be regenerated, not assumed.

## 9. New files from this review (not in the Phase 3 ZIP)

`reports/phase3_review_report.md` (this file), `reports/phase3_audit_results.txt`, `python/tests/audit_phase3.py`. They can be added to the final ZIP after approval.

## 10. Final approval checklist

**Verified**
- [x] All 8 deliverables exist and are in the ZIP (hash-verified)
- [x] Original data unchanged (20 files, SHA-256 manifest)
- [x] All 6 workbooks open in LibreOffice with 0 formula errors; stored values equal fresh recalculation
- [x] Excel, pivot dashboard, Google templates and Python agree numerically
- [x] Denominators documented and consistent for every KPI present in Excel
- [x] Phase 3 tests 22/22; Phase 2 regression 24/24; Phase 1 checks 15/15
- [x] Sampling limitation stated in all dashboards' banners, all 3 templates and the documentation

**Open**
- [ ] O-1: original six sheet names and specs supplied, or mapping confirmed
- [ ] O-2: pivot dashboard layout corrected and re-rendered
- [ ] O-3: sample design decision (stratification) and 1A message
- [ ] O-4: decision on route and train-operations views
- [ ] O-5: decision on pivot-fed cards and PivotCharts
- [ ] O-6, O-7: labelling and chart-name corrections (or accepted as-is)
- [ ] Opened and checked in Microsoft Excel (including pivots)
- [ ] Imported and checked in Google Sheets
- [ ] Power Query scripts run in Excel
- [ ] Final approval of Phase 3 (Phase 4 has not been started)
