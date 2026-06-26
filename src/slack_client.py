"""Slack API wrapper with pagination and error handling.

All public methods raise SlackClientError on API failures.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from src.config import Config

RATE_LIMIT_DELAY_SECONDS: float = 1.0
HISTORY_PAGE_SIZE: int = 200
MAX_HISTORY_PAGES: int = 100
_METADATA_EVENT_TYPE: str = "designated_volunteer_picked"

logger = logging.getLogger(__name__)


class SlackClientError(Exception):
    """Raised when a Slack API call fails or returns an unexpected response."""


class SlackClient:
    def __init__(self, config: Config) -> None:
        self._client = WebClient(token=config.slack_bot_token)
        self._bot_user_id = config.slack_bot_user_id
        self._bot_message_marker = config.bot_message_marker

    def get_bot_messages(self, channel_id: str, lookback_days: int) -> list[dict[str, Any]]:
        oldest = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).timestamp()
        messages: list[dict[str, Any]] = []
        cursor: str | None = None

        try:
            for page in range(MAX_HISTORY_PAGES):
                kwargs: dict[str, Any] = {
                    "channel": channel_id,
                    "limit": HISTORY_PAGE_SIZE,
                    "oldest": str(oldest),
                    "include_all_metadata": True,
                }
                if cursor:
                    kwargs["cursor"] = cursor

                logger.debug("Fetching history page %d for channel %s", page + 1, channel_id)
                response = self._client.conversations_history(**kwargs)

                for msg in response["messages"]:
                    if (
                        msg.get("user") == self._bot_user_id
                        and self._bot_message_marker in msg.get("text", "")
                    ):
                        messages.append(msg)

                next_cursor = response.get("response_metadata", {}).get("next_cursor")
                if not next_cursor:
                    break

                cursor = next_cursor
                time.sleep(RATE_LIMIT_DELAY_SECONDS)

        except SlackApiError as exc:
            raise SlackClientError(f"Failed to fetch channel history: {exc}") from exc

        logger.info("Fetched %d bot messages from channel %s", len(messages), channel_id)
        return messages

    def extract_picked_emails_from_messages(self, messages: list[dict[str, Any]]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for msg in messages:
            email = (
                msg.get("metadata", {})
                .get("event_payload", {})
                .get("picked_email")
            )
            if email and email not in seen:
                seen.add(email)
                result.append(email)
        return result

    def resolve_email_to_slack_user_id(self, email: str) -> str | None:
        try:
            response = self._client.users_lookupByEmail(email=email)
            return response["user"]["id"]
        except SlackApiError as exc:
            if exc.response["error"] == "users_not_found":
                return None
            raise SlackClientError(f"Failed to resolve email {email!r}: {exc}") from exc

    def post_pick_message(self, channel_id: str, slack_user_id: str, picked_email: str) -> None:
        text = f"<@{slack_user_id}> is this week's designated volunteer! {self._bot_message_marker}"
        try:
            self._client.chat_postMessage(
                channel=channel_id,
                text=text,
                metadata={
                    "event_type": _METADATA_EVENT_TYPE,
                    "event_payload": {"picked_email": picked_email},
                },
            )
        except SlackApiError as exc:
            raise SlackClientError(f"Failed to post message to {channel_id!r}: {exc}") from exc

        logger.info("Posted pick message for %s in channel %s", picked_email, channel_id)
