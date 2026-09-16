"""Executors for isolated sandboxed code execution."""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Protocol

from backend.sandbox.contracts import SandboxRequest, SandboxResult

logger = logging.getLogger(__name__)


class SandboxExecutor(Protocol):
    """Execution interface shared by Docker and local fallback implementations."""

    def run(self, request: SandboxRequest) -> SandboxResult:
        ...


class DockerSandboxExecutor:
    """Run Python code inside a network-disabled Docker container."""

    def __init__(
        self,
        image: str = "workbench-sandbox:latest",
        mem_limit: str = "256m",
        cpu_quota: int = 50_000,
        timeout_seconds: int = 30,
    ) -> None:
        self.image = image
        self.mem_limit = mem_limit
        self.cpu_quota = cpu_quota
        self.timeout_seconds = timeout_seconds

    def run(self, request: SandboxRequest) -> SandboxResult:
        if request.language != "python":
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr="",
                test_passed=False,
                error=f"Unsupported sandbox language: {request.language}",
            )

        try:
            import docker  # type: ignore
        except ImportError as exc:
            raise RuntimeError("docker Python SDK is required for DockerSandboxExecutor.") from exc

        client = docker.from_env()
        timeout = request.timeout_seconds or self.timeout_seconds

        with tempfile.TemporaryDirectory(prefix="workbench_sandbox_") as tmpdir:
            workspace = Path(tmpdir)
            self._write_files(workspace, request)
            command = self._build_command(request)

            container = None
            try:
                container = client.containers.run(
                    self.image,
                    command=command,
                    volumes={
                        str(workspace): {
                            "bind": "/workspace",
                            "mode": "rw",
                        }
                    },
                    working_dir="/workspace",
                    network_disabled=True,
                    mem_limit=self.mem_limit,
                    cpu_quota=self.cpu_quota,
                    read_only=False,
                    remove=False,
                    detach=True,
                    user="runner",
                )
                try:
                    result = container.wait(timeout=timeout)
                    exit_code = int(result.get("StatusCode", 1))
                    timed_out = False
                except Exception:
                    try:
                        container.kill()
                    except Exception:
                        pass
                    exit_code = -1
                    timed_out = True

                stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
                stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
            finally:
                if container is not None:
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass

        return SandboxResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            test_passed=bool(request.test_code) and exit_code == 0,
            timed_out=timed_out,
        )

    @staticmethod
    def _write_files(workspace: Path, request: SandboxRequest) -> None:
        safe_entry = Path(request.entry_point).name or "solution.py"
        (workspace / safe_entry).write_text(request.code, encoding="utf-8")
        if request.test_code:
            test_dir = workspace / "tests"
            test_dir.mkdir(exist_ok=True)
            (test_dir / "__init__.py").write_text("", encoding="utf-8")
            (test_dir / "test_generated.py").write_text(request.test_code, encoding="utf-8")

    @staticmethod
    def _build_command(request: SandboxRequest) -> list[str]:
        if request.test_code:
            return [
                "python",
                "-m",
                "pytest",
                "tests/test_generated.py",
                "-v",
                "--tb=short",
                "--no-header",
            ]
        return ["python", Path(request.entry_point).name or "solution.py"]


class MockSandboxExecutor:
    """Development fallback that runs code locally without isolation."""

    def run(self, request: SandboxRequest) -> SandboxResult:
        logger.warning("MockSandboxExecutor is not isolated. Use DockerSandboxExecutor for real sandboxing.")
        if request.language != "python":
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr="",
                test_passed=False,
                error=f"Unsupported sandbox language: {request.language}",
            )

        with tempfile.TemporaryDirectory(prefix="workbench_mock_sandbox_") as tmpdir:
            workspace = Path(tmpdir)
            DockerSandboxExecutor._write_files(workspace, request)
            if request.test_code:
                command = [
                    sys.executable,
                    "-m",
                    "pytest",
                    str(workspace / "tests" / "test_generated.py"),
                    "-v",
                    "--tb=short",
                    "--no-header",
                ]
            else:
                command = [sys.executable, str(workspace / (Path(request.entry_point).name or "solution.py"))]

            try:
                proc = subprocess.run(
                    command,
                    cwd=str(workspace),
                    capture_output=True,
                    text=True,
                    timeout=request.timeout_seconds or 30,
                )
            except subprocess.TimeoutExpired:
                return SandboxResult(
                    exit_code=-1,
                    stdout="",
                    stderr="",
                    test_passed=False,
                    timed_out=True,
                )
            except Exception as exc:
                return SandboxResult(
                    exit_code=-1,
                    stdout="",
                    stderr="",
                    test_passed=False,
                    error=str(exc),
                )

        return SandboxResult(
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            test_passed=bool(request.test_code) and proc.returncode == 0,
        )


def build_executor(
    image: str = "workbench-sandbox:latest",
    mem_limit: str = "256m",
    cpu_quota: int = 50_000,
    timeout_seconds: int = 30,
) -> SandboxExecutor:
    """Build Docker executor when Docker is reachable, otherwise dev fallback."""
    try:
        import docker  # type: ignore

        docker.from_env().ping()
    except Exception as exc:
        logger.warning("Docker unavailable (%s); using MockSandboxExecutor.", exc)
        return MockSandboxExecutor()

    return DockerSandboxExecutor(
        image=image,
        mem_limit=mem_limit,
        cpu_quota=cpu_quota,
        timeout_seconds=timeout_seconds,
    )
