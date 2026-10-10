import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from agent_reach_plus.readers import parse_vtt, rss_read, youtube_subtitles
from agent_reach_plus.transport import ReachError


def test_antibot_challenge_not_success():
    from agent_reach_plus.readers import fetch_url
    challenge = b'Title: Just a moment...\nWarning: This page is requiring CAPTCHA\n## Performing security verification'
    with patch("agent_reach_plus.readers.validate_url", new=AsyncMock()), patch("agent_reach_plus.readers.fetch_bytes", new=AsyncMock(return_value=challenge)):
        with pytest.raises(ReachError) as exc:
            asyncio.run(fetch_url("https://example.com"))
    assert exc.value.code == "challenge_required"


def test_subtitle_rollup_preserves_timing_without_duplicate_words():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello\n\n00:00:02.000 --> 00:00:04.000\nHello world\n\n00:00:03.000 --> 00:00:05.000\nworld again\n"
    result = parse_vtt(vtt)
    assert result["text"] == "Hello world again"
    assert result["segments"][0]["start"] == "00:00:01.000"


def test_subtitle_bad_host_never_calls_cli():
    with pytest.raises(ReachError):
        asyncio.run(youtube_subtitles("https://youtube.com.evil.example/watch?v=x"))


def test_rss_parses_fetched_bytes_no_hidden_url_fetch():
    xml = b'<rss version="2.0"><channel><title>News</title><item><title>One</title><link>https://example.com/1</link></item></channel></rss>'
    with patch("agent_reach_plus.readers.fetch_bytes", new=AsyncMock(return_value=xml)):
        result = asyncio.run(rss_read("https://example.com/rss", 5))
    assert result["data"]["entries"][0]["title"] == "One"


def test_youtube_no_subtitles_actionable():
    with patch("agent_reach_plus.readers.run_cli", new=AsyncMock(return_value='{"id":"abcdefghijk","title":"X","subtitles":{},"automatic_captions":{}}')):
        with pytest.raises(ReachError) as e:
            asyncio.run(youtube_subtitles("https://www.youtube.com/watch?v=abcdefghijk"))
    assert e.value.code == "no_subtitles"


@pytest.mark.parametrize("url", ["https://www.youtube.com/playlist?list=PL123", "https://www.youtube.com/@nasa", "https://www.youtube.com/redirect?q=http://127.0.0.1", "https://youtube.com/watch?v=abcdefghijk&v=lmnopqrstuv"])
def test_youtube_requires_one_specific_video(url):
    with patch("agent_reach_plus.readers.run_cli", new=AsyncMock(side_effect=AssertionError("invalid video must never invoke CLI"))):
        with pytest.raises(ReachError) as exc:
            asyncio.run(youtube_subtitles(url))
    assert exc.value.code == "invalid_url"
