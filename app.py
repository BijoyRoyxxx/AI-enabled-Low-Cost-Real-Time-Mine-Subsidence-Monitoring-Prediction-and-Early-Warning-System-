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
    "gateway_id": "GW-CENTRAL-01",
    "name": "Central Communication Mast",
    "lat": BASE_LAT,
    "lon": BASE_LON,
    "frequency": "915.00 MHz",
    "tx_power": "20 dBm",
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
                "battery_pct": int(batt_pct), "rssi_dbm": node["rssi"] + int(np.random.randint(-2, 3)),
                "snr_db": round(float(node["snr"] + np.random.normal(0, 0.3)), 1), "hops": node["hops"], "parent_relay": node["parent"]
            })

    return pd.DataFrame(records)

# --------------------------------------------------------------------------------------------------
# Machine Learning Engine
# --------------------------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def train_and_detect_anomalies(df: pd.DataFrame):
    features = ['tilt_mag', 'disp_rate_mmh', 'displacement_mm', 'vibration_rms', 'temperature_c']
    X = df[features].copy()
    X_scaled = StandardScaler().fit_transform(X)
    iso_model = IsolationForest(n_estimators=120, contamination=0.05, random_state=42, bootstrap=False)
    preds = iso_model.fit_predict(X_scaled)
    scores = iso_model.decision_function(X_scaled)
    
    df_result = df.copy()
    df_result['is_anomaly'] = (preds == -1)
    norm_risk = 1.0 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-6)
    df_result['subsidence_risk_pct'] = np.clip(np.round(norm_risk * 100, 1), 0, 100)
    
    def assign_severity(row):
        if row['tilt_mag'] >= 3.5 or row['subsidence_risk_pct'] >= 85: return "CRITICAL"
        elif row['vibration_rms'] >= 0.25 or row['subsidence_risk_pct'] >= 65: return "WARNING"
        elif row['is_anomaly']: return "ELEVATED"
        else: return "STABLE"

    df_result['severity'] = df_result.apply(assign_severity, axis=1)
    return df_result, iso_model

