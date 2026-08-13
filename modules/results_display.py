"""
Shared UI helper for formatting and displaying BORA analysis results
on-screen using native Streamlit components.
"""
import re
import streamlit as st


def _safe_log(msg):
    """Prints a message to console safely, avoiding UnicodeEncodeErrors on Windows terminal."""
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode('ascii', errors='replace').decode('ascii'))
        except Exception:
            pass



def _extract_section(text, start_marker, end_markers):
    """Extract text between start_marker and the first end_marker found, matching them only as standalone lines."""
    start_pattern = rf"(?mi)^\s*{re.escape(start_marker)}\s*$"
    match = re.search(start_pattern, text)
    if not match:
        # Fallback to standard substring search if not found as a standalone line
        pattern = re.escape(start_marker)
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return ""
    remaining = text[match.end():]
    # Strip leading dashes/whitespace
    remaining = re.sub(r"^\s*-{2,}\s*", "", remaining)

    earliest = len(remaining)
    for em in end_markers:
        # Match the end marker only when it appears on its own line (possibly with dashes/asterisks)
        end_pattern = rf"(?mi)^\s*(?:-{{2,}}\s*)?{re.escape(em)}\s*(?:\s*-{{2,}})?$"
        m = re.search(end_pattern, remaining)
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

    _safe_log(f"[BORA PARSE] Raw section text ({len(section_text)} chars):\n{section_text[:600]}\n---")

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
            _safe_log(f"[BORA FILTER] Skipping risk item due to {', '.join(reasons)}: {r!r}")
            continue

        risks.append(risk)
    return risks


def _clause_similarity(a, b):
    """
    Returns a 0-1 similarity score between two clause strings using
    token-set overlap (Jaccard on word sets). Fast, no external deps.
    """
    if not a or not b:
        return 0.0
    # Normalise: lowercase, strip punctuation, split into word tokens
    def tokenise(s):
        return set(re.sub(r"[^\w\s]", "", s.lower()).split())
    ta, tb = tokenise(a), tokenise(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _risk_completeness(risk):
    """Score a risk dict by how many useful fields it has filled in."""
    score = 0
    if risk.get("clause", ""):
        score += 2
    if risk.get("action", ""):
        score += 2
    if risk.get("financial", "") and risk["financial"].lower() not in ("none", "significant", ""):
        score += 3  # has actual figures — prefer this one
    if risk.get("law", "") and risk["law"].lower() not in ("none", ""):
        score += 1
    if risk.get("plain_english", ""):
        score += 1
    return score


def _deduplicate_risks(critical, moderate, low, threshold=0.70):
    """
    Post-parse dedup: if any two risk items across ALL severity tiers share
    clause text with Jaccard similarity >= threshold, keep the one with more
    complete detail (higher _risk_completeness score) and drop the other.
    Critical > Moderate > Low in tie-breaking so a clause always stays at
    its highest severity.
    """
    # Flatten with severity tag so we can compare across sections
    tagged = (
        [(r, "critical") for r in critical]
        + [(r, "moderate") for r in moderate]
        + [(r, "low") for r in low]
    )

    severity_rank = {"critical": 3, "moderate": 2, "low": 1}
    keep = [True] * len(tagged)

    for i in range(len(tagged)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(tagged)):
            if not keep[j]:
                continue
            ri, si = tagged[i]
            rj, sj = tagged[j]
            sim = _clause_similarity(ri.get("clause", ""), rj.get("clause", ""))
            if sim >= threshold:
                # Prefer higher severity; break ties by completeness
                score_i = severity_rank[si] * 10 + _risk_completeness(ri)
                score_j = severity_rank[sj] * 10 + _risk_completeness(rj)
                if score_j > score_i:
                    keep[i] = False
                    _safe_log(f"[BORA DEDUP] Dropping {si} risk '{ri.get('title','')}' "
                              f"(sim={sim:.2f}) in favour of {sj} '{rj.get('title','')}' "
                              f"(score {score_j} vs {score_i})")
                else:
                    keep[j] = False
                    _safe_log(f"[BORA DEDUP] Dropping {sj} risk '{rj.get('title','')}' "
                              f"(sim={sim:.2f}) in favour of {si} '{ri.get('title','')}' "
                              f"(score {score_i} vs {score_j})")

    # Rebuild per-severity lists preserving order
    new_critical = [tagged[i][0] for i in range(len(tagged)) if keep[i] and tagged[i][1] == "critical"]
    new_moderate = [tagged[i][0] for i in range(len(tagged)) if keep[i] and tagged[i][1] == "moderate"]
    new_low      = [tagged[i][0] for i in range(len(tagged)) if keep[i] and tagged[i][1] == "low"]
    return new_critical, new_moderate, new_low


def display_formatted_results(results):
    """
    Parse the raw analysis results text and display them using
    native Streamlit components (expanders, columns, markdown).
    Hides the raw report header and shows structured content.

    Returns (critical_count, moderate_count, low_count) so the calling
    page can show accurate metric counts from the SAME parsed lists used
    to render the cards — not from an independent emoji-counting pass.
    """
    _safe_log(f"[BORA RAW RESPONSE] Full response ({len(results)} chars):\n{results[:2000]}\n---")

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

    # Post-parse dedup: drop the less-complete duplicate when two items share
    # highly similar clause text across severity tiers
    critical_risks, moderate_risks, low_risks = _deduplicate_risks(
        critical_risks, moderate_risks, low_risks
    )

    _safe_log(f"[BORA COUNTS] After dedup: critical={len(critical_risks)}, moderate={len(moderate_risks)}, low={len(low_risks)}")

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
