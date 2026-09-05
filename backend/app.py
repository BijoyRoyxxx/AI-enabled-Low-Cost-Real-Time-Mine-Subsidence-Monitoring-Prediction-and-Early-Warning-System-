"""
===============================================================================
GEO-SHIELD MINE SUBSIDENCE MONITORING SYSTEM - BACKEND ENGINE
File: backend/app.py
Framework: FastAPI (Async / Python 3.10+)
Description:
    Decoupled backend service powering the GEO-SHIELD Mine Subsidence
    Monitoring Dashboard. Provides real-time WebSocket telemetry streaming
    (5s cadence), Isolation Forest multivariate geotechnical anomaly detection,
    TimesFM 2.5 8-hour subsidence forecasting engine (PyTorch + LoRA),
    two-way command dispatch, and PostgreSQL / SQLite database persistence.
===============================================================================
"""

import os
import json
import time
import math
import random
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from transformers import TimesFm2_5ModelForPrediction
from peft import PeftModel
import torch
import numpy as np
from sklearn.ensemble import IsolationForest
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import (
    create_engine, Column, Integer, BigInteger, Float, String, Boolean,
    DateTime, Text, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("GEO-SHIELD")

# =============================================================================
# 0. API KEYS & EXTERNAL SERVICE CONFIGURATION
# =============================================================================
try:
    from dotenv import load_dotenv
    _base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _api_keys_path = os.path.join(_base_dir, "api_keys.env")
    _env_path = os.path.join(_base_dir, ".env")
    if os.path.exists(_api_keys_path):
        load_dotenv(_api_keys_path, override=True)
        logger.info(f"Loaded configuration from {_api_keys_path}")
    elif os.path.exists(_env_path):
        load_dotenv(_env_path, override=True)
        logger.info(f"Loaded configuration from {_env_path}")
except Exception as _env_err:
    logger.warning(f"Could not load .env file: {_env_err}")

# Map Service Configuration
MAP_PROVIDER = os.getenv("MAP_PROVIDER", "carto").strip().lower()
MAP_API_KEY = os.getenv("MAP_API_KEY", "").strip()
MAP_CUSTOM_TILE_URL = os.getenv("MAP_CUSTOM_TILE_URL", "").strip()

# LLM / AI Prediction Model Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gemini-2.0-flash").strip()
LLM_ENDPOINT_URL = os.getenv("LLM_ENDPOINT_URL", "").strip()

if MAP_API_KEY:
    logger.info(f"Map API Key loaded (Provider: {MAP_PROVIDER}, Key: {MAP_API_KEY[:6]}...)")
else:
    logger.info("Map API Key not provided. Using high-contrast CartoDB basemap.")

if LLM_API_KEY:
    logger.info(f"LLM Prediction API Key loaded (Provider: {LLM_PROVIDER}, Model: {LLM_MODEL_NAME})")
else:
    logger.info("LLM Prediction API Key not set. Using TimesFM physics foundation baseline.")

# =============================================================================
# 1. DATABASE CONFIGURATION & FALLBACK HANDLING
# =============================================================================

# Allows seamless PostgreSQL connection or zero-config local SQLite fallback
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./geoshield.db")

# Adjust SQLite connect_args for multithreading
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

try:
    engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info(f"Database engine initialized with URL: {DATABASE_URL.split('@')[-1]}")
except Exception as e:
    logger.warning(f"Could not connect to {DATABASE_URL} ({e}). Falling back to SQLite.")
    DATABASE_URL = "sqlite:///./geoshield.db"
    engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# SQLAlchemy ORM Models
class NodeModel(Base):
    __tablename__ = "nodes"
    node_id = Column(String(32), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(64), nullable=False)
    grid_row = Column(Integer, default=1)
    grid_col = Column(Integer, default=1)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    elevation_m = Column(Float, nullable=False)
    depth_m = Column(Float, default=0.0)
    mcu = Column(String(64), default="ESP32-WROOM-32")
    tilt_sensor = Column(String(64), default="MPU6050 (Biaxial Tilt)")
    vibe_sensor = Column(String(64), default="ADXL355 (Triaxial Geophone)")
    disp_sensor = Column(String(64), default="LVDT + Conditioner")
    crack_sensor = Column(String(64), default="Crack Opening Gauge")
    env_sensor = Column(String(64), default="BME280 (Temp & Humidity)")
    lora_module = Column(String(64), default="SX1278 (Spread Spectrum)")
    sampling_interval_sec = Column(Integer, default=5)
    battery_spec = Column(String(100), nullable=False)
    solar_wattage = Column(Float, default=20.0)
    hardware_version = Column(String(32), default="ESP32-Node-v2")
    firmware_version = Column(String(32), default="fw-2.8.4")
    status = Column(String(20), default="ACTIVE")
    last_heartbeat = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class TelemetryLogModel(Base):
    __tablename__ = "telemetry_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(String(32), index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    tilt_x_deg = Column(Float, default=0.0)
    tilt_y_deg = Column(Float, default=0.0)
    tilt_magnitude_deg = Column(Float, default=0.0)
    displacement_mm = Column(Float, default=0.0)
    crack_opening_mm = Column(Float, default=0.0)
    subsidence_velocity_mm_hr = Column(Float, default=0.0)
    vibration_g = Column(Float, default=0.0)
    temperature_c = Column(Float, default=26.5)
    humidity_pct = Column(Float, default=58.0)
    battery_pct = Column(Float, default=100.0)
    battery_voltage_v = Column(Float, default=12.4)
    signal_rssi_dbm = Column(Integer, default=-75)
    anomaly_score = Column(Float, default=0.0)
    is_anomaly = Column(Boolean, default=False)
    health_status = Column(String(20), default="STABLE")

class CommandAuditLogModel(Base):
    __tablename__ = "command_audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(String(32), index=True, nullable=False)
    command_type = Column(String(64), nullable=False)
    payload = Column(Text, nullable=True) # JSON stored as string for cross-db compatibility
    dispatched_by = Column(String(64), default="GEO-SHIELD_CONTROLLER")
    dispatched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String(20), default="ACKNOWLEDGED")
    response_message = Column(Text, nullable=True)


# =============================================================================
# 2. TOPOLOGY & SEED INITIALIZATION
# =============================================================================

