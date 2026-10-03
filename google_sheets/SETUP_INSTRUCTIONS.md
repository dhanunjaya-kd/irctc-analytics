# Google Sheets Setup Instructions (Phase 3)

> **All data is synthetic**, from a **sampled simulation** (768 simulated runs over 24 months versus 19,708 scheduled runs in the modelled schedule, 3.9%). It is not a representative full railway schedule and not IRCTC or Indian Railways network-wide data. Compare months with per-run and capacity-normalised measures. Targets and thresholds in the templates are illustrative.

## What is here

| File | Purpose |
|---|---|
| `KPI_Tracker_Template.xlsx` | Monthly KPI tracker: 18 input counts per month, 18 calculated KPIs, targets with On target / Watch / Off target status, three charts |
| `Cancellation_Refund_Tracker_Template.xlsx` | Passenger-based and booking-based cancellation rates, refunds by event type (Passenger vs System), refund % of gross, ALERT/OK flags, lead-time table and charts |
| `Occupancy_Waitlist_Tracker_Template.xlsx` | Month x class inputs, seat occupancy, confirmed and RAC occupancy, waitlist pressure, summary by class, month x class heat map |

**Native Google Sheets files could not be created** from the build environment (no Drive or Sheets connector). The templates are `.xlsx` files that import into Google Sheets. They were recalculated with LibreOffice 24.2 and compared with the Python reference (0 mismatches, 0 error values); they were **not opened in Google Sheets**. They use only functions common to Sheets, Excel and LibreOffice (SUMIFS, COUNT, IF, IFERROR-style guards with N(), INDEX).

## Import (exact steps)

1. Go to **sheets.google.com** > **Blank spreadsheet** (or open an existing one).
2. **File > Import > Upload**, choose the `.xlsx`.
3. Import location: **Replace spreadsheet** (new template) or **Insert new sheet(s)** (add to an existing file). Leave "Convert text to numbers, dates and formulas" ticked.
4. Click **Import data**. Check that the formulas on the calculation sheets show numbers, not errors.
5. **Charts:** open the Charts or Analysis sheet. If a chart is missing or restyled, select its source range and use **Insert > Chart**. Extend a chart's range when you add months.
6. **Protect the formulas:** select a calculation sheet > **Data > Protect sheets and ranges** > add a range > "Set permissions" > restrict editing to yourself. Leave the yellow input cells open.
7. **Drop-downs** (target direction, travel class) are data-validation lists and import; re-create under **Data > Data validation** if they do not.

## Use as a tracker

* **Start blank:** select the yellow sample rows and press Delete; the formulas return blanks for empty rows (denominator rule: an empty or zero denominator gives a blank, never 0).
* **Add a month:** type it in the next empty yellow row, contiguous with the previous month. The Targets sheet of the KPI tracker reads the last filled month by counting filled rows.
* **Beyond 36 months:** copy the last formula row down on the calculation sheet and extend the input rows.

## Denominators (same as `docs/KPI_definitions.md`)

| KPI | Formula | Denominator |
|---|---|---|
| Cancellation Rate (passenger-based) | cancelled passengers / total passengers | Total passengers, all final statuses |
| Booking Cancellation Rate (companion) | cancelled bookings / total bookings | Total bookings |
| Waitlist Clearance Rate | waitlisted passengers later Confirmed or RAC / waiting-list demand | Initially waitlisted passengers |
| Seat Occupancy % | (confirmed + RAC weight x RAC) / available seats | Available seats, matched per train-class run |
| Waitlist Pressure % | uncleared waitlist passengers / available seats | Available seats. Not part of occupancy |
| On-Time Performance % | on-time runs / runs with a recorded delay | Runs with a recorded arrival delay |

Fully confirmed bookings means every passenger Confirmed; mixed-status bookings are counted separately. System auto-refunds of uncleared waitlisted passengers are not passenger cancellations. The RAC weight (0.5) is on the Settings sheet and is a configurable simulation assumption, not an official rule.

## Limitations

Sampled simulation; simulated capacity and delays; illustrative fares, refunds and targets; whole-journey occupancy only; imported charts may need re-styling.
