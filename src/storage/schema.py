"""Module 6 SQLite schema version 1."""

SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS simulation_runs (
    run_id TEXT PRIMARY KEY,
    module INTEGER NOT NULL,
    execution_mode TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('RUNNING','COMPLETED','FAILED')),
    started_at_utc TEXT NOT NULL,
    finished_at_utc TEXT,
    energyplus_version TEXT NOT NULL,
    api_version TEXT NOT NULL,
    model_path TEXT NOT NULL,
    model_checksum TEXT NOT NULL,
    weather_path TEXT NOT NULL,
    weather_checksum TEXT NOT NULL,
    configuration_checksum TEXT NOT NULL,
    expected_snapshot_count INTEGER NOT NULL CHECK(expected_snapshot_count >= 0),
    persisted_snapshot_count INTEGER NOT NULL DEFAULT 0 CHECK(persisted_snapshot_count >= 0),
    first_sequence INTEGER,
    last_sequence INTEGER,
    first_simulation_timestamp TEXT,
    last_simulation_timestamp TEXT,
    severe_count INTEGER NOT NULL DEFAULT 0,
    fatal_count INTEGER NOT NULL DEFAULT 0,
    callback_error_count INTEGER NOT NULL DEFAULT 0,
    api_error_count INTEGER NOT NULL DEFAULT 0,
    subscriber_error_count INTEGER NOT NULL DEFAULT 0,
    persistence_error_count INTEGER NOT NULL DEFAULT 0,
    queue_drained INTEGER NOT NULL DEFAULT 0 CHECK(queue_drained IN (0,1)),
    actuator_access_count INTEGER NOT NULL DEFAULT 0 CHECK(actuator_access_count >= 0),
    control_decision_count INTEGER NOT NULL DEFAULT 0 CHECK(control_decision_count >= 0),
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS building_states (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES simulation_runs(run_id) ON DELETE CASCADE,
    schema_version INTEGER NOT NULL CHECK(schema_version = 1),
    sequence INTEGER NOT NULL CHECK(sequence > 0),
    source TEXT NOT NULL,
    execution_mode TEXT NOT NULL,
    captured_at_utc TEXT NOT NULL,
    environment_number INTEGER NOT NULL,
    environment_type INTEGER NOT NULL,
    calendar_year INTEGER,
    month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    day INTEGER NOT NULL CHECK(day BETWEEN 1 AND 31),
    day_of_year INTEGER NOT NULL CHECK(day_of_year BETWEEN 1 AND 366),
    day_of_week INTEGER NOT NULL,
    hour INTEGER NOT NULL CHECK(hour BETWEEN 0 AND 24),
    minute INTEGER NOT NULL CHECK(minute BETWEEN 0 AND 99),
    current_time_hours REAL NOT NULL,
    current_simulation_time_hours REAL NOT NULL,
    zone_timestep_number INTEGER NOT NULL CHECK(zone_timestep_number > 0),
    zone_timesteps_per_hour INTEGER NOT NULL CHECK(zone_timesteps_per_hour > 0),
    warmup INTEGER NOT NULL CHECK(warmup IN (0,1)),
    outdoor_dry_bulb_c REAL NOT NULL,
    outdoor_relative_humidity_percent REAL NOT NULL
        CHECK(outdoor_relative_humidity_percent BETWEEN 0 AND 100),
    facility_purchased_electricity_raw_j REAL NOT NULL,
    facility_demand_rate_w REAL NOT NULL,
    hvac_electricity_raw_j REAL NOT NULL,
    cooling_electricity_raw_j REAL,
    heating_electricity_raw_j REAL,
    meter_units TEXT NOT NULL,
    raw_snapshot_sequence INTEGER NOT NULL,
    fingerprint TEXT NOT NULL CHECK(length(fingerprint) = 64),
    canonical_json TEXT NOT NULL,
    UNIQUE(run_id, sequence),
    UNIQUE(run_id, fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_building_states_run_sequence
ON building_states(run_id, sequence);
CREATE INDEX IF NOT EXISTS idx_building_states_run_time
ON building_states(run_id, current_simulation_time_hours);
CREATE TABLE IF NOT EXISTS zone_states (
    id INTEGER PRIMARY KEY,
    building_state_id INTEGER NOT NULL REFERENCES building_states(id) ON DELETE CASCADE,
    zone_id TEXT NOT NULL,
    exact_name TEXT NOT NULL,
    classification TEXT NOT NULL CHECK(classification IN
        ('OCCUPIED_CONDITIONED','UNOCCUPIED_CONDITIONED','PLENUM','OTHER')),
    occupancy_capable INTEGER NOT NULL CHECK(occupancy_capable IN (0,1)),
    is_plenum INTEGER NOT NULL CHECK(is_plenum IN (0,1)),
    mean_air_temperature_c REAL NOT NULL,
    occupant_count REAL NOT NULL CHECK(occupant_count >= 0),
    relative_humidity_percent REAL
        CHECK(relative_humidity_percent IS NULL OR
              relative_humidity_percent BETWEEN 0 AND 100),
    pmv REAL,
    co2_ppm REAL,
    effective_cooling_setpoint_c REAL,
    availability_json TEXT NOT NULL,
    quality_issues_json TEXT NOT NULL,
    UNIQUE(building_state_id, zone_id)
);
CREATE INDEX IF NOT EXISTS idx_zone_states_state ON zone_states(building_state_id);
CREATE INDEX IF NOT EXISTS idx_zone_states_zone ON zone_states(zone_id, building_state_id);
CREATE TABLE IF NOT EXISTS sensor_availability (
    id INTEGER PRIMARY KEY,
    building_state_id INTEGER NOT NULL REFERENCES building_states(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    available INTEGER NOT NULL CHECK(available IN (0,1)),
    source TEXT NOT NULL,
    reason TEXT NOT NULL,
    UNIQUE(building_state_id, field_name)
);
CREATE TABLE IF NOT EXISTS state_quality_issues (
    id INTEGER PRIMARY KEY,
    building_state_id INTEGER NOT NULL REFERENCES building_states(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    zone_id TEXT
);
CREATE TABLE IF NOT EXISTS storage_events (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES simulation_runs(run_id) ON DELETE CASCADE,
    created_at_utc TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT NOT NULL
);
"""
