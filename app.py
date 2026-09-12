"""
SmartPack-LM: AI-Assisted Legal Metrology Compliance Inspection Platform
SIH 2026 Problem Statement: SIH26034
Ministry of Consumer Affairs, Food & Public Distribution
Features: Multilingual UI & PDF reports (English, Hindi, Tamil, Kannada, Telugu, Malayalam).
"""
import os
import shutil
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import (
    Flask, render_template, request, redirect, url_for,
    send_file, jsonify, flash, abort, send_from_directory, session
)

from utils.database import (
    init_db, save_inspection, get_inspection,
    list_inspections, get_dashboard_metrics, delete_inspection,
    authenticate_user, create_user, list_inspectors, list_users,
    update_user_status, reset_user_password, get_user_by_id,
    create_complaint, get_complaint, list_complaints, update_complaint_status
)
from utils.auth import get_current_user, login_required, admin_required
from utils.ocr import run_ocr_pipeline, attach_field_sources
from utils.extractor import extract_all_fields
from utils.compliance import assess_compliance, load_rules
from utils.annotator import generate_evidence_image
from utils.report import generate_pdf_report
from utils.translator import (
    t, SUPPORTED_LANGUAGES, get_supported_languages,
    get_translated_status, get_translated_badge
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
SAMPLES_FOLDER = os.path.join(BASE_DIR, "static", "samples")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SAMPLES_FOLDER, exist_ok=True)

# Initialize database
init_db()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'smartpack-lm-sih2026-secret-key-govtech'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max

# Custom Jinja Filter
@app.template_filter('basename')
def filter_basename(path):
    if not path:
        return ""
    return os.path.basename(path)

# Context Processor for Multilingual Support
@app.context_processor
def inject_localization():
    """Injects translation helper, current language, and language list into all templates."""
    # Check if lang query param is provided
    lang_param = request.args.get('lang')
    if lang_param and lang_param in SUPPORTED_LANGUAGES:
        session['lang'] = lang_param
        
    current_lang = session.get('lang', 'en')
    if current_lang not in SUPPORTED_LANGUAGES:
        current_lang = 'en'
        session['lang'] = 'en'

    def translate_helper(key, **kwargs):
        return t(key, lang=current_lang, **kwargs)

    def status_helper(status_str):
        return get_translated_status(status_str, lang=current_lang)

    def badge_helper(badge_str):
        return get_translated_badge(badge_str, lang=current_lang)

    user = get_current_user()

    return {
        't': translate_helper,
        'current_lang': current_lang,
        'supported_languages': get_supported_languages(),
        'get_translated_status': status_helper,
        'get_translated_badge': badge_helper,
        'current_user': user
    }

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/set-language/<lang_code>')
def set_language(lang_code):
    """Switches active language and redirects back."""
    if lang_code in SUPPORTED_LANGUAGES:
        session['lang'] = lang_code
    
    # Redirect back to referrer or home
    referrer = request.referrer
    if referrer:
        return redirect(referrer)
    return redirect(url_for('index'))

