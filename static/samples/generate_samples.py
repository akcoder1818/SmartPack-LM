"""
SmartPack-LM: Sample Product Label Generator
Generates realistic sample label imagery for 1-click Hackathon presentation presets.
"""
import os
from PIL import Image, ImageDraw, ImageFont

SAMPLE_DIR = os.path.dirname(os.path.abspath(__file__))

def create_label(filename, header_bg, title, lines, sub_box=None):
    width, height = 800, 1000
    img = Image.new("RGB", (width, height), color=(250, 250, 252))
    draw = ImageDraw.Draw(img)

    # Border
    draw.rectangle([(10, 10), (width - 10, height - 10)], outline=(200, 205, 215), width=3)

    # Header Panel
    draw.rectangle([(10, 10), (width - 10, 140)], fill=header_bg)
    draw.text((30, 45), title, fill=(255, 255, 255))

    # Content Lines
    y = 170
    for line in lines:
        if line.startswith("---"):
            draw.line([(30, y + 5), (width - 30, y + 5)], fill=(220, 225, 230), width=2)
            y += 20
            continue
            
        draw.text((35, y), line, fill=(25, 30, 40))
        y += 45

    # Secondary Statutory Box (e.g. MRP & PKD block)
    if sub_box:
        box_y = y + 10
        draw.rectangle([(30, box_y), (width - 30, box_y + 160)], outline=(120, 130, 150), width=2, fill=(240, 243, 248))
        by = box_y + 15
        for sline in sub_box:
            draw.text((45, by), sline, fill=(10, 15, 25))
            by += 32

    # Barcode representation
    draw.rectangle([(width - 240, height - 90), (width - 40, height - 30)], outline=(50, 50, 50), width=1, fill=(255, 255, 255))
    for bx in range(width - 230, width - 50, 6):
        draw.line([(bx, height - 85), (bx, height - 35)], fill=(0, 0, 0), width=2)

    output_path = os.path.join(SAMPLE_DIR, filename)
    img.save(output_path, quality=95)
    print(f"Generated sample label: {output_path}")
    return output_path

def generate_all():
    # 1. Compliant Sample (FMCG Biscuit)
    create_label(
        "sample_compliant_biscuit.jpg",
        header_bg=(15, 75, 150),
        title="BRITANNIA GOOD DAY BUTTER COOKIES (250g)",
        lines=[
            "Generic Name: Butter Cookies / Biscuits",
            "Manufactured by: Britannia Industries Ltd.",
            "Address: Plot No. 12, Industrial Area, Sector 5, Haridwar, Uttarakhand - 249403, India",
            "Country of Origin: India",
            "---",
            "Net Weight: 250 g",
            "Date of Mfg: 08/2026",
            "Best Before: 9 Months from date of packaging",
            "Dimensions: 18 cm x 6 cm x 6 cm",
            "---",
            "Consumer Care Cell: Toll Free 1800-425-4444",
            "Email: feedback@britannia.co.in",
            "Postal Address: Britannia Consumer Care, Bangalore - 560001"
        ],
        sub_box=[
            "MAXIMUM RETAIL PRICE (MRP): Rs. 45.00",
            "(inclusive of all taxes)",
            "Unit Sale Price: Rs. 0.18 / g",
            "Batch No: BND2608A"
        ]
    )

    # 2. Non-Compliant Sample (Edible Oil)
    # Violations: Missing Country of Origin, Non-standard unit (2 lbs), Missing Consumer care, Missing taxes clause
    create_label(
        "sample_noncompliant_oil.jpg",
        header_bg=(180, 40, 40),
        title="SUNFLOW PURE REFINED SUNFLOWER OIL",
        lines=[
            "Generic Name: Edible Refined Sunflower Oil",
            "Marketed by: Sunflow Agro Products, Survey 44, Pune Road",
            "---",
            "Net Contents: 2 lbs",
            "Date of Packaging: 07/2026",
            "Best Before: 12 months",
            "---",
            "[Notice: Country of origin declaration absent]",
            "[Notice: Consumer grievance contact missing]"
        ],
        sub_box=[
            "MRP: 199",
            "Batch: SF-902",
            "For culinary use only."
        ]
    )

    # 3. Needs Review Sample (Detergent Powder)
    # Violations: Incomplete date (year only), Missing 'incl. of taxes' on MRP, incomplete address (no PIN)
    create_label(
        "sample_review_detergent.jpg",
        header_bg=(210, 130, 20),
        title="SURFMAX ADVANCED LAUNDRY DETERGENT POWDER",
        lines=[
            "Generic Name: Detergent Powder",
            "Manufactured by: CleanChem Chemical Industries",
            "Address: Plot 89, GIDC Estate, Gujarat",
            "Country of Origin: India",
            "---",
            "Net Qty: 1 kg",
            "Pkg Date: 2026",
            "---",
            "Customer Feedback: helpline@surfmaxindia.com"
        ],
        sub_box=[
            "MRP ₹ 140",
            "Batch No: DET-442"
        ]
    )

if __name__ == "__main__":
    generate_all()
