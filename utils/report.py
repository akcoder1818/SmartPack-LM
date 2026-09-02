"""
SmartPack-LM: Official Multilingual Inspection Report Generator
Generates publication-quality PDF reports in English, Hindi, Tamil, Kannada, Telugu, and Malayalam.
Includes Unicode font registration (Nirmala UI), executive summary, evidence snapshots, audit matrix, and statutory disclaimer.
"""
import os
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from utils.translator import t, get_translated_status, get_translated_badge

_FONTS_REGISTERED = False
_INDIC_FONT_AVAILABLE = False

def register_indic_fonts():
    """Registers Unicode TrueType fonts (Nirmala UI) for rendering Indian scripts in PDF."""
    global _FONTS_REGISTERED, _INDIC_FONT_AVAILABLE
    if _FONTS_REGISTERED:
        return _INDIC_FONT_AVAILABLE

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate_paths = [
        # Local bundled static/fonts
        (os.path.join(base_dir, "static", "fonts", "Nirmala.ttf"), os.path.join(base_dir, "static", "fonts", "Nirmalab.ttf")),
        # Windows system fonts
        (r"C:\Windows\Fonts\Nirmala.ttf", r"C:\Windows\Fonts\Nirmalab.ttf"),
        # Linux standard paths
        ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf")
    ]

    for reg_path, bold_path in candidate_paths:
        if os.path.exists(reg_path):
            try:
                pdfmetrics.registerFont(TTFont("IndicFont", reg_path))
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont("IndicFont-Bold", bold_path))
                else:
                    pdfmetrics.registerFont(TTFont("IndicFont-Bold", reg_path))
                _INDIC_FONT_AVAILABLE = True
                print(f"[SmartPack-LM] Registered Indic Unicode Font: {reg_path}")
                break
            except Exception as e:
                print(f"[SmartPack-LM] Font registration failed for {reg_path}: {e}")

    _FONTS_REGISTERED = True
    return _INDIC_FONT_AVAILABLE

