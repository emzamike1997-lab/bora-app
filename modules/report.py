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

# Hex string versions for use inside Paragraph HTML f-strings
NAVY_HEX = "#1B2A4A"
GOLD_HEX = "#C9A84C"
WHITE_HEX = "#FFFFFF"
RED_HEX = "#C62828"
AMBER_HEX = "#F57C00"
GREEN_HEX = "#2E7D32"
GREY_HEX = "#666666"

def parse_analysis_results(text: str) -> dict:
    """
    Parse analysis results into structured data for PDF generation.
    Returns a dict with all sections.
    """
    result = {
        "document_type": "Legal Document Analysis",
        "analysis_date": "N/A",
        "analysis_depth": "Standard",
        "reference": "BORA-" + str(abs(hash(text)))[:6],
        "overall_rating": "RED",
        "recommended_action": "Do Not Sign",
        "executive_summary": "",
        "critical_risks": [],
        "moderate_risks": [],
        "low_risks": [],
        "negotiation_priorities": [],
        "red_line_clauses": [],
        "disclaimer": ""
    }
    
    if not text or len(text.strip()) == 0:
        return result
    
    # Metadata
    dt_match = re.search(r"Document Type:\s*(.+)", text, re.IGNORECASE)
    if dt_match: result["document_type"] = dt_match.group(1).strip()
    
    ad_match = re.search(r"Analysis Date:\s*(.+)", text, re.IGNORECASE)
    if ad_match: result["analysis_date"] = ad_match.group(1).strip()
    
    dp_match = re.search(r"Analysis Depth:\s*(.+)", text, re.IGNORECASE)
    if dp_match: result["analysis_depth"] = dp_match.group(1).strip()
    
    # Detect overall rating
    text_upper = text.upper()
    if "OVERALL RISK RATING" in text_upper:
        pos = text_upper.find("OVERALL")
        end_pos = min(pos + 100, len(text_upper))
        context_str = text_upper[pos:end_pos]
        if "GREEN" in context_str:
            result["overall_rating"] = "GREEN"
        elif "AMBER" in context_str:
            result["overall_rating"] = "AMBER"
        else:
            result["overall_rating"] = "RED"
    
    # Also check recommended action
    if "DO NOT SIGN" in text_upper:
        result["overall_rating"] = "RED"
        result["recommended_action"] = "Do Not Sign"
    elif "NEGOTIATE FIRST" in text_upper:
        result["overall_rating"] = "AMBER"
        result["recommended_action"] = "Negotiate First"
    elif "REASONABLE TO SIGN" in text_upper:
        result["overall_rating"] = "GREEN"
        result["recommended_action"] = "Reasonable to Sign"
        
    # Extract executive summary
    if "EXECUTIVE SUMMARY" in text_upper:
        start = text_upper.find("EXECUTIVE SUMMARY") + len("EXECUTIVE SUMMARY")
        # Find the next major section
        next_sections = [
            "RISK SCORECARD",
            "CRITICAL RISKS", 
            "MODERATE RISKS",
            "LOW RISKS",
            "---"
        ]
        end = len(text)
        for section in next_sections:
            pos = text_upper.find(section, start)
            if pos != -1 and pos < end:
                end = pos
        summary_raw = text[start:end].strip()
        # Clean up leading hyphens or colons
        if summary_raw.startswith(":"):
            summary_raw = summary_raw[1:].strip()
        if summary_raw.startswith("---"):
            summary_raw = summary_raw[3:].strip()
        result["executive_summary"] = summary_raw
        
    # Extract individual risks using regex patterns (capturing emoji line in group 1)
    # Find all critical risks (🔴 markers)
    critical_pattern = r'(🔴[^\n]*RISK[^\n]*\n.*?)(?=🔴|🟡|🟢|MODERATE RISKS|LOW RISKS|NEGOTIATION|RED LINE|DISCLAIMER|$)'
    critical_matches = re.findall(critical_pattern, text, re.DOTALL)
    for match in critical_matches:
        risk_text = match.strip()
        if risk_text:
            result["critical_risks"].append(parse_single_risk(risk_text))
            
    # Find all moderate risks (🟡 markers)
    moderate_pattern = r'(🟡[^\n]*RISK[^\n]*\n.*?)(?=🔴|🟡|🟢|CRITICAL RISKS|LOW RISKS|NEGOTIATION|RED LINE|DISCLAIMER|$)'
    moderate_matches = re.findall(moderate_pattern, text, re.DOTALL)
    for match in moderate_matches:
        risk_text = match.strip()
        if risk_text:
            result["moderate_risks"].append(parse_single_risk(risk_text))
            
    # Find all low risks (🟢 markers)
    low_pattern = r'(🟢[^\n]*RISK[^\n]*\n.*?)(?=🔴|🟡|🟢|CRITICAL RISKS|MODERATE RISKS|NEGOTIATION|RED LINE|DISCLAIMER|$)'
    low_matches = re.findall(low_pattern, text, re.DOTALL)
    for match in low_matches:
        risk_text = match.strip()
        if risk_text:
            result["low_risks"].append(parse_single_risk(risk_text))
            
    # Also parse negotiation priorities and red line clauses if they exist in matches
    neg_match = re.search(r"NEGOTIATION PRIORITY LIST.*?\n(.*?)(?=\n(?:---|RED LINE|DISCLAIMER|$))", text, re.DOTALL | re.IGNORECASE)
    if neg_match:
        neg_text = neg_match.group(1).strip()
        neg_text_lines = [l.strip() for l in neg_text.split('\n') if l.strip()]
        for line in neg_text_lines:
            if line.upper().startswith("NEGOTIATION") or line.startswith("---") or line.startswith("Numbered list"):
                continue
            clean_line = re.sub(r'^(?:\d+\.|\-|\*|■)\s*', '', line).strip()
            if clean_line:
                result["negotiation_priorities"].append(clean_line)

    red_match = re.search(r"RED LINE CLAUSES.*?\n(.*?)(?=\n(?:---|DISCLAIMER|$))", text, re.DOTALL | re.IGNORECASE)
    if red_match:
        red_text = red_match.group(1).strip()
        if "No absolute red line clauses" not in red_text:
            parts = red_text.split('\n\n') if '\n\n' in red_text else red_text.split('\n')
            for part in parts:
                part = part.strip()
                if part and not part.startswith("---") and not part.upper().startswith("RED LINE"):
                    result["red_line_clauses"].append(part)
                    
    # Try simpler line-by-line extraction as fallback if no risks found via regex
    if not result["critical_risks"] and not result["moderate_risks"] and not result["low_risks"]:
        lines = text.split('\n')
        current_risk = None
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detect section changes
            if 'CRITICAL RISKS' in line.upper():
                current_section = 'critical'
            elif 'MODERATE RISKS' in line.upper():
                current_section = 'moderate'
            elif 'LOW RISKS' in line.upper():
                current_section = 'low'
            elif 'NEGOTIATION PRIORITY' in line.upper():
                current_section = 'negotiation'
            elif 'RED LINE' in line.upper():
                current_section = 'red_line'
                
            # Detect risk starter lines
            elif (line.startswith('🔴') or line.startswith('🟡') or line.startswith('🟢') or 
                  ('RISK' in line.upper() and current_section in ['critical', 'moderate', 'low'])):
                if current_risk:
                    if current_section == 'critical':
                        result["critical_risks"].append(current_risk)
                    elif current_section == 'moderate':
                        result["moderate_risks"].append(current_risk)
                    elif current_section == 'low':
                        result["low_risks"].append(current_risk)
                
                clean_title = line
                for emoji in ['🔴', '🟡', '🟢']:
                    clean_title = clean_title.replace(emoji, '')
                clean_title = clean_title.strip()
                clean_title = re.sub(r'^RISK\s*\d+\s*:\s*', '', clean_line, flags=re.IGNORECASE)
                
                current_risk = {
                    "title": clean_title,
                    "clause": "",
                    "law": "",
                    "explanation": "",
                    "impact": "",
                    "action": ""
                }
            elif current_risk:
                if line.startswith('Clause:'):
                    current_risk["clause"] = line.split('Clause:', 1)[-1].strip()
                elif line.startswith('Law violated:'):
                    current_risk["law"] = line.split('Law violated:', 1)[-1].strip()
                elif line.lower().startswith('plain english:'):
                    current_risk["explanation"] = line.split(':', 1)[-1].strip()
                elif line.startswith('Financial impact:'):
                    current_risk["impact"] = line.split('Financial impact:', 1)[-1].strip()
                elif line.startswith('What to do:'):
                    current_risk["action"] = line.split('What to do:', 1)[-1].strip()
            elif current_section == 'negotiation':
                if line and not line.upper().startswith('NEGOTIATION') and not line.startswith('---'):
                    clean_line = re.sub(r'^(?:\d+\.|\-|\*|■)\s*', '', line).strip()
                    if clean_line:
                        result["negotiation_priorities"].append(clean_line)
            elif current_section == 'red_line':
                if line and not line.upper().startswith('RED LINE') and "No absolute red line clauses" not in line and not line.startswith('---'):
                    result["red_line_clauses"].append(line)
        
        # Add last risk if exists
        if current_risk and current_section:
            if current_section == 'critical':
                result["critical_risks"].append(current_risk)
            elif current_section == 'moderate':
                result["moderate_risks"].append(current_risk)
            elif current_section == 'low':
                result["low_risks"].append(current_risk)
                
    return result


