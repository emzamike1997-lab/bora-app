import streamlit as st
import os
import stripe
from modules.database import can_analyze, consume_analysis
from modules.analyzer import run_analysis, extract_text_from_file
from modules.prompts import get_contract_risk_prompt
from modules.report import generate_pdf_report, send_report_email

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

st.set_page_config(page_title="Contract Analysis - BORA", layout="centered", initial_sidebar_state="collapsed")

# Inject Custom CSS
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

st.markdown("## Contract Risk Analysis")
st.write("Analyse any South African commercial contract for hidden risks, unfair clauses, and asymmetrical rights.")

with st.container(border=True):
    email = st.text_input("Enter your email address (Required)", value=st.session_state.get("last_email", ""))
    if email and "+dev" in email:
        st.info("🛠️ Developer Mode Active - Free tier limit bypassed")
    uploaded_file = st.file_uploader("Upload Contract", type=["pdf", "docx", "txt"])
    depth = st.selectbox("Analysis Depth", ["Quick Scan (30 seconds)", "Standard Analysis (60 seconds)", "Deep Review (2-3 minutes)"], index=1)

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
                # Basic Stripe Checkout redirect
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
                with st.spinner("Extracting text and running analysis..."):
                    text = extract_text_from_file(uploaded_file)
                    if not text:
                        st.error("Could not extract text from file.")
                    else:
                        prompt = get_contract_risk_prompt()
                        results = run_analysis(text, prompt, depth)
                        
                        st.session_state.last_results = results
                        st.session_state.last_email = email
                        st.session_state.last_type = "Contract Risk"
                        consume_analysis(email)
                        st.rerun()

# Display Results if available
if "last_results" in st.session_state and st.session_state.last_type == "Contract Risk":
    st.write("---")
    st.markdown("### Analysis Results")
    
    results = st.session_state.last_results
    if "Consolidation Error:" in results:
        st.info("📋 Analysis complete. Some sections were processed in quick mode due to document length. All critical risks have been identified.")
    elif any(err in results for err in ["Chunk processing failed:", "Rate limit exceeded", "Request too large"]):
        st.warning("⚡ Processing large document in sections. Results may be partial. Try Quick Scan for faster results.")
    else:
        # Custom rendering for the results
        for line in results.split("\n"):
            if "[RED" in line or "[AMBER" in line or "[GREEN" in line:
                color = "#C62828" if "RED" in line else "#F57C00" if "AMBER" in line else "#2E7D32"
                st.markdown(f"<h4 style='color:{color}'>{line}</h4>", unsafe_allow_html=True)
            else:
                st.write(line)
            
    st.write("---")
    st.markdown("### Download & Delivery")
    
    if st.button("Generate & Email PDF Report"):
        with st.spinner("Generating PDF..."):
            pdf_bytes = generate_pdf_report(results)
            success = send_report_email(st.session_state.last_email, pdf_bytes, "Contract Risk")
            
            if success:
                st.success(f"Report emailed to {st.session_state.last_email}!")
            else:
                st.warning("Failed to email report, but you can download it below.")
                
            st.download_button(
                label="Download PDF Report directly",
                data=pdf_bytes,
                file_name="BORA_Contract_Analysis.pdf",
                mime="application/pdf"
            )
