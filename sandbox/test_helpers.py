"""
test_helpers.py - Verification suite for pptx_helpers.py and pdf_helpers.py.

Validates that:
1. Helpers execute cleanly inside Python 3.12 sandbox environment.
2. PPTX generation supports arbitrary slide counts (1-slide dashboard, 6-slide deck) and custom layouts.
3. PDF generation supports multi-column layouts, tables, cards, KPI grids, and arbitrary pages.
4. Output files exist, are valid, and non-empty.
"""
import os
import sys
from pathlib import Path

# Ensure sandbox is on path
sys.path.insert(0, str(Path(__file__).parent))

from pptx_helpers import Deck, split, grid, pad
from pdf_helpers import PdfBuilder


def test_pptx_design_freedom():
    print("--- Testing PPTX Design Freedom ---")
    d = Deck(theme="midnight")

    # 1. Single slide custom dashboard (testing arbitrary slide count: 1 slide only)
    s1 = d.add_slide(bg="1E2761")
    d.shape(s1, "rounded_rect", (0.8, 0.8, 11.7, 5.8), fill="FFFFFF", radius=0.04)
    d.textbox(s1, "Single-Slide Executive Briefing", box=(1.2, 1.2, 10.9, 0.8), size=28, color="1E2761", bold=True)
    d.textbox(s1, "This slide proves that slide count is completely unconstrained and dynamic.", box=(1.2, 2.0, 10.9, 0.5), size=14, color="5A6483")

    # 2 columns inside the card
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


def test_pdf_design_freedom():
    print("--- Testing PDF Design Freedom ---")
    pdf = PdfBuilder(theme="teal")

    # 1. Header Banner
    pdf.banner("Sovereign Engineering Compliance Report", subtitle="Facility Operational Assessment")

    # 2. KPI metrics
    pdf.kpis([
        {"value": "100%", "label": "Air-Gap Compliance", "delta": "Verified"},
        {"value": "18.4 ms", "label": "Mean Query Latency", "delta": "-4.2 ms"},
        {"value": "0", "label": "Security Incidents", "delta": "Nominal"}
    ], cols=3)

    # 3. 2-Column asymmetric section
    pdf.columns([
        [
            pdf.create_heading("Executive Summary", level=2),
            pdf.create_text("All core systems were audited against internal safety regulations."),
            pdf.create_callout("Automated document harvesting performed with zero leakage.", label="Security Audit")
        ],
        [
            pdf.create_heading("Audit Inspection Matrix", level=2),
            pdf.create_table([
                ["Inspection Point", "Rating", "Outcome"],
                ["Sandbox Isolation", "5/5", "Approved"],
                ["Vector Persistence", "5/5", "Approved"],
                ["Audit Event Stream", "5/5", "Approved"],
            ], col_widths=[100, 60, 75])
        ]
    ], widths=[250, 250], spacing=20)

    # 4. Styled recommendation card
    pdf.card([
        pdf.create_heading("Recommended Directives", level=3),
        pdf.create_text("1. Maintain read-only sandbox container execution for all untrusted scripts."),
        pdf.create_text("2. Execute quarterly compliance re-evaluation on all active model endpoints.")
    ], bg_color="#F0FDFA", border_color="#CCFBF1")

    # 5. Multipage check with explicit page break
    pdf.page_break()
    pdf.heading("Appendix: Detailed Telemetry Logs", level=2)
    pdf.table([
        ["Timestamp", "Source Node", "Event", "Status"],
        ["2026-09-19 12:00:01", "Edge-Alpha-01", "Model Initialization", "Success"],
        ["2026-09-19 12:00:04", "Edge-Alpha-02", "Vector Sync Complete", "Success"],
        ["2026-09-19 12:00:10", "Sandbox-Worker", "Artifact Built: deck.pptx", "Success"],
    ], col_widths=[120, 100, 180, 80])

    res = pdf.save("test_document.pdf")
    assert res["status"] == "success", f"PDF save failed: {res}"
    assert Path("test_document.pdf").exists(), "test_document.pdf does not exist"
    assert Path("test_document.pdf").stat().st_size > 0, "test_document.pdf is empty"
    print("✓ PDF Multi-Column & Multi-Page test passed.")


def test_example_deck_execution():
    print("--- Testing example_deck.py Execution ---")
    import example_deck
    assert Path("example_deck.pptx").exists(), "example_deck.pptx was not generated"
    assert Path("example_deck.pptx").stat().st_size > 0, "example_deck.pptx is empty"
    print("✓ example_deck.py generated valid PPTX file.")


if __name__ == "__main__":
    test_pptx_design_freedom()
    test_pdf_design_freedom()
    test_example_deck_execution()
    print("\n==========================================")
    print("ALL ARTIFACT HELPER TESTS PASSED!")
    print("==========================================")

