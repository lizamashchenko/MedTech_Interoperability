import asyncio
from datetime import datetime, timezone
import uuid
import websockets
import json
import requests
from typing import Optional

FHIR_URL = "http://localhost:8080/fhir"
HEADERS = {
    "Content-Type": "application/fhir+json; charset=UTF-8",
    "Accept": "application/fhir+json"
}

registered_id = []

observations = []
device_errors = []
device_warnings = []
pressure_values = [] 

therapy_start_time: Optional[datetime] = None
therapy_end_time: Optional[datetime] = None
pause_periods: list[tuple[datetime, datetime]] = []
current_pause_start: Optional[datetime] = None

def get_precise_time():
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(timespec='milliseconds')

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

    pressure_values.append(value)

    return observation

def build_error(data):
    device_id = data["device_id"]
    message = data["message"]

    if data["severity"] == "warning":
        code = "69758-7"
        display = "Device warning message"
    elif data["severity"] == "error":
        code = "70325-2"
        display = "Device connectivity status"

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
                "code": code,
                "display": display
            }],
            "text": f"Device {data["severity"]}"
        },
        "subject": {
            "reference": f"Patient/{device_id}"
        },
        "effectiveDateTime": now,
        "valueString": message
    }
    return error

def create_diagnostic_report(data):
    global therapy_start_time, therapy_end_time, pause_periods, current_pause_start

    device_id = data["device_id"]

    if not observations and not device_errors:
        print("[INFO] No observations to include in report.")
        return

    report_id = str(uuid.uuid4())
    now_str = get_precise_time()

    all_results = (
        [{"reference": f"Observation/{oid}"} for oid in observations] +
        [{"reference": f"Observation/{oid}"} for oid in device_errors] +
        [{"reference": f"Observation/{oid}"} for oid in device_warnings] 
    )

    if therapy_start_time and therapy_end_time:
        duration_sec = (therapy_end_time - therapy_start_time).total_seconds()
    else:
        duration_sec = 0

    pause_total = sum(
        (end - start).total_seconds() for start, end in pause_periods
    )

    report = {
        "resourceType": "DiagnosticReport",
        "id": report_id,
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "11502-2",
                "display": "Wound device session summary"
            }],
            "text": "Wound therapy session summary"
        },
        "subject": {
            "reference": f"Patient/{device_id}"
        },
        "effectiveDateTime": now_str,
        "issued": now_str,
        "result": all_results,
        "conclusion": (
            f"Report contains {len(observations)} observations and "
            f"{len(device_errors)} device errors and {len(device_warnings)} warnings.\n"
            f"Total duration: {duration_sec:.1f} seconds.\n"
            f"Total pause time: {pause_total:.1f} seconds."
        )}

    response = requests.post(f"{FHIR_URL}/DiagnosticReport", json=report)
    print(f"[REPORT] DiagnosticReport submitted ({len(observations)} observations) -> {response.status_code}")
    if response.status_code != 201:
        print("Response content:")
        print(response.text) 
    observations.clear()
    device_errors.clear()
    pressure_values.clear()
    
    therapy_start_time = None
    therapy_end_time = None
    pause_periods.clear()
    current_pause_start = None

connected_devices = set()

async def register(ws):

    connected_devices.add(ws)
    try:
        async for message in ws:
            data = json.loads(message)
            device_id = data.get("device_id")
            mode = data.get("mode", "unknown")
            status = data.get("status", "unknown")

            now = datetime.now(timezone.utc)
            global therapy_start_time, therapy_end_time, current_pause_start

            if status == "running" and therapy_start_time is None:
                therapy_start_time = now
                print(f"[INFO] Therapy started at {therapy_start_time.isoformat()}")

            elif status == "paused" and current_pause_start is None:
                current_pause_start = now
                print(f"[INFO] Therapy paused at {current_pause_start.isoformat()}")

            elif status == "running" and current_pause_start is not None:
                pause_periods.append((current_pause_start, now))
                print(f"[INFO] Therapy resumed at {now.isoformat()} — pause duration: {(now - current_pause_start)}")
                current_pause_start = None

            elif status == "ended":
                therapy_end_time = now
                if current_pause_start is not None:
                    pause_periods.append((current_pause_start, therapy_end_time))
                    current_pause_start = None
                print(f"[INFO] Therapy ended at {therapy_end_time.isoformat()}")

            print(f"Received from device {device_id}: {data}")

            if device_id not in registered_id:
                ensure_resources(device_id)
                registered_id.append(device_id)

            if data.get("error", False):
                obs = build_error(data)
            else:
                obs = build_observation(data)

            obs["component"] = [
            {
                "code": {
                    "coding": [{
                        "system": "http://example.org/device-mode",
                        "code": "mode"
                    }],
                    "text": "Device mode"
                },
                "valueString": mode
            },
            {
                "code": {
                    "coding": [{
                        "system": "http://example.org/device-status",
                        "code": "status"
                    }],
                    "text": "Device status"
                },
                "valueString": status
            }]

            response = requests.post(f"{FHIR_URL}/Observation", json=obs, headers=HEADERS)
            print(f"→ FHIR status: {response.status_code}")
            if response.status_code >= 400:
                print(response.text)
            if response.status_code == 201:
                location = response.headers.get("Location")
                if location:
                    parts = location.split('/')
                    if "Observation" in parts:
                        idx = parts.index("Observation")
                        obs_id = parts[idx + 1]
                        if data.get("error", False):
                            if data["severity"] == "warning":
                                device_warnings.append(obs_id)
                            elif data["severity"] == "error":
                                device_errors.append(obs_id)
                        else:
                            observations.append(obs_id)
                else:
                    print("Warning: No Location header in response")

            if status == "ended":
                print(f"[INFO] Therapy ended. Generating report for {device_id}.")
                create_diagnostic_report(data)

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
