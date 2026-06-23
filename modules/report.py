"""
BORA PDF Report Generator
Simple reliable version
"""
import io
import os
import base64
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import (
    getSampleStyleSheet, ParagraphStyle)
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, 
    Spacer, HRFlowable)
from reportlab.lib.enums import (
    TA_LEFT, TA_CENTER, TA_RIGHT)

# Sendgrid imports needed for send_report_email
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

NAVY = colors.HexColor("#1B2A4A")
GOLD = colors.HexColor("#C9A84C")
RED = colors.HexColor("#C62828")
AMBER = colors.HexColor("#F57C00")
GREEN = colors.HexColor("#2E7D32")
LGREY = colors.HexColor("#F8F9FA")
DGREY = colors.HexColor("#2C2C2C")


def generate_pdf_report(
    results_text, 
    doc_type="Legal Document",
    analysis_depth="Standard"):
    """
    Generate a professional PDF report.
    Takes the raw results text and 
    formats it into a clean PDF.
    Always produces content regardless 
    of text format.
    """
    
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )
    
    styles = getSampleStyleSheet()
    
    # Define styles
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=NAVY,
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'Heading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=NAVY,
        spaceBefore=12,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )
    
    subheading_style = ParagraphStyle(
        'SubHeading',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=NAVY,
        spaceBefore=8,
        spaceAfter=4,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=DGREY,
        spaceAfter=6,
        fontName='Helvetica',
        leading=14
    )
    
    small_style = ParagraphStyle(
        'Small',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        fontName='Helvetica'
    )
    
    story = []
    
    # HEADER
    story.append(Paragraph(
        "BORA", title_style))
    story.append(Paragraph(
        "Legal Document Risk Analysis Report",
        ParagraphStyle(
            'Sub',
            parent=styles['Normal'],
            fontSize=12,
            textColor=GOLD,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
    ))
    story.append(HRFlowable(
        width="100%",
        thickness=2,
        color=GOLD
    ))
    story.append(Spacer(1, 6))
    
    # META INFO
    meta = (
        f"Document Type: {doc_type}  |  "
        f"Analysis Depth: {analysis_depth}  |  "
        f"Date: {datetime.now().strftime('%d %B %Y')}  |  "
        f"Reference: BORA-{datetime.now().strftime('%H%M%S')}"
    )
    story.append(Paragraph(meta, small_style))
    story.append(Spacer(1, 12))
    story.append(HRFlowable(
        width="100%",
        thickness=1,
        color=colors.lightgrey
    ))
    story.append(Spacer(1, 12))
    
    # RESULTS CONTENT
    # Simply render the results text
    # line by line with smart formatting
    
    if not results_text or len(
        results_text.strip()) == 0:
        story.append(Paragraph(
            "No analysis results available.",
            normal_style
        ))
    else:
        lines = results_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 4))
                continue
            
            # Detect and style different 
            # line types
            line_upper = line.upper()
            
            # Major section headers
            if any(header in line_upper for header in [
                'CRITICAL RISKS',
                'MODERATE RISKS', 
                'LOW RISKS',
                'NEGOTIATION PRIORITY',
                'RED LINE CLAUSES',
                'EXECUTIVE SUMMARY',
                'RISK SCORECARD',
                'RECOMMENDED NEXT STEPS',
                'SUMMARY'
            ]):
                story.append(Spacer(1, 8))
                story.append(HRFlowable(
                    width="100%",
                    thickness=1,
                    color=colors.lightgrey
                ))
                story.append(Paragraph(
                    line, heading_style))
                continue
            
            # Risk items with emoji
            if line.startswith('🔴'):
                clean = line.replace(
                    '🔴', '').strip()
                story.append(Paragraph(
                    f'<font color="#C62828">'
                    f'&#9632;</font> '
                    f'<b>{clean}</b>',
                    subheading_style
                ))
                continue
                
            if line.startswith('🟡'):
                clean = line.replace(
                    '🟡', '').strip()
                story.append(Paragraph(
                    f'<font color="#F57C00">'
                    f'&#9632;</font> '
                    f'<b>{clean}</b>',
                    subheading_style
                ))
                continue
                
            if line.startswith('🟢'):
                clean = line.replace(
                    '🟢', '').strip()
                story.append(Paragraph(
                    f'<font color="#2E7D32">'
                    f'&#9632;</font> '
                    f'<b>{clean}</b>',
                    subheading_style
                ))
                continue
            
            # Bold labels
            if any(line.startswith(label) 
                   for label in [
                'Clause:', 'Law violated:',
                'What it means', 
                'Financial impact:',
                'What to do:',
                'Concern:', 'Risk title:'
            ]):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    formatted = (
                        f'<b>{parts[0]}:</b>'
                        f'{parts[1]}'
                    )
                    story.append(Paragraph(
                        formatted, normal_style))
                    continue
            
            # Numbered list items
            if (len(line) > 2 and 
                line[0].isdigit() and 
                line[1] in '.):'):
                story.append(Paragraph(
                    line, normal_style))
                continue
            
            # Disclaimer section
            if 'IMPORTANT DISCLAIMER' in line_upper:
                story.append(Spacer(1, 12))
                story.append(HRFlowable(
                    width="100%",
                    thickness=2,
                    color=GOLD
                ))
                story.append(Spacer(1, 6))
                story.append(Paragraph(
                    'IMPORTANT DISCLAIMER',
                    ParagraphStyle(
                        'Disc',
                        parent=styles['Normal'],
                        fontSize=10,
                        textColor=NAVY,
                        fontName='Helvetica-Bold',
                        alignment=TA_CENTER
                    )
                ))
                continue
            
            # Default: normal text
            story.append(Paragraph(
                line, normal_style))
    
    # FOOTER
    story.append(Spacer(1, 20))
    story.append(HRFlowable(
        width="100%",
        thickness=2,
        color=GOLD
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "BORA is not a law firm and does not "
        "provide legal advice. This analysis "
        "is generated by AI for informational "
        "purposes only. Always consult a "
        "qualified South African attorney "
        "for legal matters.",
        ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER,
            fontName='Helvetica'
        )
    ))
    story.append(Paragraph(
        "bora-analysis.streamlit.app  |  "
        "© 2026 BORA",
        ParagraphStyle(
            'Footer2',
            parent=styles['Normal'],
            fontSize=8,
            textColor=GOLD,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
    ))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.read()


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
