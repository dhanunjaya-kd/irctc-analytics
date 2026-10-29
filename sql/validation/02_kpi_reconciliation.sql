-- 02_kpi_reconciliation.sql: reconcile the SQL KPIs against the Phase 3 reference files WITHOUT changing any KPI definition.
-- Tolerances follow docs/KPI_definitions.md section 1.8: counts exact, currency 2 decimals (0.005), ratios 4 decimals (0.00005).
CREATE VIEW qa.v_kpi_reconciliation AS
WITH t AS (
    SELECT r.kpi_key, r.kpi, r.unit, r.value AS reference_value, s.value AS sql_value,
           CASE r.unit WHEN 'INR' THEN 0.005 WHEN 'share' THEN 0.00005
                       WHEN 'seat-equivalents' THEN 0.0001 WHEN 'minutes' THEN 0.0001 WHEN 'bookings/run' THEN 0.0001 WHEN 'passengers/run' THEN 0.0001
                       ELSE 0 END AS tolerance
    FROM qa.kpi_reference r LEFT JOIN analytics.v_kpi_overall_long s ON s.kpi_key = r.kpi_key)
SELECT kpi_key, kpi, unit, reference_value, sql_value, abs(sql_value - reference_value) AS abs_diff, tolerance,
       coalesce(abs(sql_value - reference_value) <= tolerance, false) AS passed
FROM t;

CREATE VIEW qa.v_monthly_kpi_reconciliation AS
WITH ref AS (
    SELECT r.journey_month, k.kpi_key, k.value
    FROM qa.monthly_kpi_reference r
    CROSS JOIN LATERAL (VALUES
        ('total_bookings', r.total_bookings),
        ('total_passengers', r.total_passengers),
        ('confirmed_bookings', r.confirmed_bookings),
        ('mixed_bookings', r.mixed_bookings),
        ('cancelled_bookings', r.cancelled_bookings),
        ('cancelled_passengers', r.cancelled_passengers),
        ('confirmed_pax', r.confirmed_pax),
        ('rac_pax', r.rac_pax),
        ('gross_value', r.gross_value),
        ('refund_total', r.refund_total),
        ('refund_passenger', r.refund_passenger),
        ('refund_system', r.refund_system),
        ('retained_charges', r.retained_charges),
        ('net_value', r.net_value),
        ('wl_demand', r.wl_demand),
        ('wl_cleared', r.wl_cleared),
        ('wl_uncleared', r.wl_uncleared),
        ('seat_supply', r.seat_supply),
        ('booked_seats', r.booked_seats),
        ('simulated_runs', r.simulated_runs),
        ('class_runs', r.class_runs),
        ('runs_with_delay', r.runs_with_delay),
        ('on_time_runs', r.on_time_runs),
        ('delayed_runs', r.delayed_runs),
        ('delay_sum_pos', r.delay_sum_pos),
        ('passenger_cancellation_rate', r.passenger_cancellation_rate),
        ('booking_cancellation_rate', r.booking_cancellation_rate),
        ('avg_fare_per_passenger', r.avg_fare_per_passenger),
        ('avg_fare_per_booking', r.avg_fare_per_booking),
        ('wl_clearance_rate', r.wl_clearance_rate),
        ('occupancy', r.occupancy),
        ('confirmed_occupancy', r.confirmed_occupancy),
        ('rac_occupancy', r.rac_occupancy),
        ('waitlist_pressure', r.waitlist_pressure),
        ('bookings_per_run', r.bookings_per_run),
        ('passengers_per_run', r.passengers_per_run),
        ('otp', r.otp),
        ('avg_delay', r.avg_delay),
        ('bookings_growth', r.bookings_growth),
        ('bookings_per_run_growth', r.bookings_per_run_growth)
    ) AS k(kpi_key, value)),
cmp AS (
    SELECT s.journey_month, s.kpi_key, ref.value AS reference_value, s.value AS sql_value,
           CASE WHEN s.kpi_key IN ('gross_value','refund_total','refund_passenger','refund_system','retained_charges','net_value','avg_fare_per_passenger','avg_fare_per_booking') THEN 0.005
                WHEN s.kpi_key IN ('passenger_cancellation_rate','booking_cancellation_rate','wl_clearance_rate','occupancy','confirmed_occupancy','rac_occupancy','waitlist_pressure','otp','bookings_growth','bookings_per_run_growth') THEN 0.00005
                WHEN s.kpi_key IN ('booked_seats','bookings_per_run','passengers_per_run','avg_delay') THEN 0.0001
                ELSE 0 END AS tolerance
    FROM analytics.v_monthly_kpis_long s JOIN ref ON ref.journey_month = s.journey_month AND ref.kpi_key = s.kpi_key)
SELECT journey_month, kpi_key, reference_value, sql_value, abs(sql_value - reference_value) AS abs_diff, tolerance,
       ((reference_value IS NULL AND sql_value IS NULL) OR coalesce(abs(sql_value - reference_value) <= tolerance, false)) AS passed
FROM cmp;

CREATE VIEW qa.v_reconciliation_summary AS
SELECT 'overall (reports/kpi_reference_values.csv)' AS scope, count(*) AS comparisons, count(*) FILTER (WHERE passed) AS passed, count(*) FILTER (WHERE NOT passed) AS failed FROM qa.v_kpi_reconciliation
UNION ALL
SELECT 'monthly (data/processed/derived/monthly_kpis.csv)', count(*), count(*) FILTER (WHERE passed), count(*) FILTER (WHERE NOT passed) FROM qa.v_monthly_kpi_reconciliation;
