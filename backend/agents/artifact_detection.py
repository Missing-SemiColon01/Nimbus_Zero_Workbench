"""Classify user requests that require deliverable artifact generation (e.g. pptx, xlsx, pdf, docx)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactIntent:
    """Detected artifact-generation intent."""

    artifact_type: str
    tool_name: str | None = None


# Explicit task_type mapping to canonical deliverable formats.
_TASK_TYPE_MAP: dict[str, str] = {
    "presentation": "pptx",
    "pptx": "pptx",
    "slides": "pptx",
    "spreadsheet": "xlsx",
    "xlsx": "xlsx",
    "excel": "xlsx",
    "pdf": "pdf",
    "docx": "docx",
    "document": "docx",
    "report": "docx",
    "artifact": "docx",
}

# Ordered list of (compiled regex, canonical artifact_type).
# Patterns are tried in order; the first match wins.
# Specific formats (pptx, xlsx, pdf) must appear before broad document/report patterns.
_ARTIFACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 1. Presentation / slides (pptx)
    (
        re.compile(
            r"\b(?:create|generate|build|prepare|make|produce|draft|design)\b.*"
            r"\b(?:presentation|slide[s]?|deck|pitch\s*deck|slide\s*deck|powerpoint|pptx)\b",
            re.IGNORECASE,
        ),
        "pptx",
    ),
    (
        re.compile(
            r"\b(?:presentation|slide[s]?|deck|pitch\s*deck|slide\s*deck|powerpoint|pptx)\b.*"
            r"\b(?:for|about|on|regarding|explaining|covering|summarizing)\b",
            re.IGNORECASE,
        ),
        "pptx",
    ),
    # 2. Spreadsheet / Excel (xlsx)
    (
        re.compile(
            r"\b(?:create|generate|build|prepare|make|produce|draft|design)\b.*"
            r"\b(?:spreadsheet|excel|xlsx|workbook|financial\s*model|budget\s*sheet|balance\s*sheet|data\s*sheet)\b",
            re.IGNORECASE,
        ),
        "xlsx",
    ),
    (
        re.compile(
            r"\b(?:spreadsheet|excel|xlsx|workbook|financial\s*model|budget\s*sheet|balance\s*sheet)\b.*"
            r"\b(?:for|about|with|containing|on|tracking|calculating)\b",
            re.IGNORECASE,
        ),
        "xlsx",
    ),
    # 3. PDF (pdf) - must precede generic document/report patterns
    (
        re.compile(
            r"\b(?:create|generate|build|prepare|make|produce|draft|export)\b.*\b(?:pdf)\b",
            re.IGNORECASE,
        ),
        "pdf",
    ),
    (
        re.compile(
            r"\b(?:pdf)\s+(?:report|document|note|file|memo|summary|whitepaper|invoice|brief)\b",
            re.IGNORECASE,
        ),
        "pdf",
    ),
    (
        re.compile(
            r"\b(?:pdf)\b.*\b(?:for|about|on|regarding|summarizing|covering)\b",
            re.IGNORECASE,
        ),
        "pdf",
    ),
    # 4. Document / report / approval note / memo (docx) - broadest, evaluated last
    (
        re.compile(
            r"\b(?:create|generate|build|prepare|make|produce|draft|write)\b.*"
            r"\b(?:report|document|approval\s+note|docx|memo|summary\s+report|brief|proposal|whitepaper|minutes|guideline[s]?)\b",
            re.IGNORECASE,
        ),
        "docx",
    ),
    (
        re.compile(
            r"\b(?:approval\s+note|report|document|docx|memo|brief|proposal|whitepaper)\b.*"
            r"\b(?:for|about|on|regarding|covering|summarizing)\b",
            re.IGNORECASE,
        ),
        "docx",
    ),
]


def detect_artifact_intent(
    user_request: str,
    task_type: str | None = None,
) -> ArtifactIntent | None:
    """Return the artifact intent for *user_request*, or ``None`` if no artifact is needed.

    Detection strategy
    ------------------
    1. **Explicit task_type**: Recognized task types (e.g. ``"report"``, ``"artifact"``,
       ``"presentation"``) qualify as deliverable requests. The request text is still
       scanned for a more specific format match; if none matches, the mapped canonical
       format (e.g. ``"docx"`` for ``"report"``) is used.
    2. **Keyword heuristics**: The request text is matched against ordered regex patterns
       covering presentations (pptx), spreadsheets (xlsx), PDFs (pdf), and documents (docx).
       This general-purpose detection supports any domain (business, technology, operations,
       finance, academic, etc.).

    Parameters
    ----------
    user_request:
        The raw natural-language request from the user.
    task_type:
        Optional explicit task type from the API payload (e.g. ``"report"``).
    """
    if not user_request or not user_request.strip():
        return None

    # Check explicit task_type
    normalized_task_type = task_type.lower().strip() if task_type else None
    if normalized_task_type in _TASK_TYPE_MAP:
        # Still scan text for a more specific format if user request mentions one
        for pattern, artifact_type in _ARTIFACT_PATTERNS:
            if pattern.search(user_request):
                return ArtifactIntent(artifact_type=artifact_type)
        return ArtifactIntent(artifact_type=_TASK_TYPE_MAP[normalized_task_type])

    # Scan request text against ordered patterns
    for pattern, artifact_type in _ARTIFACT_PATTERNS:
        if pattern.search(user_request):
            return ArtifactIntent(artifact_type=artifact_type)

    return None
