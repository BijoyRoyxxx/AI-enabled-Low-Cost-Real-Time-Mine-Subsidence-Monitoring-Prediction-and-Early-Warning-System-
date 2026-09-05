"""
GEO-SHIELD Mine Subsidence Monitoring System - Test Suite
Verifies REST endpoints, Database Seeding, Static Files, and WebSocket Streaming.
"""

import os
import sys
import time
import json
import asyncio
import threading
import urllib.request

# Ensure workspace root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uvicorn
import websockets
from backend.app import app

def run_test():
    test_port = 8990
    config = uvicorn.Config(app, host="127.0.0.1", port=test_port, log_level="error")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(2.0)

    try:
        # Test 1: Health Check
        with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/health") as res:
            data = json.loads(res.read().decode())
            print(f"[PASS] Health: {data['status']}")
            assert data["status"] == "healthy"

        # Test 2: Monitored Nodes List
        with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/nodes") as res:
            nodes = json.loads(res.read().decode())
            print(f"[PASS] Monitored Nodes: {len(nodes)} (Gateway: {nodes[0]['node_id']})")
            assert len(nodes) == 21

        # Test 2B: Service API Keys & Provider Config
        with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/config") as res:
            cfg = json.loads(res.read().decode())
            print(f"[PASS] Service Config: Map Provider={cfg['map']['provider']}, LLM Model={cfg['llm']['model_name']}")
            assert "map" in cfg and "llm" in cfg
            assert "provider" in cfg["map"] and "has_key" in cfg["map"]
            assert "provider" in cfg["llm"] and "has_key" in cfg["llm"]

        # Test 3: TimesFM 8-Hour Forecast with AI Geotechnical Advisory
        with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/forecast/timesfm?node_id=N13") as res:
            fc = json.loads(res.read().decode())
            print(f"[PASS] TimesFM Forecast: {len(fc['forecast_points'])} forward steps (Horizon: {fc['horizon_hours']}h)")
            print(f"[PASS] AI Advisory Engine: {fc['ai_geotechnical_advisory']['provider']}, Risk: {fc['ai_geotechnical_advisory']['risk_level']}")
            assert len(fc["forecast_points"]) == 16
            assert "ai_geotechnical_advisory" in fc
            assert fc["ai_geotechnical_advisory"]["risk_level"] in ("CRITICAL", "WARNING", "STABLE", "HIGH")

        # Test 4: Geotechnical Hazards & Mesh Links
        with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/hazards") as res:
            hazards = json.loads(res.read().decode())
            print(f"[PASS] Hazard Zones: {len(hazards['hazard_zones'])}, Mesh Links: {len(hazards['mesh_links'])}")
            assert len(hazards["hazard_zones"]) == 3

        # Test 5: Two-Way Remote Command Dispatch
        req = urllib.request.Request(
            f"http://127.0.0.1:{test_port}/api/commands/dispatch",
            data=json.dumps({"node_id": "N13", "command_type": "TRIGGER_LOCAL_SIREN", "payload": {}}).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            cmd = json.loads(res.read().decode())
            print(f"[PASS] Command Dispatch: {cmd['status']} -> {cmd['response_message']}")
            assert cmd["status"] == "SUCCESS"

        # Test 6: Static Frontend Index
        with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/") as res:
            html = res.read().decode()
            print(f"[PASS] Frontend Served: {len(html)} bytes")
            assert "Mine Subsidence" in html

        # Test 7: WebSocket Telemetry Streaming
        async def verify_ws():
            async with websockets.connect(f"ws://127.0.0.1:{test_port}/ws/telemetry") as ws:
                msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
                data = json.loads(msg)
                print(f"[PASS] WebSocket Live Frame: Type={data.get('type')}, Nodes={len(data.get('nodes'))}, Overall Status={data.get('summary', {}).get('overall_status')}")
                assert len(data.get("nodes")) == 21

        asyncio.run(verify_ws())

        print("\n>>> ALL MINE SUBSIDENCE TEST SUITE CHECKS COMPLETED SUCCESSFULLY! <<<")
    finally:
        server.should_exit = True

if __name__ == "__main__":
    run_test()
