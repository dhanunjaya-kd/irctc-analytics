# KPI Definitions

The single source of truth for every metric in SQL, Python, Excel, Power BI and Tableau. If a tool disagrees with this document, the tool is wrong until proven otherwise.

**Labelling.** The data is synthetic. Every KPI value describes the synthetic dataset and is not an IRCTC or Indian Railways statistic. Capacity, occupancy, delay, fare and refund figures are simulated.

**What changed since the Phase 1 draft.** Status is now tracked per passenger, so occupancy, cancellation rate and waiting-list demand are defined on passengers; refunds are defined per cancellation event; and only a sample of train runs is simulated, which affects how volumes are read (section 1.9). See [assumptions.md](assumptions.md).

---

## 1. Global rules

### 1.1 Population

All KPIs use **valid, de-duplicated, cleaned** records only. Records rejected in Phase 2 cleaning are excluded and counted in the [data quality report](data_quality_report.md).

### 1.2 Booking, passenger, seat and status

- **Booking count** = number of `bookings` rows. **Passenger count** = number of `booking_passengers` rows. They differ because a booking carries 1 to 6 passengers. Never use one for the other.
- **Status lives on the passenger** (`initial_status`, `final_status`). `bookings.booking_status` is a derived roll-up: a shared status, or `Mixed` when passengers differ.
- **Seats** come only from `seat_capacity`.
- Status meanings and seat-equivalents are in the [data dictionary](data_dictionary.md#1-core-concepts-booking-passenger-seat-status).

### 1.3 Completed journeys

A **completed-journey passenger** is a passenger whose `final_status` is Confirmed or RAC and whose booking's `journey_date` is on or before `as_of_date`. **Cancelled and Waitlisted passengers are never counted as completed journeys.**

### 1.4 Date attribution

| Measure family | Attributed to | Why |
|---|---|---|
| Demand, occupancy, revenue, cancellations, refunds, growth | `journey_date` (cohort basis) | Numerator and denominator then describe the same set of journeys |
| Booking-behaviour views (lead time, "bookings by day of booking") | `booking_ts` date | These describe when people book |
| Punctuality | `run_date` | Delay belongs to the run |

A report that uses the booking-date basis must say so in its title or axis label.

### 1.5 Ratios

- Every percentage states its numerator and denominator below.
- Group-level ratios are **ratio of sums** (for example total booked seats divided by total capacity), never an average of per-row percentages.
- A ratio with a zero denominator is `NULL`, not 0.

### 1.6 Joins and double counting

Bookings, passengers, cancellation events, capacity and operations sit at different grains. Aggregate each to the grain of the join key **before** joining.

- Occupancy: count passengers by final status per (train, journey date, class) first (passengers join to bookings for the run and class), then join that result to `seat_capacity`. Joining passengers to capacity directly would repeat capacity once per passenger.
- Refunds: `cancellations` is one row per event. Join events to bookings only through an already-aggregated `booking_id`, or fares would repeat once per event.

### 1.7 Parameters

| Parameter | Value | Source |
|---|---|---|
| `rac_seat_weight` | 0.5 (configurable simulation assumption, not an official rule) | [assumptions.md](assumptions.md#2-project-parameters) |
| `on_time_threshold_min` | 15 | same |
| `as_of_date` | 2026-08-31 | same |

### 1.8 Reconciliation tolerance

The same KPI computed in different tools must match: **counts exactly, currency to 2 decimal places, ratios to 4 decimal places**. Any difference is investigated, not rounded away.

### 1.9 Reading volumes: only a sample of train runs is simulated

The dataset simulates 32 train runs per calendar month, not every scheduled run (D-01). Raw monthly booking and passenger totals therefore reflect how many runs were simulated as well as demand. **For trends, growth, comparisons and forecasts prefer per-run and capacity-normalised measures**: bookings per simulated run, occupancy, waiting-list pressure, cancellation rate. Train-level and route-level results rest on few runs (about 15 per train) and should show their run counts.

### 1.10 Consistency across tools

The same definitions and denominators are implemented once in Python (`python/src/kpi.py`) and reconciled in Excel and the Google Sheets templates (Phase 3). SQL, Power BI and Tableau must reproduce `reports/kpi_reference_values.csv` before they are delivered (Phases 4, 6, 7). The tool-by-tool status and the reconciliation contract are in [KPI_consistency_matrix.md](KPI_consistency_matrix.md). Phase 3 workbooks show the denominator beside every rate and label all figures as synthetic and sampled.

---

## 2. Core KPIs

### 1. Total Bookings
- **Definition:** number of valid bookings, all statuses.
- **Formula:** `COUNT(DISTINCT booking_id)`
- **Unit:** count of bookings
- **Source:** `bookings`

### 2. Total Passengers
- **Definition:** passengers across all valid bookings, all final statuses. This is booked demand in passengers, **not** travelled passengers.
- **Formula:** `COUNT(*)` on `booking_passengers`, which equals `SUM(num_passengers)` on `bookings` (BR-03)
- **Unit:** count of passengers
- **Companion:** *Completed-Journey Passengers* = passengers meeting section 1.3

### 3. Confirmed Booking Count
- **Definition:** bookings whose roll-up status is Confirmed, meaning **every** passenger finished Confirmed. Bookings with any RAC, Waitlisted or Cancelled passenger are not included.
- **Formula:** `COUNT(*) FILTER (WHERE booking_status = 'Confirmed')`
- **Companion:** *Mixed Booking Count* = `COUNT(*) FILTER (WHERE booking_status = 'Mixed')`, bookings whose passengers ended in different statuses. Show it next to this KPI so mixed bookings are never hidden.

### 4. Cancelled Booking Count
- **Definition:** bookings whose roll-up status is Cancelled, meaning every passenger was cancelled by the passenger (possibly over several events). System auto-refunds of uncleared waiting lists are **not** cancellations.
- **Formula:** `COUNT(*) FILTER (WHERE booking_status = 'Cancelled')`

### 5. Cancellation Rate
- **Basis:** passenger-based, because cancellations can be partial.
- **Numerator:** passengers with `final_status = 'Cancelled'`
- **Denominator:** Total Passengers in the same filter context, meaning all four final statuses
- **Formula:** `Cancelled passengers / Total Passengers`
- **Unit:** percentage of passengers
- **Companion:** *Booking Cancellation Rate* = Cancelled Booking Count / Total Bookings (denominator: Total Bookings). It understates cancellation because partially cancelled bookings are `Mixed`. A chart must say which basis it uses.
- **Note:** waitlisted passengers refunded by the system are **not** cancelled passengers.

### 6. Gross Booking Value
- **Definition:** sum of the fares of all valid bookings, all statuses, **before refunds**. It is **not** company revenue and **not** profit: it includes fares that were later refunded and excludes taxes and fees (A-03).
- **Formula:** `SUM(total_fare)`, which equals `SUM(fare_amount)` on `booking_passengers` (BR-03)
- **Unit:** INR

### 7. Refund Amount
- **Definition:** money returned through cancellation/refund events, both `Passenger` and `System`. Each event returns the covered passengers' fares minus the cancellation charge under the illustrative rules (A-10). It is **not** assumed to equal the original fare.
- **Formula:** `SUM(refund_amount)` from `cancellations`
- **Unit:** INR
- **Split shown where useful:** `Passenger` refunds and `System` refunds
- **Companion:** *Retained Cancellation Charges* = `SUM(cancellation_charge)`. Per event, `refund_amount + cancellation_charge = original_fare_amount` (BR-11).

### 8. Net Booking Value
- **Definition:** Gross Booking Value minus Refund Amount for the same cohort (section 1.4). Still **not** revenue or profit.
- **Formula:** `Gross Booking Value - Refund Amount`
- **Unit:** INR

### 9. Average Fare
- **Definition (primary):** average fare per passenger.
- **Formula:** `Gross Booking Value / Total Passengers`
- **Denominator:** Total Passengers, all statuses (consistent with the gross numerator)
- **Secondary, labelled when used:** average fare per booking = `Gross Booking Value / Total Bookings`
- **Unit:** INR

### 10. Seat Occupancy %
- **Definition:** share of simulated seat capacity occupied on train-class runs, using **passenger counts** at chart preparation: Confirmed passengers count fully and RAC passengers at `rac_seat_weight`.
- **Booked Seats (seat-equivalents):** `confirmed_passengers + rac_seat_weight * rac_passengers`, counting passengers by `final_status`
- **Formula:** `SUM(Booked Seats) / SUM(total_seats)`, evaluated over train-class runs
- **Denominator:** total seats from `seat_capacity` for the **same train, journey date and class** as the passengers counted
- **Treatment of statuses:** Confirmed = 1, RAC = 0.5, Waitlisted = 0, Cancelled = 0
- **Components kept distinguishable:** *Confirmed Occupancy %* = `confirmed_passengers / total_seats`; *RAC Occupancy %* = `rac_seat_weight * rac_passengers / total_seats`; their sum is Seat Occupancy %. **Waitlisted passengers are never part of occupancy**; they are shown as *Waitlist Pressure %* = `waitlisted_passengers / total_seats` (supplementary, section 3).
- **Scope:** occupancy is measured over the whole journey per train-class run. **Occupancy of intermediate station segments is outside the current scope** (A-06).
- **Rules:** capacity comes only from `seat_capacity`; passengers without a matching capacity row are excluded from numerator and denominator and reported as exceptions; a value above 100% is a data error (BR-08) and is investigated, not capped; the seat scale and the RAC weight are simulation assumptions (A-09, A-12).

### 11. Waiting-List Demand
- **Definition:** passengers who were on the waiting list **at booking time**, whatever happened afterwards. It measures unmet demand for confirmed seats.
- **Formula:** `COUNT(*) FILTER (WHERE initial_status = 'Waitlisted')` on `booking_passengers`
- **Unit:** count of passengers
- **Companions:** *Waitlist Clearance Rate* = initially waitlisted passengers whose `final_status` is Confirmed or RAC / initially waitlisted passengers (denominator: initially waitlisted passengers). *Uncleared Waitlist Passengers* = passengers with `final_status = 'Waitlisted'`, refunded by `System` events.
- **Note:** this replaces the Phase 1 definition based on end-of-life status, which could not see waitlisted passengers who later cleared. It says nothing about the cause.

### 12. On-Time Performance %
- **Numerator:** train runs with `arrival_delay_min <= on_time_threshold_min`
- **Denominator:** train runs with a non-NULL `arrival_delay_min` in the same filter context
- **Formula:** `on-time runs / runs with a recorded arrival delay`
- **Unit:** percentage of train runs
- **Note:** the 15-minute threshold is a project convention (A-11). `arrival_delay_min` is NULL where the source value was missing or out of range; those runs are excluded, never imputed.

### 13. Average Delay
- **Definition:** mean arrival delay per train run, with early arrivals counted as 0 delay.
- **Formula:** `AVG(GREATEST(arrival_delay_min, 0))`
- **Denominator:** train runs with a non-NULL `arrival_delay_min`
- **Unit:** minutes
- **Companion:** *Average Delay of Late Runs* = the average over runs above the threshold only. Always labelled as such.

### 14. Monthly Booking Growth
- **Definition:** percentage change in Total Bookings from the previous month.
- **Formula:** `(Bookings_m - Bookings_(m-1)) / Bookings_(m-1)`, with bookings grouped by journey month
- **Denominator:** the previous month's Total Bookings; `NULL` if it is 0 or the month is the first in the data
- **Note:** simulated runs per month are fixed at 32, so growth in this dataset reflects demand per run and which trains were sampled, not network growth (section 1.9). Show *Growth in Bookings per Simulated Run* alongside it. Growth between months of different length or season also reflects calendar effects, so read it with seasonality (Q5).

### 15. Route-Level Demand
- **Definition:** passengers booked on a route, all statuses, shown with the final-status split (Confirmed, RAC, Waitlisted, Cancelled).
- **Formula:** `SUM(num_passengers) GROUP BY route_id`
- **Ranking:** `RANK() OVER (ORDER BY demand DESC)`. Ties share a rank.
- **Why all statuses:** it includes waitlisted requests, which is the unmet demand a capacity review needs to see.
- **Note:** show the number of simulated runs behind each route. Compare routes on *passengers per simulated run* as well as totals.

---

## 3. Supplementary KPIs (used by the dashboards and analysis)

| KPI | Definition and formula | Denominator / notes |
|---|---|---|
| Booked Seats | `confirmed_passengers + rac_seat_weight * rac_passengers` (seat-equivalents) | Can be fractional because of RAC |
| Available Seats | `SUM(total_seats)`: total simulated capacity, **not** remaining unsold seats | Named "Available (capacity)" on dashboards |
| Remaining Seats | `GREATEST(total_seats - Booked Seats, 0)` per train-class run, then summed | Only where a capacity row exists |
| Waitlist Pressure % | `waitlisted_passengers / total_seats` for the same train-class run (final status) | Supplementary; not part of occupancy |
| Waitlist Clearance Rate | See KPI 11 | Denominator: initially waitlisted passengers |
| Mixed Booking Count | Bookings whose roll-up status is `Mixed` | Shown beside KPI 3 |
| Retained Cancellation Charges | `SUM(cancellation_charge)` | INR |
| Bookings per Simulated Run | `Total Bookings / number of simulated train runs` in the filter context | Sample-safe volume measure (section 1.9) |
| Delayed Train Count | Number of train runs with `arrival_delay_min > on_time_threshold_min` | Counts **train runs**, not distinct trains |
| Booking Lead Time (days) | `journey_date - booking_ts::date` | Used with fixed buckets for the lead-time and cancellation analysis (Q7) |
| Forecasted Demand | Model output for future periods, defined in Phase 5 | Always labelled a forecast, never shown as actual |

---

## 4. Rules that apply to every report

1. Do not count cancelled or waitlisted passengers as completed journeys.
2. Do not describe Gross or Net Booking Value as revenue or profit.
3. Do not assume a refund equals the original fare.
4. Do not count system auto-refunds of waitlisted passengers as passenger cancellations.
5. Do not include waitlisted passengers in occupancy; report them separately.
6. Do not compute occupancy from capacity and passengers that are not matched at (train, journey date, class).
7. State the denominator whenever a percentage is displayed, and state whether a cancellation rate is passenger-based or booking-based.
8. Label simulated capacity, occupancy, delay, fare and refund figures as simulated, and note that only a sample of runs is simulated.
9. Do not present correlation as causation.
