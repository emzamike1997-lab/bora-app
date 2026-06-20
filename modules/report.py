import io
import os
import re
import html
import base64
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    Table, TableStyle, HRFlowable, PageBreak, NextPageTemplate, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

NAVY = HexColor("#1B2A4A")
GOLD = HexColor("#C9A84C")
WHITE = HexColor("#FFFFFF")
LIGHT_GREY = HexColor("#F8F9FA")
DARK_GREY = HexColor("#2C2C2C")
RED = HexColor("#C62828")
AMBER = HexColor("#F57C00")
GREEN = HexColor("#2E7D32")

def parse_bora_report(text: str) -> dict:
    data = {
        "document_type": "Legal Document Analysis",
        "analysis_date": "N/A",
        "analysis_depth": "Standard",
        "reference": "BORA-" + str(abs(hash(text)))[:6],
        "overall": "GREEN",
        "critical_count": 0,
        "moderate_count": 0,
        "low_count": 0,
        "total_count": 0,
        "executive_summary": "",
        "critical_risks": [],
        "moderate_risks": [],
        "low_risks": [],
        "negotiation_list": [],
        "red_line_clauses": []
    }
    
    # Metadata
    dt_match = re.search(r"Document Type:\s*(.+)", text, re.IGNORECASE)
    if dt_match: data["document_type"] = dt_match.group(1).strip()
    
    ad_match = re.search(r"Analysis Date:\s*(.+)", text, re.IGNORECASE)
    if ad_match: data["analysis_date"] = ad_match.group(1).strip()
    
    dp_match = re.search(r"Analysis Depth:\s*(.+)", text, re.IGNORECASE)
    if dp_match: data["analysis_depth"] = dp_match.group(1).strip()
    
    # Scorecard
    crit_match = re.search(r"Critical\s*(?:\(Red\))?:\s*(\d+)", text, re.IGNORECASE)
    if crit_match: data["critical_count"] = int(crit_match.group(1))
    
    mod_match = re.search(r"Moderate\s*(?:\(Amber\))?:\s*(\d+)", text, re.IGNORECASE)
    if mod_match: data["moderate_count"] = int(mod_match.group(1))
    
    low_match = re.search(r"Low\s*(?:\(Green\))?:\s*(\d+)", text, re.IGNORECASE)
    if low_match: data["low_count"] = int(low_match.group(1))
    
    data["total_count"] = data["critical_count"] + data["moderate_count"] + data["low_count"]
    
    ov_match = re.search(r"Overall\s*risk\s*rating:\s*(RED|AMBER|GREEN)", text, re.IGNORECASE)
    if ov_match:
        data["overall"] = ov_match.group(1).upper()
    else:
        if data["critical_count"] > 0: data["overall"] = "RED"
        elif data["moderate_count"] > 0: data["overall"] = "AMBER"
    
    # Exec Summary
    es_match = re.search(r"EXECUTIVE SUMMARY[^\n]*\n(.*?)(?=\n\n(?:RISK SCORECARD|---|CRITICAL RISKS))", text, re.DOTALL)
    if es_match:
        data["executive_summary"] = es_match.group(1).strip()
    
    # Helper to extract sections
    def extract_section(header_regex, next_header_regex):
        pattern = re.compile(f"{header_regex}.*?\n(.*?)?(?=\n(?:---|{next_header_regex}|$))", re.DOTALL | re.IGNORECASE)
        match = pattern.search(text)
        return match.group(1).strip() if match and match.group(1) else ""
        
    crit_text = extract_section(r"CRITICAL RISKS.*?\n---", r"MODERATE RISKS|LOW RISKS|NEGOTIATION|RED LINE|DISCLAIMER")
    mod_text = extract_section(r"MODERATE RISKS.*?\n---", r"LOW RISKS|NEGOTIATION|RED LINE|DISCLAIMER")
    low_text = extract_section(r"LOW RISKS.*?\n---", r"NEGOTIATION|RED LINE|DISCLAIMER")
    
    data["critical_risks"] = [r.strip() for r in re.split(r"🔴", crit_text) if r.strip()]
    data["moderate_risks"] = [r.strip() for r in re.split(r"🟡", mod_text) if r.strip()]
    data["low_risks"] = [r.strip() for r in re.split(r"🟢", low_text) if r.strip()]
    
    neg_text = extract_section(r"NEGOTIATION PRIORITY LIST.*?\n---", r"RED LINE|DISCLAIMER")
    if neg_text:
        data["negotiation_list"] = [n.strip() for n in re.split(r"\n\d+\.", "\n" + neg_text) if n.strip() and not n.strip().startswith("Numbered list")]
        
    red_text = extract_section(r"RED LINE CLAUSES.*?\n---", r"DISCLAIMER")
    if red_text and "No absolute red line clauses found" not in red_text:
        data["red_line_clauses"] = [r.strip() for r in red_text.split("\n\n") if r.strip()]
            
    return data

