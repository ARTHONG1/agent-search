"""Offline contract tests for the read-only social adapters."""

import asyncio
import importlib
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def adapter(monkeypatch):
    try:
        social = importlib.import_module("agent_reach_plus.social")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Social adapters are not implemented: {exc}")
    monkeypatch.setattr(social, "has_cli", Mock(return_value=False))
    monkeypatch.setattr(social, "run_cli", AsyncMock(return_value="[]"))
    monkeypatch.setattr(social, "opencli_status", Mock(return_value=SimpleNamespace(ready=False)))
    monkeypatch.setattr(social, "Config", Mock(return_value=SimpleNamespace(get=lambda key: None)))
    return social


def run(coro):
    return asyncio.run(coro)


def install(adapter, *names):
    adapter.has_cli.side_effect = lambda name: name in names


def test_github_search_returns_structured_repos(adapter):
    install(adapter, "gh")
    adapter.run_cli.return_value = '[{"fullName":"owner/repo","url":"https://github.com/owner/repo"}]'
    result = run(adapter.social_search("python", ["github"], 2))
    assert result["errors"] == []
    assert result["results"][0]["platform"] == "github"
    assert result["results"][0]["backend"] == "gh"
    assert result["results"][0]["data"][0]["fullName"] == "owner/repo"
    name, args = adapter.run_cli.call_args.args
    assert name == "gh"
    assert args[:3] == ["search", "repos", "python"]
    assert args[args.index("--limit") + 1] == "2"
    assert {"fullName", "url", "description", "stargazersCount"} <= set(args[args.index("--json") + 1].split(","))


def test_partial_platform_failure_preserves_success(adapter):
    install(adapter, "gh", "yt-dlp")

    async def cli(name, args, **kwargs):
        if name == "gh":
            return '[{"fullName":"owner/repo"}]'
        raise adapter.ReachError("timeout", "Search timed out")

    adapter.run_cli.side_effect = cli
    result = run(adapter.social_search("python", ["github", "youtube"]))
    assert [row["platform"] for row in result["results"]] == ["github"]
    assert result["errors"] == [{"platform": "youtube", "code": "timeout", "message": "Search timed out"}]


def test_youtube_uses_fixed_safe_flags_and_bounds_entries(adapter):
    install(adapter, "yt-dlp")
    adapter.run_cli.return_value = '{"entries":[{"id":"one"},{"id":"two"},{"id":"three"}]}'
    result = run(adapter.social_search('cats; --exec "echo bad"', ["youtube"], 2))
    assert result["results"][0]["data"]["entries"] == [{"id": "one"}, {"id": "two"}]
    adapter.run_cli.assert_awaited_once_with(
        "yt-dlp", ["--ignore-config", "--flat-playlist", "--dump-single-json", 'ytsearch2:cats; --exec "echo bad"']
    )


@pytest.mark.parametrize("query", ["", "   ", "-x", "\nfoo", "foo\x00bar", "x" * 1001, None])
def test_invalid_search_query_never_calls_external_backend(adapter, query):
    with pytest.raises(adapter.ReachError):
        run(adapter.social_search(query, ["github"]))
    adapter.run_cli.assert_not_awaited()
    adapter.has_cli.assert_not_called()
    adapter.opencli_status.assert_not_called()
    adapter.Config.assert_not_called()


@pytest.mark.parametrize("limit", [0, -1, 21, True, "5", 2.5])
def test_invalid_limit_never_calls_external_backend(adapter, limit):
    with pytest.raises(adapter.ReachError):
        run(adapter.social_search("python", ["github"], limit))
    adapter.run_cli.assert_not_awaited()
    adapter.has_cli.assert_not_called()


@pytest.mark.parametrize("platforms", [[], ["unknown"], ["github"] * 6, "github", [None], ["github", "github"], ["github", "unknown"]])
def test_invalid_platform_list_is_rejected_before_external_calls(adapter, platforms):
    with pytest.raises(adapter.ReachError):
        run(adapter.social_search("python", platforms))
    adapter.run_cli.assert_not_awaited()
    adapter.has_cli.assert_not_called()


