-- 01_data_quality_checks.sql: data-quality checks as a view. Each row = one check; violations = number of offending records (0 = PASS).
-- Mirrors python/src/validate_data.py (Phase 2) so the same business rules BR-01 .. BR-17 are verified inside PostgreSQL.
-- Row-level rules are also enforced by CHECK constraints; cross-row rules can only be verified here.
-- Chart preparation = 4 hours before the first stop's departure (analytics.param('chart_prep_hours')).
CREATE VIEW qa.v_check_results AS
-- ---------------------------------------------------------------- structure (catalog)
SELECT 'STRUCT-schemas' AS check_id, 'STRUCTURE' AS category, 'schemas stg, core, analytics and qa exist' AS description,
       (4 - count(*))::bigint AS violations FROM information_schema.schemata WHERE schema_name IN ('stg','core','analytics','qa')
UNION ALL SELECT 'STRUCT-core-tables', 'STRUCTURE', '10 core tables exist', (10 - count(*))::bigint
       FROM information_schema.tables WHERE table_schema = 'core' AND table_type = 'BASE TABLE'
UNION ALL SELECT 'STRUCT-primary-keys', 'STRUCTURE', 'every core table has a primary key (10)', (10 - count(*))::bigint
       FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = 'core' AND c.contype = 'p'
UNION ALL SELECT 'STRUCT-foreign-keys', 'STRUCTURE', '18 foreign keys exist in core', abs(18 - count(*))::bigint
       FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = 'core' AND c.contype = 'f'
UNION ALL SELECT 'STRUCT-unique-constraints', 'STRUCTURE', '8 UNIQUE constraints exist in core', abs(8 - count(*))::bigint
       FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = 'core' AND c.contype = 'u'
UNION ALL SELECT 'STRUCT-check-constraints', 'STRUCTURE', '55 CHECK constraints exist in core', abs(55 - count(*))::bigint
       FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = 'core' AND c.contype = 'c'
UNION ALL SELECT 'STRUCT-constraints-validated', 'STRUCTURE', 'every core constraint is validated', count(*)::bigint
       FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = 'core' AND NOT c.convalidated
UNION ALL SELECT 'STRUCT-nullable-columns', 'STRUCTURE', 'only the 6 documented columns are nullable (arrival_time, departure_time, holiday_name, peak_period_name, arrival_delay_min, cancellation_id)', abs(6 - count(*))::bigint
       FROM information_schema.columns WHERE table_schema = 'core' AND is_nullable = 'YES'
UNION ALL SELECT 'STRUCT-secondary-indexes', 'STRUCTURE', '13 secondary indexes (ix_*) exist in core', abs(13 - count(*))::bigint
       FROM pg_indexes WHERE schemaname = 'core' AND indexname LIKE 'ix\_%'
