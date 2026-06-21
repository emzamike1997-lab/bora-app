"""
Shared UI helper for formatting and displaying BORA analysis results
on-screen using native Streamlit components.
"""
import re
import streamlit as st


def _extract_section(text, start_marker, end_markers):
    """Extract text between start_marker and the first end_marker found."""
    pattern = re.escape(start_marker)
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ""
    remaining = text[match.end():]
    # Strip leading dashes/whitespace
    remaining = re.sub(r"^\s*-{2,}\s*", "", remaining)
    
    earliest = len(remaining)
    for em in end_markers:
        m = re.search(re.escape(em), remaining, re.IGNORECASE)
        if m and m.start() < earliest:
            earliest = m.start()
    return remaining[:earliest].strip()


def _parse_individual_risks(section_text, emoji):
    """Parse individual risk items from a section, splitting on the emoji marker."""
    if not section_text.strip():
        return []
    # Split on the emoji (e.g. 🔴, 🟡, 🟢)
    raw_risks = re.split(re.escape(emoji), section_text)
    risks = []
    for r in raw_risks:
        r = r.strip()
        if not r:
            continue
        risk = {"title": "", "clause": "", "law": "", "plain_english": "", "financial": "", "action": ""}
        lines = r.split("\n")
        # Title is typically the first non-empty line (e.g. "RISK 1: ...")
        title_line = lines[0].strip() if lines else ""
        # Clean title: remove "RISK N:" prefix
        title_match = re.match(r"RISK\s*\d+\s*:\s*(.*)", title_line, re.IGNORECASE)
        risk["title"] = title_match.group(1).strip() if title_match else title_line
        
        # Parse remaining key-value lines
        full_text = "\n".join(lines[1:])
        
        clause_match = re.search(r"Clause[^:]*:\s*(.*?)(?=\n\s*(?:Law|What it means|Financial|What to do|$))", full_text, re.DOTALL | re.IGNORECASE)
        if clause_match:
            risk["clause"] = clause_match.group(1).strip()
        
        law_match = re.search(r"Law\s*(?:violated|reference)?[^:]*:\s*(.*?)(?=\n\s*(?:What it means|Financial|What to do|$))", full_text, re.DOTALL | re.IGNORECASE)
        if law_match:
            risk["law"] = law_match.group(1).strip()
        
        plain_match = re.search(r"What it means[^:]*:\s*(.*?)(?=\n\s*(?:Financial|What to do|$))", full_text, re.DOTALL | re.IGNORECASE)
        if plain_match:
            risk["plain_english"] = plain_match.group(1).strip()
        
        financial_match = re.search(r"Financial[^:]*:\s*(.*?)(?=\n\s*(?:What to do|$))", full_text, re.DOTALL | re.IGNORECASE)
        if financial_match:
            risk["financial"] = financial_match.group(1).strip()
        
        action_match = re.search(r"What to do[^:]*:\s*(.*)", full_text, re.DOTALL | re.IGNORECASE)
        if action_match:
            risk["action"] = action_match.group(1).strip()
        
        risks.append(risk)
    return risks


