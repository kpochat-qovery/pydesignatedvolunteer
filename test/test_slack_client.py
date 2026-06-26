"""Tests for slack_client.py."""

import time as time_module
from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from src.config import Config
from src.slack_client import SlackClient, SlackClientError


@pytest.fixture
def config() -> Config:
    return Config(
        slack_bot_token="xoxb-test",
        slack_channel_id="C123",
        slack_bot_user_id="UBOT123",
        google_workspace_group_email="group@example.com",
        google_service_account_key_content='{"type": "service_account"}',
        google_workspace_admin_email="admin@example.com",
        bot_message_marker="picked-by-bot",
    )


@pytest.fixture
def mock_web_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(config: Config, mock_web_client: MagicMock) -> SlackClient:
    with patch("src.slack_client.WebClient", return_value=mock_web_client):
        return SlackClient(config)


def _slack_error(error_code: str) -> SlackApiError:
    return SlackApiError(error_code, {"ok": False, "error": error_code})


def _bot_msg(ts: str = "1000.000", email: str = "a@example.com") -> dict:
    return {
        "user": "UBOT123",
        "text": "Congrats! picked-by-bot",
        "ts": ts,
        "metadata": {
            "event_type": "designated_volunteer_picked",
            "event_payload": {"picked_email": email},
        },
    }