def parse_single_risk(text: str) -> dict:
    """Extract structured data from a single risk text block."""
    risk = {
        "title": "",
        "clause": "",
        "law": "",
        "explanation": "",
        "impact": "",
        "action": ""
    }
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('Clause:'):
            risk["clause"] = line.split('Clause:', 1)[-1].strip()
        elif line.startswith('Law violated:'):
            risk["law"] = line.split('Law violated:', 1)[-1].strip()
        elif line.lower().startswith('plain english:'):
            risk["explanation"] = line.split(':', 1)[-1].strip()
        elif line.startswith('Financial impact:'):
            risk["impact"] = line.split('Financial impact:', 1)[-1].strip()
        elif line.startswith('What to do:'):
            risk["action"] = line.split('What to do:', 1)[-1].strip()
        else:
            # Set title to first line that doesn't start with known prefixes, cleaned of emojis and risk prefixes
            clean_line = line
            for emoji in ['🔴', '🟡', '🟢']:
                clean_line = clean_line.replace(emoji, '')
            clean_line = clean_line.strip()
            clean_line = re.sub(r'^RISK\s*\d+\s*:\s*', '', clean_line, flags=re.IGNORECASE)
            if not risk["title"]:
                risk["title"] = clean_line
    return risk

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

def _color_to_hex(color_obj):
    """Convert a ReportLab color object to a hex string for use in HTML."""
    if color_obj == RED: return RED_HEX
    if color_obj == AMBER: return AMBER_HEX
    if color_obj == GREEN: return GREEN_HEX
    if color_obj == NAVY: return NAVY_HEX
    if color_obj == GOLD: return GOLD_HEX
    return GREY_HEX

