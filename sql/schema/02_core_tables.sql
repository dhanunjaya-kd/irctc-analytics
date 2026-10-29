-- 02_core_tables.sql: core tables, primary keys, foreign keys, NOT NULL / UNIQUE / CHECK constraints.
-- Implements docs/data_dictionary.md (approved). Secondary indexes are created after the load (03_indexes.sql).
-- Cross-row rules (BR-02, BR-03, BR-04b, BR-05, BR-06, BR-08, BR-10b/c, BR-11a/b/e, BR-12, BR-13) cannot be CHECK constraints;
-- they are verified by sql/validation/01_data_quality_checks.sql after every load.

CREATE TABLE core.stations (
    station_id    INTEGER      NOT NULL,
    station_code  VARCHAR(8)   NOT NULL,
    station_name  VARCHAR(80)  NOT NULL,
    city          VARCHAR(60)  NOT NULL,
    state         VARCHAR(60)  NOT NULL,
    region        VARCHAR(12)  NOT NULL,
    data_origin   VARCHAR(10)  NOT NULL,
    CONSTRAINT pk_stations PRIMARY KEY (station_id),
    CONSTRAINT uq_stations_code UNIQUE (station_code),
    CONSTRAINT ck_stations_code_format CHECK (station_code = upper(btrim(station_code))),                       -- BR-16
    CONSTRAINT ck_stations_region CHECK (region IN ('North','South','East','West','Central','Northeast')),
    CONSTRAINT ck_stations_origin CHECK (data_origin IN ('PUBLIC','SYNTHETIC','DERIVED'))
);

CREATE TABLE core.routes (
    route_id               INTEGER       NOT NULL,
    origin_station_id      INTEGER       NOT NULL,
    destination_station_id INTEGER       NOT NULL,
    route_name             VARCHAR(120)  NOT NULL,
    distance_km            NUMERIC(7,1)  NOT NULL,
    data_origin            VARCHAR(10)   NOT NULL,
    CONSTRAINT pk_routes PRIMARY KEY (route_id),
    CONSTRAINT fk_routes_origin      FOREIGN KEY (origin_station_id)      REFERENCES core.stations (station_id),
    CONSTRAINT fk_routes_destination FOREIGN KEY (destination_station_id) REFERENCES core.stations (station_id),
    CONSTRAINT uq_routes_pair UNIQUE (origin_station_id, destination_station_id),
    CONSTRAINT ck_routes_distinct CHECK (origin_station_id <> destination_station_id),
    CONSTRAINT ck_routes_distance CHECK (distance_km > 0),
    CONSTRAINT ck_routes_origin CHECK (data_origin IN ('PUBLIC','SYNTHETIC','DERIVED'))
);

CREATE TABLE core.trains (
    train_id      INTEGER      NOT NULL,
    train_number  VARCHAR(10)  NOT NULL,
    train_name    VARCHAR(80)  NOT NULL,
    train_type    VARCHAR(12)  NOT NULL,
    route_id      INTEGER      NOT NULL,
    run_days      CHAR(7)      NOT NULL,
    data_origin   VARCHAR(10)  NOT NULL,
    CONSTRAINT pk_trains PRIMARY KEY (train_id),
    CONSTRAINT uq_trains_number UNIQUE (train_number),
    CONSTRAINT fk_trains_route FOREIGN KEY (route_id) REFERENCES core.routes (route_id),
    CONSTRAINT ck_trains_type CHECK (train_type IN ('Superfast','Express','Premium')),
    CONSTRAINT ck_trains_run_days CHECK (run_days ~ '^[YN]{7}$' AND run_days LIKE '%Y%'),                       -- Monday..Sunday
    CONSTRAINT ck_trains_origin CHECK (data_origin IN ('PUBLIC','SYNTHETIC','DERIVED'))
);

CREATE TABLE core.train_stops (
    train_id                 INTEGER       NOT NULL,
    stop_sequence            SMALLINT      NOT NULL,
    station_id               INTEGER       NOT NULL,
    arrival_time             TIME,
    departure_time           TIME,
    day_offset               SMALLINT      NOT NULL,
    distance_from_origin_km  NUMERIC(7,1)  NOT NULL,
    data_origin              VARCHAR(10)   NOT NULL,
    CONSTRAINT pk_train_stops PRIMARY KEY (train_id, stop_sequence),
    CONSTRAINT fk_train_stops_train   FOREIGN KEY (train_id)   REFERENCES core.trains (train_id),
    CONSTRAINT fk_train_stops_station FOREIGN KEY (station_id) REFERENCES core.stations (station_id),
    CONSTRAINT uq_train_stops_station UNIQUE (train_id, station_id),
    CONSTRAINT ck_train_stops_seq CHECK (stop_sequence >= 1),
    CONSTRAINT ck_train_stops_arrival CHECK ((stop_sequence = 1) = (arrival_time IS NULL)),                      -- arrival NULL only at the first stop
    CONSTRAINT ck_train_stops_offset CHECK (day_offset >= 0),
    CONSTRAINT ck_train_stops_distance CHECK (distance_from_origin_km >= 0),
    CONSTRAINT ck_train_stops_origin CHECK (data_origin IN ('PUBLIC','SYNTHETIC','DERIVED'))
);

