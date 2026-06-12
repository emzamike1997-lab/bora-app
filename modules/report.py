import io
import os
import html
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import base64

def generate_pdf_report(text: str) -> bytes:
    """Generates a professionally styled PDF report for BORA."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    
    styles = getSampleStyleSheet()
    
    # BORA Custom Styles
    title_style = ParagraphStyle(
        'BoraTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=HexColor('#1B2A4A'), # Deep Navy
        spaceAfter=20,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'BoraHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=HexColor('#C9A84C'), # Gold
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'BoraNormal',
        parent=styles['Normal'],
        fontSize=11,
        leading=16,
        textColor=HexColor('#2C2C2C'),
        spaceAfter=10,
        fontName='Helvetica'
    )

    red_flag_style = ParagraphStyle(
        'BoraRed',
        parent=styles['Normal'],
        fontSize=11,
        leading=16,
        textColor=HexColor('#C62828'), # Danger Red
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )

    elements = []
    
    # Title
    elements.append(Paragraph("BORA Risk Analysis Report", title_style))
    elements.append(Spacer(1, 20))

    escaped_text = html.escape(text)
    
    for line in escaped_text.split("\n"):
        line = line.strip()
        if not line:
            elements.append(Spacer(1, 10))
            continue
            
        # Try to apply semantic styling based on BORA output format
        if line.isupper() and len(line) < 50:
            elements.append(Paragraph(line, heading_style))
        elif line.startswith("[RED"):
            elements.append(Paragraph(line, red_flag_style))
        elif "CRITICAL RISKS" in line:
            elements.append(Paragraph(line, heading_style))
        elif line.startswith("-"):
            # Indent bullet points
            bullet_style = ParagraphStyle('Bullet', parent=normal_style, leftIndent=20)
            elements.append(Paragraph(line, bullet_style))
        else:
            elements.append(Paragraph(line, normal_style))
            
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes

def send_report_email(to_email: str, pdf_bytes: bytes, document_type: str):
    """Sends the PDF report via SendGrid."""
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
