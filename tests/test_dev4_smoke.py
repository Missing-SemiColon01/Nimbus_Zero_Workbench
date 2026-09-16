import httpx
import pytest

from scripts.dev4_smoke import _expect


def test_expect_returns_json_for_expected_status():
    response = httpx.Response(200, json={"status": "ok"})

    assert _expect(response, 200, "health") == {"status": "ok"}


def test_expect_exits_for_unexpected_status():
    response = httpx.Response(500, text="broken")

    with pytest.raises(SystemExit):
        _expect(response, 200, "health")
