"""Tests for config.py."""

import pytest

from src.config import (
    Config,
    ConfigurationError,
    DEFAULT_BOT_MESSAGE_MARKER,
    DEFAULT_HISTORY_LOOKBACK_DAYS,
    load_config,
)

_FULL_ENV = {
    "SLACK_BOT_TOKEN": "xoxb-test-token",
    "SLACK_CHANNEL_ID": "C12345678",
    "SLACK_BOT_USER_ID": "U12345678",
    "GOOGLE_WORKSPACE_GROUP_EMAIL": "group@example.com",
    "GOOGLE_SERVICE_ACCOUNT_KEY_FILE": "/path/to/key.json",
    "GOOGLE_WORKSPACE_ADMIN_EMAIL": "admin@example.com",
}


def test_load_config_success(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _FULL_ENV.items():
        monkeypatch.setenv(key, value)

    config = load_config()

    assert isinstance(config, Config)
    assert config.slack_bot_token == "xoxb-test-token"
    assert config.slack_channel_id == "C12345678"
    assert config.slack_bot_user_id == "U12345678"
    assert config.google_workspace_group_email == "group@example.com"
    assert config.google_service_account_key_file == "/path/to/key.json"
    assert config.google_workspace_admin_email == "admin@example.com"


@pytest.mark.parametrize("missing_var", [
    "SLACK_BOT_TOKEN",
    "SLACK_CHANNEL_ID",
    "SLACK_BOT_USER_ID",
    "GOOGLE_WORKSPACE_GROUP_EMAIL",
    "GOOGLE_SERVICE_ACCOUNT_KEY_FILE",
    "GOOGLE_WORKSPACE_ADMIN_EMAIL",
])
def test_load_config_missing_required_var(
    monkeypatch: pytest.MonkeyPatch, missing_var: str
) -> None:
    for key, value in _FULL_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv(missing_var)

    with pytest.raises(ConfigurationError, match=missing_var):
        load_config()


@pytest.mark.parametrize("bad_value", ["0", "-1", "abc", "1.5", ""])
def test_load_config_invalid_lookback_days(
    monkeypatch: pytest.MonkeyPatch, bad_value: str
) -> None:
    for key, value in _FULL_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("HISTORY_LOOKBACK_DAYS", bad_value)

    with pytest.raises(ConfigurationError, match="HISTORY_LOOKBACK_DAYS"):
        load_config()


def test_load_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _FULL_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("HISTORY_LOOKBACK_DAYS", raising=False)
    monkeypatch.delenv("BOT_MESSAGE_MARKER", raising=False)

    config = load_config()

    assert config.history_lookback_days == DEFAULT_HISTORY_LOOKBACK_DAYS
    assert config.bot_message_marker == DEFAULT_BOT_MESSAGE_MARKER


def test_load_config_custom_optional_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _FULL_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("HISTORY_LOOKBACK_DAYS", "30")
    monkeypatch.setenv("BOT_MESSAGE_MARKER", "custom-marker")

    config = load_config()

    assert config.history_lookback_days == 30
    assert config.bot_message_marker == "custom-marker"