def test_bilibili_search_uses_bili_and_preserves_text(adapter):
    install(adapter, "bili")
    adapter.run_cli.return_value = "BV1xx411c7mD: Python tutorial"
    result = run(adapter.social_search("python", ["bilibili"], 3))
    assert result["results"][0]["backend"] == "bili"
    assert result["results"][0]["data"] == "BV1xx411c7mD: Python tutorial"
    adapter.run_cli.assert_awaited_once_with("bili", ["search", "python", "--type", "video", "-n", "3", "--json"])


def test_twitter_requires_complete_explicit_credentials(adapter, monkeypatch):
    install(adapter, "twitter", "opencli")
    monkeypatch.setenv("TWITTER_AUTH_TOKEN", "inherited-must-not-be-used-directly")
    adapter.Config.return_value = SimpleNamespace(get=lambda key: "auth-only" if key == "twitter_auth_token" else None)
    result = run(adapter.social_search("python", ["twitter"]))
    assert result["results"] == []
    assert result["errors"][0]["code"] == "setup_required"
    adapter.run_cli.assert_not_awaited()
    adapter.Config.assert_called_once_with(read_only=True)


def test_twitter_credentials_only_change_child_env(adapter):
    install(adapter, "twitter")
    adapter.run_cli.twitter_env_only = True
    credentials = {"twitter_auth_token": "explicit-auth", "twitter_ct0": "explicit-csrf"}
    adapter.Config.return_value = SimpleNamespace(get=credentials.get)
    before = dict(os.environ)
    result = run(adapter.social_search("python", ["twitter"], 3))
    assert result["results"][0]["backend"] == "twitter"
    adapter.run_cli.assert_awaited_once_with(
        "twitter", ["search", "python", "-n", "3", "--json"],
        env={"TWITTER_AUTH_TOKEN": "explicit-auth", "TWITTER_CT0": "explicit-csrf"},
    )
    assert dict(os.environ) == before
    assert "explicit-auth" not in json.dumps(result)
    adapter.opencli_status.assert_not_called()


def test_twitter_without_credentials_uses_connected_opencli(adapter):
    install(adapter, "twitter", "opencli")
    adapter.opencli_status.return_value = SimpleNamespace(ready=True)
    result = run(adapter.social_search("python", ["twitter"]))
    assert result["results"][0]["backend"] == "opencli"
    adapter.run_cli.assert_awaited_once_with("opencli", ["twitter", "search", "python", "--limit", "5", "-f", "json"])


def test_twitter_cli_failure_can_use_connected_opencli(adapter):
    install(adapter, "twitter", "opencli")
    adapter.run_cli.twitter_env_only = True
    adapter.Config.return_value = SimpleNamespace(get={"twitter_auth_token": "secret", "twitter_ct0": "csrf"}.get)
    adapter.opencli_status.return_value = SimpleNamespace(ready=True)
    adapter.run_cli.side_effect = [adapter.ReachError("cli_failed", "unavailable"), "[]"]
    result = run(adapter.social_search("python", ["twitter"]))
    assert result["errors"] == []
    assert result["results"][0]["backend"] == "opencli"


@pytest.mark.parametrize("platform", ["reddit", "xiaohongshu", "facebook", "instagram"])
def test_opencli_search_requires_live_extension(adapter, platform):
    install(adapter, "opencli")
    adapter.opencli_status.return_value = SimpleNamespace(ready=False, installed=True, extension_installed=True)
    result = run(adapter.social_search("python", [platform]))
    assert result["results"] == []
    assert result["errors"][0]["code"] == "setup_required"
    adapter.run_cli.assert_not_awaited()


@pytest.mark.parametrize("platform", ["reddit", "xiaohongshu", "facebook", "instagram"])
def test_connected_opencli_search_outputs_json_and_bounds_results(adapter, platform):
    install(adapter, "opencli")
    adapter.opencli_status.return_value = SimpleNamespace(ready=True)
    adapter.run_cli.return_value = '[{"id":1},{"id":2},{"id":3}]'
    result = run(adapter.social_search("python", [platform], 2))
    assert result["results"][0]["data"] == [{"id": 1}, {"id": 2}]
    adapter.run_cli.assert_awaited_once_with("opencli", [platform, "search", "python", "--limit", "2", "-f", "json"])