-- ---------------------------------------------------------------- row counts
UNION ALL
SELECT 'ROWS-stg-core-stations', 'ROWS', 'rows loaded into core.stations equal the rows staged from the CSV file', abs((SELECT count(*) FROM stg.stations) - (SELECT count(*) FROM core.stations))::bigint
UNION ALL
SELECT 'ROWS-stg-core-routes', 'ROWS', 'rows loaded into core.routes equal the rows staged from the CSV file', abs((SELECT count(*) FROM stg.routes) - (SELECT count(*) FROM core.routes))::bigint
UNION ALL
SELECT 'ROWS-stg-core-trains', 'ROWS', 'rows loaded into core.trains equal the rows staged from the CSV file', abs((SELECT count(*) FROM stg.trains) - (SELECT count(*) FROM core.trains))::bigint
UNION ALL
SELECT 'ROWS-stg-core-train_stops', 'ROWS', 'rows loaded into core.train_stops equal the rows staged from the CSV file', abs((SELECT count(*) FROM stg.train_stops) - (SELECT count(*) FROM core.train_stops))::bigint
UNION ALL
SELECT 'ROWS-stg-core-calendar', 'ROWS', 'rows loaded into core.calendar equal the rows staged from the CSV file', abs((SELECT count(*) FROM stg.calendar) - (SELECT count(*) FROM core.calendar))::bigint
UNION ALL
SELECT 'ROWS-stg-core-seat_capacity', 'ROWS', 'rows loaded into core.seat_capacity equal the rows staged from the CSV file', abs((SELECT count(*) FROM stg.seat_capacity) - (SELECT count(*) FROM core.seat_capacity))::bigint
UNION ALL
SELECT 'ROWS-stg-core-train_operations', 'ROWS', 'rows loaded into core.train_operations equal the rows staged from the CSV file', abs((SELECT count(*) FROM stg.train_operations) - (SELECT count(*) FROM core.train_operations))::bigint
UNION ALL
SELECT 'ROWS-stg-core-bookings', 'ROWS', 'rows loaded into core.bookings equal the rows staged from the CSV file', abs((SELECT count(*) FROM stg.bookings) - (SELECT count(*) FROM core.bookings))::bigint
UNION ALL
SELECT 'ROWS-stg-core-booking_passengers', 'ROWS', 'rows loaded into core.booking_passengers equal the rows staged from the CSV file', abs((SELECT count(*) FROM stg.booking_passengers) - (SELECT count(*) FROM core.booking_passengers))::bigint
UNION ALL
SELECT 'ROWS-stg-core-cancellations', 'ROWS', 'rows loaded into core.cancellations equal the rows staged from the CSV file', abs((SELECT count(*) FROM stg.cancellations) - (SELECT count(*) FROM core.cancellations))::bigint
UNION ALL
SELECT 'ROWS-phase2-stations', 'ROWS', 'core.stations row count equals the Phase 2 cleaned row count (row_movement.csv)', abs((SELECT clean_rows FROM qa.phase2_row_movement WHERE table_name = 'stations') - (SELECT count(*) FROM core.stations))::bigint
UNION ALL
SELECT 'ROWS-phase2-routes', 'ROWS', 'core.routes row count equals the Phase 2 cleaned row count (row_movement.csv)', abs((SELECT clean_rows FROM qa.phase2_row_movement WHERE table_name = 'routes') - (SELECT count(*) FROM core.routes))::bigint
UNION ALL
SELECT 'ROWS-phase2-trains', 'ROWS', 'core.trains row count equals the Phase 2 cleaned row count (row_movement.csv)', abs((SELECT clean_rows FROM qa.phase2_row_movement WHERE table_name = 'trains') - (SELECT count(*) FROM core.trains))::bigint
UNION ALL
SELECT 'ROWS-phase2-train_stops', 'ROWS', 'core.train_stops row count equals the Phase 2 cleaned row count (row_movement.csv)', abs((SELECT clean_rows FROM qa.phase2_row_movement WHERE table_name = 'train_stops') - (SELECT count(*) FROM core.train_stops))::bigint
UNION ALL
SELECT 'ROWS-phase2-calendar', 'ROWS', 'core.calendar row count equals the Phase 2 cleaned row count (row_movement.csv)', abs((SELECT clean_rows FROM qa.phase2_row_movement WHERE table_name = 'calendar') - (SELECT count(*) FROM core.calendar))::bigint
UNION ALL
SELECT 'ROWS-phase2-seat_capacity', 'ROWS', 'core.seat_capacity row count equals the Phase 2 cleaned row count (row_movement.csv)', abs((SELECT clean_rows FROM qa.phase2_row_movement WHERE table_name = 'seat_capacity') - (SELECT count(*) FROM core.seat_capacity))::bigint
UNION ALL
SELECT 'ROWS-phase2-train_operations', 'ROWS', 'core.train_operations row count equals the Phase 2 cleaned row count (row_movement.csv)', abs((SELECT clean_rows FROM qa.phase2_row_movement WHERE table_name = 'train_operations') - (SELECT count(*) FROM core.train_operations))::bigint
UNION ALL
SELECT 'ROWS-phase2-bookings', 'ROWS', 'core.bookings row count equals the Phase 2 cleaned row count (row_movement.csv)', abs((SELECT clean_rows FROM qa.phase2_row_movement WHERE table_name = 'bookings') - (SELECT count(*) FROM core.bookings))::bigint
UNION ALL
SELECT 'ROWS-phase2-booking_passengers', 'ROWS', 'core.booking_passengers row count equals the Phase 2 cleaned row count (row_movement.csv)', abs((SELECT clean_rows FROM qa.phase2_row_movement WHERE table_name = 'booking_passengers') - (SELECT count(*) FROM core.booking_passengers))::bigint
UNION ALL
SELECT 'ROWS-phase2-cancellations', 'ROWS', 'core.cancellations row count equals the Phase 2 cleaned row count (row_movement.csv)', abs((SELECT clean_rows FROM qa.phase2_row_movement WHERE table_name = 'cancellations') - (SELECT count(*) FROM core.cancellations))::bigint
-- ---------------------------------------------------------------- BR-01 .. BR-03: statuses, roll-up, counts and fares
UNION ALL SELECT 'BR-01', 'BUSINESS RULE', 'passenger initial_status and final_status are in their documented domains', count(*)::bigint FROM core.booking_passengers
       WHERE initial_status NOT IN ('Confirmed','RAC','Waitlisted') OR final_status NOT IN ('Confirmed','RAC','Waitlisted','Cancelled')
