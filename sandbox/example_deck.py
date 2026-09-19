"""
example_deck.py - Demonstrates genuine visual composition and layout freedom with pptx_helpers.

Every slide has a completely different layout tailored to its specific information:
1. Asymmetric Dark Hero Cover
2. Asymmetric Split (Left 35% KPI Callout, Right 65% Column Chart)
3. 3-Column Architecture Matrix (Modular Container Cards)
4. Full-Width Data & Benchmark Comparison Table
5. Phased Roadmap Timeline
6. Executive Decision & Action Dashboard
"""
import json
import sys
from pptx_helpers import Deck, split, vsplit, grid, pad, SW, SH, CW, CH, BODY

theme_choice = sys.argv[1] if len(sys.argv) > 1 else "teal"
d = Deck(theme=theme_choice)

# ==============================================================================
# Slide 1: Asymmetric Dark Hero Cover
# ==============================================================================
s1 = d.add_slide(bg="064E5A")
# Decorative accent geometry
d.shape(s1, kind="circle", box=(8.5, 0.8, 5.0, 5.0), fill="028090", decor=True)
d.shape(s1, kind="circle", box=(11.0, 4.2, 2.5, 2.5), fill="00A6A6", decor=True)

# Metadata Category Badge
d.shape(s1, kind="rounded_rect", box=(0.9, 1.2, 3.4, 0.45), fill="00A6A6", radius=0.2)
d.textbox(s1, "EXECUTIVE BRIEFING  |  Q3 2026", box=(0.9, 1.2, 3.4, 0.45), size=11, color="064E5A", bold=True, align="center", vertical_align="middle", fit=False)

# Main Title & Subtitle
d.textbox(s1, "Autonomous Edge Infrastructure", box=(0.9, 2.0, 8.5, 2.0), size=44, color="FFFFFF", bold=True, align="left")
d.textbox(s1, "Performance benchmarks, telemetry audit findings, and multi-region deployment roadmap.",
          box=(0.9, 4.1, 7.8, 1.0), size=18, color="BFEDE6", align="left")

# Footer Author / Context
d.line(s1, start=(0.9, 5.8), end=(9.0, 5.8), color="00A6A6", width=1.5)
d.textbox(s1, "Prepared by Sovereign Engineering Group  •  Facility Plant Alpha & Beta",
          box=(0.9, 6.0, 9.0, 0.4), size=12, color="CADCFC", align="left")

# ==============================================================================
# Slide 2: Asymmetric Split (35% Left KPI Callout, 65% Right Performance Chart)
# ==============================================================================
s2 = d.add_slide(bg="FFFFFF")
d.textbox(s2, "Throughput Scaled Across All Production Units", box=(0.8, 0.6, CW, 0.8), size=30, color="064E5A", bold=True)
d.textbox(s2, "PERFORMANCE METRICS", box=(0.8, 0.35, 4.0, 0.3), size=11, color="017060", bold=True, fit=False)

left_box, right_box = split((0.8, 1.8, CW, 5.0), [3.5, 6.5], gap=0.4)

# Left: High-impact KPI Card
d.shape(s2, kind="rounded_rect", box=left_box, fill="064E5A", radius=0.06, shadow=True)
d.textbox(s2, "KEY TAKEAWAY", box=(left_box[0] + 0.3, left_box[1] + 0.3, left_box[2] - 0.6, 0.3), size=11, color="00A6A6", bold=True, fit=False)
d.textbox(s2, "+114%", box=(left_box[0] + 0.3, left_box[1] + 0.8, left_box[2] - 0.6, 1.2), size=52, color="FFFFFF", bold=True)
d.textbox(s2, "Telemetry event capacity increased while latency dropped by 28ms under peak load.",
          box=(left_box[0] + 0.3, left_box[1] + 2.2, left_box[2] - 0.6, 1.4), size=15, color="BFEDE6")
d.shape(s2, kind="rounded_rect", box=(left_box[0] + 0.3, left_box[1] + 3.8, left_box[2] - 0.6, 0.8), fill="028090", radius=0.04)
d.textbox(s2, "✓  Zero queue drops recorded across 45 million transactions.",
          box=(left_box[0] + 0.4, left_box[1] + 3.9, left_box[2] - 0.8, 0.6), size=12, color="FFFFFF", bold=True)

# Right: Clustered Column Chart
d.chart(s2, kind="column", categories=["Q1", "Q2", "Q3 (Target)", "Q3 (Actual)"],
        series={"Standard Capacity": [22, 28, 35, 38], "Accelerated Tier": [14, 21, 30, 42]},
        box=right_box, title="Throughput Index (M Ops/Sec)", fmt="#,##0")

