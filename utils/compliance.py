"""
SmartPack-LM: Legal Metrology Rule Compliance Assessor
Evaluates extracted label declarations against rules defined in rules/legal_metrology_rules.json.
Generates explainable compliance scores, violation warnings, and corrective recommendations.
"""
import os
import json

RULES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules", "legal_metrology_rules.json")

def load_rules(rules_path=None):
    """Dynamically loads the Legal Metrology rules JSON."""
    if rules_path is None:
        rules_path = RULES_FILE
    if not os.path.exists(rules_path):
        return []
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("rules", [])
    except Exception as e:
        print(f"Error loading rules from {rules_path}: {e}")
        return []

def assess_compliance(extracted_fields, custom_rules=None):
    """
    Evaluates extracted fields against Legal Metrology Rules.
    Returns:
    - overall_status: "COMPLIANT" | "NEEDS REVIEW" | "NON-COMPLIANT"
    - compliance_score: 0.0 - 100.0
    - rule_evaluations: List of evaluated rules with individual status and guidance
    - detected_issues: List of flagged non-compliance items
    - summary: Human readable executive summary
    """
    rules = custom_rules if custom_rules is not None else load_rules()
    
    rule_evaluations = []
    detected_issues = []
    
    total_weight = 0.0
    earned_weight = 0.0

    severity_weights = {
        "CRITICAL": 25.0,
        "HIGH": 18.0,
        "MEDIUM": 10.0,
        "LOW": 5.0
    }

    for rule in rules:
        rule_id = rule.get("id")
        field_name = rule.get("field")
        severity = rule.get("severity", "MEDIUM")
        is_required = rule.get("required", False)
        rule_ref = rule.get("rule_reference", "Legal Metrology Rules, 2011")
        title = rule.get("title", field_name)
        weight = severity_weights.get(severity, 10.0)

        # Get field extraction info
        field_info = extracted_fields.get(field_name, {})
        extracted_value = field_info.get("value")
        raw_text = field_info.get("raw_text")
        field_confidence = field_info.get("confidence", 0.0)
        field_status = field_info.get("status", "NOT_DETECTED")

        eval_item = {
            "rule_id": rule_id,
            "field": field_name,
            "title": title,
            "severity": severity,
            "rule_reference": rule_ref,
            "required": is_required,
            "extracted_value": extracted_value,
            "raw_text": raw_text,
            "confidence": field_confidence,
            "status": "NOT_DETECTED",
            "findings": "",
            "corrective_action": ""
        }

        # Assessment Logic
        if not extracted_value:
            if is_required:
                eval_item["status"] = "FAIL"
                eval_item["findings"] = f"Mandatory statutory declaration for '{title}' was NOT detected on the package label."
                eval_item["corrective_action"] = f"Ensure '{title}' is conspicuously printed on the package as required under {rule_ref}."
                detected_issues.append({
                    "rule_id": rule_id,
                    "field": field_name,
                    "title": title,
                    "severity": severity,
                    "issue_type": "MISSING_MANDATORY_DECLARATION",
                    "description": eval_item["findings"],
                    "rule_reference": rule_ref
                })
            else:
                eval_item["status"] = "N/A"
                eval_item["findings"] = f"Optional / Conditional declaration for '{title}' not detected."
        else:
            # Field is present, test qualitative criteria
            if field_name == "mrp":
                has_taxes = field_info.get("has_taxes_declaration", False)
                has_curr = bool(field_info.get("currency"))
                if has_taxes and has_curr:
                    eval_item["status"] = "PASS"
                    eval_item["findings"] = "Maximum Retail Price declared with currency symbol and explicit tax inclusion clause."
                    earned_weight += weight
                elif not has_taxes:
                    eval_item["status"] = "REVIEW"
                    eval_item["findings"] = "MRP detected, but statutory phrase '(inclusive of all taxes)' or 'incl. of all taxes' is absent or unclear."
                    eval_item["corrective_action"] = "Include '(inclusive of all taxes)' explicitly next to the retail sale price."
                    earned_weight += (weight * 0.5)
                    detected_issues.append({
                        "rule_id": rule_id,
                        "field": field_name,
                        "title": title,
                        "severity": "HIGH",
                        "issue_type": "MISSING_TAX_INCLUSION_NOTE",
                        "description": eval_item["findings"],
                        "rule_reference": rule_ref
                    })
                else:
                    eval_item["status"] = "PASS"
                    eval_item["findings"] = "MRP format detected."
                    earned_weight += (weight * 0.85)

            elif field_name == "net_quantity":
                is_std = field_info.get("is_standard_unit", False)
                if is_std:
                    eval_item["status"] = "PASS"
                    eval_item["findings"] = f"Net quantity ({extracted_value}) declared using approved SI metric units."
                    earned_weight += weight
                else:
                    eval_item["status"] = "FAIL"
                    eval_item["findings"] = f"Non-standard unit detected ('{field_info.get('unit')}'). Legal Metrology Rule 11 mandates standard SI units (g, kg, ml, l, m, cm or N)."
                    eval_item["corrective_action"] = "Replace non-standard units (e.g. dozen, lbs) with standard metric units (g, kg, ml, l, N)."
                    detected_issues.append({
                        "rule_id": rule_id,
                        "field": field_name,
                        "title": title,
                        "severity": "CRITICAL",
                        "issue_type": "NON_STANDARD_UNIT",
                        "description": eval_item["findings"],
                        "rule_reference": rule_ref
                    })

            elif field_name == "manufacturing_date":
                if field_status == "REVIEW":
                    eval_item["status"] = "REVIEW"
                    eval_item["findings"] = "Packaging/Manufacturing date detected with year only. Month and year are both compulsory under Rule 6(1)(d)."
                    eval_item["corrective_action"] = "Format manufacturing date as MM/YYYY or Month/Year."
                    earned_weight += (weight * 0.5)
                    detected_issues.append({
                        "rule_id": rule_id,
                        "field": field_name,
                        "title": title,
                        "severity": "MEDIUM",
                        "issue_type": "INCOMPLETE_DATE_FORMAT",
                        "description": eval_item["findings"],
                        "rule_reference": rule_ref
                    })
                else:
                    eval_item["status"] = "PASS"
                    eval_item["findings"] = f"Month and Year of manufacture/packaging correctly declared ({extracted_value})."
                    earned_weight += weight

            elif field_name == "consumer_care":
                multi_ch = field_info.get("has_multi_channel", False)
                if multi_ch:
                    eval_item["status"] = "PASS"
                    eval_item["findings"] = f"Comprehensive Consumer Care details declared with multiple contact channels ({extracted_value})."
                    earned_weight += weight
                elif field_info.get("phone") or field_info.get("email"):
                    eval_item["status"] = "PASS"
                    eval_item["findings"] = f"Consumer Care contact channel detected ({extracted_value})."
                    earned_weight += (weight * 0.9)
                else:
                    eval_item["status"] = "REVIEW"
                    eval_item["findings"] = "Consumer Care cell declared without explicit toll-free phone number or email."
                    eval_item["corrective_action"] = "Provide valid telephone number and email address for consumer grievance redressal."
                    earned_weight += (weight * 0.5)
                    detected_issues.append({
                        "rule_id": rule_id,
                        "field": field_name,
                        "title": title,
                        "severity": "HIGH",
                        "issue_type": "INCOMPLETE_CONSUMER_CARE",
                        "description": eval_item["findings"],
                        "rule_reference": rule_ref
                    })

            elif field_name == "manufacturer":
                has_pin = field_info.get("has_pincode", False)
                if has_pin:
                    eval_item["status"] = "PASS"
                    eval_item["findings"] = "Manufacturer / Packer name & complete postal address with PIN code verified."
                    earned_weight += weight
                else:
                    eval_item["status"] = "REVIEW"
                    eval_item["findings"] = "Manufacturer details detected, but 6-digit postal PIN code was not found in the address."
                    eval_item["corrective_action"] = "Ensure complete postal address including state and 6-digit postal PIN code is printed."
                    earned_weight += (weight * 0.7)
                    detected_issues.append({
                        "rule_id": rule_id,
                        "field": field_name,
                        "title": title,
                        "severity": "MEDIUM",
                        "issue_type": "INCOMPLETE_POSTAL_ADDRESS",
                        "description": eval_item["findings"],
                        "rule_reference": rule_ref
                    })

            elif field_name == "country_of_origin":
                eval_item["status"] = "PASS"
                eval_item["findings"] = f"Country of origin verified ({extracted_value})."
                earned_weight += weight

            elif field_name == "product_name":
                eval_item["status"] = "PASS"
                eval_item["findings"] = f"Generic / Common name declaration verified ({extracted_value})."
                earned_weight += weight

            else:
                eval_item["status"] = "PASS"
                eval_item["findings"] = f"Declaration verified ({extracted_value})."
                earned_weight += weight

        if is_required or extracted_value:
            total_weight += weight

        rule_evaluations.append(eval_item)

    # Count breakdown
    pass_count = sum(1 for r in rule_evaluations if r.get("status") == "PASS")
    review_count = sum(1 for r in rule_evaluations if r.get("status") == "REVIEW")
    fail_count = sum(1 for r in rule_evaluations if r.get("status") == "FAIL")
    verified_count = pass_count
    detected_count = sum(1 for r in rule_evaluations if r.get("extracted_value"))

    # Compute overall compliance score
    if total_weight > 0 and detected_count > 0:
        compliance_score = round((earned_weight / total_weight) * 100.0, 1)
    else:
        compliance_score = 0.0

    # Determine overall status classification:
    # A true critical fail occurs ONLY when a mandatory required rule has status == 'FAIL'
    critical_fails = any(r.get("required") and r.get("status") == "FAIL" for r in rule_evaluations)
    
    # Insufficient evidence: zero declarations or only 1 declaration detected
    is_insufficient = (detected_count == 0 or (detected_count == 1 and not any(r.get("field") == "mrp" and r.get("status") == "PASS" for r in rule_evaluations)))

    if is_insufficient:
        overall_status = "NON-COMPLIANT"
        compliance_score = 0.0
        summary_text = (
            "Unable to Verify — Insufficient / Invalid Product Evidence: "
            "Mandatory statutory declarations under Rule 6(1) could not be detected on the package image. "
            "Please ensure a clear, well-lit photograph of the statutory declaration label is captured."
        )
    elif critical_fails:
        overall_status = "NON-COMPLIANT"
        summary_text = (
            f"Assessed {len(rule_evaluations)} statutory rules. "
            f"Calculated Legal Metrology Compliance Index: {compliance_score}% ({overall_status}). "
            f"Detected {len(detected_issues)} non-compliance violations under Legal Metrology Rules, 2011."
        )
    elif compliance_score >= 85.0 and review_count == 0:
        overall_status = "COMPLIANT"
        summary_text = (
            f"Assessed {len(rule_evaluations)} statutory rules. "
            f"Calculated Legal Metrology Compliance Index: {compliance_score}% ({overall_status}). "
            f"All mandatory statutory declarations verified compliant with Legal Metrology Rules, 2011."
        )
    elif compliance_score >= 60.0:
        overall_status = "NEEDS REVIEW"
        summary_text = (
            f"Assessed {len(rule_evaluations)} statutory rules. "
            f"Calculated Legal Metrology Compliance Index: {compliance_score}% ({overall_status}). "
            f"Detected {len(detected_issues)} items requiring inspection officer review."
        )
    else:
        overall_status = "NON-COMPLIANT"
        summary_text = (
            f"Assessed {len(rule_evaluations)} statutory rules. "
            f"Calculated Legal Metrology Compliance Index: {compliance_score}% ({overall_status}). "
            f"Detected {len(detected_issues)} non-compliance violations under Legal Metrology Rules, 2011."
        )

    return {
        "overall_status": overall_status,
        "compliance_score": compliance_score,
        "rule_evaluations": rule_evaluations,
        "detected_issues": detected_issues,
        "summary": summary_text,
        "is_insufficient_evidence": is_insufficient,
        "verified_count": verified_count,
        "review_count": review_count,
        "fail_count": fail_count,
        "detected_count": detected_count
    }
