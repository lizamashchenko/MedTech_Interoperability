import requests
import uuid
import random
from datetime import datetime, timezone
import sys
import time

FHIR_URL = "http://localhost:8080/fhir"
PATIENT_ID = -1
ERROR_PROBABILITY = 0.1 

def get_precise_time():
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(timespec='milliseconds')

def create_pressure_observation(pressure: int):
    observation = {
        "resourceType": "Observation",
        "id": str(uuid.uuid4()),
        "meta": {
            "tag": [{
                "system": "urn:uuid",
                "code": str(uuid.uuid4())
            }]
        },
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

def create_device_connection_issue_observation(issue_message: str):
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
    while True:
        if random.random() < ERROR_PROBABILITY:
            create_device_connection_issue_observation("Lost connection to device")
            time.sleep(10)
        pressure = random.randint(-150, -80)
        create_pressure_observation(pressure)
        time.sleep(6)
