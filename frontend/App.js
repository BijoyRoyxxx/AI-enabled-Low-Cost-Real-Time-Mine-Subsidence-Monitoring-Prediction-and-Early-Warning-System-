const { useState, useEffect, useRef, useCallback, useMemo } = React;
const STATUS_COLORS = {
  STABLE: { fill: "#22c55e", stroke: "#15803d", bg: "#f0fdf4", text: "#15803d" },
  WARNING: { fill: "#f59e0b", stroke: "#b45309", bg: "#fffbeb", text: "#b45309" },
  DANGER: { fill: "#ef4444", stroke: "#b91c1c", bg: "#fef2f2", text: "#b91c1c" }
};
// Replace 'your-app-name' with what you plan to name your Render service
const BACKEND_HTTP = "https://mine.onrender.com";
const BACKEND_WS = "wss://mine.onrender.com/ws/telemetry";
function App() {
  const [activeTab, setActiveTab] = useState("gis");
  const [wsStatus, setWsStatus] = useState("CONNECTING");
  const [nodesList, setNodesList] = useState([]);
  const [selectedNodeId, setSelectedNodeId] = useState("N13");
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
  const [currentTimeStr, setCurrentTimeStr] = useState((/* @__PURE__ */ new Date()).toLocaleTimeString());
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTimeStr((/* @__PURE__ */ new Date()).toLocaleTimeString());
    }, 1e3);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    fetch(`${BACKEND_HTTP}/api/nodes`).then((res) => res.json()).then((data) => {
      setNodesList(data);
      if (data.length > 0 && !selectedNodeId) {
        const n13 = data.find((n) => n.node_id === "N13");
        setSelectedNodeId(n13 ? "N13" : data[0].node_id);
      }
    }).catch((err) => console.warn("Failed to fetch initial nodes:", err));
  }, []);
  useEffect(() => {
    fetch(`${BACKEND_HTTP}/api/telemetry/recent?limit=60`).then((res) => res.json()).then((records) => {
      if (records && records.length > 0) {
        setTelemetryHistory(records);
      }
    }).catch((err) => console.warn("Could not prefill telemetry history:", err));
  }, []);
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
            payload.nodes.forEach((n) => {
              nodeMap[n.node_id] = n;
            });
            setCurrentTelemetry(nodeMap);
            if (payload.summary) {
              setSystemSummary(payload.summary);
            }
            setTelemetryHistory((prev) => {
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
        reconnectTimeout = setTimeout(connectWebSocket, 4e3);
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
  return /* @__PURE__ */ React.createElement("div", { className: "app-container" }, /* @__PURE__ */ React.createElement(
    Sidebar,
    {
      activeTab,
      setActiveTab,
      summary: systemSummary
    }
  ), /* @__PURE__ */ React.createElement("main", { className: "main-content" }, /* @__PURE__ */ React.createElement(
    TopHeader,
    {
      wsStatus,
      summary: systemSummary,
      timeStr: currentTimeStr
    }
  ), /* @__PURE__ */ React.createElement("div", { className: "view-wrapper" }, toastMessage && /* @__PURE__ */ React.createElement("div", { className: `toast-banner ${toastMessage.type}` }, /* @__PURE__ */ React.createElement("span", null, toastMessage.message), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => setToastMessage(null),
      style: { background: "none", border: "none", cursor: "pointer", fontWeight: "bold" }
    },
    "\u2715"
  )), activeTab === "gis" && /* @__PURE__ */ React.createElement(
    GISMapView,
    {
      currentTelemetry,
      selectedNodeId,
      onSelectNode: setSelectedNodeId
    }
  ), activeTab === "telemetry" && /* @__PURE__ */ React.createElement(
    TelemetryView,
    {
      nodesList,
      selectedNodeId,
      setSelectedNodeId,
      nodeData: selectedNodeData,
      telemetryHistory
    }
  ), activeTab === "analytics" && /* @__PURE__ */ React.createElement(
    AI3DAnalyticsView,
    {
      selectedNodeId,
      nodeData: selectedNodeData,
      currentTelemetry
    }
  ), activeTab === "nodes" && /* @__PURE__ */ React.createElement(
    NodeManagementView,
    {
      nodesList,
      selectedNodeId,
      setSelectedNodeId,
      onCommandDispatched: (msg) => showToast(msg, "success")
    }
  ))));
}
function TopHeader({ wsStatus, summary, timeStr }) {
  const statusClass = (summary.overall_status || "STABLE").toLowerCase();
  const isDanger = summary.overall_status === "DANGER";
  return /* @__PURE__ */ React.createElement("header", { className: "top-header" }, /* @__PURE__ */ React.createElement("div", { className: "header-left" }, /* @__PURE__ */ React.createElement("div", { className: "header-title-group" }, /* @__PURE__ */ React.createElement("h1", null, "AI-Enabled Real Time Mine Subsidence Monitoring System"), /* @__PURE__ */ React.createElement("div", { className: "header-meta" }, /* @__PURE__ */ React.createElement("span", null, "Bowen Basin Longwall Panel 4B"), /* @__PURE__ */ React.createElement("span", null, "\u2022"), /* @__PURE__ */ React.createElement("span", null, "4\xD75 LoRaWAN Mesh (20 Surface Nodes + GW-01)"), /* @__PURE__ */ React.createElement("span", null, "\u2022"), /* @__PURE__ */ React.createElement("span", { style: { color: isDanger ? "#dc2626" : "#16a34a", fontWeight: "700" } }, "Subsidence Epicenter: ", summary.high_risk_node || "N13")))), /* @__PURE__ */ React.createElement("div", { className: "header-right" }, /* @__PURE__ */ React.createElement("div", { className: `status-pill ${isDanger ? "danger pulse-anim" : "stable"}`, title: "Industrial Siren Relay Output" }, /* @__PURE__ */ React.createElement("span", { className: "status-dot" }), /* @__PURE__ */ React.createElement("span", null, "SIREN: ", summary.siren_status || (isDanger ? "ACTIVE" : "STANDBY"))), /* @__PURE__ */ React.createElement("div", { className: `status-pill ${isDanger ? "danger" : "stable"}`, title: "Site LED Display Board Text" }, /* @__PURE__ */ React.createElement("span", null, "\u{1F6A8} LED: ", isDanger ? "CRITICAL ALERT" : "NORMAL")), /* @__PURE__ */ React.createElement("div", { className: "status-pill stable", title: "SX1278 4x5 Mesh Topology" }, /* @__PURE__ */ React.createElement("span", { className: "status-dot" }), /* @__PURE__ */ React.createElement("span", null, summary.lora_mesh || "MESH: ONLINE")), /* @__PURE__ */ React.createElement("div", { className: "status-pill stable", title: "NEO-6M GPS Receiver Status" }, /* @__PURE__ */ React.createElement("span", null, "\u{1F6F0}\uFE0F GPS: 12 SATS")), /* @__PURE__ */ React.createElement("div", { className: `status-pill ${wsStatus === "CONNECTED" ? "stable" : "danger"}` }, /* @__PURE__ */ React.createElement("span", { className: "status-dot" }), /* @__PURE__ */ React.createElement("span", null, wsStatus === "CONNECTED" ? "WS Live (5s)" : "WS Disconnected")), /* @__PURE__ */ React.createElement("div", { className: `status-pill ${statusClass}` }, /* @__PURE__ */ React.createElement("span", { className: "status-dot" }), /* @__PURE__ */ React.createElement("span", null, summary.overall_status || "STABLE")), /* @__PURE__ */ React.createElement("div", { style: { fontSize: "13px", fontWeight: "700", color: "#334155", marginLeft: "4px" }, className: "mono-font" }, timeStr, " AEST")));
}
function Sidebar({ activeTab, setActiveTab, summary }) {
  const [serviceConfig, setServiceConfig] = useState(null);
  useEffect(() => {
    fetch(`${BACKEND_HTTP}/api/config`).then((res) => res.json()).then((cfg) => setServiceConfig(cfg)).catch((err) => console.warn("Failed to load config:", err));
  }, []);
  const navLinks = [
    { id: "gis", label: "Live GIS Map", icon: "\u{1F5FA}\uFE0F" },
    { id: "telemetry", label: "Telemetry & Visuals", icon: "\u{1F4C8}" },
    { id: "analytics", label: "AI & 3D Analytics", icon: "\u{1F9E0}" },
    { id: "nodes", label: "Node Management", icon: "\u2699\uFE0F" }
  ];
  const mapHasKey = serviceConfig?.map?.has_key;
  const mapProvider = serviceConfig?.map?.provider || "osm";
  const llmHasKey = serviceConfig?.llm?.has_key;
  const llmProvider = serviceConfig?.llm?.provider || "gemini";
  return /* @__PURE__ */ React.createElement("aside", { className: "sidebar" }, /* @__PURE__ */ React.createElement("div", { className: "sidebar-header" }, /* @__PURE__ */ React.createElement("div", { className: "brand-icon" }, "\u{1F4E1}"), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "brand-title" }, "MINE-SUBSIDENCE"), /* @__PURE__ */ React.createElement("div", { className: "brand-subtitle" }, "AI & LoRa Mesh Platform"))), /* @__PURE__ */ React.createElement("nav", { className: "sidebar-nav" }, navLinks.map((link) => /* @__PURE__ */ React.createElement(
    "button",
    {
      key: link.id,
      className: `nav-item ${activeTab === link.id ? "active" : ""}`,
      onClick: () => setActiveTab(link.id)
    },
    /* @__PURE__ */ React.createElement("span", { className: "nav-icon" }, link.icon),
    /* @__PURE__ */ React.createElement("span", null, link.label)
  ))), /* @__PURE__ */ React.createElement("div", { className: "sidebar-footer" }, /* @__PURE__ */ React.createElement("div", { className: "quick-telemetry-badge" }, /* @__PURE__ */ React.createElement("div", { className: "quick-badge-header" }, /* @__PURE__ */ React.createElement("span", null, "Subsidence Live Metric"), /* @__PURE__ */ React.createElement("span", { style: { color: summary.overall_status === "DANGER" ? "#dc2626" : "#16a34a" } }, "\u25CF")), /* @__PURE__ */ React.createElement("div", { className: "quick-badge-row" }, /* @__PURE__ */ React.createElement("span", null, "Peak Disp:"), /* @__PURE__ */ React.createElement("span", { className: "quick-badge-val mono-font", style: { color: summary.max_displacement_mm > 50 ? "#dc2626" : "#0f172a" } }, summary.max_displacement_mm || "54.8", " mm")), /* @__PURE__ */ React.createElement("div", { className: "quick-badge-row" }, /* @__PURE__ */ React.createElement("span", null, "Max Crack:"), /* @__PURE__ */ React.createElement("span", { className: "quick-badge-val mono-font", style: { color: (summary.max_crack_mm || 4.25) > 3 ? "#dc2626" : "#0f172a" } }, summary.max_crack_mm || "4.25", " mm")), /* @__PURE__ */ React.createElement("div", { className: "quick-badge-row" }, /* @__PURE__ */ React.createElement("span", null, "Max Velocity:"), /* @__PURE__ */ React.createElement("span", { className: "quick-badge-val mono-font" }, summary.max_velocity_mm_hr || "2.45", " mm/h")), /* @__PURE__ */ React.createElement("div", { className: "quick-badge-row" }, /* @__PURE__ */ React.createElement("span", null, "Critical Apex:"), /* @__PURE__ */ React.createElement("span", { className: "quick-badge-val", style: { color: "#dc2626", fontWeight: "800" } }, summary.high_risk_node || "N13"))), /* @__PURE__ */ React.createElement("div", { style: { marginTop: "12px", padding: "10px 12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", color: "#475569" } }, /* @__PURE__ */ React.createElement("div", { style: { fontWeight: "700", color: "#1e293b", marginBottom: "6px", display: "flex", justifyContent: "space-between", alignItems: "center" } }, /* @__PURE__ */ React.createElement("span", null, "API KEYS STATUS"), /* @__PURE__ */ React.createElement("span", { style: { fontSize: "10px", color: "#0284c7", fontWeight: "600" } }, "api_keys.env")), /* @__PURE__ */ React.createElement("div", { style: { display: "flex", justifyContent: "space-between", marginBottom: "4px" } }, /* @__PURE__ */ React.createElement("span", null, "\u{1F5FA}\uFE0F Map API:"), /* @__PURE__ */ React.createElement("span", { style: { fontWeight: "600", color: mapHasKey ? "#16a34a" : "#0284c7" } }, mapHasKey ? `${mapProvider.toUpperCase()} Active` : "OpenStreetMap (Free)")), /* @__PURE__ */ React.createElement("div", { style: { display: "flex", justifyContent: "space-between" } }, /* @__PURE__ */ React.createElement("span", null, "\u{1F9E0} LLM Model:"), /* @__PURE__ */ React.createElement("span", { style: { fontWeight: "600", color: llmHasKey ? "#16a34a" : "#0284c7" } }, llmHasKey ? `${llmProvider.toUpperCase()} Live` : "TimesFM (Physics)"))), /* @__PURE__ */ React.createElement("div", { style: { marginTop: "8px", padding: "8px 12px", background: "#f1f5f9", borderRadius: "8px", fontSize: "10px", color: "#64748b" } }, /* @__PURE__ */ React.createElement("div", null, "Mesh: 21 Nodes (SX1278 LoRa)"), /* @__PURE__ */ React.createElement("div", null, "Sensors: LVDT + Crack + MPU6050 + BME280"))));
}
function GISMapView({ currentTelemetry, selectedNodeId, onSelectNode }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef({});
  const [hazardsData, setHazardsData] = useState(null);
  const [mapConfig, setMapConfig] = useState({ provider: "carto", has_key: false });
  useEffect(() => {
    fetch(`${BACKEND_HTTP}/api/hazards`).then((res) => res.json()).then((data) => setHazardsData(data)).catch((err) => console.warn("Failed to load hazard zones:", err));
    fetch(`${BACKEND_HTTP}/api/config`).then((res) => res.json()).then((cfg) => {
      if (cfg.map) setMapConfig(cfg.map);
    }).catch((err) => console.warn("Failed to load map config:", err));
  }, []);
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;
    const center = [-23.5512, 148.175];
    const map = L.map(mapContainerRef.current, {
      center,
      zoom: 16,
      zoomControl: true,
      attributionControl: false
    });
    let tileUrl = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
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
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !hazardsData) return;
    const hazardColors = {
      CRITICAL: { color: "#dc2626", fill: "#ef4444" },
      HIGH: { color: "#ea580c", fill: "#f97316" },
      MODERATE: { color: "#d97706", fill: "#f59e0b" }
    };
    hazardsData.hazard_zones.forEach((zone) => {
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
    hazardsData.mesh_links.forEach((link) => {
      L.polyline(link.coordinates, {
        color: "#0284c7",
        weight: 1.5,
        opacity: 0.6,
        dashArray: "3, 6"
      }).addTo(map);
    });
  }, [hazardsData]);
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || Object.keys(currentTelemetry).length === 0) return;
    Object.values(currentTelemetry).forEach((node) => {
      const nid = node.node_id;
      const status = node.health_status || "STABLE";
      const styleCfg = STATUS_COLORS[status] || STATUS_COLORS.STABLE;
      const isApex = nid === "N13";
      if (!markersRef.current[nid]) {
        const marker2 = L.circleMarker([node.latitude, node.longitude], {
          radius: nid === "GW-01" ? 11 : isApex ? 13 : 8,
          fillColor: styleCfg.fill,
          color: styleCfg.stroke,
          weight: isApex ? 3.5 : 2.5,
          opacity: 1,
          fillOpacity: 0.95
        }).addTo(map);
        marker2.on("click", () => {
          onSelectNode(nid);
        });
        markersRef.current[nid] = marker2;
      } else {
        const marker2 = markersRef.current[nid];
        marker2.setStyle({
          fillColor: styleCfg.fill,
          color: styleCfg.stroke,
          radius: nid === selectedNodeId ? 14 : isApex ? 13 : nid === "GW-01" ? 11 : 8,
          weight: nid === selectedNodeId ? 4 : isApex ? 3.5 : 2.5
        });
      }
      const marker = markersRef.current[nid];
      if (marker) {
        marker.bindPopup(`
          <div style="min-width: 190px;">
            <div class="popup-title">${node.node_id} ${isApex ? "\u26A0\uFE0F [CRITICAL APEX]" : ""}</div>
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
              <b class="mono-font">${node.crack_opening_mm !== void 0 ? node.crack_opening_mm : "0.00"} mm</b>
            </div>
            <div class="popup-row">
              <span>Velocity:</span>
              <b class="mono-font">${node.subsidence_velocity_mm_hr} mm/h</b>
            </div>
            <div class="popup-row">
              <span>Tilt Mag:</span>
              <b class="mono-font">${node.tilt_magnitude_deg}\xB0</b>
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
  return /* @__PURE__ */ React.createElement("div", { className: "map-view-container" }, /* @__PURE__ */ React.createElement("div", { className: "map-card-wrapper" }, /* @__PURE__ */ React.createElement("div", { ref: mapContainerRef, className: "map-viewport" }), /* @__PURE__ */ React.createElement("div", { className: "map-floating-overlay" }, /* @__PURE__ */ React.createElement("div", { style: { marginBottom: "10px", paddingBottom: "8px", borderBottom: "1px solid #e2e8f0" } }, /* @__PURE__ */ React.createElement("div", { style: { fontSize: "10px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" } }, "Map Tile Source"), /* @__PURE__ */ React.createElement("div", { style: { fontSize: "12px", fontWeight: "600", color: mapConfig.has_key ? "#16a34a" : "#0284c7" } }, mapConfig.has_key ? `${mapConfig.provider.toUpperCase()} (Custom Key)` : "OpenStreetMap Standard"), /* @__PURE__ */ React.createElement("div", { style: { fontSize: "10px", color: "#94a3b8" } }, "Set MAP_API_KEY in api_keys.env")), /* @__PURE__ */ React.createElement("div", { className: "map-legend-title" }, "Geotechnical Status"), /* @__PURE__ */ React.createElement("div", { className: "map-legend-item" }, /* @__PURE__ */ React.createElement("span", { className: "legend-badge", style: { background: "#22c55e" } }), /* @__PURE__ */ React.createElement("span", null, "Stable / Normal (<25mm)")), /* @__PURE__ */ React.createElement("div", { className: "map-legend-item" }, /* @__PURE__ */ React.createElement("span", { className: "legend-badge", style: { background: "#f59e0b" } }), /* @__PURE__ */ React.createElement("span", null, "Warning / Elevated Strain")), /* @__PURE__ */ React.createElement("div", { className: "map-legend-item" }, /* @__PURE__ */ React.createElement("span", { className: "legend-badge", style: { background: "#ef4444" } }), /* @__PURE__ */ React.createElement("span", null, "Critical Anomaly / Shear Hazard")), /* @__PURE__ */ React.createElement("div", { className: "map-legend-item", style: { marginTop: "10px", borderTop: "1px solid #e2e8f0", paddingTop: "8px" } }, /* @__PURE__ */ React.createElement("span", { style: { borderBottom: "2px dashed #0284c7", width: "16px", height: "1px", display: "inline-block" } }), /* @__PURE__ */ React.createElement("span", { style: { fontSize: "11px" } }, "LoRaWAN Mesh Topology")))));
}
function TelemetryView({ nodesList, selectedNodeId, setSelectedNodeId, nodeData, telemetryHistory }) {
  const dispChartRef = useRef(null);
  const crackChartRef = useRef(null);
  const tiltChartRef = useRef(null);
  const vibeChartRef = useRef(null);
  const nodeHistory = useMemo(() => {
    return telemetryHistory.filter((h) => h.node_id === selectedNodeId);
  }, [telemetryHistory, selectedNodeId]);
  useEffect(() => {
    if (!dispChartRef.current || nodeHistory.length === 0) return;
    const times = nodeHistory.map((h) => h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : "");
    const dispValues = nodeHistory.map((h) => h.displacement_mm || 0);
    const trace1 = {
      x: times,
      y: dispValues,
      type: "scatter",
      mode: "lines+markers",
      name: "Displacement (mm)",
      line: { color: "#0284c7", width: 3, shape: "spline" },
      marker: { size: 5, color: "#0369a1" }
    };
    const traceWarning = {
      x: times,
      y: Array(times.length).fill(50),
      type: "scatter",
      mode: "lines",
      name: "Warning Limit (50mm)",
      line: { color: "#f59e0b", width: 2, dash: "dash" }
    };
    const layout = {
      margin: { l: 50, r: 20, t: 30, b: 40 },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { family: "Inter, sans-serif", color: "#334155" },
      xaxis: { showgrid: true, gridcolor: "#f1f5f9", zeroline: false },
      yaxis: { title: "Displacement (mm)", showgrid: true, gridcolor: "#f1f5f9", zeroline: false },
      legend: { orientation: "h", y: 1.15 }
    };
    Plotly.react(dispChartRef.current, [trace1, traceWarning], layout, { responsive: true, displayModeBar: false });
  }, [nodeHistory]);
  useEffect(() => {
    if (!crackChartRef.current || nodeHistory.length === 0) return;
    const times = nodeHistory.map((h) => h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : "");
    const crackValues = nodeHistory.map((h) => h.crack_opening_mm !== void 0 ? h.crack_opening_mm : 0);
    const traceCrack = {
      x: times,
      y: crackValues,
      type: "scatter",
      mode: "lines+markers",
      name: "Crack Width (mm)",
      line: { color: "#dc2626", width: 2.5, shape: "spline" },
      marker: { size: 4, color: "#991b1b" }
    };
    const traceThreshold = {
      x: times,
      y: Array(times.length).fill(3),
      type: "scatter",
      mode: "lines",
      name: "Shear Crack Alarm (3.0mm)",
      line: { color: "#ea580c", width: 2, dash: "dot" }
    };
    const layout = {
      margin: { l: 50, r: 20, t: 30, b: 40 },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { family: "Inter, sans-serif", color: "#334155" },
      xaxis: { showgrid: true, gridcolor: "#f1f5f9", zeroline: false },
      yaxis: { title: "Crack Opening (mm)", showgrid: true, gridcolor: "#f1f5f9", zeroline: false },
      legend: { orientation: "h", y: 1.15 }
    };
    Plotly.react(crackChartRef.current, [traceCrack, traceThreshold], layout, { responsive: true, displayModeBar: false });
  }, [nodeHistory]);
  useEffect(() => {
    if (!tiltChartRef.current || nodeHistory.length === 0) return;
    const times = nodeHistory.map((h) => h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : "");
    const tiltX = nodeHistory.map((h) => h.tilt_x_deg || 0);
    const tiltY = nodeHistory.map((h) => h.tilt_y_deg || 0);
    const traceX = {
      x: times,
      y: tiltX,
      type: "scatter",
      mode: "lines",
      name: "Tilt X-Axis (\xB0)",
      line: { color: "#4f46e5", width: 2.5 }
    };
    const traceY = {
      x: times,
      y: tiltY,
      type: "scatter",
      mode: "lines",
      name: "Tilt Y-Axis (\xB0)",
      line: { color: "#06b6d4", width: 2.5 }
    };
    const layout = {
      margin: { l: 50, r: 20, t: 30, b: 40 },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { family: "Inter, sans-serif", color: "#334155" },
      xaxis: { showgrid: true, gridcolor: "#f1f5f9" },
      yaxis: { title: "Tilt Angle (\xB0)", showgrid: true, gridcolor: "#f1f5f9" },
      legend: { orientation: "h", y: 1.15 }
    };
    Plotly.react(tiltChartRef.current, [traceX, traceY], layout, { responsive: true, displayModeBar: false });
  }, [nodeHistory]);
  useEffect(() => {
    if (!vibeChartRef.current || nodeHistory.length === 0) return;
    const times = nodeHistory.map((h) => h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : "");
    const vib = nodeHistory.map((h) => h.vibration_g || 0);
    const traceVib = {
      x: times,
      y: vib,
      type: "scatter",
      mode: "lines+markers",
      name: "Peak Micro-Seismic (g)",
      fill: "tozeroy",
      fillcolor: "rgba(2, 132, 199, 0.08)",
      line: { color: "#0284c7", width: 2 }
    };
    const layout = {
      margin: { l: 50, r: 20, t: 30, b: 40 },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { family: "Inter, sans-serif", color: "#334155" },
      xaxis: { showgrid: true, gridcolor: "#f1f5f9" },
      yaxis: { title: "Acceleration (g)", showgrid: true, gridcolor: "#f1f5f9" },
      legend: { orientation: "h", y: 1.15 }
    };
    Plotly.react(vibeChartRef.current, [traceVib], layout, { responsive: true, displayModeBar: false });
  }, [nodeHistory]);
  return /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "glass-card", style: { padding: "16px 24px", marginBottom: "24px", display: "flex", alignItems: "center", justifyContent: "space-between" } }, /* @__PURE__ */ React.createElement("div", { style: { display: "flex", alignItems: "center", gap: "12px" } }, /* @__PURE__ */ React.createElement("span", { style: { fontSize: "13px", fontWeight: "700", color: "#64748b", textTransform: "uppercase" } }, "Selected Node:"), /* @__PURE__ */ React.createElement(
    "select",
    {
      value: selectedNodeId,
      onChange: (e) => setSelectedNodeId(e.target.value),
      className: "form-select",
      style: { width: "280px" }
    },
    nodesList.map((n) => /* @__PURE__ */ React.createElement("option", { key: n.node_id, value: n.node_id }, n.node_id, " \u2014 ", n.name, " ", n.node_id === "N13" ? "\u26A0\uFE0F (CRITICAL APEX)" : ""))
  )), /* @__PURE__ */ React.createElement("div", { className: `status-pill ${nodeData.health_status ? nodeData.health_status.toLowerCase() : "stable"}` }, /* @__PURE__ */ React.createElement("span", { className: "status-dot" }), /* @__PURE__ */ React.createElement("span", null, nodeData.health_status || "STABLE"))), /* @__PURE__ */ React.createElement("div", { className: "metrics-grid" }, /* @__PURE__ */ React.createElement("div", { className: `metric-card ${nodeData.displacement_mm > 45 ? "danger-border" : nodeData.displacement_mm > 25 ? "warning-border" : "stable-border"}` }, /* @__PURE__ */ React.createElement("div", { className: "metric-header" }, /* @__PURE__ */ React.createElement("span", { className: "metric-label" }, "Cumulative Displacement (LVDT)"), /* @__PURE__ */ React.createElement("div", { className: "metric-icon-box" }, "\u{1F4CF}")), /* @__PURE__ */ React.createElement("div", { className: "metric-value-box" }, /* @__PURE__ */ React.createElement("span", { className: "metric-value mono-font" }, nodeData.displacement_mm ?? "0.0"), /* @__PURE__ */ React.createElement("span", { className: "metric-unit" }, "mm")), /* @__PURE__ */ React.createElement("div", { className: "metric-subtext" }, /* @__PURE__ */ React.createElement("span", null, "Limit: 50.0 mm"), /* @__PURE__ */ React.createElement("span", { style: { color: nodeData.displacement_mm > 50 ? "#dc2626" : "#16a34a", fontWeight: "700" } }, nodeData.displacement_mm > 50 ? "THRESHOLD EXCEEDED" : "SAFE"))), /* @__PURE__ */ React.createElement("div", { className: `metric-card ${nodeData.crack_opening_mm > 3 ? "danger-border" : nodeData.crack_opening_mm > 1.5 ? "warning-border" : "stable-border"}` }, /* @__PURE__ */ React.createElement("div", { className: "metric-header" }, /* @__PURE__ */ React.createElement("span", { className: "metric-label" }, "Crack Opening Gauge"), /* @__PURE__ */ React.createElement("div", { className: "metric-icon-box" }, "\u26A1")), /* @__PURE__ */ React.createElement("div", { className: "metric-value-box" }, /* @__PURE__ */ React.createElement("span", { className: "metric-value mono-font" }, nodeData.crack_opening_mm ?? "0.00"), /* @__PURE__ */ React.createElement("span", { className: "metric-unit" }, "mm")), /* @__PURE__ */ React.createElement("div", { className: "metric-subtext" }, /* @__PURE__ */ React.createElement("span", null, "Shear Limit: 3.0 mm"), /* @__PURE__ */ React.createElement("span", { style: { color: (nodeData.crack_opening_mm || 0) > 3 ? "#dc2626" : "#16a34a", fontWeight: "700" } }, (nodeData.crack_opening_mm || 0) > 3 ? "SURFACE FISSURE" : "NOMINAL"))), /* @__PURE__ */ React.createElement("div", { className: `metric-card ${nodeData.subsidence_velocity_mm_hr > 2 ? "danger-border" : "stable-border"}` }, /* @__PURE__ */ React.createElement("div", { className: "metric-header" }, /* @__PURE__ */ React.createElement("span", { className: "metric-label" }, "Subsidence Velocity"), /* @__PURE__ */ React.createElement("div", { className: "metric-icon-box" }, "\u{1F680}")), /* @__PURE__ */ React.createElement("div", { className: "metric-value-box" }, /* @__PURE__ */ React.createElement("span", { className: "metric-value mono-font" }, nodeData.subsidence_velocity_mm_hr ?? "0.00"), /* @__PURE__ */ React.createElement("span", { className: "metric-unit" }, "mm/hr")), /* @__PURE__ */ React.createElement("div", { className: "metric-subtext" }, /* @__PURE__ */ React.createElement("span", null, "Rate of Strain"), /* @__PURE__ */ React.createElement("span", { className: "mono-font" }, nodeData.subsidence_velocity_mm_hr > 1 ? "Accelerating Shear" : "Creep"))), /* @__PURE__ */ React.createElement("div", { className: "metric-card" }, /* @__PURE__ */ React.createElement("div", { className: "metric-header" }, /* @__PURE__ */ React.createElement("span", { className: "metric-label" }, "Biaxial Inclinometer (MPU6050)"), /* @__PURE__ */ React.createElement("div", { className: "metric-icon-box" }, "\u{1F4D0}")), /* @__PURE__ */ React.createElement("div", { className: "metric-value-box" }, /* @__PURE__ */ React.createElement("span", { className: "metric-value mono-font" }, nodeData.tilt_magnitude_deg ?? "0.00"), /* @__PURE__ */ React.createElement("span", { className: "metric-unit" }, "deg")), /* @__PURE__ */ React.createElement("div", { className: "metric-subtext" }, /* @__PURE__ */ React.createElement("span", null, "Tilt X: ", nodeData.tilt_x_deg, "\xB0"), /* @__PURE__ */ React.createElement("span", null, "Tilt Y: ", nodeData.tilt_y_deg, "\xB0"))), /* @__PURE__ */ React.createElement("div", { className: `metric-card ${nodeData.vibration_g > 0.05 ? "warning-border" : ""}` }, /* @__PURE__ */ React.createElement("div", { className: "metric-header" }, /* @__PURE__ */ React.createElement("span", { className: "metric-label" }, "Micro-Seismic Geophone (ADXL355)"), /* @__PURE__ */ React.createElement("div", { className: "metric-icon-box" }, "\u{1F50A}")), /* @__PURE__ */ React.createElement("div", { className: "metric-value-box" }, /* @__PURE__ */ React.createElement("span", { className: "metric-value mono-font" }, nodeData.vibration_g ?? "0.000"), /* @__PURE__ */ React.createElement("span", { className: "metric-unit" }, "g")), /* @__PURE__ */ React.createElement("div", { className: "metric-subtext" }, /* @__PURE__ */ React.createElement("span", null, "Sub-surface Fracturing"), /* @__PURE__ */ React.createElement("span", null, nodeData.vibration_g > 0.05 ? "Burst Activity" : "Nominal"))), /* @__PURE__ */ React.createElement("div", { className: "metric-card" }, /* @__PURE__ */ React.createElement("div", { className: "metric-header" }, /* @__PURE__ */ React.createElement("span", { className: "metric-label" }, "Ambient (BME280)"), /* @__PURE__ */ React.createElement("div", { className: "metric-icon-box" }, "\u{1F324}\uFE0F")), /* @__PURE__ */ React.createElement("div", { className: "metric-value-box" }, /* @__PURE__ */ React.createElement("span", { className: "metric-value mono-font" }, nodeData.temperature_c ?? 26.5), /* @__PURE__ */ React.createElement("span", { className: "metric-unit" }, "\xB0C")), /* @__PURE__ */ React.createElement("div", { className: "metric-subtext" }, /* @__PURE__ */ React.createElement("span", null, "Relative Humidity:"), /* @__PURE__ */ React.createElement("span", { className: "mono-font" }, nodeData.humidity_pct ?? 62, "% RH"))), /* @__PURE__ */ React.createElement("div", { className: "metric-card" }, /* @__PURE__ */ React.createElement("div", { className: "metric-header" }, /* @__PURE__ */ React.createElement("span", { className: "metric-label" }, "Power & LoRa Radio"), /* @__PURE__ */ React.createElement("div", { className: "metric-icon-box" }, "\u{1F50B}")), /* @__PURE__ */ React.createElement("div", { className: "metric-value-box" }, /* @__PURE__ */ React.createElement("span", { className: "metric-value mono-font" }, nodeData.battery_pct ?? 100, "%"), /* @__PURE__ */ React.createElement("span", { className: "metric-unit" }, "LiFePO4")), /* @__PURE__ */ React.createElement("div", { className: "metric-subtext" }, /* @__PURE__ */ React.createElement("span", null, nodeData.battery_voltage_v ?? 4.1, " V"), /* @__PURE__ */ React.createElement("span", null, "SX1278 Mesh Link")))), /* @__PURE__ */ React.createElement("div", { className: "charts-grid" }, /* @__PURE__ */ React.createElement("div", { className: "chart-card" }, /* @__PURE__ */ React.createElement("div", { className: "card-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "card-title" }, "Real-Time Cumulative Displacement"), /* @__PURE__ */ React.createElement("div", { className: "card-subtitle" }, "Continuous multi-point extensometer & LVDT telemetry"))), /* @__PURE__ */ React.createElement("div", { ref: dispChartRef, className: "chart-container" })), /* @__PURE__ */ React.createElement("div", { className: "chart-card" }, /* @__PURE__ */ React.createElement("div", { className: "card-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "card-title" }, "Real-Time Crack Opening Displacement"), /* @__PURE__ */ React.createElement("div", { className: "card-subtitle" }, "Surface fissure dilation & tension fracture gauge"))), /* @__PURE__ */ React.createElement("div", { ref: crackChartRef, className: "chart-container" }))), /* @__PURE__ */ React.createElement("div", { className: "charts-grid" }, /* @__PURE__ */ React.createElement("div", { className: "chart-card" }, /* @__PURE__ */ React.createElement("div", { className: "card-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "card-title" }, "Biaxial Inclinometer Rotation (MPU6050)"), /* @__PURE__ */ React.createElement("div", { className: "card-subtitle" }, "Differential X/Y bedrock deflection angles"))), /* @__PURE__ */ React.createElement("div", { ref: tiltChartRef, className: "chart-container" })), /* @__PURE__ */ React.createElement("div", { className: "chart-card" }, /* @__PURE__ */ React.createElement("div", { className: "card-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "card-title" }, "Micro-Seismic Geophone Energy (ADXL355)"), /* @__PURE__ */ React.createElement("div", { className: "card-subtitle" }, "Goaf fracturing, acoustic emissions & seismic events"))), /* @__PURE__ */ React.createElement("div", { ref: vibeChartRef, className: "chart-container" }))));
}
function AI3DAnalyticsView({ selectedNodeId, nodeData, currentTelemetry }) {
  const forecastChartRef = useRef(null);
  const surface3DRef = useRef(null);
  const [forecastData, setForecastData] = useState(null);
  const [isLoadingForecast, setIsLoadingForecast] = useState(false);
  const fetchForecast = useCallback(() => {
    setIsLoadingForecast(true);
    fetch(`${BACKEND_HTTP}/api/forecast/timesfm?node_id=${selectedNodeId}`).then((res) => res.json()).then((data) => {
      setForecastData(data);
      setIsLoadingForecast(false);
    }).catch((err) => {
      console.warn("Forecast fetch error:", err);
      setIsLoadingForecast(false);
    });
  }, [selectedNodeId]);
  useEffect(() => {
    fetchForecast();
  }, [fetchForecast]);
  useEffect(() => {
    if (!forecastChartRef.current || !forecastData || !forecastData.forecast_points) return;
    const points = forecastData.forecast_points;
    const xTimes = points.map((p) => new Date(p.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    const p50 = points.map((p) => p.displacement_p50);
    const p10 = points.map((p) => p.displacement_p10);
    const p90 = points.map((p) => p.displacement_p90);
    const traceMedian = {
      x: xTimes,
      y: p50,
      type: "scatter",
      mode: "lines+markers",
      name: "TimesFM Median (p50)",
      line: { color: "#0284c7", width: 3 },
      marker: { size: 6 }
    };
    const traceUpper = {
      x: xTimes,
      y: p90,
      type: "scatter",
      mode: "lines",
      name: "Upper Bound (p90)",
      line: { color: "rgba(2, 132, 199, 0.2)", width: 0 },
      showlegend: false
    };
    const traceLower = {
      x: xTimes,
      y: p10,
      type: "scatter",
      mode: "lines",
      name: "80% Confidence Interval",
      fill: "tonexty",
      fillcolor: "rgba(2, 132, 199, 0.12)",
      line: { color: "rgba(2, 132, 199, 0.2)", width: 0 }
    };
    const traceCritical = {
      x: xTimes,
      y: Array(xTimes.length).fill(forecastData.critical_threshold_mm || 85),
      type: "scatter",
      mode: "lines",
      name: "Evacuation Limit (85mm)",
      line: { color: "#dc2626", width: 2.5, dash: "dot" }
    };
    const layout = {
      margin: { l: 50, r: 20, t: 30, b: 40 },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { family: "Inter, sans-serif", color: "#334155" },
      xaxis: { title: "Forecast Time (8-Hour Forward Horizon)", showgrid: true, gridcolor: "#f1f5f9" },
      yaxis: { title: "Displacement (mm)", showgrid: true, gridcolor: "#f1f5f9" },
      legend: { orientation: "h", y: 1.15 }
    };
    Plotly.react(forecastChartRef.current, [traceUpper, traceLower, traceMedian, traceCritical], layout, { responsive: true, displayModeBar: false });
  }, [forecastData]);
  useEffect(() => {
    if (!surface3DRef.current) return;
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
        const distSq = (i - centerDist) ** 2 + (j - centerDist) ** 2;
        const sag = -65 * Math.exp(-distSq / 40);
        const elevation = 260 + i * 0.2 + sag;
        row.push(elevation);
      }
      z.push(row);
    }
    const surfaceTrace = {
      z,
      x,
      y,
      type: "surface",
      colorscale: [
        [0, "#b91c1c"],
        // Maximum sag / red
        [0.3, "#f97316"],
        // Warning trough
        [0.6, "#38bdf8"],
        // Stable ground
        [1, "#0284c7"]
        // High ground
      ],
      showscale: true,
      colorbar: { title: "Elevation (m)", len: 0.8, thickness: 15 }
    };
    const layout = {
      margin: { l: 0, r: 0, t: 20, b: 0 },
      paper_bgcolor: "transparent",
      scene: {
        camera: { eye: { x: 1.5, y: 1.5, z: 1.2 } },
        xaxis: { title: "Longwall Advance (m)", gridcolor: "#e2e8f0" },
        yaxis: { title: "Panel Width (m)", gridcolor: "#e2e8f0" },
        zaxis: { title: "Elevation (m)", gridcolor: "#e2e8f0" }
      }
    };
    Plotly.react(surface3DRef.current, [surfaceTrace], layout, { responsive: true, displayModeBar: false });
  }, []);
  return /* @__PURE__ */ React.createElement("div", null, forecastData?.ai_geotechnical_advisory && /* @__PURE__ */ React.createElement("div", { className: "glass-card", style: {
    marginBottom: "24px",
    borderLeft: `6px solid ${forecastData.ai_geotechnical_advisory.risk_level === "CRITICAL" ? "#dc2626" : forecastData.ai_geotechnical_advisory.risk_level === "WARNING" ? "#d97706" : "#16a34a"}`
  } }, /* @__PURE__ */ React.createElement("div", { className: "card-header", style: { marginBottom: "14px" } }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "card-title", style: { display: "flex", alignItems: "center", gap: "10px" } }, /* @__PURE__ */ React.createElement("span", null, "\u{1F6E1}\uFE0F AI Geotechnical Risk Assessment & Advisory"), /* @__PURE__ */ React.createElement("span", { className: `status-pill ${forecastData.ai_geotechnical_advisory.risk_level === "CRITICAL" ? "danger" : forecastData.ai_geotechnical_advisory.risk_level === "WARNING" ? "warning" : "stable"}` }, forecastData.ai_geotechnical_advisory.risk_level, " RISK")), /* @__PURE__ */ React.createElement("div", { className: "card-subtitle", style: { display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" } }, /* @__PURE__ */ React.createElement("span", null, "Inference Engine: ", /* @__PURE__ */ React.createElement("b", null, forecastData.ai_geotechnical_advisory.provider)), /* @__PURE__ */ React.createElement("span", null, "\u2022"), /* @__PURE__ */ React.createElement("span", null, "Monitored Sensor: ", /* @__PURE__ */ React.createElement("b", null, selectedNodeId)))), /* @__PURE__ */ React.createElement("div", { style: { fontSize: "11px", color: "#64748b", background: "#f1f5f9", padding: "6px 12px", borderRadius: "6px", border: "1px solid #e2e8f0" } }, "Configure model & key in ", /* @__PURE__ */ React.createElement("b", { style: { color: "#0284c7" } }, "api_keys.env"))), /* @__PURE__ */ React.createElement("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px" } }, /* @__PURE__ */ React.createElement("div", { style: { background: "#f8fafc", padding: "14px 16px", borderRadius: "8px", border: "1px solid #e2e8f0" } }, /* @__PURE__ */ React.createElement("div", { style: { fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase", marginBottom: "4px" } }, "Primary Geotechnical Hazard"), /* @__PURE__ */ React.createElement("div", { style: { fontSize: "14px", fontWeight: "700", color: "#0f172a" } }, forecastData.ai_geotechnical_advisory.primary_hazard)), /* @__PURE__ */ React.createElement("div", { style: { background: "#f8fafc", padding: "14px 16px", borderRadius: "8px", border: "1px solid #e2e8f0" } }, /* @__PURE__ */ React.createElement("div", { style: { fontSize: "11px", fontWeight: "700", color: "#64748b", textTransform: "uppercase", marginBottom: "4px" } }, "Engineering Diagnosis & Prognosis"), /* @__PURE__ */ React.createElement("div", { style: { fontSize: "13px", color: "#334155", lineHeight: "1.5" } }, forecastData.ai_geotechnical_advisory.advisory_summary)), /* @__PURE__ */ React.createElement("div", { style: { background: "#fef2f2", padding: "14px 16px", borderRadius: "8px", border: "1px solid #fecaca", gridColumn: "1 / -1" } }, /* @__PURE__ */ React.createElement("div", { style: { fontSize: "11px", fontWeight: "700", color: "#991b1b", textTransform: "uppercase", marginBottom: "4px" } }, "Immediate Control Room Mitigation Protocol"), /* @__PURE__ */ React.createElement("div", { style: { fontSize: "13px", fontWeight: "600", color: "#b91c1c", lineHeight: "1.5" } }, "\u26A0\uFE0F ", forecastData.ai_geotechnical_advisory.mitigation_action)))), /* @__PURE__ */ React.createElement("div", { className: "glass-card", style: { marginBottom: "24px" } }, /* @__PURE__ */ React.createElement("div", { className: "card-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "card-title" }, /* @__PURE__ */ React.createElement("span", null, "\u{1F9E0} TimesFM 8-Hour Subsidence Displacement Forecast")), /* @__PURE__ */ React.createElement("div", { className: "card-subtitle" }, "Target Node: ", /* @__PURE__ */ React.createElement("b", null, selectedNodeId), " | Zero-Shot Time Series Foundation Model with Bayesian Uncertainty")), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: fetchForecast,
      className: "btn-primary",
      style: { padding: "8px 16px" },
      disabled: isLoadingForecast
    },
    isLoadingForecast ? "Computing..." : "Re-run Inference"
  )), forecastData && /* @__PURE__ */ React.createElement("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px", marginBottom: "20px" } }, /* @__PURE__ */ React.createElement("div", { style: { background: "#f8fafc", padding: "14px", borderRadius: "8px", border: "1px solid #e2e8f0" } }, /* @__PURE__ */ React.createElement("div", { style: { fontSize: "11px", fontWeight: "700", color: "#64748b" } }, "CURRENT MOVEMENT"), /* @__PURE__ */ React.createElement("div", { className: "mono-font", style: { fontSize: "20px", fontWeight: "800", color: "#0f172a" } }, forecastData.current_displacement_mm, " mm")), /* @__PURE__ */ React.createElement("div", { style: { background: "#f8fafc", padding: "14px", borderRadius: "8px", border: "1px solid #e2e8f0" } }, /* @__PURE__ */ React.createElement("div", { style: { fontSize: "11px", fontWeight: "700", color: "#64748b" } }, "TIME TO WARNING (50mm)"), /* @__PURE__ */ React.createElement("div", { className: "mono-font", style: { fontSize: "20px", fontWeight: "800", color: forecastData.time_to_warning_hours ? "#d97706" : "#16a34a" } }, forecastData.time_to_warning_hours ? `${forecastData.time_to_warning_hours} hrs` : "No breach (8h)")), /* @__PURE__ */ React.createElement("div", { style: { background: "#f8fafc", padding: "14px", borderRadius: "8px", border: "1px solid #e2e8f0" } }, /* @__PURE__ */ React.createElement("div", { style: { fontSize: "11px", fontWeight: "700", color: "#64748b" } }, "TIME TO EVACUATION (85mm)"), /* @__PURE__ */ React.createElement("div", { className: "mono-font", style: { fontSize: "20px", fontWeight: "800", color: forecastData.time_to_critical_hours ? "#dc2626" : "#16a34a" } }, forecastData.time_to_critical_hours ? `${forecastData.time_to_critical_hours} hrs` : "Clear"))), /* @__PURE__ */ React.createElement("div", { ref: forecastChartRef, className: "chart-container", style: { height: "380px" } })), /* @__PURE__ */ React.createElement("div", { className: "glass-card" }, /* @__PURE__ */ React.createElement("div", { className: "card-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "card-title" }, "3D Geotechnical Subsidence Trough Digital Elevation Model"), /* @__PURE__ */ React.createElement("div", { className: "card-subtitle" }, "Overlying strata deformation above Longwall Panel 4B goaf (Sag: 200m\u2013260m elevation)")), /* @__PURE__ */ React.createElement("span", { className: "status-pill danger" }, "Epicenter Node N13 at Deepest Sag")), /* @__PURE__ */ React.createElement("div", { style: { display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "24px", alignItems: "center" } }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { ref: surface3DRef, className: "chart-container", style: { height: "450px" } })), /* @__PURE__ */ React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: "16px" } }, /* @__PURE__ */ React.createElement("div", { style: { borderRadius: "10px", overflow: "hidden", border: "1px solid #cbd5e1" } }, /* @__PURE__ */ React.createElement(
    "img",
    {
      src: "assets/subsidence_3d_dem.png",
      alt: "Subsidence 3D DEM Reference",
      style: { width: "100%", height: "auto", display: "block" }
    }
  )), /* @__PURE__ */ React.createElement("div", { style: { background: "#f8fafc", padding: "14px", borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "12px", color: "#475569" } }, /* @__PURE__ */ React.createElement("div", { style: { fontWeight: "700", color: "#0f172a", marginBottom: "6px" } }, "GEOTECHNICAL DEM CHARACTERISTICS:"), /* @__PURE__ */ React.createElement("div", { style: { marginBottom: "4px" } }, "\u2022 ", /* @__PURE__ */ React.createElement("b", null, "Trough Geometry"), ": Hyperbolic subsidence basin centered over Longwall Panel 4B extraction chamber."), /* @__PURE__ */ React.createElement("div", { style: { marginBottom: "4px" } }, "\u2022 ", /* @__PURE__ */ React.createElement("b", null, "Elevation Range"), ": 200 meters at deepest apex sag up to 260 meters at unaffected regional ground."), /* @__PURE__ */ React.createElement("div", null, "\u2022 ", /* @__PURE__ */ React.createElement("b", null, "Inflection Point"), ": Maximum tensile strain occurring on the flanks (monitored by N8, N12, N14)."))))));
}
function NodeManagementView({ nodesList, selectedNodeId, setSelectedNodeId, onCommandDispatched }) {
  const [commandType, setCommandType] = useState("TARE_ZERO");
  const [paramInterval, setParamInterval] = useState(5);
  const [paramNotes, setParamNotes] = useState("Routine sensor recalibration by geotechnical engineer");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [auditLogs, setAuditLogs] = useState([]);
  const fetchAuditLogs = useCallback(() => {
    fetch(`${BACKEND_HTTP}/api/commands/history?limit=15`).then((res) => res.json()).then((data) => setAuditLogs(data)).catch((err) => console.warn("Failed to fetch audit log:", err));
  }, []);
  useEffect(() => {
    fetchAuditLogs();
  }, [fetchAuditLogs]);
  const currentPayload = useMemo(() => {
    const payload = {
      target_node: selectedNodeId,
      dispatched_at: (/* @__PURE__ */ new Date()).toISOString(),
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
      payload.duration_ms = 3e3;
    } else if (commandType === "ENTER_LOW_POWER_SLEEP") {
      payload.duty_cycle_ms = 1e4;
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
  return /* @__PURE__ */ React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: "24px" } }, /* @__PURE__ */ React.createElement("div", { className: "node-mgmt-grid" }, /* @__PURE__ */ React.createElement("div", { className: "glass-card" }, /* @__PURE__ */ React.createElement("div", { className: "card-header" }, /* @__PURE__ */ React.createElement("div", { className: "card-title" }, "Two-Way LoRa Remote Dispatch")), /* @__PURE__ */ React.createElement("form", { onSubmit: handleDispatch, className: "command-form" }, /* @__PURE__ */ React.createElement("div", { className: "form-group" }, /* @__PURE__ */ React.createElement("label", { className: "form-label" }, "Target Geotechnical Node"), /* @__PURE__ */ React.createElement(
    "select",
    {
      value: selectedNodeId,
      onChange: (e) => setSelectedNodeId(e.target.value),
      className: "form-select"
    },
    nodesList.map((n) => /* @__PURE__ */ React.createElement("option", { key: n.node_id, value: n.node_id }, n.node_id, " \u2014 ", n.name, " ", n.node_id === "N13" ? "\u26A0\uFE0F [APEX]" : ""))
  )), /* @__PURE__ */ React.createElement("div", { className: "form-group" }, /* @__PURE__ */ React.createElement("label", { className: "form-label" }, "Command Protocol"), /* @__PURE__ */ React.createElement(
    "select",
    {
      value: commandType,
      onChange: (e) => setCommandType(e.target.value),
      className: "form-select"
    },
    /* @__PURE__ */ React.createElement("option", { value: "TARE_ZERO" }, "TARE_ZERO (Reset Displacement Baseline)"),
    /* @__PURE__ */ React.createElement("option", { value: "SET_SAMPLING_RATE" }, "SET_SAMPLING_RATE (Configure Frequency)"),
    /* @__PURE__ */ React.createElement("option", { value: "CALIBRATE_INCLINOMETER" }, "CALIBRATE_INCLINOMETER (Re-Zero Tilt Bias)"),
    /* @__PURE__ */ React.createElement("option", { value: "TRIGGER_LOCAL_SIREN" }, "TRIGGER_LOCAL_SIREN (Fire Early Warning Siren Relay)"),
    /* @__PURE__ */ React.createElement("option", { value: "ACTIVATE_BUZZER" }, "ACTIVATE_BUZZER (Sound On-Node Piezo Buzzer)"),
    /* @__PURE__ */ React.createElement("option", { value: "ENTER_LOW_POWER_SLEEP" }, "ENTER_LOW_POWER_SLEEP (Conserve Battery)"),
    /* @__PURE__ */ React.createElement("option", { value: "TRIGGER_EMERGENCY_BEACON" }, "TRIGGER_EMERGENCY_BEACON (Locator Pulse)"),
    /* @__PURE__ */ React.createElement("option", { value: "RESET_MODEM" }, "RESET_MODEM (Re-Negotiate LoRaWAN)")
  )), commandType === "SET_SAMPLING_RATE" && /* @__PURE__ */ React.createElement("div", { className: "form-group" }, /* @__PURE__ */ React.createElement("label", { className: "form-label" }, "Polling Interval (Seconds)"), /* @__PURE__ */ React.createElement(
    "input",
    {
      type: "number",
      min: "1",
      max: "60",
      value: paramInterval,
      onChange: (e) => setParamInterval(e.target.value),
      className: "form-input"
    }
  )), /* @__PURE__ */ React.createElement("div", { className: "form-group" }, /* @__PURE__ */ React.createElement("label", { className: "form-label" }, "Operational Rationale / Work Order"), /* @__PURE__ */ React.createElement(
    "input",
    {
      type: "text",
      value: paramNotes,
      onChange: (e) => setParamNotes(e.target.value),
      className: "form-input",
      placeholder: "e.g. Work order #8843 longwall pass"
    }
  )), /* @__PURE__ */ React.createElement("div", { className: "form-group" }, /* @__PURE__ */ React.createElement("label", { className: "form-label" }, "Payload Transmission Preview"), /* @__PURE__ */ React.createElement("pre", { className: "code-preview" }, JSON.stringify(currentPayload, null, 2))), /* @__PURE__ */ React.createElement(
    "button",
    {
      type: "submit",
      className: "btn-primary",
      disabled: isSubmitting,
      style: { width: "100%", marginTop: "10px" }
    },
    isSubmitting ? "Transmitting via LoRaWAN Mesh..." : "\u{1F680} Dispatch Command to Node"
  ))), /* @__PURE__ */ React.createElement("div", { className: "glass-card" }, /* @__PURE__ */ React.createElement("div", { className: "card-header" }, /* @__PURE__ */ React.createElement("div", { className: "card-title" }, "Telemetry Command Audit Trail"), /* @__PURE__ */ React.createElement("button", { onClick: fetchAuditLogs, style: { background: "none", border: "none", color: "#0284c7", fontWeight: "700", cursor: "pointer", fontSize: "12px" } }, "\u{1F504} Refresh History")), /* @__PURE__ */ React.createElement("div", { className: "table-responsive" }, /* @__PURE__ */ React.createElement("table", { className: "geo-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Dispatched At"), /* @__PURE__ */ React.createElement("th", null, "Target Node"), /* @__PURE__ */ React.createElement("th", null, "Command"), /* @__PURE__ */ React.createElement("th", null, "Status"), /* @__PURE__ */ React.createElement("th", null, "Response Message"))), /* @__PURE__ */ React.createElement("tbody", null, auditLogs.length === 0 ? /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("td", { colSpan: "5", style: { textAlign: "center", color: "#64748b", padding: "24px" } }, "No commands dispatched in current session.")) : auditLogs.map((log) => /* @__PURE__ */ React.createElement("tr", { key: log.id }, /* @__PURE__ */ React.createElement("td", { className: "mono-font", style: { fontSize: "11px" } }, log.dispatched_at ? new Date(log.dispatched_at).toLocaleTimeString() : "-"), /* @__PURE__ */ React.createElement("td", { style: { fontWeight: "700", color: "#0f172a" } }, log.node_id), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("span", { style: { background: "#e0f2fe", color: "#0369a1", padding: "3px 8px", borderRadius: "4px", fontSize: "11px", fontWeight: "700" } }, log.command_type)), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("span", { className: "status-pill stable", style: { padding: "3px 8px", fontSize: "10px" } }, log.status)), /* @__PURE__ */ React.createElement("td", { style: { fontSize: "12px" } }, log.response_message)))))))), /* @__PURE__ */ React.createElement("div", { className: "glass-card" }, /* @__PURE__ */ React.createElement("div", { className: "card-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "card-title" }, "Comprehensive 21-Node Hardware Inventory"), /* @__PURE__ */ React.createElement("div", { className: "card-subtitle" }, "All 20 surface grid nodes and GW-01 base station with onboard microcontrollers, sensors, and telemetry status")), /* @__PURE__ */ React.createElement("span", { className: "status-pill stable" }, "21/21 Nodes Provisioned")), /* @__PURE__ */ React.createElement("div", { className: "table-responsive" }, /* @__PURE__ */ React.createElement("table", { className: "geo-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Node ID"), /* @__PURE__ */ React.createElement("th", null, "Grid Pos"), /* @__PURE__ */ React.createElement("th", null, "Station Role"), /* @__PURE__ */ React.createElement("th", null, "Microcontroller"), /* @__PURE__ */ React.createElement("th", null, "Sensors Onboard"), /* @__PURE__ */ React.createElement("th", null, "LoRa Radio"), /* @__PURE__ */ React.createElement("th", null, "Status"))), /* @__PURE__ */ React.createElement("tbody", null, nodesList.map((n) => /* @__PURE__ */ React.createElement("tr", { key: n.node_id, style: { background: n.node_id === selectedNodeId ? "#f0f9ff" : "transparent" } }, /* @__PURE__ */ React.createElement("td", { className: "mono-font", style: { fontWeight: "800", color: n.node_id === "N13" ? "#dc2626" : "#0f172a" } }, n.node_id, " ", n.node_id === "N13" ? "\u26A0\uFE0F [APEX]" : ""), /* @__PURE__ */ React.createElement("td", null, n.grid_row ? `R${n.grid_row}:C${n.grid_col}` : "Gateway"), /* @__PURE__ */ React.createElement("td", null, n.name), /* @__PURE__ */ React.createElement("td", { className: "mono-font", style: { fontSize: "11px" } }, n.mcu || "ESP32"), /* @__PURE__ */ React.createElement("td", { style: { fontSize: "11px" } }, [n.tilt_sensor, n.vibe_sensor, n.disp_sensor, n.crack_sensor, n.env_sensor].filter(Boolean).join(" + ") || "All Sensors"), /* @__PURE__ */ React.createElement("td", { className: "mono-font", style: { fontSize: "11px" } }, n.lora_module || "SX1278"), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("span", { className: `status-pill ${n.node_id === "N13" ? "danger" : n.node_id === "GW-01" ? "stable" : ["N8", "N12", "N14"].includes(n.node_id) ? "warning" : "stable"}`, style: { padding: "3px 8px", fontSize: "10px" } }, n.node_id === "N13" ? "CRITICAL" : ["N8", "N12", "N14"].includes(n.node_id) ? "WARNING" : "STABLE")))))))));
}
ReactDOM.createRoot(document.getElementById("root")).render(/* @__PURE__ */ React.createElement(App, null));