def generate_pdf_report(inspection_data, output_path=None, lang="en"):
    """
    Generates a formal Legal Metrology Compliance Inspection Report in the specified language.
    Supports 'en', 'hi', 'ta', 'kn', 'te', 'ml'.
    Returns: filepath if output_path is provided, or io.BytesIO buffer.
    """
    buffer = io.BytesIO() if output_path is None else open(output_path, "wb")
    
    doc = SimpleDocTemplate(
        buffer if output_path is not None else buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    # Check font registration
    indic_available = register_indic_fonts()
    use_indic = (lang != "en") and indic_available

    font_regular = "IndicFont" if use_indic else "Helvetica"
    font_bold = "IndicFont-Bold" if use_indic else "Helvetica-Bold"
    font_oblique = "IndicFont" if use_indic else "Helvetica-Oblique"

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'GovTitle',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=12,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#0A2540')
    )

    subtitle_style = ParagraphStyle(
        'GovSubtitle',
        parent=styles['Normal'],
        fontName=font_regular,
        fontSize=8.5,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#475569')
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName=font_bold,
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=6
    )

    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName=font_regular,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#1E293B')
    )

    cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )

    badge_pass = ParagraphStyle(
        'BadgePass',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=8,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#065F46')
    )

    badge_review = ParagraphStyle(
        'BadgeReview',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=8,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#92400E')
    )

    badge_fail = ParagraphStyle(
        'BadgeFail',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=8,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#991B1B')
    )

    disclaimer_style = ParagraphStyle(
        'DisclaimerText',
        parent=styles['Normal'],
        fontName=font_oblique,
        fontSize=7,
        leading=9.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#64748B')
    )

    elements = []

    # 1. Official Header in Target Language
    elements.append(Paragraph(t("gov_india", lang=lang), subtitle_style))
    elements.append(Paragraph(t("ministry_name", lang=lang), subtitle_style))
    elements.append(Paragraph(t("department_name", lang=lang), subtitle_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(t("pdf_report_title", lang=lang), title_style))
    elements.append(Paragraph(t("pdf_report_subtitle", lang=lang), subtitle_style))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0A2540'), spaceAfter=8))

    # 2. Inspection Overview Card
    insp_id = inspection_data.get("id", "N/A")
    timestamp = inspection_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    score = float(inspection_data.get("compliance_score", 0.0))
    status_raw = inspection_data.get("overall_status", "REVIEW")
    status_translated = get_translated_status(status_raw, lang=lang)
    prod_name = inspection_data.get("product_name", "Packaged Commodity")
    manufacturer = inspection_data.get("manufacturer", "Not Specified")

    ref_str = f"SP-LM-2026-{insp_id:04d}" if isinstance(insp_id, int) else f"SP-LM-{insp_id}"

    meta_table_data = [
        [
            Paragraph(f"<b>{t('th_id', lang=lang)}:</b> {ref_str}", cell_style),
            Paragraph(f"<b>{t('th_timestamp', lang=lang)}:</b> {timestamp}", cell_style)
        ],
        [
            Paragraph(f"<b>{t('th_product', lang=lang)}:</b> {prod_name}", cell_style),
            Paragraph(f"<b>{t('th_manufacturer', lang=lang)}:</b> {manufacturer[:45]}", cell_style)
        ],
        [
            Paragraph(f"<b>{t('compliance_index', lang=lang)}:</b> <b>{score}%</b>", cell_style),
            Paragraph(f"<b>{t('th_status', lang=lang)}:</b> <b>{status_translated}</b>", cell_bold)
        ]
    ]

    meta_table = Table(meta_table_data, colWidths=[260, 260])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 10))

    # 3. Visual Evidence Section
    evidence_path = inspection_data.get("evidence_image_path")
    if not evidence_path or not os.path.exists(evidence_path):
        img_paths = inspection_data.get("image_paths", {})
        evidence_path = img_paths.get("front") or img_paths.get("back")

    if evidence_path and os.path.exists(evidence_path):
        try:
            elements.append(Paragraph(t("pdf_section_1", lang=lang), section_heading))
            img_flow = Image(evidence_path, width=320, height=150, kind='proportional')
            img_flow.hAlign = 'CENTER'
            elements.append(img_flow)
            elements.append(Spacer(1, 10))
        except Exception as e:
            print(f"[SmartPack-LM] Error embedding evidence image: {e}")

    # 4. Statutory Checklist Table
    elements.append(Paragraph(t("pdf_section_2", lang=lang), section_heading))
    
    extracted_data = inspection_data.get("extracted_data", {})
    rules_eval = extracted_data.get("rule_evaluations", [])

    table_rows = [
        [
            Paragraph(f"<b>{t('th_rule', lang=lang)}</b>", cell_bold),
            Paragraph(f"<b>{t('th_declaration', lang=lang)}</b>", cell_bold),
            Paragraph(f"<b>{t('th_declaration', lang=lang)} ({t('th_timestamp', lang=lang)[:4]})</b>", cell_bold),
            Paragraph(f"<b>{t('th_compliance', lang=lang)}</b>", cell_bold)
        ]
    ]

    field_translations = {
        "manufacturer": t("rule_a_summary", lang=lang)[:35] + "...",
        "product_name": t("rule_b_summary", lang=lang)[:35] + "...",
        "net_quantity": t("rule_c_summary", lang=lang)[:35] + "...",
        "manufacturing_date": t("rule_d_summary", lang=lang)[:35] + "...",
        "best_before": "Best Before / Expiry",
        "mrp": t("rule_e_summary", lang=lang)[:35] + "...",
        "consumer_care": t("rule_f_summary", lang=lang)[:35] + "...",
        "country_of_origin": t("rule_g_summary", lang=lang)[:35] + "...",
        "unit_sale_price": "Unit Sale Price (USP)",
        "dimensions": "Dimensions / Size"
    }

    if not rules_eval:
        fields_map = [
            ("Rule 6(1)(a)", field_translations.get("manufacturer"), inspection_data.get("manufacturer")),
            ("Rule 6(1)(b)", field_translations.get("product_name"), inspection_data.get("product_name")),
            ("Rule 6(1)(c)", field_translations.get("net_quantity"), inspection_data.get("net_quantity")),
            ("Rule 6(1)(d)", field_translations.get("manufacturing_date"), inspection_data.get("manufacturing_date")),
            ("Rule 6(1)(e)", field_translations.get("mrp"), inspection_data.get("mrp")),
            ("Rule 6(1)(f)", field_translations.get("consumer_care"), inspection_data.get("consumer_care")),
            ("Rule 6(1)(g)", field_translations.get("country_of_origin"), inspection_data.get("country_of_origin"))
        ]
        for ref, title, val in fields_map:
            val_display = val if val and val != "Not Detected" else t("not_detected", lang=lang)
            st_text = "PASS" if val and val != "Not Detected" else "FAIL"
            b_style = badge_pass if st_text == "PASS" else badge_fail
            table_rows.append([
                Paragraph(ref, cell_style),
                Paragraph(str(title), cell_style),
                Paragraph(str(val_display)[:40], cell_style),
                Paragraph(get_translated_badge(st_text, lang=lang), b_style)
            ])
    else:
        for r in rules_eval:
            r_ref = r.get("rule_reference", "").split(" of ")[0] or r.get("rule_id", "")
            f_name = r.get("field", "")
            r_title = field_translations.get(f_name, r.get("title", ""))
            r_val = r.get("extracted_value") or t("not_detected", lang=lang)
            r_status = r.get("status", "NOT_DETECTED")
            
            if r_status == "PASS":
                b_style = badge_pass
            elif r_status == "REVIEW":
                b_style = badge_review
            else:
                b_style = badge_fail

            table_rows.append([
                Paragraph(r_ref, cell_style),
                Paragraph(str(r_title), cell_style),
                Paragraph(str(r_val)[:42], cell_style),
                Paragraph(get_translated_badge(r_status, lang=lang), b_style)
            ])

    rule_table = Table(table_rows, colWidths=[90, 160, 200, 70])
    rule_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#94A3B8')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(rule_table)
    elements.append(Spacer(1, 10))

    # 5. Detected Issues
    detected_issues = inspection_data.get("detected_issues", [])
    if detected_issues:
        elements.append(Paragraph(t("pdf_section_3", lang=lang), section_heading))
        issue_items = []
        for idx, iss in enumerate(detected_issues, 1):
            desc = iss.get("description", "")
            sev = iss.get("severity", "MEDIUM")
            ref = iss.get("rule_reference", "")
            issue_items.append([
                Paragraph(f"<b>{idx}. [{sev}] {iss.get('title', '')}</b>: {desc}<br/><i>{ref}</i>", cell_style)
            ])

        issue_table = Table(issue_items, colWidths=[520])
        issue_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF2F2')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#FCA5A5')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FECACA')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(issue_table)
        elements.append(Spacer(1, 10))

    # 6. Officer Signature Block
    sig_data = [
        [
            Paragraph(f"<b>{t('pdf_ai_assessment', lang=lang)}</b><br/>SmartPack-LM v2026.1<br/>Engine: OCR + Legal Metrology Rules", cell_style),
            Paragraph(f"<b>{t('pdf_officer_sign', lang=lang)}</b><br/>{t('pdf_officer_name', lang=lang)}<br/>{t('pdf_officer_seal', lang=lang)}", cell_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[260, 260])
    sig_table.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(sig_table)
    elements.append(Spacer(1, 10))

    # Statutory Disclaimer Box
    elements.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor('#CBD5E1'), spaceAfter=6))
    elements.append(Paragraph(t("pdf_disclaimer", lang=lang), disclaimer_style))

    doc.build(elements)

    if output_path is not None:
        buffer.close()
        return output_path
    else:
        buffer.seek(0)
        return buffer
