# spacex_sim.py
# SpaceX Temporal Early-Warning Simulation v0.1
# Uses Odin’s Eye

import json
import time
import random
from datetime import datetime, timedelta
from odins_eye import OdinsEye

# Pre-agreed runway for telemetry
RUNWAY_START = 50000
RUNWAY_LENGTH = 10000
RUNWAY_END = RUNWAY_START + RUNWAY_LENGTH

# Fake telemetry snapshot
def generate_telemetry(t_seconds: int):
    anomaly = t_seconds == 45  # simulate failure at T+45s
    return {
        "timestamp": (datetime.now() + timedelta(seconds=t_seconds)).isoformat(),
        "mission": "Starship Flight Test 42",
        "pressure": random.uniform(90, 110) - (20 if anomaly else 0),
        "temp": random.uniform(20, 40) + (30 if anomaly else 0),
        "vibration": random.uniform(10, 30) + (80 if anomaly else 0),  # spike = anomaly
        "status": "ANOMALY" if anomaly else "nominal"
    }

# Encode snapshot
def encode_snapshot(eye: OdinsEye, t_seconds: int):
    telemetry = generate_telemetry(t_seconds)
    data = json.dumps(telemetry).encode()
    coord = eye.encode(data)
    print(f"Encoded T+{t_seconds}s snapshot → end_mask={coord['end_mask']}")
    return coord, telemetry

# Poll for anomalies
def poll_anomalies(eye: OdinsEye):
    print(f"Polling future runway {RUNWAY_START} → {RUNWAY_END} for anomalies...")
    current = RUNWAY_START
    found = False

    while current < RUNWAY_END and not found:
        for guess_len in [512, 1024]:
            try:
                coord = {
                    "version": "0.1.1",
                    "start_mask": RUNWAY_START,
                    "end_mask": current,
                    "anchor_mask": current - 8,
                    "last_choice": 0,
                    "last_direction": 1,
                    "length_bytes": guess_len
                }
                data = eye.decode(coord)
                telemetry = json.loads(data)
                if telemetry["vibration"] > 80:
                    print(f"*** ANOMALY DETECTED! ***")
                    print(f"Coord: {coord}")
                    print(f"Future failure at {telemetry['timestamp']} (vibration {telemetry['vibration']})")
                    print(f"Alert: Abort recommended")
                    found = True
                    break
            except Exception:
                pass
        current += 10  # step for speed

    if not found:
        print("No anomaly found in runway")

# Run simulation
if __name__ == '__main__':
    eye = OdinsEye(start_mask=RUNWAY_START)

    print("Encoding pre-launch telemetry snapshots...")
    for t in range(0, 60, 5):  # T+0 to T+55s
        encode_snapshot(eye, t)
        time.sleep(0.1)  # simulate real-time encoding

    print("\nStarting future polling for anomalies...")
    poll_anomalies(eye)
