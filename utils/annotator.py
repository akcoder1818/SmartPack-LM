"""
SmartPack-LM: Visual Evidence Annotator
Draws color-coded statutory bounding boxes and declaration labels onto package imagery.
Generates audit evidence for the Web UI and PDF inspection reports.
"""
import os
import cv2
import numpy as np

def draw_statutory_boxes(img, extracted_fields, rule_status_map, field_labels, target_source=None, original_image_path=None):
    """
    Draws bounding boxes onto an image, strictly filtering fields so that
    front tokens are drawn only on front imagery, and back tokens are drawn only on back imagery.
    """
    h, w = img.shape[:2]
    annotated = img.copy()
    boxes_drawn = 0

    COLOR_PASS = (60, 179, 113)     # Emerald Green
    COLOR_REVIEW = (0, 165, 255)    # Amber / Orange
    COLOR_FAIL = (45, 52, 235)      # Red

    # Check if multiple distinct sources exist across extracted fields
    has_back_fields = any(
        isinstance(v, dict) and (v.get("source") == "back" or (v.get("image_path") and "back" in os.path.basename(v.get("image_path")).lower()))
        for v in extracted_fields.values()
    )
    has_front_fields = any(
        isinstance(v, dict) and (v.get("source") == "front" or (v.get("image_path") and "front" in os.path.basename(v.get("image_path")).lower()))
        for v in extracted_fields.values()
    )
    is_multi_source = has_back_fields and has_front_fields

    for field_name, field_data in extracted_fields.items():
        if not isinstance(field_data, dict):
            continue
        bbox = field_data.get("bbox")
        val = field_data.get("value")
        if not bbox or not val or len(bbox) < 4:
            continue

        field_source = field_data.get("source")
        field_img = field_data.get("image_path")

        # Source-based filtering:
        if target_source == "front":
            # Strict Rule F: No back-image coordinates may be drawn onto the front image
            if field_source and field_source.lower() == "back":
                continue
            if field_img and "back" in os.path.basename(field_img).lower():
                continue
            # Rule 6: If source metadata is unavailable in a multi-image inspection, do NOT guess
            if is_multi_source and field_source is None and field_img is None:
                continue

        elif target_source == "back":
            # Strict Rule G: No front-image coordinates may be drawn onto the back image
            if field_source and field_source.lower() == "front":
                continue
            if field_img and "front" in os.path.basename(field_img).lower():
                continue
            # Rule 6: If source metadata is unavailable in a multi-image inspection, do NOT guess
            if is_multi_source and field_source is None and field_img is None:
                continue

        elif original_image_path and field_img:
            try:
                if os.path.abspath(field_img) != os.path.abspath(original_image_path):
                    continue
            except Exception:
                pass

        x, y, bw, bh = bbox[:4]
        # Ensure within image bounds
        x = max(5, min(int(x), w - 10))
        y = max(5, min(int(y), h - 10))
        bw = max(20, min(int(bw), w - x - 5))
        bh = max(15, min(int(bh), h - y - 5))

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

    return annotated, boxes_drawn

def generate_evidence_image(original_image_path, extracted_fields, rule_evaluations, output_path, image_source=None, secondary_image_path=None):
    """
    Generates an annotated visual inspection evidence image with labeled bounding boxes.
    - If secondary_image_path is provided, annotates both images with their respective
      coordinates and renders a dual-panel evidence map.
    - If a single image is provided, annotates that image, drawing only tokens matching its source.
    """
    if not original_image_path or not os.path.exists(original_image_path):
        return None

    rule_status_map = {r.get("field"): r.get("status") for r in rule_evaluations}

    # Map rule evaluations to dict for quick status lookup
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

    # Determine source for primary image
    p_source = image_source
    if p_source is None:
        p_name = os.path.basename(original_image_path).lower()
        if "front" in p_name:
            p_source = "front"
        elif "back" in p_name:
            p_source = "back"

    img_primary = cv2.imread(original_image_path)
    if img_primary is None:
        return None

    # Handle Dual-Image Rendering when secondary_image_path is provided
    if secondary_image_path and os.path.exists(secondary_image_path):
        s_name = os.path.basename(secondary_image_path).lower()
        s_source = "front" if "front" in s_name else ("back" if "back" in s_name else None)
        img_secondary = cv2.imread(secondary_image_path)

        if img_secondary is not None:
            # Order panels as [Front, Back]
            if p_source == "front" or s_source == "back":
                front_path, front_img, front_src = original_image_path, img_primary, "front"
                back_path, back_img, back_src = secondary_image_path, img_secondary, "back"
            else:
                front_path, front_img, front_src = secondary_image_path, img_secondary, "front"
                back_path, back_img, back_src = original_image_path, img_primary, "back"

            ann_front, _ = draw_statutory_boxes(front_img, extracted_fields, rule_status_map, field_labels, target_source=front_src, original_image_path=front_path)
            ann_back, _ = draw_statutory_boxes(back_img, extracted_fields, rule_status_map, field_labels, target_source=back_src, original_image_path=back_path)

            # Match heights for horizontal concatenation
            target_h = max(ann_front.shape[0], ann_back.shape[0])
            if ann_front.shape[0] != target_h:
                scale_f = target_h / ann_front.shape[0]
                ann_front = cv2.resize(ann_front, (int(ann_front.shape[1] * scale_f), target_h), interpolation=cv2.INTER_AREA)
            if ann_back.shape[0] != target_h:
                scale_b = target_h / ann_back.shape[0]
                ann_back = cv2.resize(ann_back, (int(ann_back.shape[1] * scale_b), target_h), interpolation=cv2.INTER_AREA)

            header_h = 30
            hdr_front = np.zeros((header_h, ann_front.shape[1], 3), dtype=np.uint8)
            hdr_front[:] = (35, 45, 60)
            cv2.putText(hdr_front, "FRONT LABEL", (15, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            panel_front = np.vstack([hdr_front, ann_front])

            hdr_back = np.zeros((header_h, ann_back.shape[1], 3), dtype=np.uint8)
            hdr_back[:] = (35, 45, 60)
            cv2.putText(hdr_back, "BACK / STATUTORY LABEL", (15, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            panel_back = np.vstack([hdr_back, ann_back])

            sep = np.zeros((panel_front.shape[0], 6, 3), dtype=np.uint8)
            sep[:] = (80, 80, 80)
            combined_panels = np.hstack([panel_front, sep, panel_back])

            total_w = combined_panels.shape[1]
            banner_height = 45
            banner = np.zeros((banner_height, total_w, 3), dtype=np.uint8)
            banner[:] = (15, 23, 42) # Slate Dark
            cv2.putText(
                banner,
                "SMARTPACK-LM | LEGAL METROLOGY AI EVIDENCE MAP (DUAL LABEL)",
                (15, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )
            final_img = np.vstack([banner, combined_panels])
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cv2.imwrite(output_path, final_img)
            return output_path

    # Single Image Annotation
    annotated, _ = draw_statutory_boxes(
        img_primary, extracted_fields, rule_status_map, field_labels,
        target_source=p_source, original_image_path=original_image_path
    )

    w = annotated.shape[1]
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