UNION ALL SELECT 'BR-02', 'BUSINESS RULE', 'booking_status equals the roll-up of passenger final_status (single status, else Mixed)', (
         (SELECT count(*) FROM core.bookings b JOIN (SELECT booking_id, CASE WHEN count(DISTINCT final_status) = 1 THEN min(final_status) ELSE 'Mixed' END AS rollup
                                                     FROM core.booking_passengers GROUP BY booking_id) r ON r.booking_id = b.booking_id WHERE b.booking_status <> r.rollup)
       + (SELECT count(*) FROM core.bookings b WHERE NOT EXISTS (SELECT 1 FROM core.booking_passengers bp WHERE bp.booking_id = b.booking_id)))::bigint
UNION ALL SELECT 'BR-03a', 'BUSINESS RULE', 'num_passengers equals the number of passenger rows', count(*)::bigint FROM core.bookings b
       WHERE b.num_passengers <> (SELECT count(*) FROM core.booking_passengers bp WHERE bp.booking_id = b.booking_id)
UNION ALL SELECT 'BR-03b', 'BUSINESS RULE', 'total_fare equals SUM(passenger fare_amount)', count(*)::bigint FROM core.bookings b
       WHERE b.total_fare <> (SELECT sum(bp.fare_amount) FROM core.booking_passengers bp WHERE bp.booking_id = b.booking_id)
UNION ALL SELECT 'BR-03c', 'BUSINESS RULE', 'passenger_seq runs 1..n within each booking', count(*)::bigint FROM (
         SELECT booking_id FROM core.booking_passengers GROUP BY booking_id HAVING min(passenger_seq) <> 1 OR max(passenger_seq) <> count(*)) x
-- ---------------------------------------------------------------- BR-04 .. BR-07: timing, run days, stations, capacity link
UNION ALL SELECT 'BR-04a', 'BUSINESS RULE', 'booking date is on or before the journey date and lead time is 0..120 days', count(*)::bigint FROM core.bookings
       WHERE (journey_date - booking_ts::date) < 0 OR (journey_date - booking_ts::date) > analytics.param('max_advance_days')
UNION ALL SELECT 'BR-04b', 'BUSINESS RULE', 'booking_ts is before chart preparation (first departure minus 4 hours)', count(*)::bigint FROM core.bookings b
       JOIN core.train_stops s ON s.train_id = b.train_id AND s.stop_sequence = 1
       WHERE b.booking_ts > (b.journey_date + s.departure_time) - make_interval(hours => analytics.param('chart_prep_hours')::int)
UNION ALL SELECT 'BR-04c', 'BUSINESS RULE', 'journey_date inside the approved window 2024-09-01 .. 2026-08-31', count(*)::bigint FROM core.bookings
       WHERE journey_date NOT BETWEEN DATE '2024-09-01' AND DATE '2026-08-31'
UNION ALL SELECT 'BR-05a', 'BUSINESS RULE', 'booking journey_date falls on a scheduled run day of the train', count(*)::bigint FROM core.bookings b
       JOIN core.trains t ON t.train_id = b.train_id WHERE substr(t.run_days, extract(isodow FROM b.journey_date)::int, 1) <> 'Y'
UNION ALL SELECT 'BR-05b', 'BUSINESS RULE', 'each booking train/date has a train_operations row', count(*)::bigint FROM core.bookings b
       WHERE NOT EXISTS (SELECT 1 FROM core.train_operations o WHERE o.train_id = b.train_id AND o.run_date = b.journey_date)
UNION ALL SELECT 'BR-05c', 'BUSINESS RULE', 'seat_capacity rows fall on run days and have a train_operations row', count(*)::bigint FROM core.seat_capacity sc
       JOIN core.trains t ON t.train_id = sc.train_id
       WHERE substr(t.run_days, extract(isodow FROM sc.journey_date)::int, 1) <> 'Y'
          OR NOT EXISTS (SELECT 1 FROM core.train_operations o WHERE o.train_id = sc.train_id AND o.run_date = sc.journey_date)
