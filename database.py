import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os

DB_NAME = "school_checkins.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            nfc_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            birthday TEXT,
            emergency_name TEXT,
            emergency_relationship TEXT,
            emergency_phone TEXT,
            emergency_email TEXT,
            emergency_address TEXT,
            allergies TEXT,
            photo_path TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nfc_id TEXT,
            name TEXT,
            action TEXT,
            timestamp TEXT
        )
    ''')
    
    try:
        cursor.execute("SELECT action FROM checkins LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE checkins ADD COLUMN action TEXT")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            nfc_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            photo_path TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employee_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nfc_id TEXT,
            name TEXT,
            action TEXT,
            timestamp TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def register_student_profile(nfc_id, name, birthday, em_name, em_rel, em_phone, em_email, em_addr, allergies, photo_path):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    nfc_id = str(nfc_id).strip()
    name = str(name).strip()

    cursor.execute('''
        INSERT OR REPLACE INTO students (nfc_id, name, birthday, emergency_name, emergency_relationship, emergency_phone, emergency_email, emergency_address, allergies, photo_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (nfc_id, name, birthday, em_name, em_rel, em_phone, em_email, em_addr, allergies, photo_path))
    
    conn.commit()
    conn.close()
    return True, "Success"

def update_student_profile(old_nfc_id, nfc_id, name, birthday, em_name, em_rel, em_phone, em_email, em_addr, allergies, photo_path):
    old_nfc_id = str(old_nfc_id).strip()
    nfc_id = str(nfc_id).strip()
    if not nfc_id:
        return False, "Badge UID is required."

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    conn.execute("BEGIN IMMEDIATE")
    cursor.execute("SELECT 1 FROM students WHERE nfc_id = ? AND nfc_id != ?", (nfc_id, old_nfc_id))
    if cursor.fetchone():
        conn.rollback()
        conn.close()
        return False, "That badge UID is already assigned to another student."

    cursor.execute('''
        UPDATE students
        SET nfc_id = ?, name = ?, birthday = ?, emergency_name = ?,
            emergency_relationship = ?, emergency_phone = ?, emergency_email = ?,
            emergency_address = ?, allergies = ?, photo_path = ?
        WHERE nfc_id = ?
    ''', (nfc_id, name, birthday, em_name, em_rel, em_phone, em_email, em_addr, allergies, photo_path, old_nfc_id))
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    if not updated:
        return False, "The student profile could not be found."
    return True, "Success"

def register_employee_profile(nfc_id, name, photo_path):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    nfc_id = str(nfc_id).strip()
    name = str(name).strip()
    
    cursor.execute('''
        INSERT OR REPLACE INTO employees (nfc_id, name, photo_path)
        VALUES (?, ?, ?)
    ''', (nfc_id, name, photo_path))
    
    conn.commit()
    conn.close()
    return True, "Success"

def update_employee_profile(old_nfc_id, nfc_id, name, photo_path):
    old_nfc_id = str(old_nfc_id).strip()
    nfc_id = str(nfc_id).strip()
    if not nfc_id:
        return False, "Badge UID is required."

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    conn.execute("BEGIN IMMEDIATE")
    cursor.execute("SELECT 1 FROM employees WHERE nfc_id = ? AND nfc_id != ?", (nfc_id, old_nfc_id))
    if cursor.fetchone():
        conn.rollback()
        conn.close()
        return False, "That badge UID is already assigned to another employee."

    cursor.execute(
        "UPDATE employees SET nfc_id = ?, name = ?, photo_path = ? WHERE nfc_id = ?",
        (nfc_id, name, photo_path, old_nfc_id)
    )
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    if not updated:
        return False, "The employee profile could not be found."
    return True, "Success"

