"""Schemas for verified coding workflow APIs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CodingRunRequest(BaseModel):
    requirement: str = Field(min_length=1, max_length=20000)
    test_code: str = Field(min_length=1, max_length=20000)
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=30, ge=1, le=120)


class CodingAttemptResponse(BaseModel):
    attempt: int
    code: str
    exit_code: int
    stdout: str
    stderr: str
    test_passed: bool
    timed_out: bool
    error: str | None = None


class CodingRunResponse(BaseModel):
    task_id: str
    status: str
    selected_model: str | None
    provider: str | None
    attempted_models: list[str]
    verified_code: str
    attempts: list[CodingAttemptResponse] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    execution_duration: float | None = None
