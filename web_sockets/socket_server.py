import asyncio
from datetime import datetime, timezone
import uuid
import websockets
import json
import requests

FHIR_URL = "http://localhost:8080/fhir"
HEADERS = {
    "Content-Type": "application/fhir+json; charset=UTF-8",
    "Accept": "application/fhir+json"
}

registered_id = []

def ensure_resources(patient_id):
    patient_url = f"{FHIR_URL}/Patient/{patient_id}"
    device_url = f"{FHIR_URL}/Device/{patient_id}"

    patient = {
        "resourceType": "Patient",
        "id": patient_id,
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

    device_check = requests.get(device_url, headers=HEADERS)
    if device_check.status_code == 404:
        device = {
            "resourceType": "Device",
            "id": patient_id,
            "status": "active",
            "manufacturer": "Simulated Device Inc.",
            "deviceName": [{
                "name": f"Test Device {patient_id}",
                "type": "manufacturer-name"
            }],
            "patient": {
                "reference": f"Patient/{patient_id}"
            }
        }

        print(f"\nCreating Device:\n{json.dumps(device, indent=2)}")
        response = requests.put(device_url, json=device, headers=HEADERS)
        print(f"[{patient_id}] Created Device → {response.status_code}")
        if response.status_code >= 400:
            print(f"[{patient_id}] Device PUT error:\n{response.text}")
    else:
        print(f"[{patient_id}] Device already exists or error → {device_check.status_code}")

def build_observation(data):
    device_id = data["device_id"]
    value = data["value"]
    patient_id = device_id
    now = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
    observation_id = str(uuid.uuid4())

    observation = {
        "resourceType": "Observation",
        "id": observation_id,
        "status": "final",
        "category": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "vital-signs",
                "display": "Vital Signs"
            }]
        }],
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "31209-0",
                "display": "Pressure in wound therapy device"
            }],
            "text": "Wound pressure"
        },
        "subject": {
            "reference": f"Patient/{patient_id}"
        },
        "effectiveDateTime": now,
        "valueQuantity": {
            "value": value,
            "unit": "mmHg",
            "system": "http://unitsofmeasure.org",
            "code": "mm[Hg]"
        }
    }
    return observation

def build_error(data):
    device_id = data["device_id"]
    message = data["message"]
    now = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
    
    error = {
        "resourceType": "Observation",
        "id": str(uuid.uuid4()),
        "status": "final",
        "category": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "device",
                "display": "Device"
            }]
        }],
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "70325-2",
                "display": "Device connectivity status"
            }],
            "text": "Device connection issue"
        },
        "subject": {
            "reference": f"Patient/{device_id}"
        },
        "effectiveDateTime": now,
        "valueString": message
    }

    return error

connected_devices = set()

async def register(ws):
    connected_devices.add(ws)
    try:
        async for message in ws:
            data = json.loads(message)
            device_id = data.get("device_id")
            print(f"Received from device {device_id}: {data}")

            if device_id not in registered_id:
                ensure_resources(device_id)
                registered_id.append(device_id)

            if data.get("error", False):
                obs = build_error(data)
            else:
                obs = build_observation(data)

            r = requests.post(f"{FHIR_URL}/Observation", json=obs, headers=HEADERS)
            print(f"→ FHIR status: {r.status_code}")
            if r.status_code >= 400:
                print(r.text)
    finally:
        connected_devices.remove(ws)


async def handler(ws):
    print("New device connected")
    await register(ws)

async def main():
    async with websockets.serve(handler, '0.0.0.0', 6789):
        print("Server running at ws://0.0.0.0:6789")
        await asyncio.Future()

if __name__ == '__main__':
    asyncio.run(main())