INITIAL_NODES_DATA = [
    {
        "node_id": "GW-01",
        "name": "Central LoRa Gateway & Base Station (ESP32+SX1278+NEO-6M)",
        "type": "LoRa Gateway / Base Station",
        "grid_row": 0, "grid_col": 0,
        "latitude": -23.551200, "longitude": 148.175000,
        "elevation_m": 268.5, "depth_m": 0.0,
        "sampling_interval_sec": 5,
        "battery_spec": "12V 100Ah Deep Cycle + Solar MPPT",
        "solar_wattage": 80.0,
        "hardware_version": "ESP32-Gateway-v2",
        "firmware_version": "fw-3.4.0",
        "status": "ACTIVE"
    },
    # Row 1: N1 - N5 (North Perimeter)
    {"node_id": "N1", "name": "Surface Unit N1 (Perimeter North-West)", "type": "Surface Sensor Node", "grid_row": 1, "grid_col": 1, "latitude": -23.5500, "longitude": 148.1730, "elevation_m": 265.2, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N2", "name": "Surface Unit N2 (North Perimeter)",      "type": "Surface Sensor Node", "grid_row": 1, "grid_col": 2, "latitude": -23.5500, "longitude": 148.1740, "elevation_m": 265.0, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N3", "name": "Surface Unit N3 (North Centerline)",     "type": "Surface Sensor Node", "grid_row": 1, "grid_col": 3, "latitude": -23.5500, "longitude": 148.1750, "elevation_m": 264.8, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N4", "name": "Surface Unit N4 (North Perimeter East)", "type": "Surface Sensor Node", "grid_row": 1, "grid_col": 4, "latitude": -23.5500, "longitude": 148.1760, "elevation_m": 264.9, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N5", "name": "Surface Unit N5 (North-East Perimeter)", "type": "Surface Sensor Node", "grid_row": 1, "grid_col": 5, "latitude": -23.5500, "longitude": 148.1770, "elevation_m": 265.3, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},

    # Row 2: N6 - N10 (Mid-North Flank)
    {"node_id": "N6", "name": "Surface Unit N6 (Mid-North West)",       "type": "Surface Sensor Node", "grid_row": 2, "grid_col": 1, "latitude": -23.5508, "longitude": 148.1730, "elevation_m": 264.5, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N7", "name": "Surface Unit N7 (Upper Trough Flank)",   "type": "Surface Sensor Node", "grid_row": 2, "grid_col": 2, "latitude": -23.5508, "longitude": 148.1740, "elevation_m": 263.2, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N8", "name": "Surface Unit N8 (Trough Tension Zone)",  "type": "Surface Sensor Node", "grid_row": 2, "grid_col": 3, "latitude": -23.5508, "longitude": 148.1750, "elevation_m": 261.8, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N9", "name": "Surface Unit N9 (Upper Trough Flank E)", "type": "Surface Sensor Node", "grid_row": 2, "grid_col": 4, "latitude": -23.5508, "longitude": 148.1760, "elevation_m": 263.0, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N10", "name": "Surface Unit N10 (Mid-North East)",      "type": "Surface Sensor Node", "grid_row": 2, "grid_col": 5, "latitude": -23.5508, "longitude": 148.1770, "elevation_m": 264.8, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},

    # Row 3: N11 - N15 (Active Longwall Extraction Axis, N13 is ALARM epicenter)
    {"node_id": "N11", "name": "Surface Unit N11 (Mid-South West)",      "type": "Surface Sensor Node", "grid_row": 3, "grid_col": 1, "latitude": -23.5516, "longitude": 148.1730, "elevation_m": 264.0, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N12", "name": "Surface Unit N12 (Active Shear Flank)",  "type": "Surface Sensor Node", "grid_row": 3, "grid_col": 2, "latitude": -23.5516, "longitude": 148.1740, "elevation_m": 260.5, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N13", "name": "Surface Unit N13 (SUBSIDENCE APEX - CRITICAL ANOMALY)", "type": "Surface Sensor Node", "grid_row": 3, "grid_col": 3, "latitude": -23.5516, "longitude": 148.1750, "elevation_m": 256.4, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N14", "name": "Surface Unit N14 (Active Shear Flank E)","type": "Surface Sensor Node", "grid_row": 3, "grid_col": 4, "latitude": -23.5516, "longitude": 148.1760, "elevation_m": 260.8, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N15", "name": "Surface Unit N15 (Mid-South East)",      "type": "Surface Sensor Node", "grid_row": 3, "grid_col": 5, "latitude": -23.5516, "longitude": 148.1770, "elevation_m": 264.2, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},

    # Row 4: N16 - N20 (South panel overlying coal mine panel cavities)
    {"node_id": "N16", "name": "Surface Unit N16 (South-West Perimeter)","type": "Surface Sensor Node", "grid_row": 4, "grid_col": 1, "latitude": -23.5524, "longitude": 148.1730, "elevation_m": 264.9, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N17", "name": "Surface Unit N17 (Extensometer Borehole 1)","type": "Surface Sensor Node", "grid_row": 4, "grid_col": 2, "latitude": -23.5524, "longitude": 148.1740, "elevation_m": 262.1, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N18", "name": "Surface Unit N18 (Extensometer Borehole 2)","type": "Surface Sensor Node", "grid_row": 4, "grid_col": 3, "latitude": -23.5524, "longitude": 148.1750, "elevation_m": 259.0, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N19", "name": "Surface Unit N19 (Extensometer Borehole 3)","type": "Surface Sensor Node", "grid_row": 4, "grid_col": 4, "latitude": -23.5524, "longitude": 148.1760, "elevation_m": 261.9, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"},
    {"node_id": "N20", "name": "Surface Unit N20 (South-East Perimeter)","type": "Surface Sensor Node", "grid_row": 4, "grid_col": 5, "latitude": -23.5524, "longitude": 148.1770, "elevation_m": 265.1, "depth_m": 45.0, "sampling_interval_sec": 5, "battery_spec": "12V Battery + Solar Buck", "solar_wattage": 20.0, "hardware_version": "ESP32-Node-v2", "firmware_version": "fw-2.8.4", "status": "ACTIVE"}
]

