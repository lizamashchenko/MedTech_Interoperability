from flask import Flask, render_template, jsonify, request
import requests

app = Flask(__name__)

FHIR_URL = "http://localhost:8080/fhir"
PATIENT_ID = "test-patient"

def get_latest_pressure_data(patient_id):
    search_url = (
        f"{FHIR_URL}/Observation?"
        f"subject=Patient/{patient_id}&"
        f"code=31209-0&_sort=-date&_count=10"
    )

    response = requests.get(search_url)
    bundle = response.json()
    values = []

    if "entry" in bundle:
        for entry in reversed(bundle["entry"]):
            obs = entry["resource"]
            value = obs["valueQuantity"]["value"]
            time = obs["effectiveDateTime"]
            values.append({"value": value, "time": time})
    
    return values

def get_latest_device_issue(patient_id):
    search_url = (
        f"{FHIR_URL}/Observation?"
        f"subject=Patient/{patient_id}&"
        f"code=70325-2&_sort=-date&_count=1"
    )

    response = requests.get(search_url)
    bundle = response.json()
    issues = []

    if "entry" in bundle:
        for entry in bundle["entry"]:
            obs = entry["resource"]
            issue_msg = obs.get("valueString", "Unknown issue")
            time = obs.get("effectiveDateTime", "Unknown time")
            issues.append({"message": issue_msg, "time": time})
    
    return issues


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/patients")
def get_patients():
    response = requests.get(f"{FHIR_URL}/Patient?_count=100")
    bundle = response.json()
    patients = []

    if "entry" in bundle:
        for entry in bundle["entry"]:
            patient = entry["resource"]
            patients.append({
                "id": patient["id"],
                "name": f"{patient.get('name', [{'family':'Unknown'}])[0].get('given', [''])[0]} {patient.get('name', [{'family':'Unknown'}])[0]['family']}"
            })

    return jsonify(patients)

@app.route("/api/heart")
def heart_api():
    patient_id = request.args.get("patient", "test-patient")
    data = get_latest_pressure_data(patient_id)
    return jsonify(data)

@app.route("/api/issues")
def issues_api():
    patient_id = request.args.get("patient", "test-patient")
    issues = get_latest_device_issue(patient_id)
    return jsonify(issues)


if __name__ == "__main__":
    app.run(debug=True)
