# GEO-SHIELD™ Mine Subsidence Monitoring Dashboard
### Production-Grade Decoupled Geotechnical Telemetry & AI Early Warning System

**Site Deployment Target**: Bowen Basin Longwall Panel 4B (`-23.5512°, 148.1750°`), Central Queensland, Australia.

---
## 🚀 Quick Deploy

**1. Deploy the Backend API & AI Engine:**
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/BijoyRoyxxx/AI-enabled-Low-Cost-Real-Time-Mine-Subsidence-Monitoring-Prediction-and-Early-Warning-System-)

**2. Deploy the React Dashboard:**
[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2FBijoyRoyxxx%2FAI-enabled-Low-Cost-Real-Time-Mine-Subsidence-Monitoring-Prediction-and-Early-Warning-System-)
## 1. Executive Summary & Architecture

The **GEO-SHIELD™** dashboard has been rebuilt from a monolithic Streamlit script into a fully decoupled, production-ready full-stack web application.

### Key Architectural Improvements
1. **Zero Iframe Flickering**:
   - Monolithic Streamlit implementations suffer from full-component teardowns and iframe reloads on every telemetry poll.
   - GEO-SHIELD eliminates this by using **native DOM mutations in Leaflet 1.9.4** (`marker.setStyle({ fillColor, color })`) and **Plotly.js dynamic trace updating** (`Plotly.react`). The map container, satellite tiles, and chart viewports are instantiated once and smoothly mutated in place without visual flashing.
2. **Real-Time Telemetry over WebSockets**:
   - `/ws/telemetry` pushes streaming geotechnical frames every **5 seconds** across all 10 surface and sub-surface sensors.
3. **Integrated Machine Learning**:
   - Multivariate **Isolation Forest** anomaly detector scores ground displacement, subsidence velocity, biaxial tilt, and micro-seismic shock before broadcasting.
4. **Foundation Model Subsidence Forecasting**:
   - **TimesFM 8-Hour Forward Engine** provides predictive displacement horizons with $p_{10}$, $p_{50}$, and $p_{90}$ confidence intervals and time-to-evacuation alerts.
5. **Two-Way Remote Command Dispatch**:
   - Geotechnical engineers can remotely dispatch tare zeroing, sampling frequency changes, inclinometer calibration, and emergency beacons with live audit trails.
6. **High-Contrast Light Theme**:
   - Purpose-built for high-ambient-light mining control rooms (pure whites, slate-900 typography, soft elevation shadows, and pulsating status badges).

---

## 2. Directory & File Structure

```
MINE/
├── schema.sql                 # PostgreSQL DDL, 10-node topology seed, hazard zones
├── run_app.bat                # Windows 1-click launcher for backend + frontend
├── README.md                  # System architecture & operations manual
├── backend/
│   ├── app.py                 # FastAPI backend, WebSocket bus, Isolation Forest, TimesFM
│   └── requirements.txt       # Python dependencies (FastAPI, scikit-learn, Uvicorn, etc.)
├── frontend/
│   ├── index.html             # Clean HTML5 shell with React 18, Leaflet, Plotly CDNs
│   ├── styles.css             # High-contrast Light Theme (WCAG AAA contrast, glass-cards)
│   └── App.js                 # React 18 frontend logic, GIS map, dynamic charts, 2-way UI
└── tests/
    └── test_endpoints.py      # Integration test suite (REST, DB, Static, WebSocket)
```

---

## 3. Database Specification (`schema.sql`)

The database is defined in PostgreSQL DDL and seeds the following components:

### Tables
* **`nodes`**: Stores specifications for 10 mine sensors:
  - `GW-01`: Central LoRaWAN Gateway & Edge Hub (Solar 120W, 12V 100Ah LiFePO4)
  - `NODE-TLT-01`: Longwall Tailgate Crown Inclinometer (Depth 14.5m)
  - `NODE-TLT-02`: Mainheading Pillar Biaxial Inclinometer (Depth 18.0m)
  - `NODE-DSP-01`: Active Trough Multipoint Extensometer Alpha (Depth 45.0m)
  - `NODE-DSP-02`: Highwall Crest Settlement Extensometer Beta (Depth 30.0m)
  - `NODE-VIB-01`: Goaf Collapse Triaxial Geophone 01 (Depth 60.0m)
  - `NODE-VIB-02`: Haul Road Micro-Seismometer 02 (Depth 10.0m)
  - `NODE-PIZ-01`: North Aquifer Vibrating Wire Piezometer (Depth 75.0m)
  - `NODE-PIZ-02`: Interburden Strata Piezometer South (Depth 85.0m)
  - `NODE-ENV-01`: Pit-Rim Ultrasonic Weather Station (Solar 60W, 12V 60Ah)
* **`telemetry_logs`**: High-frequency time-series table storing `tilt_x`, `tilt_y`, `tilt_magnitude`, `displacement_mm`, `subsidence_velocity_mm_hr`, `vibration_g`, `pore_pressure_kpa`, `battery_pct`, `temperature_c`, `anomaly_score`, `is_anomaly`, and `health_status`.
* **`hazard_zones`**: GeoJSON hazard polygon boundaries covering:
  - `ZONE-ALPHA`: Active Goaf Caving Trough (Critical Risk)
  - `ZONE-BETA`: Tailgate Shear & Cleat Relaxation (High Risk)
  - `ZONE-GAMMA`: Highwall Crest Perimeter Buffer (Moderate Risk)
* **`command_audit_logs`**: Audit trail for remote commands dispatched to field nodes.

---

## 4. Backend API (`backend/app.py`)

