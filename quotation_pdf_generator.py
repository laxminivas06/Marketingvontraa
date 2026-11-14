"""
quotation_pdf_generator.py - Premium Corporate Quotation PDF Generator
Reconstructed according to executive corporate standards:
- Company full legal name: AIVONTRAA AUTOMATION PRIVATE LIMITED
- No logo, no GST number or GSTIN placeholder
- Quotation number clearly visible, NO 'Official Quotation' title
- Responsive layout handling short, medium, and long quotations
- Dynamic multicell text wrapping, clean pagination, and page numbers (Page X of Y)
- Complete mathematical integrity and transparent financial breakdown
"""

import math
from datetime import datetime
import fpdf

COMPANY_LEGAL_NAME = "AIVONTRAA AUTOMATION PRIVATE LIMITED"
COMPANY_SUBTITLE = "Enterprise Software, AI Automation, Web Solutions & Cloud Platforms"
COMPANY_CIN = "U72900DL2026PTC001234"
COMPANY_EMAIL = "sales@aivontraa.com"
COMPANY_WEBSITE = "www.aivontraa.com"

def clean_txt(text):
    """Sanitize text for FPDF Latin-1 encoding and strip unwanted GST remnants."""
    if text is None:
        return ""
    t = str(text)
    t = t.replace("₹", "INR ").replace("—", "-").replace("–", "-").replace("•", "*")
    t = t.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    # Guarantee no GSTIN placeholder is present
    import re
    t = re.sub(r"\bGSTIN\s*:\s*[A-Z0-9]+\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\bGST\s*#\s*:\s*[A-Z0-9]+\b", "", t, flags=re.IGNORECASE)
    return t.encode("latin-1", "replace").decode("latin-1").strip()

class CorporateQuotationPDF(fpdf.FPDF):
    def __init__(self, quote_num=""):
        super().__init__(format="A4", unit="mm")
        self.quote_num = clean_txt(quote_num)
        # 10mm margins for optimal 190mm printable width on A4 (210mm x 297mm)
        self.set_margins(10, 10, 10)
        self.set_auto_page_break(auto=False) # Manual control over table row splitting
        self.page_bottom_limit = 278.0 # Footer starts at 282mm

    def header(self):
        # Header on subsequent pages (Page 2, Page 3, etc.)
        if self.page_no() > 1:
            self.set_xy(10, 8)
            self.set_font("Arial", "B", 8)
            self.set_text_color(15, 23, 42)
            self.cell(100, 5, clean_txt(COMPANY_LEGAL_NAME), 0, 0, "L")

            self.set_font("Arial", "", 8)
            self.set_text_color(71, 85, 105)
            self.cell(90, 5, clean_txt(f"Quotation Ref: {self.quote_num}"), 0, 1, "R")

            self.set_draw_color(226, 232, 240)
            self.set_line_width(0.3)
            self.line(10, 14, 200, 14)
            self.set_y(18)

    def footer(self):
        # Professional corporate footer across all pages
        self.set_y(-14)
        self.set_draw_color(226, 232, 240)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())

        self.set_y(-11)
        self.set_font("Arial", "", 7.5)
        self.set_text_color(100, 116, 139)
        self.cell(120, 5, clean_txt(f"{COMPANY_LEGAL_NAME} - Commercial Quotation"), 0, 0, "L")
        
        # Page numbering: Page X of Y
        self.cell(70, 5, f"Page {self.page_no()} of {{nb}}", 0, 0, "R")


def calc_multicell_lines(pdf, text, col_width):
    """Calculates number of wrapped lines for a given text and width in FPDF."""
    if not text:
        return 1
    total_lines = 0
    for para in str(text).split("\n"):
        words = para.split(" ")
        cur_w = 0
        for w in words:
            word_w = pdf.get_string_width(w + " ")
            if cur_w + word_w > col_width:
                total_lines += 1
                cur_w = word_w
            else:
                cur_w += word_w
        if cur_w > 0 or not words:
            total_lines += 1
    return max(1, total_lines)


