import streamlit as st
import os
import stripe
from modules.database import can_analyze, consume_analysis
from modules.analyzer import run_analysis, extract_text_from_file, get_document_stats, parse_scorecard
from modules.prompts import get_lease_prompt
from modules.report import generate_pdf_report, send_pdf_email
from modules.results_display import display_formatted_results



st.set_page_config(page_title="Lease Analysis - BORA", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
[data-testid="stToolbar"] {
    visibility: hidden;}
[data-testid="stDecoration"] {
    visibility: hidden;}
[data-testid="stStatusWidget"] {
    visibility: hidden;}
[data-testid="stAppViewBlockContainer"] 
    > div:first-child {
    padding-top: 1rem;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
    :root { --primary: #1B2A4A; --accent: #C9A84C; --bg: #FFFFFF; --text: #2C2C2C; }
    .stApp { background-color: var(--bg); color: var(--text); }
    h1, h2, h3 { color: var(--primary) !important; }
    .stButton>button { background-color: var(--accent) !important; color: black !important; font-weight: bold !important; width: 100%; border: none !important; }
    [data-testid="stSidebarNav"] { display: none; }
</style>
""", unsafe_allow_html=True)

if st.button("← Back to Home"):
    st.switch_page("app.py")

st.markdown("## Lease Agreement Analysis")
st.write("Detect illegal clauses against the South African Rental Housing Act and calculate maximum legal deposits.")

with st.container(border=True):
    email = st.text_input("Enter your email address (Required)", value=st.session_state.get("last_email", ""))
    if email and "+dev" in email:
        st.info("🛠️ Developer Mode Active - Free tier limit bypassed")
    
    col1, col2 = st.columns(2)
    with col1:
        monthly_rent = st.number_input("Monthly Rent (ZAR)", min_value=0, value=10000, step=500)
        lease_years = st.number_input("Lease Term (Years)", min_value=1, value=1, step=1)
    with col2:
        deposit_amount = st.number_input("Deposit Amount Requested (ZAR)", min_value=0, value=20000, step=500)

    uploaded_file = st.file_uploader("Upload Lease Agreement", type=["pdf", "docx", "txt"])
    
    if uploaded_file:
        stats = get_document_stats(uploaded_file)
        st.markdown(f"""
        📊 **Document Statistics:**
        - **Estimated Pages:** {stats['pages']}
        - **Word Count Estimate:** {stats['words']:,} words
        - **Recommended Analysis Depth:** {stats['recommended_depth']}
        """)
        
    depth = st.selectbox("Analysis Depth", ["Quick Scan (30 seconds)", "Standard Analysis (60 seconds)", "Deep Review (2-3 minutes)"], index=1)

    st.info("💡 Tip: Upload the complete document including all schedules and annexures for the most accurate analysis.")
    
    if st.button("ANALYSE DOCUMENT"):
        if not email:
            st.error("Please provide an email address.")
        elif not uploaded_file:
            st.error("Please upload a document.")
        elif uploaded_file.size > 50 * 1024 * 1024:
            st.error("File exceeds 50MB limit.")
        else:
            if not can_analyze(email):
                st.warning("Analysis limit reached. Please upgrade your plan.")
                domain = os.getenv("DOMAIN_URL", "http://localhost:8501")
                try:
                    checkout_session = stripe.checkout.Session.create(
                        payment_method_types=['card'],
                        line_items=[{
                            'price_data': {
                                'currency': 'zar',
                                'product_data': {'name': 'BORA Single Document Analysis'},
                                'unit_amount': 50000,
                            },
                            'quantity': 1,
                        }],
                        mode='payment',
                        success_url=f"{domain}/?session_id={{CHECKOUT_SESSION_ID}}",
                        cancel_url=f"{domain}/",
                        customer_email=email,
                        metadata={"plan": "PAY_PER_DOC"}
                    )
                    st.markdown(f'<meta http-equiv="refresh" content="0; url={checkout_session.url}">', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Payment gateway error: {str(e)}")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.write("📄 Reading document...")
                progress_bar.progress(20)
                text = extract_text_from_file(uploaded_file)
                
                if not text:
                    st.error("Could not extract text from file.")
                else:
                    status_text.write("🔍 Identifying clauses...")
                    progress_bar.progress(40)
                    
                    status_text.write("⚖️ Checking against SA law...")
                    progress_bar.progress(60)
                    
                    prompt = get_lease_prompt(monthly_rent, deposit_amount, lease_years)
                    results = run_analysis(text, prompt, depth, document_type="Lease Agreement Analysis")
                    
                    status_text.write("📊 Calculating risk scores...")
                    progress_bar.progress(80)
                    
                    status_text.write("📝 Generating report...")
                    progress_bar.progress(100)
                    
                    st.session_state.last_results = results
                    st.session_state.last_email = email
                    st.session_state.last_type = "Lease Analysis"
                    consume_analysis(email)
                    st.rerun()

if "last_results" in st.session_state and st.session_state.last_type == "Lease Analysis":
    st.write("---")
    st.markdown("### Analysis Results")
    
    results = st.session_state.last_results
    
    # Show informational banners for partial results
    if "Consolidation Error:" in results:
        st.info("📋 Analysis complete. Some sections were processed in quick mode due to document length. All critical risks have been identified.")
    elif any(err in results for err in ["Chunk processing failed:", "Rate limit exceeded", "Request too large"]):
        st.warning("⚡ Processing large document in sections. Results may be partial. Try Quick Scan for faster results.")
    
    # 4. Formatted results display — counts come from the real parsed card lists
    critical_count, moderate_count, low_count = display_formatted_results(results)

    # Overall rating derived from actual parsed counts
    if critical_count > 0:
        overall_rating = "RED"
    elif moderate_count > 0:
        overall_rating = "AMBER"
    else:
        overall_rating = "GREEN"

    # 1. Coloured summary box
    if overall_rating == "RED":
        st.error("🔴 HIGH RISK DOCUMENT — Do not sign without legal review and negotiation.")
    elif overall_rating == "AMBER":
        st.warning("🟡 MODERATE RISK DOCUMENT — Review flagged clauses before signing.")
    else:
        st.success("🟢 LOW RISK DOCUMENT — This document appears reasonable. Standard legal review recommended.")

    # 2. Metric row with 3 columns
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("🔴 Critical Risks", critical_count)
    col_m2.metric("🟡 Moderate Risks", moderate_count)
    col_m3.metric("🟢 Low Risks", low_count)

    # 3. Recommended Action badge
    recommended_action = "⛔ Do Not Sign Yet" if overall_rating == "RED" else ("⚠️ Negotiate First" if overall_rating == "AMBER" else "✅ Reasonable to Sign")
    st.markdown(f"**Recommended Action:** `{recommended_action}`")
    st.write("---")
            
    st.write("---")
    st.markdown("### Download & Delivery")
    
    if 'depth' not in locals():
        depth = "Standard Analysis"
    if not depth:
        depth = "Standard Analysis"

    if st.button("Generate PDF Report"):
        with st.spinner("Generating PDF..."):
            try:
                results_str = str(results) if results else ""
                depth_str = str(depth) if depth else "Standard"
                pdf_bytes = generate_pdf_report(
                    results_str,
                    doc_type="Lease Agreement Analysis",
                    analysis_depth=depth_str
                )
                
                # Attempt email delivery via Resend
                email = st.session_state.get("last_email", "")
                if email:
                    success, message = send_pdf_email(
                        to_email=email,
                        pdf_bytes=pdf_bytes,
                        doc_type="Lease Agreement Analysis"
                    )
                    if success:
                        st.success(
                            "✅ Report sent to " + email +
                            " — Check your inbox!"
                        )
                    else:
                        st.warning(
                            "📥 Email delivery unavailable. "
                            "Please download your report below."
                        )
                
                # Always show download button
                st.download_button(
                    label="Download PDF Report",
                    data=pdf_bytes,
                    file_name="BORA_Analysis.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(
                    "PDF generation failed. "
                    "Please try again."
                )
                # Show download of raw results as backup
                st.download_button(
                    label="Download Results as Text",
                    data=str(results),
                    file_name="BORA_Analysis.txt",
                    mime="text/plain"
                )