CREATE TABLE core.calendar (
    calendar_date          DATE         NOT NULL,
    year                   SMALLINT     NOT NULL,
    quarter                SMALLINT     NOT NULL,
    month_number           SMALLINT     NOT NULL,
    month_name             VARCHAR(9)   NOT NULL,
    week_of_year           SMALLINT     NOT NULL,
    day_of_month           SMALLINT     NOT NULL,
    day_of_week_number     SMALLINT     NOT NULL,
    day_name               VARCHAR(9)   NOT NULL,
    is_weekend             BOOLEAN      NOT NULL,
    season                 VARCHAR(12)  NOT NULL,
    fiscal_year            SMALLINT     NOT NULL,
    is_holiday             BOOLEAN      NOT NULL,
    holiday_name           VARCHAR(60),
    is_peak_travel_period  BOOLEAN      NOT NULL,
    peak_period_name       VARCHAR(60),
    data_origin            VARCHAR(10)  NOT NULL,
    CONSTRAINT pk_calendar PRIMARY KEY (calendar_date),
    CONSTRAINT ck_calendar_quarter CHECK (quarter BETWEEN 1 AND 4),
    CONSTRAINT ck_calendar_month CHECK (month_number BETWEEN 1 AND 12),
    CONSTRAINT ck_calendar_week CHECK (week_of_year BETWEEN 1 AND 53),
    CONSTRAINT ck_calendar_day CHECK (day_of_month BETWEEN 1 AND 31),
    CONSTRAINT ck_calendar_dow CHECK (day_of_week_number BETWEEN 1 AND 7),
    CONSTRAINT ck_calendar_season CHECK (season IN ('Winter','Summer','Monsoon','Post-Monsoon')),
    CONSTRAINT ck_calendar_holiday_name CHECK (NOT is_holiday OR holiday_name IS NOT NULL),
    CONSTRAINT ck_calendar_peak_name CHECK (NOT is_peak_travel_period OR peak_period_name IS NOT NULL),
    CONSTRAINT ck_calendar_origin CHECK (data_origin IN ('PUBLIC','SYNTHETIC','DERIVED'))
);

CREATE TABLE core.seat_capacity (
    capacity_id       BIGINT       NOT NULL,
    train_id          INTEGER      NOT NULL,
    journey_date      DATE         NOT NULL,
    travel_class      CHAR(2)      NOT NULL,
    coaches_attached  SMALLINT     NOT NULL,
    seats_per_coach   SMALLINT     NOT NULL,
    total_seats       INTEGER      NOT NULL,
    rac_berths        SMALLINT     NOT NULL,
    wl_limit          INTEGER      NOT NULL,
    data_origin       VARCHAR(10)  NOT NULL,
    CONSTRAINT pk_seat_capacity PRIMARY KEY (capacity_id),
    CONSTRAINT fk_seat_capacity_train FOREIGN KEY (train_id)     REFERENCES core.trains (train_id),
    CONSTRAINT fk_seat_capacity_date  FOREIGN KEY (journey_date) REFERENCES core.calendar (calendar_date),
    CONSTRAINT uq_seat_capacity_run_class UNIQUE (train_id, journey_date, travel_class),
    CONSTRAINT ck_seat_capacity_class CHECK (travel_class IN ('SL','3A','2A','1A','CC','2S')),
    CONSTRAINT ck_seat_capacity_coaches CHECK (coaches_attached > 0),
    CONSTRAINT ck_seat_capacity_spc CHECK (seats_per_coach = CASE travel_class                                  -- BR-09b: class standard
        WHEN '1A' THEN 24 WHEN '2A' THEN 46 WHEN '3A' THEN 64 WHEN 'SL' THEN 72 WHEN 'CC' THEN 78 WHEN '2S' THEN 108 END),
    CONSTRAINT ck_seat_capacity_total CHECK (total_seats > 0 AND total_seats = coaches_attached * seats_per_coach),  -- BR-09a
    CONSTRAINT ck_seat_capacity_rac CHECK (rac_berths >= 0 AND rac_berths <= total_seats),
    CONSTRAINT ck_seat_capacity_wl CHECK (wl_limit >= 0),
    CONSTRAINT ck_seat_capacity_origin CHECK (data_origin IN ('PUBLIC','SYNTHETIC','DERIVED'))
);