def test_reddit_falls_back_to_installed_rdt(adapter):
    install(adapter, "opencli", "rdt")
    result = run(adapter.social_search("python", ["reddit"], 4))
    assert result["results"][0]["backend"] == "rdt"
    adapter.run_cli.assert_awaited_once_with("rdt", ["search", "python", "--limit", "4"])


def test_reddit_opencli_failure_falls_back_to_rdt(adapter):
    install(adapter, "opencli", "rdt")
    adapter.opencli_status.return_value = SimpleNamespace(ready=True)
    adapter.run_cli.side_effect = [adapter.ReachError("cli_failed", "not logged in"), '[{"id":"abc123"}]']
    result = run(adapter.social_search("python", ["reddit"]))
    assert result["errors"] == []
    assert result["results"][0]["backend"] == "rdt"


def test_malformed_structured_output_is_partial_error(adapter):
    install(adapter, "gh", "bili")
    adapter.run_cli.side_effect = ["not JSON", "a video"]
    result = run(adapter.social_search("python", ["github", "bilibili"]))
    assert [row["platform"] for row in result["results"]] == ["bilibili"]
    assert result["errors"][0]["code"] == "invalid_response"


def test_probe_failure_fails_closed(adapter):
    install(adapter, "opencli")
    adapter.opencli_status.side_effect = OSError("daemon unavailable")
    result = run(adapter.social_search("python", ["facebook"]))
    assert result["errors"][0]["code"] == "setup_required"
    adapter.run_cli.assert_not_awaited()


def test_github_read_uses_validated_repo_endpoint(adapter):
    install(adapter, "gh")
    adapter.run_cli.return_value = '{"full_name":"owner/repo","private":false}'
    result = run(adapter.social_read("github", "owner/repo"))
    assert result == {"platform": "github", "backend": "gh", "data": {"full_name": "owner/repo", "private": False}}
    adapter.run_cli.assert_awaited_once_with("gh", ["api", "repos/owner/repo", "--method", "GET"])


def test_github_private_repo_is_not_returned(adapter):
    install(adapter, "gh")
    adapter.run_cli.return_value = '{"full_name":"owner/private","private":true}'
    with pytest.raises(adapter.ReachError) as error:
        run(adapter.social_read("github", "owner/private"))
    assert error.value.code == "invalid_target"


def test_twitter_read_uses_tweet_command(adapter):
    install(adapter, "twitter")
    adapter.run_cli.twitter_env_only = True
    adapter.Config.return_value = SimpleNamespace(get={"twitter_auth_token": "auth", "twitter_ct0": "csrf"}.get)
    result = run(adapter.social_read("twitter", "https://x.com/someone/status/123456789"))
    assert result["backend"] == "twitter"
    assert adapter.run_cli.call_args.args == ("twitter", ["tweet", "https://x.com/someone/status/123456789", "--json"])


def test_configured_twitter_cli_without_env_only_guard_is_never_started(adapter):
    install(adapter, "twitter")
    adapter.Config.return_value = SimpleNamespace(get={"twitter_auth_token": "explicit-auth", "twitter_ct0": "explicit-csrf"}.get)
    result = run(adapter.social_search("python", ["twitter"]))
    assert result["results"] == []
    assert result["errors"][0]["code"] == "setup_required"
    adapter.run_cli.assert_not_awaited()


def test_unguarded_twitter_read_cannot_trigger_auth_failure_cookie_fallback(adapter):
    install(adapter, "twitter")
    adapter.Config.return_value = SimpleNamespace(get={"twitter_auth_token": "explicit-auth", "twitter_ct0": "explicit-csrf"}.get)
    with pytest.raises(adapter.ReachError) as error:
        run(adapter.social_read("twitter", "https://x.com/someone/status/123456789"))
    assert error.value.code == "setup_required"
    adapter.run_cli.assert_not_awaited()


