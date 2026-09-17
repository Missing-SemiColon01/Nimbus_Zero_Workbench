"""Classify user requests that need artifact generation and route to the correct tool."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactIntent:
    """Detected artifact-generation intent with the target tool name."""

    artifact_type: str
    tool_name: str


# Ordered list of (compiled regex, artifact_type, tool_name).
# Patterns are tried in order; the first match wins.  More specific patterns
# (e.g. "approval note") must appear before broad ones (e.g. "report").
_ARTIFACT_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # Presentation / slides
    (
        re.compile(
            r"\b(?:create|generate|build|prepare|make|produce|draft)\b.*"
            r"\b(?:presentation|slide[s]?|deck|pptx)\b",
            re.IGNORECASE,
        ),
        "presentation",
        "presentation.create",
    ),
    (
        re.compile(r"\b(?:presentation|slide[s]?|deck|pptx)\b.*\b(?:for|about|on|regarding)\b", re.IGNORECASE),
        "presentation",
        "presentation.create",
    ),
    # Spreadsheet / Excel
    (
        re.compile(
            r"\b(?:create|generate|build|prepare|make|produce|draft)\b.*"
            r"\b(?:spreadsheet|excel|xlsx|workbook)\b",
            re.IGNORECASE,
        ),
        "spreadsheet",
        "spreadsheet.create",
    ),
    (
        re.compile(r"\b(?:spreadsheet|excel|xlsx|workbook)\b.*\b(?:for|about|with|containing)\b", re.IGNORECASE),
        "spreadsheet",
        "spreadsheet.create",
    ),
    # PDF (must precede generic document/report patterns)
    (
        re.compile(
            r"\b(?:create|generate|build|prepare|make|produce|draft)\b.*\b(?:pdf)\b",
            re.IGNORECASE,
        ),
        "pdf",
        "pdf.create",
    ),
    (
        re.compile(r"\b(?:pdf)\s+(?:report|document|note|file)\b", re.IGNORECASE),
        "pdf",
        "pdf.create",
    ),
    # Document / report / approval note (broadest — last)
    (
        re.compile(
            r"\b(?:create|generate|build|prepare|make|produce|draft|write)\b.*"
            r"\b(?:report|document|approval\s+note|docx|memo|summary\s+report)\b",
            re.IGNORECASE,
        ),
        "document",
        "document.create",
    ),
    (
        re.compile(r"\b(?:approval\s+note|report|document|docx)\b.*\b(?:for|about|on|regarding)\b", re.IGNORECASE),
        "document",
        "document.create",
    ),
]


def detect_artifact_intent(
    user_request: str,
    task_type: str | None = None,
) -> ArtifactIntent | None:
    """Return the artifact intent for *user_request*, or ``None`` if no artifact is needed.

    Detection strategy
    ------------------
    1. **Explicit task_type**: ``"report"`` or ``"artifact"`` immediately qualify as
       an artifact request; the text is then scanned for a more specific tool.
       If no specific pattern matches, the default is ``document.create``.
    2. **Keyword heuristics**: the request text is matched against ordered regex
       patterns covering presentations, spreadsheets, PDFs, and documents.

    Parameters
    ----------
    user_request:
        The raw natural-language request from the user.
    task_type:
        Optional explicit task type from the API payload (e.g. ``"report"``).
    """
    if not user_request or not user_request.strip():
        return None

    # Fast path: explicit task_type forces artifact generation.
    if task_type in {"report", "artifact"}:
        # Still scan text for a more specific artifact type.
        for pattern, artifact_type, tool_name in _ARTIFACT_PATTERNS:
            if pattern.search(user_request):
                return ArtifactIntent(artifact_type=artifact_type, tool_name=tool_name)
        # Default to document when no specific format is mentioned.
        return ArtifactIntent(artifact_type="document", tool_name="document.create")

    # Keyword-based detection on user_request text.
    for pattern, artifact_type, tool_name in _ARTIFACT_PATTERNS:
        if pattern.search(user_request):
            return ArtifactIntent(artifact_type=artifact_type, tool_name=tool_name)

    return None