CREATE TABLE core.train_operations (
    operation_id         BIGINT       NOT NULL,
    train_id             INTEGER      NOT NULL,
    run_date             DATE         NOT NULL,
    departure_delay_min  INTEGER      NOT NULL,
    arrival_delay_min    INTEGER,
    data_origin          VARCHAR(10)  NOT NULL,
    CONSTRAINT pk_train_operations PRIMARY KEY (operation_id),
    CONSTRAINT fk_train_operations_train FOREIGN KEY (train_id) REFERENCES core.trains (train_id),
    CONSTRAINT fk_train_operations_date  FOREIGN KEY (run_date) REFERENCES core.calendar (calendar_date),
    CONSTRAINT uq_train_operations_run UNIQUE (train_id, run_date),
    CONSTRAINT ck_train_operations_dep CHECK (departure_delay_min BETWEEN -60 AND 1440),
    CONSTRAINT ck_train_operations_arr CHECK (arrival_delay_min IS NULL OR arrival_delay_min BETWEEN -60 AND 1440),  -- NULL = missing, never imputed
    CONSTRAINT ck_train_operations_origin CHECK (data_origin IN ('PUBLIC','SYNTHETIC','DERIVED'))
);

CREATE TABLE core.bookings (
    booking_id              BIGINT         NOT NULL,
    booking_reference       VARCHAR(12)    NOT NULL,
    train_id                INTEGER        NOT NULL,
    journey_date            DATE           NOT NULL,
    route_id                INTEGER        NOT NULL,
    boarding_station_id     INTEGER        NOT NULL,
    destination_station_id  INTEGER        NOT NULL,
    travel_class            CHAR(2)        NOT NULL,
    booking_ts              TIMESTAMP      NOT NULL,
    num_passengers          SMALLINT       NOT NULL,
    booking_status          VARCHAR(10)    NOT NULL,
    total_fare              NUMERIC(12,2)  NOT NULL,
    data_origin             VARCHAR(10)    NOT NULL,
    CONSTRAINT pk_bookings PRIMARY KEY (booking_id),
    CONSTRAINT uq_bookings_reference UNIQUE (booking_reference),
    CONSTRAINT fk_bookings_train       FOREIGN KEY (train_id)               REFERENCES core.trains (train_id),
    CONSTRAINT fk_bookings_date        FOREIGN KEY (journey_date)           REFERENCES core.calendar (calendar_date),
    CONSTRAINT fk_bookings_route       FOREIGN KEY (route_id)               REFERENCES core.routes (route_id),
    CONSTRAINT fk_bookings_boarding    FOREIGN KEY (boarding_station_id)    REFERENCES core.stations (station_id),
    CONSTRAINT fk_bookings_destination FOREIGN KEY (destination_station_id) REFERENCES core.stations (station_id),
    CONSTRAINT fk_bookings_capacity    FOREIGN KEY (train_id, journey_date, travel_class)                          -- BR-07
                                       REFERENCES core.seat_capacity (train_id, journey_date, travel_class),
    CONSTRAINT ck_bookings_class CHECK (travel_class IN ('SL','3A','2A','1A','CC','2S')),
    CONSTRAINT ck_bookings_pax CHECK (num_passengers BETWEEN 1 AND 6),
    CONSTRAINT ck_bookings_status CHECK (booking_status IN ('Confirmed','RAC','Waitlisted','Cancelled','Mixed')),
    CONSTRAINT ck_bookings_fare CHECK (total_fare > 0),
    CONSTRAINT ck_bookings_stations CHECK (boarding_station_id <> destination_station_id),
    CONSTRAINT ck_bookings_origin CHECK (data_origin IN ('PUBLIC','SYNTHETIC','DERIVED'))
);