# --------------------------------------------------------------------------------------------------
# Main Application
# --------------------------------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="GEO-SHIELD Hub", page_icon="📡", layout="wide", initial_sidebar_state="expanded")

    # Inject Neumorphic / Glass UI CSS
    st.markdown("""
    <style>
        /* Base App Styling */
        .stApp { 
            background: linear-gradient(135deg, #fff5f8 0%, #f4f6fa 50%, #f9f5ff 100%); 
            color: #1e293b; 
            font-family: 'Nunito', 'Segoe UI', Roboto, sans-serif; 
        }
        
        /* Hide Clutter */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: none;
            box-shadow: 4px 0 24px rgba(0,0,0,0.03);
        }
        
        /* Floating Card Styling */
        .glass-card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 24px;
            padding: 24px;
            box-shadow: 0 10px 40px rgba(160, 170, 190, 0.2);
            border: 1px solid rgba(255, 255, 255, 1);
            margin-bottom: 24px;
            backdrop-filter: blur(10px);
        }
        
        h1, h2, h3, h4 { color: #0f172a; font-weight: 700; letter-spacing: -0.02em; }
        
        /* Redesigned Metric Pills */
        .pill-box {
            display: flex;
            align-items: center;
            background: #ffffff;
            border-radius: 20px;
            padding: 16px 20px;
            box-shadow: 0 8px 24px rgba(180, 185, 200, 0.25);
            gap: 16px;
        }
        .icon-circle {
            width: 54px;
            height: 54px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.4rem;
        }
        .icon-blue { background: #e0f2fe; color: #0ea5e9; }
        .icon-orange { background: #ffedd5; color: #f97316; }
        .icon-purple { background: #f3e8ff; color: #a855f7; }
        .icon-red { background: #fee2e2; color: #ef4444; }
        .icon-green { background: #dcfce7; color: #22c55e; }
        
        .pill-data { display: flex; flex-direction: column; }
        .pill-value { font-size: 1.6rem; font-weight: 800; color: #1e293b; line-height: 1.1; }
        .pill-label { font-size: 0.8rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin-top: 4px; }
    </style>
    """, unsafe_allow_html=True)

    raw_telemetry_df = generate_synthetic_telemetry(hours=24, interval_minutes=10)
    analyzed_df, _ = train_and_detect_anomalies(raw_telemetry_df)
    latest_analyzed = analyzed_df[analyzed_df['timestamp'] == analyzed_df['timestamp'].max()].copy()
    
    n_critical = len(latest_analyzed[latest_analyzed['severity'] == 'CRITICAL'])
    n_warning = len(latest_analyzed[latest_analyzed['severity'] == 'WARNING'])

    # Clean Navigation Sidebar
    with st.sidebar:
        st.markdown("""
            <div style="padding: 10px 0 24px 0;">
                <div style="font-size: 1.4rem; font-weight: 800; color: #4f46e5; display: flex; align-items: center; gap: 10px;">
                    <span style="background: #eef2ff; padding: 8px; border-radius: 12px;">📡</span> GEO-SHIELD
                </div>
            </div>
        """, unsafe_allow_html=True)

        app_mode = st.radio(
            label="Navigation",
            options=["🌍 Overview", "📈 Telemetry", "🧠 AI Engine", "⚙️ Hardware"],
            label_visibility="collapsed"
        )
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(f"""
            <div style="text-align: center; color: #94a3b8; font-size: 0.8rem; font-weight: 600;">
                System Time<br>{datetime.now().strftime('%H:%M • %b %d')}
            </div>
        """, unsafe_allow_html=True)

    # Top Header
    st.markdown("""
        <div>
            <h2 style="margin-bottom: 4px; color: #1e293b;">Hello Admin!</h2>
            <p style="color: #64748b; font-size: 0.95rem; font-weight: 500;">Monitor live subsidence telemetry and active mesh nodes.</p>
        </div>
        <br>
    """, unsafe_allow_html=True)

    # ==============================================================================================
    # MODULE: OVERVIEW (GIS MAP & KPIs)
    # ==============================================================================================
    if app_mode == "🌍 Overview":
        
        # Redesigned Top KPI Row
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown("""
                <div class="pill-box">
                    <div class="icon-circle icon-blue">📍</div>
                    <div class="pill-data"><span class="pill-value">10</span><span class="pill-label">Active Nodes</span></div>
                </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
                <div class="pill-box">
                    <div class="icon-circle icon-red">🚨</div>
                    <div class="pill-data"><span class="pill-value">{n_critical}</span><span class="pill-label">Critical</span></div>
                </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
                <div class="pill-box">
                    <div class="icon-circle icon-orange">⚠️</div>
                    <div class="pill-data"><span class="pill-value">{n_warning}</span><span class="pill-label">Warnings</span></div>
                </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown("""
                <div class="pill-box">
                    <div class="icon-circle icon-purple">📊</div>
                    <div class="pill-data"><span class="pill-value">144k</span><span class="pill-label">Data Points</span></div>
                </div>
            """, unsafe_allow_html=True)
        with col5:
            st.markdown("""
                <div class="pill-box">
                    <div class="icon-circle icon-green">🔋</div>
                    <div class="pill-data"><span class="pill-value">89%</span><span class="pill-label">Avg Battery</span></div>
                </div>
            """, unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Map Container
        st.markdown('<div class="glass-card"><h3>🌍 Live Spatial Map</h3>', unsafe_allow_html=True)
        m = folium.Map(location=[BASE_LAT, BASE_LON], zoom_start=15, tiles="CartoDB positron")

        for _, row in latest_analyzed.iterrows():
            nid = row['node_id']
            status = row['severity']
            bg_color = "#ef4444" if status == "CRITICAL" else ("#f97316" if status in ["WARNING", "ELEVATED"] else "#22c55e")
            
            node_html = f"""<div style="background-color: {bg_color}; color: white; border-radius: 50%; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; font-size: 9px; font-weight: bold; border: 2px solid white; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">{nid.split('-')[1]}</div>"""
            
            folium.Marker(
                location=[row['lat'], row['lon']],
                tooltip=f"{nid} • Tilt: {row['tilt_mag']}°",
                icon=folium.DivIcon(html=node_html, icon_anchor=(11, 11))
            ).add_to(m)
            
        st_folium(m, width="100%", height=450, returned_objects=[])
        st.markdown('</div>', unsafe_allow_html=True)

    # ==============================================================================================
    # MODULE: TELEMETRY
    # ==============================================================================================
    elif app_mode == "📈 Telemetry":
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        
        c1, c2 = st.columns([1, 3])
        with c1:
            selected_node = st.selectbox("Select Target Node", [n['node_id'] for n in NODES_TOPOLOGY], index=3)
            
        primary_data = raw_telemetry_df[raw_telemetry_df['node_id'] == selected_node].sort_values('timestamp')
        
        # Clean Plotly Chart Styling
        st.markdown(f"#### Sensor Trends • {selected_node}")
        fig_tilt = go.Figure()
        fig_tilt.add_trace(go.Scatter(
            x=primary_data['timestamp'], y=primary_data['tilt_mag'], mode='lines',
            name='Total Tilt Vector', line=dict(color='#f97316', width=3, shape='spline')
        ))
        fig_tilt.add_trace(go.Scatter(
            x=primary_data['timestamp'], y=primary_data['displacement_mm'], mode='lines',
            name='Displacement (mm)', line=dict(color='#0ea5e9', width=3, shape='spline')
        ))

        fig_tilt.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=20, b=0),
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor="#e2e8f0")
        )
        st.plotly_chart(fig_tilt, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        c_vibe, c_rate = st.columns(2)
        with c_vibe:
            st.markdown('<div class="glass-card"><h4>Vibration Array (g RMS)</h4>', unsafe_allow_html=True)
            fig_vibe = px.line(primary_data, x="timestamp", y="vibration_rms", color_discrete_sequence=['#a855f7'])
            fig_vibe.update_traces(line=dict(width=2, shape='spline'))
            fig_vibe.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=250, margin=dict(l=0,r=0,t=0,b=0), xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#e2e8f0"))
            st.plotly_chart(fig_vibe, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c_rate:
            st.markdown('<div class="glass-card"><h4>Subsidence Rate (mm/h)</h4>', unsafe_allow_html=True)
            fig_rate = px.bar(primary_data, x="timestamp", y="disp_rate_mmh", color_discrete_sequence=['#ef4444'])
            fig_rate.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=250, margin=dict(l=0,r=0,t=0,b=0), xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#e2e8f0"))
            st.plotly_chart(fig_rate, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # ==============================================================================================
    # MODULE: AI ENGINE
    # ==============================================================================================
    elif app_mode == "🧠 AI Engine":
        c1, c2 = st.columns([1, 2])
        
        max_risk_node = analyzed_df.loc[analyzed_df['subsidence_risk_pct'].idxmax()]
        
        with c1:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=max_risk_node['subsidence_risk_pct'],
                title={'text': "Peak Hazard Index", 'font': {'size': 16, 'color': '#64748b'}},
                number={'suffix': "%", 'font': {'size': 40, 'color': '#1e293b', 'weight': 'bold'}},
                gauge={
                    'axis': {'range': [0, 100], 'visible': False},
                    'bar': {'color': "#f97316"},
                    'bgcolor': "#f1f5f9",
                    'borderwidth': 0,
                }
            ))
            fig_gauge.update_layout(paper_bgcolor='rgba(0,0,0,0)', height=280, margin=dict(l=20, r=20, t=30, b=10))
            st.plotly_chart(fig_gauge, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c2:
            st.markdown('<div class="glass-card"><h4>Anomaly Clustering Matrix</h4>', unsafe_allow_html=True)
            fig_scatter = px.scatter(
                analyzed_df, x="tilt_mag", y="vibration_rms", color="severity",
                color_discrete_map={"CRITICAL": "#ef4444", "WARNING": "#f97316", "ELEVATED": "#a855f7", "STABLE": "#e2e8f0"}
            )
            fig_scatter.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=280, margin=dict(l=0,r=0,t=10,b=0), xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#e2e8f0"))
            st.plotly_chart(fig_scatter, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="glass-card"><h4>Risk Audit Log</h4>', unsafe_allow_html=True)
        anomalies = analyzed_df[analyzed_df['severity'] != 'STABLE'].sort_values('timestamp', ascending=False)
        st.dataframe(anomalies[['timestamp', 'node_id', 'feature_triggered', 'subsidence_risk_pct', 'severity']], use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ==============================================================================================
    # MODULE: HARDWARE
    # ==============================================================================================
    elif app_mode == "⚙️ Hardware":
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("### 🎛️ Sensor Network Matrix")
        
        health_records = []
        for node in NODES_TOPOLOGY:
            health_records.append({
                "Node ID": node['node_id'],
                "Location": node['name'],
                "Battery (%)": node['battery_pct'],
                "RSSI (dBm)": node['rssi'],
                "Uplink": node['parent'],
                "Status": "Active"
            })
            
        st.dataframe(pd.DataFrame(health_records), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()