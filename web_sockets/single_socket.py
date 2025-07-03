import json
import uuid
import random
import time
import asyncio
import websockets
import requests
import argparse
from datetime import datetime, timezone

# Configuration
FHIR_URL = "http://localhost:8080/fhir"
ERROR_PROBABILITY = 0.1
HEADERS = {
    "Content-Type": "application/fhir+json; charset=UTF-8",
    "Accept": "application/fhir+json"
}


def ensure_patient(patient_id):
    patient_fhir_id = f"p{patient_id}"  # prefixed ID
    device_fhir_id = f"d{patient_id}"

    patient_url = f"{FHIR_URL}/Patient/{patient_fhir_id}"
    device_url = f"{FHIR_URL}/Device/{device_fhir_id}"

    patient = {
        "resourceType": "Patient",
        "id": patient_fhir_id,
        "name": [{
            "given": ["Test"],
            "family": "User"
        }]
    }

    print(f"\nCreating/Updating Patient:\n{json.dumps(patient, indent=2)}")
    response = requests.put(patient_url, json=patient, headers=HEADERS)
    print(f"[{patient_id}] Patient PUT → {response.status_code}")
    if response.status_code >= 400:
        print(f"[{patient_id}] Patient PUT error:\n{response.text}")

    # Check if Device exists
    device_check = requests.get(device_url, headers=HEADERS)
    if device_check.status_code == 404:
        device = {
            "resourceType": "Device",
            "id": device_fhir_id,
            "status": "active",
            "manufacturer": "Simulated Device Inc.",
            "deviceName": [{
                "name": f"Test Device {patient_id}",
                "type": "manufacturer-name"
            }],
            "patient": {
                "reference": f"Patient/{patient_fhir_id}"
            }
        }

        print(f"\nCreating Device:\n{json.dumps(device, indent=2)}")
        response = requests.put(device_url, json=device, headers=HEADERS)
        print(f"[{patient_id}] Created Device → {response.status_code}")
        if response.status_code >= 400:
            print(f"[{patient_id}] Device PUT error:\n{response.text}")
    else:
        print(f"[{patient_id}] Device already exists or error → {device_check.status_code}")

    return patient_fhir_id, device_fhir_id


def build_observation(patient_fhir_id, device_fhir_id, pressure: float) -> dict:
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
        "subject": {"reference": f"Patient/{patient_fhir_id}"},
        "device": {"reference": f"Device/{device_fhir_id}"},
        "effectiveDateTime": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
        "valueQuantity": {
            "value": pressure,
            "unit": "cmH2O",
            "system": "http://unitsofmeasure.org",
            "code": "cmH2O"
        }
    }

def build_error_observation(patient_fhir_id, device_fhir_id) -> dict:
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
        "subject": {"reference": f"Patient/{patient_fhir_id}"},
        "device": {"reference": f"Device/{device_fhir_id}"},
        "effectiveDateTime": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
        "valueString": "Suction failure"
    }


async def producer(patient_id):
    patient_fhir_id, device_fhir_id = ensure_patient(patient_id)
    time.sleep(2)
    while True:
        if random.random() < ERROR_PROBABILITY:
            obs = build_error_observation(patient_fhir_id, device_fhir_id)
            print(f"[{patient_id}] **Simulated DEVICE ERROR** at {obs['effectiveDateTime']}")
        else:
            val = -random.uniform(50, 100)
            obs = build_observation(patient_fhir_id, device_fhir_id, val)

        r = requests.post(f"{FHIR_URL}/Observation", json=obs, headers=HEADERS)
        print(f"[{patient_id}] Observation → {r.status_code}")
        if r.status_code >= 400:
            print(r.text)

        await asyncio.sleep(5)


async def handler(websocket, path):
    # You could echo or extend this in the future
    await websocket.send("Connection established.")


async def main(patient_id, ws_port):
    async with websockets.serve(handler, '0.0.0.0', ws_port):
        print(f"WebSocket server running at ws://0.0.0.0:{ws_port} for patient {patient_id}")
        await producer(patient_id)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Simulate medical device telemetry.")
    parser.add_argument('--patient-id', type=int, required=True, help="Patient ID")
    parser.add_argument('--port', type=int, default=6789, help="WebSocket port")
    args = parser.parse_args()

    asyncio.run(main(args.patient_id, args.port))