# ==============================================================================
# Slide 3: 3-Column Architecture Matrix (Modular Container Cards)
# ==============================================================================
s3 = d.add_slide(bg="F5F7FA")
d.textbox(s3, "Three Architectural Pillars of Sovereign Execution", box=(0.8, 0.6, CW, 0.8), size=30, color="064E5A", bold=True)
d.textbox(s3, "SYSTEM ARCHITECTURE", box=(0.8, 0.35, 4.0, 0.3), size=11, color="017060", bold=True, fit=False)

cols = split((0.8, 1.7, CW, 5.1), [1, 1, 1], gap=0.35)
pillars = [
    {
        "num": "01",
        "title": "Local Edge Isolation",
        "tag": "AIR-GAPPED",
        "body": "Zero network egress required. All embedding, retrieval, and inference execute on local hardware.",
        "points": ["No external API dependencies", "Immutable local vector store", "Hardware-accelerated quantization"]
    },
    {
        "num": "02",
        "title": "Deterministic Tooling",
        "tag": "SANDBOXED",
        "body": "Artifacts compile inside isolated Docker execution boundaries with resource and capability caps.",
        "points": ["Memory & CPU quota limits", "Read-only file system access", "Automatic artifact harvesting"]
    },
    {
        "num": "03",
        "title": "Traceable Governance",
        "tag": "AUDIT-READY",
        "body": "Every decision, tool call, and policy evaluation produces immutable hash-chained audit records.",
        "points": ["Granular policy enforcement", "Human-in-the-loop approvals", "Exportable compliance logs"]
    }
]

for box, p in zip(cols, pillars):
    # Card Background
    d.shape(s3, kind="rounded_rect", box=box, fill="FFFFFF", border="DCE3EC", radius=0.06, shadow=True)
    # Header Band
    d.shape(s3, kind="rounded_rect", box=(box[0], box[1], box[2], 0.7), fill="064E5A", radius=0.06)
    d.textbox(s3, p["num"], box=(box[0] + 0.2, box[1] + 0.15, 0.6, 0.4), size=18, color="00A6A6", bold=True)
    d.textbox(s3, p["tag"], box=(box[0] + box[2] - 1.6, box[1] + 0.2, 1.4, 0.3), size=9, color="BFEDE6", bold=True, align="right", fit=False)
    # Card Content
    d.textbox(s3, p["title"], box=(box[0] + 0.25, box[1] + 0.9, box[2] - 0.5, 0.6), size=19, color="064E5A", bold=True)
    d.textbox(s3, p["body"], box=(box[0] + 0.25, box[1] + 1.55, box[2] - 0.5, 1.2), size=13, color="52606D")
    d.line(s3, start=(box[0] + 0.25, box[1] + 2.85), end=(box[0] + box[2] - 0.25, box[1] + 2.85), color="DCE3EC")
    # Bullet points
    for idx, pt in enumerate(p["points"]):
        d.textbox(s3, f"•  {pt}", box=(box[0] + 0.25, box[1] + 3.05 + (idx * 0.55), box[2] - 0.5, 0.5), size=12, color="1F2933", bold=False)

# ==============================================================================
# Slide 4: Full-Width Data & Benchmark Comparison Table
# ==============================================================================
s4 = d.add_slide(bg="FFFFFF")
d.textbox(s4, "Multi-Cluster Production Benchmark Results", box=(0.8, 0.6, CW, 0.8), size=30, color="064E5A", bold=True)
d.textbox(s4, "VALIDATION AUDIT", box=(0.8, 0.35, 4.0, 0.3), size=11, color="017060", bold=True, fit=False)

table_data = [
    ["Cluster Environment", "Workload Type", "P95 Latency", "Error Rate", "Compliance Score", "Production Status"],
    ["Cluster Alpha (Edge)", "Vision & OCR Ingestion", "34.2 ms", "0.002%", "99.8 / 100", "Certified Operational"],
    ["Cluster Beta (Central)", "RAG Vector Retrieval", "18.6 ms", "0.000%", "100.0 / 100", "Certified Operational"],
    ["Cluster Gamma (Isolated)", "Sandbox Python Execution", "82.1 ms", "0.012%", "98.9 / 100", "Certified Operational"],
    ["Cluster Delta (Staging)", "Model Provider Routing", "12.4 ms", "0.001%", "99.5 / 100", "Validation Phase"],
    ["Global Failover Node", "Hot Standby Replication", "4.1 ms", "0.000%", "100.0 / 100", "Active Standby"],
]

d.table(s4, rows=table_data, box=(0.8, 1.7, CW, 4.4),
        header=True, header_bg="064E5A", header_color="FFFFFF",
        alt_bg="F0FDFA", font_size=12,
        col_widths=[2.4, 2.5, 1.6, 1.4, 2.0, 2.033])