CREATE TABLE core.cancellations (
    cancellation_id         BIGINT         NOT NULL,
    booking_id              BIGINT         NOT NULL,
    cancellation_ts         TIMESTAMP      NOT NULL,
    cancellation_type       VARCHAR(9)     NOT NULL,
    status_at_cancellation  VARCHAR(10)    NOT NULL,
    cancelled_passengers    SMALLINT       NOT NULL,
    original_fare_amount    NUMERIC(12,2)  NOT NULL,
    cancellation_charge     NUMERIC(10,2)  NOT NULL,
    refund_amount           NUMERIC(12,2)  NOT NULL,
    data_origin             VARCHAR(10)    NOT NULL,
    CONSTRAINT pk_cancellations PRIMARY KEY (cancellation_id),
    CONSTRAINT fk_cancellations_booking FOREIGN KEY (booking_id) REFERENCES core.bookings (booking_id),          -- not unique: several events per booking
    CONSTRAINT ck_cancellations_type CHECK (cancellation_type IN ('Passenger','System')),
    CONSTRAINT ck_cancellations_status CHECK (status_at_cancellation IN ('Confirmed','RAC','Waitlisted')),
    CONSTRAINT ck_cancellations_system CHECK (cancellation_type <> 'System' OR status_at_cancellation = 'Waitlisted'),
    CONSTRAINT ck_cancellations_pax CHECK (cancelled_passengers BETWEEN 1 AND 6),
    CONSTRAINT ck_cancellations_original CHECK (original_fare_amount > 0),
    CONSTRAINT ck_cancellations_amounts CHECK (cancellation_charge >= 0 AND refund_amount >= 0),
    CONSTRAINT ck_cancellations_arithmetic CHECK (refund_amount + cancellation_charge = original_fare_amount),   -- BR-11c
    CONSTRAINT ck_cancellations_origin CHECK (data_origin IN ('PUBLIC','SYNTHETIC','DERIVED'))
);

CREATE TABLE core.booking_passengers (
    passenger_id     BIGINT         NOT NULL,
    booking_id       BIGINT         NOT NULL,
    passenger_seq    SMALLINT       NOT NULL,
    age_band         VARCHAR(7)     NOT NULL,
    fare_amount      NUMERIC(10,2)  NOT NULL,
    initial_status   VARCHAR(10)    NOT NULL,
    final_status     VARCHAR(10)    NOT NULL,
    cancellation_id  BIGINT,
    data_origin      VARCHAR(10)    NOT NULL,
    CONSTRAINT pk_booking_passengers PRIMARY KEY (passenger_id),
    CONSTRAINT fk_booking_passengers_booking      FOREIGN KEY (booking_id)      REFERENCES core.bookings (booking_id),
    CONSTRAINT fk_booking_passengers_cancellation FOREIGN KEY (cancellation_id) REFERENCES core.cancellations (cancellation_id),
    CONSTRAINT uq_booking_passengers_seq UNIQUE (booking_id, passenger_seq),
    CONSTRAINT ck_booking_passengers_seq CHECK (passenger_seq BETWEEN 1 AND 6),
    CONSTRAINT ck_booking_passengers_age CHECK (age_band IN ('Child','Adult','Senior','Unknown')),               -- Unknown = missing in source, not imputed
    CONSTRAINT ck_booking_passengers_fare CHECK (fare_amount > 0),
    CONSTRAINT ck_booking_passengers_initial CHECK (initial_status IN ('Confirmed','RAC','Waitlisted')),
    CONSTRAINT ck_booking_passengers_final CHECK (final_status IN ('Confirmed','RAC','Waitlisted','Cancelled')),
    CONSTRAINT ck_booking_passengers_link CHECK ((cancellation_id IS NOT NULL) = (final_status IN ('Cancelled','Waitlisted'))),   -- BR-10a
    CONSTRAINT ck_booking_passengers_transition CHECK (                                                           -- BR-17: no demotion
        (initial_status = 'Confirmed' AND final_status IN ('Confirmed','Cancelled'))
     OR (initial_status = 'RAC'       AND final_status IN ('RAC','Confirmed','Cancelled'))
     OR (initial_status = 'Waitlisted')),
    CONSTRAINT ck_booking_passengers_origin CHECK (data_origin IN ('PUBLIC','SYNTHETIC','DERIVED'))
);

COMMENT ON TABLE core.booking_passengers IS 'One row per passenger; status is tracked here (initial_status at booking, final_status at chart preparation). SYNTHETIC.';
COMMENT ON TABLE core.cancellations      IS 'One row per refund EVENT: Passenger cancellation or System auto-refund of an uncleared waitlist. SYNTHETIC.';
COMMENT ON TABLE core.seat_capacity      IS 'One row per SIMULATED train-class run. Capacity is simulated (coaches x real seats per coach). Only 768 of 19,708 scheduled runs are simulated.';
COMMENT ON TABLE core.train_operations   IS 'One row per SIMULATED train run. Delays are simulated; arrival_delay_min NULL = missing, never imputed.';
