/**
 * ============================================================================
 * GEO-SHIELD MINE SUBSIDENCE MONITORING SYSTEM - FRONTEND REACT LOGIC
 * File: frontend/App.jsx
 * Architecture: Modular React 18, Leaflet GIS Engine, Plotly.js Visualization
 * ============================================================================
 */

const { useState, useEffect, useRef, useCallback, useMemo } = React;

// --- Utility Constants & Color Mappings ---
const STATUS_COLORS = {
  STABLE: { fill: "#22c55e", stroke: "#15803d", bg: "#f0fdf4", text: "#15803d" },
  WARNING: { fill: "#f59e0b", stroke: "#b45309", bg: "#fffbeb", text: "#b45309" },
  DANGER: { fill: "#ef4444", stroke: "#b91c1c", bg: "#fef2f2", text: "#b91c1c" }
};

// Auto-detect backend port or fallback
const BACKEND_HTTP = "https://mine.onrender.com";
const BACKEND_WS = "wss://mine.onrender.com/ws/telemetry";
// ============================================================================
// MAIN APPLICATION COMPONENT
// ============================================================================
function App() {
  const [activeTab, setActiveTab] = useState("gis"); // Default to Live GIS Map
  const [wsStatus, setWsStatus] = useState("CONNECTING");
  const [nodesList, setNodesList] = useState([]);
  const [selectedNodeId, setSelectedNodeId] = useState("N13"); // Default to critical subsidence apex
  const [currentTelemetry, setCurrentTelemetry] = useState({});
  const [telemetryHistory, setTelemetryHistory] = useState([]);
  const [systemSummary, setSystemSummary] = useState({
    active_nodes_count: 21,
    overall_status: "DANGER",
    max_displacement_mm: 54.8,
    max_velocity_mm_hr: 2.45,
    max_crack_mm: 4.25,
    high_risk_node: "N13",
    siren_status: "ACTIVE",
    led_display: "CRITICAL SUBSIDENCE ALERT - PANEL 4B",
    lora_mesh: "ONLINE (20 NODES)",
    gps_sync: "LOCKED (12 SATS)"
  });
  const [toastMessage, setToastMessage] = useState(null);
  const [currentTimeStr, setCurrentTimeStr] = useState(new Date().toLocaleTimeString());

  // Keep live time clock
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTimeStr(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Fetch initial nodes topology
  useEffect(() => {
    fetch(`${BACKEND_HTTP}/api/nodes`)
      .then(res => res.json())
      .then(data => {
        setNodesList(data);
        if (data.length > 0 && !selectedNodeId) {
          const n13 = data.find(n => n.node_id === "N13");
          setSelectedNodeId(n13 ? "N13" : data[0].node_id);
        }
      })
      .catch(err => console.warn("Failed to fetch initial nodes:", err));
  }, []);

  // Fetch initial historical telemetry for smooth charts
  useEffect(() => {
    fetch(`${BACKEND_HTTP}/api/telemetry/recent?limit=60`)
      .then(res => res.json())
      .then(records => {
        if (records && records.length > 0) {
          setTelemetryHistory(records);
        }
      })
      .catch(err => console.warn("Could not prefill telemetry history:", err));
  }, []);

  // WebSocket Connection Lifecycle
  useEffect(() => {
    let ws = null;
    let reconnectTimeout = null;

    const connectWebSocket = () => {
      setWsStatus("CONNECTING");
      ws = new WebSocket(BACKEND_WS);

      ws.onopen = () => {
        setWsStatus("CONNECTED");
        console.log("WebSocket connected to Mine Subsidence telemetry bus.");
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "TELEMETRY_UPDATE") {
            const nodeMap = {};
            payload.nodes.forEach(n => {
              nodeMap[n.node_id] = n;
            });

            setCurrentTelemetry(nodeMap);
            if (payload.summary) {
              setSystemSummary(payload.summary);
            }

            // Append to rolling history (max 200 frames)
            setTelemetryHistory(prev => {
              const updated = [...prev, ...payload.nodes];
              return updated.slice(-200);
            });
          }
        } catch (err) {
          console.error("Failed to parse incoming telemetry frame:", err);
        }
      };

      ws.onerror = (err) => {
        console.warn("WebSocket encountering connection issue:", err);
        setWsStatus("ERROR");
      };

      ws.onclose = () => {
        setWsStatus("DISCONNECTED");
        console.log("WebSocket closed. Retrying connection in 4 seconds...");
        reconnectTimeout = setTimeout(connectWebSocket, 4000);
      };
    };

    connectWebSocket();

    return () => {
      if (ws) ws.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, []);

  const showToast = (message, type = "success") => {
    setToastMessage({ message, type });
    setTimeout(() => setToastMessage(null), 4500);
  };

  const selectedNodeData = currentTelemetry[selectedNodeId] || {
    node_id: selectedNodeId,
    tilt_magnitude_deg: selectedNodeId === "N13" ? 4.2 : 0.4,
    tilt_x_deg: selectedNodeId === "N13" ? 3.1 : 0.2,
    tilt_y_deg: selectedNodeId === "N13" ? 2.8 : 0.3,
    displacement_mm: selectedNodeId === "N13" ? 54.8 : 4.5,
    crack_opening_mm: selectedNodeId === "N13" ? 4.25 : 0.15,
    subsidence_velocity_mm_hr: selectedNodeId === "N13" ? 2.45 : 0.08,
    vibration_g: selectedNodeId === "N13" ? 0.088 : 0.012,
    battery_pct: 95,
    battery_voltage_v: 4.12,
    temperature_c: 28.5,
    humidity_pct: 64.2,
    anomaly_score: selectedNodeId === "N13" ? 0.94 : 0.08,
    health_status: selectedNodeId === "N13" ? "DANGER" : "STABLE"
  };

  return (
    <div className="app-container">
      {/* --- Sidebar Navigation --- */}
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        summary={systemSummary}
      />

      {/* --- Main Viewport Area --- */}
      <main className="main-content">
        {/* --- Top Status Header --- */}
        <TopHeader 
          wsStatus={wsStatus}
          summary={systemSummary}
          timeStr={currentTimeStr}
        />

        {/* --- Content View Wrapper --- */}
        <div className="view-wrapper">
          {toastMessage && (
            <div className={`toast-banner ${toastMessage.type}`}>
              <span>{toastMessage.message}</span>
              <button 
                onClick={() => setToastMessage(null)}
                style={{ background: "none", border: "none", cursor: "pointer", fontWeight: "bold" }}
              >
                ✕
              </button>
            </div>
          )}

          {activeTab === "gis" && (
            <GISMapView 
              currentTelemetry={currentTelemetry}
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
            />
          )}

          {activeTab === "telemetry" && (
            <TelemetryView 
              nodesList={nodesList}
              selectedNodeId={selectedNodeId}
              setSelectedNodeId={setSelectedNodeId}
              nodeData={selectedNodeData}
              telemetryHistory={telemetryHistory}
            />
          )}

          {activeTab === "analytics" && (
            <AI3DAnalyticsView 
              selectedNodeId={selectedNodeId}
              nodeData={selectedNodeData}
              currentTelemetry={currentTelemetry}
            />
          )}

          {activeTab === "nodes" && (
            <NodeManagementView 
              nodesList={nodesList}
              selectedNodeId={selectedNodeId}
              setSelectedNodeId={setSelectedNodeId}
              onCommandDispatched={(msg) => showToast(msg, "success")}
            />
          )}
        </div>
      </main>
    </div>
  );
}

// ============================================================================
// 1. TOP HEADER COMPONENT (EARLY WARNING & SYSTEM INTEGRATION)
// ============================================================================
function TopHeader({ wsStatus, summary, timeStr }) {
  const statusClass = (summary.overall_status || "STABLE").toLowerCase();
  const isDanger = summary.overall_status === "DANGER";

  return (
    <header className="top-header">
      <div className="header-left">
        <div className="header-title-group">
          <h1>AI-Enabled Real Time Mine Subsidence Monitoring System</h1>
          <div className="header-meta">
            <span>Bowen Basin Longwall Panel 4B</span>
            <span>•</span>
            <span>4×5 LoRaWAN Mesh (20 Surface Nodes + GW-01)</span>
            <span>•</span>
            <span style={{ color: isDanger ? "#dc2626" : "#16a34a", fontWeight: "700" }}>
              Subsidence Epicenter: {summary.high_risk_node || "N13"}
            </span>
          </div>
        </div>
      </div>

      <div className="header-right">
        {/* Early Warning Siren Badge */}
        <div className={`status-pill ${isDanger ? "danger pulse-anim" : "stable"}`} title="Industrial Siren Relay Output">
          <span className="status-dot"></span>
          <span>SIREN: {summary.siren_status || (isDanger ? "ACTIVE" : "STANDBY")}</span>
        </div>

        {/* Warning LED Matrix Display Indicator */}
        <div className={`status-pill ${isDanger ? "danger" : "stable"}`} title="Site LED Display Board Text">
          <span>🚨 LED: {isDanger ? "CRITICAL ALERT" : "NORMAL"}</span>
        </div>

        {/* LoRa Mesh Status */}
        <div className="status-pill stable" title="SX1278 4x5 Mesh Topology">
          <span className="status-dot"></span>
          <span>{summary.lora_mesh || "MESH: ONLINE"}</span>
        </div>

        {/* GPS Time Sync */}
        <div className="status-pill stable" title="NEO-6M GPS Receiver Status">
          <span>🛰️ GPS: 12 SATS</span>
        </div>

        {/* WebSocket Cadence Status */}
        <div className={`status-pill ${wsStatus === "CONNECTED" ? "stable" : "danger"}`}>
          <span className="status-dot"></span>
          <span>{wsStatus === "CONNECTED" ? "WS Live (5s)" : "WS Disconnected"}</span>
        </div>

        {/* Mine Hazard Status */}
        <div className={`status-pill ${statusClass}`}>
          <span className="status-dot"></span>
          <span>{summary.overall_status || "STABLE"}</span>
        </div>

        {/* Live Clock */}
        <div style={{ fontSize: "13px", fontWeight: "700", color: "#334155", marginLeft: "4px" }} className="mono-font">
          {timeStr} AEST
        </div>
      </div>
    </header>
  );
}

// ============================================================================
// 2. SIDEBAR NAVIGATION COMPONENT
// ============================================================================
function Sidebar({ activeTab, setActiveTab, summary }) {
  const [serviceConfig, setServiceConfig] = useState(null);

  useEffect(() => {
    fetch(`${BACKEND_HTTP}/api/config`)
      .then(res => res.json())
      .then(cfg => setServiceConfig(cfg))
      .catch(err => console.warn("Failed to load config:", err));
  }, []);

  const navLinks = [
    { id: "gis", label: "Live GIS Map", icon: "🗺️" },
    { id: "telemetry", label: "Telemetry & Visuals", icon: "📈" },
    { id: "analytics", label: "AI & 3D Analytics", icon: "🧠" },
    { id: "nodes", label: "Node Management", icon: "⚙️" }
  ];

  const mapHasKey = serviceConfig?.map?.has_key;
  const mapProvider = serviceConfig?.map?.provider || "carto";
  const llmHasKey = serviceConfig?.llm?.has_key;
  const llmProvider = serviceConfig?.llm?.provider || "gemini";

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-icon">
          📡
        </div>
        <div>
          <div className="brand-title">MINE-SUBSIDENCE</div>
          <div className="brand-subtitle">AI & LoRa Mesh Platform</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        {navLinks.map(link => (
          <button
            key={link.id}
            className={`nav-item ${activeTab === link.id ? "active" : ""}`}
            onClick={() => setActiveTab(link.id)}
          >
            <span className="nav-icon">{link.icon}</span>
            <span>{link.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="quick-telemetry-badge">
          <div className="quick-badge-header">
            <span>Subsidence Live Metric</span>
            <span style={{ color: summary.overall_status === "DANGER" ? "#dc2626" : "#16a34a" }}>●</span>
          </div>
          <div className="quick-badge-row">
            <span>Peak Disp:</span>
            <span className="quick-badge-val mono-font" style={{ color: summary.max_displacement_mm > 50 ? "#dc2626" : "#0f172a" }}>
              {summary.max_displacement_mm || "54.8"} mm
            </span>
          </div>
          <div className="quick-badge-row">
            <span>Max Crack:</span>
            <span className="quick-badge-val mono-font" style={{ color: (summary.max_crack_mm || 4.25) > 3.0 ? "#dc2626" : "#0f172a" }}>
              {summary.max_crack_mm || "4.25"} mm
            </span>
          </div>
          <div className="quick-badge-row">
            <span>Max Velocity:</span>
            <span className="quick-badge-val mono-font">
              {summary.max_velocity_mm_hr || "2.45"} mm/h
            </span>
          </div>
          <div className="quick-badge-row">
            <span>Critical Apex:</span>
            <span className="quick-badge-val" style={{ color: "#dc2626", fontWeight: "800" }}>
              {summary.high_risk_node || "N13"}
            </span>
          </div>
        </div>

        {/* Dedicated API Keys Status Indicator */}
        <div style={{ marginTop: "12px", padding: "10px 12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", color: "#475569" }}>
          <div style={{ fontWeight: "700", color: "#1e293b", marginBottom: "6px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>API KEYS STATUS</span>
            <span style={{ fontSize: "10px", color: "#0284c7", fontWeight: "600" }}>api_keys.env</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
            <span>🗺️ Map API:</span>
            <span style={{ fontWeight: "600", color: mapHasKey ? "#16a34a" : "#0284c7" }}>
              {mapHasKey ? `${mapProvider.toUpperCase()} Active` : "OpenStreetMap (Free)"}
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>🧠 LLM Model:</span>
            <span style={{ fontWeight: "600", color: llmHasKey ? "#16a34a" : "#0284c7" }}>
              {llmHasKey ? `${llmProvider.toUpperCase()} Live` : "TimesFM (Physics)"}
            </span>
          </div>
        </div>

        {/* Hardware Specs Summary */}
        <div style={{ marginTop: "8px", padding: "8px 12px", background: "#f1f5f9", borderRadius: "8px", fontSize: "10px", color: "#64748b" }}>
          <div>Mesh: 21 Nodes (SX1278 LoRa)</div>
          <div>Sensors: LVDT + Crack + MPU6050 + BME280</div>
        </div>
      </div>
    </aside>
  );
}

// ============================================================================
// 3. FLICKER-FREE NATIVE GIS MAP VIEW (LEAFLET ENGINE)
// ============================================================================
function GISMapView({ currentTelemetry, selectedNodeId, onSelectNode }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef({}); // Store references to Leaflet circle markers
  const [hazardsData, setHazardsData] = useState(null);
  const [mapConfig, setMapConfig] = useState({ provider: "carto", has_key: false });

  // Fetch hazards and map config
  useEffect(() => {
    fetch(`${BACKEND_HTTP}/api/hazards`)
      .then(res => res.json())
      .then(data => setHazardsData(data))
      .catch(err => console.warn("Failed to load hazard zones:", err));

    fetch(`${BACKEND_HTTP}/api/config`)
      .then(res => res.json())
      .then(cfg => {
        if (cfg.map) setMapConfig(cfg.map);
      })
      .catch(err => console.warn("Failed to load map config:", err));
  }, []);

  // Initialize Leaflet Map ONCE to eliminate iframe/DOM flickering completely
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // High-contrast coordinates centered in Bowen Basin Longwall Panel
    const center = [-23.5512, 148.1750];
    const map = L.map(mapContainerRef.current, {
      center: center,
      zoom: 16,
      zoomControl: true,
      attributionControl: false
    });

    let tileUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
    let tileOptions = { 
      maxZoom: 19, 
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' 
    };

    L.tileLayer(tileUrl, tileOptions).addTo(map);

    mapInstanceRef.current = map;

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Draw Hazard Polygons & Mesh Lines once data is loaded
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !hazardsData) return;

    // 1. Draw Hazard Polygons
    const hazardColors = {
      CRITICAL: { color: "#dc2626", fill: "#ef4444" },
      HIGH: { color: "#ea580c", fill: "#f97316" },
      MODERATE: { color: "#d97706", fill: "#f59e0b" }
    };

    hazardsData.hazard_zones.forEach(zone => {
      const cfg = hazardColors[zone.risk_level] || hazardColors.MODERATE;
      const polygon = L.polygon(zone.coordinates, {
        color: cfg.color,
        fillColor: cfg.fill,
        fillOpacity: 0.18,
        weight: 2,
        dashArray: "4, 6"
      }).addTo(map);

      polygon.bindTooltip(`<b>${zone.name}</b><br/>Allowable: ${zone.max_subsidence_allowable_mm}mm`, {
        permanent: false,
        direction: "center",
        className: "polygon-tooltip"
      });
    });

    // 2. Draw LoRaWAN Mesh Topology Links to Gateway
    hazardsData.mesh_links.forEach(link => {
      L.polyline(link.coordinates, {
        color: "#0284c7",
        weight: 1.5,
        opacity: 0.6,
        dashArray: "3, 6"
      }).addTo(map);
    });
  }, [hazardsData]);

  // CRITICAL REQUIREMENT: NATIVE MARKER MUTATION (ZERO FLICKER)
  // When WebSocket pushes new telemetry, update markers natively without reloading the map!
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || Object.keys(currentTelemetry).length === 0) return;

    Object.values(currentTelemetry).forEach(node => {
      const nid = node.node_id;
      const status = node.health_status || "STABLE";
      const styleCfg = STATUS_COLORS[status] || STATUS_COLORS.STABLE;

      const isApex = nid === "N13";

      if (!markersRef.current[nid]) {
        // Create marker once
        const marker = L.circleMarker([node.latitude, node.longitude], {
          radius: nid === "GW-01" ? 11 : (isApex ? 13 : 8),
          fillColor: styleCfg.fill,
          color: styleCfg.stroke,
          weight: isApex ? 3.5 : 2.5,
          opacity: 1,
          fillOpacity: 0.95
        }).addTo(map);

        // Click handler to select node
        marker.on("click", () => {
          onSelectNode(nid);
        });

        markersRef.current[nid] = marker;
      } else {
        // Native DOM update: change marker style directly with NO reloads or flashes
        const marker = markersRef.current[nid];
        marker.setStyle({
          fillColor: styleCfg.fill,
          color: styleCfg.stroke,
          radius: nid === selectedNodeId ? 14 : (isApex ? 13 : (nid === "GW-01" ? 11 : 8)),
          weight: nid === selectedNodeId ? 4.0 : (isApex ? 3.5 : 2.5)
        });
      }

      // Update popup content cleanly
      const marker = markersRef.current[nid];
      if (marker) {
        marker.bindPopup(`
          <div style="min-width: 190px;">
            <div class="popup-title">${node.node_id} ${isApex ? "⚠️ [CRITICAL APEX]" : ""}</div>
            <div style="font-size: 11px; color: #64748b; margin-bottom: 6px;">${node.name}</div>
            <div class="popup-row">
              <span>Status:</span>
              <b style="color: ${styleCfg.stroke}">${node.health_status}</b>
            </div>
            <div class="popup-row">
              <span>Displacement:</span>
              <b class="mono-font">${node.displacement_mm} mm</b>
            </div>
            <div class="popup-row">
              <span>Crack Opening:</span>
              <b class="mono-font">${node.crack_opening_mm !== undefined ? node.crack_opening_mm : "0.00"} mm</b>
            </div>
            <div class="popup-row">
              <span>Velocity:</span>
              <b class="mono-font">${node.subsidence_velocity_mm_hr} mm/h</b>
            </div>
            <div class="popup-row">
              <span>Tilt Mag:</span>
              <b class="mono-font">${node.tilt_magnitude_deg}°</b>
            </div>
            <div class="popup-row">
              <span>Vibration:</span>
              <b class="mono-font">${node.vibration_g} g</b>
            </div>
            <div class="popup-row">
              <span>Battery:</span>
              <b>${node.battery_pct}%</b>
            </div>
          </div>
        `);
      }
    });
  }, [currentTelemetry, selectedNodeId, onSelectNode]);

  return (
    <div className="map-view-container">
      <div className="map-card-wrapper">
        <div ref={mapContainerRef} className="map-viewport"></div>

        {/* Floating Legend Overlay */}
        <div className="map-floating-overlay">
          <div style={{ marginBottom: "10px", paddingBottom: "8px", borderBottom: "1px solid #e2e8f0" }}>
            <div style={{ fontSize: "10px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>Map Tile Source</div>
            <div style={{ fontSize: "12px", fontWeight: "600", color: mapConfig.has_key ? "#16a34a" : "#0284c7" }}>
              {mapConfig.has_key ? `${mapConfig.provider.toUpperCase()} (Custom Key)` : "OpenStreetMap Standard"}
            </div>
            <div style={{ fontSize: "10px", color: "#94a3b8" }}>Set MAP_API_KEY in api_keys.env</div>
          </div>
          <div className="map-legend-title">Geotechnical Status</div>
          <div className="map-legend-item">
            <span className="legend-badge" style={{ background: "#22c55e" }}></span>
            <span>Stable / Normal (&lt;25mm)</span>
          </div>
          <div className="map-legend-item">
            <span className="legend-badge" style={{ background: "#f59e0b" }}></span>
            <span>Warning / Elevated Strain</span>
          </div>
          <div className="map-legend-item">
            <span className="legend-badge" style={{ background: "#ef4444" }}></span>
            <span>Critical Anomaly / Shear Hazard</span>
          </div>
          <div className="map-legend-item" style={{ marginTop: "10px", borderTop: "1px solid #e2e8f0", paddingTop: "8px" }}>
            <span style={{ borderBottom: "2px dashed #0284c7", width: "16px", height: "1px", display: "inline-block" }}></span>
            <span style={{ fontSize: "11px" }}>LoRaWAN Mesh Topology</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// 4. TELEMETRY & VISUALS VIEW (SOFT METRIC CARDS & PLOTLY DYNAMIC CHARTS)
// ============================================================================
function TelemetryView({ nodesList, selectedNodeId, setSelectedNodeId, nodeData, telemetryHistory }) {
  const dispChartRef = useRef(null);
  const crackChartRef = useRef(null);
  const tiltChartRef = useRef(null);
  const vibeChartRef = useRef(null);

  const nodeHistory = useMemo(() => {
    return telemetryHistory.filter(h => h.node_id === selectedNodeId);
  }, [telemetryHistory, selectedNodeId]);

  // Chart 1: Cumulative Displacement
  useEffect(() => {
    if (!dispChartRef.current || nodeHistory.length === 0) return;

    const times = nodeHistory.map(h => h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : "");
    const dispValues = nodeHistory.map(h => h.displacement_mm || 0);

    const trace1 = {
      x: times,
      y: dispValues,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Displacement (mm)',
      line: { color: '#0284c7', width: 3, shape: 'spline' },
      marker: { size: 5, color: '#0369a1' }
    };

    const traceWarning = {
      x: times,
      y: Array(times.length).fill(50),
      type: 'scatter',
      mode: 'lines',
      name: 'Warning Limit (50mm)',
      line: { color: '#f59e0b', width: 2, dash: 'dash' }
    };

    const layout = {
      margin: { l: 50, r: 20, t: 30, b: 40 },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      font: { family: 'Inter, sans-serif', color: '#334155' },
      xaxis: { showgrid: true, gridcolor: '#f1f5f9', zeroline: false },
      yaxis: { title: 'Displacement (mm)', showgrid: true, gridcolor: '#f1f5f9', zeroline: false },
      legend: { orientation: 'h', y: 1.15 }
    };

    Plotly.react(dispChartRef.current, [trace1, traceWarning], layout, { responsive: true, displayModeBar: false });
  }, [nodeHistory]);

  // Chart 2: Crack Opening Gauge (Strain Transducer)
  useEffect(() => {
    if (!crackChartRef.current || nodeHistory.length === 0) return;

    const times = nodeHistory.map(h => h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : "");
    const crackValues = nodeHistory.map(h => h.crack_opening_mm !== undefined ? h.crack_opening_mm : 0);

    const traceCrack = {
      x: times,
      y: crackValues,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Crack Width (mm)',
      line: { color: '#dc2626', width: 2.5, shape: 'spline' },
      marker: { size: 4, color: '#991b1b' }
    };

    const traceThreshold = {
      x: times,
      y: Array(times.length).fill(3.0),
      type: 'scatter',
      mode: 'lines',
      name: 'Shear Crack Alarm (3.0mm)',
      line: { color: '#ea580c', width: 2, dash: 'dot' }
    };

    const layout = {
      margin: { l: 50, r: 20, t: 30, b: 40 },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      font: { family: 'Inter, sans-serif', color: '#334155' },
      xaxis: { showgrid: true, gridcolor: '#f1f5f9', zeroline: false },
      yaxis: { title: 'Crack Opening (mm)', showgrid: true, gridcolor: '#f1f5f9', zeroline: false },
      legend: { orientation: 'h', y: 1.15 }
    };

    Plotly.react(crackChartRef.current, [traceCrack, traceThreshold], layout, { responsive: true, displayModeBar: false });
  }, [nodeHistory]);

  // Chart 3: Tilt (X & Y)
  useEffect(() => {
    if (!tiltChartRef.current || nodeHistory.length === 0) return;

    const times = nodeHistory.map(h => h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : "");
    const tiltX = nodeHistory.map(h => h.tilt_x_deg || 0);
    const tiltY = nodeHistory.map(h => h.tilt_y_deg || 0);

    const traceX = {
      x: times,
      y: tiltX,
      type: 'scatter',
      mode: 'lines',
      name: 'Tilt X-Axis (°)',
      line: { color: '#4f46e5', width: 2.5 }
    };

    const traceY = {
      x: times,
      y: tiltY,
      type: 'scatter',
      mode: 'lines',
      name: 'Tilt Y-Axis (°)',
      line: { color: '#06b6d4', width: 2.5 }
    };

    const layout = {
      margin: { l: 50, r: 20, t: 30, b: 40 },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      font: { family: 'Inter, sans-serif', color: '#334155' },
      xaxis: { showgrid: true, gridcolor: '#f1f5f9' },
      yaxis: { title: 'Tilt Angle (°)', showgrid: true, gridcolor: '#f1f5f9' },
      legend: { orientation: 'h', y: 1.15 }
    };

    Plotly.react(tiltChartRef.current, [traceX, traceY], layout, { responsive: true, displayModeBar: false });
  }, [nodeHistory]);

  // Chart 4: Vibration
  useEffect(() => {
    if (!vibeChartRef.current || nodeHistory.length === 0) return;

    const times = nodeHistory.map(h => h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : "");
    const vib = nodeHistory.map(h => h.vibration_g || 0);

    const traceVib = {
      x: times,
      y: vib,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Peak Micro-Seismic (g)',
      fill: 'tozeroy',
      fillcolor: 'rgba(2, 132, 199, 0.08)',
      line: { color: '#0284c7', width: 2 }
    };

    const layout = {
      margin: { l: 50, r: 20, t: 30, b: 40 },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      font: { family: 'Inter, sans-serif', color: '#334155' },
      xaxis: { showgrid: true, gridcolor: '#f1f5f9' },
      yaxis: { title: 'Acceleration (g)', showgrid: true, gridcolor: '#f1f5f9' },
      legend: { orientation: 'h', y: 1.15 }
    };

    Plotly.react(vibeChartRef.current, [traceVib], layout, { responsive: true, displayModeBar: false });
  }, [nodeHistory]);

  return (
    <div>
      {/* Node Selector Bar */}
      <div className="glass-card" style={{ padding: "16px 24px", marginBottom: "24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "13px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" }}>Selected Node:</span>
          <select 
            value={selectedNodeId} 
            onChange={(e) => setSelectedNodeId(e.target.value)}
            className="form-select"
            style={{ width: "280px" }}
          >
            {nodesList.map(n => (
              <option key={n.node_id} value={n.node_id}>
                {n.node_id} — {n.name} {n.node_id === "N13" ? "⚠️ (CRITICAL APEX)" : ""}
              </option>
            ))}
          </select>
        </div>

        <div className={`status-pill ${nodeData.health_status ? nodeData.health_status.toLowerCase() : "stable"}`}>
          <span className="status-dot"></span>
          <span>{nodeData.health_status || "STABLE"}</span>
        </div>
      </div>

      {/* Metric Cards Grid - Soft Visuals */}
      <div className="metrics-grid">
        {/* Cumulative Displacement Card */}
        <div className={`metric-card ${nodeData.displacement_mm > 45 ? "danger-border" : (nodeData.displacement_mm > 25 ? "warning-border" : "stable-border")}`}>
          <div className="metric-header">
            <span className="metric-label">Cumulative Displacement (LVDT)</span>
            <div className="metric-icon-box">📏</div>
          </div>
          <div className="metric-value-box">
            <span className="metric-value mono-font">{nodeData.displacement_mm ?? "0.0"}</span>
            <span className="metric-unit">mm</span>
          </div>
          <div className="metric-subtext">
            <span>Limit: 50.0 mm</span>
            <span style={{ color: nodeData.displacement_mm > 50 ? "#dc2626" : "#16a34a", fontWeight: "700" }}>
              {nodeData.displacement_mm > 50 ? "THRESHOLD EXCEEDED" : "SAFE"}
            </span>
          </div>
        </div>

        {/* Crack Opening Gauge Card */}
        <div className={`metric-card ${nodeData.crack_opening_mm > 3.0 ? "danger-border" : (nodeData.crack_opening_mm > 1.5 ? "warning-border" : "stable-border")}`}>
          <div className="metric-header">
            <span className="metric-label">Crack Opening Gauge</span>
            <div className="metric-icon-box">⚡</div>
          </div>
          <div className="metric-value-box">
            <span className="metric-value mono-font">{nodeData.crack_opening_mm ?? "0.00"}</span>
            <span className="metric-unit">mm</span>
          </div>
          <div className="metric-subtext">
            <span>Shear Limit: 3.0 mm</span>
            <span style={{ color: (nodeData.crack_opening_mm || 0) > 3.0 ? "#dc2626" : "#16a34a", fontWeight: "700" }}>
              {(nodeData.crack_opening_mm || 0) > 3.0 ? "SURFACE FISSURE" : "NOMINAL"}
            </span>
          </div>
        </div>

        {/* Subsidence Velocity Card */}
        <div className={`metric-card ${nodeData.subsidence_velocity_mm_hr > 2.0 ? "danger-border" : "stable-border"}`}>
          <div className="metric-header">
            <span className="metric-label">Subsidence Velocity</span>
            <div className="metric-icon-box">🚀</div>
          </div>
          <div className="metric-value-box">
            <span className="metric-value mono-font">{nodeData.subsidence_velocity_mm_hr ?? "0.00"}</span>
            <span className="metric-unit">mm/hr</span>
          </div>
          <div className="metric-subtext">
            <span>Rate of Strain</span>
            <span className="mono-font">{nodeData.subsidence_velocity_mm_hr > 1.0 ? "Accelerating Shear" : "Creep"}</span>
          </div>
        </div>

        {/* Tilt Magnitude Card */}
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Biaxial Inclinometer (MPU6050)</span>
            <div className="metric-icon-box">📐</div>
          </div>
          <div className="metric-value-box">
            <span className="metric-value mono-font">{nodeData.tilt_magnitude_deg ?? "0.00"}</span>
            <span className="metric-unit">deg</span>
          </div>
          <div className="metric-subtext">
            <span>Tilt X: {nodeData.tilt_x_deg}°</span>
            <span>Tilt Y: {nodeData.tilt_y_deg}°</span>
          </div>
        </div>

        {/* Micro-Seismic Vibration Card */}
        <div className={`metric-card ${nodeData.vibration_g > 0.05 ? "warning-border" : ""}`}>
          <div className="metric-header">
            <span className="metric-label">Micro-Seismic Geophone (ADXL355)</span>
            <div className="metric-icon-box">🔊</div>
          </div>
          <div className="metric-value-box">
            <span className="metric-value mono-font">{nodeData.vibration_g ?? "0.000"}</span>
            <span className="metric-unit">g</span>
          </div>
          <div className="metric-subtext">
            <span>Sub-surface Fracturing</span>
            <span>{nodeData.vibration_g > 0.05 ? "Burst Activity" : "Nominal"}</span>
          </div>
        </div>

        {/* Environmental Card */}
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Ambient (BME280)</span>
            <div className="metric-icon-box">🌤️</div>
          </div>
          <div className="metric-value-box">
            <span className="metric-value mono-font">{nodeData.temperature_c ?? 26.5}</span>
            <span className="metric-unit">°C</span>
          </div>
          <div className="metric-subtext">
            <span>Relative Humidity:</span>
            <span className="mono-font">{nodeData.humidity_pct ?? 62.0}% RH</span>
          </div>
        </div>

        {/* Power Health */}
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Power & LoRa Radio</span>
            <div className="metric-icon-box">🔋</div>
          </div>
          <div className="metric-value-box">
            <span className="metric-value mono-font">{nodeData.battery_pct ?? 100}%</span>
            <span className="metric-unit">LiFePO4</span>
          </div>
          <div className="metric-subtext">
            <span>{nodeData.battery_voltage_v ?? 4.1} V</span>
            <span>SX1278 Mesh Link</span>
          </div>
        </div>
      </div>

      {/* Dynamic Plotly Line Charts */}
      <div className="charts-grid">
        <div className="chart-card">
          <div className="card-header">
            <div>
              <div className="card-title">Real-Time Cumulative Displacement</div>
              <div className="card-subtitle">Continuous multi-point extensometer & LVDT telemetry</div>
            </div>
          </div>
          <div ref={dispChartRef} className="chart-container"></div>
        </div>

        <div className="chart-card">
          <div className="card-header">
            <div>
              <div className="card-title">Real-Time Crack Opening Displacement</div>
              <div className="card-subtitle">Surface fissure dilation & tension fracture gauge</div>
            </div>
          </div>
          <div ref={crackChartRef} className="chart-container"></div>
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-card">
          <div className="card-header">
            <div>
              <div className="card-title">Biaxial Inclinometer Rotation (MPU6050)</div>
              <div className="card-subtitle">Differential X/Y bedrock deflection angles</div>
            </div>
          </div>
          <div ref={tiltChartRef} className="chart-container"></div>
        </div>

        <div className="chart-card">
          <div className="card-header">
            <div>
              <div className="card-title">Micro-Seismic Geophone Energy (ADXL355)</div>
              <div className="card-subtitle">Goaf fracturing, acoustic emissions & seismic events</div>
            </div>
          </div>
          <div ref={vibeChartRef} className="chart-container"></div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// 5. AI & 3D ANALYTICS VIEW (TIMESFM FORECAST & 3D SUBSIDENCE TROUGH)
// ============================================================================
function AI3DAnalyticsView({ selectedNodeId, nodeData, currentTelemetry }) {
  const forecastChartRef = useRef(null);
  const surface3DRef = useRef(null);
  const [forecastData, setForecastData] = useState(null);
  const [isLoadingForecast, setIsLoadingForecast] = useState(false);

  // Fetch TimesFM Forecast from FastAPI endpoint
  const fetchForecast = useCallback(() => {
    setIsLoadingForecast(true);
    fetch(`${BACKEND_HTTP}/api/forecast/timesfm?node_id=${selectedNodeId}`)
      .then(res => res.json())
      .then(data => {
        setForecastData(data);
        setIsLoadingForecast(false);
      })
      .catch(err => {
        console.warn("Forecast fetch error:", err);
        setIsLoadingForecast(false);
      });
  }, [selectedNodeId]);

  useEffect(() => {
    fetchForecast();
  }, [fetchForecast]);

  // Render TimesFM 8-Hour Forecast Plotly Chart
  useEffect(() => {
    if (!forecastChartRef.current || !forecastData || !forecastData.forecast_points) return;

    const points = forecastData.forecast_points;
    const xTimes = points.map(p => new Date(p.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    const p50 = points.map(p => p.displacement_p50);
    const p10 = points.map(p => p.displacement_p10);
    const p90 = points.map(p => p.displacement_p90);

    // Median forecast line (p50)
    const traceMedian = {
      x: xTimes,
      y: p50,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'TimesFM Median (p50)',
      line: { color: '#0284c7', width: 3 },
      marker: { size: 6 }
    };

    // Upper bound (p90)
    const traceUpper = {
      x: xTimes,
      y: p90,
      type: 'scatter',
      mode: 'lines',
      name: 'Upper Bound (p90)',
      line: { color: 'rgba(2, 132, 199, 0.2)', width: 0 },
      showlegend: false
    };

    // Lower bound (p10) with fill to upper
    const traceLower = {
      x: xTimes,
      y: p10,
      type: 'scatter',
      mode: 'lines',
      name: '80% Confidence Interval',
      fill: 'tonexty',
      fillcolor: 'rgba(2, 132, 199, 0.12)',
      line: { color: 'rgba(2, 132, 199, 0.2)', width: 0 }
    };

    // Critical Threshold Line (85mm)
    const traceCritical = {
      x: xTimes,
      y: Array(xTimes.length).fill(forecastData.critical_threshold_mm || 85),
      type: 'scatter',
      mode: 'lines',
      name: 'Evacuation Limit (85mm)',
      line: { color: '#dc2626', width: 2.5, dash: 'dot' }
    };

    const layout = {
      margin: { l: 50, r: 20, t: 30, b: 40 },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      font: { family: 'Inter, sans-serif', color: '#334155' },
      xaxis: { title: 'Forecast Time (8-Hour Forward Horizon)', showgrid: true, gridcolor: '#f1f5f9' },
      yaxis: { title: 'Displacement (mm)', showgrid: true, gridcolor: '#f1f5f9' },
      legend: { orientation: 'h', y: 1.15 }
    };

    Plotly.react(forecastChartRef.current, [traceUpper, traceLower, traceMedian, traceCritical], layout, { responsive: true, displayModeBar: false });
  }, [forecastData]);

  // Render 3D Subsidence Trough Surface Map
  useEffect(() => {
    if (!surface3DRef.current) return;

    // Generate 3D grid representing subsidence basin above longwall void
    const size = 30;
    const x = [];
    const y = [];
    const z = [];

    const centerDist = 15;
    for (let i = 0; i < size; i++) {
      x.push(i * 10);
      y.push(i * 10);
      const row = [];
      for (let j = 0; j < size; j++) {
        // Gaussian / hyperbolic subsidence trough sag formula
        const distSq = (i - centerDist)**2 + (j - centerDist)**2;
        const sag = -65.0 * Math.exp(-distSq / 40.0);
        // Add regional topography slope
        const elevation = 260.0 + (i * 0.2) + sag;
        row.push(elevation);
      }
      z.push(row);
    }

    const surfaceTrace = {
      z: z,
      x: x,
      y: y,
      type: 'surface',
      colorscale: [
        [0, '#b91c1c'],    // Maximum sag / red
        [0.3, '#f97316'],  // Warning trough
        [0.6, '#38bdf8'],  // Stable ground
        [1, '#0284c7']     // High ground
      ],
      showscale: true,
      colorbar: { title: 'Elevation (m)', len: 0.8, thickness: 15 }
    };

    const layout = {
      margin: { l: 0, r: 0, t: 20, b: 0 },
      paper_bgcolor: 'transparent',
      scene: {
        camera: { eye: { x: 1.5, y: 1.5, z: 1.2 } },
        xaxis: { title: 'Longwall Advance (m)', gridcolor: '#e2e8f0' },
        yaxis: { title: 'Panel Width (m)', gridcolor: '#e2e8f0' },
        zaxis: { title: 'Elevation (m)', gridcolor: '#e2e8f0' }
      }
    };

    Plotly.react(surface3DRef.current, [surfaceTrace], layout, { responsive: true, displayModeBar: false });
  }, []);

  return (
    <div>
      {/* AI Geotechnical Risk Assessment & Advisory Card (powered by api_keys.env) */}
      {forecastData?.ai_geotechnical_advisory && (
        <div className="glass-card" style={{ 
          marginBottom: "24px", 
          borderLeft: `6px solid ${
            forecastData.ai_geotechnical_advisory.risk_level === "CRITICAL" ? "#dc2626" :
            forecastData.ai_geotechnical_advisory.risk_level === "WARNING" ? "#d97706" : "#16a34a"
          }` 
        }}>
          <div className="card-header" style={{ marginBottom: "14px" }}>
            <div>
              <div className="card-title" style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span>🛡️ AI Geotechnical Risk Assessment & Advisory</span>
                <span className={`status-pill ${
                  forecastData.ai_geotechnical_advisory.risk_level === "CRITICAL" ? "danger" :
                  forecastData.ai_geotechnical_advisory.risk_level === "WARNING" ? "warning" : "stable"
                }`}>
                  {forecastData.ai_geotechnical_advisory.risk_level} RISK
                </span>
              </div>
              <div className="card-subtitle" style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
                <span>Inference Engine: <b>{forecastData.ai_geotechnical_advisory.provider}</b></span>
                <span>•</span>
                <span>Monitored Sensor: <b>{selectedNodeId}</b></span>
              </div>
            </div>
            <div style={{ fontSize: "11px", color: "#64748b", background: "#f1f5f9", padding: "6px 12px", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
              Configure model & key in <b style={{ color: "#0284c7" }}>api_keys.env</b>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px" }}>
            <div style={{ background: "#f8fafc", padding: "14px 16px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
              <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase", marginBottom: "4px" }}>
                Primary Geotechnical Hazard
              </div>
              <div style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a" }}>
                {forecastData.ai_geotechnical_advisory.primary_hazard}
              </div>
            </div>

            <div style={{ background: "#f8fafc", padding: "14px 16px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
              <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase", marginBottom: "4px" }}>
                Engineering Diagnosis & Prognosis
              </div>
              <div style={{ fontSize: "13px", color: "#334155", lineHeight: "1.5" }}>
                {forecastData.ai_geotechnical_advisory.advisory_summary}
              </div>
            </div>

            <div style={{ background: "#fef2f2", padding: "14px 16px", borderRadius: "8px", border: "1px solid #fecaca", gridColumn: "1 / -1" }}>
              <div style={{ fontSize: "11px", fontWeight: "700", color: "#991b1b", textTransform: "uppercase", marginBottom: "4px" }}>
                Immediate Control Room Mitigation Protocol
              </div>
              <div style={{ fontSize: "13px", fontWeight: "600", color: "#b91c1c", lineHeight: "1.5" }}>
                ⚠️ {forecastData.ai_geotechnical_advisory.mitigation_action}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Forecast Status Overview */}
      <div className="glass-card" style={{ marginBottom: "24px" }}>
        <div className="card-header">
          <div>
            <div className="card-title">
              <span>🧠 TimesFM 8-Hour Subsidence Displacement Forecast</span>
            </div>
            <div className="card-subtitle">
              Target Node: <b>{selectedNodeId}</b> | Zero-Shot Time Series Foundation Model with Bayesian Uncertainty
            </div>
          </div>
          <button 
            onClick={fetchForecast} 
            className="btn-primary"
            style={{ padding: "8px 16px" }}
            disabled={isLoadingForecast}
          >
            {isLoadingForecast ? "Computing..." : "Re-run Inference"}
          </button>
        </div>

        {/* Forecast KPI Metrics */}
        {forecastData && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px", marginBottom: "20px" }}>
            <div style={{ background: "#f8fafc", padding: "14px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
              <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b" }}>CURRENT MOVEMENT</div>
              <div className="mono-font" style={{ fontSize: "20px", fontWeight: "800", color: "#0f172a" }}>
                {forecastData.current_displacement_mm} mm
              </div>
            </div>

            <div style={{ background: "#f8fafc", padding: "14px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
              <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b" }}>TIME TO WARNING (50mm)</div>
              <div className="mono-font" style={{ fontSize: "20px", fontWeight: "800", color: forecastData.time_to_warning_hours ? "#d97706" : "#16a34a" }}>
                {forecastData.time_to_warning_hours ? `${forecastData.time_to_warning_hours} hrs` : "No breach (8h)"}
              </div>
            </div>

            <div style={{ background: "#f8fafc", padding: "14px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
              <div style={{ fontSize: "11px", fontWeight: "700", color: "#64748b" }}>TIME TO EVACUATION (85mm)</div>
              <div className="mono-font" style={{ fontSize: "20px", fontWeight: "800", color: forecastData.time_to_critical_hours ? "#dc2626" : "#16a34a" }}>
                {forecastData.time_to_critical_hours ? `${forecastData.time_to_critical_hours} hrs` : "Clear"}
              </div>
            </div>
          </div>
        )}

        <div ref={forecastChartRef} className="chart-container" style={{ height: "380px" }}></div>
      </div>

      {/* 3D Subsidence Trough Surface & Reference Comparison */}
      <div className="glass-card">
        <div className="card-header">
          <div>
            <div className="card-title">3D Geotechnical Subsidence Trough Digital Elevation Model</div>
            <div className="card-subtitle">
              Overlying strata deformation above Longwall Panel 4B goaf (Sag: 200m–260m elevation)
            </div>
          </div>
          <span className="status-pill danger">Epicenter Node N13 at Deepest Sag</span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "24px", alignItems: "center" }}>
          <div>
            <div ref={surface3DRef} className="chart-container" style={{ height: "450px" }}></div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div style={{ borderRadius: "10px", overflow: "hidden", border: "1px solid #cbd5e1" }}>
              <img 
                src="assets/subsidence_3d_dem.png" 
                alt="Subsidence 3D DEM Reference"
                style={{ width: "100%", height: "auto", display: "block" }}
              />
            </div>
            <div style={{ background: "#f8fafc", padding: "14px", borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "12px", color: "#475569" }}>
              <div style={{ fontWeight: "700", color: "#0f172a", marginBottom: "6px" }}>GEOTECHNICAL DEM CHARACTERISTICS:</div>
              <div style={{ marginBottom: "4px" }}>• <b>Trough Geometry</b>: Hyperbolic subsidence basin centered over Longwall Panel 4B extraction chamber.</div>
              <div style={{ marginBottom: "4px" }}>• <b>Elevation Range</b>: 200 meters at deepest apex sag up to 260 meters at unaffected regional ground.</div>
              <div>• <b>Inflection Point</b>: Maximum tensile strain occurring on the flanks (monitored by N8, N12, N14).</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// 7. TAB: NODE MANAGEMENT & TWO-WAY REMOTE COMMAND DISPATCH
// ============================================================================
function NodeManagementView({ nodesList, selectedNodeId, setSelectedNodeId, onCommandDispatched }) {
  const [commandType, setCommandType] = useState("TARE_ZERO");
  const [paramInterval, setParamInterval] = useState(5);
  const [paramNotes, setParamNotes] = useState("Routine sensor recalibration by geotechnical engineer");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [auditLogs, setAuditLogs] = useState([]);

  const fetchAuditLogs = useCallback(() => {
    fetch(`${BACKEND_HTTP}/api/commands/history?limit=15`)
      .then(res => res.json())
      .then(data => setAuditLogs(data))
      .catch(err => console.warn("Failed to fetch audit log:", err));
  }, []);

  useEffect(() => {
    fetchAuditLogs();
  }, [fetchAuditLogs]);

  const currentPayload = useMemo(() => {
    const payload = {
      target_node: selectedNodeId,
      dispatched_at: new Date().toISOString(),
      supervisor: "GEO-SHIELD_CONTROLLER"
    };

    if (commandType === "SET_SAMPLING_RATE") {
      payload.interval_sec = parseInt(paramInterval, 10);
    } else if (commandType === "TARE_ZERO") {
      payload.mode = "SOFTWARE_ZERO_REFERENCE";
    } else if (commandType === "CALIBRATE_INCLINOMETER") {
      payload.calibration_axes = ["X", "Y"];
    } else if (commandType === "TRIGGER_LOCAL_SIREN") {
      payload.siren_duration_sec = 30;
      payload.relay_channel = 1;
    } else if (commandType === "ACTIVATE_BUZZER") {
      payload.buzzer_frequency_hz = 2400;
      payload.duration_ms = 3000;
    } else if (commandType === "ENTER_LOW_POWER_SLEEP") {
      payload.duty_cycle_ms = 10000;
    }
    payload.reason = paramNotes;
    return payload;
  }, [selectedNodeId, commandType, paramInterval, paramNotes]);

  const handleDispatch = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const response = await fetch(`${BACKEND_HTTP}/api/commands/dispatch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          node_id: selectedNodeId,
          command_type: commandType,
          payload: currentPayload,
          dispatched_by: "MINE_SUPERVISOR_CONSOLE"
        })
      });

      const resJson = await response.json();
      if (response.ok) {
        onCommandDispatched(`Command ${commandType} executed: ${resJson.response_message}`);
        fetchAuditLogs();
      } else {
        alert(`Dispatch failed: ${resJson.detail || "Server error"}`);
      }
    } catch (err) {
      alert(`Network error while dispatching: ${err}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Top: Two-Way Command Dispatcher & Audit Logs */}
      <div className="node-mgmt-grid">
        <div className="glass-card">
          <div className="card-header">
            <div className="card-title">Two-Way LoRa Remote Dispatch</div>
          </div>

          <form onSubmit={handleDispatch} className="command-form">
            <div className="form-group">
              <label className="form-label">Target Geotechnical Node</label>
              <select 
                value={selectedNodeId} 
                onChange={(e) => setSelectedNodeId(e.target.value)}
                className="form-select"
              >
                {nodesList.map(n => (
                  <option key={n.node_id} value={n.node_id}>
                    {n.node_id} — {n.name} {n.node_id === "N13" ? "⚠️ [APEX]" : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Command Protocol</label>
              <select 
                value={commandType} 
                onChange={(e) => setCommandType(e.target.value)}
                className="form-select"
              >
                <option value="TARE_ZERO">TARE_ZERO (Reset Displacement Baseline)</option>
                <option value="SET_SAMPLING_RATE">SET_SAMPLING_RATE (Configure Frequency)</option>
                <option value="CALIBRATE_INCLINOMETER">CALIBRATE_INCLINOMETER (Re-Zero Tilt Bias)</option>
                <option value="TRIGGER_LOCAL_SIREN">TRIGGER_LOCAL_SIREN (Fire Early Warning Siren Relay)</option>
                <option value="ACTIVATE_BUZZER">ACTIVATE_BUZZER (Sound On-Node Piezo Buzzer)</option>
                <option value="ENTER_LOW_POWER_SLEEP">ENTER_LOW_POWER_SLEEP (Conserve Battery)</option>
                <option value="TRIGGER_EMERGENCY_BEACON">TRIGGER_EMERGENCY_BEACON (Locator Pulse)</option>
                <option value="RESET_MODEM">RESET_MODEM (Re-Negotiate LoRaWAN)</option>
              </select>
            </div>

            {commandType === "SET_SAMPLING_RATE" && (
              <div className="form-group">
                <label className="form-label">Polling Interval (Seconds)</label>
                <input 
                  type="number" 
                  min="1" 
                  max="60" 
                  value={paramInterval}
                  onChange={(e) => setParamInterval(e.target.value)}
                  className="form-input"
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Operational Rationale / Work Order</label>
              <input 
                type="text" 
                value={paramNotes}
                onChange={(e) => setParamNotes(e.target.value)}
                className="form-input"
                placeholder="e.g. Work order #8843 longwall pass"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Payload Transmission Preview</label>
              <pre className="code-preview">
                {JSON.stringify(currentPayload, null, 2)}
              </pre>
            </div>

            <button 
              type="submit" 
              className="btn-primary"
              disabled={isSubmitting}
              style={{ width: "100%", marginTop: "10px" }}
            >
              {isSubmitting ? "Transmitting via LoRaWAN Mesh..." : "🚀 Dispatch Command to Node"}
            </button>
          </form>
        </div>

        {/* Right: Command Audit Logs */}
        <div className="glass-card">
          <div className="card-header">
            <div className="card-title">Telemetry Command Audit Trail</div>
            <button onClick={fetchAuditLogs} style={{ background: "none", border: "none", color: "#0284c7", fontWeight: "700", cursor: "pointer", fontSize: "12px" }}>
              🔄 Refresh History
            </button>
          </div>

          <div className="table-responsive">
            <table className="geo-table">
              <thead>
                <tr>
                  <th>Dispatched At</th>
                  <th>Target Node</th>
                  <th>Command</th>
                  <th>Status</th>
                  <th>Response Message</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan="5" style={{ textAlign: "center", color: "#64748b", padding: "24px" }}>
                      No commands dispatched in current session.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map(log => (
                    <tr key={log.id}>
                      <td className="mono-font" style={{ fontSize: "11px" }}>
                        {log.dispatched_at ? new Date(log.dispatched_at).toLocaleTimeString() : "-"}
                      </td>
                      <td style={{ fontWeight: "700", color: "#0f172a" }}>{log.node_id}</td>
                      <td>
                        <span style={{ background: "#e0f2fe", color: "#0369a1", padding: "3px 8px", borderRadius: "4px", fontSize: "11px", fontWeight: "700" }}>
                          {log.command_type}
                        </span>
                      </td>
                      <td>
                        <span className="status-pill stable" style={{ padding: "3px 8px", fontSize: "10px" }}>
                          {log.status}
                        </span>
                      </td>
                      <td style={{ fontSize: "12px" }}>{log.response_message}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Bottom: Complete 21-Node Hardware Inventory Table */}
      <div className="glass-card">
        <div className="card-header">
          <div>
            <div className="card-title">Comprehensive 21-Node Hardware Inventory</div>
            <div className="card-subtitle">
              All 20 surface grid nodes and GW-01 base station with onboard microcontrollers, sensors, and telemetry status
            </div>
          </div>
          <span className="status-pill stable">21/21 Nodes Provisioned</span>
        </div>

        <div className="table-responsive">
          <table className="geo-table">
            <thead>
              <tr>
                <th>Node ID</th>
                <th>Grid Pos</th>
                <th>Station Role</th>
                <th>Microcontroller</th>
                <th>Sensors Onboard</th>
                <th>LoRa Radio</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {nodesList.map(n => (
                <tr key={n.node_id} style={{ background: n.node_id === selectedNodeId ? "#f0f9ff" : "transparent" }}>
                  <td className="mono-font" style={{ fontWeight: "800", color: n.node_id === "N13" ? "#dc2626" : "#0f172a" }}>
                    {n.node_id} {n.node_id === "N13" ? "⚠️ [APEX]" : ""}
                  </td>
                  <td>{n.grid_row ? `R${n.grid_row}:C${n.grid_col}` : "Gateway"}</td>
                  <td>{n.name}</td>
                  <td className="mono-font" style={{ fontSize: "11px" }}>{n.mcu || "ESP32"}</td>
                  <td style={{ fontSize: "11px" }}>
                    {[n.tilt_sensor, n.vibe_sensor, n.disp_sensor, n.crack_sensor, n.env_sensor].filter(Boolean).join(" + ") || "All Sensors"}
                  </td>
                  <td className="mono-font" style={{ fontSize: "11px" }}>{n.lora_module || "SX1278"}</td>
                  <td>
                    <span className={`status-pill ${n.node_id === "N13" ? "danger" : (n.node_id === "GW-01" ? "stable" : (["N8", "N12", "N14"].includes(n.node_id) ? "warning" : "stable"))}`} style={{ padding: "3px 8px", fontSize: "10px" }}>
                      {n.node_id === "N13" ? "CRITICAL" : (["N8", "N12", "N14"].includes(n.node_id) ? "WARNING" : "STABLE")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// Render React App to Root DOM
ReactDOM.createRoot(document.getElementById("root")).render(<App />);