#!/usr/bin/env python3
"""
BID-2026-001 Auchan AI Discovery Audit
Builds two PPTX decks from the TokenShift template using unpack/add_slide/edit/pack.
  1. Internal Bid Validation (10 slides, English)
  2. External Proposal for Auchan (14 slides, French)
"""
import os, sys, shutil, subprocess, re, copy

SKILL_DIR  = "/home/pascal/.claude/skills/pptx/scripts"
TEMPLATE   = "/mnt/c/Users/pasca/TokenShift/08_Brand_Templates/01_Brand_Guidelines/TokenShift-Brand/tokenshift-template-v2.pptx"
OUT_DIR    = "/mnt/c/Users/pasca/TokenShift/90_Agent_Workspaces/sales_enablement/03_Proposed_Changes"
WORK_BASE  = "/tmp/auchan-build"

# ── Helpers ────────────────────────────────────────────────────

def run(cmd, cwd=None):
    """Run a shell command and print output."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.returncode != 0:
        print(f"WARN: {cmd}\n{r.stderr.strip()}")
    return r

def unpack(pptx, dest):
    run(f"python3 {SKILL_DIR}/office/unpack.py '{pptx}' '{dest}'")

def add_slide(work_dir, source_slide):
    """Duplicate a slide. Inserts sldId into presentation.xml. Returns (slide_num, id, rId)."""
    r = run(f"python3 {SKILL_DIR}/add_slide.py '{work_dir}' '{source_slide}'")
    output = r.stdout.strip()
    # Parse the output: e.g. 'Created slide10.xml from slide4.xml\nAdd to presentation.xml...: <p:sldId id="265" r:id="rId16"/>'
    slide_match = re.search(r"Created (slide(\d+)\.xml)", output)
    rid_match = re.search(r'r:id="(rId\d+)"', output)
    if not slide_match or not rid_match:
        print(f"WARN: Could not parse add_slide output: {output}")
        return None
    slide_num = int(slide_match.group(2))
    rid = rid_match.group(1)

    # Assign a unique ID (find max existing ID and increment)
    pres_path = os.path.join(work_dir, "ppt", "presentation.xml")
    with open(pres_path, "r", encoding="utf-8") as f:
        pxml = f.read()
    existing_ids = [int(x) for x in re.findall(r'<p:sldId id="(\d+)"', pxml)]
    new_id = max(existing_ids) + 1 if existing_ids else 265
    # Insert the new sldId before </p:sldIdLst>
    new_entry = f'<p:sldId id="{new_id}" r:id="{rid}"/>\n  '
    pxml = pxml.replace("</p:sldIdLst>", f"  {new_entry}</p:sldIdLst>")
    with open(pres_path, "w", encoding="utf-8") as f:
        f.write(pxml)
    print(f"  Added sldId id={new_id} r:id={rid} for slide{slide_num}.xml")
    return (slide_num, str(new_id), rid)

def clean(work_dir):
    run(f"python3 {SKILL_DIR}/clean.py '{work_dir}'")

def pack(work_dir, output, original):
    run(f"python3 {SKILL_DIR}/office/pack.py '{work_dir}' '{output}' --original '{original}'")

def replace_in_file(filepath, old, new):
    """Simple string replacement in a file."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    if old not in content:
        return False
    content = content.replace(old, new)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return True

def replace_text_in_slide(slide_path, replacements):
    """Replace text in <a:t> elements. Handles split runs by joining adjacent runs."""
    with open(slide_path, "r", encoding="utf-8") as f:
        xml = f.read()
    for old_text, new_text in replacements.items():
        # Escape for XML
        new_escaped = new_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        old_escaped = old_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Direct replacement in <a:t> tags
        xml = xml.replace(f">{old_escaped}</a:t>", f">{new_escaped}</a:t>")
    with open(slide_path, "w", encoding="utf-8") as f:
        f.write(xml)

def set_slide_order(work_dir, slide_ids):
    """Rewrite <p:sldIdLst> in presentation.xml with the given ordered list of (id, rId) tuples."""
    pres_path = os.path.join(work_dir, "ppt", "presentation.xml")
    with open(pres_path, "r", encoding="utf-8") as f:
        xml = f.read()
    # Build new sldIdLst
    entries = "\n    ".join(f'<p:sldId id="{sid}" r:id="{rid}"/>' for sid, rid in slide_ids)
    new_list = f"<p:sldIdLst>\n    {entries}\n  </p:sldIdLst>"
    xml = re.sub(r"<p:sldIdLst>.*?</p:sldIdLst>", new_list, xml, flags=re.DOTALL)
    with open(pres_path, "w", encoding="utf-8") as f:
        f.write(xml)

