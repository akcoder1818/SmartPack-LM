"""
SmartPack-LM: Automated Multilingual Verification & Diagnostic Test Suite
Tests:
1. Core module imports
2. Legal Metrology Rules Loading
3. Multilingual Translation Catalogs (EN, HI, TA, KN, TE, ML)
4. Translation helper functions and fallback behavior
5. Sample Label Image Generation
6. Multi-Tier OCR & Extractor execution
7. Rule Engine evaluation for PASS, REVIEW, and NON-COMPLIANT scenarios
8. Visual Evidence Bounding Box Annotation
9. Multilingual PDF Report Generation for all 6 languages
10. Flask endpoints and language switching
"""
import os
import sys

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("==================================================================")
print("  SMARTPACK-LM: MULTILINGUAL VERIFICATION TEST SUITE")
print("==================================================================")

# 1. Imports
print("[Step 1/8] Testing Core Module Imports...")
import utils.database as db
import utils.ocr as ocr
import utils.extractor as extractor
import utils.compliance as compliance
import utils.annotator as annotator
import utils.report as report
import utils.translator as translator
from static.samples.generate_samples import generate_all
print("  [OK] All modules imported successfully.")

# 2. Rules
print("[Step 2/8] Loading Legal Metrology Rules...")
rules = compliance.load_rules()
print(f"  [OK] Loaded {len(rules)} statutory rules from rules/legal_metrology_rules.json")
assert len(rules) >= 8, "Expected at least 8 statutory rules"

# 3. Translation Catalogs Verification
print("[Step 3/8] Testing Multilingual Translation Catalogs...")
expected_langs = ["en", "hi", "ta", "kn", "te", "ml"]
for lang in expected_langs:
    cat = translator.load_translations(lang)
    assert cat.get("lang_code") == lang, f"Language code mismatch for {lang}"
    assert "upload_card_title" in cat, f"Missing upload_card_title in {lang}"
    assert "pdf_report_title" in cat, f"Missing pdf_report_title in {lang}"
    print(f"  [OK] {lang.upper()} catalog verified ({len(cat)} keys) -> '{cat.get('lang_name')}'")

# Test translation function
assert translator.t("analyze_btn", lang="hi") == "उत्पाद अनुपालन का विश्लेषण करें"
assert translator.t("analyze_btn", lang="ta") == "தயாரிப்பு இணக்கத்தை ஆய்வு செய்"
assert translator.t("non_existent_key", lang="hi", default="Fallback") == "Fallback"
print("  [OK] Translation lookups and fallback verified.")

# 4. Sample Generation & Database Init
print("[Step 4/8] Generating Synthetic Test Labels & Database Init...")
generate_all()
db.init_db()
print("  [OK] Test labels and database initialized.")

# 5. Pipeline Test - 3 Compliance Scenarios
print("[Step 5/8] Testing Compliance Scenarios (Zero Regression Check)...")
s1 = os.path.join("static", "samples", "sample_compliant_biscuit.jpg")
o1 = ocr.run_ocr_pipeline(s1)
f1 = extractor.extract_all_fields(o1)
c1 = compliance.assess_compliance(f1)
assert c1.get("overall_status") == "COMPLIANT", f"Expected COMPLIANT for S1, got {c1.get('overall_status')}"
print(f"  Scenario 1 (FMCG Biscuit): Score = {c1.get('compliance_score')}% | Status = {c1.get('overall_status')} [OK]")

s2 = os.path.join("static", "samples", "sample_noncompliant_oil.jpg")
o2 = ocr.run_ocr_pipeline(s2)
f2 = extractor.extract_all_fields(o2)
c2 = compliance.assess_compliance(f2)
assert c2.get("overall_status") == "NON-COMPLIANT", f"Expected NON-COMPLIANT for S2, got {c2.get('overall_status')}"
print(f"  Scenario 2 (Edible Oil):   Score = {c2.get('compliance_score')}% | Status = {c2.get('overall_status')} [OK]")

s3 = os.path.join("static", "samples", "sample_review_detergent.jpg")
o3 = ocr.run_ocr_pipeline(s3)
f3 = extractor.extract_all_fields(o3)
c3 = compliance.assess_compliance(f3)
assert c3.get("overall_status") == "NEEDS REVIEW", f"Expected NEEDS REVIEW for S3, got {c3.get('overall_status')}"
print(f"  Scenario 3 (Detergent):    Score = {c3.get('compliance_score')}% | Status = {c3.get('overall_status')} [OK]")