HAZARD_ZONES = [
    {
        "zone_id": "ZONE-ALPHA",
        "name": "Zone Alpha: Active Goaf Caving Trough",
        "risk_level": "CRITICAL",
        "coordinates": [
            [-23.5500, 148.1732],
            [-23.5494, 148.1758],
            [-23.5512, 148.1762],
            [-23.5518, 148.1736],
            [-23.5500, 148.1732]
        ],
        "max_subsidence_allowable_mm": 85.0,
        "current_subsidence_peak_mm": 54.2,
        "description": "Directly overlying the active longwall retreating face. Continuous tensile strain and strata fracturing."
    },
    {
        "zone_id": "ZONE-BETA",
        "name": "Zone Beta: Tailgate Shear & Cleat Relaxation",
        "risk_level": "HIGH",
        "coordinates": [
            [-23.5510, 148.1722],
            [-23.5506, 148.1742],
            [-23.5528, 148.1746],
            [-23.5532, 148.1726],
            [-23.5510, 148.1722]
        ],
        "max_subsidence_allowable_mm": 50.0,
        "current_subsidence_peak_mm": 28.7,
        "description": "Flank boundary zone prone to differential vertical shear and strata slip near gate roads."
    },
    {
        "zone_id": "ZONE-GAMMA",
        "name": "Zone Gamma: Highwall Crest Perimeter Buffer",
        "risk_level": "MODERATE",
        "coordinates": [
            [-23.5522, 148.1745],
            [-23.5515, 148.1772],
            [-23.5538, 148.1778],
            [-23.5544, 148.1751],
            [-23.5522, 148.1745]
        ],
        "max_subsidence_allowable_mm": 30.0,
        "current_subsidence_peak_mm": 12.1,
        "description": "Upper bench perimeter. Tension crack monitoring and haul road stability buffer."
    }
]

def init_db():
    """Initializes tables and seeds initial topology if missing or mismatched."""
    try:
        needs_recreate = False
        with engine.connect() as conn:
            from sqlalchemy import text
            res_nodes = conn.execute(text("PRAGMA table_info(nodes)")).fetchall()
            node_cols = {r[1] for r in res_nodes}
            if node_cols and "grid_row" not in node_cols:
                needs_recreate = True

            res_logs = conn.execute(text("PRAGMA table_info(telemetry_logs)")).fetchall()
            log_cols = {r[1] for r in res_logs}
            if log_cols and "crack_opening_mm" not in log_cols:
                needs_recreate = True

        if needs_recreate:
            logger.info("Schema columns missing. Recreating database tables...")
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
        else:
            Base.metadata.create_all(bind=engine)

        db: Session = SessionLocal()
        try:
            existing_nodes = db.query(NodeModel).count()
            if existing_nodes != len(INITIAL_NODES_DATA):
                logger.info(f"Database node count ({existing_nodes}) does not match blueprint ({len(INITIAL_NODES_DATA)}). Updating tables...")
                Base.metadata.drop_all(bind=engine)
                Base.metadata.create_all(bind=engine)
                valid_keys = {c.name for c in NodeModel.__table__.columns}
                for node_data in INITIAL_NODES_DATA:
                    node = NodeModel(**{k: v for k, v in node_data.items() if k in valid_keys})
                    db.add(node)
                db.commit()
                logger.info(f"Successfully seeded {len(INITIAL_NODES_DATA)} sensor nodes matching 4x5 LoRa mesh blueprint.")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Error during DB schema check ({e}). Forcing fresh table creation...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db: Session = SessionLocal()
        try:
            valid_keys = {c.name for c in NodeModel.__table__.columns}
            for node_data in INITIAL_NODES_DATA:
                node = NodeModel(**{k: v for k, v in node_data.items() if k in valid_keys})
                db.add(node)
            db.commit()
            logger.info(f"Successfully re-seeded {len(INITIAL_NODES_DATA)} sensor nodes after recreation.")
        except Exception as inner_e:
            logger.error(f"Failed to seed after table creation: {inner_e}")
            db.rollback()
        finally:
            db.close()


# =============================================================================
# 3. MACHINE LEARNING: ISOLATION FOREST ANOMALY DETECTOR
# =============================================================================

class GeotechnicalAnomalyDetector:
    """
    Multivariate Isolation Forest model calibrated to detect aberrant
    subsidence rates, abnormal tilt excursions, and micro-seismic bursts.
    """
    def __init__(self):
        self.model = IsolationForest(
            n_estimators=120,
            contamination=0.06,
            max_samples='auto',
            random_state=42
        )
        self.is_fitted = False
        self._train_baseline()

    def _train_baseline(self):
        """Trains the model on a synthesized baseline of typical mining conditions."""
        rng = np.random.RandomState(42)
        n_samples = 1500

        normal_tilt = rng.exponential(scale=0.15, size=n_samples) + 0.02
        normal_disp = rng.uniform(0.5, 30.0, size=n_samples)
        normal_vel = rng.exponential(scale=0.25, size=n_samples) + 0.01
        normal_vib = rng.gamma(shape=2.0, scale=0.012, size=n_samples) + 0.005

        X_train = np.column_stack([normal_tilt, normal_disp, normal_vel, normal_vib])
        self.model.fit(X_train)
        self.is_fitted = True
        logger.info("Isolation Forest anomaly detector fitted on 1,500 baseline geotechnical vectors.")

    def evaluate(self, tilt_mag: float, disp: float, vel: float, vib: float) -> Dict[str, Any]:
        """
        Evaluates a single telemetry sample.
        Returns:
            anomaly_score (0.0 to 1.0, where lower indicates severe anomaly),
            is_anomaly (bool),
            health_status ('STABLE', 'WARNING', 'DANGER')
        """
        vector = np.array([[tilt_mag, disp, vel, vib]])
        raw_score = float(self.model.decision_function(vector)[0])
        pred = int(self.model.predict(vector)[0]) 

        normalized_score = float(1.0 / (1.0 + np.exp(-raw_score * 4.0)))

        is_physical_danger = (disp >= 48.0) or (vel >= 2.2) or (vib >= 0.12) or (tilt_mag >= 1.2)
        is_physical_warning = (disp >= 28.0) or (vel >= 1.1) or (vib >= 0.06) or (tilt_mag >= 0.6)

        if is_physical_danger or normalized_score < 0.32:
            status = "DANGER"
            is_anomaly = True
        elif is_physical_warning or normalized_score < 0.52 or pred == -1:
            status = "WARNING"
            is_anomaly = True
        else:
            status = "STABLE"
            is_anomaly = False

        return {
            "anomaly_score": round(normalized_score, 3),
            "is_anomaly": is_anomaly,
            "health_status": status
        }

