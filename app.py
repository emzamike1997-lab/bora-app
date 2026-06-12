import streamlit as st
import stripe
import os
from dotenv import load_dotenv
from modules.database import init_db, upgrade_plan, add_analyses

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

# Load env variables
load_dotenv()

# Configure Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY")

st.set_page_config(
    page_title="BORA - Legal Document Analysis",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Initialize DB
init_db()

# Custom CSS for BORA Branding
st.markdown("""
<style>
    :root {
        --primary: #1B2A4A;
        --accent: #C9A84C;
        --bg: #FFFFFF;
        --text: #2C2C2C;
    }
    
    .stApp {
        background-color: var(--bg);
        color: var(--text);
    }
    
    h1, h2, h3 {
        color: var(--primary) !important;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }
    
    .stButton>button {
        background-color: var(--accent) !important;
        color: black !important;
        font-weight: bold !important;
        border: none !important;
        border-radius: 4px !important;
        width: 100%;
        padding: 0.75rem !important;
    }
    
    .stButton>button:hover {
        opacity: 0.9;
    }

    [data-testid="stSidebarNav"] {
        display: none;
    }
    
    .card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s;
        background-color: white;
    }
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }
    .card-icon {
        font-size: 2rem;
        color: var(--accent);
        margin-bottom: 10px;
    }
    .card-title {
        color: var(--primary);
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .card-desc {
        color: #666;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

def handle_stripe_redirect():
    """Handles return from Stripe Checkout via query params."""
    params = st.query_params
    if "session_id" in params:
        session_id = params["session_id"]
        # Check if we already processed this session
        if "processed_sessions" not in st.session_state:
            st.session_state.processed_sessions = set()
            
        if session_id in st.session_state.processed_sessions:
            return
            
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == "paid":
                email = session.customer_details.email
                plan = session.metadata.get("plan", "FREE")
                
                if plan == "PAY_PER_DOC":
                    add_analyses(email, 1)
                    st.success(f"Payment successful! 1 analysis added to {email}.")
                else:
                    upgrade_plan(email, plan, session.subscription, session.customer)
                    st.success(f"Subscription active! Upgraded {email} to {plan}.")
                
                st.session_state.processed_sessions.add(session_id)
                # Clear query params so refresh doesn't trigger again
                st.query_params.clear()
                
        except Exception as e:
            st.error("Error verifying payment. Please contact support.")

handle_stripe_redirect()

# Header
col1, col2 = st.columns([1, 4])
with col1:
    # Use placeholder for logo
    if os.path.exists("assets/bora_logo.png"):
        st.image("assets/bora_logo.png", width=80)
    else:
        st.markdown("<h1 style='color:#1B2A4A; font-size:3rem; margin-top:0;'>BORA</h1>", unsafe_allow_html=True)
with col2:
    st.markdown("<h3 style='margin-top: 15px;'>Know what you're signing before you sign it.</h3>", unsafe_allow_html=True)

st.write("---")

st.markdown("### Select Analysis Type")

# Cards layout using columns
c1, c2 = st.columns(2)

with c1:
    st.markdown("""
        <div class="card">
            <div class="card-icon">📄</div>
            <div class="card-title">Contract Risk Analysis</div>
            <div class="card-desc">Analyse commercial contracts for hidden risks and uncapped liabilities.</div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("Analyse Contract"):
        st.switch_page("pages/contract_analysis.py")
        
    st.markdown("""
        <div class="card">
            <div class="card-icon">🏠</div>
            <div class="card-title">Lease Agreement Analysis</div>
            <div class="card-desc">Detect illegal clauses and Rental Housing Act violations.</div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("Analyse Lease"):
        st.switch_page("pages/lease_analysis.py")

with c2:
    st.markdown("""
        <div class="card">
            <div class="card-icon">💼</div>
            <div class="card-title">Employment Contract Analysis</div>
            <div class="card-desc">Check compliance against BCEA and LRA, and calculate CCMA exposure.</div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("Analyse Employment Contract"):
        st.switch_page("pages/employment_analysis.py")
        
    st.markdown("""
        <div class="card">
            <div class="card-icon">🔍</div>
            <div class="card-title">General Document Scan</div>
            <div class="card-desc">Scan any document for hidden liabilities and operational traps.</div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("General Scan"):
        st.switch_page("pages/general_scan.py")

# Pricing Section
st.write("---")
st.markdown("<h3 style='text-align: center;'>Pricing Plans</h3>", unsafe_allow_html=True)

p1, p2, p3 = st.columns(3)
with p1:
    st.markdown("""
    <div style='text-align:center; padding:20px; border:1px solid #eee; border-radius:8px;'>
        <h4 style='color:#1B2A4A;'>Pay Per Document</h4>
        <h2 style='color:#C9A84C;'>R500</h2>
        <p>Single Analysis</p>
        <p>Full PDF Report</p>
        <p>No Watermark</p>
    </div>
    """, unsafe_allow_html=True)

with p2:
    st.markdown("""
    <div style='text-align:center; padding:20px; border:2px solid #1B2A4A; border-radius:8px; background-color:#f8f9fc;'>
        <h4 style='color:#1B2A4A;'>Monthly</h4>
        <h2 style='color:#1B2A4A;'>R299<span style='font-size:14px'>/mo</span></h2>
        <p>Unlimited Analyses</p>
        <p>Full PDF Reports</p>
        <p>Priority Processing</p>
    </div>
    """, unsafe_allow_html=True)

with p3:
    st.markdown("""
    <div style='text-align:center; padding:20px; border:1px solid #eee; border-radius:8px;'>
        <h4 style='color:#1B2A4A;'>Business</h4>
        <h2 style='color:#C9A84C;'>R1499<span style='font-size:14px'>/mo</span></h2>
        <p>Everything in Monthly</p>
        <p>Up to 5 Users</p>
        <p>API Access</p>
    </div>
    """, unsafe_allow_html=True)
