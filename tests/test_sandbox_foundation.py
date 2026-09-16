from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.sandbox.contracts import SandboxRequest, SandboxResult
from backend.sandbox.executor import DockerSandboxExecutor, MockSandboxExecutor, build_executor


def test_sandbox_result_success_helpers():
    assert SandboxResult(exit_code=0, stdout="", stderr="", test_passed=False).success is True
    assert SandboxResult(exit_code=1, stdout="", stderr="", test_passed=False).success is False
    assert SandboxResult(exit_code=0, stdout="", stderr="", test_passed=False, timed_out=True).success is False


def test_sandbox_result_summary_contains_core_fields():
    result = SandboxResult(exit_code=2, stdout="hello", stderr="oops", test_passed=False, error="bad")

    summary = result.short_summary()

    assert "exit_code=2" in summary
    assert "hello" in summary
    assert "oops" in summary
    assert "error=bad" in summary
    assert "test_passed=False" in summary


def test_mock_executor_runs_simple_python():
    result = MockSandboxExecutor().run(SandboxRequest(code="print('hello sandbox')"))

    assert result.success is True
    assert "hello sandbox" in result.stdout


def test_mock_executor_runs_passing_pytest():
    code = "def add(a, b):\n    return a + b\n"
    test_code = (
        "import importlib.util, pathlib\n"
        "root = pathlib.Path(__file__).parent.parent\n"
        "spec = importlib.util.spec_from_file_location('solution', root / 'solution.py')\n"
        "solution = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(solution)\n"
        "def test_add():\n"
        "    assert solution.add(2, 3) == 5\n"
    )

    result = MockSandboxExecutor().run(SandboxRequest(code=code, test_code=test_code))

    assert result.success is True
    assert result.test_passed is True


def test_mock_executor_reports_timeout():
    result = MockSandboxExecutor().run(
        SandboxRequest(code="import time; time.sleep(10)", timeout_seconds=1)
    )

    assert result.success is False
    assert result.timed_out is True


def test_docker_executor_passes_isolation_flags():
    mock_docker = MagicMock()
    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = b""
    mock_docker.from_env.return_value.containers.run.return_value = mock_container

    with patch.dict("sys.modules", {"docker": mock_docker}):
        result = DockerSandboxExecutor(image="test-image").run(SandboxRequest(code="print(1)"))

    assert result.success is True
    call_kwargs = mock_docker.from_env.return_value.containers.run.call_args.kwargs
    assert call_kwargs["network_disabled"] is True
    assert call_kwargs["mem_limit"] == "256m"
    assert call_kwargs["cpu_quota"] == 50_000
    assert call_kwargs["user"] == "runner"
    assert list(call_kwargs["volumes"].values())[0]["bind"] == "/workspace"


def test_build_executor_falls_back_when_docker_unavailable():
    mock_docker = MagicMock()
    mock_docker.from_env.return_value.ping.side_effect = RuntimeError("no docker")

    with patch.dict("sys.modules", {"docker": mock_docker}):
        executor = build_executor()

    assert isinstance(executor, MockSandboxExecutor)