def get_slide_ids(work_dir):
    """Parse current slide IDs from presentation.xml."""
    pres_path = os.path.join(work_dir, "ppt", "presentation.xml")
    with open(pres_path, "r", encoding="utf-8") as f:
        xml = f.read()
    return re.findall(r'<p:sldId id="(\d+)" r:id="(rId\d+)"/>', xml)

def get_slide_path(work_dir, slide_num):
    """Get the path to a slide XML file."""
    return os.path.join(work_dir, "ppt", "slides", f"slide{slide_num}.xml")

# ══════════════════════════════════════════════════════════════
#  INTERNAL DECK (10 slides, English)
# ══════════════════════════════════════════════════════════════

def build_internal():
    print("\n=== BUILDING INTERNAL DECK ===")
    work = os.path.join(WORK_BASE, "internal")
    if os.path.exists(work):
        shutil.rmtree(work)

    # 1. Unpack template
    unpack(TEMPLATE, work)

    # Template slides: 1=Title, 2=Agenda, 3=SectionDiv, 4=Content, 5=TwoCol, 6=Metrics, 7=4Phase, 8=Chart, 9=ThankYou
    # Target: 10 slides
    # Slide mapping (template → target):
    #   T1 → S1: Title
    #   T6 → S2: Opportunity Summary (metrics)
    #   T3 → S3: Client Context (section divider)
    #   T7 → S4: Solution (4-phase → 4 workstreams)
    #   T5 → S5: Win Strategy (two-column)
    #   T7dup → S6: Delivery Plan (4-phase → 5 weeks)
    #   T6dup → S7: Pricing & P&L (metrics)
    #   T4 → S8: Competitive Landscape (content)
    #   T4dup → S9: Risk Assessment (content)
    #   T9 → S10: Go/No-Go (thank you)

    # 2. Duplicate slides we need extra copies of
    dup_content = add_slide(work, "slide4.xml")  # for Risk Assessment
    dup_metrics = add_slide(work, "slide6.xml")  # for Pricing & P&L
    dup_4phase  = add_slide(work, "slide7.xml")  # for Delivery Plan

    # 3. Build rId→slide mapping
    rels_path = os.path.join(work, "ppt", "_rels", "presentation.xml.rels")
    with open(rels_path, "r", encoding="utf-8") as f:
        rels_xml = f.read()
    rid_to_slide = {}
    for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="slides/(slide\d+\.xml)"', rels_xml):
        rid_to_slide[m.group(1)] = m.group(2)

    # Map original template slides (1-9) from presentation.xml
    ids = get_slide_ids(work)
    slide_by_num = {}
    for sid, rid in ids:
        sfile = rid_to_slide.get(rid, "")
        if sfile:
            num = int(re.search(r"slide(\d+)", sfile).group(1))
            slide_by_num[num] = (sid, rid)
    print(f"Slide map: {slide_by_num}")

    # Duplicated slides: use the returned (slide_num, id, rId) tuples
    dup_content_entry = (dup_content[1], dup_content[2])
    dup_metrics_entry = (dup_metrics[1], dup_metrics[2])
    dup_4phase_entry  = (dup_4phase[1], dup_4phase[2])

    # Original slide entries: (id, rId)
    T1 = slide_by_num[1]   # Title
    T3 = slide_by_num[3]   # Section Divider
    T4 = slide_by_num[4]   # Content
    T5 = slide_by_num[5]   # Two-Column
    T6 = slide_by_num[6]   # Metrics
    T7 = slide_by_num[7]   # 4-Phase
    T9 = slide_by_num[9]   # Thank You

    # 4. Set slide order for internal deck (10 slides)
    order = [
        T1,                  # S1: Title
        T6,                  # S2: Opportunity Summary (Metrics)
        T3,                  # S3: Client Context (Section Divider)
        T7,                  # S4: Solution (4-Phase)
        T5,                  # S5: Win Strategy (Two-Column)
        dup_4phase_entry,    # S6: Delivery Plan (4-Phase dup)
        dup_metrics_entry,   # S7: Pricing & P&L (Metrics dup)
        T4,                  # S8: Competitive Landscape (Content)
        dup_content_entry,   # S9: Risk Assessment (Content dup)
        T9,                  # S10: Go/No-Go (Thank You)
    ]
    set_slide_order(work, order)

    # 5. Edit slide content (English)
    slides_dir = os.path.join(work, "ppt", "slides")

    # Re-read rels after add_slide calls added new entries
    with open(rels_path, "r", encoding="utf-8") as f:
        rels_xml = f.read()
    rid_to_slide = {}
    for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="slides/(slide\d+\.xml)"', rels_xml):
        rid_to_slide[m.group(1)] = m.group(2)
    print(f"Updated rId→slide: {rid_to_slide}")

    # Helper to get slide file from rId
    def sf(rid):
        return os.path.join(slides_dir, rid_to_slide[rid])

    # S1: Title
    replace_text_in_slide(sf(order[0][1]), {
        "Presentation Title": "Auchan AI Discovery Audit",
        "Subtitle or context line goes here": "Internal Bid Validation | BID-2026-001",
        "February 2026": "23 February 2026 | CONFIDENTIAL - INTERNAL",
    })

    # S2: Opportunity Summary (Metrics slide)
    replace_text_in_slide(sf(order[1][1]), {
        "Key Metrics": "Opportunity Summary",
        "4": "EUR 95K",
        "85%": "5 wks",
        "6mo": "62.5%",
        "3.2x": "4.5/5",
        "Phases of": "Investment",
        "transformation": "(Pioneer -20%)",
        "AI adoption rate": "Duration",
        "post-implementation": "Kick-off to delivery",
        "Average time": "Gross Margin",
        "to production": "EUR 59.4K profit",
        "ROI within": "Go/No-Go Score",
        "first year": "RECOMMENDATION: GO",
    })

    # S3: Client Context (Section Divider)
    replace_text_in_slide(sf(order[2][1]), {
        "01": "",
        "Section Title": "Client Context: Auchan Retail",
        "Supporting context for this section": "EUR 32B revenue | 160K employees | EUR 1.2B net loss | 9+ AI projects | EU AI Act deadline Aug 2026",
    })

    # S4: Solution (4-Phase slide)
    replace_text_in_slide(sf(order[3][1]), {
        "Our 4-Phase Approach": "Proposed Solution: DIAGNOSE Framework",
        "Diagnose": "AI Landscape",
        "Build": "Process & ROI",
        "Transition": "Governance",
        "Assure": "Workforce Impact",
        "AI readiness assessment, workflow mapping, opportunity identification": "Inventory of 9+ AI projects, maturity scoring, integration review, data readiness assessment",
        "Agentic process redesign, LLM/RAG deployment, integration architecture": "Top 10 use cases, process mapping, ROI modeling, impact/effort prioritization",
        "Workforce upskilling, change management, pilot-to-production scaling": "EU AI Act gap analysis, risk mapping, governance framework, compliance roadmap",
        "Ongoing governance, performance monitoring, continuous optimization": "Role impact analysis, skills adjacency, AI literacy plan, HR readiness assessment",
    })

    # S5: Win Strategy (Two-Column)
    replace_text_in_slide(sf(order[4][1]), {
        "Two-Column Comparison": "Win Strategy: Our Advantages vs. Competition",
        "Before": "Our Advantages",
        "After": "Competition Weaknesses",
        "Manual processes": "40-60% cheaper than Big Four",
        "Siloed teams": "50% faster: 5 weeks vs. 12 weeks",
        "Pilot-only AI projects": "Unique workforce angle - not just a tech audit",
        "No measurable ROI": "AI-native, not consulting with an AI add-on",
        "AI-powered workflows": "Big Four: expensive, slow, governance-only",
        "Cross-functional integration": "Accenture/Capgemini: generic, no workforce angle",
        "Production-grade deployment": "IBM: tied to their stack (conflict of interest)",
        "Tracked, measurable outcomes": "Boutiques: no C-level credibility",
    })

    # S6: Delivery Plan (4-Phase duplicate)
    replace_text_in_slide(sf(order[5][1]), {
        "Our 4-Phase Approach": "Delivery Plan: 5-Week Timeline",
        "Diagnose": "W1: Kick-off",
        "Build": "W2: AI Assess",
        "Transition": "W3: ROI Map",
        "Assure": "W4-5: Gov+WF",
        "AI readiness assessment, workflow mapping, opportunity identification": "Scoping, key interviews, data collection. Team: Sr Consultant (25d), AI Engineer (15d), CEO (3d)",
        "Agentic process redesign, LLM/RAG deployment, integration architecture": "Project inventory, maturity scoring, technical review. 2-3 onsite visits at Villeneuve d'Ascq",
        "Workforce upskilling, change management, pilot-to-production scaling": "Use cases, process mapping, ROI modeling. Total 43 consulting days across 5 weeks",
        "Ongoing governance, performance monitoring, continuous optimization": "EU AI Act gap, workforce impact, roadmap synthesis. Board-ready COMEX presentation",
    })

    # S7: Pricing & P&L (Metrics duplicate)
    replace_text_in_slide(sf(order[6][1]), {
        "Key Metrics": "Deal Economics: Pricing & P&L",
        "4": "EUR 95K",
        "85%": "EUR 35.6K",
        "6mo": "EUR 59.4K",
        "3.2x": "EUR 530K+",
        "Phases of": "Revenue",
        "transformation": "(Price HT)",
        "AI adoption rate": "COGS",
        "post-implementation": "(37.5% of revenue)",
        "Average time": "Gross Profit",
        "to production": "(62.5% margin)",
        "ROI within": "Est. LTV",
        "first year": "(Weighted upsell)",
    })

    # S8: Competitive Landscape (Content slide)
    replace_text_in_slide(sf(order[7][1]), {
        "Content Slide Title": "Competitive Landscape",
        "Key point one with supporting detail that provides context for the audience.": "Accenture/Capgemini: HIGH threat. Strong brand but expensive, slow, generic. We win on price (-60%), speed (5 vs 12 wks).",
        "Key point two explaining another aspect of the topic or insight.": "IBM: MEDIUM threat. Proprietary AI stack, existing infra. Conflict of interest. We win on independence and holistic approach.",
        "Key point three with data or evidence to support the narrative.": "Big Four (Deloitte, EY): MEDIUM threat. Audit credibility, decision networks. Governance-only, no AI execution. We combine tech + workforce + regulation.",
        "Key point four summarizing the implication or call to action.": "Boutique AI firms: LOW threat. Deep tech expertise, agile. No C-level credibility. We have strategic C-level positioning.",
        "Visual / Chart": "Key Message:",
        "Placeholder": "\"9+ AI projects - do you know which ones work?\"",
    })

    # S9: Risk Assessment (Content duplicate)
    replace_text_in_slide(sf(order[8][1]), {
        "Content Slide Title": "Risk Assessment: 5 Identified Risks",
        "Key point one with supporting detail that provides context for the audience.": "Sponsor instability (MEDIUM): Identify backup sponsor from W1. Maintain 2+ COMEX contact points.",
        "Key point two explaining another aspect of the topic or insight.": "Scope creep (HIGH): Strict scoping in W1, formal change request process. Scope validated in kick-off memo.",
        "Key point three with data or evidence to support the narrative.": "Procurement delays (MEDIUM): Engage procurement in parallel with sponsor. Plan LOI if PO delayed.",
        "Key point four summarizing the implication or call to action.": "Political sensitivity (MEDIUM): Neutral deliverables (facts + data). No judgment on past choices. Incumbent competition (HIGH): Pitch independence + speed. Propose visible quick-win from W2.",
        "Visual / Chart": "Mitigation",
        "Placeholder": "Strategy",
    })

    # S10: Go/No-Go (Thank You slide)
    replace_text_in_slide(sf(order[9][1]), {
        "Thank you": "RECOMMENDATION: GO",
        "From code to culture.": "Score: 4.5 / 5",
        "pascal@tokenshift.com": "Validate with stakeholders by 24 Feb",
        "+33 X XX XX XX XX": "Submit proposal to Auchan by 28 Feb",
        "tokenshift.com": "BID-2026-001 | CONFIDENTIAL - INTERNAL",
    })

    # 6. Clean and pack
    clean(work)
    out_path = os.path.join(OUT_DIR, "Auchan-Internal-Bid-Validation-2026-02-23.pptx")
    pack(work, out_path, TEMPLATE)
    print(f"\nInternal deck: {out_path}")
    return out_path

