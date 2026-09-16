"""Schemas for sandbox execution APIs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SandboxRunRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100_000)
    test_code: str = Field(default="", max_length=100_000)
    language: str = "python"
    timeout_seconds: int = Field(default=30, ge=1, le=120)


class SandboxRunResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    test_passed: bool
    timed_out: bool
    success: bool
    summary: str