# 6. Evidence Annotation & Save
ev_path = os.path.join("uploads", "test_evidence_s1.jpg")
annotator.generate_evidence_image(s1, f1, c1.get("rule_evaluations", []), ev_path)

insp_id = db.save_inspection({
    "product_name": f1.get("product_name", {}).get("value"),
    "manufacturer": f1.get("manufacturer", {}).get("value"),
    "country_of_origin": f1.get("country_of_origin", {}).get("value"),
    "net_quantity": f1.get("net_quantity", {}).get("value"),
    "mrp": f1.get("mrp", {}).get("value"),
    "manufacturing_date": f1.get("manufacturing_date", {}).get("value"),
    "consumer_care": f1.get("consumer_care", {}).get("value"),
    "compliance_score": c1.get("compliance_score"),
    "overall_status": c1.get("overall_status"),
    "detected_issues": c1.get("detected_issues"),
    "extracted_data": {"rule_evaluations": c1.get("rule_evaluations")},
    "evidence_image_path": ev_path
})
item = db.get_inspection(insp_id)

# 7. Multilingual PDF Generation (All 6 Languages)
print("[Step 6/8] Testing Multilingual PDF Report Generation...")
for lang in expected_langs:
    pdf_out = os.path.join("uploads", f"Test_Report_{lang.upper()}.pdf")
    report.generate_pdf_report(item, pdf_out, lang=lang)
    assert os.path.exists(pdf_out) and os.path.getsize(pdf_out) > 5000, f"PDF generation failed for {lang}"
    print(f"  [OK] Generated {lang.upper()} PDF Report ({os.path.getsize(pdf_out)} bytes) -> {pdf_out}")

# 8. Flask App & Language Switching Routes
print("[Step 7/8] Testing Flask Routes and Language Switching...")
import app as flask_app
client = flask_app.app.test_client()

r_home = client.get("/")
assert r_home.status_code == 200

# Switch to Hindi
r_switch_hi = client.get("/set-language/hi", follow_redirects=True)
assert r_switch_hi.status_code == 200
assert "भारत सरकार" in r_switch_hi.data.decode("utf-8")
print("  [OK] Language switch to Hindi verified in HTML response.")

# Switch to Tamil
r_switch_ta = client.get("/set-language/ta", follow_redirects=True)
assert r_switch_ta.status_code == 200
assert "இந்திய அரசு" in r_switch_ta.data.decode("utf-8")
print("  [OK] Language switch to Tamil verified in HTML response.")

# Switch to Kannada
r_switch_kn = client.get("/set-language/kn", follow_redirects=True)
assert r_switch_kn.status_code == 200
assert "ಭಾರತ ಸರ್ಕಾರ" in r_switch_kn.data.decode("utf-8")
print("  [OK] Language switch to Kannada verified in HTML response.")

# Switch to Telugu
r_switch_te = client.get("/set-language/te", follow_redirects=True)
assert r_switch_te.status_code == 200
assert "భారత ప్రభుత్వం" in r_switch_te.data.decode("utf-8")
print("  [OK] Language switch to Telugu verified in HTML response.")

# Switch to Malayalam
r_switch_ml = client.get("/set-language/ml", follow_redirects=True)
assert r_switch_ml.status_code == 200
assert "ഭാരത സർക്കാർ" in r_switch_ml.data.decode("utf-8")
print("  [OK] Language switch to Malayalam verified in HTML response.")

# Reset to English
r_switch_en = client.get("/set-language/en", follow_redirects=True)
assert r_switch_en.status_code == 200

# Test Multilingual PDF Endpoint
r_pdf_hi = client.get(f"/report/{insp_id}?lang=hi")
assert r_pdf_hi.status_code == 200
assert r_pdf_hi.headers["Content-Type"] == "application/pdf"
print("  [OK] Multilingual PDF download route (/report/<id>?lang=hi) verified.")

print("[Step 8/8] Testing Dashboard Metrics Aggregation...")
metrics = db.get_dashboard_metrics()
print(f"  [OK] Dashboard Metrics: Total={metrics['total_inspections']} | Compliant={metrics['compliant_count']}")

print("==================================================================")
print("  [SUCCESS] ALL MULTILINGUAL TEST SUITE CHECKS PASSED (100%)")
print("==================================================================")
