from getpass import getpass
import hashlib
import hmac
from html import escape
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
import re
import secrets
from time import time
from urllib.parse import parse_qs, quote, urlsplit

import mysql.connector
from mysql.connector import Error


MYSQL_USER = ""
MYSQL_PASSWORD = ""
SESSION_TTL_SECONDS = 8 * 60 * 60
PASSWORD_ITERATIONS = 600_000
SESSIONS = {}

SECTIONS = {
    "departments": {
        "title": "Departments",
        "table": "departments",
        "primary_key": "department_id",
        "fields": [
            ("Department name", "department_name", "text", True, None),
            ("Location", "location", "text", False, None),
        ],
        "values": ("department_name", "location"),
        "insert": "INSERT INTO departments (department_name, location) VALUES (%s, %s)",
        "update": "UPDATE departments SET department_name = %s, location = %s WHERE department_id = %s",
        "query": "SELECT department_id, department_name, location FROM departments ORDER BY department_id",
        "columns": ("ID", "Department", "Location"),
        "search": ("department_name", "location"),
    },
    "doctors": {
        "title": "Doctors",
        "table": "doctors",
        "primary_key": "doctor_id",
        "fields": [
            ("Name", "name", "text", True, None),
            ("Department", "department_id", "select", True, "departments"),
            ("Specialization", "specialization", "text", False, None),
            ("Phone", "phone", "tel", False, None),
            ("Email", "email", "email", False, None),
        ],
        "values": ("name", "department_id", "specialization", "phone", "email"),
        "insert": "INSERT INTO doctors (name, department_id, specialization, phone, email) VALUES (%s, %s, %s, %s, %s)",
        "update": "UPDATE doctors SET name = %s, department_id = %s, specialization = %s, phone = %s, email = %s WHERE doctor_id = %s",
        "query": "SELECT d.doctor_id, d.name, dep.department_name, d.specialization, d.phone, d.email FROM doctors d JOIN departments dep ON dep.department_id = d.department_id ORDER BY d.doctor_id",
        "columns": ("ID", "Name", "Department", "Specialization", "Phone", "Email"),
        "search": ("d.name", "dep.department_name", "d.specialization", "d.phone", "d.email"),
    },
    "patients": {
        "title": "Patients",
        "table": "patients",
        "primary_key": "patient_id",
        "fields": [
            ("Name", "name", "text", True, None),
            ("Date of birth", "dob", "date", False, None),
            ("Phone", "phone", "tel", False, None),
            ("Address", "address", "textarea", False, None),
            ("Blood group", "blood_group", "text", False, None),
        ],
        "values": ("name", "dob", "phone", "address", "blood_group"),
        "insert": "INSERT INTO patients (name, dob, phone, address, blood_group) VALUES (%s, %s, %s, %s, %s)",
        "update": "UPDATE patients SET name = %s, dob = %s, phone = %s, address = %s, blood_group = %s WHERE patient_id = %s",
        "query": "SELECT patient_id, name, dob, phone, address, blood_group FROM patients ORDER BY patient_id",
        "columns": ("ID", "Name", "Date of birth", "Phone", "Address", "Blood group"),
        "search": ("name", "phone", "address", "blood_group"),
    },
    "appointments": {
        "title": "Appointments",
        "table": "appointments",
        "primary_key": "app_id",
        "fields": [
            ("Patient", "patient_id", "select", True, "patients"),
            ("Doctor", "doctor_id", "select", True, "doctors"),
            ("Date", "date", "date", True, None),
            ("Time", "time", "time", True, None),
            ("Status", "status", "text", False, None),
            ("Reason", "reason", "textarea", False, None),
        ],
        "values": ("patient_id", "doctor_id", "date", "time", "status", "reason"),
        "insert": "INSERT INTO appointments (patient_id, doctor_id, date, time, status, reason) VALUES (%s, %s, %s, %s, %s, %s)",
        "update": "UPDATE appointments SET patient_id = %s, doctor_id = %s, date = %s, time = %s, status = %s, reason = %s WHERE app_id = %s",
        "query": "SELECT a.app_id, p.name, d.name, a.date, a.time, a.status, a.reason FROM appointments a JOIN patients p ON p.patient_id = a.patient_id JOIN doctors d ON d.doctor_id = a.doctor_id ORDER BY a.date DESC, a.time",
        "columns": ("ID", "Patient", "Doctor", "Date", "Time", "Status", "Reason"),
        "search": ("p.name", "d.name", "a.status", "a.reason"),
    },
    "visits": {
        "title": "Visits",
        "table": "visits",
        "primary_key": "visit_id",
        "fields": [
            ("Patient", "patient_id", "select", True, "patients"),
            ("Visit date", "visit_date", "date", True, None),
            ("Diagnosis", "diagnosis", "text", False, None),
            ("Notes", "notes", "textarea", False, None),
            ("Treatment", "treatment", "textarea", False, None),
        ],
        "values": ("patient_id", "visit_date", "diagnosis", "notes", "treatment"),
        "insert": "INSERT INTO visits (patient_id, visit_date, diagnosis, notes, treatment) VALUES (%s, %s, %s, %s, %s)",
        "update": "UPDATE visits SET patient_id = %s, visit_date = %s, diagnosis = %s, notes = %s, treatment = %s WHERE visit_id = %s",
        "query": "SELECT v.visit_id, p.name, v.visit_date, v.diagnosis, v.notes, v.treatment FROM visits v JOIN patients p ON p.patient_id = v.patient_id ORDER BY v.visit_date DESC",
        "columns": ("ID", "Patient", "Visit date", "Diagnosis", "Notes", "Treatment"),
        "search": ("p.name", "v.diagnosis", "v.notes", "v.treatment"),
    },
    "bills": {
        "title": "Bills",
        "table": "bills",
        "primary_key": "bill_id",
        "fields": [
            ("Visit", "visit_id", "select", True, "visits"),
            ("Amount", "amount", "number", True, None),
            ("Date", "date", "date", True, None),
            ("Status", "status", "text", False, None),
            ("Payment mode", "payment_mode", "text", False, None),
        ],
        "values": ("visit_id", "amount", "date", "status", "payment_mode"),
        "insert": "INSERT INTO bills (visit_id, amount, date, status, payment_mode) VALUES (%s, %s, %s, %s, %s)",
        "update": "UPDATE bills SET visit_id = %s, amount = %s, date = %s, status = %s, payment_mode = %s WHERE bill_id = %s",
        "query": "SELECT b.bill_id, b.visit_id, p.name, b.amount, b.date, b.status, b.payment_mode FROM bills b JOIN visits v ON v.visit_id = b.visit_id JOIN patients p ON p.patient_id = v.patient_id ORDER BY b.bill_id",
        "columns": ("ID", "Visit ID", "Patient", "Amount", "Date", "Status", "Payment mode"),
        "search": ("CAST(b.bill_id AS CHAR)", "CAST(b.visit_id AS CHAR)", "p.name", "b.status", "b.payment_mode"),
    },
    "medicines": {
        "title": "Medicines",
        "table": "medicines",
        "primary_key": "medicine_id",
        "fields": [
            ("Name", "name", "text", True, None),
            ("Dosage", "dosage", "text", False, None),
            ("Price", "price", "number", False, None),
            ("Stock", "stock", "number", False, None),
        ],
        "values": ("name", "dosage", "price", "stock"),
        "insert": "INSERT INTO medicines (name, dosage, price, stock) VALUES (%s, %s, %s, %s)",
        "update": "UPDATE medicines SET name = %s, dosage = %s, price = %s, stock = %s WHERE medicine_id = %s",
        "query": "SELECT medicine_id, name, dosage, price, stock FROM medicines ORDER BY medicine_id",
        "columns": ("ID", "Name", "Dosage", "Price", "Stock"),
        "search": ("name", "dosage"),
    },
    "medical_records": {
        "title": "Medical records",
        "table": "medical_records",
        "primary_key": "record_id",
        "fields": [
            ("Visit", "visit_id", "select", True, "visits"),
            ("Medicine (optional)", "medicine_id", "select", False, "medicines"),
            ("Room (optional)", "room_id", "select", False, "rooms"),
            ("Details", "details", "textarea", False, None),
            ("Prescription", "prescription", "textarea", False, None),
            ("Test results", "test_results", "textarea", False, None),
        ],
        "values": ("visit_id", "medicine_id", "room_id", "details", "prescription", "test_results"),
        "insert": "INSERT INTO medical_records (visit_id, medicine_id, room_id, details, prescription, test_results) VALUES (%s, %s, %s, %s, %s, %s)",
        "update": "UPDATE medical_records SET visit_id = %s, medicine_id = %s, room_id = %s, details = %s, prescription = %s, test_results = %s WHERE record_id = %s",
        "query": "SELECT mr.record_id, mr.visit_id, p.name, m.name, r.room_id, mr.details, mr.prescription, mr.test_results FROM medical_records mr JOIN visits v ON v.visit_id = mr.visit_id JOIN patients p ON p.patient_id = v.patient_id LEFT JOIN medicines m ON m.medicine_id = mr.medicine_id LEFT JOIN rooms r ON r.room_id = mr.room_id ORDER BY mr.record_id",
        "columns": ("ID", "Visit ID", "Patient", "Medicine", "Room ID", "Details", "Prescription", "Test results"),
        "search": ("CAST(mr.record_id AS CHAR)", "CAST(mr.visit_id AS CHAR)", "p.name", "m.name", "mr.details", "mr.prescription", "mr.test_results"),
    },
    "rooms": {
        "title": "Rooms",
        "table": "rooms",
        "primary_key": "room_id",
        "fields": [
            ("Room type", "room_type", "text", False, None),
            ("Ward", "ward", "text", False, None),
            ("Bed number", "bed_number", "text", False, None),
            ("Status", "status", "text", False, None),
        ],
        "values": ("room_type", "ward", "bed_number", "status"),
        "insert": "INSERT INTO rooms (room_type, ward, bed_number, status) VALUES (%s, %s, %s, %s)",
        "update": "UPDATE rooms SET room_type = %s, ward = %s, bed_number = %s, status = %s WHERE room_id = %s",
        "query": "SELECT room_id, room_type, ward, bed_number, status FROM rooms ORDER BY room_id",
        "columns": ("ID", "Room type", "Ward", "Bed number", "Status"),
        "search": ("room_type", "ward", "bed_number", "status"),
    },
    "lab_tests": {
        "title": "Lab tests",
        "table": "lab_tests",
        "primary_key": "test_id",
        "fields": [
            ("Test name", "test_name", "text", True, None),
            ("Cost", "cost", "number", False, None),
            ("Result", "result", "text", False, None),
        ],
        "values": ("test_name", "cost", "result"),
        "insert": "INSERT INTO lab_tests (test_name, cost, result) VALUES (%s, %s, %s)",
        "update": "UPDATE lab_tests SET test_name = %s, cost = %s, result = %s WHERE test_id = %s",
        "query": "SELECT test_id, test_name, cost, result FROM lab_tests ORDER BY test_id",
        "columns": ("ID", "Test name", "Cost", "Result"),
        "search": ("test_name", "result"),
    },
    "medical_record_lab_tests": {
        "title": "Lab test orders",
        "table": "medical_record_lab_tests",
        "primary_key": "record_test_id",
        "fields": [
            ("Medical record", "record_id", "select", True, "medical_records"),
            ("Lab test", "test_id", "select", True, "lab_tests"),
        ],
        "values": ("record_id", "test_id"),
        "insert": "INSERT INTO medical_record_lab_tests (record_id, test_id) VALUES (%s, %s)",
        "update": "UPDATE medical_record_lab_tests SET record_id = %s, test_id = %s WHERE record_test_id = %s",
        "query": "SELECT mrt.record_test_id, mrt.record_id, p.name, lt.test_name FROM medical_record_lab_tests mrt JOIN medical_records mr ON mr.record_id = mrt.record_id JOIN visits v ON v.visit_id = mr.visit_id JOIN patients p ON p.patient_id = v.patient_id JOIN lab_tests lt ON lt.test_id = mrt.test_id ORDER BY mrt.record_test_id",
        "columns": ("ID", "Record ID", "Patient", "Lab test"),
        "search": ("CAST(mrt.record_test_id AS CHAR)", "CAST(mrt.record_id AS CHAR)", "p.name", "lt.test_name"),
    },
}

