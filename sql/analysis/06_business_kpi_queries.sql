-- 06_business_kpi_queries.sql: the 15 approved KPIs (docs/KPI_definitions.md) written directly against the core tables, with numerator and denominator shown.
-- These are independent of the analytics views; sql/validation reconciles both against reports/kpi_reference_values.csv.
-- SYNTHETIC data, SAMPLED simulation: 768 simulated runs of 19,708 scheduled (3.9%). Values are NOT IRCTC network-wide metrics; monthly totals reflect the
-- sampling design, so trends use per-run and capacity-normalised measures. Nothing here forecasts.

-- [K1] Total Bookings.
SELECT count(*) AS total_bookings FROM core.bookings;

-- [K2] Total Passengers (booked demand in passengers, all final statuses).
SELECT count(*) AS total_passengers FROM core.booking_passengers;

-- [K3] Confirmed Booking Count = bookings where EVERY passenger finished Confirmed; Mixed-status bookings are reported separately.
SELECT count(*) FILTER (WHERE booking_status = 'Confirmed') AS confirmed_booking_count, count(*) FILTER (WHERE booking_status = 'Mixed') AS mixed_booking_count FROM core.bookings;

-- [K4] Cancelled Booking Count = bookings where every passenger was cancelled by the passenger (System auto-refunds are not cancellations).
SELECT count(*) FILTER (WHERE booking_status = 'Cancelled') AS cancelled_booking_count FROM core.bookings;

-- [K5] Cancellation Rate (passenger-based): cancelled passengers / total passengers; companion: booking-based rate.
SELECT p.cancelled_passengers, p.total_passengers, round(p.cancelled_passengers::numeric / p.total_passengers, 4) AS cancellation_rate_passenger_based,
       b.cancelled_bookings, b.total_bookings, round(b.cancelled_bookings::numeric / b.total_bookings, 4) AS cancellation_rate_booking_based
FROM (SELECT count(*) FILTER (WHERE final_status = 'Cancelled') AS cancelled_passengers, count(*) AS total_passengers FROM core.booking_passengers) p,
     (SELECT count(*) FILTER (WHERE booking_status = 'Cancelled') AS cancelled_bookings, count(*) AS total_bookings FROM core.bookings) b;

-- [K6] Gross Booking Value (before refunds; not revenue or profit).
SELECT sum(total_fare) AS gross_booking_value FROM core.bookings;

-- [K7] Refund Amount: Passenger events and System auto-refund events, plus retained charges (refund = original fare minus charge).
SELECT sum(refund_amount) AS refund_amount,
       sum(refund_amount) FILTER (WHERE cancellation_type = 'Passenger') AS refund_passenger_events,
       sum(refund_amount) FILTER (WHERE cancellation_type = 'System')    AS refund_system_events,
       sum(cancellation_charge) AS retained_charges
FROM core.cancellations;

-- [K8] Net Booking Value = Gross Booking Value - Refund Amount (not revenue or profit).
SELECT (SELECT sum(total_fare) FROM core.bookings) - (SELECT sum(refund_amount) FROM core.cancellations) AS net_booking_value;

-- [K9] Average Fare: per passenger (primary, denominator = total passengers) and per booking (secondary).
SELECT round((SELECT sum(total_fare) FROM core.bookings) / (SELECT count(*) FROM core.booking_passengers), 2) AS avg_fare_per_passenger,
       round((SELECT sum(total_fare) FROM core.bookings) / (SELECT count(*) FROM core.bookings), 2) AS avg_fare_per_booking;

-- [K10] Seat Occupancy %: (Confirmed + 0.5 x RAC) / seats, matched per train-class run. Passengers are aggregated to the class-run grain BEFORE joining to capacity.
--       Waitlisted passengers hold no seat: they appear as Waitlist Pressure %, not in occupancy.
WITH pax AS (
    SELECT b.train_id, b.journey_date, b.travel_class,
           count(*) FILTER (WHERE bp.final_status = 'Confirmed')  AS confirmed_pax,
           count(*) FILTER (WHERE bp.final_status = 'RAC')        AS rac_pax,
           count(*) FILTER (WHERE bp.final_status = 'Waitlisted') AS waitlisted_pax
    FROM core.booking_passengers bp JOIN core.bookings b ON b.booking_id = bp.booking_id
    GROUP BY b.train_id, b.journey_date, b.travel_class)
