-- 01_load_staging.sql: load the cleaned CSV files (Phase 2) into stg.* with psql \copy (client-side).
-- Paths are relative to the PROJECT ROOT: run psql from the project root (the runner scripts do this).
-- The ORIGINAL files are only read, never modified.
\echo '>> loading staging tables from data/processed/cleaned/*.csv'
\copy stg.stations           FROM 'data/processed/cleaned/stations.csv'           WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy stg.routes             FROM 'data/processed/cleaned/routes.csv'             WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy stg.trains             FROM 'data/processed/cleaned/trains.csv'             WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy stg.train_stops        FROM 'data/processed/cleaned/train_stops.csv'        WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy stg.calendar           FROM 'data/processed/cleaned/calendar.csv'           WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy stg.seat_capacity      FROM 'data/processed/cleaned/seat_capacity.csv'      WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy stg.train_operations   FROM 'data/processed/cleaned/train_operations.csv'   WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy stg.bookings           FROM 'data/processed/cleaned/bookings.csv'           WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy stg.booking_passengers FROM 'data/processed/cleaned/booking_passengers.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy stg.cancellations      FROM 'data/processed/cleaned/cancellations.csv'      WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
