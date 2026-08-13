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


def _parse_individual_risks(section_text):
    """
    Parse individual risk items from a section.

    Handles both formats the model may produce:
      - Numbered:  "1. **TITLE**\\nClause: ..."  (current actual Groq format)
      - Emoji:     "🔴 RISK 1: TITLE\\nClause: ..."  (legacy fallback)

    Logs the raw section text and any filtered-out items to the console.
    """
    if not section_text.strip():
        return []

    print(f"[BORA PARSE] Raw section text ({len(section_text)} chars):\n{section_text[:600]}\n---")

    # Split on numbered headings at the start of a line e.g. "1. **TITLE**" or "1. TITLE"
    parts = re.split(r"(?m)(?=^\d+\.\s+\*{0,2}\S)", section_text)

    # Fallback: if no numbered splits found, try emoji split
    if len(parts) <= 1:
        emoji_pattern = r"(🔴|🟡|🟢)"
        raw_splits = re.split(emoji_pattern, section_text)
        # re.split with a capturing group interleaves delimiters:
        # ['', '🔴', 'text', '🟡', 'text2', ...]
        reassembled = []
        i = 0
        while i < len(raw_splits):
            if re.match(emoji_pattern, raw_splits[i]):
                chunk = raw_splits[i] + (raw_splits[i + 1] if i + 1 < len(raw_splits) else "")
                reassembled.append(chunk)
                i += 2
            else:
                if raw_splits[i].strip():
                    reassembled.append(raw_splits[i])
                i += 1
        parts = reassembled

    risks = []
    for r in parts:
        r = r.strip()
        if not r:
            continue

        risk = {"title": "", "clause": "", "law": "", "plain_english": "", "financial": "", "action": ""}
        lines = r.split("\n")
        title_line = lines[0].strip() if lines else ""

        # Strip leading number+dot: "1. **TITLE**" -> "TITLE"
        num_match = re.match(r"^\d+\.\s+\*{0,2}(.*?)\*{0,2}\s*$", title_line)
        if num_match:
            risk["title"] = num_match.group(1).strip()
        else:
            # Emoji prefix fallback: "🔴 RISK 1: TITLE"
            cleaned = re.sub(r"^(?:🔴|🟡|🟢)\s*", "", title_line)
            risk_label = re.match(r"RISK\s*\d+\s*:\s*(.*)", cleaned, re.IGNORECASE)
            risk["title"] = risk_label.group(1).strip() if risk_label else cleaned.strip("*").strip()

        # Parse remaining key-value lines
        full_text = "\n".join(lines[1:])

        clause_match = re.search(
            r"Clause[^:]*:\s*(.*?)(?=\n\s*(?:Law|Concern|What it means|Financial|What to do|$))",
            full_text, re.DOTALL | re.IGNORECASE)
        if clause_match:
            risk["clause"] = clause_match.group(1).strip()

        law_match = re.search(
            r"(?:Law\s*(?:violated|reference)?|Concern)[^:]*:\s*(.*?)(?=\n\s*(?:What it means|Financial|What to do|$))",
            full_text, re.DOTALL | re.IGNORECASE)
        if law_match:
            risk["law"] = law_match.group(1).strip()

        plain_match = re.search(
            r"What it means[^:]*:\s*(.*?)(?=\n\s*(?:Financial|What to do|$))",
            full_text, re.DOTALL | re.IGNORECASE)
        if plain_match:
            risk["plain_english"] = plain_match.group(1).strip()

        financial_match = re.search(
            r"Financial[^:]*:\s*(.*?)(?=\n\s*(?:What to do|$))",
            full_text, re.DOTALL | re.IGNORECASE)
        if financial_match:
            risk["financial"] = financial_match.group(1).strip()

        action_match = re.search(r"What to do[^:]*:\s*(.*)", full_text, re.DOTALL | re.IGNORECASE)
        if action_match:
            risk["action"] = action_match.group(1).strip()

        # Guards to filter out invalid or placeholder risk items
        title = risk["title"]
        is_empty_or_punctuation = not any(c.isalnum() for c in title)
        is_placeholder = title.startswith("(") and title.endswith(")")
        is_missing_fields = not risk["clause"] and not risk["action"]

        if is_empty_or_punctuation or is_placeholder or is_missing_fields:
            reasons = []
            if is_empty_or_punctuation:
                reasons.append("empty or punctuation title")
            if is_placeholder:
                reasons.append("category placeholder title")
            if is_missing_fields:
                reasons.append("missing both Clause and What to do")
            print(f"[BORA FILTER] Skipping risk item due to {', '.join(reasons)}: {r!r}")
            continue

        risks.append(risk)
    return risks


def display_formatted_results(results):
    """
    Parse the raw analysis results text and display them using
    native Streamlit components (expanders, columns, markdown).
    Hides the raw report header and shows structured content.

    Returns (critical_count, moderate_count, low_count) so the calling
    page can show accurate metric counts from the SAME parsed lists used
    to render the cards — not from an independent emoji-counting pass.
    """
    print(f"[BORA RAW RESPONSE] Full response ({len(results)} chars):\n{results[:2000]}\n---")

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

    critical_risks = _parse_individual_risks(critical_text)
    moderate_risks = _parse_individual_risks(moderate_text)
    low_risks = _parse_individual_risks(low_text)

    print(f"[BORA COUNTS] Parsed: critical={len(critical_risks)}, moderate={len(moderate_risks)}, low={len(low_risks)}")

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
        items = [n.strip() for n in re.split(r"\n\d+\.", "\n" + neg_text) if n.strip()]
        for i, item in enumerate(items, 1):
            st.markdown(f"{i}. {item}")
        st.divider()

    # --- STEP 4: Red Line Clauses ---
    red_text = _extract_section(results, "RED LINE CLAUSES", ["DISCLAIMER"])
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

    # Return counts from the real parsed lists — not from emoji counting
    return len(critical_risks), len(moderate_risks), len(low_risks)