def test_configured_unguarded_twitter_prefers_connected_opencli(adapter):
    install(adapter, "twitter", "opencli")
    adapter.Config.return_value = SimpleNamespace(get={"twitter_auth_token": "explicit-auth", "twitter_ct0": "explicit-csrf"}.get)
    adapter.opencli_status.return_value = SimpleNamespace(ready=True)
    result = run(adapter.social_search("python", ["twitter"]))
    assert result["results"][0]["backend"] == "opencli"
    assert [call.args[0] for call in adapter.run_cli.await_args_list] == ["opencli"]


def test_twitter_read_opencli_uses_upstream_thread_command(adapter):
    install(adapter, "opencli")
    adapter.opencli_status.return_value = SimpleNamespace(ready=True)
    result = run(adapter.social_read("twitter", "https://twitter.com/someone/status/123456789"))
    assert result["backend"] == "opencli"
    adapter.run_cli.assert_awaited_once_with("opencli", ["twitter", "thread", "https://twitter.com/someone/status/123456789", "-f", "json"])


@pytest.mark.parametrize("target", ["abc123", "t3_abc123", "https://www.reddit.com/r/python/comments/abc123/title/", "https://redd.it/abc123"])
def test_reddit_read_normalizes_id_or_url(adapter, target):
    install(adapter, "rdt")
    result = run(adapter.social_read("reddit", target))
    assert result["backend"] == "rdt"
    adapter.run_cli.assert_awaited_once_with("rdt", ["read", "abc123"])


def test_reddit_read_opencli(adapter):
    install(adapter, "opencli")
    adapter.opencli_status.return_value = SimpleNamespace(ready=True)
    result = run(adapter.social_read("reddit", "abc123"))
    assert result["backend"] == "opencli"
    adapter.run_cli.assert_awaited_once_with("opencli", ["reddit", "read", "abc123", "-f", "json"])


def test_bilibili_read_uses_video_command(adapter):
    install(adapter, "bili")
    result = run(adapter.social_read("bilibili", "BV1xx411c7mD"))
    assert result["backend"] == "bili"
    adapter.run_cli.assert_awaited_once_with("bili", ["video", "BV1xx411c7mD", "--json"])


def test_bilibili_read_falls_back_to_ready_opencli(adapter):
    install(adapter, "opencli")
    adapter.opencli_status.return_value = SimpleNamespace(ready=True)
    result = run(adapter.social_read("bilibili", "BV1xx411c7mD"))
    assert result["backend"] == "opencli"
    adapter.run_cli.assert_awaited_once_with("opencli", ["bilibili", "video", "BV1xx411c7mD", "-f", "json"])


def test_xiaohongshu_read_keeps_complete_signed_url(adapter):
    install(adapter, "opencli")
    adapter.opencli_status.return_value = SimpleNamespace(ready=True)
    target = "https://www.xiaohongshu.com/explore/abcdef0123456789abcdef01?xsec_token=abc%2Bdef&xsec_source=pc_search"
    result = run(adapter.social_read("xiaohongshu", target))
    assert result["backend"] == "opencli"
    adapter.run_cli.assert_awaited_once_with("opencli", ["xiaohongshu", "note", target, "-f", "json"])


