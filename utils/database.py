"""
SmartPack-LM: SQLite Database Layer
Stores inspection history, extracted fields, compliance assessments, and provides analytics metrics for the GovTech dashboard.
"""
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "smartpack.db")

def get_db_connection(db_path=None):
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Create users table for Admin & Inspector authentication
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inspector_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        email TEXT,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'INSPECTOR',
        phone TEXT,
        department TEXT,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        created_at TEXT NOT NULL
    )
    """)

    # Create inspections table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inspections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        product_name TEXT,
        manufacturer TEXT,
        country_of_origin TEXT,
        net_quantity TEXT,
        mrp TEXT,
        manufacturing_date TEXT,
        best_before TEXT,
        consumer_care TEXT,
        unit_sale_price TEXT,
        dimensions TEXT,
        compliance_score REAL NOT NULL,
        overall_status TEXT NOT NULL,
        detected_issues TEXT,
        extracted_data TEXT,
        image_paths TEXT,
        evidence_image_path TEXT,
        officer_notes TEXT,
        location_data TEXT,
        inspector_id INTEGER
    )
    """)
    conn.commit()

    # Create complaints table for citizen grievance redressal
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_no TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT,
        user_email TEXT,
        contact_number TEXT,
        inspection_id INTEGER NOT NULL,
        product_name TEXT,
        compliance_result TEXT,
        violations TEXT,
        location_address TEXT,
        latitude REAL,
        longitude REAL,
        inspection_timestamp TEXT,
        created_at TEXT NOT NULL,
        evidence_image_path TEXT,
        retailer_details TEXT,
        description TEXT,
        status TEXT NOT NULL DEFAULT 'Submitted',
        admin_notes TEXT
    )
    """)
    conn.commit()

    # Gracefully migrate inspections table if columns are missing
    cursor.execute("PRAGMA table_info(inspections)")
    columns = [col["name"] for col in cursor.fetchall()]
    if "location_data" not in columns:
        try:
            cursor.execute("ALTER TABLE inspections ADD COLUMN location_data TEXT")
            conn.commit()
        except Exception as e:
            print(f"[SmartPack-LM] Database migration notice (location_data): {e}")

    if "inspector_id" not in columns:
        try:
            cursor.execute("ALTER TABLE inspections ADD COLUMN inspector_id INTEGER")
            conn.commit()
        except Exception as e:
            print(f"[SmartPack-LM] Database migration notice (inspector_id): {e}")

    if "user_id" not in columns:
        try:
            cursor.execute("ALTER TABLE inspections ADD COLUMN user_id INTEGER")
            conn.commit()
        except Exception as e:
            print(f"[SmartPack-LM] Database migration notice (user_id): {e}")

    if "performed_by" not in columns:
        try:
            cursor.execute("ALTER TABLE inspections ADD COLUMN performed_by TEXT")
            conn.commit()
        except Exception as e:
            print(f"[SmartPack-LM] Database migration notice (performed_by): {e}")

    if "role" not in columns:
        try:
            cursor.execute("ALTER TABLE inspections ADD COLUMN role TEXT DEFAULT 'PUBLIC'")
            conn.commit()
        except Exception as e:
            print(f"[SmartPack-LM] Database migration notice (role): {e}")

    # Ensure default Admin account exists if no admin user present
    cursor.execute("SELECT id FROM users WHERE role = 'ADMIN' LIMIT 1")
    admin_row = cursor.fetchone()
    if not admin_row:
        from werkzeug.security import generate_password_hash
        admin_pass = os.environ.get("SMARTPACK_ADMIN_PASSWORD", "Admin@SIH2026")
        admin_hash = generate_password_hash(admin_pass)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute("""
            INSERT INTO users (inspector_id, name, username, email, password_hash, role, phone, department, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "ADMIN-001",
                "Directorate General of Legal Metrology",
                "admin",
                "admin@smartpack.gov.in",
                admin_hash,
                "ADMIN",
                "+91-11-2338-0000",
                "Ministry of Consumer Affairs, Food & Public Distribution",
                "ACTIVE",
                now_str
            ))
            conn.commit()
            print("[SmartPack-LM] Default Admin initialized: username 'admin'")
        except Exception as e:
            print(f"[SmartPack-LM] Notice creating default admin: {e}")

    conn.close()

