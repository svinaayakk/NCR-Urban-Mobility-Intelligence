PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS trips;
DROP TABLE IF EXISTS demand_supply;
DROP TABLE IF EXISTS traffic;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS weather;
DROP TABLE IF EXISTS drivers;
DROP TABLE IF EXISTS vehicles;
DROP TABLE IF EXISTS zones;

CREATE TABLE zones (
    zone_id TEXT PRIMARY KEY,
    zone_name TEXT NOT NULL,
    city TEXT NOT NULL,
    zone_type TEXT,
    population_density_score INTEGER,
    commercial_density_score INTEGER,
    residential_density_score INTEGER,
    metro_access TEXT,
    airport_proximity TEXT
);

CREATE TABLE vehicles (
    vehicle_id TEXT PRIMARY KEY,
    vehicle_type TEXT NOT NULL,
    fuel_type TEXT,
    capacity INTEGER,
    vehicle_age_years REAL,
    join_date TEXT,
    home_zone_id TEXT,
    status TEXT,
    FOREIGN KEY (home_zone_id) REFERENCES zones(zone_id)
);

CREATE TABLE drivers (
    driver_id TEXT PRIMARY KEY,
    vehicle_id TEXT,
    home_zone_id TEXT,
    experience_years REAL,
    driver_rating REAL,
    join_date TEXT,
    driver_status TEXT,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
    FOREIGN KEY (home_zone_id) REFERENCES zones(zone_id)
);

CREATE TABLE weather (
    timestamp TEXT PRIMARY KEY,
    temperature_c REAL,
    rainfall_mm REAL,
    humidity_pct REAL,
    visibility_km REAL,
    weather_condition TEXT
);

CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    event_date TEXT,
    zone_id TEXT,
    event_type TEXT,
    expected_impact TEXT,
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
);

CREATE TABLE traffic (
    timestamp TEXT,
    zone_id TEXT,
    congestion_level TEXT,
    avg_speed_kmph REAL,
    traffic_index REAL,
    PRIMARY KEY (timestamp, zone_id),
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
);

CREATE TABLE demand_supply (
    timestamp TEXT,
    zone_id TEXT,
    ride_requests INTEGER,
    available_vehicles INTEGER,
    completed_trips INTEGER,
    cancelled_trips INTEGER,
    avg_wait_time_min REAL,
    PRIMARY KEY (timestamp, zone_id),
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
);

CREATE TABLE trips (
    trip_id TEXT PRIMARY KEY,
    request_timestamp TEXT,
    pickup_timestamp TEXT,
    dropoff_timestamp TEXT,
    pickup_zone_id TEXT,
    drop_zone_id TEXT,
    driver_id TEXT,
    vehicle_id TEXT,
    vehicle_type TEXT,
    distance_km REAL,
    fare REAL,
    wait_time_min REAL,
    trip_duration_min REAL,
    status TEXT,
    cancellation_reason TEXT,
    payment_method TEXT,
    surge_multiplier REAL,
    discount REAL,
    rating REAL,
    is_driver_linked INTEGER,
    FOREIGN KEY (pickup_zone_id) REFERENCES zones(zone_id),
    FOREIGN KEY (drop_zone_id) REFERENCES zones(zone_id),
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id)
);

CREATE INDEX idx_trips_pickup_time ON trips(pickup_zone_id, request_timestamp);
CREATE INDEX idx_trips_vehicle_type ON trips(vehicle_type);
CREATE INDEX idx_demand_zone_time ON demand_supply(zone_id, timestamp);