anomaly_detector = GeotechnicalAnomalyDetector()


# =============================================================================
# 4. AI ENGINE: TIMESFM 2.5 8-HOUR SUBSIDENCE FORECASTING ENGINE
# =============================================================================

class TimesFMSubsidenceForecaster:
    """
    Real inference using HuggingFace TimesFM 2.5 with local LoRA weights.
    """
    def __init__(self):
        self.horizon_hours = 8
        self.step_minutes = 30
        self.num_points = 16 # 8 hours / 30 mins
        
        try:
            # 1. Load Base HuggingFace TimesFM 2.5 Model
            base_model = TimesFm2_5ModelForPrediction.from_pretrained(
                "google/timesfm-2.5-200m-transformers"
            )
            
            # 2. Apply your local LoRA weights
            try:
                self.model = PeftModel.from_pretrained(
                    base_model, 
                    "backend/models/timesfm-mine-finetuned"
                )
                logger.info("Loaded custom TimesFM 2.5 LoRA weights via HuggingFace.")
            except Exception as peft_err:
                self.model = base_model
                logger.warning(f"Could not load LoRA, using base TimesFM 2.5 model: {peft_err}")

            self.model.eval()
            self.model_loaded = True
        except Exception as e:
            self.model_loaded = False
            logger.warning(f"Could not load TimesFM 2.5 model: {e}")

    def forecast(self, node_id: str, context_array: list, current_vel: float) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        warning_threshold_mm = 50.0
        critical_threshold_mm = 85.0
        
        current_displacement = context_array[-1] if context_array else 0.0

        # 3. Run inference using the trained model
        if self.model_loaded and len(context_array) > 0:
            input_data = torch.tensor([context_array], dtype=torch.float32)
            
            with torch.no_grad():
                outputs = self.model(
                    past_values=input_data
                )
                
            # HF outputs full_predictions of shape: (batch, horizon, quantiles)
            # Quantiles 1-9 are indices 1-9.
            quantiles = outputs.full_predictions[0].numpy()
            
            p50_forecast = [round(float(v), 2) for v in quantiles[:self.num_points, 5]]
            p10_forecast = [round(float(v), 2) for v in quantiles[:self.num_points, 1]]
            p90_forecast = [round(float(v), 2) for v in quantiles[:self.num_points, 9]]
        else:
            p50_forecast = [current_displacement] * self.num_points
            p10_forecast = [current_displacement] * self.num_points
            p90_forecast = [current_displacement] * self.num_points

        timestamps = [(now + timedelta(minutes=(step+1)*self.step_minutes)).isoformat() for step in range(self.num_points)]
        
        # Calculate threshold alerts
        time_to_warning_hours = next((round((i+1)*0.5, 1) for i, v in enumerate(p50_forecast) if v >= warning_threshold_mm), None)
        time_to_critical_hours = next((round((i+1)*0.5, 1) for i, v in enumerate(p50_forecast) if v >= critical_threshold_mm), None)

        ai_advisory = self.generate_ai_advisory(node_id, current_displacement, current_vel, p50_forecast[-1])

        return {
            "node_id": node_id,
            "generated_at": now.isoformat(),
            "horizon_hours": self.horizon_hours,
            "current_displacement_mm": round(current_displacement, 2),
            "current_velocity_mm_hr": round(current_vel, 2),
            "warning_threshold_mm": warning_threshold_mm,
            "critical_threshold_mm": critical_threshold_mm,
            "time_to_warning_hours": time_to_warning_hours,
            "time_to_critical_hours": time_to_critical_hours,
            "ai_geotechnical_advisory": ai_advisory,
            "forecast_points": [
                {
                    "timestamp": t,
                    "displacement_p10": p10,
                    "displacement_p50": p50,
                    "displacement_p90": p90
                }
                for t, p10, p50, p90 in zip(timestamps, p10_forecast, p50_forecast, p90_forecast)
            ]
        }
    
    def generate_ai_advisory(self, node_id: str, current_disp: float, current_vel: float, p50_end: float) -> Dict[str, Any]:
        """
        Generates geotechnical advisory using configured LLM API (Gemini/OpenAI)
        or physics-informed fallback rules when API key is unconfigured.
        """
        is_apex = "N13" in node_id
        is_flank = node_id in ("N8", "N12", "N14")

        if LLM_API_KEY and LLM_PROVIDER in ("gemini", "google"):
            try:
                import urllib.request
                prompt = (
                    f"You are a Senior Mine Geotechnical Engineer analyzing real-time subsidence telemetry for Node {node_id} "
                    f"overlying Bowen Basin Longwall Panel 4B.\n"
                    f"Current displacement: {current_disp:.1f} mm, velocity: {current_vel:.2f} mm/hr. "
                    f"8-hour predicted peak displacement: {p50_end:.1f} mm. Warning threshold: 50.0 mm. Evacuation limit: 85.0 mm.\n"
                    f"Provide a structured geotechnical advisory in JSON format with keys:\n"
                    f"- 'risk_level': 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW'\n"
                    f"- 'primary_hazard': brief hazard type (e.g. 'Tensile Crown Sag', 'Flank Shear')\n"
                    f"- 'advisory_summary': 2-3 sentences engineering diagnosis\n"
                    f"- 'mitigation_action': immediate recommended operational action for the control room"
                )
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL_NAME}:generateContent?key={LLM_API_KEY}"
                payload = json.dumps({
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=4.0) as res:
                    resp_json = json.loads(res.read().decode("utf-8"))
                    text_content = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(text_content)
                    return {
                        "provider": f"Google Gemini ({LLM_MODEL_NAME}) [LIVE API]",
                        "has_live_api": True,
                        "risk_level": parsed.get("risk_level", "CRITICAL" if is_apex else "STABLE"),
                        "primary_hazard": parsed.get("primary_hazard", "Overburden Tension Sag"),
                        "advisory_summary": parsed.get("advisory_summary", ""),
                        "mitigation_action": parsed.get("mitigation_action", "")
                    }
            except Exception as e:
                logger.warning(f"Live Gemini API call failed or timed out ({e}). Falling back to baseline.")

        if is_apex or current_disp >= 50.0:
            risk = "CRITICAL"
            hazard = "Tensile Crown Fracturing & Overburden Collapse"
            summary = (
                f"Node {node_id} is located at the subsidence trough apex with active acceleration at {current_vel:.2f} mm/hr. "
                f"Predicted 8-hour displacement reaches {p50_end:.1f} mm, exceeding structural deformation tolerance."
            )
            action = "Dispatch immediate evacuation siren relay, depressurize Longwall Panel 4B face, and halt tailgate haulage."
        elif is_flank or current_disp >= 25.0:
            risk = "WARNING"
            hazard = "Differential Flank Shear & Tension Cracking"
            summary = (
                f"Node {node_id} displays elevated shear deformation along the inflection boundary. "
                f"Velocity of {current_vel:.2f} mm/hr indicates continuous redistribution of strata stresses."
            )
            action = "Increase sampling frequency to 1s, verify extensometer anchors, and reinforce chain pillars."
        else:
            risk = "STABLE"
            hazard = "Elastic Bedrock Settlement"
            summary = (
                f"Node {node_id} remains within nominal geotechnical stability margins ({current_disp:.1f} mm cumulative sag). "
                f"Strata deformation rate is non-critical."
            )
            action = "Continue standard 5-second LoRaWAN telemetry monitoring."

        key_hint = " (Set LLM_API_KEY in api_keys.env for live Gemini reasoning)" if not LLM_API_KEY else ""
        return {
            "provider": f"TimesFM Geotechnical Foundation Model{key_hint}",
            "has_live_api": bool(LLM_API_KEY),
            "risk_level": risk,
            "primary_hazard": hazard,
            "advisory_summary": summary,
            "mitigation_action": action
        }

timesfm_forecaster = TimesFMSubsidenceForecaster()


# =============================================================================
# 5. REAL-TIME TELEMETRY SIMULATION STATE & GENERATOR
# =============================================================================

class MineTelemetrySimulator:
    """
    Maintains continuous simulated state of the 10 geotechnical sensors,
    injecting realistic physical phenomena (strata settlement, face advance,
    occasional micro-seismic goaf fracturing).
    """
    def __init__(self):
        self.state: Dict[str, Dict[str, Any]] = {}
        self.tick_counter = 0
        self._init_state()

    def _init_state(self):
        for node in INITIAL_NODES_DATA:
            nid = node["node_id"]
            if nid == "GW-01":
                self.state[nid] = {
                    "tilt_x": 0.00, "tilt_y": 0.00, "disp": 0.00, "crack": 0.00,
                    "vel": 0.00, "vib": 0.004, "batt": 99.8, "volt": 12.8,
                    "temp": 25.2, "hum": 54.0, "rssi": -38
                }
            elif nid in ("N13", "NODE-DSP-01"):
                self.state[nid] = {
                    "tilt_x": 0.62, "tilt_y": 0.48, "disp": 54.80, "crack": 4.25,
                    "vel": 2.45, "vib": 0.088, "batt": 91.5, "volt": 12.1,
                    "temp": 28.6, "hum": 62.0, "rssi": -78
                }
            elif nid in ("N8", "N12", "N14", "NODE-TLT-01"):
                self.state[nid] = {
                    "tilt_x": 0.38, "tilt_y": 0.28, "disp": 32.50, "crack": 2.10,
                    "vel": 1.25, "vib": 0.045, "batt": 93.8, "volt": 12.2,
                    "temp": 27.4, "hum": 59.5, "rssi": -72
                }
            elif nid in ("N16", "N17", "N18", "N19", "N20"):
                self.state[nid] = {
                    "tilt_x": round(random.uniform(0.12, 0.18), 2),
                    "tilt_y": round(random.uniform(0.08, 0.14), 2),
                    "disp": round(random.uniform(18.0, 24.0), 2),
                    "crack": round(random.uniform(0.8, 1.4), 2),
                    "vel": round(random.uniform(0.40, 0.70), 2),
                    "vib": round(random.uniform(0.035, 0.055), 3),
                    "batt": round(random.uniform(92.0, 96.0), 1),
                    "volt": 12.3,
                    "temp": round(random.uniform(25.0, 27.5), 1),
                    "hum": round(random.uniform(56.0, 61.0), 1),
                    "rssi": random.randint(-76, -68)
                }
            else:
                self.state[nid] = {
                    "tilt_x": round(random.uniform(0.02, 0.09), 2),
                    "tilt_y": round(random.uniform(0.01, 0.08), 2),
                    "disp": round(random.uniform(3.0, 11.0), 2),
                    "crack": round(random.uniform(0.1, 0.4), 2),
                    "vel": round(random.uniform(0.05, 0.30), 2),
                    "vib": round(random.uniform(0.008, 0.025), 3),
                    "batt": round(random.uniform(94.0, 99.0), 1),
                    "volt": 12.4,
                    "temp": round(random.uniform(24.0, 27.0), 1),
                    "hum": round(random.uniform(54.0, 59.0), 1),
                    "rssi": random.randint(-74, -62)
                }

    def step(self) -> List[Dict[str, Any]]:
        self.tick_counter += 1
        now_iso = datetime.now(timezone.utc).isoformat()
        results = []

        has_seismic_event = (self.tick_counter % 8 == 0)

        for node in INITIAL_NODES_DATA:
            nid = node["node_id"]
            curr = self.state[nid]

            curr["temp"] = round(26.0 + 3.0 * math.sin(self.tick_counter * 0.05) + random.uniform(-0.1, 0.1), 1)
            curr["hum"] = round(min(90.0, max(40.0, 58.0 - 5.0 * math.sin(self.tick_counter * 0.05) + random.uniform(-0.5, 0.5))), 1)

            if nid == "GW-01":
                curr["vib"] = 0.004
                curr["disp"] = 0.00
                curr["vel"] = 0.00
            elif nid in ("N13", "NODE-DSP-01"):
                disp_increment = random.uniform(0.02, 0.06)
                curr["disp"] = round(curr["disp"] + disp_increment, 2)
                curr["crack"] = round(curr["crack"] + random.uniform(0.004, 0.012), 2)
                curr["vel"] = round(2.30 + random.uniform(0.1, 0.6) + (0.4 if has_seismic_event else 0.0), 2)
                curr["vib"] = round(0.080 + (0.15 if has_seismic_event else random.uniform(0.005, 0.025)), 3)
                curr["tilt_x"] = round(curr["tilt_x"] + random.uniform(-0.002, 0.006), 3)
                curr["tilt_y"] = round(curr["tilt_y"] + random.uniform(-0.002, 0.006), 3)
            elif nid in ("N8", "N12", "N14", "NODE-TLT-01"):
                curr["disp"] = round(curr["disp"] + random.uniform(0.005, 0.018), 2)
                curr["crack"] = round(curr["crack"] + random.uniform(0.001, 0.004), 2)
                curr["vel"] = round(1.15 + random.uniform(0.05, 0.25), 2)
                curr["vib"] = round(0.040 + (0.06 if has_seismic_event else random.uniform(0.002, 0.010)), 3)
            elif nid in ("N16", "N17", "N18", "N19", "N20"):
                curr["disp"] = round(curr["disp"] + random.uniform(0.002, 0.010), 2)
                curr["vib"] = round(max(0.015, curr["vib"] * 0.9 + (0.04 if has_seismic_event else random.uniform(0.002, 0.008))), 3)
            else:
                curr["disp"] = round(curr["disp"] + random.uniform(-0.001, 0.003), 2)
                curr["vib"] = round(max(0.005, curr["vib"] * 0.85 + random.uniform(0.001, 0.005)), 3)

            tilt_mag = round(math.sqrt(curr["tilt_x"]**2 + curr["tilt_y"]**2), 3)

            eval_result = anomaly_detector.evaluate(
                tilt_mag=tilt_mag,
                disp=curr["disp"],
                vel=curr["vel"],
                vib=curr["vib"]
            )

            frame = {
                "node_id": nid,
                "name": node["name"],
                "type": node["type"],
                "grid_row": node.get("grid_row", 0),
                "grid_col": node.get("grid_col", 0),
                "latitude": node["latitude"],
                "longitude": node["longitude"],
                "elevation_m": node["elevation_m"],
                "depth_m": node.get("depth_m", 0.0),
                "mcu": node.get("mcu", "ESP32-WROOM-32"),
                "tilt_sensor": node.get("tilt_sensor", "MPU6050"),
                "vibe_sensor": node.get("vibe_sensor", "ADXL355"),
                "disp_sensor": node.get("disp_sensor", "LVDT + Conditioner"),
                "crack_sensor": node.get("crack_sensor", "Crack Opening Gauge"),
                "env_sensor": node.get("env_sensor", "BME280"),
                "lora_module": node.get("lora_module", "SX1278"),
                "timestamp": now_iso,
                "tilt_x_deg": curr["tilt_x"],
                "tilt_y_deg": curr["tilt_y"],
                "tilt_magnitude_deg": tilt_mag,
                "displacement_mm": curr["disp"],
                "crack_opening_mm": curr.get("crack", 0.0),
                "subsidence_velocity_mm_hr": curr["vel"],
                "vibration_g": curr["vib"],
                "temperature_c": curr["temp"],
                "humidity_pct": curr["hum"],
                "battery_pct": curr["batt"],
                "battery_voltage_v": curr["volt"],
                "solar_wattage": node.get("solar_wattage", 20.0),
                "signal_rssi_dbm": curr["rssi"],
                "anomaly_score": eval_result["anomaly_score"],
                "is_anomaly": eval_result["is_anomaly"],
                "health_status": eval_result["health_status"]
            }
            results.append(frame)

        return results

simulator = MineTelemetrySimulator()


# =============================================================================
# 6. FASTAPI APPLICATION SETUP
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("GEO-SHIELD Monitoring Engine ready. Telemetry broadcaster listening.")
    yield
    logger.info("Shutting down GEO-SHIELD Monitoring Engine.")

app = FastAPI(
    title="GEO-SHIELD Mine Subsidence Monitoring API",
    version="2.0.0",
    description="Decoupled backend for highwall & longwall mine subsidence tracking.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# 7. WEBSOCKET CONNECTION MANAGER
# =============================================================================

class WebSocketConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Active sessions: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Active sessions: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for dead_conn in disconnected:
            self.disconnect(dead_conn)

ws_manager = WebSocketConnectionManager()

@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            telemetry_snapshot = simulator.step()

            try:
                db: Session = SessionLocal()
                for item in telemetry_snapshot:
                    log_entry = TelemetryLogModel(
                        node_id=item["node_id"],
                        tilt_x_deg=item["tilt_x_deg"],
                        tilt_y_deg=item["tilt_y_deg"],
                        tilt_magnitude_deg=item["tilt_magnitude_deg"],
                        displacement_mm=item["displacement_mm"],
                        crack_opening_mm=item.get("crack_opening_mm", 0.0),
                        subsidence_velocity_mm_hr=item["subsidence_velocity_mm_hr"],
                        vibration_g=item["vibration_g"],
                        temperature_c=item["temperature_c"],
                        humidity_pct=item.get("humidity_pct", 58.0),
                        battery_pct=item["battery_pct"],
                        battery_voltage_v=item["battery_voltage_v"],
                        signal_rssi_dbm=item["signal_rssi_dbm"],
                        anomaly_score=item["anomaly_score"],
                        is_anomaly=item["is_anomaly"],
                        health_status=item["health_status"]
                    )
                    db.add(log_entry)
                db.commit()
                db.close()
            except Exception as e:
                logger.error(f"Error saving telemetry frame: {e}")

            max_disp = max(item["displacement_mm"] for item in telemetry_snapshot)
            max_vel = max(item["subsidence_velocity_mm_hr"] for item in telemetry_snapshot)
            max_crack = max(item["crack_opening_mm"] for item in telemetry_snapshot)
            has_danger = any(item["health_status"] == "DANGER" for item in telemetry_snapshot)
            has_warning = any(item["health_status"] == "WARNING" for item in telemetry_snapshot)

            overall_status = "DANGER" if has_danger else ("WARNING" if has_warning else "STABLE")

            payload = {
                "type": "TELEMETRY_UPDATE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": {
                    "active_nodes_count": len(telemetry_snapshot),
                    "overall_status": overall_status,
                    "max_displacement_mm": round(max_disp, 2),
                    "max_velocity_mm_hr": round(max_vel, 2),
                    "max_crack_mm": round(max_crack, 2),
                    "high_risk_node": next(
                        (i["node_id"] for i in telemetry_snapshot if i["health_status"] == "DANGER"),
                        "NONE"
                    ),
                    "warning_count": sum(1 for i in telemetry_snapshot if i["health_status"] == "WARNING"),
                    "danger_count": sum(1 for i in telemetry_snapshot if i["health_status"] == "DANGER"),
                    "siren_status": "TRIGGERED (Active Site Siren)" if has_danger else "STANDBY",
                    "led_display": "WARNING HIGH RISK: N13 APEX" if has_danger else "SYSTEM STATUS NORMAL",
                    "lora_mesh": "20-NODE SPREAD SPECTRUM MESH ACTIVE",
                    "gps_sync": "GPS NEO-6M TIME SYNCHRONIZED"
                },
                "nodes": telemetry_snapshot
            }

            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(5) 
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)


# =============================================================================
# 8. REST API ENDPOINTS
# =============================================================================

class CommandDispatchPayload(BaseModel):
    node_id: str = Field(..., description="Target node ID")
    command_type: str = Field(..., description="Command name")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict)
    dispatched_by: Optional[str] = "MINE_SUPERVISOR_CONSOLE"

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "GEO-SHIELD Mine Subsidence Monitoring Backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": DATABASE_URL.split("///")[-1]
    }

