# Skill: Build Word Documents with `docx_helpers`

You write a short, self-contained Python script using the `DocxBuilder` class from `docx_helpers`.
The `docx_helpers` module is pre-installed in `/opt/sandbox`.

## Workflow
1. Initialize `DocxBuilder(theme="modern")`.
2. Add title, subtitles, headings, structured paragraphs, and bullet points.
3. Save document to `"document.docx"` or `"/work/artifact.docx"`.

## Quick Skeleton
```python
from docx_helpers import DocxBuilder

doc = DocxBuilder(theme="modern")
doc.add_title("Engineering Operations Audit", subtitle="Facility Alpha & Beta Review - Q3")

doc.add_heading("1. Executive Summary", level=1)
doc.add_paragraph("This report summarizes the operational review conducted across production facilities during the third quarter.")

doc.add_heading("2. Key Findings", level=1)
doc.add_bullet("Near-miss incident rate declined by 34% following the updated protocol.")
doc.add_bullet("Equipment maintenance cycles were reduced from 48 hours to 12 hours.")
doc.add_bullet("Material inventory tracking reached 99.4% accuracy.")

doc.add_heading("3. Recommendations", level=1)
doc.add_paragraph("Based on the audit, the following immediate actions are recommended:")
doc.add_bullet("Implement real-time sensor telematics on critical conveyor units.")
doc.add_bullet("Extend the technician safety certification program through Q4.")

doc.save("document.docx")
```

