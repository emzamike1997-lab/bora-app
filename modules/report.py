import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER

NAVY = colors.HexColor("#1B2A4A")
GOLD = colors.HexColor("#C9A84C")
RED_COLOR = colors.HexColor("#C62828")
AMBER_COLOR = colors.HexColor("#F57C00")
GREEN_COLOR = colors.HexColor("#2E7D32")
DGREY = colors.HexColor("#2C2C2C")


def generate_pdf_report(results_text, doc_type="Legal Document", analysis_depth="Standard"):
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
    
    title_style = ParagraphStyle(
        'BTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=NAVY,
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    subtitle_style = ParagraphStyle(
        'BSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=GOLD,
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    heading_style = ParagraphStyle(
        'BHeading',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=NAVY,
        spaceBefore=14,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )
    sub_style = ParagraphStyle(
        'BSub',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=NAVY,
        spaceBefore=8,
        spaceAfter=4,
        fontName='Helvetica-Bold'
    )
    normal_style = ParagraphStyle(
        'BNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=DGREY,
        spaceAfter=5,
        fontName='Helvetica',
        leading=14
    )
    label_style = ParagraphStyle(
        'BLabel',
        parent=styles['Normal'],
        fontSize=10,
        textColor=DGREY,
        spaceAfter=3,
        fontName='Helvetica',
        leading=14
    )
    meta_style = ParagraphStyle(
        'BMeta',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )
    footer_style = ParagraphStyle(
        'BFooter',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )
    url_style = ParagraphStyle(
        'BURL',
        parent=styles['Normal'],
        fontSize=8,
        textColor=GOLD,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    story = []

    # HEADER
    story.append(Spacer(1, 10))
    story.append(Paragraph("BORA", title_style))
    story.append(Paragraph(
        "Legal Document Risk Analysis Report",
        subtitle_style
    ))
    story.append(HRFlowable(
        width="100%", thickness=2, color=GOLD))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Document Type: {doc_type}  |  "
        f"Depth: {analysis_depth}  |  "
        f"Date: {datetime.now().strftime('%d %B %Y')}  |  "
        f"Ref: BORA-{datetime.now().strftime('%H%M%S')}",
        meta_style
    ))
    story.append(Spacer(1, 16))
    story.append(HRFlowable(
        width="100%", thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 12))

    # CONTENT
    if not results_text or len(results_text.strip()) == 0:
        story.append(Paragraph(
            "No analysis results available.", normal_style))
    else:
        for line in results_text.split('\n'):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 3))
                continue

            upper = line.upper()

            # Section headers
            if any(h in upper for h in [
                'CRITICAL RISKS', 'MODERATE RISKS',
                'LOW RISKS', 'NEGOTIATION PRIORITY',
                'RED LINE CLAUSES', 'EXECUTIVE SUMMARY',
                'RISK SCORECARD', 'RECOMMENDED NEXT STEPS',
                'SUMMARY', 'NEGOTIATION PRIORITY LIST'
            ]):
                story.append(Spacer(1, 6))
                story.append(HRFlowable(
                    width="100%", thickness=1,
                    color=colors.lightgrey))
                story.append(Paragraph(line, heading_style))
                continue

            # Risk emoji lines
            if line.startswith('\U0001f534'):
                clean = line.replace('\U0001f534', '').strip()
                story.append(Paragraph(
                    '<font color="#C62828"><b>&#9632; ' +
                    clean + '</b></font>',
                    sub_style
                ))
                continue

            if line.startswith('\U0001f7e1'):
                clean = line.replace('\U0001f7e1', '').strip()
                story.append(Paragraph(
                    '<font color="#F57C00"><b>&#9632; ' +
                    clean + '</b></font>',
                    sub_style
                ))
                continue

            if line.startswith('\U0001f7e2'):
                clean = line.replace('\U0001f7e2', '').strip()
                story.append(Paragraph(
                    '<font color="#2E7D32"><b>&#9632; ' +
                    clean + '</b></font>',
                    sub_style
                ))
                continue

            # Label lines
            for label in [
                'Clause:', 'Law violated:',
                'Plain English:', 'Financial impact:',
                'What to do:', 'Concern:',
                'Risk title:', 'What it means'
            ]:
                if line.startswith(label):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        story.append(Paragraph(
                            '<b>' + parts[0] + ':</b> ' +
                            parts[1].strip(),
                            label_style
                        ))
                    else:
                        story.append(Paragraph(
                            line, label_style))
                    break
            else:
                # Disclaimer
                if 'IMPORTANT DISCLAIMER' in upper:
                    story.append(Spacer(1, 12))
                    story.append(HRFlowable(
                        width="100%", thickness=2,
                        color=GOLD))
                    story.append(Spacer(1, 6))
                    story.append(Paragraph(
                        'IMPORTANT DISCLAIMER',
                        ParagraphStyle(
                            'DH',
                            parent=styles['Normal'],
                            fontSize=10,
                            textColor=NAVY,
                            fontName='Helvetica-Bold',
                            alignment=TA_CENTER
                        )
                    ))
                    continue
                # Default
                story.append(Paragraph(line, normal_style))

    # FOOTER
    story.append(Spacer(1, 20))
    story.append(HRFlowable(
        width="100%", thickness=2, color=GOLD))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "BORA is not a law firm and does not provide legal advice. "
        "This analysis is generated by AI for informational purposes only. "
        "Always consult a qualified South African attorney.",
        footer_style
    ))
    story.append(Paragraph(
        "bora-analysis.streamlit.app  |  © 2026 BORA",
        url_style
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


import resend


def send_pdf_email(
    to_email,
    pdf_bytes,
    doc_type="Legal Document"):

    import os
    import base64

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        return False, "No email API key configured"

    resend.api_key = api_key

    from_email = os.getenv(
        "RESEND_FROM_EMAIL",
        "BORA Reports <reports@bora-analysis.co.za>"
    )

    try:
        pdf_base64 = base64.b64encode(
            pdf_bytes).decode()

        params = {
            "from": from_email,
            "to": [to_email],
            "subject": f"Your BORA {doc_type} Report",
            "html": """
            <div style='font-family: Arial, sans-serif;
                        max-width: 600px; margin: 0 auto;'>
                <div style='background: #1B2A4A;
                            padding: 24px;
                            text-align: center;'>
                    <h1 style='color: #C9A84C;
                               margin: 0;'>BORA</h1>
                    <p style='color: white; margin: 8px 0 0;'>
                        Legal Document Analysis
                    </p>
                </div>
                <div style='padding: 24px;
                            background: #f9f9f9;'>
                    <h2 style='color: #1B2A4A;'>
                        Your Analysis Report is Ready
                    </h2>
                    <p style='color: #555;'>
                        Please find your BORA risk analysis
                        report attached to this email.
                    </p>
                    <p style='color: #555;'>
                        This report identifies potential legal
                        risks in your document and provides
                        recommended actions for each risk found.
                    </p>
                    <div style='background: #FFF8E1;
                                border-left: 4px solid #F57C00;
                                padding: 12px 16px;
                                margin: 16px 0;'>
                        <strong>Important:</strong> This analysis
                        is for informational purposes only and
                        does not constitute legal advice.
                        Always consult a qualified South African
                        attorney for legal matters.
                    </div>
                </div>
                <div style='background: #1B2A4A;
                            padding: 16px;
                            text-align: center;'>
                    <p style='color: #C9A84C;
                               margin: 0;
                               font-size: 12px;'>
                        bora-analysis.streamlit.app
                    </p>
                    <p style='color: white;
                               margin: 4px 0 0;
                               font-size: 11px;'>
                        BORA is not a law firm and does not
                        provide legal advice.
                    </p>
                </div>
            </div>
            """,
            "attachments": [
                {
                    "filename": "BORA_Analysis_Report.pdf",
                    "content": pdf_base64,
                    "type": "application/pdf"
                }
            ]
        }

        response = resend.Emails.send(params)

        if response and hasattr(response, 'id'):
            return True, "Email sent successfully"
        else:
            return False, "Email send failed"

    except Exception as e:
        return False, str(e)
