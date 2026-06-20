import streamlit as st
import stripe
import os
from dotenv import load_dotenv
from modules.database import init_db, upgrade_plan, add_analyses

# ── 1. Page config FIRST ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="BORA - Legal Document Analysis",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ── 2. CSS — branding removal + flash fix + theme ────────────────────────────
st.markdown("""
<style>
/* --- Streamlit chrome removal --- */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
[data-testid="stToolbar"]       {visibility: hidden;}
[data-testid="stDecoration"]    {visibility: hidden;}
[data-testid="stStatusWidget"]  {visibility: hidden;}
[data-testid="stSidebarNav"]    {display: none;}

/* --- Eliminate black/white flash on load --- */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stApp"], .stApp {
    background-color: #FFFFFF !important;
}

/* Reduce top padding */
[data-testid="stAppViewBlockContainer"] > div:first-child {
    padding-top: 1rem;
}

/* --- Smooth fade-in so content appears gracefully --- */
[data-testid="stAppViewContainer"] {
    animation: boraFadeIn 0.25s ease-in;
}
@keyframes boraFadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
}

/* --- BORA design tokens --- */
:root {
    --primary : #1B2A4A;
    --accent  : #C9A84C;
    --bg      : #FFFFFF;
    --bg-soft : #F8F9FA;
    --text    : #2C2C2C;
    --muted   : #666666;
    --border  : #E0E0E0;
}

/* --- Typography --- */
h1, h2, h3 {
    color: var(--primary) !important;
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}

/* --- Gold buttons --- */
.stButton > button {
    background-color: var(--accent) !important;
    color: #000000 !important;
    font-weight: bold !important;
    border: none !important;
    border-radius: 4px !important;
    width: 100%;
    padding: 0.75rem !important;
    transition: opacity 0.2s;
}
.stButton > button:hover {
    opacity: 0.88;
}

/* --- Analysis type cards --- */
.bora-card {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 12px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    transition: transform 0.2s, box-shadow 0.2s;
    background-color: var(--bg);
    min-height: 110px;
}
.bora-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 16px rgba(0,0,0,0.10);
}
.bora-card-icon  { font-size: 2rem; color: var(--accent); margin-bottom: 8px; }
.bora-card-title { color: var(--primary); font-size: 1.15rem; font-weight: 700; margin-bottom: 4px; }
.bora-card-desc  { color: var(--muted); font-size: 0.88rem; line-height: 1.45; }

/* --- Pricing cards --- */
.price-card {
    text-align: center;
    padding: 24px 16px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg);
    height: 100%;
}
.price-card.featured {
    border: 2px solid var(--primary);
    background-color: var(--bg-soft);
}
.price-card h4 { color: var(--primary); margin-bottom: 4px; }
.price-card .price-amount {
    font-size: 2rem;
    font-weight: 800;
    color: var(--accent);
    margin: 8px 0;
}
.price-card.featured .price-amount { color: var(--primary); }
.price-card p  { color: var(--muted); font-size: 0.88rem; margin: 4px 0; }
.price-badge {
    display: inline-block;
    background: var(--primary);
    color: #fff;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    padding: 2px 8px;
    border-radius: 20px;
    margin-bottom: 8px;
    text-transform: uppercase;
}
</style>
""", unsafe_allow_html=True)

# ── 3. Environment + Stripe ───────────────────────────────────────────────────
load_dotenv()
stripe.api_key = os.getenv("STRIPE_API_KEY")

# ── 4. Database ───────────────────────────────────────────────────────────────
init_db()

# ── 5. Handle Stripe redirect ─────────────────────────────────────────────────
def handle_stripe_redirect():
    params = st.query_params
    if "session_id" not in params:
        return
    session_id = params["session_id"]
    if "processed_sessions" not in st.session_state:
        st.session_state.processed_sessions = set()
    if session_id in st.session_state.processed_sessions:
        return
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid":
            email = session.customer_details.email
            plan  = session.metadata.get("plan", "FREE")
            if plan == "PAY_PER_DOC":
                add_analyses(email, 1)
                st.success(f"✅ Payment successful! 1 analysis added to {email}.")
            else:
                upgrade_plan(email, plan, session.subscription, session.customer)
                st.success(f"✅ Subscription active! {email} upgraded to {plan}.")
            st.session_state.processed_sessions.add(session_id)
            st.query_params.clear()
    except Exception:
        st.error("Payment verification failed. Please contact support.")

