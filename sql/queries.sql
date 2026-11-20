-- Analysis queries run against the SQLite export of a simulated week.
-- Each query is introduced by a "-- name:" line and is run by twin/store.py.

-- name: busiest_segments
-- Average weekday trips on each road segment and its busiest hour.
WITH daily AS (
    SELECT segment, day, SUM(trips) AS trips
    FROM road_usage GROUP BY segment, day
), peak AS (
    SELECT segment, hour, SUM(trips) AS trips,
           ROW_NUMBER() OVER (PARTITION BY segment ORDER BY SUM(trips) DESC) AS rk
    FROM road_usage GROUP BY segment, hour
)
SELECT d.segment,
       ROUND(AVG(d.trips), 0)            AS avg_weekday_trips,
       p.hour                            AS peak_hour,
       ROUND(p.trips / 5.0, 0)           AS avg_trips_in_peak_hour
FROM daily d JOIN peak p ON p.segment = d.segment AND p.rk = 1
GROUP BY d.segment
ORDER BY avg_weekday_trips DESC
LIMIT 10;

-- name: peak_occupancy
-- Highest number of people in each non-residential building, when it occurs and the share of capacity used.
SELECT o.place, o.kind, o.day, o.time, o.people, p.capacity,
       ROUND(100.0 * o.people / p.capacity, 0) AS utilisation_pct
FROM (
    SELECT occupancy.*, ROW_NUMBER() OVER (PARTITION BY place ORDER BY people DESC, day, step) AS rk
    FROM occupancy WHERE kind NOT IN ('hall', 'gate')
) o JOIN places p ON p.place = o.place
WHERE o.rk = 1
ORDER BY utilisation_pct DESC;

-- name: trips_by_day_purpose
SELECT day, purpose, COUNT(*) AS trips, ROUND(AVG(distance_m), 0) AS mean_distance_m
FROM trips
GROUP BY day, purpose
ORDER BY CASE day WHEN 'Mon' THEN 1 WHEN 'Tue' THEN 2 WHEN 'Wed' THEN 3 WHEN 'Thu' THEN 4 ELSE 5 END, trips DESC;

-- name: mode_split
SELECT mode, COUNT(*) AS trips,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM trips), 1) AS share_pct,
       ROUND(AVG(minutes), 1) AS mean_minutes
FROM trips GROUP BY mode;

-- name: hall_outflow_peak
-- Departures from each hall in the busiest 15-minute window of the week.
SELECT origin AS hall, day, CAST(depart_min / 15 AS INTEGER) * 15 AS window_start_min, COUNT(*) AS departures
FROM trips
WHERE origin LIKE 'Hall %'
GROUP BY origin, day, window_start_min
ORDER BY departures DESC
LIMIT 8;