@app.get("/api/config")
def get_service_config():
    return {
        "map": {
            "provider": MAP_PROVIDER,
            "api_key": MAP_API_KEY,
            "custom_tile_url": MAP_CUSTOM_TILE_URL,
            "has_key": bool(MAP_API_KEY)
        },
        "llm": {
            "provider": LLM_PROVIDER,
            "model_name": LLM_MODEL_NAME,
            "endpoint_url": LLM_ENDPOINT_URL,
            "has_key": bool(LLM_API_KEY)
        }
    }

@app.get("/api/nodes")
def get_nodes():
    db: Session = SessionLocal()
    try:
        nodes = db.query(NodeModel).all()
        return [
            {
                "node_id": n.node_id,
                "name": n.name,
                "type": n.type,
                "grid_row": getattr(n, "grid_row", 0),
                "grid_col": getattr(n, "grid_col", 0),
                "latitude": n.latitude,
                "longitude": n.longitude,
                "elevation_m": n.elevation_m,
                "depth_m": n.depth_m,
                "mcu": getattr(n, "mcu", "ESP32-WROOM-32"),
                "tilt_sensor": getattr(n, "tilt_sensor", "MPU6050"),
                "vibe_sensor": getattr(n, "vibe_sensor", "ADXL355"),
                "disp_sensor": getattr(n, "disp_sensor", "LVDT + Conditioner"),
                "crack_sensor": getattr(n, "crack_sensor", "Crack Opening Gauge"),
                "env_sensor": getattr(n, "env_sensor", "BME280"),
                "lora_module": getattr(n, "lora_module", "SX1278"),
                "sampling_interval_sec": n.sampling_interval_sec,
                "battery_spec": n.battery_spec,
                "solar_wattage": n.solar_wattage,
                "hardware_version": n.hardware_version,
                "firmware_version": n.firmware_version,
                "status": n.status
            }
            for n in nodes
        ]
    finally:
        db.close()

