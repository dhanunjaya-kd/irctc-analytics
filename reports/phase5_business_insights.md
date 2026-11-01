# Phase 5: Business insights

> **Read this first.** The data is **synthetic** and comes from a **sampled simulation** (768 simulated runs against 19,708 scheduled runs, 3.9%). Nothing below describes actual IRCTC or Indian Railways network-wide performance, real passenger behaviour, or any forecast. Because the generator deliberately builds in seasonal and holiday demand, weekday effects, a 1% monthly demand trend, cancellation rising with lead time, and delays varying with season, distance and train type (assumption A-20), the analysis demonstrates **method** and can only rediscover what was built in. Each finding is split into OBSERVED (what the data directly shows), INTERPRETATION (a reasonable analytical reading) and LIMITATION (what cannot be concluded). Statistical associations are not causes.

Scope: 201,182 bookings, 405,200 passengers, 2,285 simulated train-class runs and 768 simulated runs over 24 months. All KPIs use the approved definitions and reconcile with `reports/kpi_reference_values.csv`.

## 1. Demand level and the sampling design

**OBSERVED**

* Bookings per simulated run range from 186 (2024-09) to 359 (2026-05); the 24-month average is 262 bookings and 528 passengers per run.
* A straight-line fit to bookings per run rises by +2.36 per month (95% CI +0.23 to +4.49), about 0.9% of the average per month; R-squared = 0.19, p = 0.032.

**INTERPRETATION**

* Per-run measures are the valid basis for comparing months: exactly 32 runs are simulated every month, so raw monthly totals mostly reflect which trains were sampled.
* The fitted slope of about 0.9% per month is consistent in size with the 1% monthly demand trend documented in A-20; the low R-squared reflects strong seasonal swings around the line.

**LIMITATION**

* Synthetic, sampled simulation (768 of 19,708 scheduled runs; assumptions A-02, A-16): this describes the dataset, not IRCTC or any real railway network.
* The slope describes these 24 months only; it is not extrapolated and not a forecast.

## 2. Peak travel periods and seasonality

**OBSERVED**

* Runs inside peak travel periods carry 639 passengers each against 498 on other days; occupancy is 84.2% against 70.7%.
* Test S-02: difference +96 to +185 passengers per run (95% CI), Cohen's d = 0.59, p < 0.001. Test S-03 on occupancy: d = 0.72, p < 0.001.

**INTERPRETATION**

* Peak-period demand is clearly higher in this dataset (medium effect on passengers per run, medium on occupancy): the method recovers the modelled peak-period uplift (A-15, A-20).
* For capacity planning in a real setting this is the kind of comparison that matters, but only real data could support a real conclusion.

**LIMITATION**

* Synthetic, sampled simulation (768 of 19,708 scheduled runs; assumptions A-02, A-16): this describes the dataset, not IRCTC or any real railway network.
* Peak windows are modelled, not an official calendar (A-15). Only two years are simulated, so each calendar month is observed twice.

## 3. Weekday and weekend demand

**OBSERVED**

* Runs on weekend days average 500 passengers against 536 on weekdays; the weekend-minus-weekday difference is -73 to +1 (95% CI), Welch p = 0.054.
* By weekday, passengers per run are highest on Friday (624, 96 runs) and lowest on Tuesday (452, 137 runs).

**INTERPRETATION**

* The weekend-versus-weekday contrast is not statistically distinguishable from zero here, although weekday effects are built into the generator (A-20). That illustrates how much a 768-run sample can resolve: with 63 to 158 runs per weekday the intervals overlap.

**LIMITATION**

* Synthetic, sampled simulation (768 of 19,708 scheduled runs; assumptions A-02, A-16): this describes the dataset, not IRCTC or any real railway network.
* A non-significant test does not show that no effect exists, only that this sample cannot detect it.

## 4. Capacity and occupancy

**OBSERVED**

* Seat occupancy is 73.5% overall (Confirmed 70.8% plus RAC 2.7%); waitlist pressure is 5.7% of seat supply. Bootstrap 95% interval for occupancy: 71.9% to 74.9%.
* Across 2,285 class-runs the median occupancy is 76.1%; 31.2% are at or above 95% and 20.0% are below 50%.
* Class occupancy ranges from 52.5% (CC, 34 class-runs) to 76.8% (3A); the difference between classes is significant (S-05, p < 0.001) with a small effect (epsilon-squared = 0.026).
* Train-level occupancy ranges from 35.6% (S1017) to 97.6% (S1015); each train has only 9 to 20 simulated runs.

**INTERPRETATION**

* The average hides a wide spread: 31% of class-runs are nearly full while 20% are under half full, so average occupancy alone would mislead a capacity discussion.
* Waitlisted passengers hold no seat, so occupancy stays at or below 100% by construction; waitlist pressure is the separate signal of unmet demand.

**LIMITATION**

* Synthetic, sampled simulation (768 of 19,708 scheduled runs; assumptions A-02, A-16): this describes the dataset, not IRCTC or any real railway network.
* Capacity is simulated (A-12: 1 to 3 coaches per class with real seats per coach), the RAC weight of 0.5 is a configurable assumption (A-09), and train and class rankings rest on few runs, so they are indicative only.