OPTION_QUERIES = {
    "departments": "SELECT department_id, department_name FROM departments ORDER BY department_name",
    "doctors": "SELECT doctor_id, name FROM doctors ORDER BY name",
    "patients": "SELECT patient_id, name FROM patients ORDER BY name",
    "visits": "SELECT v.visit_id, CONCAT(v.visit_id, ' - ', p.name, ' - ', v.visit_date) FROM visits v JOIN patients p ON p.patient_id = v.patient_id ORDER BY v.visit_id DESC",
    "medicines": "SELECT medicine_id, name FROM medicines ORDER BY name",
    "rooms": "SELECT room_id, CONCAT(room_id, ' - ', COALESCE(room_type, ''), ' - ', COALESCE(bed_number, '')) FROM rooms ORDER BY room_id",
    "medical_records": "SELECT mr.record_id, CONCAT(mr.record_id, ' - ', p.name, ' - ', v.visit_date) FROM medical_records mr JOIN visits v ON v.visit_id = mr.visit_id JOIN patients p ON p.patient_id = v.patient_id ORDER BY mr.record_id DESC",
    "lab_tests": "SELECT test_id, test_name FROM lab_tests ORDER BY test_name",
}


def open_database():
    return mysql.connector.connect(
        host="127.0.0.1",
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database="hospital_management_system",
    )


