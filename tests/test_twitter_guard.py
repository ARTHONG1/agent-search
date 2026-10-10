from unittest.mock import patch

import pytest

from agent_reach_plus.twitter_guard import environment_cookies


def test_incomplete_twitter_env_never_extracts_browser():
    from twitter_cli.exceptions import AuthenticationError
    with patch.dict("os.environ", {"TWITTER_AUTH_TOKEN": "one"}, clear=True):
        with pytest.raises(AuthenticationError):
            environment_cookies()


def test_expired_credentials_fail_without_browser_fallback():
    from twitter_cli.exceptions import AuthenticationError
    with patch.dict("os.environ", {"TWITTER_AUTH_TOKEN": "one", "TWITTER_CT0": "two"}, clear=True), patch("twitter_cli.auth.verify_cookies", side_effect=AuthenticationError("expired")), patch("twitter_cli.auth.extract_from_browser", side_effect=AssertionError("must not extract")):
        with pytest.raises(AuthenticationError, match="expired"):
            environment_cookies()


def test_valid_explicit_credentials_forwarded():
    with patch.dict("os.environ", {"TWITTER_AUTH_TOKEN": "one", "TWITTER_CT0": "two"}, clear=True), patch("twitter_cli.auth.verify_cookies"):
        assert environment_cookies() == {"auth_token": "one", "ct0": "two"}
