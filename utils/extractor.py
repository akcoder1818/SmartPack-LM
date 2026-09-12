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
    
    t = text
    # 1. Normalize Devanagari numerals to standard ASCII digits (Tesseract eng+hin)
    devanagari_to_ascii = str.maketrans({
        '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
        '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
    })
    t = t.translate(devanagari_to_ascii)

    # 2. Normalize smart quotes and OCR symbol artifacts
    t = t.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')

    # 3. Currency normalization
    t = t.replace("₹", " Rs. ")
    t = re.sub(r'\b(?:Rs\.|Rs|INR|Re\.|Re)\b', ' Rs. ', t, flags=re.IGNORECASE)

    # 4. Common OCR word concatenations on statutory declarations
    t = re.sub(r'\bNet\s*Weight\b', 'Net Weight', t, flags=re.IGNORECASE)
    t = re.sub(r'\bNetWeight\b', 'Net Weight', t, flags=re.IGNORECASE)
    t = re.sub(r'\bNetContents\b', 'Net Contents', t, flags=re.IGNORECASE)
    t = re.sub(r'\bNetQuantity\b', 'Net Quantity', t, flags=re.IGNORECASE)
    t = re.sub(r'\bNetQty\b', 'Net Qty', t, flags=re.IGNORECASE)
    t = re.sub(r'\bCountryofOrigin\b', 'Country of Origin', t, flags=re.IGNORECASE)
    t = re.sub(r'\bConsumerCare\b', 'Consumer Care', t, flags=re.IGNORECASE)
    t = re.sub(r'\bUnitSalePrice\b', 'Unit Sale Price', t, flags=re.IGNORECASE)
    t = re.sub(r'\bGenericName\b', 'Generic Name', t, flags=re.IGNORECASE)

    # 5. Common OCR tax clause concatenations: ofaltaxes -> of all taxes, ofall -> of all, etc.
    t = re.sub(r'\bofaltaxes\b', 'of all taxes', t, flags=re.IGNORECASE)
    t = re.sub(r'\bofall\s*taxes\b', 'of all taxes', t, flags=re.IGNORECASE)
    t = re.sub(r'\binclusiveof\b', 'inclusive of ', t, flags=re.IGNORECASE)
    t = re.sub(r'\binclof\b', 'incl of ', t, flags=re.IGNORECASE)

    # 6. Common OCR spaces in email addresses: e.g. "feedback @ britannia.co.in"
    t = re.sub(r'([a-zA-Z0-9_.+-]+)\s*@\s*([a-zA-Z0-9-.]+)\s*\.\s*([a-zA-Z]{2,})', r'\1@\2.\3', t)

    t = re.sub(r'[\t\r]+', ' ', t)
    return t