def delete_student_profile(nfc_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE nfc_id = ?", (str(nfc_id).strip(),))
    conn.commit()
    conn.close()

def delete_employee_profile(nfc_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM employees WHERE nfc_id = ?", (str(nfc_id).strip(),))
    conn.commit()
    conn.close()

def get_student_full_profile(nfc_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nfc_id, name, birthday, emergency_name, emergency_relationship, emergency_phone, emergency_email, emergency_address, allergies, photo_path FROM students WHERE nfc_id = ?", (str(nfc_id).strip(),))
    row = cursor.fetchone()
    conn.close()
    return row

def get_employee_full_profile(nfc_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nfc_id, name, photo_path FROM employees WHERE nfc_id = ?", (str(nfc_id).strip(),))
    row = cursor.fetchone()
    conn.close()
    return row

def log_student_checkin(nfc_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    nfc_id = str(nfc_id).strip()
    
    cursor.execute("SELECT name, emergency_name, emergency_relationship, emergency_phone, emergency_email, allergies, photo_path FROM students WHERE nfc_id = ?", (nfc_id,))
    result = cursor.fetchone()
    
    if result:
        name, em_name, em_rel, em_phone, em_email, allergies, photo_path = result
        
        today_date = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT action FROM checkins WHERE nfc_id = ? AND timestamp LIKE ? ORDER BY id DESC LIMIT 1", (nfc_id, f"{today_date}%"))
        last_log = cursor.fetchone()
        
        action = "Check Out" if last_log and last_log[0] == "Check In" else "Check In"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("INSERT INTO checkins (nfc_id, name, action, timestamp) VALUES (?, ?, ?, ?)", (nfc_id, name, action, timestamp))
        conn.commit()
        conn.close()
        return {
            "name": name, "action": action, "timestamp": timestamp, 
            "em_name": em_name, "em_rel": em_rel, "em_phone": em_phone, 
            "em_email": em_email, "allergies": allergies, "photo": photo_path
        }
    else:
        conn.close()
        return None

def log_employee_clock(nfc_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    nfc_id = str(nfc_id).strip()
    
    cursor.execute("SELECT name, photo_path FROM employees WHERE nfc_id = ?", (nfc_id,))
    emp_result = cursor.fetchone()
    
    if not emp_result:
        conn.close()
        return None, None, None, None
        
    name, photo_path = emp_result
    
    today_date = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT action FROM employee_logs WHERE nfc_id = ? AND timestamp LIKE ? ORDER BY id DESC LIMIT 1", (nfc_id, f"{today_date}%"))
    last_log = cursor.fetchone()
    
    action = "Clock Out" if last_log and last_log[0] == "Clock In" else "Clock In"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("INSERT INTO employee_logs (nfc_id, name, action, timestamp) VALUES (?, ?, ?, ?)", (nfc_id, name, action, timestamp))
    conn.commit()
    conn.close()
    return name, action, timestamp, photo_path

def get_students_with_todays_activity():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute("SELECT nfc_id, name, birthday, emergency_name, emergency_phone, allergies FROM students")
    students = cursor.fetchall()
    
    results = []
    for s in students:
        nfc_id, name, bday, em_name, phone, allergies = s
        
        cursor.execute("SELECT timestamp FROM checkins WHERE nfc_id = ? AND action = 'Check In' AND timestamp LIKE ? ORDER BY id DESC LIMIT 1", (nfc_id, f"{today_date}%"))
        ci = cursor.fetchone()
        check_in_time = ci[0].split(" ")[1] if ci else "Not Checked In"
        
        cursor.execute("SELECT timestamp FROM checkins WHERE nfc_id = ? AND action = 'Check Out' AND timestamp LIKE ? ORDER BY id DESC LIMIT 1", (nfc_id, f"{today_date}%"))
        co = cursor.fetchone()
        check_out_time = co[0].split(" ")[1] if co else "Not Checked Out"
        
        results.append((nfc_id, name, bday, check_in_time, check_out_time, em_name, phone, allergies))
    
    conn.close()
    return results

def search_students_with_activity(query):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today_date = datetime.now().strftime("%Y-%m-%d")
    q = f"%{query}%"
    
    cursor.execute("SELECT nfc_id, name, birthday, emergency_name, emergency_phone, allergies FROM students WHERE name LIKE ? OR nfc_id LIKE ?", (q, q))
    students = cursor.fetchall()
    
    results = []
    for s in students:
        nfc_id, name, bday, em_name, phone, allergies = s
        cursor.execute("SELECT timestamp FROM checkins WHERE nfc_id = ? AND action = 'Check In' AND timestamp LIKE ? ORDER BY id DESC LIMIT 1", (nfc_id, f"{today_date}%"))
        ci = cursor.fetchone()
        check_in_time = ci[0].split(" ")[1] if ci else "Not Checked In"
        
        cursor.execute("SELECT timestamp FROM checkins WHERE nfc_id = ? AND action = 'Check Out' AND timestamp LIKE ? ORDER BY id DESC LIMIT 1", (nfc_id, f"{today_date}%"))
        co = cursor.fetchone()
        check_out_time = co[0].split(" ")[1] if co else "Not Checked Out"
        
        results.append((nfc_id, name, bday, check_in_time, check_out_time, em_name, phone, allergies))
        
    conn.close()
    return results

def get_all_employees():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nfc_id, name, photo_path FROM employees")
    rows = cursor.fetchall()
    conn.close()
    return rows

def has_todays_activity():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today_date = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) FROM checkins WHERE timestamp LIKE ?", (f"{today_date}%",))
    c_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM employee_logs WHERE timestamp LIKE ?", (f"{today_date}%",))
    e_count = cursor.fetchone()[0]
    conn.close()
    return (c_count + e_count) > 0

def get_employee_hours_report():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nfc_id, name, action, timestamp FROM employee_logs ORDER BY timestamp ASC")
    logs = cursor.fetchall()
    conn.close()

    employee_data = {}
    today_str = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now()
    start_of_week = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    active_sessions = {}

    for nfc_id, name, action, ts_str in logs:
        if nfc_id not in employee_data:
            employee_data[nfc_id] = {"name": name, "daily_seconds": 0, "weekly_seconds": 0}
            
        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        date_str = ts.strftime("%Y-%m-%d")

        if action == "Clock In":
            active_sessions[nfc_id] = ts
        elif action == "Clock Out" and nfc_id in active_sessions:
            start_time = active_sessions.pop(nfc_id)
            duration = (ts - start_time).total_seconds()
            
            if duration > 0:
                if date_str == today_str:
                    employee_data[nfc_id]["daily_seconds"] += duration
                if date_str >= start_of_week:
                    employee_data[nfc_id]["weekly_seconds"] += duration

    report_rows = []
    for nfc_id, data in employee_data.items():
        daily_hrs = round(data["daily_seconds"] / 3600, 2)
        weekly_hrs = round(data["weekly_seconds"] / 3600, 2)
        report_rows.append((data["name"], nfc_id, f"{daily_hrs} hrs", f"{weekly_hrs} hrs"))

    return report_rows

def export_to_excel():
    conn = sqlite3.connect(DB_NAME)
    df_checkins = pd.read_sql_query("SELECT id, nfc_id, name, action, timestamp FROM checkins", conn)
    df_emp_logs = pd.read_sql_query("SELECT id, nfc_id, name, action, timestamp FROM employee_logs", conn)
    conn.close()
    
    os.makedirs("exports", exist_ok=True)
    filename = f"exports/system_report_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df_checkins.to_excel(writer, sheet_name='Student Check-ins (Name & UID)', index=False)
        df_emp_logs.to_excel(writer, sheet_name='Employee Time Logs (Name & UID)', index=False)
        
    return filename

def export_employee_hours_to_excel():
    rows = get_employee_hours_report()
    df = pd.DataFrame(rows, columns=["Employee Name", "NFC ID", "Hours Today", "Hours This Week"])
    
    os.makedirs("exports", exist_ok=True)
    filename = f"exports/employee_hours_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"
    df.to_excel(filename, index=False)
    return filename