def display_formatted_results(results):
    """
    Parse the raw analysis results text and display them using
    native Streamlit components (expanders, columns, markdown).
    Hides the raw report header and shows structured content.
    """
    # --- STEP 1: Extract Executive Summary ---
    exec_summary = _extract_section(results, "EXECUTIVE SUMMARY",
                                     ["RISK SCORECARD", "CRITICAL RISKS", "---"])
    if exec_summary:
        st.markdown("### 📝 Executive Summary")
        st.write(exec_summary)
        st.divider()
    
    # --- STEP 2: Parse and display individual risks ---
    critical_text = _extract_section(results, "CRITICAL RISKS",
                                      ["MODERATE RISKS", "LOW RISKS", "NEGOTIATION PRIORITY", "RED LINE CLAUSES", "DISCLAIMER"])
    moderate_text = _extract_section(results, "MODERATE RISKS",
                                      ["LOW RISKS", "NEGOTIATION PRIORITY", "RED LINE CLAUSES", "DISCLAIMER"])
    low_text = _extract_section(results, "LOW RISKS",
                                 ["NEGOTIATION PRIORITY", "RED LINE CLAUSES", "DISCLAIMER"])
    
    critical_risks = _parse_individual_risks(critical_text, "🔴")
    moderate_risks = _parse_individual_risks(moderate_text, "🟡")
    low_risks = _parse_individual_risks(low_text, "🟢")
    
    # Display critical risks (expanded)
    if critical_risks:
        st.markdown("### 🔴 Critical Risks")
        for i, risk in enumerate(critical_risks):
            label = risk["title"] if risk["title"] else f"Critical Risk {i+1}"
            with st.expander(f"🔴 {label}", expanded=True):
                if risk["clause"]:
                    st.markdown(f"**Clause:** {risk['clause']}")
                if risk["law"]:
                    st.markdown(f"**Law violated:** {risk['law']}")
                if risk["plain_english"]:
                    st.markdown(f"**Plain English:** {risk['plain_english']}")
                if risk["financial"]:
                    st.markdown(f"**Financial impact:** {risk['financial']}")
                if risk["action"]:
                    st.info(f"**What to do:** {risk['action']}")
        st.divider()
    
    # Display moderate risks (collapsed)
    if moderate_risks:
        st.markdown("### 🟡 Moderate Risks")
        for i, risk in enumerate(moderate_risks):
            label = risk["title"] if risk["title"] else f"Moderate Risk {i+1}"
            with st.expander(f"🟡 {label}", expanded=False):
                if risk["clause"]:
                    st.markdown(f"**Clause:** {risk['clause']}")
                if risk["law"]:
                    st.markdown(f"**Law violated:** {risk['law']}")
                if risk["plain_english"]:
                    st.markdown(f"**Plain English:** {risk['plain_english']}")
                if risk["financial"]:
                    st.markdown(f"**Financial impact:** {risk['financial']}")
                if risk["action"]:
                    st.info(f"**What to do:** {risk['action']}")
        st.divider()
    
    # Display low risks (collapsed)
    if low_risks:
        st.markdown("### 🟢 Low Risks")
        for i, risk in enumerate(low_risks):
            label = risk["title"] if risk["title"] else f"Low Risk {i+1}"
            with st.expander(f"🟢 {label}", expanded=False):
                if risk["clause"]:
                    st.markdown(f"**Clause:** {risk['clause']}")
                if risk["law"]:
                    st.markdown(f"**Law violated:** {risk['law']}")
                if risk["plain_english"]:
                    st.markdown(f"**Plain English:** {risk['plain_english']}")
                if risk["financial"]:
                    st.markdown(f"**Financial impact:** {risk['financial']}")
                if risk["action"]:
                    st.info(f"**What to do:** {risk['action']}")
        st.divider()
    
    # --- STEP 3: Negotiation Priority List ---
    neg_text = _extract_section(results, "NEGOTIATION PRIORITY LIST",
                                 ["RED LINE CLAUSES", "DISCLAIMER"])
    if neg_text.strip():
        st.markdown("### 📋 Negotiation Priority List")
        # Clean up and re-number
        items = [n.strip() for n in re.split(r"\n\d+\.", "\n" + neg_text) if n.strip()]
        for i, item in enumerate(items, 1):
            st.markdown(f"{i}. {item}")
        st.divider()
    
    # --- STEP 4: Red Line Clauses ---
    red_text = _extract_section(results, "RED LINE CLAUSES",
                                 ["DISCLAIMER"])
    if red_text.strip():
        if "no absolute red line clauses found" in red_text.lower() or "none identified" in red_text.lower():
            st.success("✅ No absolute red line clauses found")
        else:
            st.error("⚠️ RED LINE CLAUSES — Do not sign if these are not removed")
            for clause in red_text.split("\n\n"):
                clause = clause.strip()
                if clause:
                    st.markdown(f"- {clause}")
        st.divider()
    
    # --- STEP 5: Disclaimer ---
    disc_text = _extract_section(results, "DISCLAIMER", [])
    if disc_text.strip():
        st.warning(f"⚠️ IMPORTANT DISCLAIMER\n\n{disc_text}")
    
    # Fallback: if no sections were parsed at all, show raw text
    if not exec_summary and not critical_risks and not moderate_risks and not low_risks:
        st.markdown(results, unsafe_allow_html=True)