handle_stripe_redirect()

# ── 6. Header ─────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 4])
with col_logo:
    if os.path.exists("assets/bora_logo.png"):
        st.image("assets/bora_logo.png", width=80)
    else:
        st.markdown(
            "<h1 style='color:#1B2A4A;font-size:3rem;margin-top:0;'>BORA</h1>",
            unsafe_allow_html=True
        )
with col_title:
    st.markdown(
        "<h3 style='margin-top:18px;'>Know what you're signing before you sign it.</h3>",
        unsafe_allow_html=True
    )

st.write("---")

# ── 7. Analysis type cards ────────────────────────────────────────────────────
st.markdown("### Select Analysis Type")

left, right = st.columns(2)

with left:
    st.markdown("""
        <div class="bora-card">
            <div class="bora-card-icon">📄</div>
            <div class="bora-card-title">Contract Risk Analysis</div>
            <div class="bora-card-desc">
                Analyse commercial contracts for hidden risks,
                uncapped liabilities, and CPA violations.
            </div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("Analyse Contract", key="btn_contract"):
        st.switch_page("pages/contract_analysis.py")

    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

    st.markdown("""
        <div class="bora-card">
            <div class="bora-card-icon">🏠</div>
            <div class="bora-card-title">Lease Agreement Analysis</div>
            <div class="bora-card-desc">
                Detect illegal clauses and Rental Housing Act
                violations before you sign.
            </div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("Analyse Lease", key="btn_lease"):
        st.switch_page("pages/lease_analysis.py")

with right:
    st.markdown("""
        <div class="bora-card">
            <div class="bora-card-icon">💼</div>
            <div class="bora-card-title">Employment Contract Analysis</div>
            <div class="bora-card-desc">
                Check BCEA and LRA compliance and calculate
                your exact CCMA exposure.
            </div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("Analyse Employment Contract", key="btn_employment"):
        st.switch_page("pages/employment_analysis.py")

    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

    st.markdown("""
        <div class="bora-card">
            <div class="bora-card-icon">🔍</div>
            <div class="bora-card-title">General Document Scan</div>
            <div class="bora-card-desc">
                Scan any document for hidden liabilities
                and operational traps.
            </div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("General Scan", key="btn_general"):
        st.switch_page("pages/general_scan.py")

# ── 8. Pricing section ────────────────────────────────────────────────────────
st.write("---")
st.markdown(
    "<h3 style='text-align:center;margin-bottom:24px;'>Pricing Plans</h3>",
    unsafe_allow_html=True
)

p1, p2, p3 = st.columns(3)

with p1:
    st.markdown("""
        <div class="price-card">
            <h4>Pay Per Document</h4>
            <div class="price-amount">$16</div>
            <p>Single analysis</p>
            <p>Full PDF report</p>
            <p>No watermark</p>
            <p>Valid 7 days</p>
        </div>
    """, unsafe_allow_html=True)

with p2:
    st.markdown("""
        <div class="price-card featured">
            <div class="price-badge">Most Popular</div>
            <h4>Monthly</h4>
            <div class="price-amount">$16<span style='font-size:14px;font-weight:400'>/mo</span></div>
            <p>Unlimited analyses</p>
            <p>Full PDF reports</p>
            <p>Priority processing</p>
            <p>30-day history</p>
        </div>
    """, unsafe_allow_html=True)

with p3:
    st.markdown("""
        <div class="price-card">
            <h4>Business</h4>
            <div class="price-amount">$80<span style='font-size:14px;font-weight:400'>/mo</span></div>
            <p>Everything in Monthly</p>
            <p>Up to 5 users</p>
            <p>API access</p>
            <p>90-day history</p>
        </div>
    """, unsafe_allow_html=True)

# Small legal footer
st.write("---")
st.markdown(
    "<p style='text-align:center;color:#999;font-size:0.78rem;'>"
    "BORA is not a law firm and does not provide legal advice. "
    "Results are for informational purposes only."
    "</p>",
    unsafe_allow_html=True
)