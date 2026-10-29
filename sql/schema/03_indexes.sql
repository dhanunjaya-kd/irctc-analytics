-- 03_indexes.sql: secondary indexes, created AFTER the bulk load (faster load, then ANALYZE).
-- Primary-key and UNIQUE constraints already create their own indexes. Each index below supports a foreign-key join or a
-- filter used by the analytical SQL; see docs/postgresql_design.md for the reasoning and sql/analysis for the queries.

-- foreign-key support (the UNIQUE constraints already cover routes.origin, train_stops.train_id, seat_capacity.train_id,
-- train_operations.train_id and booking_passengers.booking_id as leading columns)
CREATE INDEX ix_routes_destination        ON core.routes (destination_station_id);
CREATE INDEX ix_trains_route              ON core.trains (route_id);
CREATE INDEX ix_train_stops_station       ON core.train_stops (station_id);
CREATE INDEX ix_seat_capacity_date        ON core.seat_capacity (journey_date);
CREATE INDEX ix_train_operations_date     ON core.train_operations (run_date);

-- bookings: composite FK to seat_capacity, time filters, route and status analysis
CREATE INDEX ix_bookings_run_class        ON core.bookings (train_id, journey_date, travel_class);
CREATE INDEX ix_bookings_journey_date     ON core.bookings (journey_date);
CREATE INDEX ix_bookings_route            ON core.bookings (route_id);
CREATE INDEX ix_bookings_status           ON core.bookings (booking_status);

-- passengers: status analysis (waiting list, cancellation) and the optional refund link
CREATE INDEX ix_bp_status_pair            ON core.booking_passengers (initial_status, final_status);
CREATE INDEX ix_bp_cancellation           ON core.booking_passengers (cancellation_id) WHERE cancellation_id IS NOT NULL;

-- cancellation events: join to booking, refund analysis by type and time
CREATE INDEX ix_cancellations_booking     ON core.cancellations (booking_id);
CREATE INDEX ix_cancellations_type_ts     ON core.cancellations (cancellation_type, cancellation_ts);