UNION ALL SELECT 'BR-06a', 'BUSINESS RULE', 'booking route_id equals the train route', count(*)::bigint FROM core.bookings b JOIN core.trains t ON t.train_id = b.train_id WHERE t.route_id <> b.route_id
UNION ALL SELECT 'BR-06b', 'BUSINESS RULE', 'boarding and destination stations equal the route origin and destination', count(*)::bigint FROM core.bookings b
       JOIN core.routes r ON r.route_id = b.route_id WHERE r.origin_station_id <> b.boarding_station_id OR r.destination_station_id <> b.destination_station_id
UNION ALL SELECT 'BR-06c', 'BUSINESS RULE', 'boarding and destination stations differ', count(*)::bigint FROM core.bookings WHERE boarding_station_id = destination_station_id
UNION ALL SELECT 'BR-07', 'BUSINESS RULE', 'each booking train/date/class has a seat_capacity row', count(*)::bigint FROM core.bookings b
       WHERE NOT EXISTS (SELECT 1 FROM core.seat_capacity sc WHERE sc.train_id = b.train_id AND sc.journey_date = b.journey_date AND sc.travel_class = b.travel_class)
-- ---------------------------------------------------------------- BR-08 .. BR-09: occupancy limits and capacity arithmetic
UNION ALL SELECT 'BR-08a', 'BUSINESS RULE', 'Confirmed passengers <= total_seats - rac_berths', count(*)::bigint FROM analytics.v_class_run WHERE confirmed_pax > total_seats - rac_berths
UNION ALL SELECT 'BR-08b', 'BUSINESS RULE', 'RAC passengers <= 2 x rac_berths (none where rac_berths = 0)', count(*)::bigint FROM analytics.v_class_run WHERE rac_pax > 2 * rac_berths
UNION ALL SELECT 'BR-08c', 'BUSINESS RULE', 'Confirmed + RAC weight x RAC <= total_seats (occupancy <= 100%)', count(*)::bigint FROM analytics.v_class_run WHERE booked_seats > total_seats
UNION ALL SELECT 'BR-08d', 'BUSINESS RULE', 'Waitlisted passengers <= wl_limit', count(*)::bigint FROM analytics.v_class_run WHERE wl_final_pax > wl_limit
UNION ALL SELECT 'BR-09a', 'BUSINESS RULE', 'total_seats = coaches_attached x seats_per_coach', count(*)::bigint FROM core.seat_capacity WHERE total_seats <> coaches_attached * seats_per_coach
UNION ALL SELECT 'BR-09b', 'BUSINESS RULE', 'seats_per_coach equals the class standard', count(*)::bigint FROM core.seat_capacity
       WHERE seats_per_coach <> CASE travel_class WHEN '1A' THEN 24 WHEN '2A' THEN 46 WHEN '3A' THEN 64 WHEN 'SL' THEN 72 WHEN 'CC' THEN 78 WHEN '2S' THEN 108 END
-- ---------------------------------------------------------------- BR-10 .. BR-12: cancellation linkage, event arithmetic, timing
UNION ALL SELECT 'BR-10a', 'BUSINESS RULE', 'cancellation_id is set exactly when final_status is Cancelled or Waitlisted', count(*)::bigint FROM core.booking_passengers
       WHERE (cancellation_id IS NOT NULL) <> (final_status IN ('Cancelled','Waitlisted'))
UNION ALL SELECT 'BR-10b', 'BUSINESS RULE', 'Passenger events link Cancelled passengers; System events link Waitlisted passengers', count(*)::bigint FROM core.booking_passengers bp
       JOIN core.cancellations c ON c.cancellation_id = bp.cancellation_id
       WHERE (c.cancellation_type = 'Passenger' AND bp.final_status <> 'Cancelled') OR (c.cancellation_type = 'System' AND bp.final_status <> 'Waitlisted')
UNION ALL SELECT 'BR-10c', 'BUSINESS RULE', 'linked passengers belong to the event booking', count(*)::bigint FROM core.booking_passengers bp
       JOIN core.cancellations c ON c.cancellation_id = bp.cancellation_id WHERE c.booking_id <> bp.booking_id
UNION ALL SELECT 'BR-11a', 'BUSINESS RULE', 'cancelled_passengers equals the number of linked passengers', count(*)::bigint FROM core.cancellations c
       WHERE c.cancelled_passengers <> (SELECT count(*) FROM core.booking_passengers bp WHERE bp.cancellation_id = c.cancellation_id)