# =========================================================
# USER & INSPECTOR MANAGEMENT
# =========================================================
def create_user(*args, db_path=None, **kwargs):
    from werkzeug.security import generate_password_hash
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    if args and isinstance(args[0], dict):
        user_data = dict(args[0])
    else:
        user_data = {}
    user_data.update(kwargs)

    raw_password = user_data.get("password")
    pwd_hash = generate_password_hash(raw_password) if raw_password else user_data.get("password_hash")
    now_str = user_data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    role = user_data.get("role", "INSPECTOR").upper()
    badge_id = user_data.get("inspector_id")
    if not badge_id:
        import time
        if role == "USER":
            badge_id = f"USR-{int(time.time() * 1000)}"
        else:
            badge_id = f"INS-{int(time.time() * 1000)}"

    default_dept = "Consumer / Citizen" if role == "USER" else "Legal Metrology Enforcement"
    department = user_data.get("department") or default_dept

    try:
        cursor.execute("""
        INSERT INTO users (
            inspector_id, name, username, email, password_hash,
            role, phone, department, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            badge_id,
            user_data.get("name"),
            user_data.get("username", "").strip().lower(),
            user_data.get("email", ""),
            pwd_hash,
            role,
            user_data.get("phone", ""),
            department,
            user_data.get("status", "ACTIVE"),
            now_str
        ))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {"success": True, "id": user_id, "user_id": user_id, "error": None}
    except sqlite3.IntegrityError as ie:
        conn.close()
        return {"success": False, "id": None, "user_id": None, "error": f"Username or Inspector ID already exists: {ie}"}
    except Exception as e:
        conn.close()
        return {"success": False, "id": None, "user_id": None, "error": str(e)}

def get_user_by_id(user_id, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_username(username, db_path=None):
    if not username:
        return None
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE", (username.strip().lower(), username.strip().lower()))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def authenticate_user(username, password, db_path=None):
    from werkzeug.security import check_password_hash
    user = get_user_by_username(username, db_path=db_path)
    if not user:
        return None
    if user.get("status") != "ACTIVE":
        return None
    if not check_password_hash(user.get("password_hash", ""), password):
        return None
    return user

def list_inspectors(search=None, status=None, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    query = """
    SELECT u.*,
           (SELECT COUNT(*) FROM inspections i WHERE i.inspector_id = u.id) as total_scans,
           (SELECT COUNT(*) FROM inspections i WHERE i.inspector_id = u.id AND i.overall_status = 'COMPLIANT') as compliant_scans,
           (SELECT MAX(i.timestamp) FROM inspections i WHERE i.inspector_id = u.id) as last_scan
    FROM users u
    WHERE u.role = 'INSPECTOR'
    """
    params = []
    if search:
        query += " AND (u.name LIKE ? OR u.username LIKE ? OR u.inspector_id LIKE ? OR u.department LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])
    if status and status != 'ALL':
        query += " AND u.status = ?"
        params.append(status)

    query += " ORDER BY u.id DESC"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_user_status(user_id, status, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE id = ? AND role = 'INSPECTOR'", (status, user_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def list_users(search=None, role=None, status=None, db_path=None):
    """
    Retrieves directory of registered portal users without exposing password hashes.
    Supports filtering by search query (name, username, email, phone), role, and status.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    query = """
    SELECT u.id, u.inspector_id, u.name, u.username, u.email, u.role, u.phone, u.department, u.status, u.created_at,
           (SELECT COUNT(*) FROM inspections i WHERE i.user_id = u.id OR (i.inspector_id = u.id AND u.role IN ('INSPECTOR', 'ADMIN'))) as scan_count
    FROM users u
    WHERE 1=1
    """
    params = []
    if search:
        query += " AND (u.name LIKE ? OR u.username LIKE ? OR u.email LIKE ? OR u.phone LIKE ? OR u.inspector_id LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term, term])
    if role and role != 'ALL':
        query += " AND u.role = ?"
        params.append(role)
    if status and status != 'ALL':
        query += " AND u.status = ?"
        params.append(status)

    query += " ORDER BY u.id ASC"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def reset_user_password(user_id, new_password, db_path=None):
    from werkzeug.security import generate_password_hash
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    pwd_hash = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pwd_hash, user_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

# =========================================================
# INSPECTIONS DATABASE OPERATIONS
# =========================================================
def save_inspection(data, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    timestamp = data.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    detected_issues = json.dumps(data.get("detected_issues", []))
    extracted_data = json.dumps(data.get("extracted_data", {}))
    image_paths = json.dumps(data.get("image_paths", {}))
    
    raw_loc = data.get("location_data")
    location_data = json.dumps(raw_loc) if isinstance(raw_loc, dict) else (raw_loc or "")
    inspector_id = data.get("inspector_id")
    user_id = data.get("user_id")
    performed_by = data.get("performed_by") or data.get("officer_notes") or "Field Inspection"
    role = data.get("role") or "PUBLIC"
    
    cursor.execute("""
    INSERT INTO inspections (
        timestamp, product_name, manufacturer, country_of_origin,
        net_quantity, mrp, manufacturing_date, best_before,
        consumer_care, unit_sale_price, dimensions,
        compliance_score, overall_status, detected_issues,
        extracted_data, image_paths, evidence_image_path, officer_notes,
        location_data, inspector_id, user_id, performed_by, role
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        timestamp,
        data.get("product_name", "Unknown Commodity"),
        data.get("manufacturer", "Not Specified"),
        data.get("country_of_origin", "Not Detected"),
        data.get("net_quantity", "Not Detected"),
        data.get("mrp", "Not Detected"),
        data.get("manufacturing_date", "Not Detected"),
        data.get("best_before", "N/A"),
        data.get("consumer_care", "Not Detected"),
        data.get("unit_sale_price", "N/A"),
        data.get("dimensions", "N/A"),
        float(data.get("compliance_score", 0.0)),
        data.get("overall_status", "REVIEW"),
        detected_issues,
        extracted_data,
        image_paths,
        data.get("evidence_image_path", ""),
        data.get("officer_notes", ""),
        location_data,
        inspector_id,
        user_id,
        performed_by,
        role
    ))
    inspection_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return inspection_id

def get_inspection(inspection_id, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT i.*, 
           COALESCE(u.name, i.performed_by, 'Authorized Officer') as inspector_name, 
           COALESCE(u.inspector_id, 'INSP') as inspector_badge, 
           COALESCE(u.department, 'Legal Metrology') as inspector_dept,
           usr.name as user_name,
           usr.email as user_email
    FROM inspections i
    LEFT JOIN users u ON i.inspector_id = u.id
    LEFT JOIN users usr ON i.user_id = usr.id
    WHERE i.id = ?
    """, (inspection_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    
    item = dict(row)
    item["detected_issues"] = json.loads(item["detected_issues"] or "[]")
    item["extracted_data"] = json.loads(item["extracted_data"] or "{}")
    item["image_paths"] = json.loads(item["image_paths"] or "{}")
    if "location_data" in item and item["location_data"]:
        try:
            item["location_data"] = json.loads(item["location_data"])
        except Exception:
            item["location_data"] = None
    else:
        item["location_data"] = None
    return item

def list_inspections(search=None, status=None, inspector_id=None, user_id=None, role=None, date_from=None, date_to=None, limit=50, offset=0, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    query = """
    SELECT i.*, 
           COALESCE(u.name, i.performed_by, 'Field Inspection') as inspector_name, 
           COALESCE(u.inspector_id, '') as inspector_badge, 
           COALESCE(u.department, 'Legal Metrology Enforcement') as inspector_dept
    FROM inspections i
    LEFT JOIN users u ON (i.inspector_id = u.id OR i.user_id = u.id)
    WHERE 1=1
    """
    params = []
    
    if search:
        query += " AND (i.product_name LIKE ? OR i.manufacturer LIKE ? OR i.country_of_origin LIKE ? OR i.id = ? OR u.name LIKE ? OR u.inspector_id LIKE ? OR i.performed_by LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, search if str(search).isdigit() else -1, term, term, term])
        
    if status and status != "ALL":
        query += " AND i.overall_status = ?"
        params.append(status)

    if user_id:
        query += " AND (i.user_id = ? OR (i.inspector_id = ? AND i.role = 'USER'))"
        params.extend([user_id, user_id])
    elif inspector_id:
        query += " AND i.inspector_id = ?"
        params.append(inspector_id)
    elif role:
        query += " AND (i.role = ? OR i.role IS NULL)"
        params.append(role)

    if date_from:
        query += " AND i.timestamp >= ?"
        params.append(f"{date_from} 00:00:00")

    if date_to:
        query += " AND i.timestamp <= ?"
        params.append(f"{date_to} 23:59:59")
        
    query += " ORDER BY i.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    
    count_query = """
    SELECT COUNT(*) as total
    FROM inspections i
    LEFT JOIN users u ON (i.inspector_id = u.id OR i.user_id = u.id)
    WHERE 1=1
    """
    count_params = []
    if search:
        count_query += " AND (i.product_name LIKE ? OR i.manufacturer LIKE ? OR i.country_of_origin LIKE ? OR i.id = ? OR u.name LIKE ? OR u.inspector_id LIKE ? OR i.performed_by LIKE ?)"
        count_params.extend([term, term, term, search if str(search).isdigit() else -1, term, term, term])
    if status and status != "ALL":
        count_query += " AND i.overall_status = ?"
        count_params.append(status)
    if user_id:
        count_query += " AND (i.user_id = ? OR (i.inspector_id = ? AND i.role = 'USER'))"
        count_params.extend([user_id, user_id])
    elif inspector_id:
        count_query += " AND i.inspector_id = ?"
        count_params.append(inspector_id)
    elif role:
        count_query += " AND (i.role = ? OR i.role IS NULL)"
        count_params.append(role)
    if date_from:
        count_query += " AND i.timestamp >= ?"
        count_params.append(f"{date_from} 00:00:00")
    if date_to:
        count_query += " AND i.timestamp <= ?"
        count_params.append(f"{date_to} 23:59:59")
        
    cursor.execute(count_query, tuple(count_params))
    total_count = cursor.fetchone()["total"]
    
    conn.close()
    
    inspections = []
    for r in rows:
        item = dict(r)
        item["detected_issues"] = json.loads(item["detected_issues"] or "[]")
        item["extracted_data"] = json.loads(item["extracted_data"] or "{}")
        item["image_paths"] = json.loads(item["image_paths"] or "{}")
        if "location_data" in item and item["location_data"]:
            try:
                item["location_data"] = json.loads(item["location_data"])
            except Exception:
                item["location_data"] = None
        else:
            item["location_data"] = None
        inspections.append(item)
        
    return inspections, total_count

# =========================================================
# COMPLAINTS DATABASE OPERATIONS (CITIZEN GRIEVANCE REDRESSAL)
# =========================================================
def create_complaint(data, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as cnt FROM complaints")
    count_row = cursor.fetchone()
    next_num = (count_row["cnt"] if count_row else 0) + 1
    complaint_no = f"CMP-2026-{next_num:04d}"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raw_violations = data.get("violations", [])
    violations_json = json.dumps(raw_violations) if isinstance(raw_violations, (list, dict)) else (raw_violations or "[]")

    cursor.execute("""
    INSERT INTO complaints (
        complaint_no, user_id, user_name, user_email, contact_number,
        inspection_id, product_name, compliance_result, violations,
        location_address, latitude, longitude, inspection_timestamp,
        created_at, evidence_image_path, retailer_details, description,
        status, admin_notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        complaint_no,
        data.get("user_id"),
        data.get("user_name", "Citizen"),
        data.get("user_email", ""),
        data.get("contact_number", ""),
        data.get("inspection_id"),
        data.get("product_name", "Packaged Commodity"),
        data.get("compliance_result", "NON-COMPLIANT"),
        violations_json,
        data.get("location_address", ""),
        data.get("latitude"),
        data.get("longitude"),
        data.get("inspection_timestamp", ""),
        now_str,
        data.get("evidence_image_path", ""),
        data.get("retailer_details", ""),
        data.get("description", ""),
        data.get("status", "Submitted"),
        data.get("admin_notes", "")
    ))
    complaint_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": complaint_id, "complaint_no": complaint_no}

def get_complaint(complaint_id, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    if str(complaint_id).isdigit():
        cursor.execute("SELECT * FROM complaints WHERE id = ?", (int(complaint_id),))
    else:
        cursor.execute("SELECT * FROM complaints WHERE complaint_no = ?", (str(complaint_id),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    item = dict(row)
    try:
        item["violations"] = json.loads(item["violations"] or "[]")
    except Exception:
        item["violations"] = []
    return item

def list_complaints(user_id=None, status=None, search=None, limit=50, offset=0, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    query = "SELECT * FROM complaints WHERE 1=1"
    params = []

    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)

    if status and status != "ALL":
        query += " AND status = ?"
        params.append(status)

    if search:
        query += " AND (complaint_no LIKE ? OR product_name LIKE ? OR user_name LIKE ? OR user_email LIKE ? OR retailer_details LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term, term])

    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    count_query = "SELECT COUNT(*) as total FROM complaints WHERE 1=1"
    count_params = []
    if user_id:
        count_query += " AND user_id = ?"
        count_params.append(user_id)
    if status and status != "ALL":
        count_query += " AND status = ?"
        count_params.append(status)
    if search:
        count_query += " AND (complaint_no LIKE ? OR product_name LIKE ? OR user_name LIKE ? OR user_email LIKE ? OR retailer_details LIKE ?)"
        count_params.extend([term, term, term, term, term])

    cursor.execute(count_query, tuple(count_params))
    total_count = cursor.fetchone()["total"]
    conn.close()

    complaints = []
    for r in rows:
        item = dict(r)
        try:
            item["violations"] = json.loads(item["violations"] or "[]")
        except Exception:
            item["violations"] = []
        complaints.append(item)
    return complaints, total_count

def update_complaint_status(complaint_id, status, admin_notes=None, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    if admin_notes is not None:
        cursor.execute("UPDATE complaints SET status = ?, admin_notes = ? WHERE id = ?", (status, admin_notes, complaint_id))
    else:
        cursor.execute("UPDATE complaints SET status = ? WHERE id = ?", (status, complaint_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def get_dashboard_metrics(inspector_id=None, user_id=None, role=None, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    where_clause = " WHERE 1=1"
    params = []
    if user_id:
        where_clause += " AND (user_id = ? OR (inspector_id = ? AND role = 'USER'))"
        params.extend([user_id, user_id])
    elif inspector_id:
        where_clause += " AND inspector_id = ?"
        params.append(inspector_id)
    elif role:
        where_clause += " AND (role = ? OR role IS NULL)"
        params.append(role)
    
    cursor.execute(f"SELECT COUNT(*) as total FROM inspections{where_clause}", tuple(params))
    total = cursor.fetchone()["total"]
    
    cursor.execute(f"SELECT COUNT(*) as compliant FROM inspections{where_clause} AND overall_status = 'COMPLIANT'", tuple(params))
    compliant = cursor.fetchone()["compliant"]
    
    cursor.execute(f"SELECT COUNT(*) as review FROM inspections{where_clause} AND overall_status = 'NEEDS REVIEW'", tuple(params))
    review = cursor.fetchone()["review"]
    
    cursor.execute(f"SELECT COUNT(*) as non_compliant FROM inspections{where_clause} AND overall_status = 'NON-COMPLIANT'", tuple(params))
    non_compliant = cursor.fetchone()["non_compliant"]
    
    cursor.execute(f"SELECT AVG(compliance_score) as avg_score FROM inspections{where_clause}", tuple(params))
    avg_score_row = cursor.fetchone()
    avg_score = round(avg_score_row["avg_score"] or 0, 1)

    # Scans Today
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_params = list(params)
    today_where = where_clause + " AND timestamp LIKE ?"
    today_params.append(f"{today_str}%")
    cursor.execute(f"SELECT COUNT(*) as scans_today FROM inspections{today_where}", tuple(today_params))
    scans_today = cursor.fetchone()["scans_today"]

    # Total Inspectors
    cursor.execute("SELECT COUNT(*) as total_inspectors FROM users WHERE role = 'INSPECTOR'")
    total_inspectors = cursor.fetchone()["total_inspectors"]

    cursor.execute("SELECT COUNT(*) as active_inspectors FROM users WHERE role = 'INSPECTOR' AND status = 'ACTIVE'")
    active_inspectors = cursor.fetchone()["active_inspectors"]
    
    # Violation counts
    cursor.execute(f"SELECT detected_issues FROM inspections{where_clause} AND detected_issues IS NOT NULL", tuple(params))
    all_issues_rows = cursor.fetchall()
    
    violation_counts = {
        "MRP Non-Compliance": 0,
        "Net Quantity / Units": 0,
        "Country of Origin Missing": 0,
        "Consumer Care Contact Absent": 0,
        "Mfg / Packaging Date Absent": 0,
        "Manufacturer Address Incomplete": 0,
        "Unit Sale Price Missing": 0
    }
    
    total_violations_found = 0
    for row in all_issues_rows:
        issues = json.loads(row["detected_issues"] or "[]")
        total_violations_found += len(issues)
        for iss in issues:
            field = iss.get("field", "")
            if field == "mrp":
                violation_counts["MRP Non-Compliance"] += 1
            elif field == "net_quantity":
                violation_counts["Net Quantity / Units"] += 1
            elif field == "country_of_origin":
                violation_counts["Country of Origin Missing"] += 1
            elif field == "consumer_care":
                violation_counts["Consumer Care Contact Absent"] += 1
            elif field == "manufacturing_date":
                violation_counts["Mfg / Packaging Date Absent"] += 1
            elif field == "manufacturer":
                violation_counts["Manufacturer Address Incomplete"] += 1
            elif field == "unit_sale_price":
                violation_counts["Unit Sale Price Missing"] += 1

    # Scans over time (last 7 recorded dates)
    cursor.execute(f"""
    SELECT SUBSTR(timestamp, 1, 10) as scan_date, COUNT(*) as count
    FROM inspections{where_clause}
    GROUP BY scan_date
    ORDER BY scan_date DESC
    LIMIT 7
    """, tuple(params))
    timeline_rows = cursor.fetchall()
    scans_timeline = [{"date": r["scan_date"], "count": r["count"]} for r in reversed(timeline_rows)]

    # Inspector-wise scan count (system-wide for admin, or self for inspector)
    inspector_stats = []
    if not inspector_id:
        cursor.execute("""
        SELECT u.id, u.name, u.inspector_id, u.department,
               COUNT(i.id) as total_scans,
               SUM(CASE WHEN i.overall_status = 'COMPLIANT' THEN 1 ELSE 0 END) as compliant_scans,
               SUM(CASE WHEN i.overall_status = 'NON-COMPLIANT' THEN 1 ELSE 0 END) as non_compliant_scans
        FROM users u
        LEFT JOIN inspections i ON u.id = i.inspector_id
        WHERE u.role = 'INSPECTOR'
        GROUP BY u.id
        ORDER BY total_scans DESC
        LIMIT 10
        """)
        inspector_stats = [dict(r) for r in cursor.fetchall()]

    # Location distribution
    cursor.execute(f"SELECT location_data FROM inspections{where_clause} AND location_data IS NOT NULL AND location_data != ''", tuple(params))
    loc_rows = cursor.fetchall()
    city_counts = {}
    for r in loc_rows:
        try:
            loc = json.loads(r["location_data"])
            city = loc.get("city") or loc.get("district") or loc.get("state")
            if city:
                city_counts[city] = city_counts.get(city, 0) + 1
        except Exception:
            pass
    top_cities = sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    # Recent inspections
    joined_where = where_clause.replace("inspector_id", "i.inspector_id").replace("user_id", "i.user_id").replace("role", "i.role")
    cursor.execute(f"""
    SELECT i.*, u.name as inspector_name, u.inspector_id as inspector_badge
    FROM inspections i
    LEFT JOIN users u ON i.inspector_id = u.id
    {joined_where}
    ORDER BY i.id DESC LIMIT 5
    """, tuple(params))
    recent_rows = cursor.fetchall()
    recent = []
    for r in recent_rows:
        item = dict(r)
        item["detected_issues"] = json.loads(item["detected_issues"] or "[]")
        recent.append(item)
        
    conn.close()
    
    return {
        "total_inspections": total,
        "compliant_count": compliant,
        "review_count": review,
        "non_compliant_count": non_compliant,
        "total_violations": non_compliant + review,
        "total_violations_found": total_violations_found,
        "compliance_rate": round((compliant / total * 100) if total > 0 else 0, 1),
        "average_score": avg_score,
        "scans_today": scans_today,
        "total_inspectors": total_inspectors,
        "active_inspectors": active_inspectors,
        "violation_counts": violation_counts,
        "scans_timeline": scans_timeline,
        "inspector_stats": inspector_stats,
        "top_cities": top_cities,
        "recent_inspections": recent
    }

def delete_inspection(inspection_id, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inspections WHERE id = ?", (inspection_id,))
    conn.commit()
    conn.close()