d.shape(s4, kind="rounded_rect", box=(0.8, 6.35, CW, 0.6), fill="E6FFFA", border="00A6A6", radius=0.03)
d.textbox(s4, "✓  All production clusters meet ISO-27001 latency and 99.5% minimum compliance standards.",
          box=(1.0, 6.42, CW - 0.4, 0.45), size=12, color="064E5A", bold=True, fit=False)

# ==============================================================================
# Slide 5: Phased Strategic Roadmap (Timeline Flow)
# ==============================================================================
s5 = d.add_slide(bg="F5F7FA")
d.textbox(s5, "Phased Implementation Timeline & Milestones", box=(0.8, 0.6, CW, 0.8), size=30, color="064E5A", bold=True)
d.textbox(s5, "STRATEGIC ROADMAP", box=(0.8, 0.35, 4.0, 0.3), size=11, color="017060", bold=True, fit=False)

roadmap_steps = [
    {"title": "Phase 1: Architecture Audit", "body": "Consolidate model registry, audit pipelines, and sandbox policies."},
    {"title": "Phase 2: Edge Pilot", "body": "Deploy 12 edge inspection units at Facility Alpha with zero egress."},
    {"title": "Phase 3: Security Hardening", "body": "Implement memory limits, sandbox privilege dropping, and audit verification."},
    {"title": "Phase 4: Global Rollout", "body": "Scale to 45 clusters with real-time health telemetry and failover."},
]

d.timeline(s5, roadmap_steps, box=(0.8, 2.0, CW, 4.5), orient="h")

# ==============================================================================
# Slide 6: Executive Decision & Action Dashboard
# ==============================================================================
s6 = d.add_slide(bg="0B192C")
d.textbox(s6, "Executive Recommendations & Sign-Off Matrix", box=(0.8, 0.6, CW, 0.8), size=30, color="FFFFFF", bold=True)
d.textbox(s6, "DECISION DASHBOARD", box=(0.8, 0.35, 4.0, 0.3), size=11, color="00A6A6", bold=True, fit=False)

# Top KPI Summary Row
kpi_boxes = split((0.8, 1.7, CW, 1.5), [1, 1, 1, 1], gap=0.3)
metrics = [
    ("45/45", "Nodes Online"),
    ("100%", "Compliance"),
    ("$1.4M", "Annualized Savings"),
    ("Oct 1", "Go-Live Target")
]
for k_box, (m_val, m_lab) in zip(kpi_boxes, metrics):
    d.shape(s6, kind="rounded_rect", box=k_box, fill="1E3E62", radius=0.06)
    d.textbox(s6, m_val, box=(k_box[0] + 0.15, k_box[1] + 0.2, k_box[2] - 0.3, 0.6), size=24, color="00A6A6", bold=True, align="center")
    d.textbox(s6, m_lab, box=(k_box[0] + 0.15, k_box[1] + 0.85, k_box[2] - 0.3, 0.4), size=12, color="E0E0E0", align="center")

# Bottom Split: Left Approved Actions, Right Next Milestones
b_left, b_right = split((0.8, 3.5, CW, 3.2), [1, 1], gap=0.4)

d.shape(s6, kind="rounded_rect", box=b_left, fill="1E3E62", radius=0.06)
d.textbox(s6, "APPROVED OPERATIONAL DIRECTIVES", box=(b_left[0] + 0.3, b_left[1] + 0.3, b_left[2] - 0.6, 0.4), size=13, color="00A6A6", bold=True)
d.textbox(s6, "1. Authorize procurement of additional local GPU inference nodes for Facility Beta.\n2. Mandate offline sandbox execution for all customer-facing document builds.\n3. Ratify revised SLA target of 99.95% for all core telemetry services.",
          box=(b_left[0] + 0.3, b_left[1] + 0.8, b_left[2] - 0.6, 2.1), size=13, color="FFFFFF", space_after=8)

d.shape(s6, kind="rounded_rect", box=b_right, fill="1E3E62", radius=0.06)
d.textbox(s6, "IMMEDIATE NEXT STEPS", box=(b_right[0] + 0.3, b_right[1] + 0.3, b_right[2] - 0.6, 0.4), size=13, color="00A6A6", bold=True)
d.textbox(s6, "•  Friday, 17:00 UTC — Complete final smoke test across production clusters.\n•  Monday, 09:00 UTC — Executive sign-off on Q4 infrastructure budget.\n•  Wednesday, 14:00 UTC — Comprehensive security drill with air-gapped simulation.",
          box=(b_right[0] + 0.3, b_right[1] + 0.8, b_right[2] - 0.6, 2.1), size=13, color="FFFFFF", space_after=8)

# Output JSON result
result = d.save("example_deck.pptx")
print(json.dumps(result, indent=2))
