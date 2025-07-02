import requests
import uuid
import random
from datetime import datetime, timezone
import sys
import time

FHIR_URL = "http://localhost:8080/fhir"
PATIENT_ID = -1
ERROR_PROBABILITY = 0.1 

observations_in_last_minute = []
device_issues_in_last_minute = []
pressure_values_in_last_minute = [] 

def get_precise_time():
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(timespec='milliseconds')

def now_dt():
    return datetime.now(timezone.utc)

def create_pressure_observation(pressure: int):
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
            "reference": f"Patient/p{PATIENT_ID}"
        },
        "effectiveDateTime": get_precise_time(),
        "valueQuantity": {
            "value": pressure,
            "unit": "mmHg",
            "system": "http://unitsofmeasure.org",
            "code": "mm[Hg]"
        }
    }

    response = requests.post(f"{FHIR_URL}/Observation", json=observation)
    print(f"Sent {pressure} mmHg at {observation['effectiveDateTime']} -> {response.status_code}")
    if response.status_code == 201:
        location = response.headers.get("Location")
        if location:
            parts = location.split('/')
            if "Observation" in parts:
                idx = parts.index("Observation")
                obs_id = parts[idx + 1]
                observations_in_last_minute.append(obs_id)
                pressure_values_in_last_minute.append(pressure)
        else:
            print("Warning: No Location header in response")

def create_device_issue(issue_message: str):
    observation = {
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
            "reference": f"Patient/p{PATIENT_ID}"
        },
        "effectiveDateTime": get_precise_time(),
        "valueString": issue_message
    }

    response = requests.post(f"{FHIR_URL}/Observation", json=observation)
    print(f"Sent DEVICE CONNECTION ISSUE '{issue_message}' at {observation['effectiveDateTime']} -> {response.status_code}")
    if response.status_code == 201:
        location = response.headers.get("Location")
        if location:
            obs_id = location.split("/Observation/")[1].split("/")[0]
            device_issues_in_last_minute.append(obs_id)

def create_diagnostic_report():
    if not observations_in_last_minute and not device_issues_in_last_minute:
        print("[INFO] No observations to include in report.")
        return

    report_id = str(uuid.uuid4())
    now_str = get_precise_time()

    all_results = (
        [{"reference": f"Observation/{oid}"} for oid in observations_in_last_minute] +
        [{"reference": f"Observation/{oid}"} for oid in device_issues_in_last_minute]
    )

    if pressure_values_in_last_minute:
        min_val = min(pressure_values_in_last_minute)
        max_val = max(pressure_values_in_last_minute)
        avg_val = sum(pressure_values_in_last_minute) / len(pressure_values_in_last_minute)
        stats_text = f"Pressure stats — min: {min_val} mmHg, max: {max_val} mmHg, avg: {avg_val:.2f} mmHg."
    else:
        stats_text = "No pressure data available."

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
            "reference": f"Patient/p{PATIENT_ID}"
        },
        "effectiveDateTime": now_str,
        "issued": now_str,
        "result": all_results,
        "conclusion": (
            f"Report contains {len(observations_in_last_minute)} observations and "
            f"{len(device_issues_in_last_minute)} device issues from the past minute. "
            f"{stats_text}"
        )}

    response = requests.post(f"{FHIR_URL}/DiagnosticReport", json=report)
    print(f"[REPORT] DiagnosticReport submitted ({len(observations_in_last_minute)} observations) -> {response.status_code}")
    if response.status_code != 201:
        print("Response content:")
        print(response.text) 
    observations_in_last_minute.clear()


def ensure_patient():
    patient = {
        "resourceType": "Patient",
        "id": f"p{PATIENT_ID}",
        "name": [{
            "given": ["Test"],
            "family": "User"
        }]
    }
    requests.put(f"{FHIR_URL}/Patient/p{PATIENT_ID}", json=patient)

if __name__ == "__main__":
    if len(sys.argv) != 2:
            print("Usage: python send_pressure.py <patient-id>")
            sys.exit(1)

    PATIENT_ID = sys.argv[1]
    ensure_patient()

    last_report_time = now_dt()

    while True:
        if random.random() < ERROR_PROBABILITY:
            create_device_issue("Lost connection to device")
            time.sleep(10)
        else:
            pressure = random.randint(-150, -80)
            create_pressure_observation(pressure)
        
        if (now_dt() - last_report_time).total_seconds() >= 20 :
            create_diagnostic_report()
            last_report_time = now_dt()

        time.sleep(6)