def onCover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    
    canvas.setFillColor(GOLD)
    canvas.circle(A4[0]/2, A4[1] - 120, 40, fill=1, stroke=0)
    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 40)
    canvas.drawCentredString(A4[0]/2, A4[1] - 135, "B")
    
    # Bottom section lines
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(1)
    canvas.line(50, 40, A4[0]-50, 40)
    canvas.restoreState()

def onContent(canvas, doc):
    canvas.saveState()
    # Watermark
    canvas.setFillColor(HexColor("#EAEAEA"))
    canvas.setFont("Helvetica-Bold", 150)
    canvas.translate(A4[0]/2, A4[1]/2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, "BORA")
    canvas.restoreState()
    
    # Header
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 30, A4[0], 30, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 10)
    canvas.drawString(50, A4[1] - 20, "BORA Risk Analysis Report")
    if hasattr(doc, 'document_type'):
        canvas.drawRightString(A4[0] - 50, A4[1] - 20, str(doc.document_type))
    canvas.restoreState()
    
    # Footer
    canvas.saveState()
    canvas.setFillColor(LIGHT_GREY)
    canvas.rect(0, 0, A4[0], 30, fill=1, stroke=0)
    canvas.setFillColor(DARK_GREY)
    canvas.setFont("Helvetica", 9)
    canvas.drawString(50, 10, "Confidential")
    canvas.drawCentredString(A4[0] / 2, 10, f"Page {canvas.getPageNumber()}")
    canvas.drawRightString(A4[0] - 50, 10, "bora-analysis.streamlit.app")
    canvas.restoreState()

class BORADocTemplate(BaseDocTemplate):
    def __init__(self, filename, document_type, **kw):
        super().__init__(filename, **kw)
        self.document_type = document_type

def make_risk_table(risk_str, stripe_color, styles):
    lines = risk_str.split("\n")
    title = lines[0].strip()
    
    normal = styles['Normal']
    navy_bold = ParagraphStyle('NavyBold', parent=normal, fontName='Helvetica-Bold', textColor=NAVY)
    grey_label = "<font color='#666666'>%s</font>"
    
    content = [Paragraph(title, navy_bold)]
    
    for line in lines[1:]:
        if not line.strip(): continue
        if ":" in line:
            k, v = line.split(":", 1)
            kl = k.lower().strip()
            
            if "clause" in kl:
                content.append(Paragraph(f"{grey_label % k + ':'} <font color='#1B2A4A'>{v}</font>", normal))
            elif "law" in kl:
                content.append(Paragraph(f"{grey_label % k + ':'} <font color='{stripe_color}'>{v}</font>", normal))
            elif "what to do" in kl or "action" in kl:
                t = Table([[Paragraph(f"<b>{k}:</b> {v}", normal)]], style=[
                    ('BACKGROUND', (0,0), (0,0), HexColor("#FFF8E1")),
                    ('TOPPADDING', (0,0), (0,0), 6),
                    ('BOTTOMPADDING', (0,0), (0,0), 6),
                ])
                content.append(t)
            elif "financial" in kl:
                content.append(Paragraph(f"<b>{k}:</b> {v}", normal))
            else:
                content.append(Paragraph(f"{grey_label % k + ':'} {v}", normal))
        else:
            content.append(Paragraph(line, normal))
            
    t = Table([["", content]], colWidths=[4, A4[0]-100-4], style=[
        ('BACKGROUND', (0,0), (0,0), stripe_color),
        ('BACKGROUND', (1,0), (1,0), LIGHT_GREY),
        ('LEFTPADDING', (1,0), (1,0), 12),
        ('RIGHTPADDING', (1,0), (1,0), 12),
        ('TOPPADDING', (1,0), (1,0), 12),
        ('BOTTOMPADDING', (1,0), (1,0), 12),
        ('VALIGN', (0,0), (-1,-1), 'TOP')
    ])
    return KeepTogether(t)