@app.route('/')
def index():
    """Home landing page with Dual Label Upload and Preset Samples."""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Main Analysis Endpoint:
    1. Preprocess & Save Uploaded Images (Front & Back)
    2. Execute Multi-Tier OCR Pipeline
    3. Extract Statutory Declarations
    4. Validate against Legal Metrology Rules Engine
    5. Generate Visual Evidence Image with Bounding Boxes
    6. Persist Audit Record in SQLite
    7. Redirect to Result Page
    """
    if 'front_image' not in request.files:
        flash('Front label image is required.', 'danger')
        return redirect(url_for('index'))

    front_file = request.files['front_image']
    back_file = request.files.get('back_image')
    officer_notes = request.form.get('officer_notes', '')

    if front_file.filename == '':
        flash('Please select an image file to analyze.', 'warning')
        return redirect(url_for('index'))

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save front image
    front_path = None
    if front_file and allowed_file(front_file.filename):
        front_fname = f"front_{timestamp_str}_{secure_filename(front_file.filename)}"
        front_path = os.path.join(app.config['UPLOAD_FOLDER'], front_fname)
        front_file.save(front_path)

    # Save back image (if provided)
    back_path = None
    if back_file and back_file.filename != '' and allowed_file(back_file.filename):
        back_fname = f"back_{timestamp_str}_{secure_filename(back_file.filename)}"
        back_path = os.path.join(app.config['UPLOAD_FOLDER'], back_fname)
        back_file.save(back_path)

    primary_image_path = back_path if back_path else front_path
    secondary_image_path = front_path if (back_path and front_path) else None

    # Step 1: Execute OCR (Front & Back processed independently with preserved source identity)
    if back_path and front_path:
        front_ocr = run_ocr_pipeline(front_path, source="front")
        back_ocr = run_ocr_pipeline(back_path, source="back")
        combined_text = (front_ocr.get("full_text", "") + "\n" + back_ocr.get("full_text", "")).strip()
        combined_tokens = front_ocr.get("tokens", []) + back_ocr.get("tokens", [])
        combined_lines = front_ocr.get("lines", []) + back_ocr.get("lines", [])
        ocr_res = {
            "engine": back_ocr.get("engine") or front_ocr.get("engine", "SmartPack-LM OCR Engine"),
            "full_text": combined_text,
            "tokens": combined_tokens,
            "lines": combined_lines,
            "success": front_ocr.get("success", False) or back_ocr.get("success", False)
        }
    else:
        single_source = "front" if front_path else ("back" if back_path else None)
        ocr_res = run_ocr_pipeline(primary_image_path, source=single_source)

    # Step 2: Extract Statutory Declarations & preserve token source identity
    extracted_fields = extract_all_fields(ocr_res)
    attach_field_sources(extracted_fields, ocr_res.get("tokens", []))

    # Step 3: Legal Metrology Rule Compliance Assessment
    compliance_assessment = assess_compliance(extracted_fields)

    # Server-Side Pipeline Trace Logging
    print("\n[SmartPack-LM Pipeline] =================================================")
    print(f"[SmartPack-LM Pipeline] 1. OCR RAW TEXT ({len(ocr_res.get('lines', []))} lines, Engine: {ocr_res.get('engine')}):")
    for l in ocr_res.get("lines", [])[:10]:
        print(f"  | {l}")
    if len(ocr_res.get("lines", [])) > 10:
        print(f"  | ... ({len(ocr_res.get('lines', [])) - 10} more lines)")
    print("[SmartPack-LM Pipeline] 2. EXTRACTED & NORMALIZED FIELDS:")
    for fn, fv in extracted_fields.items():
        if isinstance(fv, dict):
            print(f"  - {fn}: val={fv.get('value')!r} | conf={fv.get('confidence')} | status={fv.get('status')}")
    print(f"[SmartPack-LM Pipeline] 3. LEGAL METROLOGY RULE EVALUATION:")
    print(f"  Overall Status: {compliance_assessment.get('overall_status')} | Score: {compliance_assessment.get('compliance_score')}%")
    for re_item in compliance_assessment.get("rule_evaluations", []):
        print(f"  [{re_item.get('status')}] {re_item.get('field')} ({re_item.get('severity')}): {re_item.get('findings')}")
    print("[SmartPack-LM Pipeline] =================================================\n")

    # Step 4: Generate Visual Evidence Annotated Map
    evidence_fname = f"evidence_{timestamp_str}.jpg"
    evidence_path = os.path.join(app.config['UPLOAD_FOLDER'], evidence_fname)
    generate_evidence_image(
        primary_image_path,
        extracted_fields,
        compliance_assessment.get("rule_evaluations", []),
        evidence_path,
        secondary_image_path=secondary_image_path
    )

    # Step 5: Save Inspection Record
    inspection_payload = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "product_name": extracted_fields.get("product_name", {}).get("value") or "Packaged Commodity",
        "manufacturer": extracted_fields.get("manufacturer", {}).get("value") or "Not Specified",
        "country_of_origin": extracted_fields.get("country_of_origin", {}).get("value") or "Not Detected",
        "net_quantity": extracted_fields.get("net_quantity", {}).get("value") or "Not Detected",
        "mrp": extracted_fields.get("mrp", {}).get("value") or "Not Detected",
        "manufacturing_date": extracted_fields.get("manufacturing_date", {}).get("value") or "Not Detected",
        "best_before": extracted_fields.get("best_before", {}).get("value") or "N/A",
        "consumer_care": extracted_fields.get("consumer_care", {}).get("value") or "Not Detected",
        "unit_sale_price": extracted_fields.get("unit_sale_price", {}).get("value") or "N/A",
        "dimensions": extracted_fields.get("dimensions", {}).get("value") or "N/A",
        "compliance_score": compliance_assessment.get("compliance_score", 0.0),
        "overall_status": compliance_assessment.get("overall_status", "REVIEW"),
        "detected_issues": compliance_assessment.get("detected_issues", []),
        "extracted_data": {
            "fields": extracted_fields,
            "rule_evaluations": compliance_assessment.get("rule_evaluations", []),
            "ocr_raw_text": ocr_res.get("full_text", ""),
            "ocr_engine": ocr_res.get("engine", "PaddleOCR / Hybrid")
        },
        "image_paths": {
            "front": front_path,
            "back": back_path
        },
        "evidence_image_path": evidence_path,
        "officer_notes": officer_notes,
        "location_data": None
    }

    # Determine user identity and role from session
    curr_user = get_current_user()
    if curr_user:
        user_role = curr_user.get('role', 'PUBLIC')
        user_display = curr_user.get('name') or curr_user.get('username') or 'Authenticated User'
        inspection_payload["role"] = user_role
        inspection_payload["performed_by"] = user_display
        if user_role == 'INSPECTOR':
            inspection_payload["inspector_id"] = curr_user['id']
            inspection_payload["user_id"] = None
        elif user_role == 'ADMIN':
            inspection_payload["inspector_id"] = curr_user['id']
            inspection_payload["user_id"] = None
        elif user_role == 'USER':
            inspection_payload["inspector_id"] = None
            inspection_payload["user_id"] = curr_user['id']
        else:
            inspection_payload["inspector_id"] = None
            inspection_payload["user_id"] = curr_user['id']
    else:
        inspection_payload["role"] = "PUBLIC"
        inspection_payload["performed_by"] = "Public / Unauthenticated Citizen"
        inspection_payload["inspector_id"] = None
        inspection_payload["user_id"] = None

    # Safely parse inspection location data if provided
    raw_location = request.form.get('location_data')
    if raw_location:
        try:
            import json as pyjson
            parsed_loc = pyjson.loads(raw_location)
            if isinstance(parsed_loc, dict) and parsed_loc.get('latitude') is not None:
                inspection_payload["location_data"] = parsed_loc
        except Exception as e:
            print(f"[SmartPack-LM] Note: could not parse location payload: {e}")

    inspection_id = save_inspection(inspection_payload)
    return redirect(url_for('view_result', inspection_id=inspection_id))

@app.route('/result/<int:inspection_id>')
def view_result(inspection_id):
    """Inspection Result Detail View."""
    inspection = get_inspection(inspection_id)
    if not inspection:
        flash(f"Inspection record #{inspection_id} not found.", "warning")
        return redirect(url_for('dashboard'))

    return render_template('result.html', inspection=inspection)

@app.route('/report/<int:inspection_id>')
def download_report(inspection_id):
    """Generates and streams official multilingual PDF inspection report."""
    inspection = get_inspection(inspection_id)
    if not inspection:
        abort(404)

    # Determine requested language
    target_lang = request.args.get('lang') or session.get('lang', 'en')
    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = 'en'

    pdf_buffer = generate_pdf_report(inspection, lang=target_lang)
    filename = f"SmartPack_LM_Report_SP-LM-{inspection_id:04d}_{target_lang.upper()}.pdf"
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# ==============================================================================
# AUTHENTICATION ROUTES (PART 1 & PART 2)
# ==============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin and Inspector Authentication Portal."""
    if session.get('user_id') and get_current_user():
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("Please enter both username/email and password.", "warning")
            return render_template('login.html')

        user = authenticate_user(username, password)
        if not user:
            flash("Invalid credentials or account is deactivated. Contact Administrator.", "danger")
            return render_template('login.html')

        # Store user details in session
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        session['name'] = user['name']

        flash(f"Welcome back, {user['name']} ({user['role']}). Secure session active.", "success")
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Clears authenticated session and redirects to login."""
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('role', None)
    session.pop('name', None)
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Citizen / Consumer Registration Portal."""
    if session.get('user_id') and get_current_user():
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        form_data = {'name': name, 'username': username, 'email': email, 'phone': phone}

        if not (name and username and email and password):
            flash("Please fill in all mandatory fields.", "warning")
            return render_template('register.html', form_data=form_data)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "warning")
            return render_template('register.html', form_data=form_data)

        if password != confirm_password:
            flash("Passwords do not match. Please verify and re-enter.", "warning")
            return render_template('register.html', form_data=form_data)

        # Create user with role='USER'
        result = create_user(
            name=name,
            username=username,
            email=email,
            phone=phone,
            password=password,
            role='USER',
            department='Consumer / Citizen'
        )

        if result.get('success'):
            flash("Your citizen account has been successfully created! Please sign in.", "success")
            return redirect(url_for('login'))
        else:
            flash(f"Registration failed: {result.get('error', 'Username or email already exists.')}", "danger")
            return render_template('register.html', form_data=form_data)

    return render_template('register.html', form_data={})