UNION ALL SELECT 'BR-11b', 'BUSINESS RULE', 'original_fare_amount equals SUM(linked passenger fares)', count(*)::bigint FROM core.cancellations c
       WHERE c.original_fare_amount <> (SELECT sum(bp.fare_amount) FROM core.booking_passengers bp WHERE bp.cancellation_id = c.cancellation_id)
UNION ALL SELECT 'BR-11c', 'BUSINESS RULE', 'refund + charge = original fare; refund and charge >= 0', count(*)::bigint FROM core.cancellations
       WHERE refund_amount + cancellation_charge <> original_fare_amount OR refund_amount < 0 OR cancellation_charge < 0
UNION ALL SELECT 'BR-11d', 'BUSINESS RULE', 'status_at_cancellation and type are in domain; System events are Waitlisted', count(*)::bigint FROM core.cancellations
       WHERE status_at_cancellation NOT IN ('Confirmed','RAC','Waitlisted') OR cancellation_type NOT IN ('Passenger','System') OR (cancellation_type = 'System' AND status_at_cancellation <> 'Waitlisted')
UNION ALL SELECT 'BR-11e', 'BUSINESS RULE', 'every cancellation event has at least one linked passenger', count(*)::bigint FROM core.cancellations c
       WHERE NOT EXISTS (SELECT 1 FROM core.booking_passengers bp WHERE bp.cancellation_id = c.cancellation_id)
UNION ALL SELECT 'BR-12', 'BUSINESS RULE', 'booking_ts <= cancellation_ts <= chart preparation time', count(*)::bigint FROM core.cancellations c
       JOIN core.bookings b ON b.booking_id = c.booking_id JOIN core.train_stops s ON s.train_id = b.train_id AND s.stop_sequence = 1
       WHERE c.cancellation_ts < b.booking_ts OR c.cancellation_ts > (b.journey_date + s.departure_time) - make_interval(hours => analytics.param('chart_prep_hours')::int)
-- ---------------------------------------------------------------- BR-13 .. BR-17
UNION ALL SELECT 'BR-13', 'BUSINESS RULE', 'train stops: sequence 1..n, distance strictly increasing, terminals match the route, no arrival at origin / departure at terminus', (
         (SELECT count(*) FROM (SELECT train_id FROM core.train_stops GROUP BY train_id HAVING min(stop_sequence) <> 1 OR max(stop_sequence) <> count(*)) x)
       + (SELECT count(*) FROM (SELECT distance_from_origin_km AS d, lag(distance_from_origin_km) OVER (PARTITION BY train_id ORDER BY stop_sequence) AS prev FROM core.train_stops) y WHERE prev IS NOT NULL AND d <= prev)
       + (SELECT count(*) FROM core.trains t JOIN core.routes r ON r.route_id = t.route_id
          WHERE (SELECT station_id FROM core.train_stops WHERE train_id = t.train_id AND stop_sequence = 1) <> r.origin_station_id
             OR (SELECT station_id FROM core.train_stops WHERE train_id = t.train_id ORDER BY stop_sequence DESC LIMIT 1) <> r.destination_station_id)
       + (SELECT count(*) FROM core.train_stops s WHERE s.stop_sequence = (SELECT max(stop_sequence) FROM core.train_stops x WHERE x.train_id = s.train_id) AND s.departure_time IS NOT NULL))::bigint
UNION ALL SELECT 'BR-14', 'BUSINESS RULE', 'no personally identifiable columns or values (name, e-mail, phone, address, ID numbers)', (
         (SELECT count(*) FROM information_schema.columns WHERE table_schema IN ('core','analytics')
            AND column_name ~* '(email|phone|mobile|address|aadhaar|aadhar|pan_number|dob|birth|passenger_name|first_name|last_name|passport)')
       + (SELECT count(*) FROM core.bookings WHERE booking_reference ~ '[@]|[0-9]{10}')
       + (SELECT count(*) FROM core.trains WHERE train_name ~ '[@]|[0-9]{10}')
       + (SELECT count(*) FROM core.stations WHERE station_name ~ '[@]|[0-9]{10}' OR city ~ '[@]|[0-9]{10}'))::bigint
UNION ALL SELECT 'BR-15', 'BUSINESS RULE', 'fares > 0, passengers per booking 1..6', (
         (SELECT count(*) FROM core.booking_passengers WHERE fare_amount <= 0) + (SELECT count(*) FROM core.bookings WHERE total_fare <= 0 OR num_passengers NOT BETWEEN 1 AND 6))::bigint