SELECT sum(coalesce(p.confirmed_pax, 0) + analytics.param('rac_seat_weight') * coalesce(p.rac_pax, 0)) AS booked_seats, sum(sc.total_seats) AS available_seats,
       round(sum(coalesce(p.confirmed_pax, 0) + analytics.param('rac_seat_weight') * coalesce(p.rac_pax, 0)) / sum(sc.total_seats), 4) AS seat_occupancy,
       round(sum(coalesce(p.confirmed_pax, 0))::numeric / sum(sc.total_seats), 4) AS confirmed_occupancy,
       round(analytics.param('rac_seat_weight') * sum(coalesce(p.rac_pax, 0)) / sum(sc.total_seats), 4) AS rac_occupancy,
       round(sum(coalesce(p.waitlisted_pax, 0))::numeric / sum(sc.total_seats), 4) AS waitlist_pressure
FROM core.seat_capacity sc
LEFT JOIN pax p ON p.train_id = sc.train_id AND p.journey_date = sc.journey_date AND p.travel_class = sc.travel_class;

-- [K11] Waiting-List Demand (initial status), Waitlist Clearance Rate (denominator = initially waitlisted passengers) and Uncleared Waitlist Passengers.
SELECT count(*) FILTER (WHERE initial_status = 'Waitlisted') AS waiting_list_demand,
       count(*) FILTER (WHERE initial_status = 'Waitlisted' AND final_status IN ('Confirmed','RAC')) AS cleared,
       round(count(*) FILTER (WHERE initial_status = 'Waitlisted' AND final_status IN ('Confirmed','RAC'))::numeric / count(*) FILTER (WHERE initial_status = 'Waitlisted'), 4) AS waitlist_clearance_rate,
       count(*) FILTER (WHERE final_status = 'Waitlisted') AS uncleared_waitlist_passengers
FROM core.booking_passengers;

-- [K12] On-Time Performance %: runs with arrival delay <= 15 minutes / runs with a RECORDED arrival delay (NULL delays are excluded, never imputed).
SELECT count(*) FILTER (WHERE arrival_delay_min <= 15) AS on_time_runs, count(arrival_delay_min) AS runs_with_recorded_delay,
       round(count(*) FILTER (WHERE arrival_delay_min <= 15)::numeric / count(arrival_delay_min), 4) AS on_time_performance
FROM core.train_operations;

-- [K13] Average Delay (early arrivals count as 0) and the average over late runs only (labelled separately).
SELECT round(avg(greatest(arrival_delay_min, 0)), 2) AS avg_delay_minutes, round(avg(arrival_delay_min) FILTER (WHERE arrival_delay_min > 15), 2) AS avg_delay_of_late_runs_minutes
FROM core.train_operations WHERE arrival_delay_min IS NOT NULL;

-- [K14] Monthly Booking Growth (previous month's bookings is the denominator) next to growth in bookings per simulated run, which is the sampling-safe view.
WITH bm AS (SELECT to_char(journey_date, 'YYYY-MM') AS journey_month, count(*) AS bookings FROM core.bookings GROUP BY 1),
     m  AS (SELECT bm.journey_month, bm.bookings,
                   (SELECT count(*) FROM core.train_operations o WHERE to_char(o.run_date, 'YYYY-MM') = bm.journey_month) AS simulated_runs
            FROM bm)
SELECT journey_month, bookings, simulated_runs,
       round(bookings::numeric / NULLIF(lag(bookings) OVER (ORDER BY journey_month), 0) - 1, 4) AS monthly_booking_growth,
       round((bookings::numeric / simulated_runs) / NULLIF(lag(bookings::numeric / simulated_runs) OVER (ORDER BY journey_month), 0) - 1, 4) AS growth_in_bookings_per_run
FROM m ORDER BY journey_month LIMIT 6;

-- [K15] Route-Level Demand: passengers booked on each route with the final-status split, simulated runs behind it, and rank (ties share a rank).
WITH r AS (
    SELECT p.route_name, count(*) AS passengers,
           count(*) FILTER (WHERE p.final_status = 'Confirmed') AS confirmed, count(*) FILTER (WHERE p.final_status = 'RAC') AS rac,
           count(*) FILTER (WHERE p.final_status = 'Waitlisted') AS waitlisted, count(*) FILTER (WHERE p.final_status = 'Cancelled') AS cancelled
    FROM analytics.v_passenger p GROUP BY p.route_name)
SELECT route_name, passengers, confirmed, rac, waitlisted, cancelled, rank() OVER (ORDER BY passengers DESC) AS demand_rank,
       (SELECT count(*) FROM analytics.v_run o WHERE o.route_name = r.route_name) AS simulated_runs
FROM r ORDER BY demand_rank, route_name LIMIT 10;