# ==============================================================================
# DASHBOARD & INSPECTION HISTORY (PARTS 3, 4, 5, 6)
# ==============================================================================

@app.route('/dashboard')
def dashboard():
    """GovTech Compliance Analytics Dashboard & Audit Trail."""
    current_user = get_current_user()
    inspector_id = None
    user_id = None
    role_filter = None

    if current_user:
        if current_user['role'] == 'INSPECTOR':
            inspector_id = current_user['id']
        elif current_user['role'] == 'USER':
            user_id = current_user['id']
        elif current_user['role'] == 'ADMIN':
            pass
    else:
        role_filter = 'PUBLIC'

    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'ALL').strip()
    page = int(request.args.get('page', 1))
    per_page = 15
    offset = (page - 1) * per_page

    inspections, total_count = list_inspections(
        search=search_query if search_query else None,
        status=status_filter if status_filter != 'ALL' else None,
        inspector_id=inspector_id,
        user_id=user_id,
        role=role_filter,
        limit=per_page,
        offset=offset
    )

    metrics = get_dashboard_metrics(inspector_id=inspector_id, user_id=user_id, role=role_filter)

    return render_template(
        'dashboard.html',
        inspections=inspections,
        total_count=total_count,
        metrics=metrics,
        search_query=search_query,
        status_filter=status_filter,
        page=page
    )

