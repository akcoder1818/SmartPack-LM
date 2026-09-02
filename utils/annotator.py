"""
SmartPack-LM: Visual Evidence Annotator
Draws color-coded statutory bounding boxes and declaration labels onto package imagery.
Generates audit evidence for the Web UI and PDF inspection reports.
"""
import os
import cv2
import numpy as np

def generate_evidence_image(original_image_path, extracted_fields, rule_evaluations, output_path):
    """
    Generates an annotated visual inspection evidence image with labeled bounding boxes:
    - Green Box: Fully Compliant Declaration (PASS)
    - Orange Box: Declaration Needs Review (REVIEW)
    - Red Markers: Non-compliant / Missing Declarations
    """
    if not original_image_path or not os.path.exists(original_image_path):
        return None

    img = cv2.imread(original_image_path)
    if img is None:
        return None

    h, w = img.shape[:2]
    annotated = img.copy()

    # Color palette (BGR for OpenCV)
    COLOR_PASS = (60, 179, 113)     # Emerald Green
    COLOR_REVIEW = (0, 165, 255)    # Amber / Orange
    COLOR_FAIL = (45, 52, 235)      # Red
    COLOR_BG = (20, 24, 33)         # Deep Navy Background for Labels

    # Map rule evaluations to dict for quick status lookup
    rule_status_map = {r.get("field"): r.get("status") for r in rule_evaluations}

    # Draw bounding boxes for detected fields
    field_labels = {
        "mrp": "MRP (Rule 6.1.e)",
        "net_quantity": "Net Qty (Rule 6.1.c)",
        "manufacturing_date": "Mfg Date (Rule 6.1.d)",
        "best_before": "Best Before (Rule 6.1.d)",
        "consumer_care": "Consumer Care (Rule 6.1.f)",
        "country_of_origin": "Origin (Rule 6.1.g)",
        "manufacturer": "Manufacturer (Rule 6.1.a)",
        "product_name": "Commodity Name (Rule 6.1.b)",
        "unit_sale_price": "USP (Rule 6.1.h)"
    }

    boxes_drawn = 0

    for field_name, field_data in extracted_fields.items():
        bbox = field_data.get("bbox")
        val = field_data.get("value")
        if not bbox or not val:
            continue

        x, y, bw, bh = bbox
        # Ensure within image bounds
        x = max(5, min(x, w - 10))
        y = max(5, min(y, h - 10))
        bw = max(20, min(bw, w - x - 5))
        bh = max(15, min(bh, h - y - 5))

        status = rule_status_map.get(field_name, "PASS")
        if status == "PASS":
            box_color = COLOR_PASS
            status_text = "PASS"
        elif status == "REVIEW":
            box_color = COLOR_REVIEW
            status_text = "REVIEW"
        else:
            box_color = COLOR_FAIL
            status_text = "FAIL"

        # Draw main bounding box with rounded aesthetic thickness
        cv2.rectangle(annotated, (x, y), (x + bw, y + bh), box_color, 2)

        # Label tag above box
        label_title = field_labels.get(field_name, field_name.upper())
        tag_text = f"{label_title}: {status_text}"
        
        # Calculate label size
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.45
        thickness = 1
        (text_w, text_h), baseline = cv2.getTextSize(tag_text, font, font_scale, thickness)

        # Tag background position
        tag_y1 = max(0, y - text_h - 8)
        tag_y2 = y
        tag_x1 = x
        tag_x2 = min(w, x + text_w + 10)

        # Draw filled rectangle for tag
        cv2.rectangle(annotated, (tag_x1, tag_y1), (tag_x2, tag_y2), box_color, -1)
        # White text inside tag
        cv2.putText(
            annotated,
            tag_text,
            (tag_x1 + 5, tag_y2 - 4),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA
        )
        boxes_drawn += 1

    # If no specific boxes were available (e.g. general OCR lines), add summary header banner
    banner_height = 45
    banner = np.zeros((banner_height, w, 3), dtype=np.uint8)
    banner[:] = (15, 23, 42) # Slate Dark

    cv2.putText(
        banner,
        "SMARTPACK-LM | LEGAL METROLOGY AI EVIDENCE MAP",
        (15, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    combined = np.vstack([banner, annotated])

    # Save output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, combined)
    return output_path
