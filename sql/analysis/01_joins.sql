-- 01_joins.sql: join techniques on the core tables. Every label [J..] marks one runnable statement.
-- SYNTHETIC data, sampled simulation (768 of 19,708 scheduled runs): counts are per simulated run population, not network totals.

-- [J1] INNER JOIN across three tables: bookings and passengers by route and train type (top 10).
SELECT r.route_name, t.train_type, count(*) AS bookings, sum(b.num_passengers) AS passengers
FROM core.bookings b
JOIN core.trains t ON t.train_id = b.train_id
JOIN core.routes r ON r.route_id = t.route_id
GROUP BY r.route_name, t.train_type
ORDER BY passengers DESC, r.route_name
LIMIT 10;

-- [J2] LEFT JOIN: every station with the number of routes that start there (stations with none still appear, with 0).
SELECT s.station_code, s.city, count(r.route_id) AS routes_from_station
FROM core.stations s
LEFT JOIN core.routes r ON r.origin_station_id = s.station_id
GROUP BY s.station_id, s.station_code, s.city
ORDER BY routes_from_station, s.station_code;

-- [J3] ANTI-JOIN (LEFT JOIN ... IS NULL): stations that are never the boarding station of any booking in the simulated data.
SELECT s.station_code, s.city
FROM core.stations s
LEFT JOIN core.bookings b ON b.boarding_station_id = s.station_id
WHERE b.booking_id IS NULL
ORDER BY s.station_code;

-- [J4] RIGHT JOIN: simulated train-class runs (right side) with no booking at all (NULL on the left side).
SELECT sc.capacity_id, sc.journey_date, sc.travel_class, sc.total_seats
FROM (SELECT train_id, journey_date, travel_class, count(*) AS bookings FROM core.bookings GROUP BY train_id, journey_date, travel_class) x
RIGHT JOIN core.seat_capacity sc ON sc.train_id = x.train_id AND sc.journey_date = x.journey_date AND sc.travel_class = x.travel_class
WHERE x.bookings IS NULL
ORDER BY sc.journey_date, sc.travel_class;

-- [J5] FULL OUTER JOIN: months present in the bookings, only in the operations table, or in both (a quick completeness check).
SELECT coalesce(b.journey_month, o.journey_month) AS journey_month, b.bookings, o.simulated_runs
FROM (SELECT journey_month, count(*) AS bookings FROM analytics.v_booking GROUP BY journey_month) b
FULL OUTER JOIN (SELECT journey_month, count(*) AS simulated_runs FROM analytics.v_run GROUP BY journey_month) o ON o.journey_month = b.journey_month
ORDER BY 1;

-- [J6] SELF JOIN: consecutive stops of the same train give each leg; the legs of a train add up to its route distance.
SELECT t.train_number, r.distance_km AS route_distance_km, sum(b.distance_from_origin_km - a.distance_from_origin_km) AS sum_of_legs_km, count(*) AS legs
FROM core.train_stops a
JOIN core.train_stops b ON b.train_id = a.train_id AND b.stop_sequence = a.stop_sequence + 1
JOIN core.trains t ON t.train_id = a.train_id
JOIN core.routes r ON r.route_id = t.route_id
GROUP BY t.train_number, r.distance_km
ORDER BY t.train_number
LIMIT 10;

-- [J7] CROSS JOIN: a month x class grid so that months where a class has no simulated run show 0 instead of disappearing.
SELECT m.journey_month, c.travel_class, count(cr.capacity_id) AS class_runs
FROM (SELECT DISTINCT journey_month FROM analytics.v_class_run) m
CROSS JOIN (VALUES ('SL'), ('3A'), ('2A'), ('1A'), ('CC'), ('2S')) AS c(travel_class)
LEFT JOIN analytics.v_class_run cr ON cr.journey_month = m.journey_month AND cr.travel_class = c.travel_class
GROUP BY m.journey_month, c.travel_class
ORDER BY m.journey_month, c.travel_class
LIMIT 12;

-- [J8] Join at the right grain: aggregate passengers per class-run FIRST, then join to capacity (joining passengers straight to capacity would repeat seats once per passenger).
SELECT sc.travel_class, sum(sc.total_seats) AS seats, sum(p.passengers) AS passengers
FROM core.seat_capacity sc
LEFT JOIN (SELECT b.train_id, b.journey_date, b.travel_class, count(*) AS passengers
           FROM core.booking_passengers bp JOIN core.bookings b ON b.booking_id = bp.booking_id GROUP BY 1, 2, 3) p
       ON p.train_id = sc.train_id AND p.journey_date = sc.journey_date AND p.travel_class = sc.travel_class
GROUP BY sc.travel_class
ORDER BY sc.travel_class;
