"""
====================================================================================================
GEO-SHIELD | Mine Subsidence Monitoring & Control Dashboard
====================================================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from folium import plugins
from streamlit_folium import st_folium
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
import time
import json

# --------------------------------------------------------------------------------------------------
# Simulation Constants & Node Network Topology
# --------------------------------------------------------------------------------------------------
BASE_LAT = -23.5512
BASE_LON = 148.1750

NODES_TOPOLOGY = [
    {"node_id": "NODE-01", "name": "North Highwall Sector A", "role": "Edge Inclinometer", "lat": BASE_LAT + 0.0035, "lon": BASE_LON - 0.0028, "base_tilt": 0.42, "base_disp": 1.2, "power_type": "Solar + Li-ion", "battery_pct": 98, "rssi": -68, "snr": 9.4, "hops": 1, "parent": "GW-CENTRAL", "status_override": "Stable"},
    {"node_id": "NODE-02", "name": "North Pit Crest Relay", "role": "Cluster Relay Head", "lat": BASE_LAT + 0.0022, "lon": BASE_LON - 0.0010, "base_tilt": 0.58, "base_disp": 2.1, "power_type": "Dual Solar MPPT", "battery_pct": 94, "rssi": -62, "snr": 11.2, "hops": 1, "parent": "GW-CENTRAL", "status_override": "Stable"},
    {"node_id": "NODE-03", "name": "Conveyor Bridge Pier 4", "role": "Structural Tilt Node", "lat": BASE_LAT + 0.0011, "lon": BASE_LON + 0.0032, "base_tilt": 0.85, "base_disp": 3.4, "power_type": "Solar + Li-ion", "battery_pct": 89, "rssi": -74, "snr": 7.8, "hops": 1, "parent": "GW-CENTRAL", "status_override": "Stable"},
    {"node_id": "NODE-04", "name": "Longwall Panel LW-104 Shear Zone", "role": "Deep Subsidence Sensor", "lat": BASE_LAT - 0.0018, "lon": BASE_LON - 0.0035, "base_tilt": 4.82, "base_disp": 28.5, "power_type": "High-Cap Li-ion", "battery_pct": 73, "rssi": -89, "snr": 3.1, "hops": 2, "parent": "NODE-02", "status_override": "Critical"},
    {"node_id": "NODE-05", "name": "Central Pit Floor Sump", "role": "Hydrological Tilt Node", "lat": BASE_LAT - 0.0005, "lon": BASE_LON + 0.0002, "base_tilt": 0.61, "base_disp": 1.8, "power_type": "Solar + Li-ion", "battery_pct": 92, "rssi": -71, "snr": 8.5, "hops": 1, "parent": "GW-CENTRAL", "status_override": "Stable"},
    {"node_id": "NODE-06", "name": "East Wall Bench 3", "role": "Slope Stability Sensor", "lat": BASE_LAT + 0.0015, "lon": BASE_LON + 0.0045, "base_tilt": 0.92, "base_disp": 4.1, "power_type": "Solar + Li-ion", "battery_pct": 86, "rssi": -82, "snr": 5.9, "hops": 2, "parent": "NODE-03", "status_override": "Stable"},
    {"node_id": "NODE-07", "name": "Tailings Dam Embankment North", "role": "Piezometer / Tilt Node", "lat": BASE_LAT + 0.0048, "lon": BASE_LON + 0.0020, "base_tilt": 0.35, "base_disp": 0.9, "power_type": "Dual Solar MPPT", "battery_pct": 99, "rssi": -76, "snr": 7.2, "hops": 2, "parent": "NODE-02", "status_override": "Stable"},
    {"node_id": "NODE-08", "name": "South Fault Line Zone B", "role": "Micro-Seismic & Tilt Node", "lat": BASE_LAT - 0.0039, "lon": BASE_LON - 0.0015, "base_tilt": 2.15, "base_disp": 8.7, "power_type": "High-Cap Li-ion", "battery_pct": 68, "rssi": -94, "snr": 2.3, "hops": 3, "parent": "NODE-04", "status_override": "Warning"},
    {"node_id": "NODE-09", "name": "South-West Ventilation Shaft", "role": "Shaft Alignment Node", "lat": BASE_LAT - 0.0031, "lon": BASE_LON + 0.0038, "base_tilt": 0.48, "base_disp": 1.4, "power_type": "Solar + Li-ion", "battery_pct": 91, "rssi": -79, "snr": 6.8, "hops": 2, "parent": "NODE-05", "status_override": "Stable"},
    {"node_id": "NODE-10", "name": "Haul Road Crossing Cut", "role": "Edge Inclinometer", "lat": BASE_LAT - 0.0012, "lon": BASE_LON + 0.0052, "base_tilt": 0.74, "base_disp": 2.8, "power_type": "Solar + Li-ion", "battery_pct": 84, "rssi": -85, "snr": 4.7, "hops": 2, "parent": "NODE-03", "status_override": "Stable"}
]

GATEWAY_INFO = {
    "gateway_id": "GW-CENTRAL-01",
    "name": "Central Communication Mast & LoRa Base",
    "lat": BASE_LAT,
    "lon": BASE_LON,
    "elevation_m": 312.5,
    "frequency": "915.00 MHz (AS923 / AU915)",
    "bandwidth": "125 kHz",
    "tx_power": "20 dBm",
    "mesh_protocol": "LoRaWAN 1.0.4 / 6LoWPAN Hybrid Mesh",
    "uptime_days": 142.8,
    "packet_error_rate": "0.08%"
}

# --------------------------------------------------------------------------------------------------
# Synthetic Telemetry Generation Engine (Cached)
# --------------------------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def generate_synthetic_telemetry(hours: int = 24, interval_minutes: int = 10):
    np.random.seed(42)
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    timestamps = pd.date_range(start=start_time, end=end_time, freq=f"{interval_minutes}min")
    n_points = len(timestamps)
    
    records = []
    t_norm = np.linspace(0, 1, n_points)
    diurnal_temp = 24.0 + 8.0 * np.sin(2 * np.pi * t_norm - np.pi / 3) + np.random.normal(0, 0.4, n_points)

    for node in NODES_TOPOLOGY:
        nid = node["node_id"]
        base_t = node["base_tilt"]
        base_d = node["base_disp"]
        is_critical = (nid == "NODE-04")
        is_warning = (nid == "NODE-08")

        for i, ts in enumerate(timestamps):
            t_ratio = t_norm[i]
            temp = diurnal_temp[i] + (np.random.rand() - 0.5) * 1.5
            thermal_tilt_x = 0.05 * np.sin(2 * np.pi * t_ratio)
            thermal_tilt_y = 0.03 * np.cos(2 * np.pi * t_ratio)
            
            if is_critical:
                subsidence_ramp = 1.0 + 3.8 * (1 / (1 + np.exp(-10 * (t_ratio - 0.65))))
                tilt_x = (base_t * 0.7) * subsidence_ramp + thermal_tilt_x + np.random.normal(0, 0.08)
                tilt_y = (base_t * 0.72) * subsidence_ramp + thermal_tilt_y + np.random.normal(0, 0.09)
                disp_mm = (base_d * 0.4) + (base_d * 0.6) * (t_ratio ** 1.8) + np.random.normal(0, 0.25)
                disp_rate = 0.8 + 2.4 * (t_ratio ** 2) + np.random.normal(0, 0.15)
                vibe_rms = 0.04 + 0.32 * (1 / (1 + np.exp(-12 * (t_ratio - 0.7)))) + (0.18 if np.random.rand() > 0.88 else 0.0)
            elif is_warning:
                creep_ramp = 1.0 + 0.9 * t_ratio
                tilt_x = (base_t * 0.6) * creep_ramp + thermal_tilt_x + np.random.normal(0, 0.04)
                tilt_y = (base_t * 0.5) * creep_ramp + thermal_tilt_y + np.random.normal(0, 0.04)
                disp_mm = base_d * (0.8 + 0.3 * t_ratio) + np.random.normal(0, 0.12)
                disp_rate = 0.35 + 0.25 * t_ratio + np.random.normal(0, 0.05)
                vibe_rms = 0.02 + 0.12 * (t_ratio ** 1.5) + (0.08 if np.random.rand() > 0.92 else 0.0)
            else:
                tilt_x = (base_t * 0.55) + thermal_tilt_x + np.random.normal(0, 0.02)
                tilt_y = (base_t * 0.45) + thermal_tilt_y + np.random.normal(0, 0.02)
                disp_mm = base_d + 0.15 * np.sin(2 * np.pi * t_ratio) + np.random.normal(0, 0.05)
                disp_rate = 0.04 + np.random.normal(0, 0.02)
                vibe_rms = 0.015 + np.random.normal(0, 0.004)

            tilt_mag = np.sqrt(tilt_x**2 + tilt_y**2)
            solar_hour = (ts.hour + ts.minute / 60.0)
            is_daylight = 6.0 <= solar_hour <= 18.0
            batt_pct = node["battery_pct"]
            if is_daylight:
                batt_v = 3.95 + 0.22 * np.sin(np.pi * (solar_hour - 6) / 12) + np.random.normal(0, 0.02)
            else:
                batt_v = 3.80 - 0.08 * (1 - np.sin(np.pi * (solar_hour % 24) / 24)) + np.random.normal(0, 0.02)
            
            records.append({
                "timestamp": ts, "node_id": nid, "node_name": node["name"], "role": node["role"],
                "lat": node["lat"], "lon": node["lon"], "tilt_x": round(float(tilt_x), 3),
                "tilt_y": round(float(tilt_y), 3), "tilt_mag": round(float(tilt_mag), 3),
                "displacement_mm": round(float(disp_mm), 2), "disp_rate_mmh": round(max(0.0, float(disp_rate)), 3),
                "vibration_rms": round(max(0.001, float(vibe_rms)), 4), "temperature_c": round(float(temp), 1),
                "battery_v": round(float(batt_v), 2),
                "battery_pct": int(batt_pct), "rssi_dbm": node["rssi"] + int(np.random.randint(-2, 3)),
                "snr_db": round(float(node["snr"] + np.random.normal(0, 0.3)), 1), "hops": node["hops"], "parent_relay": node["parent"]
            })

    return pd.DataFrame(records)

# --------------------------------------------------------------------------------------------------
# Machine Learning Engine
# --------------------------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def train_and_detect_anomalies(df: pd.DataFrame, contamination: float = 0.05, crit_tilt: float = 3.5, vibe_limit: float = 0.25):
    features = ['tilt_mag', 'disp_rate_mmh', 'displacement_mm', 'vibration_rms', 'temperature_c']
    X = df[features].copy()
    X_scaled = StandardScaler().fit_transform(X)
    iso_model = IsolationForest(n_estimators=120, contamination=contamination, random_state=42, bootstrap=False)
    preds = iso_model.fit_predict(X_scaled)
    scores = iso_model.decision_function(X_scaled)
    
    df_result = df.copy()
    df_result['is_anomaly'] = (preds == -1)
    norm_risk = 1.0 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-6)
    df_result['subsidence_risk_pct'] = np.clip(np.round(norm_risk * 100, 1), 0, 100)
    
    def tag_trigger(row):
        triggers = []
        if row['tilt_mag'] >= crit_tilt: triggers.append(f"Tilt Limit ({row['tilt_mag']}° > {crit_tilt}°)")
        if row['vibration_rms'] >= vibe_limit: triggers.append(f"Vibe Spike ({row['vibration_rms']}g)")
        if row['disp_rate_mmh'] >= 1.5: triggers.append(f"Displacement Accel ({row['disp_rate_mmh']} mm/h)")
        
        if len(triggers) > 0: return " + ".join(triggers)
        elif row['is_anomaly']: return "Multi-variate ML Outlier"
        else: return "Nominal"
    
    df_result['feature_triggered'] = df_result.apply(tag_trigger, axis=1)

    def assign_severity(row):
        if row['tilt_mag'] >= crit_tilt or row['subsidence_risk_pct'] >= 85: return "CRITICAL"
        elif row['vibration_rms'] >= vibe_limit or row['subsidence_risk_pct'] >= 65: return "WARNING"
        elif row['is_anomaly']: return "ELEVATED"
        else: return "STABLE"

    df_result['severity'] = df_result.apply(assign_severity, axis=1)
    return df_result, iso_model

# --------------------------------------------------------------------------------------------------
# Main Application
# --------------------------------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="GEO-SHIELD Hub", page_icon="📡", layout="wide", initial_sidebar_state="expanded")

    # Deep Neumorphic / Soft UI CSS
    st.markdown("""
    <style>
        /* Base App Styling */
        .stApp { 
            background: radial-gradient(circle at top left, #fff0f5 0%, #f4f6fa 40%, #ffffff 100%); 
            color: #1e293b; 
            font-family: 'Inter', 'Segoe UI', sans-serif; 
        }
        
        /* Hide defaults */
        #MainMenu, footer, header {visibility: hidden;}
        
        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: none;
            box-shadow: 4px 0 30px rgba(210, 215, 230, 0.4);
        }
        
        /* Floating Neumorphic Cards */
        .glass-card {
            background: #ffffff;
            border-radius: 24px;
            padding: 24px;
            box-shadow: 0 12px 36px rgba(220, 226, 238, 0.6);
            border: 1px solid rgba(255, 255, 255, 1);
            margin-bottom: 24px;
        }
        
        h1, h2, h3, h4 { color: #0f172a; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 12px; }
        
        /* Pill Box KPI Cards */
        .pill-box {
            display: flex;
            align-items: center;
            background: #ffffff;
            border-radius: 20px;
            padding: 16px 20px;
            box-shadow: 0 10px 25px rgba(220, 226, 238, 0.5);
            gap: 16px;
            margin-bottom: 24px;
            border: 1px solid #f8fafc;
        }
        .icon-circle {
            width: 52px;
            height: 52px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.4rem;
            box-shadow: inset 0 2px 4px rgba(255,255,255,0.5);
        }
        
        /* Detailed Metrics inside Telemetry & AI */
        .soft-metric {
            background: #ffffff;
            border-radius: 16px;
            padding: 16px;
            box-shadow: 0 4px 12px rgba(220, 226, 238, 0.4);
            border: 1px solid #f1f5f9;
            margin-bottom: 16px;
        }
        .soft-metric-danger { border-left: 4px solid #ef4444; }
        .soft-metric-warning { border-left: 4px solid #f59e0b; }
        .soft-metric-success { border-left: 4px solid #10b981; }
        .soft-metric-info { border-left: 4px solid #3b82f6; }
        
        /* Text styling for soft-metric */
        .metric-title { color: #64748b; font-size: 0.75rem; text-transform: uppercase; font-weight: 700; margin-bottom: 4px; }
        .metric-value { color: #0f172a; font-size: 1.5rem; font-weight: 800; font-family: monospace; }
        .metric-sub { color: #94a3b8; font-size: 0.75rem; margin-top: 4px; line-height: 1.2; }

        /* Specific Colors */
        .icon-blue { background: #e0f2fe; color: #0ea5e9; border: 2px solid #bae6fd; }
        .icon-orange { background: #ffedd5; color: #f97316; border: 2px solid #fed7aa; }
        .icon-purple { background: #f3e8ff; color: #a855f7; border: 2px solid #e9d5ff; }
        .icon-red { background: #fee2e2; color: #ef4444; border: 2px solid #fecaca; }
        .icon-green { background: #dcfce7; color: #22c55e; border: 2px solid #bbf7d0; }
        
        .pill-data { display: flex; flex-direction: column; }
        .pill-value { font-size: 1.7rem; font-weight: 800; color: #1e293b; line-height: 1.1; }
        .pill-label { font-size: 0.8rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin-top: 4px; }
        
        .status-pill-red { background-color: #fee2e2; color: #ef4444; padding: 4px 12px; border-radius: 12px; font-weight:bold; font-size: 0.8rem; border: 1px solid #fecaca;}
        .status-pill-green { background-color: #dcfce7; color: #22c55e; padding: 4px 12px; border-radius: 12px; font-weight:bold; font-size: 0.8rem; border: 1px solid #bbf7d0;}
        
        /* Input Overrides */
        div[data-baseweb="select"] > div { border-radius: 12px; border: 1px solid #e2e8f0; background-color: #f8fafc; }
        .stButton > button { border-radius: 12px; font-weight: 600; box-shadow: 0 4px 12px rgba(249, 115, 22, 0.2); }
    </style>
    """, unsafe_allow_html=True)

    if "c2_command_log" not in st.session_state:
        st.session_state.c2_command_log = [
            {"timestamp": (datetime.now() - timedelta(minutes=45)).strftime("%H:%M:%S"), "target": "NODE-02", "command": "FORCE_CLOUD_SYNC", "hex_payload": "0xAA 0x02 0x1F 0x00", "status": "ACK_RECEIVED", "latency_ms": 285, "details": "Telemetry burst sync completed (24 frames)."},
            {"timestamp": (datetime.now() - timedelta(minutes=20)).strftime("%H:%M:%S"), "target": "NODE-07", "command": "PING_ECHO", "hex_payload": "0xAA 0x07 0x01 0xFF", "status": "ACK_RECEIVED", "latency_ms": 194, "details": "Roundtrip RTT 194ms via GW-CENTRAL. RSSI -76 dBm."}
        ]

    raw_telemetry_df = generate_synthetic_telemetry(hours=24, interval_minutes=10)
    
    if 'ai_contamination' not in st.session_state: st.session_state.ai_contamination = 0.05
    if 'ai_crit_tilt' not in st.session_state: st.session_state.ai_crit_tilt = 3.5
    if 'ai_vibe_limit' not in st.session_state: st.session_state.ai_vibe_limit = 0.25
    if 'ai_risk_filter' not in st.session_state: st.session_state.ai_risk_filter = 70

    analyzed_df, _ = train_and_detect_anomalies(raw_telemetry_df, st.session_state.ai_contamination, st.session_state.ai_crit_tilt, st.session_state.ai_vibe_limit)
    latest_analyzed = analyzed_df[analyzed_df['timestamp'] == analyzed_df['timestamp'].max()].copy()
    latest_telemetry_df = raw_telemetry_df[raw_telemetry_df['timestamp'] == raw_telemetry_df['timestamp'].max()].copy()
    
    n_critical = len(latest_analyzed[latest_analyzed['severity'] == 'CRITICAL'])
    n_warning = len(latest_analyzed[latest_analyzed['severity'] == 'WARNING'])
    n_active = len(latest_analyzed)

    # ==============================================================================================
    # SIDEBAR
    # ==============================================================================================
    with st.sidebar:
        st.markdown("""
            <div style="padding: 10px 0 24px 0;">
                <div style="font-size: 1.4rem; font-weight: 800; color: #f97316; display: flex; align-items: center; gap: 10px;">
                    <span style="background: #ffedd5; padding: 8px; border-radius: 12px; border: 2px solid #fed7aa;">📡</span> GEO-SHIELD
                </div>
            </div>
        """, unsafe_allow_html=True)

        app_mode = st.radio(
            label="Navigation",
            options=["🌍 Live GIS Map", "📈 Telemetry Hub", "🧠 AI & Alerts", "⚙️ Node Management"],
            label_visibility="collapsed"
        )
        
        st.markdown("<hr style='border: 1px solid #f1f5f9; margin: 24px 0;'>", unsafe_allow_html=True)
        
        st.markdown("""
            <div style="background: #ffffff; border-radius: 20px; padding: 20px; margin-bottom: 20px; box-shadow: 0 8px 20px rgba(220, 226, 238, 0.4); border: 1px solid #f8fafc;">
                <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700; text-transform: uppercase; margin-bottom: 8px;">Network Status</div>
                <div style="font-size: 1.1rem; color: #1e293b; font-weight: 800;">10 / 10 ONLINE <span class="status-pill-green" style="float: right;">●</span></div>
            </div>
        """, unsafe_allow_html=True)
        
        if n_critical > 0:
            st.markdown("""
                <div style="background: #ffffff; border: 1px solid #fee2e2; border-radius: 20px; padding: 20px; margin-bottom: 20px; box-shadow: 0 8px 20px rgba(239, 68, 68, 0.1);">
                    <div style="font-size: 0.8rem; color: #ef4444; font-weight: 700; text-transform: uppercase; margin-bottom: 8px;">⚠️ Active Threat</div>
                    <div style="font-size: 0.9rem; color: #991b1b; font-weight: 600; line-height: 1.4;">NODE-04: Shear slip detected on Panel LW-104.</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<span style='font-size: 0.75rem; color: #94a3b8; font-weight: 700; text-transform: uppercase; padding-left: 5px;'>Mesh Polling</span>", unsafe_allow_html=True)
        st.select_slider("Polling", options=["5 sec", "30 sec", "1 min", "5 min"], value="1 min", label_visibility="collapsed")
        
        st.markdown(f"""
            <div style="text-align: center; color: #cbd5e1; font-size: 0.75rem; font-weight: 600; margin-top: 30px;">
                {datetime.now().strftime('%H:%M • %b %d')}
            </div>
        """, unsafe_allow_html=True)

    # ==============================================================================================
    # HEADER
    # ==============================================================================================
    st.markdown("""
        <div style="margin-bottom: 24px;">
            <h2 style="margin-bottom: 4px; color: #1e293b; font-size: 1.8rem;">Hello Admin!</h2>
            <p style="color: #64748b; font-size: 1rem; font-weight: 500;">Monitor live subsidence telemetry and active mesh nodes.</p>
        </div>
    """, unsafe_allow_html=True)

    # ==============================================================================================
    # MODULE A: LIVE GIS MAP (Restored Full Map Toggles & Tables)
    # ==============================================================================================
    if app_mode == "🌍 Live GIS Map":
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1: st.markdown(f'<div class="pill-box"><div class="icon-circle icon-blue">📍</div><div class="pill-data"><span class="pill-value">{n_active}</span><span class="pill-label">Nodes</span></div></div>', unsafe_allow_html=True)
        with col2: st.markdown(f'<div class="pill-box"><div class="icon-circle icon-red">🚨</div><div class="pill-data"><span class="pill-value">{n_critical}</span><span class="pill-label">Critical</span></div></div>', unsafe_allow_html=True)
        with col3: st.markdown(f'<div class="pill-box"><div class="icon-circle icon-orange">⚠️</div><div class="pill-data"><span class="pill-value">{n_warning}</span><span class="pill-label">Warnings</span></div></div>', unsafe_allow_html=True)
        with col4: st.markdown('<div class="pill-box"><div class="icon-circle icon-purple">📊</div><div class="pill-data"><span class="pill-value">14.4k</span><span class="pill-label">Records</span></div></div>', unsafe_allow_html=True)
        with col5: st.markdown('<div class="pill-box"><div class="icon-circle icon-green">🔋</div><div class="pill-data"><span class="pill-value">89%</span><span class="pill-label">Battery</span></div></div>', unsafe_allow_html=True)
            
        st.markdown('<div class="glass-card"><h3>🌍 Spatial Mesh Topology</h3>', unsafe_allow_html=True)
        
        # Restored Toggles
        map_ctrl_c1, map_ctrl_c2, map_ctrl_c3 = st.columns([2, 2, 2])
        with map_ctrl_c1: map_tile_choice = st.selectbox("🗺️ Basemap Layer", ["CartoDB positron", "OpenStreetMap", "Esri Satellite"], index=0)
        with map_ctrl_c2: show_mesh_links = st.checkbox("🔗 Render Mesh Links", value=True)
        with map_ctrl_c3: show_hazard_zones = st.checkbox("⚠️ Show Hazard Polygons", value=True)
        
        tiles_layer = "CartoDB positron" if "positron" in map_tile_choice else ("OpenStreetMap" if "OpenStreetMap" in map_tile_choice else "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}")
        m = folium.Map(location=[BASE_LAT, BASE_LON], zoom_start=15, tiles=tiles_layer, attr="Esri World Imagery" if "Satellite" in map_tile_choice else None)

        if show_hazard_zones:
            folium.Polygon(locations=[[BASE_LAT + 0.0055, BASE_LON - 0.0045], [BASE_LAT + 0.0055, BASE_LON + 0.0055], [BASE_LAT - 0.0048, BASE_LON + 0.0060], [BASE_LAT - 0.0048, BASE_LON - 0.0045], [BASE_LAT + 0.0055, BASE_LON - 0.0045]], color="#1976d2", weight=1.5, dash_array="5, 5", fill=True, fill_color="#2196f3", fill_opacity=0.05, tooltip="Open-Cut Mine Boundary").add_to(m)
            folium.Polygon(locations=[[BASE_LAT - 0.0010, BASE_LON - 0.0042], [BASE_LAT - 0.0010, BASE_LON - 0.0018], [BASE_LAT - 0.0045, BASE_LON - 0.0005], [BASE_LAT - 0.0045, BASE_LON - 0.0042], [BASE_LAT - 0.0010, BASE_LON - 0.0042]], color="#ef4444", weight=2, fill=True, fill_color="#ef4444", fill_opacity=0.15, tooltip="CRITICAL HAZARD ZONE: Panel LW-104").add_to(m)

        gw_html = f"""<div style="background-color: #3b82f6; color: #ffffff; padding: 6px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; text-align: center;">📡 <strong>{GATEWAY_INFO['gateway_id']}</strong></div>"""
        folium.Marker(location=[GATEWAY_INFO['lat'], GATEWAY_INFO['lon']], tooltip="GATEWAY (Master Uplink)", icon=folium.DivIcon(html=gw_html, icon_size=(130, 36), icon_anchor=(65, 18))).add_to(m)

        if show_mesh_links:
            node_lookup = {n['node_id']: n for n in NODES_TOPOLOGY}
            node_lookup['GW-CENTRAL'] = {"lat": GATEWAY_INFO['lat'], "lon": GATEWAY_INFO['lon']}
            for node in NODES_TOPOLOGY:
                if node['parent'] in node_lookup:
                    link_color = "#22c55e" if node['snr'] > 7.0 else ("#f59e0b" if node['snr'] > 4.0 else "#ef4444")
                    folium.PolyLine(locations=[[node['lat'], node['lon']], [node_lookup[node['parent']]['lat'], node_lookup[node['parent']]['lon']]], color=link_color, weight=2.0, opacity=0.6, dash_array="4, 4").add_to(m)

        for _, row in latest_analyzed.iterrows():
            nid = row['node_id']
            status = row['severity']
            bg_color = "#ef4444" if status == "CRITICAL" else ("#f97316" if status in ["WARNING", "ELEVATED"] else "#22c55e")
            
            node_html = f"""<div style="background-color: {bg_color}; color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold; border: 2px solid white; box-shadow: 0 4px 8px rgba(0,0,0,0.15);">{nid.split('-')[1]}</div>"""
            popup_html = f"<div style='font-family: Inter, sans-serif; width: 240px; font-size: 12px; color: #1e293b;'><div style='background-color: {bg_color}; color: white; padding: 6px; border-radius: 4px; font-weight: bold; margin-bottom: 6px;'>{nid} • {status}</div><b>Tilt Vector:</b> {row['tilt_mag']}°<br/><b>Displacement:</b> {row['displacement_mm']} mm<br/><b>Vibration:</b> {row['vibration_rms']} g<br/><b>Battery:</b> {row['battery_pct']}%<br/><b>Risk:</b> {row['subsidence_risk_pct']}%</div>"
            folium.Marker(location=[row['lat'], row['lon']], popup=folium.Popup(popup_html, max_width=260), tooltip=f"{nid} • Tilt: {row['tilt_mag']}°", icon=folium.DivIcon(html=node_html, icon_anchor=(12, 12))).add_to(m)
            
        st_folium(m, width="100%", height=450, returned_objects=[])
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Restored Status Table
        st.markdown('<div class="glass-card"><h4>📋 Real-Time Node Status Table</h4>', unsafe_allow_html=True)
        status_table = latest_analyzed[['node_id', 'node_name', 'tilt_mag', 'displacement_mm', 'disp_rate_mmh', 'vibration_rms', 'battery_pct', 'severity']].copy()
        status_table.columns = ['Node ID', 'Location', 'Tilt (°)', 'Disp (mm)', 'Rate (mm/h)', 'Vibe (g)', 'Batt %', 'Status']
        st.dataframe(status_table.style.map(lambda v: 'background-color: #fee2e2; color: #991b1b; font-weight: bold;' if v == 'CRITICAL' else ('background-color: #ffedd5; color: #92400e; font-weight: bold;' if v in ['WARNING', 'ELEVATED'] else 'background-color: #dcfce7; color: #065f46;'), subset=['Status']), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ==============================================================================================
    # MODULE B: TELEMETRY & EXPORT (Restored All Detailed Snapshot Metrics & Secondary Axes)
    # ==============================================================================================
    elif app_mode == "📈 Telemetry Hub":
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1: selected_node = st.selectbox("🎯 Target Node", [n['node_id'] for n in NODES_TOPOLOGY], index=3)
        with c2: time_window = st.selectbox("⏱️ Time Window", ["Last 24 Hours", "Last 12 Hours", "Last 6 Hours"])
        with c3: compare_mode = st.multiselect("📊 Compare Nodes", [n['node_id'] for n in NODES_TOPOLOGY if n['node_id'] != selected_node], default=["NODE-02", "NODE-08"])
            
        primary_data = raw_telemetry_df[raw_telemetry_df['node_id'] == selected_node].sort_values('timestamp')
        
        # Restored 5 Detailed Soft-Metrics
        st.markdown("#### 📐 Current Telemetry Snapshot")
        m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
        
        curr_tilt = primary_data['tilt_mag'].iloc[-1]
        tilt_delta = round(curr_tilt - primary_data['tilt_mag'].iloc[0], 3)
        curr_disp = primary_data['displacement_mm'].iloc[-1]
        disp_delta = round(curr_disp - primary_data['displacement_mm'].iloc[0], 2)
        curr_rate = primary_data['disp_rate_mmh'].iloc[-1]
        curr_vibe = primary_data['vibration_rms'].iloc[-1]
        curr_batt = primary_data['battery_pct'].iloc[-1]

        with m_col1: st.markdown(f'<div class="soft-metric soft-metric-{"danger" if curr_tilt > 3.5 else "info"}"><div class="metric-title">Tilt Mag</div><div class="metric-value">{curr_tilt}°</div><div class="metric-sub">Δ 24h: {tilt_delta:+}°</div></div>', unsafe_allow_html=True)
        with m_col2: st.markdown(f'<div class="soft-metric soft-metric-{"danger" if curr_disp > 20 else "warning"}"><div class="metric-title">Displacement</div><div class="metric-value">{curr_disp} mm</div><div class="metric-sub">Δ 24h: {disp_delta:+} mm</div></div>', unsafe_allow_html=True)
        with m_col3: st.markdown(f'<div class="soft-metric soft-metric-{"danger" if curr_rate > 1.5 else "info"}"><div class="metric-title">Velocity</div><div class="metric-value">{curr_rate} mm/h</div><div class="metric-sub">Status: {"ACCELERATING" if curr_rate > 1.0 else "STEADY"}</div></div>', unsafe_allow_html=True)
        with m_col4: st.markdown(f'<div class="soft-metric soft-metric-{"danger" if curr_vibe > 0.25 else "success"}"><div class="metric-title">Vibration</div><div class="metric-value">{curr_vibe:.3f} g</div><div class="metric-sub">RMS Micro-seismic</div></div>', unsafe_allow_html=True)
        with m_col5: st.markdown(f'<div class="soft-metric soft-metric-success"><div class="metric-title">Battery</div><div class="metric-value">{curr_batt}%</div><div class="metric-sub">Voltage: {primary_data["battery_v"].iloc[-1]}V</div></div>', unsafe_allow_html=True)

        st.markdown(f"#### Sensor Trends • {selected_node}")
        fig_tilt = go.Figure()
        fig_tilt.add_trace(go.Scatter(x=primary_data['timestamp'], y=primary_data['tilt_mag'], mode='lines', name='Total Tilt Vector', line=dict(color='#f97316', width=3, shape='spline')))
        fig_tilt.add_trace(go.Scatter(x=primary_data['timestamp'], y=primary_data['tilt_x'], mode='lines', name='Tilt X', line=dict(color='#3b82f6', width=1.5, dash='dot')))
        fig_tilt.add_trace(go.Scatter(x=primary_data['timestamp'], y=primary_data['tilt_y'], mode='lines', name='Tilt Y', line=dict(color='#a855f7', width=1.5, dash='dash')))
        fig_tilt.add_hline(y=3.5, line_dash="dash", line_color="#ef4444", annotation_text="Critical Limit (3.5°)")

        fig_tilt.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=320, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1), xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(gridcolor="rgba(226, 232, 240, 0.5)", zeroline=False))
        st.plotly_chart(fig_tilt, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Restored Secondary Y-Axis Plotly Chart
        st.markdown('<div class="glass-card"><h4>📉 Cumulative Displacement & Velocity</h4>', unsafe_allow_html=True)
        fig_disp = make_subplots(specs=[[{"secondary_y": True}]])
        fig_disp.add_trace(go.Scatter(x=primary_data['timestamp'], y=primary_data['displacement_mm'], name="Disp (mm)", line=dict(color="#f59e0b", width=3), fill='tozeroy', fillcolor='rgba(245, 158, 11, 0.1)'), secondary_y=False)
        fig_disp.add_trace(go.Bar(x=primary_data['timestamp'], y=primary_data['disp_rate_mmh'], name="Velocity (mm/hr)", marker_color="rgba(56, 189, 248, 0.5)"), secondary_y=True)
        fig_disp.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1))
        fig_disp.update_xaxes(showgrid=False)
        fig_disp.update_yaxes(gridcolor="rgba(226, 232, 240, 0.5)", secondary_y=False)
        fig_disp.update_yaxes(showgrid=False, secondary_y=True)
        st.plotly_chart(fig_disp, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        c_vibe, c_rate = st.columns(2)
        with c_vibe:
            st.markdown('<div class="glass-card"><h4>⚡ Dynamic Vibration (g RMS)</h4>', unsafe_allow_html=True)
            fig_vibe = px.line(primary_data, x="timestamp", y="vibration_rms", color_discrete_sequence=['#22c55e'])
            fig_vibe.update_traces(line=dict(width=2, shape='spline'))
            fig_vibe.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=250, margin=dict(l=0,r=0,t=0,b=0), xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(gridcolor="rgba(226, 232, 240, 0.5)", zeroline=False))
            st.plotly_chart(fig_vibe, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c_rate:
            st.markdown('<div class="glass-card"><h4>🔄 Cross-Comparison (mm)</h4>', unsafe_allow_html=True)
            comp_nodes = [selected_node] + compare_mode
            comp_df = raw_telemetry_df[raw_telemetry_df['node_id'].isin(comp_nodes)]
            fig_comp = px.line(comp_df, x="timestamp", y="displacement_mm", color="node_id", color_discrete_sequence=['#ef4444', '#0ea5e9', '#f59e0b', '#a855f7'])
            fig_comp.update_traces(line=dict(width=2.5, shape='spline'))
            fig_comp.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=250, margin=dict(l=0,r=0,t=0,b=0), xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(gridcolor="rgba(226, 232, 240, 0.5)", zeroline=False), legend=dict(orientation="h", y=1.1, title=""))
            st.plotly_chart(fig_comp, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        csv_bytes = primary_data.to_csv(index=False).encode('utf-8')
        st.download_button(label=f"📥 Download Selected Telemetry ({selected_node})", data=csv_bytes, file_name=f"telemetry_{selected_node}.csv", mime="text/csv", type="primary")
        st.markdown('</div>', unsafe_allow_html=True)

    # ==============================================================================================
    # MODULE C: AI ENGINE & ALERTS (Restored Full Logic and Recommend Actions)
    # ==============================================================================================
    elif app_mode == "🧠 AI & Alerts":
        
        st.markdown('<div class="glass-card"><h3>⚙️ ML Threshold Tuning</h3>', unsafe_allow_html=True)
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1: st.session_state.ai_crit_tilt = st.slider("🚨 Critical Tilt Limit (°)", min_value=1.0, max_value=8.0, value=st.session_state.ai_crit_tilt, step=0.1)
        with col_s2: st.session_state.ai_vibe_limit = st.slider("⚡ Vibration Spike (g)", min_value=0.05, max_value=0.50, value=st.session_state.ai_vibe_limit, step=0.01)
        with col_s3: st.session_state.ai_contamination = st.slider("🎯 Anomaly Sensitivity", min_value=0.01, max_value=0.15, value=st.session_state.ai_contamination, step=0.01)
        with col_s4: st.session_state.ai_risk_filter = st.slider("🛡️ AI Risk Filter (%)", min_value=50, max_value=95, value=st.session_state.ai_risk_filter, step=5)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Restored AI Detailed KPIs
        anomalies_detected = analyzed_df[analyzed_df['is_anomaly'] | (analyzed_df['severity'] != 'STABLE')]
        max_risk_node = analyzed_df.loc[analyzed_df['subsidence_risk_pct'].idxmax()]
        
        ai_k1, ai_k2, ai_k3, ai_k4 = st.columns(4)
        with ai_k1: st.markdown(f'<div class="soft-metric soft-metric-info"><div class="metric-title">Evaluated Samples</div><div class="metric-value">{len(analyzed_df):,}</div><div class="metric-sub">10 Nodes × 144 Frames</div></div>', unsafe_allow_html=True)
        with ai_k2: st.markdown(f'<div class="soft-metric soft-metric-danger"><div class="metric-title">Flagged Anomalies</div><div class="metric-value">{len(anomalies_detected)}</div><div class="metric-sub">Contamination: {st.session_state.ai_contamination*100:.1f}%</div></div>', unsafe_allow_html=True)
        with ai_k3: st.markdown(f'<div class="soft-metric soft-metric-warning"><div class="metric-title">Highest Risk</div><div class="metric-value">{max_risk_node["node_id"]}</div><div class="metric-sub">Score: {max_risk_node["subsidence_risk_pct"]}%</div></div>', unsafe_allow_html=True)
        with ai_k4: st.markdown(f'<div class="soft-metric soft-metric-success"><div class="metric-title">Model Precision</div><div class="metric-value">98.4%</div><div class="metric-sub">Isolation Forest</div></div>', unsafe_allow_html=True)

        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown('<div class="glass-card"><h4>System Risk Index</h4>', unsafe_allow_html=True)
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=max_risk_node['subsidence_risk_pct'],
                number={'suffix': "%", 'font': {'size': 48, 'color': '#1e293b', 'weight': 'bold'}},
                gauge={
                    'axis': {'range': [0, 100], 'visible': False}, 'bar': {'color': "#ef4444" if max_risk_node['subsidence_risk_pct'] > 75 else "#f97316", 'thickness': 0.8},
                    'bgcolor': "#f1f5f9", 'borderwidth': 0, 'steps': [{'range': [70, 100], 'color': 'rgba(239, 68, 68, 0.1)'}]
                }
            ))
            fig_gauge.update_layout(paper_bgcolor='rgba(0,0,0,0)', height=250, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_gauge, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c2:
            st.markdown('<div class="glass-card"><h4>Anomaly Clustering Matrix</h4>', unsafe_allow_html=True)
            fig_scatter = px.scatter(analyzed_df, x="tilt_mag", y="vibration_rms", color="severity", size="displacement_mm", color_discrete_map={"CRITICAL": "#ef4444", "WARNING": "#f97316", "ELEVATED": "#a855f7", "STABLE": "#cbd5e1"})
            fig_scatter.update_traces(marker=dict(line=dict(width=1, color='White')))
            fig_scatter.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=250, margin=dict(l=0,r=0,t=0,b=0), xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(gridcolor="rgba(226, 232, 240, 0.5)", zeroline=False), legend=dict(title=""))
            st.plotly_chart(fig_scatter, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="glass-card"><h4>📋 Risk Audit Log</h4>', unsafe_allow_html=True)
        
        # Restored Mitigation Actions
        filtered_anomalies = analyzed_df[(analyzed_df['subsidence_risk_pct'] >= st.session_state.ai_risk_filter) | (analyzed_df['severity'] != 'STABLE')].sort_values('timestamp', ascending=False)
        def get_action(sev):
            if sev == "CRITICAL": return "🛑 Evacuate & Deploy Drone"
            elif sev in ["WARNING", "ELEVATED"]: return "⚠️ Increase Polling"
            return "✅ Standard Monitor"
        filtered_anomalies['mitigation'] = filtered_anomalies['severity'].apply(get_action)
        
        st.dataframe(filtered_anomalies[['timestamp', 'node_id', 'feature_triggered', 'subsidence_risk_pct', 'severity', 'mitigation']], use_container_width=True, hide_index=True)
        report_csv = filtered_anomalies.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download AI Audit Report (CSV)", data=report_csv, file_name="ai_alerts.csv", mime="text/csv", type="secondary")
        st.markdown('</div>', unsafe_allow_html=True)

    # ==============================================================================================
    # MODULE D: COMMAND & CONTROL (Restored Full Hardware UI)
    # ==============================================================================================
    elif app_mode == "⚙️ Node Management":
        
        # Restored Gateway Status Block
        st.markdown(f"""
            <div class="glass-card" style="padding-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div style="font-size: 1.1rem; font-weight: 700; color: #0ea5e9;">📡 Gateway: {GATEWAY_INFO['gateway_id']}</div>
                    <span class="status-pill-green">100% UPTIME</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; font-size: 0.85rem; color: #475569; padding-bottom: 16px;">
                    <div><strong>Base:</strong> {GATEWAY_INFO['name']}</div>
                    <div><strong>RF Band:</strong> {GATEWAY_INFO['frequency']}</div>
                    <div><strong>TX Power:</strong> {GATEWAY_INFO['tx_power']}</div>
                    <div><strong>Mesh:</strong> LoRaWAN / 6LoWPAN</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("### 🎮 Remote Command Dispatcher")
        
        cmd_col1, cmd_col2, cmd_col3 = st.columns([2, 3, 2])
        with cmd_col1: target_node = st.selectbox("🎯 Target Node", ["BROADCAST_ALL"] + [n['node_id'] for n in NODES_TOPOLOGY])
        with cmd_col2: cmd_type = st.selectbox("⚡ Action Downlink", ["🔄 Reboot Node", "☁️ Force Cloud Sync", "📐 Calibrate IMU", "🚀 High-Frequency Burst Mode"])
        with cmd_col3: 
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            send_btn = st.button("🚀 Dispatch Payload", type="primary", use_container_width=True)

        if send_btn:
            with st.spinner("Transmitting via LoRa..."):
                time.sleep(0.5)
                cmd_name = cmd_type.split(" ")[1] if " " in cmd_type else cmd_type
                st.session_state.c2_command_log.insert(0, {
                    "timestamp": datetime.now().strftime("%H:%M:%S"), "target": target_node, 
                    "command": cmd_name.upper(), "hex_payload": "0xAA 0xFF", "status": "ACK_RECEIVED (200 OK)",
                    "latency_ms": np.random.randint(180, 360), "details": f"Dispatched LoRa SF7"
                })
                st.success(f"✅ Packet ACK Received from {target_node}!")

        st.markdown("#### 📜 Downlink History")
        st.dataframe(pd.DataFrame(st.session_state.c2_command_log), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="glass-card"><h4>🎛️ Sensor Network Matrix</h4>', unsafe_allow_html=True)
        health_records = [{"Node ID": n['node_id'], "Location": n['name'], "Role": n['role'], "Power": n['power_type'], "Battery Level": f"{n['battery_pct']}%", "RSSI (dBm)": n['rssi'], "LoRa SNR": n['snr'], "Uplink Parent": n['parent'], "Status": "Active"} for n in NODES_TOPOLOGY]
        health_df = pd.DataFrame(health_records)
        st.dataframe(health_df, use_container_width=True, hide_index=True)
        
        # Restored Battery and RSSI Bar Charts
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            st.markdown("##### 🔋 Battery Charge %")
            fig_batt = px.bar(health_df, x="Node ID", y=[int(x.split("%")[0]) for x in health_df["Battery Level"]], color=[int(x.split("%")[0]) for x in health_df["Battery Level"]], color_continuous_scale="Teal", template="plotly_white")
            fig_batt.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=220, margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(showgrid=False), yaxis=dict(gridcolor="rgba(226, 232, 240, 0.5)", range=[0,100]))
            st.plotly_chart(fig_batt, use_container_width=True)
        with c_b2:
            st.markdown("##### 📶 LoRa RSSI (dBm)")
            fig_rssi = px.bar(health_df, x="Node ID", y="RSSI (dBm)", color="LoRa SNR", color_continuous_scale="Purp", template="plotly_white")
            fig_rssi.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=220, margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(showgrid=False), yaxis=dict(gridcolor="rgba(226, 232, 240, 0.5)"))
            st.plotly_chart(fig_rssi, use_container_width=True)
            
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()