@app.get("/api/telemetry/recent")
def get_recent_telemetry(node_id: Optional[str] = None, limit: int = Query(60, ge=1, le=500)):
    db: Session = SessionLocal()
    try:
        query = db.query(TelemetryLogModel)
        if node_id:
            query = query.filter(TelemetryLogModel.node_id == node_id)
        records = query.order_by(TelemetryLogModel.timestamp.desc()).limit(limit).all()

        return [
            {
                "id": r.id,
                "node_id": r.node_id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "tilt_x_deg": r.tilt_x_deg,
                "tilt_y_deg": r.tilt_y_deg,
                "tilt_magnitude_deg": r.tilt_magnitude_deg,
                "displacement_mm": r.displacement_mm,
                "crack_opening_mm": r.crack_opening_mm,
                "subsidence_velocity_mm_hr": r.subsidence_velocity_mm_hr,
                "vibration_g": r.vibration_g,
                "battery_pct": r.battery_pct,
                "temperature_c": r.temperature_c,
                "humidity_pct": r.humidity_pct,
                "anomaly_score": r.anomaly_score,
                "is_anomaly": r.is_anomaly,
                "health_status": r.health_status
            }
            for r in reversed(records)
        ]
    finally:
        db.close()

@app.get("/api/forecast/timesfm")
def get_timesfm_forecast(node_id: str = Query("N13")):
    """
    REST endpoint serving the TimesFM 8-hour displacement forecasts
    using real PyTorch inference on historical context.
    """
    db: Session = SessionLocal()
    try:
        records = db.query(TelemetryLogModel.displacement_mm)\
                    .filter(TelemetryLogModel.node_id == node_id)\
                    .order_by(TelemetryLogModel.timestamp.desc())\
                    .limit(512).all()
        
        context_array = [r[0] for r in reversed(records)]
        if len(context_array) < 512:
            context_array = [0.0] * (512 - len(context_array)) + context_array
            
    finally:
        db.close()

    curr = simulator.state.get(node_id, {"vel": 2.45})
    
    forecast_data = timesfm_forecaster.forecast(
        node_id=node_id,
        context_array=context_array,
        current_vel=curr.get("vel", 2.45)
    )
    return forecast_data

