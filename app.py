"""
====================================================================================================
GEO-SHIELD | Mine Subsidence Monitoring & Control Dashboard
High Contrast & Advanced Visuals Edition
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

# --------------------------------------------------------------------------------------------------
# Simulation Constants & Node Network Topology
# --------------------------------------------------------------------------------------------------
BASE_LAT = -23.5512
BASE_LON = 148.1750

NODES_TOPOLOGY = [
    {"node_id": "NODE-01", "name": "North Highwall Sector A", "role": "Edge Inclinometer", "lat": BASE_LAT + 0.0035, "lon": BASE_LON - 0.0028, "base_tilt": 0.42, "base_disp": 1.2, "power_type": "Solar + Li-ion", "battery_pct": 98, "rssi": -68, "snr": 9.4, "hops": 1, "parent": "GW-CENTRAL"},
    {"node_id": "NODE-02", "name": "North Pit Crest Relay", "role": "Cluster Relay Head", "lat": BASE_LAT + 0.0022, "lon": BASE_LON - 0.0010, "base_tilt": 0.58, "base_disp": 2.1, "power_type": "Dual Solar MPPT", "battery_pct": 94, "rssi": -62, "snr": 11.2, "hops": 1, "parent": "GW-CENTRAL"},
    {"node_id": "NODE-03", "name": "Conveyor Bridge Pier 4", "role": "Structural Tilt Node", "lat": BASE_LAT + 0.0011, "lon": BASE_LON + 0.0032, "base_tilt": 0.85, "base_disp": 3.4, "power_type": "Solar + Li-ion", "battery_pct": 89, "rssi": -74, "snr": 7.8, "hops": 1, "parent": "GW-CENTRAL"},
    {"node_id": "NODE-04", "name": "Longwall Panel LW-104 Shear Zone", "role": "Deep Subsidence Sensor", "lat": BASE_LAT - 0.0018, "lon": BASE_LON - 0.0035, "base_tilt": 4.82, "base_disp": 28.5, "power_type": "High-Cap Li-ion", "battery_pct": 73, "rssi": -89, "snr": 3.1, "hops": 2, "parent": "NODE-02"},
    {"node_id": "NODE-05", "name": "Central Pit Floor Sump", "role": "Hydrological Tilt Node", "lat": BASE_LAT - 0.0005, "lon": BASE_LON + 0.0002, "base_tilt": 0.61, "base_disp": 1.8, "power_type": "Solar + Li-ion", "battery_pct": 92, "rssi": -71, "snr": 8.5, "hops": 1, "parent": "GW-CENTRAL"},
    {"node_id": "NODE-06", "name": "East Wall Bench 3", "role": "Slope Stability Sensor", "lat": BASE_LAT + 0.0015, "lon": BASE_LON + 0.0045, "base_tilt": 0.92, "base_disp": 4.1, "power_type": "Solar + Li-ion", "battery_pct": 86, "rssi": -82, "snr": 5.9, "hops": 2, "parent": "NODE-03"},
    {"node_id": "NODE-07", "name": "Tailings Dam Embankment North", "role": "Piezometer / Tilt Node", "lat": BASE_LAT + 0.0048, "lon": BASE_LON + 0.0020, "base_tilt": 0.35, "base_disp": 0.9, "power_type": "Dual Solar MPPT", "battery_pct": 99, "rssi": -76, "snr": 7.2, "hops": 2, "parent": "NODE-02"},
    {"node_id": "NODE-08", "name": "South Fault Line Zone B", "role": "Micro-Seismic & Tilt Node", "lat": BASE_LAT - 0.0039, "lon": BASE_LON - 0.0015, "base_tilt": 2.15, "base_disp": 8.7, "power_type": "High-Cap Li-ion", "battery_pct": 68, "rssi": -94, "snr": 2.3, "hops": 3, "parent": "NODE-04"},
    {"node_id": "NODE-09", "name": "South-West Ventilation Shaft", "role": "Shaft Alignment Node", "lat": BASE_LAT - 0.0031, "lon": BASE_LON + 0.0038, "base_tilt": 0.48, "base_disp": 1.4, "power_type": "Solar + Li-ion", "battery_pct": 91, "rssi": -79, "snr": 6.8, "hops": 2, "parent": "NODE-05"},
    {"node_id": "NODE-10", "name": "Haul Road Crossing Cut", "role": "Edge Inclinometer", "lat": BASE_LAT - 0.0012, "lon": BASE_LON + 0.0052, "base_tilt": 0.74, "base_disp": 2.8, "power_type": "Solar + Li-ion", "battery_pct": 84, "rssi": -85, "snr": 4.7, "hops": 2, "parent": "NODE-03"}
]

GATEWAY_INFO = {
    "gateway_id": "GW-CENTRAL-01", "name": "Central Communication Mast", "lat": BASE_LAT, "lon": BASE_LON,
    "frequency": "915.00 MHz", "tx_power": "20 dBm", "packet_error_rate": "0.08%"
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
            batt_pct = node["battery_pct"]
            
            records.append({
                "timestamp": ts, "node_id": nid, "node_name": node["name"], "role": node["role"],
                "lat": node["lat"], "lon": node["lon"], "tilt_x": round(float(tilt_x), 3),
                "tilt_y": round(float(tilt_y), 3), "tilt_mag": round(float(tilt_mag), 3),
                "displacement_mm": round(float(disp_mm), 2), "disp_rate_mmh": round(max(0.0, float(disp_rate)), 3),
                "vibration_rms": round(max(0.001, float(vibe_rms)), 4), "temperature_c": round(float(temp), 1),
                "battery_v": round(3.8 + np.random.normal(0, 0.1), 2),
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
        if row['tilt_mag'] >= crit_tilt: triggers.append(f"Tilt Limit ({row['tilt_mag']}°)")
        if row['vibration_rms'] >= vibe_limit: triggers.append(f"Vibe Spike ({row['vibration_rms']}g)")
        if row['disp_rate_mmh'] >= 1.5: triggers.append(f"Velocity Limit ({row['disp_rate_mmh']} mm/h)")
        
        if len(triggers) > 0: return " | ".join(triggers)
        elif row['is_anomaly']: return "Multi-variate ML Outlier"
        else: return "Nominal Stability"
    
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

    # High Contrast UI CSS (Fixing faint text issues)
    st.markdown("""
    <style>
        /* Base App Styling - Forcing High Contrast Dark Text on Light Background */
        .stApp { 
            background: #f4f6f9; 
            color: #000000 !important; 
            font-family: 'Inter', 'Segoe UI', sans-serif; 
        }
        
        /* Typography Enforcement */
        h1, h2, h3, h4, h5 { color: #000000 !important; font-weight: 800 !important; letter-spacing: -0.01em; margin-bottom: 12px; }
        p, span, div { color: #111827; }
        
        /* Force Streamlit Labels (Sliders, Selectboxes) to be BOLD and BLACK */
        .stSlider label, .stSelectbox label, .stCheckbox label, div[data-testid="stMarkdownContainer"] p { 
            font-weight: 800 !important; 
            color: #000000 !important; 
            font-size: 1.05rem !important; 
        }
        
        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 2px solid #e2e8f0;
            box-shadow: 4px 0 20px rgba(0, 0, 0, 0.05);
        }
        
        /* High Contrast Floating Cards */
        .glass-card {
            background: #ffffff;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
            border: 1px solid #cbd5e1;
            margin-bottom: 24px;
        }
        
        /* Pill Box KPI Cards (High Legibility) */
        .pill-box {
            display: flex;
            align-items: center;
            background: #ffffff;
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            gap: 16px;
            margin-bottom: 24px;
            border: 2px solid #e2e8f0;
        }
        .icon-circle {
            width: 56px;
            height: 56px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.6rem;
            font-weight: bold;
        }
        
        .icon-blue { background: #dbeafe; color: #1d4ed8; border: 2px solid #93c5fd; }
        .icon-orange { background: #ffedd5; color: #c2410c; border: 2px solid #fdba74; }
        .icon-purple { background: #f3e8ff; color: #7e22ce; border: 2px solid #d8b4fe; }
        .icon-red { background: #fee2e2; color: #b91c1c; border: 2px solid #fca5a5; }
        .icon-green { background: #dcfce7; color: #15803d; border: 2px solid #86efac; }
        
        .pill-data { display: flex; flex-direction: column; }
        .pill-value { font-size: 1.8rem; font-weight: 900; color: #000000 !important; line-height: 1.1; }
        .pill-label { font-size: 0.9rem; font-weight: 800; color: #475569 !important; text-transform: uppercase; margin-top: 4px; }
        
        /* Metric Cards */
        .soft-metric {
            background: #ffffff;
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08);
            border: 2px solid #cbd5e1;
            margin-bottom: 16px;
        }
        .soft-metric-danger { border-left: 6px solid #dc2626; }
        .soft-metric-warning { border-left: 6px solid #d97706; }
        .soft-metric-success { border-left: 6px solid #16a34a; }
        .soft-metric-info { border-left: 6px solid #2563eb; }
        
        .metric-title { color: #1e293b !important; font-size: 0.85rem !important; text-transform: uppercase; font-weight: 800 !important; margin-bottom: 4px; }
        .metric-value { color: #000000 !important; font-size: 1.6rem; font-weight: 900; }
        .metric-sub { color: #334155 !important; font-size: 0.8rem !important; font-weight: 600 !important; margin-top: 4px; }

        /* Badges */
        .status-pill-red { background-color: #fee2e2; color: #b91c1c; padding: 6px 14px; border-radius: 8px; font-weight: 900; font-size: 0.85rem; border: 2px solid #fca5a5;}
        .status-pill-green { background-color: #dcfce7; color: #15803d; padding: 6px 14px; border-radius: 8px; font-weight: 900; font-size: 0.85rem; border: 2px solid #86efac;}
    </style>
    """, unsafe_allow_html=True)

    # Initialize Command Log
    if "c2_command_log" not in st.session_state:
        st.session_state.c2_command_log = [
            {"timestamp": (datetime.now() - timedelta(minutes=45)).strftime("%H:%M:%S"), "target": "NODE-02", "command": "FORCE_CLOUD_SYNC", "hex_payload": "0xAA 0x02 0x1F 0x00", "status": "ACK_RECEIVED", "latency_ms": 285, "details": "Telemetry burst sync completed."},
            {"timestamp": (datetime.now() - timedelta(minutes=20)).strftime("%H:%M:%S"), "target": "NODE-07", "command": "PING_ECHO", "hex_payload": "0xAA 0x07 0x01 0xFF", "status": "ACK_RECEIVED", "latency_ms": 194, "details": "Roundtrip RTT 194ms."}
        ]

    raw_telemetry_df = generate_synthetic_telemetry(hours=24, interval_minutes=10)
    
    # Store AI Params
    if 'ai_contamination' not in st.session_state: st.session_state.ai_contamination = 0.05
    if 'ai_crit_tilt' not in st.session_state: st.session_state.ai_crit_tilt = 3.5
    if 'ai_vibe_limit' not in st.session_state: st.session_state.ai_vibe_limit = 0.25
    if 'ai_risk_filter' not in st.session_state: st.session_state.ai_risk_filter = 70

    analyzed_df, _ = train_and_detect_anomalies(raw_telemetry_df, st.session_state.ai_contamination, st.session_state.ai_crit_tilt, st.session_state.ai_vibe_limit)
    latest_analyzed = analyzed_df[analyzed_df['timestamp'] == analyzed_df['timestamp'].max()].copy()
    
    n_critical = len(latest_analyzed[latest_analyzed['severity'] == 'CRITICAL'])
    n_warning = len(latest_analyzed[latest_analyzed['severity'] == 'WARNING'])
    n_active = len(latest_analyzed)

    # ==============================================================================================
    # SIDEBAR NAVIGATION
    # ==============================================================================================
    with st.sidebar:
        st.markdown("""
            <div style="padding: 10px 0 24px 0;">
                <div style="font-size: 1.6rem; font-weight: 900; color: #000000; display: flex; align-items: center; gap: 12px;">
                    <span style="background: #ffedd5; padding: 10px; border-radius: 8px; border: 2px solid #ea580c; color: #ea580c;">📡</span> GEO-SHIELD
                </div>
            </div>
        """, unsafe_allow_html=True)

        app_mode = st.radio(
            label="Navigation Menu",
            options=["🌍 Live GIS Map", "📈 Telemetry & Visuals", "🧠 AI & 3D Analytics", "⚙️ Node Management"],
            label_visibility="collapsed"
        )
        
        st.markdown("<hr style='border: 1px solid #cbd5e1; margin: 24px 0;'>", unsafe_allow_html=True)
        
        st.markdown("""
            <div style="background: #ffffff; border-radius: 12px; padding: 16px; margin-bottom: 20px; border: 2px solid #94a3b8;">
                <div style="font-size: 0.9rem; color: #000000; font-weight: 800; text-transform: uppercase; margin-bottom: 8px;">Network Status</div>
                <div style="font-size: 1.2rem; color: #000000; font-weight: 900;">10 / 10 ONLINE <span class="status-pill-green" style="float: right;">●</span></div>
            </div>
        """, unsafe_allow_html=True)
        
        if n_critical > 0:
            st.markdown("""
                <div style="background: #fef2f2; border: 2px solid #ef4444; border-radius: 12px; padding: 16px; margin-bottom: 20px;">
                    <div style="font-size: 0.9rem; color: #b91c1c; font-weight: 900; text-transform: uppercase; margin-bottom: 8px;">⚠️ Active Threat</div>
                    <div style="font-size: 1rem; color: #7f1d1d; font-weight: 700; line-height: 1.4;">NODE-04: Shear slip detected on Panel LW-104.</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<span style='font-size: 0.85rem; color: #000000; font-weight: 900; text-transform: uppercase;'>Mesh Polling Frequency</span>", unsafe_allow_html=True)
        st.select_slider("Polling", options=["5 sec", "30 sec", "1 min", "5 min"], value="1 min", label_visibility="collapsed")
        
        st.markdown(f"""
            <div style="text-align: center; color: #475569; font-size: 0.85rem; font-weight: 800; margin-top: 40px;">
                SYSTEM TIME: {datetime.now().strftime('%H:%M • %b %d')}
            </div>
        """, unsafe_allow_html=True)

    # ==============================================================================================
    # MAIN HEADER
    # ==============================================================================================
    st.markdown("""
        <div style="margin-bottom: 32px;">
            <h1 style="margin-bottom: 4px; color: #000000; font-size: 2.2rem; font-weight: 900;">Hello Admin!</h1>
            <p style="color: #334155; font-size: 1.1rem; font-weight: 600;">Monitor live subsidence telemetry, active mesh nodes, and AI-driven warnings.</p>
        </div>
    """, unsafe_allow_html=True)

    # ==============================================================================================
    # MODULE A: LIVE GIS MAP
    # ==============================================================================================
    if app_mode == "🌍 Live GIS Map":
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1: st.markdown(f'<div class="pill-box"><div class="icon-circle icon-blue">📍</div><div class="pill-data"><span class="pill-value">{n_active}</span><span class="pill-label">Total Nodes</span></div></div>', unsafe_allow_html=True)
        with col2: st.markdown(f'<div class="pill-box"><div class="icon-circle icon-red">🚨</div><div class="pill-data"><span class="pill-value">{n_critical}</span><span class="pill-label">Critical</span></div></div>', unsafe_allow_html=True)
        with col3: st.markdown(f'<div class="pill-box"><div class="icon-circle icon-orange">⚠️</div><div class="pill-data"><span class="pill-value">{n_warning}</span><span class="pill-label">Warnings</span></div></div>', unsafe_allow_html=True)
        with col4: st.markdown('<div class="pill-box"><div class="icon-circle icon-purple">📊</div><div class="pill-data"><span class="pill-value">14.4k</span><span class="pill-label">Data Points</span></div></div>', unsafe_allow_html=True)
        with col5: st.markdown('<div class="pill-box"><div class="icon-circle icon-green">🔋</div><div class="pill-data"><span class="pill-value">89%</span><span class="pill-label">Battery Avg</span></div></div>', unsafe_allow_html=True)
            
        st.markdown('<div class="glass-card"><h3>🌍 Spatial Mesh Topology</h3>', unsafe_allow_html=True)
        
        map_ctrl_c1, map_ctrl_c2, map_ctrl_c3 = st.columns([2, 2, 2])
        with map_ctrl_c1: map_tile_choice = st.selectbox("Select Basemap Layer (View Style)", ["CartoDB positron", "OpenStreetMap", "Esri Satellite"], index=0)
        with map_ctrl_c2: show_mesh_links = st.checkbox("🔗 Render Wireless Mesh Links", value=True)
        with map_ctrl_c3: show_hazard_zones = st.checkbox("⚠️ Show Mining Hazard Polygons", value=True)
        
        tiles_layer = "CartoDB positron" if "positron" in map_tile_choice else ("OpenStreetMap" if "OpenStreetMap" in map_tile_choice else "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}")
        m = folium.Map(location=[BASE_LAT, BASE_LON], zoom_start=15, tiles=tiles_layer, attr="Esri World Imagery" if "Satellite" in map_tile_choice else None)

        if show_hazard_zones:
            folium.Polygon(locations=[[BASE_LAT + 0.0055, BASE_LON - 0.0045], [BASE_LAT + 0.0055, BASE_LON + 0.0055], [BASE_LAT - 0.0048, BASE_LON + 0.0060], [BASE_LAT - 0.0048, BASE_LON - 0.0045], [BASE_LAT + 0.0055, BASE_LON - 0.0045]], color="#1d4ed8", weight=2, dash_array="5, 5", fill=True, fill_color="#3b82f6", fill_opacity=0.1, tooltip="Open-Cut Mine Boundary").add_to(m)
            folium.Polygon(locations=[[BASE_LAT - 0.0010, BASE_LON - 0.0042], [BASE_LAT - 0.0010, BASE_LON - 0.0018], [BASE_LAT - 0.0045, BASE_LON - 0.0005], [BASE_LAT - 0.0045, BASE_LON - 0.0042], [BASE_LAT - 0.0010, BASE_LON - 0.0042]], color="#b91c1c", weight=3, fill=True, fill_color="#ef4444", fill_opacity=0.25, tooltip="CRITICAL HAZARD ZONE: Panel LW-104").add_to(m)

        gw_html = f"""<div style="background-color: #1d4ed8; color: #ffffff; padding: 6px 10px; border-radius: 4px; font-size: 12px; font-weight: 800; text-align: center; border: 2px solid white;">📡 <strong>{GATEWAY_INFO['gateway_id']}</strong></div>"""
        folium.Marker(location=[GATEWAY_INFO['lat'], GATEWAY_INFO['lon']], tooltip="GATEWAY (Master Uplink)", icon=folium.DivIcon(html=gw_html, icon_size=(130, 36), icon_anchor=(65, 18))).add_to(m)

        if show_mesh_links:
            node_lookup = {n['node_id']: n for n in NODES_TOPOLOGY}
            node_lookup['GW-CENTRAL'] = {"lat": GATEWAY_INFO['lat'], "lon": GATEWAY_INFO['lon']}
            for node in NODES_TOPOLOGY:
                if node['parent'] in node_lookup:
                    link_color = "#15803d" if node['snr'] > 7.0 else ("#b45309" if node['snr'] > 4.0 else "#b91c1c")
                    folium.PolyLine(locations=[[node['lat'], node['lon']], [node_lookup[node['parent']]['lat'], node_lookup[node['parent']]['lon']]], color=link_color, weight=2.5, opacity=0.8, dash_array="5, 5").add_to(m)

        for _, row in latest_analyzed.iterrows():
            nid = row['node_id']
            status = row['severity']
            bg_color = "#dc2626" if status == "CRITICAL" else ("#ea580c" if status in ["WARNING", "ELEVATED"] else "#16a34a")
            
            node_html = f"""<div style="background-color: {bg_color}; color: white; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 900; border: 3px solid white; box-shadow: 0 4px 8px rgba(0,0,0,0.3);">{nid.split('-')[1]}</div>"""
            popup_html = f"<div style='font-family: Inter, sans-serif; width: 240px; font-size: 14px; color: #000;'><div style='background-color: {bg_color}; color: white; padding: 6px; border-radius: 4px; font-weight: 900; margin-bottom: 6px;'>{nid} • {status}</div><b>Tilt Vector:</b> {row['tilt_mag']}°<br/><b>Displacement:</b> {row['displacement_mm']} mm<br/><b>Vibration:</b> {row['vibration_rms']} g<br/><b>Battery:</b> {row['battery_pct']}%<br/><b>Risk:</b> {row['subsidence_risk_pct']}%</div>"
            folium.Marker(location=[row['lat'], row['lon']], popup=folium.Popup(popup_html, max_width=280), tooltip=f"{nid} • Tilt: {row['tilt_mag']}°", icon=folium.DivIcon(html=node_html, icon_anchor=(14, 14))).add_to(m)
            
        st_folium(m, width="100%", height=500, returned_objects=[])
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="glass-card"><h4>📋 Real-Time Node Status Table</h4>', unsafe_allow_html=True)
        status_table = latest_analyzed[['node_id', 'node_name', 'tilt_mag', 'displacement_mm', 'disp_rate_mmh', 'vibration_rms', 'battery_pct', 'severity']].copy()
        status_table.columns = ['Node ID', 'Location', 'Tilt (°)', 'Disp (mm)', 'Rate (mm/h)', 'Vibe (g)', 'Batt %', 'Status']
        st.dataframe(status_table.style.map(lambda v: 'background-color: #fca5a5; color: #7f1d1d; font-weight: 900;' if v == 'CRITICAL' else ('background-color: #fed7aa; color: #7c2d12; font-weight: 900;' if v in ['WARNING', 'ELEVATED'] else 'background-color: #bbf7d0; color: #14532d; font-weight: bold;'), subset=['Status']), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ==============================================================================================
    # MODULE B: TELEMETRY & VISUALS (Added Radar Chart Graphic)
    # ==============================================================================================
    elif app_mode == "📈 Telemetry & Visuals":
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1: selected_node = st.selectbox("🎯 Target Node Configuration", [n['node_id'] for n in NODES_TOPOLOGY], index=3)
        with c2: time_window = st.selectbox("⏱️ Time Window Span", ["Last 24 Hours", "Last 12 Hours", "Last 6 Hours"])
        with c3: compare_mode = st.multiselect("📊 Overlay Nodes (Compare)", [n['node_id'] for n in NODES_TOPOLOGY if n['node_id'] != selected_node], default=["NODE-02", "NODE-08"])
            
        primary_data = raw_telemetry_df[raw_telemetry_df['node_id'] == selected_node].sort_values('timestamp')
        
        st.markdown("#### 📐 High-Contrast Telemetry Snapshot")
        m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
        
        curr_tilt = primary_data['tilt_mag'].iloc[-1]
        tilt_delta = round(curr_tilt - primary_data['tilt_mag'].iloc[0], 3)
        curr_disp = primary_data['displacement_mm'].iloc[-1]
        disp_delta = round(curr_disp - primary_data['displacement_mm'].iloc[0], 2)
        curr_rate = primary_data['disp_rate_mmh'].iloc[-1]
        curr_vibe = primary_data['vibration_rms'].iloc[-1]
        curr_batt = primary_data['battery_pct'].iloc[-1]

        with m_col1: st.markdown(f'<div class="soft-metric soft-metric-{"danger" if curr_tilt > 3.5 else "info"}"><div class="metric-title">Tilt Magnitude</div><div class="metric-value">{curr_tilt}°</div><div class="metric-sub">Δ 24h: {tilt_delta:+}°</div></div>', unsafe_allow_html=True)
        with m_col2: st.markdown(f'<div class="soft-metric soft-metric-{"danger" if curr_disp > 20 else "warning"}"><div class="metric-title">Displacement</div><div class="metric-value">{curr_disp} mm</div><div class="metric-sub">Δ 24h: {disp_delta:+} mm</div></div>', unsafe_allow_html=True)
        with m_col3: st.markdown(f'<div class="soft-metric soft-metric-{"danger" if curr_rate > 1.5 else "info"}"><div class="metric-title">Subsidence Velocity</div><div class="metric-value">{curr_rate} mm/h</div><div class="metric-sub">State: {"ACCELERATING" if curr_rate > 1.0 else "STEADY"}</div></div>', unsafe_allow_html=True)
        with m_col4: st.markdown(f'<div class="soft-metric soft-metric-{"danger" if curr_vibe > 0.25 else "success"}"><div class="metric-title">Vibration (RMS)</div><div class="metric-value">{curr_vibe:.3f} g</div><div class="metric-sub">Micro-seismic Energy</div></div>', unsafe_allow_html=True)
        with m_col5: st.markdown(f'<div class="soft-metric soft-metric-success"><div class="metric-title">Power Status</div><div class="metric-value">{curr_batt}%</div><div class="metric-sub">Voltage: {primary_data["battery_v"].iloc[-1]}V</div></div>', unsafe_allow_html=True)
        
        st.markdown("---")

        # NEW GRAPHICAL VISUAL: Node Multi-variate Radar Profile
        st.markdown(f"#### 🕸️ Node Health Profile (Radar Graphic) • {selected_node}")
        
        max_vals = raw_telemetry_df[['tilt_mag', 'displacement_mm', 'disp_rate_mmh', 'vibration_rms']].max()
        radar_r = [
            (curr_tilt / max_vals['tilt_mag']) * 100,
            (curr_disp / max_vals['displacement_mm']) * 100,
            (curr_rate / max_vals['disp_rate_mmh']) * 100,
            (curr_vibe / max_vals['vibration_rms']) * 100,
            (primary_data['temperature_c'].iloc[-1] / 40.0) * 100
        ]
        radar_theta = ['Tilt Severity', 'Total Displ.', 'Velocity', 'Vibration', 'Heat Stress']
        
        c_radar, c_tilt = st.columns([1, 2])
        with c_radar:
            fig_radar = go.Figure(data=go.Scatterpolar(r=radar_r + [radar_r[0]], theta=radar_theta + [radar_theta[0]], fill='toself', marker=dict(color='#ea580c'), line=dict(color='#c2410c', width=3)))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor='#cbd5e1'), angularaxis=dict(tickfont=dict(size=13, color="#000", weight="bold"))),
                paper_bgcolor='rgba(0,0,0,0)', height=380, margin=dict(l=40, r=40, t=20, b=20)
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        with c_tilt:
            fig_tilt = go.Figure()
            fig_tilt.add_trace(go.Scatter(x=primary_data['timestamp'], y=primary_data['tilt_mag'], mode='lines', name='Total Vector', line=dict(color='#ea580c', width=4, shape='spline')))
            fig_tilt.add_trace(go.Scatter(x=primary_data['timestamp'], y=primary_data['tilt_x'], mode='lines', name='Tilt X', line=dict(color='#2563eb', width=2, dash='dot')))
            fig_tilt.add_hline(y=3.5, line_dash="dash", line_width=3, line_color="#dc2626", annotation_text="CRITICAL THRESHOLD (3.5°)", annotation_font_color="#dc2626", annotation_font_size=12)
            fig_tilt.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=380, margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1, font=dict(color="#000", size=12)),
                xaxis=dict(showgrid=True, gridcolor="#e2e8f0", title="Time"), yaxis=dict(gridcolor="#cbd5e1", title="Degrees (°)")
            )
            st.plotly_chart(fig_tilt, use_container_width=True)
            
        st.markdown('</div>', unsafe_allow_html=True)
        
        c_vibe, c_rate = st.columns(2)
        with c_vibe:
            st.markdown('<div class="glass-card"><h4>⚡ Dynamic Vibration Tracking (g RMS)</h4>', unsafe_allow_html=True)
            fig_vibe = px.line(primary_data, x="timestamp", y="vibration_rms", color_discrete_sequence=['#7e22ce'])
            fig_vibe.update_traces(line=dict(width=3, shape='spline'), fill='tozeroy', fillcolor='rgba(126, 34, 206, 0.15)')
            fig_vibe.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=0,r=0,t=0,b=0), xaxis=dict(showgrid=True, gridcolor="#e2e8f0"), yaxis=dict(gridcolor="#cbd5e1"))
            st.plotly_chart(fig_vibe, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c_rate:
            st.markdown('<div class="glass-card"><h4>🔄 Overlay Comparison (Displacement mm)</h4>', unsafe_allow_html=True)
            comp_nodes = [selected_node] + compare_mode
            comp_df = raw_telemetry_df[raw_telemetry_df['node_id'].isin(comp_nodes)]
            fig_comp = px.line(comp_df, x="timestamp", y="displacement_mm", color="node_id", color_discrete_sequence=['#dc2626', '#2563eb', '#d97706', '#16a34a'])
            fig_comp.update_traces(line=dict(width=3, shape='spline'))
            fig_comp.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=0,r=0,t=0,b=0), xaxis=dict(showgrid=True, gridcolor="#e2e8f0"), yaxis=dict(gridcolor="#cbd5e1"), legend=dict(orientation="h", y=1.1, title="", font=dict(color="#000")))
            st.plotly_chart(fig_comp, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        csv_bytes = primary_data.to_csv(index=False).encode('utf-8')
        st.download_button(label=f"📥 Download Full Selected Telemetry ({selected_node})", data=csv_bytes, file_name=f"telemetry_{selected_node}.csv", mime="text/csv", type="primary")
        st.markdown('</div>', unsafe_allow_html=True)

    # ==============================================================================================
    # MODULE C: AI ENGINE & 3D ANALYTICS
    # ==============================================================================================
    elif app_mode == "🧠 AI & 3D Analytics":
        
        st.markdown('<div class="glass-card"><h3>⚙️ Machine Learning Tuning (Bold Labels)</h3>', unsafe_allow_html=True)
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1: st.session_state.ai_crit_tilt = st.slider("🚨 Define Critical Tilt Limit (°)", min_value=1.0, max_value=8.0, value=st.session_state.ai_crit_tilt, step=0.1)
        with col_s2: st.session_state.ai_vibe_limit = st.slider("⚡ Set Vibration Spike Limit (g)", min_value=0.05, max_value=0.50, value=st.session_state.ai_vibe_limit, step=0.01)
        with col_s3: st.session_state.ai_contamination = st.slider("🎯 AI Anomaly Sensitivity Range", min_value=0.01, max_value=0.15, value=st.session_state.ai_contamination, step=0.01)
        with col_s4: st.session_state.ai_risk_filter = st.slider("🛡️ Audit Log Display Filter (%)", min_value=50, max_value=95, value=st.session_state.ai_risk_filter, step=5)
        st.markdown('</div>', unsafe_allow_html=True)
        
        anomalies_detected = analyzed_df[analyzed_df['is_anomaly'] | (analyzed_df['severity'] != 'STABLE')]
        max_risk_node = analyzed_df.loc[analyzed_df['subsidence_risk_pct'].idxmax()]
        
        ai_k1, ai_k2, ai_k3, ai_k4 = st.columns(4)
        with ai_k1: st.markdown(f'<div class="soft-metric soft-metric-info"><div class="metric-title">Evaluated Samples Matrix</div><div class="metric-value">{len(analyzed_df):,}</div><div class="metric-sub">10 Nodes × 144 Frames</div></div>', unsafe_allow_html=True)
        with ai_k2: st.markdown(f'<div class="soft-metric soft-metric-danger"><div class="metric-title">Total Flagged Anomalies</div><div class="metric-value">{len(anomalies_detected)}</div><div class="metric-sub">Contamination: {st.session_state.ai_contamination*100:.1f}%</div></div>', unsafe_allow_html=True)
        with ai_k3: st.markdown(f'<div class="soft-metric soft-metric-warning"><div class="metric-title">Highest Risk Asset</div><div class="metric-value">{max_risk_node["node_id"]}</div><div class="metric-sub">Score: {max_risk_node["subsidence_risk_pct"]}%</div></div>', unsafe_allow_html=True)
        with ai_k4: st.markdown(f'<div class="soft-metric soft-metric-success"><div class="metric-title">Model Precision Rate</div><div class="metric-value">98.4%</div><div class="metric-sub">Isolation Forest</div></div>', unsafe_allow_html=True)

        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown('<div class="glass-card"><h4>Overall System Risk Index</h4>', unsafe_allow_html=True)
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=max_risk_node['subsidence_risk_pct'],
                number={'suffix': "%", 'font': {'size': 56, 'color': '#000000', 'weight': 'bold'}},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 2, 'tickcolor': "black"}, 
                    'bar': {'color': "#dc2626" if max_risk_node['subsidence_risk_pct'] > 75 else "#ea580c", 'thickness': 0.8},
                    'bgcolor': "#e2e8f0", 'borderwidth': 2, 'bordercolor': "#cbd5e1",
                    'steps': [{'range': [85, 100], 'color': 'rgba(220, 38, 38, 0.2)'}]
                }
            ))
            fig_gauge.update_layout(paper_bgcolor='rgba(0,0,0,0)', height=380, margin=dict(l=20, r=20, t=20, b=10))
            st.plotly_chart(fig_gauge, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c2:
            # NEW GRAPHICAL VISUAL: 3D Scatter for AI Clustering
            st.markdown('<div class="glass-card"><h4>🌌 3D Anomaly Clustering Matrix</h4>', unsafe_allow_html=True)
            fig_3d = px.scatter_3d(
                analyzed_df, x="tilt_mag", y="displacement_mm", z="vibration_rms", color="severity", 
                size="subsidence_risk_pct", size_max=15, opacity=0.8,
                color_discrete_map={"CRITICAL": "#dc2626", "WARNING": "#ea580c", "ELEVATED": "#7e22ce", "STABLE": "#94a3b8"}
            )
            fig_3d.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', height=380, margin=dict(l=0,r=0,t=0,b=0),
                scene=dict(
                    xaxis_title="Tilt (°)", yaxis_title="Displacement (mm)", zaxis_title="Vibration (g)",
                    xaxis=dict(backgroundcolor="#f8fafc", gridcolor="white", showbackground=True),
                    yaxis=dict(backgroundcolor="#f8fafc", gridcolor="white", showbackground=True),
                    zaxis=dict(backgroundcolor="#f8fafc", gridcolor="white", showbackground=True)
                ),
                legend=dict(title="", font=dict(color="#000", size=14))
            )
            st.plotly_chart(fig_3d, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="glass-card"><h4>📋 Risk Audit Log & AI Mitigations</h4>', unsafe_allow_html=True)
        filtered_anomalies = analyzed_df[(analyzed_df['subsidence_risk_pct'] >= st.session_state.ai_risk_filter) | (analyzed_df['severity'] != 'STABLE')].sort_values('timestamp', ascending=False)
        
        def get_action(sev):
            if sev == "CRITICAL": return "🛑 Evacuate Sector & Deploy Drone"
            elif sev in ["WARNING", "ELEVATED"]: return "⚠️ Increase Polling to 30s"
            return "✅ Standard Active Monitoring"
        filtered_anomalies['Recommended Action'] = filtered_anomalies['severity'].apply(get_action)
        
        audit_disp = filtered_anomalies[['timestamp', 'node_id', 'feature_triggered', 'subsidence_risk_pct', 'severity', 'Recommended Action']]
        audit_disp.columns = ['Timestamp', 'Node ID', 'Triggers', 'Risk Score %', 'Severity', 'Recommended Action']
        
        st.dataframe(audit_disp.style.map(lambda v: 'background-color: #fee2e2; color: #b91c1c; font-weight: 900;' if v == 'CRITICAL' else ('background-color: #ffedd5; color: #c2410c; font-weight: 800;' if v in ['WARNING', 'ELEVATED'] else ''), subset=['Severity']), use_container_width=True, hide_index=True)
        
        report_csv = filtered_anomalies.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download Secure AI Audit Report (CSV)", data=report_csv, file_name="ai_alerts_report.csv", mime="text/csv", type="primary")
        st.markdown('</div>', unsafe_allow_html=True)

    # ==============================================================================================
    # MODULE D: COMMAND & CONTROL
    # ==============================================================================================
    elif app_mode == "⚙️ Node Management":
        
        st.markdown(f"""
            <div class="glass-card" style="padding-bottom: 12px; border: 2px solid #94a3b8;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <div style="font-size: 1.3rem; font-weight: 900; color: #1d4ed8;">📡 Master Gateway: {GATEWAY_INFO['gateway_id']}</div>
                    <span class="status-pill-green">100% ONLINE UPTIME</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; font-size: 1rem; color: #111827; padding-bottom: 16px; font-weight: 600;">
                    <div><span style="color: #64748b; font-size: 0.8rem; display: block; text-transform: uppercase;">Base Name</span> {GATEWAY_INFO['name']}</div>
                    <div><span style="color: #64748b; font-size: 0.8rem; display: block; text-transform: uppercase;">RF Band Protocol</span> {GATEWAY_INFO['frequency']}</div>
                    <div><span style="color: #64748b; font-size: 0.8rem; display: block; text-transform: uppercase;">TX Power Out</span> {GATEWAY_INFO['tx_power']}</div>
                    <div><span style="color: #64748b; font-size: 0.8rem; display: block; text-transform: uppercase;">Mesh Arch</span> LoRaWAN / 6LoWPAN</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("### 🎮 Two-Way Remote Command Dispatcher")
        
        cmd_col1, cmd_col2, cmd_col3 = st.columns([2, 3, 2])
        with cmd_col1: target_node = st.selectbox("🎯 Select Target Node", ["BROADCAST_ALL"] + [n['node_id'] for n in NODES_TOPOLOGY])
        with cmd_col2: cmd_type = st.selectbox("⚡ Execute Action Downlink", ["🔄 Reboot Node Hardware", "☁️ Force Immediate Sync", "📐 Calibrate IMU Baseline", "🚀 High-Frequency Mode"])
        with cmd_col3: 
            st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)
            send_btn = st.button("🚀 Dispatch Secure Payload", type="primary", use_container_width=True)

        if send_btn:
            with st.spinner("Transmitting via Encrypted LoRa Link..."):
                time.sleep(0.6)
                cmd_name = cmd_type.split(" ")[1] if " " in cmd_type else cmd_type
                st.session_state.c2_command_log.insert(0, {
                    "timestamp": datetime.now().strftime("%H:%M:%S"), "target": target_node, 
                    "command": cmd_name.upper(), "hex_payload": "0xAA 0xFF 0x1B", "status": "ACK_RECEIVED (200 OK)",
                    "latency_ms": np.random.randint(180, 360), "details": f"Dispatched via LoRa SF7"
                })
                st.success(f"✅ Secure Packet Acknowledgment Received from {target_node}!")

        st.markdown("#### 📜 Secure Downlink History Log")
        st.dataframe(pd.DataFrame(st.session_state.c2_command_log), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="glass-card"><h4>🎛️ Complete Sensor Hardware Matrix</h4>', unsafe_allow_html=True)
        health_records = [{"Node ID": n['node_id'], "Location Code": n['name'], "Hardware Role": n['role'], "Power System": n['power_type'], "Battery Level": f"{n['battery_pct']}%", "RSSI (dBm)": n['rssi'], "LoRa SNR": n['snr'], "Uplink Target": n['parent'], "Status": "Active"} for n in NODES_TOPOLOGY]
        health_df = pd.DataFrame(health_records)
        st.dataframe(health_df, use_container_width=True, hide_index=True)
        
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            st.markdown("##### 🔋 Battery Charge Distribution (%)")
            fig_batt = px.bar(health_df, x="Node ID", y=[int(x.split("%")[0]) for x in health_df["Battery Level"]], color=[int(x.split("%")[0]) for x in health_df["Battery Level"]], color_continuous_scale="Teal", template="plotly_white")
            fig_batt.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=250, margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#cbd5e1", range=[0,100]))
            st.plotly_chart(fig_batt, use_container_width=True)
        with c_b2:
            st.markdown("##### 📶 LoRa RSSI Signal Heatmap (dBm)")
            fig_rssi = px.bar(health_df, x="Node ID", y="RSSI (dBm)", color="LoRa SNR", color_continuous_scale="Purp", template="plotly_white")
            fig_rssi.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=250, margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#cbd5e1"))
            st.plotly_chart(fig_rssi, use_container_width=True)
            
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()