@app.route('/inspections')
@app.route('/history')
def inspection_history():
    """Dedicated Searchable & Filterable Inspection Audit Log."""
    current_user = get_current_user()
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'ALL').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page

    # Role-based inspection access control:
    # ADMIN -> views all inspections (can optionally filter by specific inspector)
    # INSPECTOR -> views only their own inspections (inspector_id)
    # USER -> views only their own inspections (user_id)
    # Unauthenticated / Public -> sees only public/demo inspections
    inspectors_list = []
    inspector_filter = None
    user_filter = None
    role_filter = None

    if current_user:
        if current_user['role'] == 'ADMIN':
            inspectors_list = list_inspectors()
            raw_inspector_param = request.args.get('inspector_id', '').strip()
            inspector_filter = int(raw_inspector_param) if raw_inspector_param.isdigit() else None
        elif current_user['role'] == 'INSPECTOR':
            inspector_filter = current_user['id']
        elif current_user['role'] == 'USER':
            user_filter = current_user['id']
    else:
        role_filter = 'PUBLIC'

    inspections, total_count = list_inspections(
        search=search_query if search_query else None,
        status=status_filter if status_filter != 'ALL' else None,
        inspector_id=inspector_filter,
        user_id=user_filter,
        role=role_filter,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None,
        limit=per_page,
        offset=offset
    )

    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

    return render_template(
        'inspections.html',
        inspections=inspections,
        total_count=total_count,
        search_query=search_query,
        status_filter=status_filter,
        inspector_filter=request.args.get('inspector_id', ''),
        date_from=date_from,
        date_to=date_to,
        inspectors_list=inspectors_list,
        page=page,
        total_pages=total_pages
    )

# ==============================================================================
# ADMIN INSPECTOR MANAGEMENT ROUTES (PART 7)
# ==============================================================================

@app.route('/admin/inspectors')
@app.route('/inspectors')
@admin_required
def manage_inspectors():
    """Admin Inspector Roster and Performance Management Console."""
    status_filter = request.args.get('status', 'ALL').strip()
    search_query = request.args.get('search', '').strip()

    status_arg = status_filter if status_filter in ['ACTIVE', 'INACTIVE'] else None
    inspectors = list_inspectors(status=status_arg, search=search_query if search_query else None)

    return render_template(
        'inspectors.html',
        inspectors=inspectors,
        status_filter=status_filter,
        search_query=search_query
    )

