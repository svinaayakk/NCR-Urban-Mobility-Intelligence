-- name: zone_hourly_fleet_pressure
-- Identify the highest demand pressure zone-hours. Values above 1 mean more requests than available vehicles.
SELECT
    z.city,
    z.zone_name,
    d.timestamp,
    d.ride_requests,
    d.available_vehicles,
    ROUND(1.0 * d.ride_requests / NULLIF(d.available_vehicles, 0), 2) AS demand_supply_ratio,
    d.cancelled_trips,
    d.avg_wait_time_min
FROM demand_supply d
JOIN zones z ON z.zone_id = d.zone_id
ORDER BY demand_supply_ratio DESC, d.cancelled_trips DESC
LIMIT 100;

-- name: zone_experience_hotspots
-- Prioritize zones with both poor customer experience and meaningful trip volume.
SELECT
    z.city,
    z.zone_name,
    COUNT(*) AS trips,
    ROUND(100.0 * AVG(CASE WHEN t.status = 'Cancelled' THEN 1.0 ELSE 0.0 END), 2) AS cancellation_rate_pct,
    ROUND(AVG(t.wait_time_min), 2) AS avg_wait_time_min,
    ROUND(SUM(CASE WHEN t.status = 'Completed' THEN t.fare ELSE 0 END), 2) AS completed_revenue
FROM trips t
JOIN zones z ON z.zone_id = t.pickup_zone_id
GROUP BY z.city, z.zone_name
ORDER BY cancellation_rate_pct DESC, avg_wait_time_min DESC, trips DESC;

-- name: vehicle_revenue_performance
SELECT
    vehicle_type,
    COUNT(*) AS trips,
    ROUND(SUM(CASE WHEN status = 'Completed' THEN fare ELSE 0 END), 2) AS completed_revenue,
    ROUND(AVG(fare), 2) AS avg_fare,
    ROUND(100.0 * AVG(CASE WHEN status = 'Cancelled' THEN 1.0 ELSE 0.0 END), 2) AS cancellation_rate_pct
FROM trips
GROUP BY vehicle_type
ORDER BY completed_revenue DESC;

-- name: cross_city_corridors
SELECT
    pickup.city || ' → ' || dropoff.city AS corridor,
    COUNT(*) AS trips,
    ROUND(AVG(t.wait_time_min), 2) AS avg_wait_time_min,
    ROUND(SUM(CASE WHEN t.status = 'Completed' THEN t.fare ELSE 0 END), 2) AS completed_revenue
FROM trips t
JOIN zones pickup ON pickup.zone_id = t.pickup_zone_id
JOIN zones dropoff ON dropoff.zone_id = t.drop_zone_id
WHERE pickup.city <> dropoff.city
GROUP BY pickup.city, dropoff.city
ORDER BY trips DESC;

-- name: traffic_customer_experience
SELECT
    tr.congestion_level,
    COUNT(*) AS trips,
    ROUND(AVG(t.trip_duration_min), 2) AS avg_trip_duration_min,
    ROUND(AVG(t.wait_time_min), 2) AS avg_wait_time_min,
    ROUND(100.0 * AVG(CASE WHEN t.status = 'Cancelled' THEN 1.0 ELSE 0.0 END), 2) AS cancellation_rate_pct
FROM trips t
JOIN traffic tr
  ON tr.zone_id = t.pickup_zone_id
 AND tr.timestamp = t.request_timestamp
GROUP BY tr.congestion_level
ORDER BY avg_trip_duration_min DESC;
