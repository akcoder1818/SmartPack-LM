# SmartPack-LM: AI-Assisted Packaged Commodity Compliance Inspection System

[![SIH 2026](https://img.shields.io/badge/Smart%20India%20Hackathon-2026-orange.svg)](https://www.sih.gov.in/)
[![Problem Statement](https://img.shields.io/badge/Problem%20ID-SIH26034-blue.svg)](#)
[![Ministry](https://img.shields.io/badge/Ministry-Consumer%20Affairs%2C%20Food%20%26%20Public%20Distribution-green.svg)](#)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-yellow.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

> **Software System to check compliance of Packaged Commodities under Legal Metrology (Packaged Commodities) Rules, 2011 by scanning products, images and labels.**

---

## 📌 Statutory Disclaimer
> [!IMPORTANT]
> **Decision Support Notice:** SmartPack-LM is an AI-assisted inspection support platform designed to assist Legal Metrology officers and market surveillance teams. It **does NOT** make a final legal determination. All final legal proceedings, compounding of offenses, and statutory actions remain exclusively under the authority of designated Legal Metrology Officers under the *Legal Metrology Act, 2009*.

---

## 🚀 Key Features

1. **Dual Label Ingestion**: Supports simultaneous upload of Front & Back label images, or multi-panel scans.
2. **Multi-Tier OCR & Preprocessing**:
   - OpenCV Image Processing (CLAHE contrast equalization, bilateral denoising, adaptive Otsu binarization).
   - Multi-Tier OCR fallback: `PaddleOCR` $\rightarrow$ `Tesseract (pytesseract)` $\rightarrow$ `EasyOCR` $\rightarrow$ `Intelligent Synthetic Fallback`.
3. **Statutory Declaration Extraction**:
   - **Rule 6(1)(a)**: Name & Address of Manufacturer / Packer / Importer with 6-digit postal PIN code verification.
   - **Rule 6(1)(b)**: Generic / Common Name of the commodity.
   - **Rule 6(1)(c)**: Net Quantity in standard SI metric units ($g, kg, ml, l, m, cm, N$). Flags non-standard units (e.g. *dozen, lbs, oz*).
   - **Rule 6(1)(d)**: Month & Year of Manufacture / Pre-packing ($MM/YYYY$) and Best Before / Expiry dates.
   - **Rule 6(1)(e)**: Maximum Retail Price (MRP) in ₹/Rs. with mandatory `(inclusive of all taxes)` declaration.
   - **Rule 6(1)(f)**: Consumer Care Cell details (Toll-Free/Telephone number, Email, Address).
   - **Rule 6(1)(g)**: Country of Origin declaration for domestic and imported goods.
   - **Rule 6(1)(h)**: Unit Sale Price (USP) for multi-unit or bulk packages ($> 1 kg/L$).
   - **Rule 6(1)(i)**: Dimensions & Size specifications where applicable.
4. **External JSON Rule Engine (`rules/legal_metrology_rules.json`)**: Configurable rule specifications with severity weighting without altering Python code.
5. **Visual Evidence Bounding Box Map**: Automatically draws color-coded bounding boxes on the label images (Green for Compliant, Orange for Review, Red for Violations).
6. **Automated Official PDF Inspection Report**: High-resolution, printable PDF generated via ReportLab complete with inspection metadata, embedded evidence images, statutory audit matrix, and legal disclaimers.
7. **GovTech Analytics Dashboard**: SQLite database persistence with real-time KPI metrics, violation breakdown charts, and searchable audit trail.
8. **1-Click Evaluation Presets**: Pre-packaged sample commodity scenarios (Compliant Biscuit, Non-compliant Edible Oil, Review-required Detergent) for fail-safe hackathon demonstrations.

---

## 📂 Project Architecture

```
SmartPack-LM/
│
├── app.py                      # Flask Application entrypoint & routes
├── requirements.txt            # Python dependencies
├── Procfile                    # Render / Heroku deployment config
├── .gitignore                  # Git ignore rules
├── README.md                   # Complete documentation & user guide
├── smartpack.db                # SQLite database (auto-created on start)
│
├── rules/
│   └── legal_metrology_rules.json  # Declarative Legal Metrology rules
│
├── utils/
│   ├── __init__.py             # Package initializer
│   ├── ocr.py                  # Multi-Tier OCR & OpenCV preprocessing
│   ├── extractor.py            # Regex & NLP statutory field extractor
│   ├── compliance.py           # Legal Metrology compliance validator
│   ├── annotator.py            # OpenCV bounding-box evidence generator
│   ├── database.py             # SQLite database CRUD & dashboard metrics
│   └── report.py               # ReportLab official PDF report generator
│
├── templates/
│   ├── base.html               # GovTech layout, navbar & footer
│   ├── index.html              # Drag-and-drop dual label scanner & presets
│   ├── result.html             # Audit scorecard, evidence map & matrix
│   ├── dashboard.html          # Analytics charts & searchable audit log
│   └── rules.html              # Interactive Legal Metrology rules catalog
│
├── static/
│   ├── css/
│   │   └── style.css           # GovTech styling (Navy, Saffron, Emerald)
│   ├── js/
│   │   └── app.js              # Dropzone handlers, preview & progress animation
│   └── samples/                # Sample test images & generator script
│       ├── generate_samples.py
│       ├── sample_compliant_biscuit.jpg
│       ├── sample_noncompliant_oil.jpg
│       └── sample_review_detergent.jpg
│
└── uploads/                    # User scans & generated evidence artifacts
```

---

## ⚙️ Installation & Local Setup

### 1. Prerequisites
- Python 3.10 or 3.11 installed.
- (Optional) Tesseract-OCR if you wish to use local Tesseract binary.

### 2. Clone / Navigate to Project Directory
```bash
cd SmartPack-LM
```

### 3. Create & Activate Virtual Environment
```bash
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

*(Optional: If you want PaddleOCR or EasyOCR support, you can also run `pip install paddlepaddle paddleocr` or `pip install easyocr`)*.

---

## ▶️ Running the Application

Start the Flask server:
```bash
python app.py
```

The portal will start on:
👉 **`http://127.0.0.1:5000`**

Open your web browser and navigate to `http://127.0.0.1:5000`.

---

## 🧪 Testing & Demonstration Guide

### Quick 1-Click Evaluation Presets
On the home page, click on any of the pre-loaded demo buttons:
1. 🟢 **Sample 1: FMCG Biscuit Pack (100% Compliant)**
   - *Expected Outcome*: Score 100%, Status `COMPLIANT`. All Rule 6(1) declarations present with standard SI units and full taxes declaration.
2. 🔴 **Sample 2: Edible Oil Bottle (Non-Compliant)**
   - *Expected Outcome*: Score < 50%, Status `NON-COMPLIANT`. Flags missing Country of Origin, non-standard unit (`2 lbs`), missing consumer care helpline, and missing tax clause.
3. 🟡 **Sample 3: Laundry Detergent (Needs Review)**
   - *Expected Outcome*: Score ~70%, Status `NEEDS REVIEW`. Flags partial date format (`2026` year only) and missing `inclusive of all taxes` note on MRP.

### Custom Product Scan
1. Drag and drop a Front Label image and (optionally) a Back/Declarations panel.
2. Click **"Analyze Product Compliance"**.
3. View the instant compliance score, interactive visual evidence map with bounding boxes, and click **"Download PDF Report"** to get an official printable audit sheet.

---

## ☁️ Deployment Instructions

### Deploy to Render
1. Push the repository to GitHub.
2. Log into [Render.com](https://render.com) and click **New + $\rightarrow$ Web Service**.
3. Connect your GitHub repository.
4. Set the following settings:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Click **Deploy Web Service**.

---

## 📜 Regulatory Reference
- **The Legal Metrology Act, 2009** (Act No. 1 of 2010).
- **The Legal Metrology (Packaged Commodities) Rules, 2011** (GSR 202(E) as amended).
- Department of Consumer Affairs, Ministry of Consumer Affairs, Food and Public Distribution, Government of India.
