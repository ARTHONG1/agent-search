import asyncio
import sys
import time
from unittest.mock import patch

import pytest

from agent_reach_plus.transport import (
    ReachError,
    bounded,
    redact,
    run_cli,
    validate_limit,
    validate_query,
    validate_url,
)


@pytest.mark.parametrize("value", ["", "  ", "--help", "x\n--cookie", "a" * 1001])
def test_rejects_query_option_injection(value):
    with pytest.raises(ReachError):
        validate_query(value)


@pytest.mark.parametrize("value", ["file:///a", "https://u:p@example.com", "http://127.0.0.1/x", "http://[::1]/", "http://localhost", "https://example.com:22", "http://2130706433/"])
def test_private_and_credential_urls_rejected(value):
    with pytest.raises(ReachError):
        asyncio.run(validate_url(value))


def test_private_dns_rejected():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("192.168.1.1", 443))]):
        with pytest.raises(ReachError):
            asyncio.run(validate_url("https://public.example/"))


def test_limits_and_boolean_rejected():
    for n in [0, -1, 21, True, 1.5]:
        with pytest.raises(ReachError):
            validate_limit(n)


def test_subprocess_bounded_without_shell():
    with patch("agent_reach_plus.transport.cli_argv", return_value=[sys.executable]):
        result = asyncio.run(run_cli("test", ["-c", "print('literal & echo no shell')"]))
    assert result.strip() == "literal & echo no shell"


def test_subprocess_timeout_is_actionable():
    with patch("agent_reach_plus.transport.cli_argv", return_value=[sys.executable]):
        with pytest.raises(ReachError, match="timeout"):
            asyncio.run(run_cli("test", ["-c", "import time; time.sleep(5)"], timeout=0.1))


def test_output_cap_indicates_truncation():
    result = bounded({"text": "a" * 1000}, 100)
    assert result["truncated"] is True
    assert len(result["preview"]) == 100


def test_errors_redact_credentials():
    result = redact("https://api.x/?tavilyApiKey=secret123 Bearer secret456 auth_token=secret789")
    assert "secret" not in result


def test_twitter_missing_guard_never_uses_stock_executable():
    from agent_reach_plus.transport import cli_argv
    with patch("importlib.util.find_spec", return_value=None):
        with pytest.raises(ReachError, match="guard"):
            cli_argv("twitter")


def test_descendant_does_not_extend_timeout():
    code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)']);time.sleep(10)"
    begin = time.monotonic()
    with patch("agent_reach_plus.transport.cli_argv", return_value=[sys.executable]):
        with pytest.raises(ReachError, match="timeout"):
            asyncio.run(run_cli("test", ["-c", code], timeout=0.4))
    assert time.monotonic() - begin < 3


def test_cancelled_cli_closes_descendants():
    async def run():
        code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)']);time.sleep(10)"
        with patch("agent_reach_plus.transport.cli_argv", return_value=[sys.executable]):
            task = asyncio.create_task(run_cli("test", ["-c", code]))
            await asyncio.sleep(0.4)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    begin = time.monotonic()
    asyncio.run(run())
    assert time.monotonic() - begin < 3


def test_fetch_pins_public_address_and_preserves_host_sni():

    import httpx

    from agent_reach_plus.transport import fetch_bytes

    requested = []
    def respond(request):
        requested.append(request)
        return httpx.Response(200, content=b"public-content")
    real_client = httpx.AsyncClient
    def client(**kwargs):
        kwargs["transport"] = httpx.MockTransport(respond)
        return real_client(**kwargs)
    answers = [(2, 1, 6, "", ("93.184.216.34", 443))]
    with patch("socket.getaddrinfo", return_value=answers), patch("agent_reach_plus.transport.httpx.AsyncClient", side_effect=client):
        assert asyncio.run(fetch_bytes("https://public.example/path")) == b"public-content"
    assert requested[0].url.host == "93.184.216.34"
    assert requested[0].headers["host"] == "public.example"
    assert requested[0].extensions["sni_hostname"] == "public.example"
