"""
backend/agents/events.py
========================
Async event bus for continuous agent activity streaming via SSE.

An AgentEventStreamer is created per task request. Backend components
(runtime, workbench, code_workflow) push typed events onto its queue.
The FastAPI SSE endpoint drains the queue and yields formatted
``data: {...}\\n\\n`` lines to the client until the ``done`` sentinel arrives.

Usage (emitter side):
    streamer = AgentEventStreamer()
    streamer.emit_thought("Selecting python-pptx generation strategy...")
    streamer.emit_tool_call_start("python-pptx", "Generating slide deck")
    streamer.emit_tool_call_log("python-pptx", "Slide 1 created")
    streamer.emit_tool_call_end("python-pptx", success=True, duration_ms=1840)
    streamer.emit_content_delta("Here is the presentation...")
    streamer.emit_artifact_ready("report.pptx", "pptx", 48000, "/api/v1/artifacts/report.pptx/download")
    streamer.emit_task_complete(task_id, duration_ms=4200)
    streamer.emit_done()

Usage (consumer/SSE side):
    async for event_str in streamer:
        yield event_str
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, AsyncIterator


# ---------------------------------------------------------------------------
# Typed event payloads
# ---------------------------------------------------------------------------

@dataclass
class TaskInitPayload:
    task_id: str
    model: str | None = None
    intent: str | None = None
    capabilities: list[str] = field(default_factory=list)


@dataclass
class ThoughtPayload:
    text: str
    phase: str = "reasoning"


@dataclass
class ToolCallStartPayload:
    tool: str
    description: str
    args_preview: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallLogPayload:
    tool: str
    line: str


@dataclass
class ToolCallEndPayload:
    tool: str
    success: bool
    duration_ms: float | None = None
    summary: str | None = None


@dataclass
class ContentDeltaPayload:
    delta: str


@dataclass
class ArtifactReadyPayload:
    name: str
    file_type: str
    size_bytes: int
    download_url: str
    preview_url: str | None = None


@dataclass
class TaskCompletePayload:
    task_id: str
    duration_ms: float
    model: str | None = None
    provider: str | None = None
    tool_count: int = 0


@dataclass
class TaskErrorPayload:
    error: str
    task_id: str | None = None


# ---------------------------------------------------------------------------
# Event envelope
# ---------------------------------------------------------------------------

@dataclass
class AgentStreamEvent:
    """Wire envelope: always has a ``type`` and a ``payload`` dict."""
    type: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_sse_line(self) -> str:
        """Format as a single SSE ``data:`` line (with trailing double-newline)."""
        data = json.dumps(
            {"type": self.type, "timestamp": self.timestamp, "payload": self.payload},
            default=str,
        )
        return f"data: {data}\n\n"


# ---------------------------------------------------------------------------
# Streamer
# ---------------------------------------------------------------------------

_DONE_SENTINEL = object()  # unique object marking stream completion


class AgentEventStreamer:
    """
    Per-task async event bus.

    Backend components call the ``emit_*`` helpers from any coroutine; the
    SSE route consumes events via ``async for event_str in streamer``.
    """

    def __init__(self, maxsize: int = 256) -> None:
        self._queue: asyncio.Queue[AgentStreamEvent | object] = asyncio.Queue(maxsize=maxsize)
        self._start_time = time.perf_counter()

    # -- Emit helpers ---------------------------------------------------------

    def _put(self, event_type: str, payload: Any) -> None:
        """Non-blocking enqueue. Drops silently if queue is full (safety guard)."""
        event = AgentStreamEvent(
            type=event_type,
            payload=asdict(payload) if hasattr(payload, "__dataclass_fields__") else payload,
        )
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            pass  # Never block an agent coroutine for a slow client

    def emit_task_init(
        self,
        task_id: str,
        model: str | None = None,
        intent: str | None = None,
        capabilities: list[str] | None = None,
    ) -> None:
        self._put("task_init", TaskInitPayload(
            task_id=task_id,
            model=model,
            intent=intent,
            capabilities=capabilities or [],
        ))

    def emit_thought(self, text: str, phase: str = "reasoning") -> None:
        self._put("thought", ThoughtPayload(text=text, phase=phase))

    def emit_tool_call_start(
        self,
        tool: str,
        description: str,
        args_preview: dict[str, Any] | None = None,
    ) -> None:
        self._put("tool_call_start", ToolCallStartPayload(
            tool=tool,
            description=description,
            args_preview=args_preview or {},
        ))

    def emit_tool_call_log(self, tool: str, line: str) -> None:
        self._put("tool_call_log", ToolCallLogPayload(tool=tool, line=line))

    def emit_tool_call_end(
        self,
        tool: str,
        success: bool,
        duration_ms: float | None = None,
        summary: str | None = None,
    ) -> None:
        self._put("tool_call_end", ToolCallEndPayload(
            tool=tool,
            success=success,
            duration_ms=duration_ms,
            summary=summary,
        ))

    def emit_content_delta(self, delta: str) -> None:
        self._put("content_delta", ContentDeltaPayload(delta=delta))

    def emit_artifact_ready(
        self,
        name: str,
        file_type: str,
        size_bytes: int,
        download_url: str,
        preview_url: str | None = None,
    ) -> None:
        self._put("artifact_ready", ArtifactReadyPayload(
            name=name,
            file_type=file_type,
            size_bytes=size_bytes,
            download_url=download_url,
            preview_url=preview_url,
        ))

    def emit_task_complete(
        self,
        task_id: str,
        model: str | None = None,
        provider: str | None = None,
        tool_count: int = 0,
    ) -> None:
        duration_ms = round((time.perf_counter() - self._start_time) * 1000, 1)
        self._put("task_complete", TaskCompletePayload(
            task_id=task_id,
            duration_ms=duration_ms,
            model=model,
            provider=provider,
            tool_count=tool_count,
        ))

    def emit_task_error(self, error: str, task_id: str | None = None) -> None:
        self._put("task_error", TaskErrorPayload(error=error, task_id=task_id))

    def emit_done(self) -> None:
        """Signal the consumer that the stream is finished."""
        try:
            self._queue.put_nowait(_DONE_SENTINEL)
        except asyncio.QueueFull:
            pass

    # -- Consumer (async iterator) -------------------------------------------

    async def __aiter__(self) -> AsyncIterator[str]:
        """
        Yields formatted SSE strings until the ``done`` sentinel is received.

        Also yields a keep-alive comment every 15 seconds so proxies and
        browsers do not drop the connection on long-running tasks.
        """
        while True:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=15.0)
            except (TimeoutError, asyncio.TimeoutError):
                # Keep-alive comment: browsers ignore SSE comment lines
                yield ": keepalive\n\n"
                continue

            if item is _DONE_SENTINEL:
                yield "data: {\"type\": \"done\"}\n\n"
                return

            assert isinstance(item, AgentStreamEvent)
            yield item.to_sse_line()
