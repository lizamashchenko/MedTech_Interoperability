import json
import uuid
import random
import time
import asyncio
import websockets
import requests
from datetime import datetime, timezone

# Configuration
FHIR_URL = "http://localhost:8888/fhir"
# Map each device to its patient
DEVICE_TO_PATIENT = {
    "neg-pressure-device-1": "patient-1",
    "neg-pressure-device-2": "patient-2"
}
DEVICE_IDS = list(DEVICE_TO_PATIENT.keys())
WS_PORT = 6789
HEADERS = {
    "Content-Type": "application/fhir+json; charset=UTF-8",
    "Accept": "application/fhir+json"
}

# Track WebSocket clients
device_clients = set()

async def register(ws):
    device_clients.add(ws)
    try:
        await ws.wait_closed()
    finally:
        device_clients.remove(ws)

async def notify_all(message: str):
    if device_clients:
        await asyncio.gather(*(client.send(message) for client in device_clients))

# Ensure FHIR Patient & Device

def ensure_resources():
    # Create Patients
    for pid in set(DEVICE_TO_PATIENT.values()):
        patient = {
            "resourceType": "Patient",
            "id": pid,
            "name": [{"given": ["Test"], "family": "User"}]
        }
        r = requests.put(
            f"{FHIR_URL}/Patient/{pid}", json=patient, headers=HEADERS
        )
        print(f"Ensure Patient {pid} → {r.status_code}")

    # Create Devices
    for did, pid in DEVICE_TO_PATIENT.items():
        device = {
            "resourceType": "Device",
            "id": did,
            "status": "active",
            "type": {"coding": [{
                "system": "http://snomed.info/sct",
                "code": "428191000124105",
                "display": "NPWT Device"
            }]},
            "owner": {"reference": f"Patient/{pid}"},
            "manufacturer": "Acme Medical",
            "deviceName": [{"name": f"Pump {did[-1]}", "type": "user-friendly-name"}]
        }
        r = requests.put(
            f"{FHIR_URL}/Device/{did}", json=device, headers=HEADERS
        )
        print(f"Ensure Device {did} → {r.status_code}")

# Build a normal Observation resource
def build_observation(did: str, pressure: float) -> dict:
    pid = DEVICE_TO_PATIENT[did]
    return {
        "resourceType": "Observation",
        "id": str(uuid.uuid4()),
        "status": "final",
        "category": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs"
        }]}],
        "code": {"coding": [{
            "system": "http://loinc.org",
            "code": "14147-5",
            "display": "Negative Pressure"
        }], "text": "Negative Pressure"},
        "subject": {"reference": f"Patient/{pid}"},
        "device": {"reference": f"Device/{did}"},
        "effectiveDateTime": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
        "valueQuantity": {
            "value": pressure,
            "unit": "cmH2O",
            "system": "http://unitsofmeasure.org",
            "code": "cmH2O"
        }
    }

# Build an error Observation resource
def build_error_observation(did: str) -> dict:
    pid = DEVICE_TO_PATIENT[did]
    return {
        "resourceType": "Observation",
        "id": str(uuid.uuid4()),
        "status": "final",
        "category": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs"
        }]}],
        "code": {"coding": [{
            "system": "http://example.org/fhir/CodeSystem/device-error",
            "code": "DEVICE_ERROR",
            "display": "Device Error"
        }], "text": "Device Error"},
        "subject": {"reference": f"Patient/{pid}"},
        "device": {"reference": f"Device/{did}"},
        "effectiveDateTime": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
        "valueString": "Suction failure"
    }

async def producer():
    ensure_resources()
    time.sleep(2)
    while True:
        for did in DEVICE_IDS:
            # 90% chance to simulate device error
            if random.random() < 0.1:
                obs = build_error_observation(did)
                payload = {"device": did, "time": obs["effectiveDateTime"], "error": True, "message": "Suction failure"}
                print(f"[{did}] **Simulated DEVICE ERROR** at {obs['effectiveDateTime']}")
            else:
                val = -random.uniform(50, 100)
                obs = build_observation(did, val)
                payload = {"device": did, "time": obs["effectiveDateTime"], "value": val}

            # POST to HAPI
            r = requests.post(
                f"{FHIR_URL}/Observation", json=obs, headers=HEADERS
            )
            print(f"[{did}] Observation → {r.status_code}")
            if r.status_code >= 400:
                print(r.text)

            # Push via WebSocket
            await notify_all(json.dumps(payload))
        await asyncio.sleep(5)

async def handler(ws):
    print("→ New WS client connected")
    await register(ws)

async def main():
    # Start WebSocket server and data producer
    async with websockets.serve(handler, '127.0.0.1', WS_PORT):
        print(f"WebSocket server running at ws://127.0.0.1:{WS_PORT}")
        await producer()

if __name__ == '__main__':
    asyncio.run(main())