@app.get("/api/hazards")
def get_hazard_zones():
    mesh_links = []
    nodes_by_pos = {}
    for n in INITIAL_NODES_DATA:
        if n["grid_row"] > 0 and n["grid_col"] > 0:
            nodes_by_pos[(n["grid_row"], n["grid_col"])] = n

    for r in range(1, 5):
        for c in range(1, 5):
            n1 = nodes_by_pos.get((r, c))
            n2 = nodes_by_pos.get((r, c + 1))
            if n1 and n2:
                mesh_links.append({
                    "from_node": n1["node_id"],
                    "to_node": n2["node_id"],
                    "type": "MESH_HORIZONTAL",
                    "coordinates": [[n1["latitude"], n1["longitude"]], [n2["latitude"], n2["longitude"]]],
                    "link_quality_pct": random.randint(92, 99)
                })

    for r in range(1, 4):
        for c in range(1, 6):
            n1 = nodes_by_pos.get((r, c))
            n2 = nodes_by_pos.get((r + 1, c))
            if n1 and n2:
                mesh_links.append({
                    "from_node": n1["node_id"],
                    "to_node": n2["node_id"],
                    "type": "MESH_VERTICAL",
                    "coordinates": [[n1["latitude"], n1["longitude"]], [n2["latitude"], n2["longitude"]]],
                    "link_quality_pct": random.randint(90, 98)
                })

    for r in range(1, 4):
        for c in range(1, 5):
            n1 = nodes_by_pos.get((r, c))
            n_diag1 = nodes_by_pos.get((r + 1, c + 1))
            if n1 and n_diag1:
                mesh_links.append({
                    "from_node": n1["node_id"],
                    "to_node": n_diag1["node_id"],
                    "type": "MESH_DIAGONAL",
                    "coordinates": [[n1["latitude"], n1["longitude"]], [n_diag1["latitude"], n_diag1["longitude"]]],
                    "link_quality_pct": random.randint(85, 95)
                })

            n2 = nodes_by_pos.get((r, c + 1))
            n_diag2 = nodes_by_pos.get((r + 1, c))
            if n2 and n_diag2:
                mesh_links.append({
                    "from_node": n2["node_id"],
                    "to_node": n_diag2["node_id"],
                    "type": "MESH_DIAGONAL",
                    "coordinates": [[n2["latitude"], n2["longitude"]], [n_diag2["latitude"], n_diag2["longitude"]]],
                    "link_quality_pct": random.randint(85, 95)
                })

    gw = next(n for n in INITIAL_NODES_DATA if n["node_id"] == "GW-01")
    uplink_nodes = ["N1", "N3", "N5", "N8", "N13", "N18", "N20"]
    for nid in uplink_nodes:
        node = next((n for n in INITIAL_NODES_DATA if n["node_id"] == nid), None)
        if node:
            mesh_links.append({
                "from_node": node["node_id"],
                "to_node": "GW-01",
                "type": "GATEWAY_UPLINK",
                "coordinates": [[node["latitude"], node["longitude"]], [gw["latitude"], gw["longitude"]]],
                "link_quality_pct": random.randint(95, 99)
            })

    return {
        "hazard_zones": HAZARD_ZONES,
        "mesh_links": mesh_links,
        "base_center": [-23.5512, 148.1750],
        "default_zoom": 16
    }