def test_get_bot_messages_returns_only_bot_messages(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    bot_msg = _bot_msg()
    other_user_msg = {"user": "UOTHER", "text": "Hello picked-by-bot", "ts": "2000.000"}
    no_marker_msg = {"user": "UBOT123", "text": "No marker here", "ts": "3000.000"}

    mock_web_client.conversations_history.return_value = {
        "messages": [bot_msg, other_user_msg, no_marker_msg],
        "response_metadata": {"next_cursor": ""},
    }

    result = client.get_bot_messages("C123", 30)

    assert result == [bot_msg]


def test_get_bot_messages_paginates(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    page1_msg = _bot_msg(ts="1000.000", email="a@example.com")
    page2_msg = _bot_msg(ts="2000.000", email="b@example.com")

    mock_web_client.conversations_history.side_effect = [
        {"messages": [page1_msg], "response_metadata": {"next_cursor": "cursor-abc"}},
        {"messages": [page2_msg], "response_metadata": {"next_cursor": ""}},
    ]

    with patch("src.slack_client.time.sleep"):
        result = client.get_bot_messages("C123", 30)

    assert len(result) == 2
    assert mock_web_client.conversations_history.call_count == 2
    second_call_kwargs = mock_web_client.conversations_history.call_args_list[1].kwargs
    assert second_call_kwargs["cursor"] == "cursor-abc"


def test_get_bot_messages_respects_lookback_window(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    mock_web_client.conversations_history.return_value = {
        "messages": [],
        "response_metadata": {"next_cursor": ""},
    }

    before = time_module.time()
    client.get_bot_messages("C123", 7)

    call_kwargs = mock_web_client.conversations_history.call_args.kwargs
    oldest = float(call_kwargs["oldest"])
    expected_oldest = before - 7 * 86400
    assert abs(oldest - expected_oldest) < 5


def test_get_bot_messages_raises_on_api_error(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    mock_web_client.conversations_history.side_effect = _slack_error("channel_not_found")

    with pytest.raises(SlackClientError, match="channel_not_found"):
        client.get_bot_messages("CBAD", 30)


def test_extract_picked_emails_from_messages_deduplicates(client: SlackClient) -> None:
    messages = [
        {"metadata": {"event_payload": {"picked_email": "a@example.com"}}},
        {"metadata": {"event_payload": {"picked_email": "b@example.com"}}},
        {"metadata": {"event_payload": {"picked_email": "a@example.com"}}},
        {"metadata": {"event_payload": {}}},
        {"metadata": {}},
        {},
    ]

    result = client.extract_picked_emails_from_messages(messages)

    assert result == ["a@example.com", "b@example.com"]


def test_resolve_email_to_user_id_success(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    mock_web_client.users_lookupByEmail.return_value = {"user": {"id": "U999ABC"}}

    result = client.resolve_email_to_slack_user_id("user@example.com")

    assert result == "U999ABC"
    mock_web_client.users_lookupByEmail.assert_called_once_with(email="user@example.com")


def test_resolve_email_to_user_id_not_found(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    mock_web_client.users_lookupByEmail.side_effect = _slack_error("users_not_found")

    result = client.resolve_email_to_slack_user_id("ghost@example.com")

    assert result is None


def test_resolve_email_to_user_id_api_error(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    mock_web_client.users_lookupByEmail.side_effect = _slack_error("ratelimited")

    with pytest.raises(SlackClientError, match="ratelimited"):
        client.resolve_email_to_slack_user_id("user@example.com")


def test_post_memory_message_embeds_metadata(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    client.post_memory_message("C123", "volunteer@example.com")

    mock_web_client.chat_postMessage.assert_called_once()
    kwargs = mock_web_client.chat_postMessage.call_args.kwargs
    assert kwargs["channel"] == "C123"
    assert "picked-by-bot" in kwargs["text"]
    assert kwargs["metadata"]["event_type"] == "designated_volunteer_picked"
    assert kwargs["metadata"]["event_payload"]["picked_email"] == "volunteer@example.com"


def test_post_memory_message_raises_on_api_error(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    mock_web_client.chat_postMessage.side_effect = _slack_error("not_in_channel")

    with pytest.raises(SlackClientError, match="not_in_channel"):
        client.post_memory_message("C123", "user@example.com")


def test_post_announcement_mentions_user(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    client.post_announcement("C999", "U456")

    mock_web_client.chat_postMessage.assert_called_once()
    kwargs = mock_web_client.chat_postMessage.call_args.kwargs
    assert kwargs["channel"] == "C999"
    assert "<@U456>" in kwargs["text"]
    assert "metadata" not in kwargs


def test_post_announcement_raises_on_api_error(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    mock_web_client.chat_postMessage.side_effect = _slack_error("not_in_channel")

    with pytest.raises(SlackClientError, match="not_in_channel"):
        client.post_announcement("C999", "U456")


def _channels_page(channels: list[dict], next_cursor: str = "") -> dict:
    return {
        "channels": channels,
        "response_metadata": {"next_cursor": next_cursor},
    }


def test_resolve_channel_name_to_id_success(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    mock_web_client.conversations_list.return_value = _channels_page(
        [{"id": "C999", "name": "general"}, {"id": "C111", "name": "random"}]
    )

    result = client.resolve_channel_name_to_id("general")

    assert result == "C999"


def test_resolve_channel_name_to_id_strips_hash(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    mock_web_client.conversations_list.return_value = _channels_page(
        [{"id": "C999", "name": "general"}]
    )

    result = client.resolve_channel_name_to_id("#general")

    assert result == "C999"


def test_resolve_channel_name_to_id_paginates(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    mock_web_client.conversations_list.side_effect = [
        _channels_page([{"id": "C111", "name": "random"}], next_cursor="cursor-xyz"),
        _channels_page([{"id": "C999", "name": "general"}]),
    ]

    with patch("src.slack_client.time.sleep"):
        result = client.resolve_channel_name_to_id("general")

    assert result == "C999"
    assert mock_web_client.conversations_list.call_count == 2
    second_call_kwargs = mock_web_client.conversations_list.call_args_list[1].kwargs
    assert second_call_kwargs["cursor"] == "cursor-xyz"


def test_resolve_channel_name_to_id_not_found(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    mock_web_client.conversations_list.return_value = _channels_page(
        [{"id": "C111", "name": "random"}]
    )

    with pytest.raises(SlackClientError, match="not found"):
        client.resolve_channel_name_to_id("nonexistent")


def test_resolve_channel_name_to_id_raises_on_api_error(
    client: SlackClient, mock_web_client: MagicMock
) -> None:
    mock_web_client.conversations_list.side_effect = _slack_error("not_authed")

    with pytest.raises(SlackClientError, match="not_authed"):
        client.resolve_channel_name_to_id("general")
