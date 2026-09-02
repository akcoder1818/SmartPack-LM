import json
import os

BASE_DIR = rC:\Users\ASUS\.gemini\antigravity\scratch\SmartPack-LM
os.makedirs(os.path.join(BASE_DIR, rules), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, utils), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, templates), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, static, css), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, static, js), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, static, samples), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, uploads), exist_ok=True)

# 1. rules/legal_metrology_rules.json
rules_data = {
  version: 2026.1,
  regulatory_authority: Ministry of Consumer Affairs, Food & Public Distribution, Department of Consumer Affairs, Government of India,
  source_legislation: Legal Metrology Act, 2009 & Legal Metrology (Packaged Commodities) Rules, 2011 (as amended),
  effective_date: 2011-04-01,
  rules: [
    {
      id: LMR_RULE_6_1_A_MANUFACTURER,
      field: manufacturer,
      title: Name & Address of Manufacturer / Packer / Importer,
      description: The name and complete address of the manufacturer, or where the manufacturer is not the packer, the name and address of the manufacturer and packer, or in case of an imported package, the name and address of the importer.,
      required: True,
      applicability: all_packaged_commodities,
      severity: CRITICAL,
      rule_reference: Rule 6(1)(a) of Legal Metrology (Packaged Commodities) Rules, 2011,
      validation_criteria: {
        keywords: [manufactured by, mfg by, packed by, pkd by, marketed by, imported by, mktd by, mfd by],
        min_characters: 8,
        address_indicators: [pincode, pin, road, street, dist, state, nagar, plot, sector, industrial area, pvt, ltd]
      },
      guidance: Every pre-packaged commodity must clearly disclose the legal entity responsible along with complete address including PIN code.
    },
    {
      id: LMR_RULE_6_1_B_GENERIC_NAME,
      field: product_name,
      title: Generic / Common Name of the Commodity,
      description: The common or generic names of the commodity contained in the package and in case of packages with more than one product, the name and number or quantity of each product.,
      required: True,
      applicability: all_packaged_commodities,
      severity: HIGH,
      rule_reference: Rule 6(1)(b) of Legal Metrology (Packaged Commodities) Rules, 2011,
      validation_criteria: {
        min_characters: 3,
        reject_pure_numeric: True
      },
      guidance: Declaration of generic name enables consumers to identify the exact nature of the product without ambiguity.
    },
    {
      id: LMR_RULE_6_1_C_NET_QUANTITY,
      field: net_quantity,
      title: Net Quantity Declaration in Standard Units,
      description: The net quantity, in terms of the standard unit of weight or measure, of the commodity contained in the package, or where the commodity is packed or sold by number, the number of the commodity contained in the package.,
      required: True,
      applicability: all_packaged_commodities,
      severity: CRITICAL,
      rule_reference: Rule 6(1)(c) & Rule 11 of Legal Metrology (Packaged Commodities) Rules, 2011,
      validation_criteria: {
        valid_units: [g, gm, gms, gram, grams, kg, kilogram, kilograms, ml, millilitre, l, ltr, litre, litres, m, metre, cm, centimetre, mm, units, u, pcs, pieces, n, count],
        non_standard_units: [dozen, gross, tola, seer, pound, lbs, oz, ounce, pao],
        keywords: [net weight, net wt, net qty, net quantity, net volume, net content, net contents]
      },
      guidance: Net quantity must be declared using SI/Metric standard units (kg, g, l, ml, m, cm or N). Non-standard units (such as dozen, lbs) are non-compliant.
    },
    {
      id: LMR_RULE_6_1_D_MFG_DATE,
      field: manufacturing_date,
      title: Month and Year of Manufacture / Packing,
      description: The month and year in which the commodity is manufactured or pre-packed or imported. For packages containing commodities which may become unfit for consumption, 'Best Before' or 'Use By' date must also be mentioned.,
      required: True,
      applicability: all_packaged_commodities,
      severity: HIGH,
      rule_reference: Rule 6(1)(d) of Legal Metrology (Packaged Commodities) Rules, 2011,
      validation_criteria: {
        keywords: [mfg date, mfg dt, mfd, date of mfg, date of packaging, pkd date, pkd dt, packed on, mfg., pkd.],
        valid_date_formats: [MM/YYYY, MM/YY, MMM/YYYY, MMM-YY, DD/MM/YYYY, YYYY-MM-DD]
      },
      guidance: Declaration of month and year of packaging or manufacturing is compulsory to protect consumer interest.
    },
    {
      id: LMR_RULE_6_1_D_BEST_BEFORE,
      field: best_before,
      title: Best Before / Expiry / Use By Date,
      description: Declaration of 'Best Before' date or expiry date for commodities which may degrade over time.,
      required: False,
      applicability: perishable_and_food_commodities,
      severity: MEDIUM,
      rule_reference: Rule 6(1)(d) Proviso of Legal Metrology (Packaged Commodities) Rules, 2011,
      validation_criteria: {
        keywords: [best before, use by, expiry date, exp date, exp dt, exp., best before within, months from mfg, months from packaging]
      },
      guidance: Important for food, pharmaceutical and cosmetic items to inform safe shelf life.
    },
    {
      id: LMR_RULE_6_1_E_MRP,
      field: mrp,
      title: Maximum Retail Price (MRP) Inclusive of All Taxes,
      description: The retail sale price of the package shall be clearly indicated in the format 'Maximum or Max. Retail Price Rs. or ₹ ..... (inclusive of all taxes)'.,
      required: True,
      applicability: all_packaged_commodities,
      severity: CRITICAL,
      rule_reference: Rule 6(1)(e) of Legal Metrology (Packaged Commodities) Rules, 2011,
      validation_criteria: {
        keywords: [mrp, m.r.p., maximum retail price, max retail price, retail sale price],
        currency_symbols: [₹, rs, rs., inr],
        tax_declaration_keywords: [inclusive of all taxes, incl. of all taxes, incl all taxes, incl of taxes, inclusive of taxes]
      },
      guidance: MRP must explicitly include currency symbols and the phrase 'inclusive of all taxes' or 'incl. of all taxes'.
    },
    {
      id: LMR_RULE_6_1_F_CONSUMER_CARE,
      field: consumer_care,
      title: Consumer Care / Grievance Redressal Mechanism,
      description: The name, address, telephone number, and e-mail address of the person who can be contacted by the consumer in case of a complaint or consumer grievance.,
      required: True,
      applicability: all_packaged_commodities,
      severity: CRITICAL,
      rule_reference: Rule 6(1)(f) & Rule 6(2) of Legal Metrology (Packaged Commodities) Rules, 2011,
      validation_criteria: {
        keywords: [consumer care, customer care, customer feedback, grievance cell, toll free, helpline, complaints, reach us at, call us],
        requires_contact_channel: True,
        phone_pattern: (\\b1800[- ]?\\d{3}[- ]?\\d{3,4}\\b|\\b\\+?91[- ]?\\d{10}\\b|\\b0\\d{2,4}[- ]?\\d{6,8}\\b),
        email_pattern: [a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+
      },
      guidance: A mandatory consumer care cell with telephone/toll-free number, email, and postal address must be legible on the package.
    },
    {
      id: LMR_RULE_6_1_G_COUNTRY_OF_ORIGIN,
      field: country_of_origin,
      title: Country of Origin / Manufacturing,
      description: The name of the country of origin or manufacture or assembly in case of imported products, and country of origin for domestic packaged commodities.,
      required: True,
      applicability: all_packaged_commodities,
      severity: HIGH,
      rule_reference: Rule 6(1)(g) of Legal Metrology (Packaged Commodities) Rules, 2011 (Amended 2017/2020),
      validation_criteria: {
        keywords: [country of origin, made in, product of, origin:, manufactured in, produced in, assembled in],
        valid_countries: [india, china, usa, germany, japan, vietnam, thailand, bangladesh, indonesia, taiwan, korea, malaysia, uk, italy, france, sri lanka, nepal, bhutan]
      },
      guidance: Declaration of Country of Origin is compulsory on all packaging to provide transparency to consumers.
    },
    {
      id: LMR_RULE_6_1_H_UNIT_SALE_PRICE,
      field: unit_sale_price,
      title: Unit Sale Price (USP),
      description: Declaration of unit sale price (e.g. ₹ per g, ₹ per ml, ₹ per piece) for packages containing more than 1 kg or 1 litre or multiple numbers.,
      required: False,
      applicability: commodities_over_unit_threshold,
      severity: MEDIUM,
      rule_reference: Rule 6(1)(e) Proviso / Amendment Rule 2021 (effective 2022),
      validation_criteria: {
        keywords: [unit sale price, usp, price per unit, per g, per kg, per ml, per l, per piece, per n, per u]
      },
      guidance: Mandatory under the 2021/2022 amendments to enable consumers to compare price-to-quantity value across different package sizes.
    },
    {
      id: LMR_RULE_6_1_I_DIMENSIONS,
      field: dimensions,
      title: Dimensions / Size of the Commodity (Where Applicable),
      description: The sizes or dimensions of the commodity contained in the package, where the package contains piece goods or items defined by physical dimensions.,
      required: False,
      applicability: textiles_hardware_dimensions_applicable,
      severity: LOW,
      rule_reference: Rule 6(1)(d) & Schedule II of Legal Metrology (Packaged Commodities) Rules, 2011,
      validation_criteria: {
        keywords: [dimensions, dimension, size, length, width, height, lxwxh, cm x, mm x, m x, inches]
      },
      guidance: Required for goods sold by length, width, area, or dimensional attributes.
    }
  ]
}

rules_file = os.path.join(BASE_DIR, rules, legal_metrology_rules.json)
with open(rules_file, w, encoding=utf-8) as f:
    json.dump(rules_data, f, indent=2)
print(Wrote rules/legal_metrology_rules.json)
