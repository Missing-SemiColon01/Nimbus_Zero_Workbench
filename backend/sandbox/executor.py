"""Executors for isolated sandboxed code execution."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Protocol, Any

from backend.sandbox.contracts import SandboxRequest, SandboxResult

logger = logging.getLogger(__name__)


class SandboxExecutor(Protocol):
    """Execution interface shared by Docker and local fallback implementations."""

    def run(self, request: SandboxRequest) -> SandboxResult:
        ...


class DockerSandboxExecutor:
    """Run Python code inside a network-disabled Docker container."""

    SUPPORTED_ARTIFACT_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx"}

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

        try:
            client = docker.from_env()
        except Exception as exc:
            logger.error("Failed to initialize Docker client: %s", exc)
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr="",
                test_passed=False,
                error=f"Docker client initialization failed: {exc}",
            )

        timeout = request.timeout_seconds or self.timeout_seconds
        target_artifacts_dir = Path(request.artifacts_dir) if request.artifacts_dir else None

        # Create or use isolated workspace
        is_custom_workspace = bool(request.workspace_dir)
        if is_custom_workspace:
            workspace = Path(request.workspace_dir).resolve()
            workspace.mkdir(parents=True, exist_ok=True)
            return self._execute_in_workspace(client, workspace, request, timeout, target_artifacts_dir)
        else:
            prefix = f"workbench_sandbox_{request.task_id}_" if request.task_id else "workbench_sandbox_"
            with tempfile.TemporaryDirectory(prefix=prefix) as tmpdir:
                workspace = Path(tmpdir)
                return self._execute_in_workspace(client, workspace, request, timeout, target_artifacts_dir)

    def _execute_in_workspace(
        self,
        client: Any,
        workspace: Path,
        request: SandboxRequest,
        timeout: int,
        target_artifacts_dir: Path | None,
    ) -> SandboxResult:
        self._write_files(workspace, request)
        command = self._build_command(request)

        # Snapshot files in workspace before run
        existing_files = {p.name for p in workspace.rglob("*") if p.is_file()}

        container = None
        exit_code = -1
        timed_out = False
        stdout = ""
        stderr = ""

        # In Linux/Docker, mounting a host temp directory can cause permission issues if the container
        # runs as a non-root user (e.g. runner/1000:1000) while the host dir is owned by the host process.
        # Prioritize default container user (or matching host uid:gid) so container can read/write files.
        host_uid_gid = None
        if hasattr(os, "getuid") and hasattr(os, "getgid"):
            host_uid_gid = f"{os.getuid()}:{os.getgid()}"

        user_options = [None, host_uid_gid, "runner", "1000:1000"]
        run_error = None

        for user_candidate in user_options:
            run_kwargs: dict[str, Any] = {
                "command": command,
                "volumes": {
                    str(workspace): {
                        "bind": "/workspace",
                        "mode": "rw",
                    }
                },
                "working_dir": "/workspace",
                "network_disabled": True,
                "mem_limit": self.mem_limit,
                "cpu_quota": self.cpu_quota,
                "read_only": False,
                "remove": False,
                "detach": True,
            }
            if user_candidate:
                run_kwargs["user"] = user_candidate

            try:
                container = client.containers.run(self.image, **run_kwargs)
                run_error = None
                break
            except Exception as exc:
                run_error = exc
                err_str = str(exc).lower()
                # If failure is related to user not existing, try next user option
                if "user" in err_str or "unable to find user" in err_str or "no such user" in err_str:
                    continue
                break

        if container is None:
            logger.error("Failed to run Docker container: %s", run_error)
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr="",
                test_passed=False,
                error=f"Docker container execution failed: {run_error}",
            )

        try:
            try:
                result = container.wait(timeout=timeout)
                exit_code = int(result.get("StatusCode", 1))
                timed_out = False
            except Exception:
                timed_out = True
                exit_code = -1
                try:
                    stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
                    stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
                except Exception:
                    pass
                try:
                    container.kill()
                except Exception:
                    pass

            if not timed_out:
                try:
                    stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
                    stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
                except Exception as log_exc:
                    logger.warning("Failed to retrieve container logs: %s", log_exc)
        finally:
            # Automatically remove temporary container
            try:
                container.remove(force=True)
            except Exception as rem_exc:
                logger.debug("Failed to remove container: %s", rem_exc)

        # Collect any generated artifacts
        artifacts, generated_files = self._harvest_artifacts(
            workspace, existing_files, target_artifacts_dir, request.task_id
        )

        return SandboxResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            test_passed=bool(request.test_code) and exit_code == 0,
            timed_out=timed_out,
            artifacts=artifacts,
            generated_files=generated_files,
        )

    @classmethod
    def _harvest_artifacts(
        cls,
        workspace: Path,
        existing_files: set[str],
        target_artifacts_dir: Path | None,
        task_id: str | None,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        import shutil
        import mimetypes

        artifacts: list[str] = []
        generated_files: list[dict[str, Any]] = []

        for p in workspace.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in cls.SUPPORTED_ARTIFACT_EXTENSIONS:
                continue
            if p.name in existing_files:
                continue

            dest_path = p
            if target_artifacts_dir is not None:
                target_artifacts_dir.mkdir(parents=True, exist_ok=True)
                dest_path = target_artifacts_dir / p.name
                shutil.copy2(p, dest_path)

            storage_uri = str(dest_path.resolve())
            artifacts.append(storage_uri)

            mime_type, _ = mimetypes.guess_type(dest_path.name)
            stat = dest_path.stat()
            file_meta = {
                "filename": dest_path.name,
                "file_type": dest_path.suffix.lstrip(".").lower(),
                "size_bytes": stat.st_size,
                "storage_uri": storage_uri,
                "mime_type": mime_type or "application/octet-stream",
                "task_id": task_id or "unknown",
            }
            generated_files.append(file_meta)

        return artifacts, generated_files

    @staticmethod
    def _write_files(workspace: Path, request: SandboxRequest) -> None:
        try:
            workspace.chmod(0o777)
        except Exception:
            pass

        safe_entry = Path(request.entry_point).name or "solution.py"
        entry_stem = Path(safe_entry).stem
        entry_file = workspace / safe_entry
        entry_file.write_text(request.code, encoding="utf-8")
        try:
            entry_file.chmod(0o666)
        except Exception:
            pass

        if request.test_code:
            test_dir = workspace / "tests"
            test_dir.mkdir(exist_ok=True)
            try:
                test_dir.chmod(0o777)
            except Exception:
                pass

            init_file = test_dir / "__init__.py"
            init_file.write_text("", encoding="utf-8")
            try:
                init_file.chmod(0o666)
            except Exception:
                pass

            # Automatically expose symbols from the entry file (solution.py) into the test script
            # so models asserting variables or functions directly will not raise NameError
            test_content = request.test_code
            if f"import {entry_stem}" not in test_content and f"from {entry_stem}" not in test_content:
                test_content = f"import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parent.parent))\ntry:\n    from {entry_stem} import *\nexcept Exception:\n    pass\n\n{test_content}"
            gen_test_file = test_dir / "test_generated.py"
            gen_test_file.write_text(test_content, encoding="utf-8")
            try:
                gen_test_file.chmod(0o666)
            except Exception:
                pass

    @staticmethod
    def _build_command(request: SandboxRequest) -> list[str]:
        if request.test_code:
            return [
                "python",
                "-m",
                "pytest",
                "tests/test_generated.py",
                "-o",
                "pythonpath=.",
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

        target_artifacts_dir = Path(request.artifacts_dir) if request.artifacts_dir else None
        is_custom_workspace = bool(request.workspace_dir)

        if is_custom_workspace:
            workspace = Path(request.workspace_dir).resolve()
            workspace.mkdir(parents=True, exist_ok=True)
            return self._execute_in_workspace(workspace, request, target_artifacts_dir)
        else:
            prefix = f"workbench_mock_sandbox_{request.task_id}_" if request.task_id else "workbench_mock_sandbox_"
            with tempfile.TemporaryDirectory(prefix=prefix) as tmpdir:
                workspace = Path(tmpdir)
                return self._execute_in_workspace(workspace, request, target_artifacts_dir)

    def _execute_in_workspace(
        self,
        workspace: Path,
        request: SandboxRequest,
        target_artifacts_dir: Path | None,
    ) -> SandboxResult:
        DockerSandboxExecutor._write_files(workspace, request)
        existing_files = {p.name for p in workspace.rglob("*") if p.is_file()}

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

        artifacts, generated_files = DockerSandboxExecutor._harvest_artifacts(
            workspace, existing_files, target_artifacts_dir, request.task_id
        )

        return SandboxResult(
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            test_passed=bool(request.test_code) and proc.returncode == 0,
            artifacts=artifacts,
            generated_files=generated_files,
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
