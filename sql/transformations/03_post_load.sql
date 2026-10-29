-- 05_post_load.sql: refresh planner statistics after the bulk load.
ANALYZE core.stations; ANALYZE core.routes; ANALYZE core.trains; ANALYZE core.train_stops; ANALYZE core.calendar;
ANALYZE core.seat_capacity; ANALYZE core.train_operations; ANALYZE core.bookings; ANALYZE core.cancellations; ANALYZE core.booking_passengers;
