"""Dev 4A local backend smoke checks.

Run after starting the API:
    .venv\\Scripts\\python.exe scripts\\dev4_smoke.py
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx


def _print_check(name: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def _expect(response: httpx.Response, status_code: int, name: str) -> dict[str, Any] | list[Any]:
    if response.status_code != status_code:
        _print_check(name, False, f"HTTP {response.status_code}: {response.text[:300]}")
        raise SystemExit(1)
    _print_check(name, True)
    return response.json()


def run(base_url: str) -> None:
    api = base_url.rstrip("/")
    with httpx.Client(timeout=20.0) as client:
        health = _expect(client.get(f"{api}/health"), 200, "health")
        _print_check("sovereign mode", bool(health.get("sovereign_mode")), json.dumps(health))

        models = _expect(client.get(f"{api}/models"), 200, "models")
        _print_check("model registry non-empty", isinstance(models, list) and bool(models), f"{len(models)} model(s)")

        tools = _expect(client.get(f"{api}/tools"), 200, "tools")
        tool_names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
        required_tools = {"rag.search", "vision.analyze", "document.create", "presentation.create"}
        missing_tools = sorted(required_tools.difference(tool_names))
        _print_check("required tools registered", not missing_tools, f"missing={missing_tools}" if missing_tools else "")

        task = _expect(
            client.post(
                f"{api}/tasks",
                json={
                    "request": "Summarize this local smoke test request in one sentence.",
                    "task_type": "reasoning",
                },
            ),
            201,
            "basic task",
        )
        _print_check("task id returned", bool(task.get("task_id")), task.get("task_id", ""))
        _print_check("task trace fields returned", "tool_results" in task and "generated_artifacts" in task)

        artifacts = _expect(client.get(f"{api}/artifacts"), 200, "artifacts")
        _print_check("artifact list shape", isinstance(artifacts, list), f"{len(artifacts)} artifact(s)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Dev 4A local backend smoke checks.")
    parser.add_argument("--api", default="http://localhost:8000/api/v1", help="Base API URL")
    args = parser.parse_args()
    try:
        run(args.api)
    except httpx.ConnectError:
        print(f"[FAIL] API unavailable at {args.api}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
