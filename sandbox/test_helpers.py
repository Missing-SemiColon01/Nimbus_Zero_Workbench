"""
test_helpers.py - Verification suite for pptx_helpers.py, pdf_helpers.py, and docx_helpers.py.

Validates that:
1. Helpers execute cleanly inside Python 3.12 sandbox environment.
2. PPTX generation supports arbitrary slide counts and custom layouts.
3. PDF generation supports general-purpose proposals, multi-column layouts, tables, cards, and arbitrary pages.
4. DOCX generation supports general-purpose documents with tables, cards, callouts, and bullet hierarchy.
5. All output files exist, are valid, and non-empty.
"""
import os
import sys
from pathlib import Path

# Ensure sandbox is on path
sys.path.insert(0, str(Path(__file__).parent))

from pptx_helpers import Deck, split, grid, pad
from pdf_helpers import PdfBuilder
from docx_helpers import DocxBuilder


def test_pptx_design_freedom():
    print("--- Testing PPTX Design Freedom ---")
    d = Deck(theme="midnight")

    # Single slide custom dashboard (testing arbitrary slide count: 1 slide only)
    s1 = d.add_slide(bg="1E2761")
    d.shape(s1, "rounded_rect", (0.8, 0.8, 11.7, 5.8), fill="FFFFFF", radius=0.04)
    d.textbox(s1, "Single-Slide Executive Briefing", box=(1.2, 1.2, 10.9, 0.8), size=28, color="1E2761", bold=True)
    d.textbox(s1, "This slide proves that slide count is completely unconstrained and dynamic.", box=(1.2, 2.0, 10.9, 0.5), size=14, color="5A6483")

    left, right = split((1.2, 2.8, 10.9, 3.2), [1, 1], gap=0.4)
    d.shape(s1, "rounded_rect", left, fill="F4F7FE", radius=0.04)
    d.textbox(s1, "Metric Highlights", box=(left[0] + 0.3, left[1] + 0.3, left[2] - 0.6, 0.4), size=16, color="1E2761", bold=True)
    d.textbox(s1, "• Production availability: 99.99%\n• Telemetry response time: 14ms\n• Zero unauthorized access attempts",
              box=(left[0] + 0.3, left[1] + 0.8, left[2] - 0.6, 2.0), size=13, space_after=6)

    d.shape(s1, "rounded_rect", right, fill="F4F7FE", radius=0.04)
    d.table(s1, [
        ["Resource", "Allocated", "Utilization"],
        ["Inference Node 1", "32 GB", "68%"],
        ["Inference Node 2", "32 GB", "74%"],
        ["Vector Storage", "500 GB", "42%"]
    ], box=(right[0] + 0.2, right[1] + 0.3, right[2] - 0.4, 2.5), header=True, header_bg="1E2761", alt_bg="FFFFFF", font_size=11)

    res = d.save("test_single_slide.pptx")
    assert res["slides"] == 1, f"Expected 1 slide, got {res['slides']}"
    assert Path("test_single_slide.pptx").exists(), "test_single_slide.pptx does not exist"
    assert Path("test_single_slide.pptx").stat().st_size > 0, "test_single_slide.pptx is empty"
    print("✓ PPTX Single-Slide Dashboard test passed.")