UNION ALL SELECT 'BR-16', 'BUSINESS RULE', 'station_code unique, upper-case, trimmed', (
         (SELECT count(*) FROM (SELECT station_code FROM core.stations GROUP BY station_code HAVING count(*) > 1) d) + (SELECT count(*) FROM core.stations WHERE station_code <> upper(btrim(station_code))))::bigint
UNION ALL SELECT 'BR-17', 'BUSINESS RULE', 'no demotion between initial and final passenger status', count(*)::bigint FROM core.booking_passengers
       WHERE NOT ((initial_status = 'Confirmed' AND final_status IN ('Confirmed','Cancelled')) OR (initial_status = 'RAC' AND final_status IN ('RAC','Confirmed','Cancelled')) OR initial_status = 'Waitlisted')
-- ---------------------------------------------------------------- domains and labelling
UNION ALL SELECT 'DOM-class', 'DOMAIN', 'travel_class in {1A, 2A, 3A, SL, CC, 2S} for bookings and capacity', (
         (SELECT count(*) FROM core.bookings WHERE travel_class NOT IN ('1A','2A','3A','SL','CC','2S')) + (SELECT count(*) FROM core.seat_capacity WHERE travel_class NOT IN ('1A','2A','3A','SL','CC','2S')))::bigint
UNION ALL SELECT 'DOM-age', 'DOMAIN', 'age_band in {Child, Adult, Senior, Unknown}', count(*)::bigint FROM core.booking_passengers WHERE age_band NOT IN ('Child','Adult','Senior','Unknown')
UNION ALL SELECT 'DOM-delay', 'DOMAIN', 'non-null delays inside -60..1440 minutes', count(*)::bigint FROM core.train_operations
       WHERE departure_delay_min NOT BETWEEN -60 AND 1440 OR (arrival_delay_min IS NOT NULL AND arrival_delay_min NOT BETWEEN -60 AND 1440)
UNION ALL SELECT 'DOM-origin', 'LABELLING', 'every row of every core table is labelled data_origin = SYNTHETIC', ((SELECT count(*) FROM core.stations WHERE data_origin <> 'SYNTHETIC') + (SELECT count(*) FROM core.routes WHERE data_origin <> 'SYNTHETIC') + (SELECT count(*) FROM core.trains WHERE data_origin <> 'SYNTHETIC') + (SELECT count(*) FROM core.train_stops WHERE data_origin <> 'SYNTHETIC') + (SELECT count(*) FROM core.calendar WHERE data_origin <> 'SYNTHETIC') + (SELECT count(*) FROM core.seat_capacity WHERE data_origin <> 'SYNTHETIC') + (SELECT count(*) FROM core.train_operations WHERE data_origin <> 'SYNTHETIC') + (SELECT count(*) FROM core.bookings WHERE data_origin <> 'SYNTHETIC') + (SELECT count(*) FROM core.booking_passengers WHERE data_origin <> 'SYNTHETIC') + (SELECT count(*) FROM core.cancellations WHERE data_origin <> 'SYNTHETIC'))::bigint
-- ---------------------------------------------------------------- size requirements (project specification)
UNION ALL SELECT 'SIZE-bookings', 'SIZE', 'at least 100,000 bookings', greatest(0, 100000 - count(*))::bigint FROM core.bookings
UNION ALL SELECT 'SIZE-trains', 'SIZE', 'at least 50 trains', greatest(0, 50 - count(*))::bigint FROM core.trains
UNION ALL SELECT 'SIZE-stations', 'SIZE', 'at least 30 stations', greatest(0, 30 - count(*))::bigint FROM core.stations
UNION ALL SELECT 'SIZE-months', 'SIZE', 'at least 24 months of journeys', greatest(0, 24 - count(DISTINCT to_char(journey_date, 'YYYY-MM')))::bigint FROM core.bookings;

CREATE VIEW qa.v_check_summary AS
SELECT count(*) AS checks, count(*) FILTER (WHERE violations = 0) AS passed, count(*) FILTER (WHERE violations <> 0) AS failed FROM qa.v_check_results;
COMMENT ON VIEW qa.v_check_results IS 'Data-quality checks (violations = 0 means PASS). Mirrors python/src/validate_data.py. SYNTHETIC, sampled simulation.';