def make_risk_table(risk, stripe_color, styles):
    if isinstance(risk, str):
        risk = parse_single_risk(risk)
        
    title = risk.get("title", "").strip()
    stripe_hex = _color_to_hex(stripe_color)
    
    normal = styles['Normal']
    navy_bold = ParagraphStyle('NavyBoldRisk', parent=normal, fontName='Helvetica-Bold', textColor=NAVY)
    grey_label = f"<font color='{GREY_HEX}'>%s</font>"
    
    content = []
    if title:
        content.append(Paragraph(title, navy_bold))
        content.append(Spacer(1, 4))
        
    if risk.get("clause"):
        content.append(Paragraph(f"{grey_label % 'Clause:'} <font color='{NAVY_HEX}'>{html.escape(risk['clause'])}</font>", normal))
        content.append(Spacer(1, 4))
        
    if risk.get("law"):
        content.append(Paragraph(f"{grey_label % 'Law violated:'} <font color='{stripe_hex}'>{html.escape(risk['law'])}</font>", normal))
        content.append(Spacer(1, 4))
        
    if risk.get("explanation"):
        content.append(Paragraph(f"<b>Plain English:</b> {html.escape(risk['explanation'])}", normal))
        content.append(Spacer(1, 4))
        
    if risk.get("impact"):
        content.append(Paragraph(f"<b>Financial impact:</b> {html.escape(risk['impact'])}", normal))
        content.append(Spacer(1, 4))
        
    if risk.get("action"):
        t = Table([[Paragraph(f"<b>What to do:</b> {html.escape(risk['action'])}", normal)]], style=[
            ('BACKGROUND', (0,0), (0,0), HexColor("#FFF8E1")),
            ('TOPPADDING', (0,0), (0,0), 6),
            ('BOTTOMPADDING', (0,0), (0,0), 6),
            ('LEFTPADDING', (0,0), (0,0), 8),
            ('RIGHTPADDING', (0,0), (0,0), 8),
        ])
        content.append(t)
        
    # Remove trailing spacer if present
    if content and isinstance(content[-1], Spacer):
        content.pop()
        
    if not content:
        return Paragraph("", normal)
            
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
    parsed = parse_analysis_results(text)
    
    buffer = io.BytesIO()
    doc = BORADocTemplate(buffer, parsed['document_type'], pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    
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
    card_content.append(Paragraph(parsed['document_type'].upper(), navy_24_bold_center))
    card_content.append(Spacer(1, 10))
    card_content.append(HRFlowable(width="80%", thickness=1, color=GOLD))
    card_content.append(Spacer(1, 20))
    
    cw = (A4[0]-100)/3
    t_data = [
        [Paragraph("Analysis Date", grey_10_center), Paragraph("Analysis Depth", grey_10_center), Paragraph("Reference", grey_10_center)],
        [Paragraph(parsed['analysis_date'], navy_12_bold_center), Paragraph(parsed['analysis_depth'], navy_12_bold_center), Paragraph(parsed['reference'], navy_12_bold_center)]
    ]
    card_content.append(Table(t_data, colWidths=[cw, cw, cw]))
    card_content.append(Spacer(1, 30))
    
    if parsed["overall_rating"] == "RED":
        rating_text = "HIGH RISK"
        rating_color = RED
    elif parsed["overall_rating"] == "AMBER":
        rating_text = "MODERATE RISK"
        rating_color = AMBER
    else:
        rating_text = "LOW RISK"
        rating_color = GREEN
        
    badge_table = Table([[Paragraph(rating_text, white_14_bold_center)]], colWidths=[200], rowHeights=[40])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), rating_color),
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
    t = Table([[Paragraph("EXECUTIVE SUMMARY", white_14_bold)]], colWidths=[A4[0]-100], style=[
        ('BACKGROUND', (0,0), (0,0), NAVY), 
        ('LEFTPADDING', (0,0), (0,0), 10),
        ('TOPPADDING', (0,0), (0,0), 6),
        ('BOTTOMPADDING', (0,0), (0,0), 6)
    ])
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
        
    critical_count = len(parsed["critical_risks"])
    moderate_count = len(parsed["moderate_risks"])
    low_count = len(parsed["low_risks"])
    total = critical_count + moderate_count + low_count
    
    sb = Table([[ 
        make_score_box("Total Risks", total, NAVY),
        make_score_box("Critical/Red", critical_count, RED),
        make_score_box("Moderate/Amber", moderate_count, AMBER),
        make_score_box("Low/Green", low_count, GREEN)
    ]], style=[('ALIGN', (0,0), (-1,-1), 'CENTER')])
    elements.append(sb)
    elements.append(Spacer(1, 20))
    
    action_bg = HexColor("#FFEBEE") if parsed['overall_rating'] == "RED" else (HexColor("#FFF3E0") if parsed['overall_rating'] == "AMBER" else HexColor("#E8F5E9"))
    if parsed['overall_rating'] == "RED": action_text = "⛔ DO NOT SIGN — This document contains critical legal violations that must be addressed before signing."
    elif parsed['overall_rating'] == "AMBER": action_text = "⚠️ NEGOTIATE FIRST — Review and negotiate flagged clauses before signing."
    else: action_text = "✅ REASONABLE TO SIGN — Standard legal review recommended."
    
    t = Table([[Paragraph(action_text, normal)]], colWidths=[A4[0]-100], style=[
        ('BACKGROUND', (0,0), (0,0), action_bg),
        ('PADDING', (0,0), (0,0), 12),
    ])
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    if parsed['executive_summary']:
        elements.append(Paragraph(parsed['executive_summary'], ParagraphStyle('ES', parent=normal, fontSize=11, textColor=DARK_GREY)))
        elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("<b>Table of Contents</b>", ParagraphStyle('TOC_Title', parent=normal, fontSize=12, textColor=NAVY)))
    elements.append(Spacer(1, 10))
    
    toc_items = ["1. Executive Summary"]
    if total == 0 and len(text) > 100:
        toc_items.append("2. Analysis Results")
    else:
        if parsed['critical_risks']: toc_items.append(f"{len(toc_items)+1}. Critical Risks")
        if parsed['moderate_risks']: toc_items.append(f"{len(toc_items)+1}. Moderate Risks")
        if parsed['low_risks']: toc_items.append(f"{len(toc_items)+1}. Low Risks")
    if parsed['negotiation_priorities']: toc_items.append(f"{len(toc_items)+1}. Negotiation Priority List")
    if parsed['red_line_clauses']: toc_items.append(f"{len(toc_items)+1}. Red Line Clauses")
    
    for item in toc_items:
        elements.append(Paragraph(item, normal))
    
    elements.append(PageBreak())
    
    # ---------------- RISK SECTIONS ----------------
    def add_risk_section_new(banner_text, risks, color):
        t = Table([[Paragraph(banner_text, white_13_bold)]], colWidths=[A4[0]-100], style=[
            ('BACKGROUND', (0,0), (0,0), NAVY), 
            ('LEFTPADDING', (0,0), (0,0), 10),
            ('TOPPADDING', (0,0), (0,0), 6),
            ('BOTTOMPADDING', (0,0), (0,0), 6)
        ])
        elements.append(t)
        elements.append(Spacer(1, 15))
        
        if not risks:
            risk_label = "critical" if color == RED else ("moderate" if color == AMBER else "low")
            elements.append(Paragraph(f"No {risk_label} risks identified in this document.", normal))
            elements.append(Spacer(1, 15))
        else:
            for risk in risks:
                elements.append(make_risk_table(risk, color, styles))
                elements.append(Spacer(1, 8))
            elements.append(Spacer(1, 10))
            elements.append(HRFlowable(width="100%", thickness=0.5, color=GOLD))
            elements.append(Spacer(1, 15))
            
    if total == 0 and len(text) > 100:
        # Fallback: render raw results as text
        elements.append(Table([[Paragraph("ANALYSIS RESULTS", white_14_bold)]], colWidths=[A4[0]-100], style=[
            ('BACKGROUND', (0,0), (0,0), NAVY), 
            ('LEFTPADDING', (0,0), (0,0), 10),
            ('TOPPADDING', (0,0), (0,0), 6),
            ('BOTTOMPADDING', (0,0), (0,0), 6)
        ]))
        elements.append(Spacer(1, 15))
        
        for line in text.split('\n'):
            line = line.strip()
            if line:
                elements.append(Paragraph(html.escape(line), normal))
                elements.append(Spacer(1, 4))
    else:
        add_risk_section_new("CRITICAL RISKS — Must Address Before Signing", parsed['critical_risks'], RED)
        add_risk_section_new("MODERATE RISKS — Should Negotiate", parsed['moderate_risks'], AMBER)
        add_risk_section_new("LOW RISKS — Acceptable Clauses", parsed['low_risks'], GREEN)
        
    # ---------------- NEGOTIATION PRIORITY LIST ----------------
    if parsed['negotiation_priorities']:
        t = Table([[Paragraph("NEGOTIATION PRIORITY LIST", white_13_bold)]], colWidths=[A4[0]-100], style=[
            ('BACKGROUND', (0,0), (0,0), NAVY), 
            ('LEFTPADDING', (0,0), (0,0), 10),
            ('TOPPADDING', (0,0), (0,0), 6),
            ('BOTTOMPADDING', (0,0), (0,0), 6)
        ])
        elements.append(t)
        elements.append(Spacer(1, 15))
        
        n_data = []
        for i, item in enumerate(parsed['negotiation_priorities']):
            bullet = Paragraph(f"<font color='{GOLD_HEX}'>■</font> {i+1}.", normal)
            text_p = Paragraph(html.escape(item), normal)
            n_data.append([bullet, text_p])
            
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
    if parsed['red_line_clauses']:
        t = Table([[Paragraph("⚠️ RED LINE CLAUSES — Do not sign if these are not removed", white_13_bold)]], colWidths=[A4[0]-100], style=[
            ('BACKGROUND', (0,0), (0,0), RED), 
            ('LEFTPADDING', (0,0), (0,0), 10),
            ('TOPPADDING', (0,0), (0,0), 6),
            ('BOTTOMPADDING', (0,0), (0,0), 6)
        ])
        elements.append(t)
        elements.append(Spacer(1, 15))
        
        for r in parsed['red_line_clauses']:
            rt = Table([[Paragraph(html.escape(r), ParagraphStyle('R', parent=normal, textColor=RED, fontName='Helvetica-Bold'))]], colWidths=[A4[0]-100], style=[
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