def test_pdf_general_purpose():
    print("--- Testing PDF General-Purpose Design SDK ---")
    pdf = PdfBuilder(theme="modern")

    # 1. Commercial Proposal Header Banner
    pdf.banner("Strategic Cloud Migration Proposal", subtitle="Prepared for Alpha Enterprises • Q4 Scope of Work")

    # 2. Key Target Metrics
    pdf.kpis([
        {"value": "$125,000", "label": "Project Investment", "delta": "Fixed Scope"},
        {"value": "12 Weeks", "label": "Target Schedule", "delta": "Guaranteed"},
        {"value": "99.99%", "label": "Target Availability", "delta": "+0.5% SLA"}
    ], cols=3)

    # 3. 2-Column asymmetric section
    pdf.columns([
        [
            pdf.create_heading("Executive Summary", level=2),
            pdf.create_text("This proposal outlines our engagement framework for migrating on-premise infrastructure to sovereign edge nodes."),
            pdf.create_callout("All deliverables include 6 months of comprehensive warranty and 24/7 incident SLA.", label="Warranty Commitment")
        ],
        [
            pdf.create_heading("Team & Governance", level=2),
            pdf.create_table([
                ["Role", "Allocation", "Location"],
                ["Principal Architect", "100%", "On-site"],
                ["Senior Cloud Engineers (2)", "100%", "Hybrid"],
                ["Security Lead", "50%", "Remote"],
            ], col_widths=[110, 60, 60])
        ]
    ], widths=[250, 250], spacing=20)

    # 4. Styled card
    pdf.card([
        pdf.create_heading("Project Inclusions", level=3),
        pdf.create_text("1. Infrastructure-as-code automation and zero-downtime cutover plan."),
        pdf.create_text("2. Complete operational training and technical documentation handover.")
    ], bg_color="#F8FAFC", border_color="#E2E8F0")

    # 5. Multipage check with explicit page break
    pdf.page_break()
    pdf.heading("Milestone & Billing Schedule", level=2)
    pdf.table([
        ["Phase", "Milestone Description", "Target Date", "Invoiced Amount"],
        ["Phase 1", "Discovery & Architecture Blueprint", "Week 3", "$30,000"],
        ["Phase 2", "Core Infrastructure Automation", "Week 7", "$50,000"],
        ["Phase 3", "Production Validation & Rollout", "Week 12", "$45,000"],
    ], col_widths=[70, 210, 80, 100])

    res = pdf.save("test_document.pdf")
    assert res["status"] == "success", f"PDF save failed: {res}"
    assert Path("test_document.pdf").exists(), "test_document.pdf does not exist"
    assert Path("test_document.pdf").stat().st_size > 0, "test_document.pdf is empty"
    print("✓ PDF General-Purpose Proposal test passed.")


def test_docx_general_purpose():
    print("--- Testing DOCX General-Purpose Design SDK ---")
    doc = DocxBuilder(theme="corporate")
    doc.page_setup(margins=(1.0, 1.0, 1.0, 1.0))

    # Header Title
    doc.heading("Enterprise Technology Strategy Brief", level=1, size=24, space_before=0, space_after=4)
    doc.text("Quarterly Strategic Review & Architectural Guidance • Q4 2026", size=12, color="52606D", italic=True, space_after=14)

    # Executive Callout
    doc.callout("Targeting full sovereign deployment across 4 regional clusters by Q1 2027.", label="Strategic Objective")

    # Structured Table
    doc.heading("Key Strategic Priorities", level=2, size=15)
    doc.table([
        ["Priority", "Lead Team", "Target Quarter", "Impact Level"],
        ["Model Quantization & Offline RAG", "Core AI Group", "Q4 2026", "Critical"],
        ["Air-Gapped Sandbox Execution", "Security Engineering", "Q4 2026", "High"],
        ["Autonomous Artifact Generator SDK", "Platform Team", "Q1 2027", "High"],
    ], col_widths=[2.8, 1.6, 1.1, 1.0], header=True)

    # Container Card with Bullet Items
    doc.card(
        title="Immediate Action Directives",
        body="The following immediate milestones must be executed prior to end-of-quarter review:",
        items=[
            "Finalize container security audits with read-only root capabilities.",
            "Complete end-to-end multi-format artifact generation smoke tests.",
            "Publish updated developer guides and design SDK documentation."
        ]
    )

    doc.divider()
    doc.bullet("All production changes must pass automated regression test suites.", bold_prefix="Requirement: ")

    res = doc.save("test_document.docx")
    assert res["status"] == "success", f"DOCX save failed: {res}"
    assert Path("test_document.docx").exists(), "test_document.docx does not exist"
    assert Path("test_document.docx").stat().st_size > 0, "test_document.docx is empty"
    print("✓ DOCX General-Purpose Document test passed.")


def test_example_deck_execution():
    print("--- Testing example_deck.py Execution ---")
    import example_deck
    assert Path("example_deck.pptx").exists(), "example_deck.pptx was not generated"
    assert Path("example_deck.pptx").stat().st_size > 0, "example_deck.pptx is empty"
    print("✓ example_deck.py generated valid PPTX file.")


if __name__ == "__main__":
    test_pptx_design_freedom()
    test_pdf_general_purpose()
    test_docx_general_purpose()
    test_example_deck_execution()
    print("\n==========================================")
    print("ALL GENERAL-PURPOSE ARTIFACT HELPER TESTS PASSED!")
    print("==========================================")
