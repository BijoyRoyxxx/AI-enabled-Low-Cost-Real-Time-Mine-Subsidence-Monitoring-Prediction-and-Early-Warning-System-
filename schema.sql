-- ============================================================================
-- GEO-SHIELD MINE SUBSIDENCE MONITORING SYSTEM
-- Database Schema: schema.sql (PostgreSQL)
-- Circuit & Architecture: ESP32 + MPU6050 + ADXL355 + LVDT + Crack Gauge + BME280 + SX1278
-- Target Site: Bowen Basin Longwall Coal Mine Panel (-23.5512, 148.1750)
-- Surface Topology: 20-Node Multi-Hop LoRa Mesh Grid (N1 to N20) + Gateway
-- ============================================================================

DROP TABLE IF EXISTS command_audit_logs CASCADE;
DROP TABLE IF EXISTS telemetry_logs CASCADE;
DROP TABLE IF EXISTS hazard_zones CASCADE;
DROP TABLE IF EXISTS nodes CASCADE;

-- ----------------------------------------------------------------------------
-- 1. NODES TABLE (Surface Units N1..N20 & Gateway Base Station)
-- ----------------------------------------------------------------------------
CREATE TABLE nodes (
    node_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(64) NOT NULL, -- 'Surface Sensor Node', 'LoRa Gateway / Base Station'
    grid_row INT DEFAULT 1,
    grid_col INT DEFAULT 1,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    elevation_m DOUBLE PRECISION NOT NULL,
    depth_m DOUBLE PRECISION DEFAULT 0.0,
    mcu VARCHAR(64) DEFAULT 'ESP32-WROOM-32',
    tilt_sensor VARCHAR(64) DEFAULT 'MPU6050 (Biaxial Tilt)',
    vibe_sensor VARCHAR(64) DEFAULT 'ADXL355 (Triaxial Geophone)',
    disp_sensor VARCHAR(64) DEFAULT 'LVDT + Conditioner',
    crack_sensor VARCHAR(64) DEFAULT 'Crack Opening Gauge',
    env_sensor VARCHAR(64) DEFAULT 'BME280 (Temp & Humidity)',
    lora_module VARCHAR(64) DEFAULT 'SX1278 (Spread Spectrum)',
    battery_spec VARCHAR(100) DEFAULT '12V Lead-Acid / LiFePO4 + Solar Buck Reg',
    solar_wattage DOUBLE PRECISION DEFAULT 20.0,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_nodes_status ON nodes(status);

-- ----------------------------------------------------------------------------
-- 2. TELEMETRY LOGS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE telemetry_logs (
    id BIGSERIAL PRIMARY KEY,
    node_id VARCHAR(32) NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    tilt_x_deg DOUBLE PRECISION DEFAULT 0.0,
    tilt_y_deg DOUBLE PRECISION DEFAULT 0.0,
    tilt_magnitude_deg DOUBLE PRECISION DEFAULT 0.0,
    displacement_mm DOUBLE PRECISION DEFAULT 0.0,
    crack_opening_mm DOUBLE PRECISION DEFAULT 0.0,
    subsidence_velocity_mm_hr DOUBLE PRECISION DEFAULT 0.0,
    vibration_g DOUBLE PRECISION DEFAULT 0.0,
    temperature_c DOUBLE PRECISION DEFAULT 26.5,
    humidity_pct DOUBLE PRECISION DEFAULT 58.0,
    battery_pct DOUBLE PRECISION DEFAULT 100.0,
    battery_voltage_v DOUBLE PRECISION DEFAULT 12.4,
    signal_rssi_dbm INT DEFAULT -75,
    anomaly_score DOUBLE PRECISION DEFAULT 0.0,
    is_anomaly BOOLEAN DEFAULT FALSE,
    health_status VARCHAR(20) DEFAULT 'STABLE'
);

CREATE INDEX idx_telemetry_node_time ON telemetry_logs(node_id, timestamp DESC);
CREATE INDEX idx_telemetry_timestamp ON telemetry_logs(timestamp DESC);

-- ----------------------------------------------------------------------------
-- 3. HAZARD ZONES TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE hazard_zones (
    zone_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    polygon_geojson TEXT NOT NULL,
    max_subsidence_allowable_mm DOUBLE PRECISION NOT NULL,
    current_subsidence_peak_mm DOUBLE PRECISION DEFAULT 0.0,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 4. COMMAND AUDIT LOGS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE command_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    node_id VARCHAR(32) NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    command_type VARCHAR(64) NOT NULL,
    payload JSONB,
    dispatched_by VARCHAR(64) DEFAULT 'GEO-SHIELD_CONTROLLER',
    dispatched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'ACKNOWLEDGED',
    response_message TEXT
);

-- ============================================================================
-- SEED DATA: 20 SENSOR NODES (N1..N20) IN 4x5 GRID + GATEWAY
-- ============================================================================

INSERT INTO nodes (node_id, name, type, grid_row, grid_col, latitude, longitude, elevation_m, depth_m, status)
VALUES
    -- Base Station / LoRa Gateway
    ('GW-01', 'Central LoRa Base Station (ESP32+SX1278+NEO-6M)', 'LoRa Gateway / Base Station', 0, 0, -23.55120, 148.17500, 268.5, 0.0, 'ACTIVE'),

    -- Row 1: N1 to N5
    ('N1',  'Surface Unit N1 (Perimeter North-West)', 'Surface Sensor Node', 1, 1, -23.55000, 148.17300, 265.2, 45.0, 'ACTIVE'),
    ('N2',  'Surface Unit N2 (North Perimeter)',      'Surface Sensor Node', 1, 2, -23.55000, 148.17400, 265.0, 45.0, 'ACTIVE'),
    ('N3',  'Surface Unit N3 (North Centerline)',     'Surface Sensor Node', 1, 3, -23.55000, 148.17500, 264.8, 45.0, 'ACTIVE'),
    ('N4',  'Surface Unit N4 (North Perimeter East)', 'Surface Sensor Node', 1, 4, -23.55000, 148.17600, 264.9, 45.0, 'ACTIVE'),
    ('N5',  'Surface Unit N5 (North-East Perimeter)', 'Surface Sensor Node', 1, 5, -23.55000, 148.17700, 265.3, 45.0, 'ACTIVE'),

    -- Row 2: N6 to N10
    ('N6',  'Surface Unit N6 (Mid-North West)',       'Surface Sensor Node', 2, 1, -23.55080, 148.17300, 264.5, 45.0, 'ACTIVE'),
    ('N7',  'Surface Unit N7 (Upper Trough Flank)',   'Surface Sensor Node', 2, 2, -23.55080, 148.17400, 263.2, 45.0, 'ACTIVE'),
    ('N8',  'Surface Unit N8 (Trough Tension Zone)',  'Surface Sensor Node', 2, 3, -23.55080, 148.17500, 261.8, 45.0, 'ACTIVE'),
    ('N9',  'Surface Unit N9 (Upper Trough Flank E)', 'Surface Sensor Node', 2, 4, -23.55080, 148.17600, 263.0, 45.0, 'ACTIVE'),
    ('N10', 'Surface Unit N10 (Mid-North East)',      'Surface Sensor Node', 2, 5, -23.55080, 148.17700, 264.8, 45.0, 'ACTIVE'),

    -- Row 3: N11 to N15 (N13 is the active longwall subsidence epicenter)
    ('N11', 'Surface Unit N11 (Mid-South West)',      'Surface Sensor Node', 3, 1, -23.55160, 148.17300, 264.0, 45.0, 'ACTIVE'),
    ('N12', 'Surface Unit N12 (Active Shear Flank)',  'Surface Sensor Node', 3, 2, -23.55160, 148.17400, 260.5, 45.0, 'ACTIVE'),
    ('N13', 'Surface Unit N13 (SUBSIDENCE APEX - CRITICAL ANOMALY)', 'Surface Sensor Node', 3, 3, -23.55160, 148.17500, 256.4, 45.0, 'ACTIVE'),
    ('N14', 'Surface Unit N14 (Active Shear Flank E)','Surface Sensor Node', 3, 4, -23.55160, 148.17600, 260.8, 45.0, 'ACTIVE'),
    ('N15', 'Surface Unit N15 (Mid-South East)',      'Surface Sensor Node', 3, 5, -23.55160, 148.17700, 264.2, 45.0, 'ACTIVE'),

    -- Row 4: N16 to N20 (South panel perimeter over extraction voids)
    ('N16', 'Surface Unit N16 (South-West Perimeter)','Surface Sensor Node', 4, 1, -23.55240, 148.17300, 264.9, 45.0, 'ACTIVE'),
    ('N17', 'Surface Unit N17 (Extensometer Borehole 1)','Surface Sensor Node', 4, 2, -23.55240, 148.17400, 262.1, 45.0, 'ACTIVE'),
    ('N18', 'Surface Unit N18 (Extensometer Borehole 2)','Surface Sensor Node', 4, 3, -23.55240, 148.17500, 259.0, 45.0, 'ACTIVE'),
    ('N19', 'Surface Unit N19 (Extensometer Borehole 3)','Surface Sensor Node', 4, 4, -23.55240, 148.17600, 261.9, 45.0, 'ACTIVE'),
    ('N20', 'Surface Unit N20 (South-East Perimeter)','Surface Sensor Node', 4, 5, -23.55240, 148.17700, 265.1, 45.0, 'ACTIVE');

-- ============================================================================
-- SEED DATA: GEOTECHNICAL HAZARD ZONES
-- ============================================================================

INSERT INTO hazard_zones (zone_id, name, risk_level, polygon_geojson, max_subsidence_allowable_mm, current_subsidence_peak_mm, description)
VALUES
    (
        'ZONE-ALPHA',
        'Zone Alpha: Underground Coal Mine Active Extraction Panel',
        'CRITICAL',
        '{"type":"Polygon","coordinates":[[[148.1735,-23.5505],[148.1765,-23.5505],[148.1765,-23.5522],[148.1735,-23.5522],[148.1735,-23.5505]]]}',
        85.0,
        54.8,
        'Directly overlying the active coal extraction chambers and coal carts gallery. Maximum surface sag at Node N13.'
    ),
    (
        'ZONE-BETA',
        'Zone Beta: LoRa Mesh Inter-Node Shear Boundary',
        'HIGH',
        '{"type":"Polygon","coordinates":[[[148.1728,-23.5498],[148.1772,-23.5498],[148.1772,-23.5528],[148.1728,-23.5528],[148.1728,-23.5498]]]}',
        50.0,
        26.4,
        '20-node multi-hop spread-spectrum mesh monitoring buffer.'
    );