@app.route('/admin/inspectors/create', methods=['POST'])
@admin_required
def create_inspector_route():
    """Provisions a new Inspector account with secure hashed password."""
    name = request.form.get('name', '').strip()
    inspector_id = request.form.get('inspector_id', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    department = request.form.get('department', '').strip()

    if not (name and inspector_id and username and password):
        flash("Please provide all required fields (Name, Inspector Badge ID, Username, Password).", "warning")
        return redirect(url_for('manage_inspectors'))

    res = create_user(
        inspector_id=inspector_id,
        name=name,
        username=username,
        password=password,
        email=email,
        role='INSPECTOR',
        phone=phone,
        department=department
    )

    if res.get('success'):
        flash(f"Inspector account '{name}' ({inspector_id}) created successfully.", "success")
    else:
        flash(f"Failed to create inspector: {res.get('error')}", "danger")

    return redirect(url_for('manage_inspectors'))

@app.route('/admin/inspectors/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_inspector_status(user_id):
    """Activates or deactivates an inspector account."""
    new_status = request.form.get('status', 'INACTIVE').strip()
    if new_status not in ['ACTIVE', 'INACTIVE']:
        new_status = 'INACTIVE'

    success = update_user_status(user_id, new_status)
    if success:
        flash(f"Inspector status updated to {new_status}.", "success")
    else:
        flash("Failed to update inspector status.", "danger")

    return redirect(url_for('manage_inspectors'))

@app.route('/admin/inspectors/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_inspector_password_route(user_id):
    """Resets an inspector's password."""
    new_pwd = request.form.get('new_password', '').strip()
    if not new_pwd or len(new_pwd) < 6:
        flash("Password must be at least 6 characters long.", "warning")
        return redirect(url_for('manage_inspectors'))

    success = reset_user_password(user_id, new_pwd)
    if success:
        flash("Inspector password updated successfully.", "success")
    else:
        flash("Failed to reset inspector password.", "danger")

    return redirect(url_for('manage_inspectors'))

@app.route('/admin/users')
@admin_required
def admin_users():
    """Admin Registered Users Management Directory."""
    search_query = request.args.get('search', '').strip()
    role_filter = request.args.get('role', 'ALL').strip()
    status_filter = request.args.get('status', 'ALL').strip()

    users = list_users(
        search=search_query if search_query else None,
        role=role_filter if role_filter != 'ALL' else None,
        status=status_filter if status_filter != 'ALL' else None
    )

    all_users = list_users()
    counts = {
        'total': len(all_users),
        'user': sum(1 for u in all_users if u.get('role') == 'USER'),
        'inspector': sum(1 for u in all_users if u.get('role') == 'INSPECTOR'),
        'admin': sum(1 for u in all_users if u.get('role') == 'ADMIN')
    }

    return render_template(
        'admin_users.html',
        users=users,
        search_query=search_query,
        role_filter=role_filter,
        status_filter=status_filter,
        counts=counts
    )

# ==============================================================================
# CITIZEN GRIEVANCE REDRESSAL & COMPLAINTS MANAGEMENT
# ==============================================================================

@app.route('/complaint/new', methods=['GET', 'POST'])
@login_required
def new_complaint():
    """Citizen Grievance Submission Route."""
    current_user = get_current_user()

    if request.method == 'GET':
        inspection_id_raw = request.args.get('inspection_id')
        if not inspection_id_raw or not str(inspection_id_raw).isdigit():
            flash("A valid inspection ID is required to register a grievance.", "warning")
            return redirect(url_for('index'))

        inspection = get_inspection(int(inspection_id_raw))
        if not inspection:
            flash("Inspection record not found.", "warning")
            return redirect(url_for('index'))

        return render_template('complaint_form.html', inspection=inspection, current_user=current_user)

    # Handle POST
    inspection_id = request.form.get('inspection_id')
    if not inspection_id or not str(inspection_id).isdigit():
        flash("Invalid inspection reference.", "danger")
        return redirect(url_for('index'))

    inspection = get_inspection(int(inspection_id))
    if not inspection:
        flash("Associated inspection not found.", "danger")
        return redirect(url_for('index'))

    retailer_details = request.form.get('retailer_details', '').strip()
    description = request.form.get('description', '').strip()
    contact_number = request.form.get('contact_number', '').strip() or current_user.get('phone', '')

    if not retailer_details or not description:
        flash("Please provide retailer/shop details and a description of the issue.", "warning")
        return render_template('complaint_form.html', inspection=inspection, current_user=current_user)

    loc = inspection.get('location_data') or {}
    complaint_data = {
        "user_id": current_user['id'],
        "user_name": current_user['name'],
        "user_email": current_user.get('email', ''),
        "contact_number": contact_number,
        "inspection_id": inspection['id'],
        "product_name": inspection.get('product_name', 'Packaged Commodity'),
        "compliance_result": inspection.get('overall_status', 'NON-COMPLIANT'),
        "violations": inspection.get('detected_issues', []),
        "location_address": loc.get('address', '') if isinstance(loc, dict) else '',
        "latitude": loc.get('latitude') if isinstance(loc, dict) else None,
        "longitude": loc.get('longitude') if isinstance(loc, dict) else None,
        "inspection_timestamp": inspection.get('timestamp', ''),
        "evidence_image_path": inspection.get('evidence_image_path', ''),
        "retailer_details": retailer_details,
        "description": description,
        "status": "Submitted"
    }

    res = create_complaint(complaint_data)
    flash(f"Grievance {res['complaint_no']} successfully filed under Legal Metrology Act, 2009!", "success")
    return redirect(url_for('view_complaint_detail', complaint_id=res['id']))

@app.route('/complaint/<int:complaint_id>')
@login_required
def view_complaint_detail(complaint_id):
    """View and track a specific complaint."""
    current_user = get_current_user()
    complaint = get_complaint(complaint_id)
    if not complaint:
        flash("Grievance record not found.", "warning")
        return redirect(url_for('list_user_complaints') if current_user['role'] == 'USER' else url_for('admin_complaints'))

    # Access control: Citizens can ONLY view their own complaint. Admin can view all.
    if current_user['role'] != 'ADMIN' and complaint['user_id'] != current_user['id']:
        flash("Access denied: You are not authorized to view this grievance record.", "danger")
        return redirect(url_for('list_user_complaints'))

    return render_template('complaint_view.html', complaint=complaint, current_user=current_user)

@app.route('/complaints')
@login_required
def list_user_complaints():
    """Citizen Complaint History view."""
    current_user = get_current_user()
    if current_user['role'] == 'ADMIN':
        return redirect(url_for('admin_complaints'))

    complaints, total_count = list_complaints(user_id=current_user['id'])
    return render_template('user_complaints.html', complaints=complaints, total_count=total_count, current_user=current_user)

@app.route('/admin/complaints')
@admin_required
def admin_complaints():
    """Admin Complaint Redressal Management Console."""
    status_filter = request.args.get('status', 'ALL').strip()
    search_query = request.args.get('search', '').strip()

    status_arg = status_filter if status_filter in ['Submitted', 'Under Review', 'Resolved', 'Rejected'] else None
    complaints, total_count = list_complaints(
        status=status_arg,
        search=search_query if search_query else None
    )

    return render_template(
        'admin_complaints.html',
        complaints=complaints,
        total_count=total_count,
        status_filter=status_filter,
        search_query=search_query
    )

@app.route('/admin/complaints/<int:complaint_id>/status', methods=['POST'])
@admin_required
def admin_update_complaint_status(complaint_id):
    """Admin endpoint to update grievance status and enforcement notes."""
    new_status = request.form.get('status', 'Submitted').strip()
    admin_notes = request.form.get('admin_notes', '').strip()

    if new_status not in ['Submitted', 'Under Review', 'Resolved', 'Rejected']:
        flash("Invalid status choice.", "warning")
        return redirect(url_for('admin_complaints'))

    updated = update_complaint_status(complaint_id, new_status, admin_notes=admin_notes)
    if updated:
        flash(f"Grievance #{complaint_id} status updated to '{new_status}'.", "success")
    else:
        flash("Failed to update grievance status.", "danger")

    return redirect(url_for('admin_complaints'))

@app.route('/rules')
def view_rules():
    """Interactive Legal Metrology Rules Catalog."""
    rules = load_rules()
    return render_template('rules.html', rules=rules)

@app.route('/sample/<sample_key>')
def load_sample(sample_key):
    """
    1-Click Demo Presets for Hackathon Evaluation:
    - 'compliant': 100% Compliant FMCG Biscuit Pack
    - 'noncompliant': Edible Oil (Missing Country of origin, Consumer care, Non-standard Net qty)
    - 'review': Detergent (Partial Date, Missing 'incl of taxes')
    """
    sample_files = {
        "compliant": "sample_compliant_biscuit.jpg",
        "noncompliant": "sample_noncompliant_oil.jpg",
        "review": "sample_review_detergent.jpg"
    }

    sample_filename = sample_files.get(sample_key, "sample_compliant_biscuit.jpg")
    src_path = os.path.join(SAMPLES_FOLDER, sample_filename)

    # Ensure samples exist
    if not os.path.exists(src_path):
        from static.samples.generate_samples import generate_all
        generate_all()

    # Copy to uploads
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_fname = f"sample_{sample_key}_{timestamp_str}.jpg"
    dest_path = os.path.join(app.config['UPLOAD_FOLDER'], dest_fname)
    shutil.copyfile(src_path, dest_path)

    # Run full pipeline
    ocr_res = run_ocr_pipeline(dest_path)
    extracted_fields = extract_all_fields(ocr_res)
    attach_field_sources(extracted_fields, ocr_res.get("tokens", []))
    compliance_assessment = assess_compliance(extracted_fields)

    evidence_fname = f"evidence_sample_{sample_key}_{timestamp_str}.jpg"
    evidence_path = os.path.join(app.config['UPLOAD_FOLDER'], evidence_fname)
    generate_evidence_image(
        dest_path,
        extracted_fields,
        compliance_assessment.get("rule_evaluations", []),
        evidence_path
    )

    inspection_payload = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "product_name": extracted_fields.get("product_name", {}).get("value") or "Sample Commodity",
        "manufacturer": extracted_fields.get("manufacturer", {}).get("value") or "Sample Manufacturer",
        "country_of_origin": extracted_fields.get("country_of_origin", {}).get("value") or "Not Detected",
        "net_quantity": extracted_fields.get("net_quantity", {}).get("value") or "Not Detected",
        "mrp": extracted_fields.get("mrp", {}).get("value") or "Not Detected",
        "manufacturing_date": extracted_fields.get("manufacturing_date", {}).get("value") or "Not Detected",
        "best_before": extracted_fields.get("best_before", {}).get("value") or "N/A",
        "consumer_care": extracted_fields.get("consumer_care", {}).get("value") or "Not Detected",
        "unit_sale_price": extracted_fields.get("unit_sale_price", {}).get("value") or "N/A",
        "dimensions": extracted_fields.get("dimensions", {}).get("value") or "N/A",
        "compliance_score": compliance_assessment.get("compliance_score", 0.0),
        "overall_status": compliance_assessment.get("overall_status", "REVIEW"),
        "detected_issues": compliance_assessment.get("detected_issues", []),
        "extracted_data": {
            "fields": extracted_fields,
            "rule_evaluations": compliance_assessment.get("rule_evaluations", []),
            "ocr_raw_text": ocr_res.get("full_text", ""),
            "ocr_engine": ocr_res.get("engine", "SmartPack-LM Fallback OCR")
        },
        "image_paths": {
            "front": dest_path,
            "back": None
        },
        "evidence_image_path": evidence_path,
        "officer_notes": f"Demo preset scan: {sample_key.upper()} scenario"
    }

    # Demo preset scans remain PUBLIC per Legal Metrology specification
    inspection_payload["role"] = "PUBLIC"
    inspection_payload["performed_by"] = "Public / Demo Preset"
    inspection_payload["inspector_id"] = None
    inspection_payload["user_id"] = None

    inspection_id = save_inspection(inspection_payload)
    return redirect(url_for('view_result', inspection_id=inspection_id))

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Securely serves uploaded and evidence images."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/delete/<int:inspection_id>', methods=['POST'])
def api_delete_inspection(inspection_id):
    """Deletes an inspection record from the database."""
    delete_inspection(inspection_id)
    return jsonify({"success": True, "deleted_id": inspection_id})

@app.errorhandler(413)
def request_entity_too_large(error):
    flash("Uploaded image is too large. Maximum allowed size is 16MB.", "danger")
    return redirect(url_for('index')), 413

@app.errorhandler(404)
def not_found(error):
    return render_template('base.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('base.html'), 500

if __name__ == '__main__':
    # Ensure sample labels exist
    from static.samples.generate_samples import generate_all
    generate_all()
    
    print("==================================================================")
    print("  SmartPack-LM: Legal Metrology Compliance Inspection Platform")
    print("  Ministry of Consumer Affairs | SIH 2026 (#SIH26034)")
    print("  Multilingual Support: EN, HI, TA, KN, TE, ML")
    print("  Server running on http://127.0.0.1:5000")
    print("==================================================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
