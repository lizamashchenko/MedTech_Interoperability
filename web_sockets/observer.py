from flask import Flask, render_template, jsonify, request, send_file
import requests
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


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

            status = "unknown"
            for component in obs.get("component", []):
                if "code" in component and component["code"]["text"] == "Device status":
                    status = component.get("valueString", "unknown")
                    break

            values.append({
                "value": value,
                "time": time,
                "status": status
            })

    return values

def get_latest_device_error(patient_id):
    search_url = (
        f"{FHIR_URL}/Observation?"
        f"subject=Patient/{patient_id}&"
        f"code=70325-2&_sort=-date"
    )

    response = requests.get(search_url)
    bundle = response.json()
    issues = []

    if "entry" in bundle:
        for entry in bundle["entry"]:
            obs = entry["resource"]
            issue_msg = obs.get("valueString", "Unknown error")
            time = obs.get("effectiveDateTime", "Unknown time")
            issues.append({"message": issue_msg, "time": time})
    
    return issues

def get_latest_device_warning(patient_id):
    search_url = (
        f"{FHIR_URL}/Observation?"
        f"subject=Patient/{patient_id}&"
        f"code=69758-7&_sort=-date"
    )

    response = requests.get(search_url)
    bundle = response.json()
    issues = []

    if "entry" in bundle:
        for entry in bundle["entry"]:
            obs = entry["resource"]
            issue_msg = obs.get("valueString", "Unknown warning")
            time = obs.get("effectiveDateTime", "Unknown time")
            issues.append({"message": issue_msg, "time": time})
    
    return issues

def get_latest_reports(patient_id):
    search_url = (
        f"{FHIR_URL}/DiagnosticReport?"
        f"subject=Patient/{patient_id}&"    
        f"_sort=-issued&_count=5"
    )

    response = requests.get(search_url)
    bundle = response.json()
    reports = []

    if "entry" in bundle:
        for entry in bundle["entry"]:
            report = entry["resource"]
            reports.append({
                "issued": report.get("issued", "Unknown time"),
                "text": report.get("conclusion", "No summary")
            })

    return reports

def fetch_observations_for_latest_report(patient_id):
    report_url = (
        f"{FHIR_URL}/DiagnosticReport?"
        f"subject=Patient/{patient_id}&"
        f"_sort=-issued&_count=1"
    )
    report_response = requests.get(report_url).json()
    
    if "entry" not in report_response or len(report_response["entry"]) == 0:
        return None, []

    report = report_response["entry"][0]["resource"]
    report_time = report.get("issued", "Unknown")
    obs_refs = [ref["reference"] for ref in report.get("result", []) if "reference" in ref]
    
    observations = []
    for ref in obs_refs:
        obs_url = f"{FHIR_URL}/{ref}"
        obs = requests.get(obs_url).json()
        
        time = obs.get("effectiveDateTime", "N/A")
        status = obs.get("status", "N/A")
        code = obs.get("code", {}).get("text", "Unknown Code")
        value = "-"
        if "valueQuantity" in obs:
            value = f"{obs['valueQuantity']['value']} {obs['valueQuantity'].get('unit', '')}"
        elif "valueString" in obs:
            value = obs["valueString"]

        observations.append({
            "time": time,
            "code": code,
            "value": value,
            "status": status
        })

    return report_time, observations

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

@app.route("/api/errors")
def errors_api():
    patient_id = request.args.get("patient", "test-patient")
    issues = get_latest_device_error(patient_id)
    return jsonify(issues)

@app.route("/api/warning")
def warnings_api():
    patient_id = request.args.get("patient", "test-patient")
    issues = get_latest_device_warning(patient_id)
    return jsonify(issues)

@app.route("/api/reports")
def reports_api():
    patient_id = request.args.get("patient", "test-patient")
    reports = get_latest_reports(patient_id)
    return jsonify(reports)

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from flask import send_file
import io
from datetime import datetime

from datetime import datetime, timedelta

@app.route("/api/report/pdf")
def generate_pdf_report():
    patient_id = request.args.get("patient", "test-patient")
    report_time, observations = fetch_observations_for_latest_report(patient_id)

    # Parse times and statuses for calculation
    times = []
    pause_intervals = []  # store paused periods as (start, end) tuples
    pause_start = None

    for obs in observations:
        try:
            t = datetime.fromisoformat(obs["time"].replace("Z", "+00:00"))
        except Exception:
            continue
        times.append(t)

        status = obs.get("status", "").lower()
        if status == "paused" and pause_start is None:
            pause_start = t
        elif status != "paused" and pause_start is not None:
            pause_intervals.append((pause_start, t))
            pause_start = None

    # If last status was paused and no end time, assume pause ended at last observation time
    if pause_start is not None and times:
        pause_intervals.append((pause_start, max(times)))

    if times:
        therapy_start = min(times)
        therapy_end = max(times)
        duration = therapy_end - therapy_start
    else:
        therapy_start = therapy_end = None
        duration = timedelta(0)

    # Sum pause durations
    pause_duration = timedelta(0)
    for start, end in pause_intervals:
        pause_duration += (end - start)

    # Format for display
    def fmt_dt(dt):
        return dt.strftime("%d %b %Y, %H:%M:%S") if dt else "N/A"
    def fmt_td(td):
        # Format timedelta as H:MM:SS
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=50, bottomMargin=50)

    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle(
        'title',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.white,
        backColor=colors.darkblue,
        alignment=1,  # center
        spaceAfter=20,
        leading=26
    )
    elements.append(Paragraph(f"📄 Patient Diagnostic Report", title_style))

    # Meta info: patient ID, report time
    elements.append(Paragraph(f"<b>Patient ID:</b> {patient_id}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Report Time:</b> {report_time}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    # New therapy info section
    therapy_info = f"""
        <b>Therapy Start:</b> {fmt_dt(therapy_start)}<br/>
        <b>Therapy End:</b> {fmt_dt(therapy_end)}<br/>
        <b>Duration:</b> {fmt_td(duration)}<br/>
        <b>Pause Duration:</b> {fmt_td(pause_duration)}
    """
    elements.append(Paragraph(therapy_info, styles["Normal"]))
    elements.append(Spacer(1, 12))

    # Table with observations (with formatted times)
    data = [["Time", "Code", "Value", "Status"]]
    for obs in observations:
        try:
            dt = datetime.fromisoformat(obs["time"].replace("Z", "+00:00"))
            readable_time = dt.strftime("%d %b %Y, %H:%M:%S")
        except Exception:
            readable_time = obs["time"]

        data.append([
            readable_time,
            obs["code"],
            str(obs["value"]),
            obs["status"]
        ])

    if observations:
        table = Table(data, repeatRows=1, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#007bff")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No observations found for the latest report.", styles["Normal"]))

    elements.append(Spacer(1, 20))
    footer = datetime.now().strftime("Generated on %Y-%m-%d at %H:%M:%S")
    footer_style = ParagraphStyle("footer", fontSize=8, alignment=2, textColor=colors.grey)
    elements.append(Paragraph(footer, footer_style))

    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True,
                     download_name=f"report_{patient_id}.pdf",
                     mimetype='application/pdf')

if __name__ == "__main__":
    app.run(debug=True)