def generate_pdf_report(text: str) -> bytes:
    data = parse_bora_report(text)
    
    buffer = io.BytesIO()
    doc = BORADocTemplate(buffer, data['document_type'], pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
    template_cover = PageTemplate(id='Cover', frames=frame, onPage=onCover)
    template_content = PageTemplate(id='Content', frames=frame, onPage=onContent)
    doc.addPageTemplates([template_cover, template_content])
    
    styles = getSampleStyleSheet()
    normal = styles['Normal']
    normal.fontName = 'Helvetica'
    normal.textColor = DARK_GREY
    
    white_16_center = ParagraphStyle('w16', parent=normal, textColor=WHITE, fontSize=16, alignment=1)
    gold_36_center = ParagraphStyle('g36', parent=normal, textColor=GOLD, fontName='Helvetica-Bold', fontSize=36, alignment=1)
    navy_10_spaced_center = ParagraphStyle('n10', parent=normal, textColor=NAVY, fontSize=10, alignment=1, spaceAfter=5)
    navy_24_bold_center = ParagraphStyle('n24', parent=normal, textColor=NAVY, fontName='Helvetica-Bold', fontSize=24, alignment=1)
    grey_10_center = ParagraphStyle('g10', parent=normal, textColor=DARK_GREY, fontSize=10, alignment=1)
    navy_12_bold_center = ParagraphStyle('n12', parent=normal, textColor=NAVY, fontName='Helvetica-Bold', fontSize=12, alignment=1)
    white_14_bold_center = ParagraphStyle('w14', parent=normal, textColor=WHITE, fontName='Helvetica-Bold', fontSize=14, alignment=1)
    white_10_center = ParagraphStyle('w10', parent=normal, textColor=WHITE, fontSize=10, alignment=1)
    gold_10_center = ParagraphStyle('g10c', parent=normal, textColor=GOLD, fontSize=10, alignment=1)
    grey_9_center = ParagraphStyle('g9', parent=normal, textColor=HexColor("#AAAAAA"), fontSize=9, alignment=1)
    
    white_14_bold = ParagraphStyle('w14b', parent=normal, textColor=WHITE, fontName='Helvetica-Bold', fontSize=14)
    white_13_bold = ParagraphStyle('w13b', parent=normal, textColor=WHITE, fontName='Helvetica-Bold', fontSize=13)
    
    elements = []
    
    # ---------------- COVER PAGE ----------------
    elements.append(Spacer(1, 150))
    elements.append(Paragraph("BORA", gold_36_center))
    elements.append(Paragraph("Legal Document Analysis Report", white_16_center))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=GOLD))
    elements.append(Spacer(1, 40))
    
    # White Card Table
    card_content = []
    card_content.append(Spacer(1, 20))
    card_content.append(Paragraph("C O N F I D E N T I A L   R I S K   A N A L Y S I S", navy_10_spaced_center))
    card_content.append(Paragraph(data['document_type'].upper(), navy_24_bold_center))
    card_content.append(Spacer(1, 10))
    card_content.append(HRFlowable(width="80%", thickness=1, color=GOLD))
    card_content.append(Spacer(1, 20))
    
    cw = (A4[0]-100)/3
    t_data = [
        [Paragraph("Analysis Date", grey_10_center), Paragraph("Analysis Depth", grey_10_center), Paragraph("Reference", grey_10_center)],
        [Paragraph(data['analysis_date'], navy_12_bold_center), Paragraph(data['analysis_depth'], navy_12_bold_center), Paragraph(data['reference'], navy_12_bold_center)]
    ]
    card_content.append(Table(t_data, colWidths=[cw, cw, cw]))
    card_content.append(Spacer(1, 30))
    
    badge_color = RED if data['overall'] == 'RED' else (AMBER if data['overall'] == 'AMBER' else GREEN)
    badge_text = "HIGH RISK" if data['overall'] == 'RED' else ("MODERATE RISK" if data['overall'] == 'AMBER' else "LOW RISK")
    
    badge_table = Table([[Paragraph(badge_text, white_14_bold_center)]], colWidths=[200], rowHeights=[40])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), badge_color),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('VALIGN', (0,0), (0,0), 'MIDDLE'),
    ]))
    wrapper = Table([[badge_table]], colWidths=[A4[0]-100], style=[('ALIGN', (0,0), (0,0), 'CENTER')])
    card_content.append(wrapper)
    card_content.append(Spacer(1, 20))
    
    card_table = Table([[card_content]], colWidths=[A4[0]-100])
    card_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), WHITE),
        ('LEFTPADDING', (0,0), (0,0), 0),
        ('RIGHTPADDING', (0,0), (0,0), 0),
    ]))
    
    elements.append(card_table)
    
    elements.append(Spacer(1, 100))
    elements.append(Paragraph("Prepared by BORA AI Legal Analysis", white_10_center))
    elements.append(Paragraph("bora-analysis.streamlit.app", gold_10_center))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("This report is confidential and prepared exclusively for the document owner.", grey_9_center))
    
    elements.append(NextPageTemplate('Content'))
    elements.append(PageBreak())
    
    # ---------------- EXECUTIVE SUMMARY PAGE ----------------
    t = Table([[Paragraph("EXECUTIVE SUMMARY", white_14_bold)]], colWidths=[A4[0]-100], style=[('BACKGROUND', (0,0), (0,0), NAVY), ('LEFTPADDING', (0,0), (0,0), 10)])
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    def make_score_box(title, count, color):
        return Table([
            [Paragraph(str(count), ParagraphStyle('C', parent=normal, fontName='Helvetica-Bold', fontSize=36, textColor=color, alignment=1))],
            [Paragraph(title, ParagraphStyle('T', parent=normal, fontSize=10, textColor=DARK_GREY, alignment=1))]
        ], colWidths=[(A4[0]-100-30)/4], rowHeights=[60, 20], style=[
            ('BOX', (0,0), (-1,-1), 1, color),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (0,0), 'BOTTOM'),
            ('VALIGN', (0,1), (0,1), 'TOP'),
        ])
        
    sb = Table([[ 
        make_score_box("Total Risks", data['total_count'], NAVY),
        make_score_box("Critical/Red", data['critical_count'], RED),
        make_score_box("Moderate/Amber", data['moderate_count'], AMBER),
        make_score_box("Low/Green", data['low_count'], GREEN)
    ]], style=[('ALIGN', (0,0), (-1,-1), 'CENTER')])
    elements.append(sb)
    elements.append(Spacer(1, 20))
    
    action_bg = HexColor("#FFEBEE") if data['overall'] == "RED" else (HexColor("#FFF3E0") if data['overall'] == "AMBER" else HexColor("#E8F5E9"))
    if data['overall'] == "RED": action_text = "⛔ DO NOT SIGN — This document contains critical legal violations that must be addressed before signing."
    elif data['overall'] == "AMBER": action_text = "⚠️ NEGOTIATE FIRST — Review and negotiate flagged clauses before signing."
    else: action_text = "✅ REASONABLE TO SIGN — Standard legal review recommended."
    
    t = Table([[Paragraph(action_text, normal)]], colWidths=[A4[0]-100], style=[
        ('BACKGROUND', (0,0), (0,0), action_bg),
        ('PADDING', (0,0), (0,0), 12),
    ])
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    if data['executive_summary']:
        elements.append(Paragraph(data['executive_summary'], ParagraphStyle('ES', parent=normal, fontSize=11, textColor=DARK_GREY)))
        elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("<b>Table of Contents</b>", ParagraphStyle('TOC_Title', parent=normal, fontSize=12, textColor=NAVY)))
    elements.append(Spacer(1, 10))
    
    toc_items = ["1. Executive Summary"]
    if data['critical_risks']: toc_items.append(f"{len(toc_items)+1}. Critical Risks")
    if data['moderate_risks']: toc_items.append(f"{len(toc_items)+1}. Moderate Risks")
    if data['low_risks']: toc_items.append(f"{len(toc_items)+1}. Low Risks")
    if data['negotiation_list']: toc_items.append(f"{len(toc_items)+1}. Negotiation Priority List")
    if data['red_line_clauses']: toc_items.append(f"{len(toc_items)+1}. Red Line Clauses")
    
    for item in toc_items:
        elements.append(Paragraph(item, normal))
    
    elements.append(PageBreak())
    
    # ---------------- RISK SECTIONS ----------------
    def add_risk_section(title, risks, color):
        if not risks: return
        t = Table([[Paragraph(title, white_13_bold)]], colWidths=[A4[0]-100], style=[('BACKGROUND', (0,0), (0,0), NAVY), ('LEFTPADDING', (0,0), (0,0), 10)])
        elements.append(t)
        elements.append(Spacer(1, 15))
        for risk in risks:
            elements.append(make_risk_table(risk, color, styles))
            elements.append(Spacer(1, 8))
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=GOLD))
        elements.append(Spacer(1, 15))
        
    add_risk_section("CRITICAL RISKS", data['critical_risks'], RED)
    add_risk_section("MODERATE RISKS", data['moderate_risks'], AMBER)
    add_risk_section("LOW RISKS", data['low_risks'], GREEN)
    
    # ---------------- NEGOTIATION PRIORITY LIST ----------------
    if data['negotiation_list']:
        t = Table([[Paragraph("NEGOTIATION PRIORITY LIST", white_13_bold)]], colWidths=[A4[0]-100], style=[('BACKGROUND', (0,0), (0,0), NAVY), ('LEFTPADDING', (0,0), (0,0), 10)])
        elements.append(t)
        elements.append(Spacer(1, 15))
        
        n_data = []
        for i, item in enumerate(data['negotiation_list']):
            bullet = Paragraph(f"<font color='{GOLD}'>■</font> {i+1}.", normal)
            text = Paragraph(item, normal)
            n_data.append([bullet, text])
            
        nt = Table(n_data, colWidths=[30, A4[0]-130], style=[
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 8)
        ])
        for i in range(len(n_data)):
            bg = WHITE if i % 2 == 0 else LIGHT_GREY
            nt.setStyle(TableStyle([('BACKGROUND', (0,i), (-1,i), bg)]))
            
        elements.append(nt)
        elements.append(Spacer(1, 20))
        
    # ---------------- RED LINE CLAUSES ----------------
    if data['red_line_clauses']:
        t = Table([[Paragraph("⚠️ RED LINE CLAUSES — Do not sign if these are not removed", white_13_bold)]], colWidths=[A4[0]-100], style=[('BACKGROUND', (0,0), (0,0), RED), ('LEFTPADDING', (0,0), (0,0), 10)])
        elements.append(t)
        elements.append(Spacer(1, 15))
        
        for r in data['red_line_clauses']:
            rt = Table([[Paragraph(r, ParagraphStyle('R', parent=normal, textColor=RED, fontName='Helvetica-Bold'))]], colWidths=[A4[0]-100], style=[
                ('BOX', (0,0), (-1,-1), 2, RED),
                ('PADDING', (0,0), (-1,-1), 10),
                ('BACKGROUND', (0,0), (-1,-1), HexColor("#FFEBEE"))
            ])
            elements.append(rt)
            elements.append(Spacer(1, 10))
            
    # ---------------- DISCLAIMER ----------------
    elements.append(NextPageTemplate('Cover'))
    elements.append(PageBreak())
    
    elements.append(Spacer(1, 200))
    elements.append(Paragraph("B", ParagraphStyle('Bg', parent=normal, textColor=GOLD, fontName='Helvetica-Bold', fontSize=60, alignment=1)))
    elements.append(Spacer(1, 40))
    
    disc_text = """© 2026 BORA. All rights reserved.<br/><br/>
    BORA is not a law firm and does not provide legal advice.
    This analysis is generated by AI and is provided for informational purposes only.
    For legally binding advice please consult a qualified South African attorney before signing any contract.
    We accept no liability for decisions made based on this analysis."""
    
    elements.append(Paragraph(disc_text, white_10_center))
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="60%", thickness=1, color=GOLD))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("bora-analysis.streamlit.app", gold_10_center))
    
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes

def send_report_email(to_email: str, pdf_bytes: bytes, document_type: str):
    api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("SENDGRID_FROM_EMAIL", "reports@bora-analysis.co.za")
    
    if not api_key:
        print("Warning: SENDGRID_API_KEY not set. Cannot send email.")
        return False
        
    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=f"Your BORA {document_type} Report",
        html_content="""
        <div style="font-family: Arial, sans-serif; color: #2C2C2C;">
            <h2 style="color: #1B2A4A;">Your Document Analysis is Complete</h2>
            <p>Thank you for using BORA. Please find your detailed risk analysis report attached.</p>
            <br>
            <p><strong>Know what you're signing before you sign it.</strong></p>
            <p style="color: #C9A84C;">The BORA Team</p>
        </div>
        """
    )
    
    encoded_pdf = base64.b64encode(pdf_bytes).decode()
    attachment = Attachment()
    attachment.file_content = FileContent(encoded_pdf)
    attachment.file_type = FileType('application/pdf')
    attachment.file_name = FileName(f"BORA_{document_type.replace(' ', '_')}_Report.pdf")
    attachment.disposition = Disposition('attachment')
    message.attachment = attachment
    
    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