## 5. Waiting list

**OBSERVED**

* 36,876 passengers (9.1%) were waitlisted when booking. Only 19.2% (95% CI 18.8% to 19.6%) cleared to Confirmed or RAC; 24,200 (65.6%) were still waitlisted at chart preparation and refunded by the System.
* Clearance by class ranges from 12.8% (2A) to 25.6% (CC); the difference is statistically detectable (S-11, p < 0.001) but small (Cramer's V = 0.04).

**INTERPRETATION**

* In this simulation most waitlist demand never converts to a seat, which follows from the queue rules and the cancellation-driven clearing built into the generator (A-08, A-19).
* Uncleared waitlist passengers are the clearest measure of unmet demand in the dataset.

**LIMITATION**

* Synthetic, sampled simulation (768 of 19,708 scheduled runs; assumptions A-02, A-16): this describes the dataset, not IRCTC or any real railway network.
* Auto-refunds of uncleared waitlists are a synthetic business rule (A-19). The S-11 p-value is optimistic because passengers cluster within bookings and runs; rely on the effect size.

## 6. Cancellations and refunds

**OBSERVED**

* The passenger cancellation rate is 13.8% (cluster-bootstrap 95% CI 13.7% to 14.0%); the booking-based rate is 13.2% because 3,943 bookings were only partially cancelled.
* Booking-based cancellation rises with lead time from 9.5% of passengers (0-3 days) to 22.4% (61-120 days); chi-square p < 0.001, Cramer's V = 0.11.
* Cancellation is lowest in 1A (8.1%) and highest in SL (14.6%).
* Refunds total INR 107,083,527 (17.5% of gross booking value): INR 71,884,437 from passenger cancellations and INR 35,199,090 from System auto-refunds; INR 9,656,744 was retained as cancellation charges.

**INTERPRETATION**

* The lead-time gradient is a recovered built-in pattern (A-20), not evidence that booking early causes cancellation.
* About 33% of refunded value comes from System refunds of uncleared waitlists rather than from passengers choosing to cancel, which matters when interpreting refund totals.

**LIMITATION**

* Synthetic, sampled simulation (768 of 19,708 scheduled runs; assumptions A-02, A-16): this describes the dataset, not IRCTC or any real railway network.
* Fares, charges and refunds follow illustrative rules, not real tariffs or refund policies (A-10).

## 7. Booking value and fares

**OBSERVED**

* Gross booking value is INR 612,966,953, net booking value INR 505,883,426 (82.5% of gross); average fare per passenger INR 1,512.75 (95% CI 1,509 to 1,516).
* The fare distribution is right-skewed: median INR 1,053, 95th percentile INR 3,694; mean fare by class ranges from INR 754 (2S) to INR 6,672 (1A).
* Fare per passenger is positively correlated with route distance (Spearman rho = 0.48).

**INTERPRETATION**

* Class mix and distance explain most of the spread in fares.
* The distance relationship is mechanical, because fares are generated from distance, class and age (A-10); it is not a pricing discovery.

**LIMITATION**

* Synthetic, sampled simulation (768 of 19,708 scheduled runs; assumptions A-02, A-16): this describes the dataset, not IRCTC or any real railway network.
* Gross and net booking value are not revenue or profit (A-18).

## 8. Punctuality

**OBSERVED**

* On-time performance (arrival delay of at most 15 minutes) is 74.8% (95% Wilson interval 71.5% to 77.8%) over 745 runs with a recorded delay; the average delay is 19.0 minutes with early arrivals counted as 0.
* On-time share by season: Winter 70.6%, Summer 78.4%, Monsoon 73.1%, Post-Monsoon 79.0%. Seasonal differences are not significant (delay S-06, p = 0.079; on-time share S-07, p = 0.206).
* Passengers per run and arrival delay are essentially uncorrelated (S-10, Spearman rho = 0.02, 95% CI -0.06 to 0.10).

**INTERPRETATION**

* With 124 to 249 runs with a recorded delay per season, only large seasonal differences would be detectable; the seasonal effect built into the generator (A-20) is too small to resolve here.
* Busier runs are not later in this dataset, consistent with delays being generated from season, distance and train type rather than from demand.

**LIMITATION**

* Synthetic, sampled simulation (768 of 19,708 scheduled runs; assumptions A-02, A-16): this describes the dataset, not IRCTC or any real railway network.
* 23 runs have no recorded arrival delay; they are excluded, not imputed. The 15-minute threshold is a project convention (A-11), not the railway's punctuality standard.

## 9. What this analysis can and cannot support

* **Can support:** a demonstration of a reproducible analytics workflow (loading, validation, cleaning, KPI calculation, reconciliation, EDA, statistics, visualisation) whose KPIs agree with the approved definitions and with the SQL layer.
* **Cannot support:** any statement about actual IRCTC or Indian Railways performance, real passenger behaviour, real fares, or the future. No forecast is made or implied.
* **Would be needed for real conclusions:** real booking and operations data covering the full schedule, not a 3.9% sample of simulated runs; real fare and refund rules; and a design that accounts for the clustering of passengers within bookings and runs.
