"""Stable contracts for sandboxed code execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SandboxRequest:
    """Input required to execute code in a sandbox workspace."""

    code: str
    test_code: str = ""
    language: str = "python"
    timeout_seconds: int = 30
    entry_point: str = "solution.py"


@dataclass(frozen=True)
class SandboxResult:
    """Captured result of one sandbox execution."""

    exit_code: int
    stdout: str
    stderr: str
    test_passed: bool
    timed_out: bool = False
    error: str | None = None

    @property
    def success(self) -> bool:
        """True when execution completed successfully without sandbox errors."""
        return self.exit_code == 0 and not self.timed_out and self.error is None

    def short_summary(self) -> str:
        """Return a compact human-readable execution summary."""
        parts = [f"exit_code={self.exit_code}"]
        if self.timed_out:
            parts.append("timed_out=True")
        if self.stdout.strip():
            parts.append(f"stdout:\n{self.stdout.strip()[:1000]}")
        if self.stderr.strip():
            parts.append(f"stderr:\n{self.stderr.strip()[:1000]}")
        if self.error:
            parts.append(f"error={self.error}")
        parts.append(f"test_passed={self.test_passed}")
        return "\n".join(parts)
