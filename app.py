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
    list_inspections, get_dashboard_metrics, delete_inspection
)
from utils.ocr import run_ocr_pipeline
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

    return {
        't': translate_helper,
        'current_lang': current_lang,
        'supported_languages': get_supported_languages(),
        'get_translated_status': status_helper,
        'get_translated_badge': badge_helper
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

    # Step 1: Execute OCR
    ocr_res = run_ocr_pipeline(primary_image_path)
    
    # If front is separate, also run OCR on front to capture product name/branding
    if back_path and front_path:
        front_ocr = run_ocr_pipeline(front_path)
        combined_text = (front_ocr.get("full_text", "") + "\n" + ocr_res.get("full_text", "")).strip()
        combined_tokens = front_ocr.get("tokens", []) + ocr_res.get("tokens", [])
        combined_lines = front_ocr.get("lines", []) + ocr_res.get("lines", [])
        ocr_res["full_text"] = combined_text
        ocr_res["tokens"] = combined_tokens
        ocr_res["lines"] = combined_lines

    # Step 2: Extract Statutory Declarations
    extracted_fields = extract_all_fields(ocr_res)

    # Step 3: Legal Metrology Rule Compliance Assessment
    compliance_assessment = assess_compliance(extracted_fields)

    # Step 4: Generate Visual Evidence Annotated Map
    evidence_fname = f"evidence_{timestamp_str}.jpg"
    evidence_path = os.path.join(app.config['UPLOAD_FOLDER'], evidence_fname)
    generate_evidence_image(
        primary_image_path,
        extracted_fields,
        compliance_assessment.get("rule_evaluations", []),
        evidence_path
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
        "officer_notes": officer_notes
    }

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

@app.route('/dashboard')
def dashboard():
    """GovTech Compliance Analytics Dashboard & Audit Trail."""
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'ALL').strip()
    page = int(request.args.get('page', 1))
    per_page = 25
    offset = (page - 1) * per_page

    inspections, total_count = list_inspections(
        search=search_query if search_query else None,
        status=status_filter if status_filter != 'ALL' else None,
        limit=per_page,
        offset=offset
    )

    metrics = get_dashboard_metrics()

    return render_template(
        'dashboard.html',
        inspections=inspections,
        total_count=total_count,
        metrics=metrics,
        search_query=search_query,
        status_filter=status_filter,
        page=page
    )

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