@pytest.mark.parametrize("platform,target", [
    ("github", "--help"), ("github", "owner/repo/extra"), ("github", "../repo"),
    ("github", "https://github.com/owner/repo"), ("github", "owner/.."),
    ("twitter", "https://evil.test/user/status/123"), ("twitter", "https://x.com.evil.test/user/status/123"),
    ("twitter", "https://x.com@evil.test/user/status/123"), ("twitter", "file:///user/status/123"),
    ("twitter", "https://x.com/user/status/not-a-number"), ("twitter", "--help"),
    ("reddit", "https://evil.test/comments/abc123"), ("reddit", "--help"),
    ("reddit", "https://www.reddit.com/r/python"), ("reddit", "https://www.reddit.com:444/r/python/comments/abc123/"),
    ("bilibili", "BV123"), ("bilibili", "--help"),
    ("xiaohongshu", "abcdef0123456789abcdef01"),
    ("xiaohongshu", "https://www.xiaohongshu.com/explore/abcdef0123456789abcdef01"),
    ("xiaohongshu", "https://www.xiaohongshu.com/explore/abcdef0123456789abcdef01?xsec_token="),
    ("xiaohongshu", "https://evil.test/explore/abcdef0123456789abcdef01?xsec_token=abc"),
    ("xiaohongshu", "https://www.xiaohongshu.com/explore/abcdef0123456789abcdef01?xsec_token=abc&xsec_token="),
    ("facebook", "zuck"), ("instagram", "nasa"), ("youtube", "https://youtu.be/abc"),
    ("unknown", "target"), ("github", None), ("github", "owner/repo\n"),
])
def test_invalid_read_targets_never_call_external_backend(adapter, platform, target):
    with pytest.raises(adapter.ReachError):
        run(adapter.social_read(platform, target))
    adapter.run_cli.assert_not_awaited()
    adapter.has_cli.assert_not_called()
    adapter.opencli_status.assert_not_called()
    adapter.Config.assert_not_called()


def test_read_setup_required_is_structured_exception(adapter):
    with pytest.raises(adapter.ReachError) as error:
        run(adapter.social_read("xiaohongshu", "https://www.xiaohongshu.com/explore/abcdef0123456789abcdef01?xsec_token=abc"))
    assert error.value.code == "setup_required"
    adapter.run_cli.assert_not_awaited()


def test_unexpected_backend_failure_does_not_abort_other_platforms(adapter):
    install(adapter, "gh", "bili")
    adapter.run_cli.side_effect = [OSError("private implementation detail"), "a video"]
    result = run(adapter.social_search("python", ["github", "bilibili"]))
    assert result["results"][0]["platform"] == "bilibili"
    assert result["errors"][0]["code"] == "backend_error"
    assert "private implementation detail" not in json.dumps(result)


def test_platform_searches_start_concurrently_and_keep_request_order(adapter):
    install(adapter, "gh", "bili")

    async def exercise():
        started = set()
        both_started = asyncio.Event()

        async def cli(name, args, **kwargs):
            started.add(name)
            if len(started) == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), 0.25)
            return '[{"id":"one"}]'

        adapter.run_cli.side_effect = cli
        return await adapter.social_search("python", ["github", "bilibili"])

    result = run(exercise())
    assert result["errors"] == []
    assert [row["platform"] for row in result["results"]] == ["github", "bilibili"]


def test_search_limit_keeps_nested_comments_and_metadata(adapter):
    install(adapter, "opencli")
    adapter.opencli_status.return_value = SimpleNamespace(ready=True)
    adapter.run_cli.return_value = '{"results":[{"id":1,"comments":[1,2,3]},{"id":2}],"metadata":{"pages":[1,2,3]}}'
    result = run(adapter.social_search("python", ["reddit"], 1))
    assert result["results"][0]["data"] == {"results": [{"id": 1, "comments": [1, 2, 3]}], "metadata": {"pages": [1, 2, 3]}}


@pytest.mark.parametrize("platform", ["bilibili", "facebook"])
def test_exit_zero_failure_envelope_is_a_platform_error(adapter, platform):
    install(adapter, "bili", "opencli")
    adapter.opencli_status.return_value = SimpleNamespace(ready=True)
    adapter.run_cli.return_value = '{"ok":false,"error":{"code":"auth_required","message":"token=secret"}}'
    result = run(adapter.social_search("python", [platform]))
    assert result["results"] == []
    assert result["errors"][0]["code"] == "auth_required"
    assert "secret" not in json.dumps(result)


def test_read_failure_envelope_raises(adapter):
    install(adapter, "bili")
    adapter.run_cli.return_value = '{"ok":false,"error":"not found"}'
    with pytest.raises(adapter.ReachError) as error:
        run(adapter.social_read("bilibili", "BV1xx411c7mD"))
    assert error.value.code == "backend_error"