def fetch_rows(query, values=()):
    connection = open_database()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(query, values)
            return cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password, stored_hash):
    try:
        salt_hex, expected_hash = stored_hash.split("$", 1)
        actual_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex),
            PASSWORD_ITERATIONS,
        ).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual_hash, expected_hash)


def validate_credentials(username, password):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,50}", username):
        return "Username must be 3-50 characters: letters, numbers, ., _ or -."
    if len(password) < 12:
        return "Password must be at least 12 characters."
    return ""


def setup_initial_account():
    while True:
        username = input("Create hospital app login username: ").strip()
        if re.fullmatch(r"[A-Za-z0-9_.-]{3,50}", username):
            break
        print("Username must be 3-50 characters: letters, numbers, ., _ or -.")
    while True:
        password = getpass("Create hospital app login password: ")
        error = validate_credentials(username, password)
        if error:
            print(error)
            continue
        if password != getpass("Confirm password: "):
            print("Passwords did not match. Try again.")
            continue
        break
    connection = open_database()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO app_users (username, password_hash) VALUES (%s, %s)",
                (username, hash_password(password)),
            )
            connection.commit()
        except Error:
            connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()
    print("Hospital app login account created.")


def ensure_user_table():
    connection = open_database()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS app_users (
                    user_id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()
            cursor.execute("SELECT COUNT(*) FROM app_users")
            return cursor.fetchone()[0]
        finally:
            cursor.close()
    finally:
        connection.close()


def render_field(field, option_data, values=None):
    label, name, kind, required, option_source = field
    values = values or {}
    required_attr = " required" if required else ""
    safe_name = escape(name, quote=True)
    safe_label = escape(label)
    value = "" if values.get(name) is None else str(values[name])
    if kind == "select":
        placeholder = "-- Choose --" if required else "-- None --"
        options = f'<option value="">{placeholder}</option>'
        options += "".join(
            f'<option value="{escape(str(option_id), quote=True)}"'
            f'{" selected" if str(option_id) == value else ""}>'
            f'{escape(str(option_label))}</option>'
            for option_id, option_label in option_data.get(option_source, [])
        )
        return f"<label>{safe_label}<select name=\"{safe_name}\"{required_attr}>{options}</select></label>"
    if kind == "textarea":
        return (
            f"<label>{safe_label}<textarea name=\"{safe_name}\" maxlength=\"2000\""
            f"{required_attr}>{escape(value)}</textarea></label>"
        )
    extra = ' step="0.01" min="0"' if kind == "number" else ""
    return (
        f"<label>{safe_label}<input name=\"{safe_name}\" type=\"{kind}\""
        f' value="{escape(value, quote=True)}"{extra}{required_attr}></label>'
    )


def login_page(message=""):
    message_html = f'<p class="message error">{escape(message)}</p>' if message else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in - Hospital Management System</title><style>
body {{ font: 16px Arial,sans-serif; background:#f1f5f9; color:#172033; margin:0; }}
main {{ max-width:420px; margin:10vh auto; padding:32px; background:white; border-radius:14px; box-shadow:0 8px 30px #0f172a18; }}
label {{ display:block; margin:16px 0; }} input {{ box-sizing:border-box; width:100%; padding:11px; margin-top:6px; border:1px solid #cbd5e1; border-radius:6px; }}
button {{ padding:11px 18px; background:#0f766e; color:white; border:0; border-radius:6px; cursor:pointer; }}
.message {{ padding:12px; border-radius:6px; }} .error {{ background:#fff1f0; }}
</style></head><body><main><h1>Hospital Management System</h1><h2>Sign in</h2>{message_html}
<form method="post" action="/login"><label>Username<input name="username" autocomplete="username" required></label>
<label>Password<input name="password" type="password" autocomplete="current-password" required></label>
<button type="submit">Sign in</button></form></main></body></html>"""


def page(section_key=None, message="", edit_id=None, search="", csrf_token="", username=""):
    navigation = "".join(
        f'<a class="{"active" if key == section_key else ""}" href="/{key}">{escape(section["title"])}</a>'
        for key, section in SECTIONS.items()
    )
    notice = f'<p class="message">{escape(message)}</p>' if message else ""
    dashboard = section_key is None
    if dashboard:
        cards = []
        for key, section in SECTIONS.items():
            total = fetch_rows(f"SELECT COUNT(*) FROM {section['table']}")[0][0]
            cards.append(
                f'<a class="card" href="/{key}"><span>{escape(section["title"])}</span>'
                f'<strong>{total}</strong><small>Manage records →</small></a>'
            )
        content = f'<section class="cards">{"".join(cards)}</section>'
        title = "Overview"
    else:
        section = SECTIONS[section_key]
        edit_values = {}
        if edit_id is not None:
            record = fetch_rows(
                f"SELECT {', '.join(section['values'])} FROM {section['table']} "
                f"WHERE {section['primary_key']} = %s",
                (edit_id,),
            )
            if record:
                edit_values = dict(zip(section["values"], record[0]))
            else:
                edit_id = None
                message = "Record not found."
                notice = f'<p class="message">{escape(message)}</p>'
        option_sources = {
            field[4] for field in section["fields"] if field[4] is not None
        }
        option_data = {source: fetch_rows(OPTION_QUERIES[source]) for source in option_sources}
        query = section["query"]
        parameters = ()
        if search:
            query = query.replace(
                "ORDER BY",
                "WHERE (" + " OR ".join(f"{column} LIKE %s" for column in section["search"]) + ") ORDER BY",
                1,
            )
            parameters = tuple(f"%{search}%" for _ in section["search"])
        records = fetch_rows(query, parameters)
        headers = "".join(f"<th>{escape(column)}</th>" for column in section["columns"])
        rows = []
        for record in records:
            record_id = record[0]
            cells = "".join(
                f"<td>{escape('' if value is None else str(value))}</td>"
                for value in record
            )
            actions = (
                f'<td class="actions"><a href="/{section_key}?edit={record_id}">Edit</a>'
                f'<form method="post" action="/{section_key}/delete" onsubmit="return confirm(\'Delete this record?\')">'
                f'<input type="hidden" name="csrf_token" value="{escape(csrf_token, quote=True)}">'
                f'<input type="hidden" name="record_id" value="{record_id}">'
                f'<button class="link danger" type="submit">Delete</button></form></td>'
            )
            rows.append(f"<tr>{cells}{actions}</tr>")
        form_fields = "".join(render_field(field, option_data, edit_values) for field in section["fields"])
        content = f"""
{notice}
<section class="panel">
<h2>{"Edit " + escape(section["title"]) if edit_id is not None else "Add " + escape(section["title"])}</h2>
<form class="record-form" method="post" action="/{section_key + '/edit' if edit_id is not None else section_key}">
<input type="hidden" name="csrf_token" value="{escape(csrf_token, quote=True)}">
{f'<input type="hidden" name="record_id" value="{edit_id}">' if edit_id is not None else ""}
{form_fields}<div class="form-actions"><button type="submit">{"Update" if edit_id is not None else "Save"}</button>
{f'<a href="/{section_key}">Cancel</a>' if edit_id is not None else ""}</div></form></section>
<section class="panel"><div class="table-heading"><h2>Saved {escape(section["title"])}</h2>
<form method="get" action="/{section_key}" class="search"><input name="search" type="search" value="{escape(search, quote=True)}" placeholder="Search records">
<button type="submit">Search</button>{"<a href='/" + section_key + "'>Clear</a>" if search else ""}</form></div>
<div class="table-wrap"><table><thead><tr>{headers}<th>Actions</th></tr></thead>
<tbody>{"".join(rows) if rows else f'<tr><td colspan="{len(section["columns"]) + 1}">No records found.</td></tr>'}</tbody></table></div></section>"""
        title = section["title"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} - Hospital Management System</title><style>
:root {{ color-scheme:light; --ink:#172033; --muted:#64748b; --line:#dbe3ed; --teal:#0f766e; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:#f1f5f9; color:var(--ink); font:15px Arial,sans-serif; }}
header {{ background:#0f2d3a; color:white; padding:22px max(22px,calc((100% - 1280px)/2)); }}
header h1 {{ margin:0; font-size:23px; }} main {{ max-width:1280px; margin:auto; padding:24px; }}
nav {{ display:flex; gap:8px; flex-wrap:wrap; margin:18px 0 26px; }} nav a {{ color:#164e63; background:white; border:1px solid var(--line); border-radius:20px; padding:8px 13px; text-decoration:none; }}
nav a.active, nav a:hover {{ color:white; background:var(--teal); border-color:var(--teal); }}
.topline {{ display:flex; justify-content:space-between; align-items:center; gap:16px; }} .topline a {{ color:#d1fae5; }}
.message {{ padding:12px 14px; background:#ecfdf5; border-radius:8px; }} .panel {{ background:white; border:1px solid var(--line); border-radius:12px; padding:20px; margin:18px 0; }}
h2 {{ margin:0 0 16px; font-size:19px; }} .record-form {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:0 18px; }}
label {{ display:block; margin:6px 0 12px; color:#334155; font-size:14px; }} input,textarea,select {{ display:block; width:100%; margin-top:6px; padding:10px; border:1px solid #cbd5e1; border-radius:6px; font:inherit; background:white; }}
textarea {{ min-height:76px; resize:vertical; }} button {{ padding:10px 14px; color:white; background:var(--teal); border:0; border-radius:6px; font:inherit; cursor:pointer; }}
.form-actions {{ grid-column:1/-1; display:flex; align-items:center; gap:12px; }} .form-actions a {{ color:var(--muted); }}
.table-heading {{ display:flex; align-items:center; justify-content:space-between; gap:14px; flex-wrap:wrap; }} .table-heading h2 {{ margin:0; }}
.search {{ display:flex; gap:8px; align-items:center; }} .search input {{ width:min(280px,55vw); margin:0; }} .search a {{ color:var(--muted); }}
.table-wrap {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; margin-top:16px; font-size:14px; }} th,td {{ border-bottom:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }} th {{ background:#f8fafc; white-space:nowrap; }}
.actions {{ white-space:nowrap; }} .actions a {{ margin-right:10px; color:var(--teal); }} .actions form {{ display:inline; }} button.link {{ padding:0; background:none; color:#b91c1c; }} .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; }}
.card {{ display:grid; gap:10px; padding:20px; text-decoration:none; color:var(--ink); background:white; border:1px solid var(--line); border-radius:12px; }} .card strong {{ font-size:30px; color:var(--teal); }} .card small {{ color:var(--muted); }}
@media(max-width:600px) {{ main {{ padding:16px; }} header {{ padding:18px 16px; }} .topline {{ align-items:flex-start; flex-direction:column; }} .search {{ width:100%; }} .search input {{ flex:1; }} }}
</style></head><body><header><div class="topline"><h1>Hospital Management System</h1>
<span>Signed in as {escape(username)} · <form style="display:inline" method="post" action="/logout">
<input type="hidden" name="csrf_token" value="{escape(csrf_token, quote=True)}"><button type="submit">Sign out</button></form></span></div></header>
<main><nav><a class="{"active" if dashboard else ""}" href="/">Overview</a>{navigation}</nav><h2>{escape(title)}</h2>{content}</main></body></html>"""


class HospitalApp(BaseHTTPRequestHandler):
    def respond(self, content, status=200, headers=()):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def current_session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except CookieError:
            return None
        morsel = cookie.get("sid")
        session = SESSIONS.get(morsel.value) if morsel else None
        if session and session["expires_at"] <= time():
            del SESSIONS[morsel.value]
            return None
        return (morsel.value, session) if session else None

    def read_form(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length < 0 or length > 1_000_000:
            return None
        try:
            return parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        except UnicodeDecodeError:
            return None

    def redirect(self, location, headers=()):
        self.respond("", 303, (("Location", location), *headers))

    def do_GET(self):
        request = urlsplit(self.path)
        route = request.path.strip("/")
        query = parse_qs(request.query)
        if route == "login":
            if self.current_session():
                self.redirect("/")
            else:
                self.respond(login_page(query.get("message", [""])[0]))
            return
        session_entry = self.current_session()
        if not session_entry:
            self.redirect("/login")
            return
        _, session = session_entry
        if route and route not in SECTIONS:
            self.respond("<h1>Page not found</h1>", 404)
            return
        try:
            edit_id = None
            if query.get("edit"):
                edit_id = int(query["edit"][0])
                if edit_id < 1:
                    raise ValueError
            self.respond(
                page(
                    route or None,
                    query.get("message", [""])[0],
                    edit_id,
                    query.get("search", [""])[0].strip(),
                    session["csrf_token"],
                    session["username"],
                )
            )
        except ValueError:
            self.respond("<h1>Invalid record ID</h1>", 400)
        except Error as error:
            print(f"Database error while loading {route or 'overview'}: {error}")
            self.respond("<h1>Could not load this page</h1><p>Check the terminal for details.</p>", 500)

    def do_POST(self):
        route = urlsplit(self.path).path.strip("/")
        form = self.read_form()
        if form is None:
            self.respond("<h1>Invalid request body</h1>", 400)
            return
        if route == "login":
            username = form.get("username", [""])[0].strip()
            password = form.get("password", [""])[0]
            try:
                accounts = fetch_rows(
                    "SELECT user_id, username, password_hash FROM app_users WHERE username = %s",
                    (username,),
                )
            except Error as error:
                print(f"Database error during sign in: {error}")
                self.respond("<h1>Sign in is temporarily unavailable</h1>", 500)
                return
            if not accounts or not verify_password(password, accounts[0][2]):
                self.respond(login_page("Incorrect username or password."), 401)
                return
            token = secrets.token_urlsafe(32)
            SESSIONS[token] = {
                "user_id": accounts[0][0],
                "username": accounts[0][1],
                "csrf_token": secrets.token_urlsafe(32),
                "expires_at": time() + SESSION_TTL_SECONDS,
            }
            cookie = f"sid={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_TTL_SECONDS}"
            self.redirect("/", (("Set-Cookie", cookie),))
            return
        session_entry = self.current_session()
        if not session_entry:
            self.redirect("/login")
            return
        token, session = session_entry
        if not hmac.compare_digest(form.get("csrf_token", [""])[0], session["csrf_token"]):
            self.respond("<h1>Invalid or expired form. Reload the page and try again.</h1>", 403)
            return
        if route == "logout":
            del SESSIONS[token]
            self.redirect("/login", (("Set-Cookie", "sid=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"),))
            return
        is_edit = route.endswith("/edit")
        is_delete = route.endswith("/delete")
        section_key = route.rsplit("/", 1)[0] if is_edit or is_delete else route
        if section_key not in SECTIONS:
            self.respond("<h1>Page not found</h1>", 404)
            return
        section = SECTIONS[section_key]
        record_id = None
        if is_edit or is_delete:
            try:
                record_id = int(form.get("record_id", [""])[0])
                if record_id < 1:
                    raise ValueError
            except ValueError:
                self.respond("<h1>Invalid record ID</h1>", 400)
                return
        values = {name: form.get(name, [""])[0].strip() for name in section["values"]}
        missing = [
            label for label, name, _, required, _ in section["fields"]
            if required and not values[name]
        ]
        if missing and not is_delete:
            try:
                self.respond(
                    page(
                        section_key,
                        "Please fill in: " + ", ".join(missing),
                        record_id if is_edit else None,
                        csrf_token=session["csrf_token"],
                        username=session["username"],
                    )
                )
            except Error as error:
                print(f"Database error while validating {section_key}: {error}")
                self.respond("<h1>Could not load the form</h1>", 500)
            return
        parameters = tuple(values[name] or None for name in section["values"])
        if is_edit:
            parameters += (record_id,)
        connection = None
        cursor = None
        try:
            connection = open_database()
            cursor = connection.cursor()
            if is_delete:
                cursor.execute(
                    f"DELETE FROM {section['table']} WHERE {section['primary_key']} = %s",
                    (record_id,),
                )
                if cursor.rowcount == 0:
                    raise ValueError("Record not found.")
                message = "Record deleted successfully."
            elif is_edit:
                cursor.execute(section["update"], parameters)
                if cursor.rowcount == 0:
                    cursor.execute(
                        f"SELECT {section['primary_key']} FROM {section['table']} "
                        f"WHERE {section['primary_key']} = %s",
                        (record_id,),
                    )
                    if cursor.fetchone() is None:
                        raise ValueError("Record not found.")
                message = f"{section['title']} updated successfully."
            else:
                cursor.execute(section["insert"], parameters)
                message = f"{section['title']} saved successfully."
            connection.commit()
        except ValueError as error:
            if connection:
                connection.rollback()
            message = str(error)
        except Error as error:
            if connection:
                connection.rollback()
            print(f"Database error while processing {section_key}: {error}")
            if is_delete and getattr(error, "errno", None) == 1451:
                message = "Cannot delete this record while other records depend on it."
            elif is_delete:
                message = "Could not delete record. Check the terminal for details."
            else:
                message = "Could not save record. Check the terminal for details."
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
        self.redirect(f"/{section_key}?message={quote(message)}")

    def log_message(self, format_string, *args):
        print(format_string % args)


if __name__ == "__main__":
    MYSQL_USER = input("MySQL username (often root): ").strip()
    MYSQL_PASSWORD = getpass("MySQL password: ")
    try:
        connection = open_database()
        connection.close()
    except Error as error:
        raise SystemExit(
            "Could not connect to the hospital_management_system database. "
            "Create it by running hospital_management_system.sql first. "
            f"MySQL error: {error}"
        ) from error
    try:
        account_count = ensure_user_table()
    except Error as error:
        raise SystemExit(f"Could not initialize hospital app accounts: {error}") from error
    if account_count == 0:
        print("No hospital app account exists yet. Create the first admin account.")
        try:
            setup_initial_account()
        except Error as error:
            raise SystemExit(f"Could not create the hospital app account: {error}") from error
    print("Hospital app is running at http://127.0.0.1:8001")
    HTTPServer(("127.0.0.1", 8001), HospitalApp).serve_forever()
