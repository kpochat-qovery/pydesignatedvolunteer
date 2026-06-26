"""Tests for config.py."""

import json
import pytest

from src.config import (
    Config,
    ConfigurationError,
    DEFAULT_BOT_MESSAGE_MARKER,
    DEFAULT_HISTORY_LOOKBACK_DAYS,
    load_config,
)

_FAKE_KEY_CONTENT = json.dumps({"type": "service_account", "project_id": "test"})

_FULL_ENV = {
    "SLACK_BOT_TOKEN": "xoxb-test-token",
    "SLACK_CHANNEL_ID": "C12345678",
    "SLACK_BOT_USER_ID": "U12345678",
    "GOOGLE_WORKSPACE_GROUP_EMAIL": "group@example.com",
    "GOOGLE_SERVICE_ACCOUNT_KEY": _FAKE_KEY_CONTENT,
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
    assert config.google_service_account_key_content == _FAKE_KEY_CONTENT
    assert config.google_workspace_admin_email == "admin@example.com"


@pytest.mark.parametrize("missing_var", [
    "SLACK_BOT_TOKEN",
    "SLACK_CHANNEL_ID",
    "SLACK_BOT_USER_ID",
    "GOOGLE_WORKSPACE_GROUP_EMAIL",
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


def test_load_config_missing_both_google_key_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _FULL_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_KEY")

    with pytest.raises(ConfigurationError, match="GOOGLE_SERVICE_ACCOUNT_KEY"):
        load_config()


def test_load_config_key_file_reads_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory
) -> None:
    key_file = tmp_path / "key.json"
    key_file.write_text(_FAKE_KEY_CONTENT)

    for key, value in _FULL_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_KEY")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_KEY_FILE", str(key_file))

    config = load_config()

    assert config.google_service_account_key_content == _FAKE_KEY_CONTENT


def test_load_config_inline_key_takes_precedence_over_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory
) -> None:
    key_file = tmp_path / "key.json"
    key_file.write_text('{"type": "service_account", "project_id": "from-file"}')

    for key, value in _FULL_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_KEY_FILE", str(key_file))

    config = load_config()

    assert config.google_service_account_key_content == _FAKE_KEY_CONTENT


def test_load_config_both_set_logs_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory, caplog: pytest.LogCaptureFixture
) -> None:
    key_file = tmp_path / "key.json"
    key_file.write_text("{}")

    for key, value in _FULL_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_KEY_FILE", str(key_file))

    import logging
    with caplog.at_level(logging.WARNING, logger="src.config"):
        load_config()

    assert "GOOGLE_SERVICE_ACCOUNT_KEY_FILE will not be used" in caplog.text


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
