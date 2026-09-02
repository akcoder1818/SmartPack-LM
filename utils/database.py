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
        officer_notes TEXT
    )
    """)
    conn.commit()
    conn.close()

def save_inspection(data, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    timestamp = data.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    detected_issues = json.dumps(data.get("detected_issues", []))
    extracted_data = json.dumps(data.get("extracted_data", {}))
    image_paths = json.dumps(data.get("image_paths", {}))
    
    cursor.execute("""
    INSERT INTO inspections (
        timestamp, product_name, manufacturer, country_of_origin,
        net_quantity, mrp, manufacturing_date, best_before,
        consumer_care, unit_sale_price, dimensions,
        compliance_score, overall_status, detected_issues,
        extracted_data, image_paths, evidence_image_path, officer_notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        data.get("officer_notes", "")
    ))
    inspection_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return inspection_id

def get_inspection(inspection_id, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inspections WHERE id = ?", (inspection_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    
    item = dict(row)
    item["detected_issues"] = json.loads(item["detected_issues"] or "[]")
    item["extracted_data"] = json.loads(item["extracted_data"] or "{}")
    item["image_paths"] = json.loads(item["image_paths"] or "{}")
    return item

def list_inspections(search=None, status=None, limit=50, offset=0, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    query = "SELECT * FROM inspections WHERE 1=1"
    params = []
    
    if search:
        query += " AND (product_name LIKE ? OR manufacturer LIKE ? OR country_of_origin LIKE ? OR id = ?)"
        term = f"%{search}%"
        params.extend([term, term, term, search if str(search).isdigit() else -1])
        
    if status and status != "ALL":
        query += " AND overall_status = ?"
        params.append(status)
        
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    
    count_query = "SELECT COUNT(*) as total FROM inspections WHERE 1=1"
    count_params = []
    if search:
        count_query += " AND (product_name LIKE ? OR manufacturer LIKE ? OR country_of_origin LIKE ? OR id = ?)"
        count_params.extend([term, term, term, search if str(search).isdigit() else -1])
    if status and status != "ALL":
        count_query += " AND overall_status = ?"
        count_params.append(status)
        
    cursor.execute(count_query, tuple(count_params))
    total_count = cursor.fetchone()["total"]
    
    conn.close()
    
    inspections = []
    for r in rows:
        item = dict(r)
        item["detected_issues"] = json.loads(item["detected_issues"] or "[]")
        item["extracted_data"] = json.loads(item["extracted_data"] or "{}")
        item["image_paths"] = json.loads(item["image_paths"] or "{}")
        inspections.append(item)
        
    return inspections, total_count

def get_dashboard_metrics(db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM inspections")
    total = cursor.fetchone()["total"]
    
    cursor.execute("SELECT COUNT(*) as compliant FROM inspections WHERE overall_status = 'COMPLIANT'")
    compliant = cursor.fetchone()["compliant"]
    
    cursor.execute("SELECT COUNT(*) as review FROM inspections WHERE overall_status = 'NEEDS REVIEW'")
    review = cursor.fetchone()["review"]
    
    cursor.execute("SELECT COUNT(*) as non_compliant FROM inspections WHERE overall_status = 'NON-COMPLIANT'")
    non_compliant = cursor.fetchone()["non_compliant"]
    
    cursor.execute("SELECT AVG(compliance_score) as avg_score FROM inspections")
    avg_score_row = cursor.fetchone()
    avg_score = round(avg_score_row["avg_score"] or 0, 1)
    
    cursor.execute("SELECT detected_issues FROM inspections WHERE detected_issues IS NOT NULL")
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
    
    for row in all_issues_rows:
        issues = json.loads(row["detected_issues"] or "[]")
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
                
    cursor.execute("SELECT * FROM inspections ORDER BY id DESC LIMIT 5")
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
        "compliance_rate": round((compliant / total * 100) if total > 0 else 0, 1),
        "average_score": avg_score,
        "violation_counts": violation_counts,
        "recent_inspections": recent
    }

def delete_inspection(inspection_id, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inspections WHERE id = ?", (inspection_id,))
    conn.commit()
    conn.close()
