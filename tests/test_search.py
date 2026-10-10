import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from agent_reach_plus.search import code_search, web_search
from agent_reach_plus.transport import ReachError


def test_exa_error_not_presented_as_success():
    payload = '{"isError":true,"content":[{"type":"text","text":"rate limit"}]}'
    with patch("agent_reach_plus.search.run_cli", new=AsyncMock(return_value=payload)):
        with pytest.raises(ReachError) as e:
            asyncio.run(web_search("AI education"))
    assert e.value.code == "search_failed"


def test_auto_does_not_silently_switch_to_metered_provider():
    with patch("agent_reach_plus.search.run_cli", new=AsyncMock(side_effect=ReachError("rate_limited", "limit"))):
        with pytest.raises(ReachError) as e:
            asyncio.run(web_search("AI education", provider="auto"))
    assert e.value.code == "rate_limited"


def test_exa_results_retain_source_links():
    payload = '{"content":[{"type":"text","text":"Title: X\\nURL: https://example.com/x"}]}'
    with patch("agent_reach_plus.search.run_cli", new=AsyncMock(return_value=payload)):
        result = asyncio.run(web_search("AI education"))
    assert result["backend"] == "Exa"
    assert "https://example.com/x" in result["data"]["content"]


def test_empty_code_search_is_not_success():
    with patch("agent_reach_plus.search.run_cli", new=AsyncMock(return_value='{"content":[]}')):
        with pytest.raises(ReachError) as exc:
            asyncio.run(code_search("example"))
    assert exc.value.code == "empty_response"


def test_provider_rate_limit_text_not_success():
    payload = '{"content":[{"type":"text","text":"You have hit the free MCP rate limit. Please retry later."}]}'
    with patch("agent_reach_plus.search.run_cli", new=AsyncMock(return_value=payload)):
        with pytest.raises(ReachError) as exc:
            asyncio.run(web_search("AI education"))
    assert exc.value.code == "rate_limited"