# ══════════════════════════════════════════════════════════════
#  EXTERNAL DECK (14 slides, French)
# ══════════════════════════════════════════════════════════════

def build_external():
    print("\n=== BUILDING EXTERNAL DECK ===")
    work = os.path.join(WORK_BASE, "external")
    if os.path.exists(work):
        shutil.rmtree(work)

    # 1. Unpack template
    unpack(TEMPLATE, work)

    # Target: 14 slides
    # Slide mapping:
    #   T1 → S1: Title
    #   T2 → S2: Executive Summary (Agenda)
    #   T3 → S3: Your Context (Section Divider)
    #   T4 → S4: The Challenge (Content)
    #   T7 → S5: DIAGNOSE Framework (4-Phase)
    #   T5 → S6: WS Details 1&2 (Two-Column)
    #   T5dup → S7: WS Details 3&4 (Two-Column dup)
    #   T4dup → S8: Deliverables (Content dup)
    #   T7dup → S9: Timeline (4-Phase dup)
    #   T4dup2 → S10: Team (Content dup2)
    #   T6 → S11: Investment (Metrics) -- repurposed as Why TokenShift won't fit metrics layout
    #   T5dup2 → S12: Why TokenShift (Two-Column dup2)
    #   T7dup2 → S13: What Comes Next (4-Phase dup2)
    #   T9 → S14: Let's Start (Thank You)
    # Remove T8 (Chart)

    # 2. Duplicate slides
    dup4a = add_slide(work, "slide4.xml")   # for Deliverables
    dup4b = add_slide(work, "slide4.xml")   # for Team
    dup5a = add_slide(work, "slide5.xml")   # for WS 3&4
    dup5b = add_slide(work, "slide5.xml")   # for Why TokenShift
    dup7a = add_slide(work, "slide7.xml")   # for Timeline
    dup7b = add_slide(work, "slide7.xml")   # for What Comes Next

    # Build rId→slide mapping
    rels_path = os.path.join(work, "ppt", "_rels", "presentation.xml.rels")
    with open(rels_path, "r", encoding="utf-8") as f:
        rels_xml = f.read()
    rid_to_slide = {}
    for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="slides/(slide\d+\.xml)"', rels_xml):
        rid_to_slide[m.group(1)] = m.group(2)

    ids = get_slide_ids(work)
    slide_by_num = {}
    for sid, rid in ids:
        sfile = rid_to_slide.get(rid, "")
        if sfile:
            num = int(re.search(r"slide(\d+)", sfile).group(1))
            slide_by_num[num] = (sid, rid)
    print(f"Slide map: {slide_by_num}")

    # Original entries
    T1 = slide_by_num[1]; T2 = slide_by_num[2]; T3 = slide_by_num[3]
    T4 = slide_by_num[4]; T5 = slide_by_num[5]; T6 = slide_by_num[6]
    T7 = slide_by_num[7]; T9 = slide_by_num[9]

    # Dup entries from add_slide returns: (slide_num, id, rId)
    D4a = (dup4a[1], dup4a[2]); D4b = (dup4b[1], dup4b[2])
    D5a = (dup5a[1], dup5a[2]); D5b = (dup5b[1], dup5b[2])
    D7a = (dup7a[1], dup7a[2]); D7b = (dup7b[1], dup7b[2])

    # 3. Set slide order (14 slides, remove T8=Chart)
    order = [
        T1,   # S1: Title
        T2,   # S2: Executive Summary (Agenda)
        T3,   # S3: Your Context (Section Divider)
        T4,   # S4: The Challenge (Content)
        T7,   # S5: DIAGNOSE Framework (4-Phase)
        T5,   # S6: WS Details 1&2 (Two-Column)
        D5a,  # S7: WS Details 3&4 (Two-Column dup)
        D4a,  # S8: Deliverables (Content dup)
        D7a,  # S9: Timeline (4-Phase dup)
        D4b,  # S10: Team (Content dup)
        D5b,  # S11: Why TokenShift (Two-Column dup)
        T6,   # S12: Investment (Metrics)
        D7b,  # S13: What Comes Next (4-Phase dup)
        T9,   # S14: Let's Start (Thank You)
    ]
    set_slide_order(work, order)

    # 4. Edit slide content (French)
    slides_dir = os.path.join(work, "ppt", "slides")

    # Re-read rels after add_slide calls
    with open(rels_path, "r", encoding="utf-8") as f:
        rels_xml = f.read()
    rid_to_slide = {}
    for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="slides/(slide\d+\.xml)"', rels_xml):
        rid_to_slide[m.group(1)] = m.group(2)
    print(f"Updated rId→slide: {rid_to_slide}")

    def sf(rid):
        return os.path.join(slides_dir, rid_to_slide[rid])

    # S1: Title
    replace_text_in_slide(sf(order[0][1]), {
        "Presentation Title": "AI Discovery Audit",
        "Subtitle or context line goes here": "Proposition pour Auchan Retail",
        "February 2026": "Fevrier 2026 | CONFIDENTIEL",
    })

    # S2: Executive Summary (Agenda slide - 4 sections)
    replace_text_in_slide(sf(order[1][1]), {
        "Agenda": "Synthese Executive",
        "Section One": "Clarte",
        "Section Two": "Conformite",
        "Section Three": "Confiance",
        "Section Four": "Rapidite",
    })
    # Also replace the descriptions
    replace_text_in_slide(sf(order[1][1]), {
        "Brief description of section content": "",
    })
    # Need to replace each description individually - they all have same text
    # Use a more targeted approach for the agenda slide
    agenda_path = sf(order[1][1])
    with open(agenda_path, "r", encoding="utf-8") as f:
        xml = f.read()
    # The 4 descriptions are identical placeholders - replace by occurrence
    desc_texts = [
        "Vision unifiee de vos 9+ projets IA et de leur valeur reelle",
        "Gap analysis EU AI Act avant l'echeance d'aout 2026",
        "Donnees et preuves pour les decisions du Conseil d'Administration",
        "De l'audit a la feuille de route en 5 semaines, pas 12",
    ]
    # Since all 4 have the same placeholder text which was already blanked, we need a different approach
    # Let's not blank them but replace them sequentially - re-read and handle
    # Actually the replace already blanked all 4. Let's add them back by modifying the section names
    # The agenda format is: "01 Section One \n Brief description..."
    # Let me update the section names to include the descriptions
    xml = xml.replace(">Clarte<", ">Clarte: Vision unifiee de vos 9+ projets IA<")
    xml = xml.replace(">Conformite<", ">Conformite: Gap analysis EU AI Act avant aout 2026<")
    xml = xml.replace(">Confiance<", ">Confiance: Donnees pour les decisions du Conseil<")
    xml = xml.replace(">Rapidite<", ">Rapidite: De l'audit a la roadmap en 5 semaines<")
    with open(agenda_path, "w", encoding="utf-8") as f:
        f.write(xml)

    # S3: Your Context (Section Divider)
    replace_text_in_slide(sf(order[2][1]), {
        "01": "",
        "Section Title": "Comprendre Votre Transformation",
        "Supporting context for this section": "EUR 750 M plan de transformation | 9+ projets IA sans gouvernance unifiee | EU AI Act aout 2026",
    })

    # S4: The Challenge (Content)
    replace_text_in_slide(sf(order[3][1]), {
        "Content Slide Title": "Le Defi : 9+ Projets IA. 0 Vision Unifiee.",
        "Key point one with supporting detail that provides context for the audience.": "9+ projets IA actifs (Trigo, DRUID, RELEX, Ocado, IBM, Smartway) a travers supply chain, magasins, operations et paiements.",
        "Key point two explaining another aspect of the topic or insight.": "Aucun cadre de gouvernance IA centralise, pas de comite IA, pas de registre d'algorithmes.",
        "Key point three with data or evidence to support the narrative.": "EU AI Act applicable en aout 2026 : classification des risques, documentation et audit trail obligatoires.",
        "Key point four summarizing the implication or call to action.": "2 389 postes en restructuration : l'IA doit accompagner, pas remplacer, les equipes.",
        "Visual / Chart": "Question cle :",
        "Placeholder": "Savez-vous lesquels fonctionnent ?",
    })

    # S5: DIAGNOSE Framework (4-Phase)
    replace_text_in_slide(sf(order[4][1]), {
        "Our 4-Phase Approach": "Notre Approche : Le Framework DIAGNOSE",
        "Diagnose": "Cartographie IA",
        "Build": "Processus & ROI",
        "Transition": "Gouvernance",
        "Assure": "Impact Workforce",
        "AI readiness assessment, workflow mapping, opportunity identification": "Inventaire complet de vos projets IA, scoring de maturite, evaluation de l'integration et de la qualite des donnees",
        "Agentic process redesign, LLM/RAG deployment, integration architecture": "Top 10 des cas d'usage, mapping des processus impactes, modelisation du ROI, priorisation impact vs. effort",
        "Workforce upskilling, change management, pilot-to-production scaling": "Readiness EU AI Act, mapping des risques IA, gap analysis du cadre de gouvernance, feuille de route conformite",
        "Ongoing governance, performance monitoring, continuous optimization": "Analyse d'impact par role, adjacence des competences, plan de litteratie IA, evaluation readiness RH",
    })

    # S6: WS Details 1&2 (Two-Column)
    replace_text_in_slide(sf(order[5][1]), {
        "Two-Column Comparison": "Axes 1 & 2 : Cartographie IA et ROI",
        "Before": "01 Cartographie IA",
        "After": "02 Processus & ROI",
        "Manual processes": "Inventaire exhaustif des 9+ projets IA",
        "Siloed teams": "Scoring de maturite (echelle 1-5)",
        "Pilot-only AI projects": "Revue des architectures d'integration",
        "No measurable ROI": "Evaluation qualite et disponibilite des donnees",
        "AI-powered workflows": "Selection des top 10 cas d'usage IA",
        "Cross-functional integration": "Mapping des processus metier impactes",
        "Production-grade deployment": "Modelisation ROI par cas d'usage",
        "Tracked, measurable outcomes": "Matrice de priorisation impact vs. effort",
    })

    # S7: WS Details 3&4 (Two-Column dup)
    replace_text_in_slide(sf(order[6][1]), {
        "Two-Column Comparison": "Axes 3 & 4 : Gouvernance et Workforce",
        "Before": "03 Gouvernance & Conformite",
        "After": "04 Impact Workforce",
        "Manual processes": "Evaluation readiness EU AI Act",
        "Siloed teams": "Classification des risques par systeme IA",
        "Pilot-only AI projects": "Gap analysis du cadre de gouvernance",
        "No measurable ROI": "Feuille de route conformite avec jalons",
        "AI-powered workflows": "Analyse d'impact IA par famille de roles",
        "Cross-functional integration": "Cartographie d'adjacence des competences",
        "Production-grade deployment": "Plan de litteratie IA par niveau",
        "Tracked, measurable outcomes": "Recommandations formation et reconversion",
    })

    # S8: Deliverables (Content dup)
    replace_text_in_slide(sf(order[7][1]), {
        "Content Slide Title": "Vos Livrables : 6 Livrables Concrets",
        "Key point one with supporting detail that provides context for the audience.": "01 Feuille de Route Board-Ready : Plan strategique IA a 18 mois avec priorites, investissements et jalons pour le Conseil.",
        "Key point two explaining another aspect of the topic or insight.": "02 Scorecard Maturite IA : Evaluation detaillee de chaque projet (scoring 1-5) avec benchmark sectoriel.",
        "Key point three with data or evidence to support the narrative.": "03 Portefeuille Cas d'Usage + ROI : Top 10 cas d'usage avec modelisation ROI et matrice effort/impact.",
        "Key point four summarizing the implication or call to action.": "04 Rapport Conformite EU AI Act | 05 Evaluation Impact Workforce | 06 Note de Synthese COMEX",
        "Visual / Chart": "6 livrables",
        "Placeholder": "strategiques et operationnels",
    })

    # S9: Timeline (4-Phase dup)
    replace_text_in_slide(sf(order[8][1]), {
        "Our 4-Phase Approach": "Calendrier & Jalons : 5 Semaines",
        "Diagnose": "S1: Kick-off",
        "Build": "S2: Evaluation",
        "Transition": "S3: ROI Map",
        "Assure": "S4-5: Synthese",
        "AI readiness assessment, workflow mapping, opportunity identification": "Cadrage, interviews direction, collecte donnees existantes. Effort client: ~3h",
        "Agentic process redesign, LLM/RAG deployment, integration architecture": "Inventaire projets, scoring maturite, revue technique. Effort client: ~2h",
        "Workforce upskilling, change management, pilot-to-production scaling": "Cas d'usage, processus, modelisation ROI, priorisation. Effort client: ~3h",
        "Ongoing governance, performance monitoring, continuous optimization": "EU AI Act, risques, impact RH, feuille de route, presentation COMEX. Effort: ~4h",
    })

    # S10: Team (Content dup)
    replace_text_in_slide(sf(order[9][1]), {
        "Content Slide Title": "Votre Equipe Dediee",
        "Key point one with supporting detail that provides context for the audience.": "Consultant Senior Transformation IA (25 jours) : Lead de la mission. Cadrage strategique, interviews direction, analyse, livrables, presentation COMEX.",
        "Key point two explaining another aspect of the topic or insight.": "Ingenieur IA (15 jours) : Evaluation technique des projets IA, scoring de maturite, revue des architectures, analyse data readiness.",
        "Key point three with data or evidence to support the narrative.": "CEO - Supervision Executif (3 jours) : Alignement strategique C-level, revue qualite des livrables, presentation COMEX finale.",
        "Key point four summarizing the implication or call to action.": "Total : 43 jours de consulting | 2-3 visites sur site a Villeneuve d'Ascq",
        "Visual / Chart": "43 jours",
        "Placeholder": "de consulting senior",
    })

    # S11: Why TokenShift (Two-Column dup)
    replace_text_in_slide(sf(order[10][1]), {
        "Two-Column Comparison": "Pourquoi TokenShift",
        "Before": "Methodologie",
        "After": "Philosophie",
        "Manual processes": "Methodologie AI-Native depuis le jour 1",
        "Siloed teams": "5 semaines de l'audit a la feuille de route",
        "Pilot-only AI projects": "Specialisation EU AI Act integree",
        "No measurable ROI": "Independance totale (aucun editeur)",
        "AI-powered workflows": "Expertise workforce unique sur le marche",
        "Cross-functional integration": "Transformation technologique ET humaine",
        "Production-grade deployment": "Recommandations au service de vos interets",
        "Tracked, measurable outcomes": "From code to culture.",
    })

    # S12: Investment (Metrics)
    replace_text_in_slide(sf(order[11][1]), {
        "Key Metrics": "Investissement",
        "4": "EUR 95K",
        "85%": "5 sem.",
        "6mo": "43 j.",
        "3.2x": "50/50",
        "Phases of": "Prix HT",
        "transformation": "DIAGNOSE complet",
        "AI adoption rate": "Duree",
        "post-implementation": "Kick-off a livraison",
        "Average time": "Consulting",
        "to production": "Senior + technique",
        "ROI within": "Paiement",
        "first year": "Kick-off / Livraison",
    })

    # S13: What Comes Next (4-Phase dup)
    replace_text_in_slide(sf(order[12][1]), {
        "Our 4-Phase Approach": "Et Apres ? Un Partenariat Complet",
        "Diagnose": "DIAGNOSE",
        "Build": "BUILD",
        "Transition": "TRANSITION",
        "Assure": "ASSURE",
        "AI readiness assessment, workflow mapping, opportunity identification": "Audit de maturite IA, feuille de route, conformite. Vous etes ici. EUR 95K",
        "Agentic process redesign, LLM/RAG deployment, integration architecture": "Implementation IA, redesign processus, deploiement LLM/RAG. EUR 200-400K",
        "Workforce upskilling, change management, pilot-to-production scaling": "Transformation workforce, upskilling, change management. EUR 100-200K",
        "Ongoing governance, performance monitoring, continuous optimization": "Gouvernance continue, optimisation, monitoring IA. EUR 90K/an",
    })

    # S14: Let's Start (Thank You)
    replace_text_in_slide(sf(order[13][1]), {
        "Thank you": "Passons a l'Action",
        "From code to culture.": "Pret a transformer vos ambitions IA en resultats concrets.",
        "pascal@tokenshift.com": "Prochain pas : appel de cadrage 30 min",
        "+33 X XX XX XX XX": "Pascal, CEO | TokenShift",
        "tokenshift.com": "From code to culture.",
    })

    # 5. Clean and pack
    clean(work)
    out_path = os.path.join(OUT_DIR, "Auchan-AI-Discovery-Audit-Proposal-2026-02-23.pptx")
    pack(work, out_path, TEMPLATE)
    print(f"\nExternal deck: {out_path}")
    return out_path

# ── Main ─────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(WORK_BASE, exist_ok=True)
    internal = build_internal()
    external = build_external()
    print(f"\n=== DONE ===")
    print(f"Internal: {internal}")
    print(f"External: {external}")
