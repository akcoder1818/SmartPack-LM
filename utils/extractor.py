"""
SmartPack-LM: Statutory Field Extractor
Extracts declarations mandated by Legal Metrology (Packaged Commodities) Rules, 2011.
Provides confidence scores, normalized formats, and token bounding-box mapping.
"""
import re

def normalize_text(text):
    """Clean and normalize OCR text for consistent pattern matching."""
    if not text:
        return ""
    # Normalize common OCR currency quirks
    t = text.replace("₹", " Rs. ").replace("Rs.", " Rs. ").replace("Rs ", " Rs. ")
    t = re.sub(r'[\t\r]+', ' ', t)
    return t

def extract_mrp(full_text, tokens=None):
    """
    Extracts Maximum Retail Price declaration under Rule 6(1)(e).
    Checks for:
    - Numeric value
    - Currency symbol (₹ / Rs.)
    - 'inclusive of all taxes' or 'incl. of all taxes' declaration
    """
    result = {
        "value": None,
        "raw_text": None,
        "amount": None,
        "currency": None,
        "has_taxes_declaration": False,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    # Pattern for MRP with currency and optional taxes clause
    mrp_regex = re.compile(
        r'(?:M\.?R\.?P\.?|Maximum\s+Retail\s+Price|Max\.?\s*Retail\s*Price|Retail\s+Price)\s*[:.-]?\s*'
        r'([₹RsINR\.\s]*)\s*(\d+(?:[.,]\d{2})?)\s*'
        r'(\(?\s*(?:incl\.?|inclusive)?\s*(?:of)?\s*(?:all)?\s*taxes\s*\)?)?',
        re.IGNORECASE
    )

    match = mrp_regex.search(full_text)
    if match:
        curr_part = match.group(1).strip()
        amt_part = match.group(2).replace(',', '.').strip()

        try:
            val_float = float(amt_part)
            result["amount"] = val_float
            result["value"] = f"Rs. {val_float:.2f}"
            result["raw_text"] = match.group(0).strip()
            
            # Check currency symbol
            has_currency = bool(re.search(r'[₹RsINR]', curr_part, re.IGNORECASE) or 'rs' in match.group(0).lower() or '₹' in match.group(0))
            result["currency"] = "INR" if has_currency else None

            # Check inclusive of all taxes
            has_tax = bool(re.search(r'incl|inclusive|taxes', full_text[match.start():match.start()+100], re.IGNORECASE))
            result["has_taxes_declaration"] = has_tax

            # Confidence score calculation
            conf = 0.5
            if has_currency:
                conf += 0.25
            if has_tax:
                conf += 0.25
            result["confidence"] = round(conf, 2)
            result["status"] = "PASS" if (has_currency and has_tax) else "REVIEW"

        except ValueError:
            pass

    # If full regex failed, try loose numeric search near MRP keyword
    if not result["value"]:
        loose = re.search(r'(?:MRP|Retail\s*Price)[^\d\n]*(\d+(?:\.\d{2})?)', full_text, re.IGNORECASE)
        if loose:
            amt = float(loose.group(1))
            result["amount"] = amt
            result["value"] = f"Rs. {amt:.2f}"
            result["raw_text"] = loose.group(0)
            result["confidence"] = 0.4
            result["status"] = "REVIEW"

    # Find bounding box from tokens
    if tokens and result["raw_text"]:
        for tok in tokens:
            if "mrp" in tok["text"].lower() or (result["value"] and str(int(result["amount"] or 0)) in tok["text"]):
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_net_quantity(full_text, tokens=None):
    """
    Extracts Net Quantity declaration under Rule 6(1)(c) & Rule 11.
    Validates standard SI metric units (g, kg, ml, l, m, cm, N/units).
    Flags non-standard units (lbs, dozen, oz).
    """
    result = {
        "value": None,
        "raw_text": None,
        "quantity": None,
        "unit": None,
        "is_standard_unit": False,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    # Standard SI units vs non-standard
    valid_units = r'(?:kg|kilogram|kilograms|g|gm|gms|gram|grams|mg|ml|millilitre|millilitres|l|ltr|litre|litres|m|metre|cm|centimetre|mm|units|pcs|pieces|n|count)'
    non_std_units = r'(?:dozen|gross|tola|seer|pound|lbs|oz|ounce|pao)'

    qty_regex = re.compile(
        r'(?:Net\s*(?:Quantity|Qty|Weight|Wt|Volume|Vol|Contents?|Content)?\s*[:.-]?\s*)'
        r'(\d+(?:\.\d+)?)\s*(' + valid_units + r'|' + non_std_units + r')\b',
        re.IGNORECASE
    )

    match = qty_regex.search(full_text)
    if not match:
        # Try standalone number + unit pattern
        match = re.search(r'\b(\d+(?:\.\d+)?)\s*(' + valid_units + r'|' + non_std_units + r')\b', full_text, re.IGNORECASE)

    if match:
        val_str = match.group(1)
        unit_str = match.group(2).lower()
        
        try:
            val_num = float(val_str)
            result["quantity"] = val_num
            result["unit"] = unit_str
            result["value"] = f"{val_str} {unit_str}"
            result["raw_text"] = match.group(0).strip()

            # Check if unit is standard SI
            is_non_std = bool(re.match(r'^' + non_std_units + r'$', unit_str, re.IGNORECASE))
            result["is_standard_unit"] = not is_non_std

            if result["is_standard_unit"]:
                result["confidence"] = 0.95
                result["status"] = "PASS"
            else:
                result["confidence"] = 0.60
                result["status"] = "REVIEW" # Non-standard unit flag
        except ValueError:
            pass

    # Find token bbox
    if tokens and result["raw_text"]:
        for tok in tokens:
            if "net" in tok["text"].lower() or (result["unit"] and result["unit"] in tok["text"].lower()):
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_manufacturing_date(full_text, tokens=None):
    """
    Extracts Month and Year of Manufacture / Packaging under Rule 6(1)(d).
    Accepts MM/YYYY, MM/YY, MMM-YYYY, DD/MM/YYYY.
    """
    result = {
        "value": None,
        "raw_text": None,
        "date_str": None,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    date_patterns = [
        r'(?:Mfg\.?\s*(?:Date|Dt)?|Date\s*of\s*Mfg|Date\s*of\s*Packaging|Packed\s*(?:on|Date|Dt)?|Pkg\.?\s*Dt|MFD|PKD)[:.-]?\s*([A-Za-z]{3}[-/.]\d{2,4}|\d{1,2}[-/.]\d{2,4}|\d{2,4})',
        r'(?:Manufactured|Packed)\s*[:.-]?\s*(\d{1,2}[/-]\d{2,4}|[A-Za-z]{3}[-/.]\d{2,4})'
    ]

    for pattern in date_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            date_val = match.group(1).strip()
            result["date_str"] = date_val
            result["value"] = date_val
            result["raw_text"] = match.group(0).strip()
            
            if re.match(r'^\d{4}$', date_val):
                result["confidence"] = 0.55
                result["status"] = "REVIEW"
            else:
                result["confidence"] = 0.90
                result["status"] = "PASS"
            break

    if tokens and result["raw_text"]:
        for tok in tokens:
            if "mfg" in tok["text"].lower() or "pkd" in tok["text"].lower() or "packed" in tok["text"].lower():
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_best_before(full_text, tokens=None):
    """
    Extracts Best Before / Expiry declaration under Rule 6(1)(d) Proviso.
    """
    result = {
        "value": None,
        "raw_text": None,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    bb_regex = re.compile(
        r'(?:Best\s*Before|Use\s*By|Expiry\s*Date|Exp\.?\s*(?:Date|Dt)?|Exp\.)[:.-]?\s*'
        r'(\d{1,2}\s*(?:Months|Years|Days)(?:\s*from\s*(?:date\s*of\s*)?(?:mfg|packaging|manufacture))?|\d{1,2}[-/.]\d{2,4}|[A-Za-z]{3}[-/.]\d{2,4})',
        re.IGNORECASE
    )

    match = bb_regex.search(full_text)
    if match:
        result["value"] = match.group(1).strip()
        result["raw_text"] = match.group(0).strip()
        result["confidence"] = 0.88
        result["status"] = "PASS"

    if tokens and result["raw_text"]:
        for tok in tokens:
            if "best before" in tok["text"].lower() or "expiry" in tok["text"].lower() or "exp" in tok["text"].lower():
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_consumer_care(full_text, tokens=None):
    """
    Extracts Consumer Care details under Rule 6(1)(f) & Rule 6(2).
    Requires contact channels (Toll-free/phone number, email, address).
    """
    result = {
        "value": None,
        "raw_text": None,
        "phone": None,
        "email": None,
        "address": None,
        "has_multi_channel": False,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    phone_match = re.search(r'(?:Toll\s*Free|Helpline|Tel|Call|Phone|Contact|Care\s*No)?\s*[:.-]?\s*(\b1800[- ]?\d{3}[- ]?\d{3,4}\b|\b\+?91[- ]?\\d{10}\b|\b0\d{2,4}[- ]?\d{6,8}\b|\b\d{10}\b)', full_text, re.IGNORECASE)
    if phone_match:
        result["phone"] = phone_match.group(1).strip()

    email_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', full_text)
    if email_match:
        result["email"] = email_match.group(1).strip()

    cc_header_match = re.search(r'(?:Consumer\s*Care|Customer\s*Care|Customer\s*Feedback|Grievance\s*Cell|Reach\s*Us\s*At)[^:\n]*[:.-]?(.*?)(?:\n|$)', full_text, re.IGNORECASE)
    if cc_header_match:
        result["raw_text"] = cc_header_match.group(0).strip()

    parts = []
    if result["phone"]:
        parts.append(f"Tel: {result['phone']}")
    if result["email"]:
        parts.append(f"Email: {result['email']}")
    if cc_header_match and not parts:
        parts.append(cc_header_match.group(0).strip())

    if parts:
        result["value"] = " | ".join(parts)
        channels = (1 if result["phone"] else 0) + (1 if result["email"] else 0)
        result["has_multi_channel"] = channels >= 2
        conf = 0.5 + (0.25 * channels)
        result["confidence"] = min(conf, 0.95)
        result["status"] = "PASS" if channels >= 1 else "REVIEW"

    if tokens and (result["phone"] or result["email"] or "consumer" in full_text.lower()):
        for tok in tokens:
            if "consumer" in tok["text"].lower() or "care" in tok["text"].lower() or "feedback" in tok["text"].lower() or "1800" in tok["text"]:
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_country_of_origin(full_text, tokens=None):
    """
    Extracts Country of Origin under Rule 6(1)(g).
    """
    result = {
        "value": None,
        "raw_text": None,
        "country": None,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    known_countries = [
        "India", "China", "USA", "United States", "Germany", "Japan", "Vietnam",
        "Thailand", "Bangladesh", "Indonesia", "Taiwan", "Korea", "South Korea",
        "Malaysia", "UK", "United Kingdom", "Italy", "France", "Sri Lanka", "Nepal", "Bhutan"
    ]
    countries_regex = "|".join(known_countries)

    co_match = re.search(
        r'(?:Country\s*of\s*Origin|Made\s*in|Product\s*of|Manufactured\s*in|Origin\s*:)[:.-]?\s*([A-Za-z\s]+)',
        full_text,
        re.IGNORECASE
    )

    if co_match:
        detected_text = co_match.group(1).strip()
        for c in known_countries:
            if c.lower() in detected_text.lower():
                result["country"] = c
                result["value"] = c
                result["raw_text"] = co_match.group(0).strip()
                result["confidence"] = 0.95
                result["status"] = "PASS"
                break
        if not result["value"]:
            first_word = detected_text.split()[0] if detected_text else ""
            if len(first_word) > 2:
                result["country"] = first_word.capitalize()
                result["value"] = first_word.capitalize()
                result["raw_text"] = co_match.group(0).strip()
                result["confidence"] = 0.70
                result["status"] = "PASS"

    if not result["value"]:
        direct = re.search(r'\b(Made\s*in\s*(' + countries_regex + r'))\b', full_text, re.IGNORECASE)
        if direct:
            result["country"] = direct.group(2).capitalize()
            result["value"] = direct.group(2).capitalize()
            result["raw_text"] = direct.group(1)
            result["confidence"] = 0.90
            result["status"] = "PASS"

    if tokens and result["raw_text"]:
        for tok in tokens:
            if "origin" in tok["text"].lower() or "made in" in tok["text"].lower() or (result["country"] and result["country"].lower() in tok["text"].lower()):
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_manufacturer(full_text, tokens=None):
    """
    Extracts Manufacturer / Packer / Importer name & address under Rule 6(1)(a).
    """
    result = {
        "value": None,
        "raw_text": None,
        "has_pincode": False,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    mfg_match = re.search(
        r'(?:Manufactured\s*by|Mfg\s*by|Packed\s*by|Pkd\s*by|Marketed\s*by|Mktd\s*by|Imported\s*by|Mfd\s*by)[:.-]?\s*([^\n\r]+(?:\n[^\n\r]+)?)',
        full_text,
        re.IGNORECASE
    )

    if mfg_match:
        mfg_str = mfg_match.group(1).strip()
        result["value"] = mfg_str
        result["raw_text"] = mfg_match.group(0).strip()
        
        has_pin = bool(re.search(r'\b\d{6}\b', mfg_str) or re.search(r'pin(?:code)?', mfg_str, re.IGNORECASE))
        result["has_pincode"] = has_pin
        
        conf = 0.65 + (0.25 if has_pin else 0.0) + (0.1 if len(mfg_str) > 25 else 0.0)
        result["confidence"] = min(conf, 0.95)
        result["status"] = "PASS" if has_pin else "REVIEW"

    if tokens and result["raw_text"]:
        for tok in tokens:
            if "manufactured" in tok["text"].lower() or "mfg" in tok["text"].lower() or "packed" in tok["text"].lower():
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_product_name(full_text, lines=None, tokens=None):
    """
    Extracts generic or brand name of commodity under Rule 6(1)(b).
    """
    result = {
        "value": None,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    if lines and len(lines) > 0:
        for l in lines[:3]:
            cleaned = l.strip()
            if len(cleaned) >= 4 and not re.match(r'^\d+$', cleaned) and not any(k in cleaned.lower() for k in ["mfg", "mrp", "exp", "net wt"]):
                result["value"] = cleaned
                result["confidence"] = 0.85
                result["status"] = "PASS"
                break

    if not result["value"]:
        first_line = full_text.splitlines()[0] if full_text else ""
        if len(first_line.strip()) >= 3:
            result["value"] = first_line.strip()
            result["confidence"] = 0.70
            result["status"] = "PASS"

    if tokens and result["value"]:
        for tok in tokens:
            if result["value"].lower() in tok["text"].lower() or tok["text"].lower() in result["value"].lower():
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_unit_sale_price(full_text, tokens=None):
    """
    Extracts Unit Sale Price (USP) under Rule 6(1)(e) Proviso / 2021 Amendment.
    """
    result = {
        "value": None,
        "raw_text": None,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    usp_regex = re.compile(
        r'(?:Unit\s*Sale\s*Price|USP|Price\s*per\s*Unit)[:.-]?\s*([₹RsINR\.\s]*\s*\d+(?:\.\d{2})?\s*/\s*(?:g|gm|kg|ml|l|ltr|piece|item|N|units?))\b',
        re.IGNORECASE
    )

    match = usp_regex.search(full_text)
    if match:
        result["value"] = match.group(1).strip()
        result["raw_text"] = match.group(0).strip()
        result["confidence"] = 0.90
        result["status"] = "PASS"

    if tokens and result["raw_text"]:
        for tok in tokens:
            if "unit sale" in tok["text"].lower() or "usp" in tok["text"].lower() or "/g" in tok["text"].lower() or "/ml" in tok["text"].lower():
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_dimensions(full_text, tokens=None):
    """
    Extracts dimensions/size declaration under Rule 6(1)(d) where applicable.
    """
    result = {
        "value": None,
        "raw_text": None,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    dim_regex = re.compile(
        r'(?:Dimensions?|Size|LxWxH)[:.-]?\s*(\d+(?:\.\d+)?\s*(?:cm|mm|m|inch|in)\s*[xX*]\s*\d+(?:\.\d+)?\s*(?:cm|mm|m|inch|in)(?:\s*[xX*]\s*\d+(?:\.\d+)?\s*(?:cm|mm|m|inch|in))?)',
        re.IGNORECASE
    )

    match = dim_regex.search(full_text)
    if match:
        result["value"] = match.group(1).strip()
        result["raw_text"] = match.group(0).strip()
        result["confidence"] = 0.88
        result["status"] = "PASS"

    return result

def extract_all_fields(ocr_result):
    """
    Master extractor combining all statutory field detectors.
    """
    full_text = normalize_text(ocr_result.get("full_text", ""))
    lines = ocr_result.get("lines", [])
    tokens = ocr_result.get("tokens", [])

    extracted = {
        "product_name": extract_product_name(full_text, lines, tokens),
        "manufacturer": extract_manufacturer(full_text, tokens),
        "country_of_origin": extract_country_of_origin(full_text, tokens),
        "net_quantity": extract_net_quantity(full_text, tokens),
        "mrp": extract_mrp(full_text, tokens),
        "manufacturing_date": extract_manufacturing_date(full_text, tokens),
        "best_before": extract_best_before(full_text, tokens),
        "consumer_care": extract_consumer_care(full_text, tokens),
        "unit_sale_price": extract_unit_sale_price(full_text, tokens),
        "dimensions": extract_dimensions(full_text, tokens)
    }

    return extracted