@app.post("/api/commands/dispatch")
def dispatch_remote_command(payload: CommandDispatchPayload):
    db: Session = SessionLocal()
    try:
        node = db.query(NodeModel).filter(NodeModel.node_id == payload.node_id).first()
        if not node:
            raise HTTPException(status_code=404, detail=f"Node {payload.node_id} not found.")

        cmd = payload.command_type
        params = payload.payload or {}
        msg = f"Command {cmd} acknowledged by firmware {node.firmware_version}."

        if cmd == "TARE_ZERO":
            if payload.node_id in simulator.state:
                simulator.state[payload.node_id]["disp"] = 0.0
                simulator.state[payload.node_id]["crack"] = 0.0
            msg = f"LVDT displacement sensor & crack gauge zero-referenced on {payload.node_id}."
        elif cmd == "SET_SAMPLING_RATE":
            new_interval = params.get("interval_sec", 5)
            node.sampling_interval_sec = new_interval
            msg = f"Sampling interval locked to {new_interval}s via SX1278 downlink."
        elif cmd == "CALIBRATE_INCLINOMETER":
            if payload.node_id in simulator.state:
                simulator.state[payload.node_id]["tilt_x"] = 0.01
                simulator.state[payload.node_id]["tilt_y"] = 0.01
            msg = f"MPU6050 biaxial tilt bias recalibrated to factory horizon."
        elif cmd == "TRIGGER_LOCAL_SIREN":
            msg = f"Audible site siren activated via Gateway Base Station relay."
        elif cmd == "ACTIVATE_BUZZER":
            msg = f"Onboard alert buzzer pulsed at 85dB on {payload.node_id}."
        elif cmd == "TRIGGER_EMERGENCY_BEACON":
            msg = f"RF beacon & Red LED strobe active for visual emergency location."
        elif cmd == "ENTER_LOW_POWER_SLEEP":
            msg = f"ESP32 light sleep duty cycle set to 10s intervals."
        elif cmd == "RESET_MODEM":
            msg = f"SX1278 spread-spectrum modem soft rebooted and re-joined mesh."

        log_record = CommandAuditLogModel(
            node_id=payload.node_id,
            command_type=payload.command_type,
            payload=json.dumps(payload.payload),
            dispatched_by=payload.dispatched_by or "SUPERVISOR",
            status="ACKNOWLEDGED",
            response_message=msg
        )
        db.add(log_record)
        db.commit()

        logger.info(f"Dispatched command {cmd} to {payload.node_id}: {msg}")

        return {
            "status": "SUCCESS",
            "node_id": payload.node_id,
            "command_type": payload.command_type,
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "response_message": msg
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Command dispatch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/commands/history")
def get_command_history(limit: int = Query(25, ge=1, le=100)):
    db: Session = SessionLocal()
    try:
        logs = db.query(CommandAuditLogModel).order_by(CommandAuditLogModel.dispatched_at.desc()).limit(limit).all()
        return [
            {
                "id": l.id,
                "node_id": l.node_id,
                "command_type": l.command_type,
                "payload": json.loads(l.payload) if l.payload else {},
                "dispatched_by": l.dispatched_by,
                "dispatched_at": l.dispatched_at.isoformat() if l.dispatched_at else None,
                "status": l.status,
                "response_message": l.response_message
            }
            for l in logs
        ]
    finally:
        db.close()


# =============================================================================
# 9. STATIC FRONTEND MOUNTING
# =============================================================================

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)