### Core Services
* **Database Driver Support**: Supports PostgreSQL via standard `DATABASE_URL` (e.g. `postgresql://user:pass@localhost:5432/geoshield`). If PostgreSQL is not configured, it **automatically falls back to a zero-config local SQLite database** (`geoshield.db`) and seeds the exact schema and 10 nodes seamlessly.
* **Isolation Forest ML Pipeline**:
  - Model: `sklearn.ensemble.IsolationForest(n_estimators=120, contamination=0.06)`
  - Evaluates multivariate feature vector: `[tilt_magnitude, displacement, velocity, vibration]`
  - Emits normalized anomaly scores ($0.0 \to 1.0$) and categorizes nodes into `STABLE`, `WARNING`, or `DANGER`.
* **TimesFM Forecasting Engine (`/api/forecast/timesfm`)**:
  - Simulates zero-shot time series foundation model forward inference for 8 hours (16 steps).
  - Computes median displacement trajectory $p_{50}$ alongside $p_{10}$ and $p_{90}$ confidence intervals.
  - Automatically calculates time until breach of the 50mm warning and 85mm evacuation thresholds.
* **WebSocket Bus (`/ws/telemetry`)**:
  - Streams full 10-node JSON telemetry updates every 5 seconds.
  - Simulates physical geotechnical behaviors: longwall face retreat subsidence, diurnal temperature cycles, and periodic micro-seismic fracture events.
* **REST Endpoints**:
  - `GET /health`: Service health and active database driver.
  - `GET /api/nodes`: 10 monitored geotechnical nodes and hardware specs.
  - `GET /api/telemetry/recent`: Recent history buffer for initial chart hydration.
  - `GET /api/forecast/timesfm?node_id=...`: TimesFM 8-hour displacement projection.
  - `GET /api/hazards`: Hazard polygons and mesh connection lines.
  - `POST /api/commands/dispatch`: Dispatch two-way remote commands to field sensors.
  - `GET /api/commands/history`: Fetch recent command audit log.
* **Static File Server**:
  - Automatically mounts `/frontend` at `/` so the dashboard can be run as a single unified service or completely decoupled behind Nginx/Caddy.

---

## 5. Frontend UI & Theme (`index.html`, `styles.css`, `App.js`)

### High-Contrast Light Theme
* **Color Hierarchy**:
  - Surfaces: `#ffffff` (crisp white cards) on `#f8fafc` (slate-50 background).
  - Typography: `#0f172a` (slate-900) primary text and `#334155` (slate-700) body. Contrast ratio exceeds WCAG AAA (7:1+).
  - Borders & Shadows: Subtle slate borders `#e2e8f0` with layered elevation `box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05)`.
* **Status Badges & Pills**:
  - `STABLE`: Green pill (`#f0fdf4`, text `#15803d`, steady green dot).
  - `WARNING`: Amber pill (`#fffbeb`, text `#b45309`, gentle amber pulse).
  - `DANGER`: Red pill (`#fef2f2`, text `#b91c1c`, high-visibility red strobe).

### Navigation & Views
1. **Live GIS Map View**:
   - Leaflet map centered at Bowen Basin coordinates `[-23.5512, 148.1750]`.
   - Hazard polygons with dashed warning borders.
   - LoRaWAN mesh communication links to Central Gateway `GW-01`.
   - **Native Marker Updates**: Circle markers are updated directly in Leaflet memory; no iframe reloads or map flashes.
2. **Telemetry & Visuals View**:
   - Soft-metric cards: Cumulative Displacement, Subsidence Velocity, Tilt Magnitude, Micro-Seismic Peak, and Battery Health.
   - Dynamic multi-trace Plotly charts for Displacement, Biaxial Tilt ($X, Y$), and Vibration Spectrum.
3. **AI & 3D Analytics View**:
   - TimesFM 8-Hour Subsidence Forecast chart with 80% confidence interval band ($p_{10}-p_{90}$) and threshold warning lines.
   - Interactive 3D Plotly Surface depicting the digital elevation model (DEM) and subsidence trough sagging above the longwall void.
4. **Node Management View**:
   - Two-Way Remote Command UI with node dropdown, command presets (`TARE_ZERO`, `SET_SAMPLING_RATE`, `CALIBRATE_INCLINOMETER`, `ENTER_LOW_POWER_SLEEP`, `TRIGGER_EMERGENCY_BEACON`), live JSON payload preview, and audit trail table.

---

## 6. Quickstart & Local Execution

### Option A: 1-Click Launch (Windows)
Double-click `run_app.bat`. This will:
1. Verify Python dependencies.
2. Launch the FastAPI Uvicorn server on `http://localhost:8000`.
3. Open your browser directly to the dashboard.

### Option B: Manual Command Line
From the project root:
```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Run FastAPI Backend
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```
Open **`http://localhost:8000`** in any modern web browser.

### Option C: Using with PostgreSQL
To connect to an external PostgreSQL instance:
```bash
# Set environment variable
export DATABASE_URL="postgresql://username:password@localhost:5432/geoshield"
# (On Windows PowerShell: $env:DATABASE_URL="postgresql://username:password@localhost:5432/geoshield")

# Provision tables
psql -U username -d geoshield -f schema.sql

# Start server
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

---

## 7. Automated Test Suite

To run the automated verification test suite:
```bash
python tests/test_endpoints.py
```
**Verification results include**:
* ✅ `GET /health` operational status
* ✅ `GET /api/nodes` (all 10 nodes seeded and accessible)
* ✅ `GET /api/forecast/timesfm` (16-step 8-hour projection with uncertainty bounds)
* ✅ `GET /api/hazards` (hazard polygons & mesh topology)
* ✅ `POST /api/commands/dispatch` (remote command handling & audit persistence)
* ✅ Static `index.html` frontend serving
* ✅ Real-time `/ws/telemetry` WebSocket streaming verification (5s cadence)