def draw_table_header(pdf):
    """Renders the standard investment table column headings."""
    pdf.set_fill_color(241, 245, 249) # var(--slate-100)
    pdf.set_draw_color(203, 213, 225) # var(--slate-300)
    pdf.set_text_color(15, 23, 42)    # var(--slate-900)
    pdf.set_font("Arial", "B", 8.5)
    
    # 120mm Description, 32mm Billing Cadence, 38mm Amount = 190mm Total
    pdf.cell(120, 7.5, "  Deliverable Item & Scope", 1, 0, "L", fill=True)
    pdf.cell(32, 7.5, "Billing Cadence", 1, 0, "C", fill=True)
    pdf.cell(38, 7.5, "Amount  ", 1, 1, "R", fill=True)


def generate_corporate_quotation_pdf(q: dict) -> bytes:
    """
    Main PDF generation function.
    Converts quotation data dictionary into a premium corporate PDF.
    """
    curr = q.get("currency", "INR").upper()
    sym = "$" if curr == "USD" else "INR "
    quote_num = q.get("quoteNumber", "AIV-QT-2026-0000")
    created_date = q.get("createdAt") or datetime.now().strftime("%Y-%m-%d")

    pdf = CorporateQuotationPDF(quote_num=quote_num)
    pdf.alias_nb_pages()
    pdf.add_page()

    # =========================================================================
    # 1. PAGE 1 HEADER: Company Legal Name & Clean Quotation Identifier
    # =========================================================================
    # Left column: Full Legal Name & Company Meta
    pdf.set_xy(10, 11)
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(15, 23, 42) # Slate-900
    pdf.cell(120, 6.5, clean_txt(COMPANY_LEGAL_NAME), 0, 0, "L")

    # Right column: Quotation Reference & Date (NO 'Official Quotation' title)
    pdf.set_font("Arial", "B", 10.5)
    pdf.set_text_color(30, 64, 175) # Corporate Blue (slate-800 / primary)
    pdf.cell(70, 6.5, clean_txt("QUOTATION"), 0, 1, "R")

    # Subtitle line
    pdf.set_xy(10, 18)
    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(120, 4.5, clean_txt(COMPANY_SUBTITLE), 0, 0, "L")

    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(70, 4.5, clean_txt(f"Quote Ref: {quote_num}"), 0, 1, "R")

    # Corporate meta line (CIN, Email, Website - strictly NO GST number field)
    pdf.set_xy(10, 22.5)
    pdf.set_font("Arial", "", 7.5)
    pdf.set_text_color(100, 116, 139)
    corporate_contact = f"CIN: {COMPANY_CIN} | Email: {COMPANY_EMAIL} | Web: {COMPANY_WEBSITE}"
    pdf.cell(120, 4.5, clean_txt(corporate_contact), 0, 0, "L")

    pdf.cell(70, 4.5, clean_txt(f"Issue Date: {created_date}"), 0, 1, "R")

    # Elegant horizontal accent rule
    pdf.set_y(28.5)
    pdf.set_draw_color(30, 64, 175) # Primary accent line
    pdf.set_line_width(0.75)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.set_line_width(0.2) # reset

    # =========================================================================
    # 2. CUSTOMER & COMMERCIAL TEAM METADATA CARD
    # =========================================================================
    card_y = pdf.get_y() + 4
    card_h = 24.0
    pdf.set_fill_color(248, 250, 252) # Slate-50
    pdf.set_draw_color(226, 232, 240) # Slate-200
    pdf.rect(10, card_y, 190, card_h, "DF")

    # Prepared For (Left)
    pdf.set_xy(14, card_y + 2.5)
    pdf.set_font("Arial", "B", 7.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(90, 4, "PREPARED FOR:", 0, 0, "L")

    # Client Success / Commercial Team (Right)
    pdf.cell(90, 4, "COMMERCIAL DELIVERY TEAM:", 0, 1, "L")

    # Client Name & Executive Name
    pdf.set_x(14)
    pdf.set_font("Arial", "B", 10.5)
    pdf.set_text_color(15, 23, 42)
    client_name = q.get("clientName", "-")
    pdf.cell(90, 5.5, clean_txt(client_name), 0, 0, "L")

    pdf.set_font("Arial", "B", 9)
    exec_name = q.get("commExecutiveName") or q.get("executiveName") or "Lead Commercial Executive"
    pdf.cell(90, 5.5, clean_txt(exec_name), 0, 1, "L")

    # Domain / Benchmark & Coordinator
    pdf.set_x(14)
    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(71, 85, 105)
    domain_info = f"Domain: {q.get('domainName')}" if q.get("domainName") else f"Solution: {q.get('categoryName', 'Web Application')}"
    pdf.cell(90, 4.5, clean_txt(domain_info), 0, 0, "L")

    doc_coord = q.get("docCoordinatorName") or "Project Documentation Coordinator"
    pdf.cell(90, 4.5, clean_txt(f"Documentation: {doc_coord}"), 0, 1, "L")

    pdf.set_y(card_y + card_h + 4)

    # =========================================================================
    # 3. SOLUTION SCOPE & KEY DELIVERABLES
    # =========================================================================
    pdf.set_font("Arial", "B", 9.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(190, 5.5, clean_txt("1. Solution Scope & Specifications"), 0, 1, "L")

    cat_name = q.get("categoryName") or q.get("classification") or "Custom Web Platform"
    classification = q.get("classification", "Application")
    cat_desc = f"{cat_name} ({classification})"
    
    pdf.set_font("Arial", "", 8.5)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(190, 4.5, clean_txt(f"Solution Classification: {cat_desc}"), 0, 1, "L")

    if q.get("referenceUrl"):
        pdf.set_font("Arial", "", 8)
        pdf.cell(190, 4, clean_txt(f"Benchmark Reference: {q.get('referenceUrl')}"), 0, 1, "L")

    # Specifications list (if present in quotation object)
    features = q.get("features", [])
    if not features and q.get("requirements"):
        features = q.get("requirements")[:4]
    if features:
        pdf.ln(1)
        pdf.set_font("Arial", "", 7.5)
        pdf.set_text_color(71, 85, 105)
        for f in features[:4]:
            pdf.cell(5, 4, "-", 0, 0, "R")
            pdf.cell(185, 4, clean_txt(f" {f}"), 0, 1, "L")

    pdf.ln(3)

    # =========================================================================
    # 4. INVESTMENT SCHEDULE & FINANCIAL BREAKDOWN
    # =========================================================================
    pdf.set_font("Arial", "B", 9.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(190, 5.5, clean_txt("2. Investment Schedule"), 0, 1, "L")

    draw_table_header(pdf)

    # Prepare list of items
    pay_period = q.get("selectedPaymentPeriod") or q.get("billingCadence") or "One-Time"
    base_price = float(q.get("basePrice", q.get("websitePrice", 0)) or 0)
    domain_amount = float(q.get("domainAmount", 0) or 0)

    items = []
    # 1. Base Core implementation
    items.append({
        "name": f"{cat_name} - Core Architecture & Implementation",
        "desc": f"Includes responsive frontend design, backend integration, and deployment.",
        "cadence": pay_period,
        "amount": base_price
    })

    # 2. Custom Domain
    if domain_amount > 0:
        dom_name = q.get("domainName") or "Custom Domain"
        items.append({
            "name": f"Domain Registration & DNS Configuration: {dom_name}",
            "desc": "Annual domain registration and SSL/DNS infrastructure setup.",
            "cadence": "One-Time",
            "amount": domain_amount
        })

    # 3. Add-on items
    for a in q.get("addons", []):
        aname = a.get("name", "Optional Deliverable")
        adesc = a.get("desc", "")
        acycle = a.get("billingCycle", "One-Time")
        aprice = float(a.get("price", 0) or 0)
        items.append({
            "name": aname,
            "desc": adesc,
            "cadence": acycle,
            "amount": aprice
        })

    # Render table items dynamically
    col1_w = 120.0
    col2_w = 32.0
    col3_w = 38.0

    for idx, item in enumerate(items):
        full_text = item["name"]
        if item.get("desc"):
            full_text += f"\n{item['desc']}"
        
        pdf.set_font("Arial", "", 8)
        lines = calc_multicell_lines(pdf, full_text, col1_w - 6)
        row_h = max(7.0, lines * 4.2 + 2.5)

        # Intelligent Page Break check
        if pdf.get_y() + row_h > pdf.page_bottom_limit:
            pdf.add_page()
            draw_table_header(pdf)

        start_x = 10.0
        start_y = pdf.get_y()

        # Alternate row fill
        if idx % 2 == 1:
            pdf.set_fill_color(250, 250, 252)
            pdf.rect(start_x, start_y, 190, row_h, "F")

        # Borders
        pdf.set_draw_color(226, 232, 240)
        pdf.rect(start_x, start_y, col1_w, row_h)
        pdf.rect(start_x + col1_w, start_y, col2_w, row_h)
        pdf.rect(start_x + col1_w + col2_w, start_y, col3_w, row_h)

        # Col 1: Description
        pdf.set_xy(start_x + 2, start_y + 1.2)
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(col1_w - 4, 4, clean_txt(item["name"]), 0, 1, "L")
        
        if item.get("desc"):
            pdf.set_x(start_x + 2)
            pdf.set_font("Arial", "", 7.5)
            pdf.set_text_color(100, 116, 139)
            pdf.multi_cell(col1_w - 4, 3.8, clean_txt(item["desc"]), 0, "L")

        # Col 2: Cadence
        pdf.set_xy(start_x + col1_w, start_y)
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(col2_w, row_h, clean_txt(item["cadence"]), 0, 0, "C")

        # Col 3: Amount
        pdf.set_xy(start_x + col1_w + col2_w, start_y)
        pdf.set_font("Arial", "B", 8.5)
        pdf.set_text_color(15, 23, 42)
        amt_str = f"{sym}{item['amount']:,.2f}  "
        pdf.cell(col3_w, row_h, clean_txt(amt_str), 0, 0, "R")

        pdf.set_y(start_y + row_h)

    # =========================================================================
    # 5. FINANCIAL TOTALS SUMMARY BLOCK
    # =========================================================================
    subtotal = float(q.get("oneTimeSubtotal", q.get("subtotal", 0)) or 0)
    gst = float(q.get("oneTimeGST", q.get("gstAmount", 0)) or 0)
    total = float(q.get("oneTimeTotal", q.get("totalPrice", 0)) or 0)

    # Check if totals block fits on current page (needs ~30mm)
    if pdf.get_y() + 32.0 > pdf.page_bottom_limit:
        pdf.add_page()

    # One-Time Subtotal
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(203, 213, 225)
    pdf.set_font("Arial", "B", 8.5)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(152, 6.5, "  One-Time Investment Subtotal", 1, 0, "L", fill=True)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(38, 6.5, clean_txt(f"{sym}{subtotal:,.2f}  "), 1, 1, "R", fill=True)

    # Applicable Taxes (where applicable)
    if gst > 0:
        pdf.set_font("Arial", "", 8.5)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(152, 6.0, "  Applicable Taxes (18% GST)", 1, 0, "L")
        pdf.cell(38, 6.0, clean_txt(f"{sym}{gst:,.2f}  "), 1, 1, "R")
    else:
        pdf.set_font("Arial", "", 8.5)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(152, 6.0, "  Applicable Taxes", 1, 0, "L")
        pdf.cell(38, 6.0, clean_txt(f"{sym}0.00  "), 1, 1, "R")

    # Final Total One-Time Investment (Bold Accent Bar)
    pdf.set_fill_color(238, 242, 255) # Indigo-50
    pdf.set_draw_color(165, 180, 252) # Indigo-300
    pdf.set_font("Arial", "B", 9.5)
    pdf.set_text_color(30, 64, 175)   # Primary Indigo / Blue
    pdf.cell(152, 7.5, "  Total One-Time Application Investment (Payable Amount)", 1, 0, "L", fill=True)
    pdf.cell(38, 7.5, clean_txt(f"{sym}{total:,.2f}  "), 1, 1, "R", fill=True)

    # Monthly Recurring Costs (if applicable)
    m_str = q.get("monthlyTotalStr")
    if m_str and m_str not in ["$0 / Month", "₹0 / Month", "INR 0 / Month", "$0.00 / Month"]:
        pdf.set_fill_color(240, 249, 255)
        pdf.set_draw_color(186, 230, 253)
        pdf.set_font("Arial", "B", 8.5)
        pdf.set_text_color(2, 132, 199)
        pdf.cell(152, 6.5, "  Monthly Recurring Subscription Total", 1, 0, "L", fill=True)
        pdf.cell(38, 6.5, clean_txt(f"{m_str}  "), 1, 1, "R", fill=True)

    # Annual Recurring Costs (if applicable)
    a_str = q.get("annualTotalStr")
    if a_str and a_str not in ["$0 / Year", "₹0 / Year", "INR 0 / Year", "$0.00 / Year"]:
        pdf.set_fill_color(250, 245, 255)
        pdf.set_draw_color(233, 213, 255)
        pdf.set_font("Arial", "B", 8.5)
        pdf.set_text_color(124, 58, 237)
        pdf.cell(152, 6.5, "  Annual Recurring Subscription Total", 1, 0, "L", fill=True)
        pdf.cell(38, 6.5, clean_txt(f"{a_str}  "), 1, 1, "R", fill=True)

    pdf.ln(3)

    # =========================================================================
    # 6. TERMS & CONDITIONS
    # =========================================================================
    # Check if space is sufficient for terms + signatures (~55mm)
    if pdf.get_y() + 55.0 > pdf.page_bottom_limit:
        pdf.add_page()

    pdf.set_font("Arial", "B", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(190, 4.5, "TERMS & COMMERCIAL CONDITIONS:", 0, 1, "L")

    pdf.set_font("Arial", "", 7.5)
    pdf.set_text_color(100, 116, 139)
    terms_list = [
        "1. 50% advance upon project kickoff; balance 50% upon final staging review and deployment.",
        "2. Production schedule commences immediately upon receipt of client assets, credentials, and brief.",
        "3. Deliverables carry 30 calendar days of post-launch technical defect warranty and bug support.",
        "4. Recurring subscriptions (if selected) are billed in accordance with the specified billing cadence."
    ]
    for term in terms_list:
        pdf.cell(190, 3.8, clean_txt(term), 0, 1, "L")

    # =========================================================================
    # 7. CORPORATE & CLIENT ACCEPTANCE SIGN-OFF
    # =========================================================================
    # Check if signature block fits (~30mm)
    if pdf.get_y() + 32.0 > pdf.page_bottom_limit:
        pdf.add_page()

    pdf.ln(5)
    sig_y = pdf.get_y()

    # Left: For Aivontraa
    pdf.set_xy(10, sig_y)
    pdf.set_font("Arial", "B", 8)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(90, 4, clean_txt(f"For {COMPANY_LEGAL_NAME}"), 0, 0, "L")

    # Right: Client Acceptance
    pdf.cell(10, 4, "", 0, 0)
    pdf.cell(90, 4, "CLIENT ACCEPTANCE SIGN-OFF", 0, 1, "R")

    # Signature line
    pdf.ln(10)
    pdf.set_draw_color(148, 163, 184)
    line_y = pdf.get_y()
    pdf.line(10, line_y, 80, line_y)
    pdf.line(130, line_y, 200, line_y)

    pdf.set_xy(10, line_y + 1.5)
    pdf.set_font("Arial", "", 7.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(90, 4, "Authorized Signatory (Commercial Operations)", 0, 0, "L")
    pdf.cell(10, 4, "", 0, 0)
    pdf.cell(90, 4, "Authorized Representative Signature & Date", 0, 1, "R")

    return pdf.output(dest="S").encode("latin1")