def extract_mrp(full_text, tokens=None):
    """
    Extracts Maximum Retail Price declaration under Rule 6(1)(e).
    Checks for:
    - Numeric value
    - Currency symbol (₹ / Rs. / INR)
    - 'inclusive of all taxes' or 'incl. of all taxes' declaration
    Tolerates common OCR punctuation, spacing, and label variants:
      M.R.P., MRP ₹, MRP Rs, MRP INR, Max Retail Price, Maximum Retail Price (MRP),
      and multiline tax inclusion declarations.
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

    if not full_text:
        return result

    # Comprehensive tax inclusion pattern
    tax_pattern = r'(?:\(?\s*(?:incl\.?|inclusive|inc\.?)\s*(?:of)?\s*(?:all)?\s*taxes?\s*\)?|\ball\s*taxes\s*incl(?:uded|usive)?\b|\btaxes\s*incl(?:uded|usive)?\b|\bincl\.?\s*taxes?\b|\bof\s*all\s*taxes\b|\bofaltaxes\b)'

    # Pattern 1: Structured MRP declaration with optional (MRP) subtag or tax clause
    mrp_regex = re.compile(
        r'(?:M\.?\s*R\.?\s*P\.?|Maximum\s+Retail\s+Price(?:\s*\(?\s*MRP\s*\)?)?|Max\.?\s*Retail\s*Price|Retail\s+Price)\s*'
        r'(?:' + tax_pattern + r')?\s*[:.\-_=~;]?\s*'
        r'([₹RsINR\.\s]*)\s*(\d+(?:[.,]\d{1,2})?)\s*(?:/[-–])?\s*'
        r'(' + tax_pattern + r')?',
        re.IGNORECASE
    )

    match = mrp_regex.search(full_text)
    val_float = None

    if match:
        curr_part = match.group(1).strip()
        amt_part = match.group(2).replace(',', '.').strip()
        try:
            val_float = float(amt_part)
            result["amount"] = val_float
            result["value"] = f"Rs. {val_float:.2f}"
            result["raw_text"] = match.group(0).strip()
        except ValueError:
            pass

    # Pattern 2: Fallback loose search with MRP keyword context
    if val_float is None:
        loose = re.search(
            r'(?:M\.?\s*R\.?\s*P\.?|Maximum\s+Retail\s+Price(?:\s*\(?\s*MRP\s*\)?)?|Max(?:imum)?\.?\s*Retail\s*Price|Retail\s*Price)\s*'
            r'[:.\-_=~;]?[^\d\n\r]*?([₹RsINR\.\s]*)\s*(\d+(?:[.,]\d{1,2})?)',
            full_text,
            re.IGNORECASE
        )
        if loose:
            try:
                amt = float(loose.group(2).replace(',', '.'))
                val_float = amt
                result["amount"] = amt
                result["value"] = f"Rs. {amt:.2f}"
                result["raw_text"] = loose.group(0).strip()
                match = loose
            except (ValueError, IndexError):
                pass

    if val_float is not None and match:
        # Check currency symbol in match and surrounding window (up to 60 chars)
        match_start = match.start()
        match_end = match.end()
        curr_window = full_text[max(0, match_start - 30):min(len(full_text), match_end + 30)]
        has_currency = bool(
            re.search(r'[₹]|(?:\b(?:Rs\.?|INR|Rupees?)\b)', curr_window, re.IGNORECASE) or
            'rs' in match.group(0).lower() or
            '₹' in match.group(0) or
            'inr' in match.group(0).lower()
        )
        result["currency"] = "INR" if has_currency else None

        # Check inclusive of all taxes in match or surrounding lines (up to 150 chars forward and backward)
        taxes_window = full_text[max(0, match_start - 60):min(len(full_text), match_end + 150)]
        has_tax = bool(re.search(tax_pattern, taxes_window, re.IGNORECASE))
        result["has_taxes_declaration"] = has_tax

        # Confidence and status calculation
        if has_currency and has_tax:
            result["confidence"] = 0.95
            result["status"] = "PASS"
        elif has_currency:
            result["confidence"] = 0.75
            result["status"] = "REVIEW"  # Tax clause absent/unclear
        else:
            result["confidence"] = 0.50
            result["status"] = "REVIEW"

    # Find bounding box from tokens
    if tokens and result["raw_text"]:
        for tok in tokens:
            t_lower = tok["text"].lower()
            if "mrp" in t_lower or "m.r.p" in t_lower or (result["value"] and str(int(result["amount"] or 0)) in tok["text"]):
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_net_quantity(full_text, tokens=None):
    """
    Extracts Net Quantity declaration under Rule 6(1)(c) & Rule 11.
    Validates standard SI metric units (g, kg, ml, l, m, cm, N/units).
    Flags non-standard units (lbs, dozen, oz).
    Tolerates localized OCR substitutions (e.g. '250 9' -> '250 g', 'm1' -> 'ml', 'Ibs' -> 'lbs').
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

    if not full_text:
        return result

    # Standard SI units vs non-standard
    valid_units = r'(?:kg|kilograms?|g|gms?|grams?|mg|milligrams?|ml|millilitres?|milliliters?|l|ltr|ltrs?|litres?|liters?|m|metres?|meters?|cm|centimetres?|centimeters?|mm|units?|pcs|pieces?|n|count)'
    # Non-standard units under Rule 11 (including OCR variants like Ibs with capital I or 1bs)
    non_std_units = r'(?:dozen|gross|tola|seer|pounds?|lbs?|Ibs|1bs|oz|ounces?|pao)'
    ocr_units = r'(?:9|k9|m1)'

    # Explicit declaration prefix
    net_prefix = r'(?:Net\s*(?:Quantity|Qty|Weight|Wt|Mass|Volume|Vol|Contents?|Content|Qnty)?|Quantity|Qty|Weight|Wt|Net)\s*[:.\-_=~;]?'

    # Pattern 1: Explicit declaration prefix (allows localized OCR unit substitutions like '9' for 'g', 'Ibs' for 'lbs')
    qty_regex = re.compile(
        net_prefix + r'\s*(\d+(?:\.\d+)?)\s*(' + valid_units + r'|' + non_std_units + r'|' + ocr_units + r')\b',
        re.IGNORECASE
    )

    match = qty_regex.search(full_text)
    is_ocr_substituted = False

    if not match:
        # Pattern 2: Standalone number + standard unit
        match = re.search(r'\b(\d+(?:\.\d+)?)\s*(' + valid_units + r'|' + non_std_units + r')\b', full_text, re.IGNORECASE)

    if match:
        val_str = match.group(1)
        unit_raw = match.group(2).lower()
        
        # Localized unit normalization
        if unit_raw == '9':
            unit_str = 'g'
            is_ocr_substituted = True
        elif unit_raw == 'k9':
            unit_str = 'kg'
            is_ocr_substituted = True
        elif unit_raw == 'm1':
            unit_str = 'ml'
            is_ocr_substituted = True
        elif unit_raw in ('ibs', '1bs', 'lb', 'lbs'):
            unit_str = 'lbs'
        else:
            unit_str = unit_raw

        try:
            val_num = float(val_str)
            result["quantity"] = val_num
            result["unit"] = unit_str
            result["value"] = f"{val_str} {unit_str}"
            result["raw_text"] = match.group(0).strip()

            # Check if unit is standard SI
            is_non_std = bool(re.match(r'^(?:dozen|gross|tola|seer|pounds?|lbs?|Ibs|1bs|oz|ounces?|pao)$', unit_str, re.IGNORECASE))
            result["is_standard_unit"] = not is_non_std

            if result["is_standard_unit"]:
                result["confidence"] = 0.90 if is_ocr_substituted else 0.95
                result["status"] = "PASS"
            else:
                # Non-standard unit detected -> Report FAIL under Rule 11 (actionable violation, NOT missing)
                result["confidence"] = 0.85
                result["status"] = "FAIL"
        except ValueError:
            pass

    # Find token bbox
    if tokens and result["raw_text"]:
        for tok in tokens:
            t_lower = tok["text"].lower()
            if "net" in t_lower or "qty" in t_lower or (result["unit"] and result["unit"] in t_lower):
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_manufacturing_date(full_text, tokens=None):
    """
    Extracts Month and Year of Manufacture / Packaging under Rule 6(1)(d).
    Accepts MM/YYYY, MM/YY, MMM-YYYY, MMM/YYYY, DD/MM/YYYY, YYYY.
    Tolerates OCR variations (e.g. 'Date of ig', 'Date of mg', 'Date of Mfy', 'PKD ON:', 'MFD:').
    """
    result = {
        "value": None,
        "raw_text": None,
        "date_str": None,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    if not full_text:
        return result

    date_patterns = [
        # Standard explicit headers with date values
        r'(?:Date\s*of\s*(?:Mf[gyG]|ig|mg|Manufacture|Packaging|Packing|Pkg|PKD)|Manufacturing\s*Date|Packaging\s*Date|Packing\s*Date|Packed\s*on|Manufactured\s*on|Mfg\.?\s*(?:Date|Dt)?|Mfy\.?\s*(?:Date|Dt)?|Mfd\.?\s*(?:Date|Dt)?|Pkg\.?\s*(?:Date|Dt)?|PKD\.?\s*(?:Date|Dt|ON)?|MFD\.?\s*(?:Date|Dt|ON)?|MFG\.?|DOM\.?|D\.O\.M\.?|DOP\.?|D\.O\.P\.?|Month\s*(?:&|and)\s*Year\s*of\s*(?:Mfg|Packaging|Manufacture)|Mth\s*(?:&|and)\s*Yr\s*of\s*(?:Mfg|Packaging))\s*[:.\-_=~;]?\s*([A-Za-z]{3,9}\s*[-/.]\s*\d{2,4}|\d{1,2}\s*[-/.]\s*\d{2,4}|\d{4})',
        # Catch manufactured or packed followed by date
        r'(?:Manufactured|Packed)\s*[:.\-_=~;]?\s*(\d{1,2}\s*[-/.]\s*\d{2,4}|[A-Za-z]{3,9}\s*[-/.]\s*\d{2,4})',
        # Tolerant catch: "Date of ... : MM/YYYY"
        r'(?:Date\s*of\s*[A-Za-z.]+)\s*[:.\-_=~;]?\s*([A-Za-z]{3,9}\s*[-/.]\s*\d{2,4}|\d{1,2}\s*[-/.]\s*\d{2,4})'
    ]

    for pattern in date_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            date_raw = match.group(1).strip()
            # Normalize internal spaces e.g. "08 / 2026" -> "08/2026"
            date_val = re.sub(r'\s*([-/.]\s*)', '/', date_raw) if '/' in date_raw else date_raw.replace(' ', '')
            result["date_str"] = date_val
            result["value"] = date_val
            result["raw_text"] = match.group(0).strip()

            if re.match(r'^\d{4}$', date_val):
                result["confidence"] = 0.55
                result["status"] = "REVIEW"  # Incomplete date under Rule 6(1)(d)
            else:
                result["confidence"] = 0.90
                result["status"] = "PASS"
            break

    if tokens and result["raw_text"]:
        for tok in tokens:
            t_lower = tok["text"].lower()
            if "mfg" in t_lower or "mfy" in t_lower or "pkd" in t_lower or "packed" in t_lower or "date" in t_lower:
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_best_before(full_text, tokens=None):
    """
    Extracts Best Before / Expiry declaration under Rule 6(1)(d) Proviso.
    Tolerates OCR variants like 'Best Bef', 'Best Bfore', 'Best Before:9 Before: Months', 'Use Before', 'Expiry Date'.
    """
    result = {
        "value": None,
        "raw_text": None,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    if not full_text:
        return result

    bb_regex = re.compile(
        r'(?:Best\s*(?:Before|Bef|Bfore|Befor)|Use\s*(?:Before|By)|Date\s*of\s*Expiry|Expiry\s*(?:Date|Dt)?|Exp\.?\s*(?:Date|Dt)?|Exp\.)\s*[:.\-_=~;]?\s*'
        r'(\d{1,2}(?:\s*(?:Before:?|Bef:?))?\s*(?:Months?|Years?|Days?|Mths?|Yrs?)(?:\s*from\s*(?:date\s*of\s*)?(?:mfg|packaging|manufacture|pkg|mfd|mfy|packing))?|\d{1,2}\s*[-/.]\s*\d{2,4}|[A-Za-z]{3}\s*[-/.]\s*\d{2,4})',
        re.IGNORECASE
    )

    match = bb_regex.search(full_text)
    if match:
        val = match.group(1).strip()
        # Clean potential OCR stutter like "9 Before: Months" -> "9 Months"
        val = re.sub(r'(\d{1,2})\s*(?:Before:?|Bef:?)\s*', r'\1 ', val, flags=re.IGNORECASE)
        result["value"] = val
        result["raw_text"] = match.group(0).strip()
        result["confidence"] = 0.88
        result["status"] = "PASS"

    if tokens and result["raw_text"]:
        for tok in tokens:
            t_lower = tok["text"].lower()
            if "best before" in t_lower or "bfore" in t_lower or "expiry" in t_lower or "exp" in t_lower:
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_consumer_care(full_text, tokens=None):
    """
    Extracts Consumer Care details under Rule 6(1)(f) & Rule 6(2).
    Requires contact channels (Toll-free/phone number, email, address).
    Supports Consumer Care, Consumer Care Gel/Cell, Customer Care, Consumer Complaint, Helpline, Grievance Cell.
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

    if not full_text:
        return result

    # Phone numbers: toll-free 1800, mobile with optional +91, landline
    phone_match = re.search(
        r'(?:Toll\s*Free|Helpline|Tel|Call|Phone|Contact|Care\s*No)?\s*[:.\-_=~;]?\s*'
        r'(\b1800[- ]?\d{3,4}[- ]?\d{3,4}\b|(?:\+?91[- ]?)?[6-9]\d{9}\b|\b0\d{2,4}[- ]?\d{6,8}\b|\b\d{10}\b)',
        full_text,
        re.IGNORECASE
    )
    if phone_match:
        result["phone"] = phone_match.group(1).strip()

    # Email pattern: handles normalized and raw email formats
    email_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', full_text)
    if email_match:
        result["email"] = email_match.group(1).strip()

    cc_header_match = re.search(
        r'(?:Consumer\s*Care(?:\s*(?:Cell|Gel|No\.?|Number))?|Consumer\s*Complaint(?:\s*(?:Cell|Gel|No\.?))?|Customer\s*Care(?:\s*(?:Cell|Gel|No\.?|Number))?|Customer\s*(?:Feedback|Support)|Grievance\s*Cell|Reach\s*Us\s*At)[^:\n]*[:.\-_=~;]?(.*?)(?:\n|$)',
        full_text,
        re.IGNORECASE
    )
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
        conf = 0.60 + (0.20 * channels)
        result["confidence"] = min(conf, 0.95)
        result["status"] = "PASS" if channels >= 1 else "REVIEW"

    if tokens and (result["phone"] or result["email"] or "consumer" in full_text.lower()):
        for tok in tokens:
            t_lower = tok["text"].lower()
            if "consumer" in t_lower or "care" in t_lower or "feedback" in t_lower or "1800" in tok["text"]:
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_country_of_origin(full_text, tokens=None):
    """
    Extracts Country of Origin under Rule 6(1)(g).
    Tolerates OCR variants like 'Country Of Orlgin', 'Made in', 'Product of', 'Country ofOrigin: Origin: India'.
    Strictly prevents stop words ('Origin', 'Declaration', 'Absent') from being marked as country.
    """
    result = {
        "value": None,
        "raw_text": None,
        "country": None,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    if not full_text:
        return result

    # Check for explicit absent notice first (e.g. synthetic non-compliant sample notice)
    if re.search(r'\[Notice:\s*Country\s*(?:of\s*origin)?\s*declaration\s*absent\]', full_text, re.IGNORECASE):
        return result

    known_countries = [
        "India", "China", "USA", "United States", "Germany", "Japan", "Vietnam",
        "Thailand", "Bangladesh", "Indonesia", "Taiwan", "Korea", "South Korea",
        "Malaysia", "UK", "United Kingdom", "Italy", "France", "Sri Lanka", "Nepal", "Bhutan"
    ]
    countries_regex = "|".join(known_countries)

    # 1. Search for explicit Country of Origin declaration
    co_match = re.search(
        r'(?:Country\s*of\s*(?:Origin|Orlgin|Origln|Origi|Orig)|Made\s*in|Product\s*of|Manufactured\s*in|Origin)\s*'
        r'(?:[:.\-_=~;]?\s*(?:Origin|Orlgin|Country))*\s*[:.\-_=~;]?\s*([^\n\r]+)',
        full_text,
        re.IGNORECASE
    )

    if co_match:
        context_str = co_match.group(1).strip()
        # Look for a valid country in the captured context
        for c in known_countries:
            if re.search(r'\b' + re.escape(c) + r'\b', context_str, re.IGNORECASE):
                result["country"] = c
                result["value"] = c
                result["raw_text"] = co_match.group(0).strip()
                result["confidence"] = 0.95
                result["status"] = "PASS"
                break

    # 2. Search for direct "Made in <Country>" or "Product of <Country>" anywhere
    if not result["value"]:
        direct = re.search(r'\b(?:Made\s*in|Product\s*of|Origin\s*:?)\s*(' + countries_regex + r')\b', full_text, re.IGNORECASE)
        if direct:
            found_c = direct.group(1).capitalize()
            # Canonicalize name
            if found_c.lower() == "united states":
                found_c = "USA"
            result["country"] = found_c
            result["value"] = found_c
            result["raw_text"] = direct.group(0)
            result["confidence"] = 0.90
            result["status"] = "PASS"

    if tokens and result["raw_text"]:
        for tok in tokens:
            t_lower = tok["text"].lower()
            if "origin" in t_lower or "made in" in t_lower or (result["country"] and result["country"].lower() in t_lower):
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_manufacturer(full_text, tokens=None):
    """
    Extracts Manufacturer / Packer / Importer name & address under Rule 6(1)(a).
    Supports 'Manufactured by', 'Manufacturer', 'Manufactured & Packed by', 'Packed by', 'Mfd by', 'Marketed by'.
    Captures multi-line addresses and verifies 6-digit postal PIN codes (including spaced PIN codes like '249 403').
    """
    result = {
        "value": None,
        "raw_text": None,
        "has_pincode": False,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    if not full_text:
        return result

    mfg_match = re.search(
        r'(?:Manufactured\s*(?:&|and)\s*(?:Packed|Marketed)\s*by|Manufactured\s*by|Manufacturer\s*(?:Name\s*&?\s*Address|Address)?|'
        r'Mfg\.?\s*(?:&|and)\s*Pkd\.?\s*by|Mfg\.?\s*by|Mfd\.?\s*by|Packed\s*by|Pkd\.?\s*by|Marketed\s*by|Mktd\.?\s*by|Imported\s*by)\s*'
        r'[:.\-_=~;]?\s*([^\n\r]+(?:\n[^\n\r]+){0,3})',
        full_text,
        re.IGNORECASE
    )

    if mfg_match:
        raw_mfg_str = mfg_match.group(1).strip()
        # Clean leading stray artifacts like "by.", "by:", "'", or "Address:"
        cleaned_mfg = re.sub(r'^(?:by[.:\s]+|[\'"]+|Address[:.\s]+)+', '', raw_mfg_str, flags=re.IGNORECASE).strip()
        
        # Truncate if it runs into another statutory declaration keyword
        stop_keywords = r'\b(?:Net\s*Weight|Net\s*Qty|Net\s*Contents|Country\s*of\s*Origin|MRP|Best\s*Before|Date\s*of|Batch)\b'
        cleaned_mfg = re.split(stop_keywords, cleaned_mfg, flags=re.IGNORECASE)[0].strip()

        if len(cleaned_mfg) >= 6:
            result["value"] = cleaned_mfg
            result["raw_text"] = mfg_match.group(0).strip()

            # PIN code detection: 6 digits (contiguous or with single space 123 456)
            has_pin = bool(
                re.search(r'\b\d{6}\b', cleaned_mfg) or
                re.search(r'\b\d{3}\s\d{3}\b', cleaned_mfg) or
                re.search(r'pin(?:code)?', cleaned_mfg, re.IGNORECASE)
            )
            result["has_pincode"] = has_pin

            conf = 0.70 + (0.25 if has_pin else 0.0) + (0.05 if len(cleaned_mfg) > 25 else 0.0)
            result["confidence"] = min(conf, 0.95)
            result["status"] = "PASS" if has_pin else "REVIEW"

    if tokens and result["raw_text"]:
        for tok in tokens:
            t_lower = tok["text"].lower()
            if "manufactured" in t_lower or "manufacturer" in t_lower or "mfg" in t_lower or "packed" in t_lower or "marketed" in t_lower:
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_product_name(full_text, lines=None, tokens=None):
    """
    Extracts generic or brand name of commodity under Rule 6(1)(b).
    Prioritizes explicit statutory declarations ('Generic Name:', 'Common Name:', 'Commodity:').
    """
    result = {
        "value": None,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    if not full_text and not lines:
        return result

    # 1. Prioritize statutory 'Generic Name:' or 'Commodity:' line
    gen_match = re.search(
        r'(?:Generic\s*Name|Common\s*Name|Name\s*of\s*(?:the\s*)?Commodity|Commodity|Product\s*Name)\s*[:.\-_=~;]?\s*([^\n\r]+)',
        full_text,
        re.IGNORECASE
    )
    if gen_match:
        val = gen_match.group(1).strip()
        # Clean trailing separators
        val = re.sub(r'[:.\-_=~;]+$', '', val).strip()
        if len(val) >= 3 and not re.match(r'^\d+$', val):
            result["value"] = val
            result["confidence"] = 0.95
            result["status"] = "PASS"

    # 2. Fall back to top clean lines (brand/product title)
    if not result["value"] and lines and len(lines) > 0:
        for l in lines[:4]:
            cleaned = l.strip()
            # Clean leading/trailing punctuation
            cleaned = re.sub(r'^[^\w\s]+|[^\w\s]+$', '', cleaned).strip()
            # Ensure line has reasonable alphabetic content and not pure noise
            alpha_count = sum(1 for c in cleaned if c.isalpha())
            if len(cleaned) >= 4 and alpha_count >= 3 and not re.match(r'^\d+$', cleaned):
                if not any(k in cleaned.lower() for k in ["mfg", "mrp", "exp", "net wt", "batch", "date of"]):
                    result["value"] = cleaned
                    result["confidence"] = 0.85
                    result["status"] = "PASS"
                    break

    if not result["value"] and full_text:
        first_line = full_text.splitlines()[0] if full_text else ""
        cleaned = re.sub(r'^[^\w\s]+|[^\w\s]+$', '', first_line).strip()
        if len(cleaned) >= 3 and sum(1 for c in cleaned if c.isalpha()) >= 3:
            result["value"] = cleaned
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
    Supports Unit Sale Price, Unit Selling Price, Sale Price per, Price per Unit/kg/litre.
    Never infers a unit sale price from MRP.
    """
    result = {
        "value": None,
        "raw_text": None,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    if not full_text:
        return result

    usp_regex = re.compile(
        r'(?:Unit\s*Sale\s*Price|Unit\s*Selling\s*Price|Sale\s*Price\s*per|Price\s*per\s*(?:Unit|kg|litre|liter|g|gm|ml)|USP)\s*[:.\-_=~;]?\s*'
        r'([₹RsINR\.\s]*\s*\d+(?:\.\d{1,2})?\s*/?\s*(?:per\s*)?(?:g|gm|kg|ml|l|ltr|litre|piece|item|N|units?|9))\b',
        re.IGNORECASE
    )

    match = usp_regex.search(full_text)
    if match:
        val = match.group(1).strip()
        # Clean OCR unit substitution like '/ 9' -> '/ g'
        val = re.sub(r'/\s*9\b', '/ g', val)
        result["value"] = val
        result["raw_text"] = match.group(0).strip()
        result["confidence"] = 0.90
        result["status"] = "PASS"

    if tokens and result["raw_text"]:
        for tok in tokens:
            t_lower = tok["text"].lower()
            if "unit sale" in t_lower or "usp" in t_lower or "/g" in t_lower or "/ml" in t_lower or "/kg" in t_lower:
                result["bbox"] = tok["bbox"]
                break

    return result

def extract_dimensions(full_text, tokens=None):
    """
    Extracts dimensions/size declaration under Rule 6(1)(d) where applicable.
    Conservative pattern requiring recognizable dimension patterns.
    """
    result = {
        "value": None,
        "raw_text": None,
        "confidence": 0.0,
        "bbox": None,
        "status": "NOT_DETECTED"
    }

    if not full_text:
        return result

    dim_regex = re.compile(
        r'(?:Dimensions?|Size|LxWxH)\s*[:.\-_=~;]?\s*'
        r'(\d+(?:\.\d+)?\s*(?:cm|mm|m|inch|in|em)?\s*[xX*]\s*\d+(?:\.\d+)?\s*(?:cm|mm|m|inch|in|em)?(?:\s*[xX*]\s*\d+(?:\.\d+)?\s*(?:cm|mm|m|inch|in|em)?)?)',
        re.IGNORECASE
    )

    match = dim_regex.search(full_text)
    if match:
        val = match.group(1).strip()
        # Clean OCR artifact "em" -> "cm"
        val = re.sub(r'\bem\b', 'cm', val)
        result["value"] = val
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
