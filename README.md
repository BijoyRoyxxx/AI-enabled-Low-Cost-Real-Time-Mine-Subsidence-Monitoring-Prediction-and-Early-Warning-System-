# 📡 GEO-SHIELD | Mine Subsidence Monitoring & Control Dashboard

An industrial-grade, interactive central command hub for a wireless LoRa mesh network of geotechnical edge sensor nodes deployed across an active coal mining basin.

---

## 🚀 Key Features & Modules

### 🌍 1. Live GIS Map (Spatial View)
- Interactive spatial mapping using **Folium** and **Streamlit-Folium**.
- Real-time tracking of **10 simulated sensor nodes** distributed across pit walls, conveyor piers, ventilation shafts, and tailings dams.
- Color-coded node status:
  - 🟢 **Green (Stable)**: Nominal baseline movements (< 1.8° tilt).
  - 🟡 **Yellow (Warning)**: Micro-movements and creep along fault lines (`NODE-08`).
  - 🔴 **Red (Critical Anomaly)**: Active shear slip and accelerated subsidence (`NODE-04`).
- Rich hover tooltips & popups displaying Node ID, 2-axis Tilt ($X, Y$, Vector Magnitude), Displacement ($mm$), Vibration ($g$ RMS), Battery %, and RSSI/SNR.
- **LoRa wireless mesh topology links** and active subsidence hazard polygon overlays.

### 📈 2. Telemetry Hub (Real-Time Streams)
- High-fidelity synthetic time-series generation cached with `@st.cache_data` (24h continuous streams).
- Multi-line interactive **Plotly** charts:
  - Multi-Axis Inclinometer Rolling Tilt ($X, Y$, Magnitude in degrees) with dynamic alarm limit reference lines.
  - Cumulative Ground Displacement ($mm$) and Subsidence Velocity ($mm/h$) on dual axes.
  - Dynamic Micro-Seismic Vibration energy ($g$ RMS).
  - Multi-Node Cross-Comparison overlay mode.
- Top KPI metric cards showing instantaneous values, rolling peaks, and 24-hour rate-of-change ($\Delta$).
- One-click Telemetry CSV Data Export.

### 🧠 3. AI Engine & Alerts (Isolation Forest)
- Unsupervised Machine Learning anomaly detection using **Scikit-Learn `IsolationForest`**.
- Multi-feature training matrix: `[tilt_mag, disp_rate_mmh, displacement_mm, vibration_rms, temperature_c]`.
- Calibrated **Subsidence Risk Score Index (0–100%)** with dynamic radial gauge visualization.
- Interactive threshold sliders:
  - *Critical Tilt Threshold (°)*
  - *Vibration Spike Limit (g RMS)*
  - *AI Anomaly Sensitivity / Contamination Rate*
  - *Risk Confidence Filter (%)*
- Anomaly Audit Log table with automatic mitigation recommendations and CSV export.

### ⚙️ 4. Node Management (Command & Control Hub)
- **Central Gateway status**: Frequency (915 MHz), TX power, elevation, bandwidth, and packet loss metrics.
- Complete **10-node hardware & health matrix**: Signal Strength (RSSI dBm), SNR dB, Mesh Hops, Battery Status (Solar MPPT vs Li-ion), Voltage, and Uptime.
- **Two-Way LoRa Downlink Command Dispatcher**:
  - `Reboot Node` (Watchdog Soft Reset)
  - `Force Immediate Cloud Telemetry Sync`
  - `Calibrate IMU Zero-Point Baseline`
  - `Ping Echo / LoRa Roundtrip Check`
  - `Set Ultra-Low Power Sleep vs High-Frequency Burst Modes`
- Live Downlink Command Console logging hex payloads, ACK response times, and roundtrip latencies.

---

## 🛠️ Installation & Execution

### 1. Launch the Dashboard
```bash
streamlit run app.py
```
*Or using Python 3.12 explicitly:*
```powershell
& "C:\Users\broy1\AppData\Local\Programs\Python\Python312\Scripts\streamlit.exe" run app.py
```

### 2. Browser Access
Open your browser and navigate to:
```
http://localhost:8501
```

---

## 🎨 Industrial Control Room Theme
- Custom High-Contrast Industrial Dark SCADA stylesheet (`#0b0f19` charcoal base, cyan telemetry accents, and pulsing LED indicator badges).
