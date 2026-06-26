"""Slack API wrapper with pagination and error handling.

All public methods raise SlackClientError on API failures.
"""

import logging
import time
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config import Config

RATE_LIMIT_DELAY_SECONDS: float = 1.0
HISTORY_PAGE_SIZE: int = 200
MAX_HISTORY_PAGES: int = 100
CHANNELS_PAGE_SIZE: int = 200
MAX_CHANNELS_PAGES: int = 50
_METADATA_EVENT_TYPE: str = "designated_volunteer_picked"

logger = logging.getLogger(__name__)


class SlackClientError(Exception):
    """Raised when a Slack API call fails or returns an unexpected response."""


class SlackClient:
    def __init__(self, config: Config) -> None:
        self._client = WebClient(token=config.slack_bot_token)
        auth_test = self._client.auth_test()
        self._bot_user_id = auth_test["user_id"]
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
            if msg.get("metadata", {}).get("event_payload", {}).get("list_history_reset"):
                logger.info(f"Message with list reset flag found. Current list of emails seen is {seen}")
                break
        return result

    def resolve_channel_name_to_id(self, channel_name: str) -> str:
        name = channel_name.lstrip("#")
        cursor: str | None = None
        try:
            for _ in range(MAX_CHANNELS_PAGES):
                kwargs: dict[str, Any] = {
                    "limit": CHANNELS_PAGE_SIZE,
                    "exclude_archived": True,
                }
                if cursor:
                    kwargs["cursor"] = cursor

                response = self._client.conversations_list(**kwargs)

                for channel in response["channels"]:
                    if channel["name"] == name:
                        logger.info("Resolved channel name %r to ID %s", channel_name, channel["id"])
                        return channel["id"]

                next_cursor = response.get("response_metadata", {}).get("next_cursor")
                if not next_cursor:
                    break

                cursor = next_cursor
                time.sleep(RATE_LIMIT_DELAY_SECONDS)

        except SlackApiError as exc:
            raise SlackClientError(f"Failed to list channels: {exc}") from exc

        raise SlackClientError(f"Channel {channel_name!r} not found")

    def resolve_email_to_slack_user_id(self, email: str) -> str | None:
        try:
            response = self._client.users_lookupByEmail(email=email)
            return response["user"]["id"]
        except SlackApiError as exc:
            if exc.response["error"] == "users_not_found":
                return None
            raise SlackClientError(f"Failed to resolve email {email!r}: {exc}") from exc

    def post_memory_message(self, channel_id: str, picked_email: str, slack_user_id: str, list_reset: bool) -> None:
        text = f"Volunteer record {self._bot_message_marker}: <@{slack_user_id}>"
        if list_reset:
            event_payload = {"picked_email": picked_email, "list_history_reset": True}
        else:
            event_payload = {"picked_email": picked_email}
        try:
            self._client.chat_postMessage(
                channel=channel_id,
                text=text,
                metadata={
                    "event_type": _METADATA_EVENT_TYPE,
                    "event_payload": event_payload,
                },
            )
        except SlackApiError as exc:
            raise SlackClientError(f"Failed to post memory message to {channel_id!r}: {exc}") from exc

        logger.info("Posted memory message for %s in channel %s", picked_email, channel_id)

    def post_announcement(self, channel_id: str, slack_user_id: str) -> None:
        text = random.choice([
    f"🎉 Congratulations, <@{slack_user_id}>! The algorithm has selected you as this month's Gathering Architect™. Your reward? The deep satisfaction of finding a coworking space that somehow pleases everyone. You've got this. Probably.",
    f"📣 Attention team: the random picker has spoken, and it has spoken loudly in the direction of <@{slack_user_id}>. This month's gathering is in your very capable, slightly unwilling hands. We believe in you unconditionally.",
    f"🌟 Big news! <@{slack_user_id}> has been chosen by the sacred algorithm to organize this month's gathering. Think of it as a leadership opportunity. A very logistical, calendar-heavy, opinion-heavy leadership opportunity.",
    f"👑 All hail <@{slack_user_id}>, our Designated Volunteer of the Month! May your inbox be light, your venue choices be uncontested, and your team be unusually decisive about dates. (Two of those things will happen.)",
    f"🎲 The dice have been rolled, the wheel has been spun, and the universe has landed on <@{slack_user_id}>. Organizing this month's gathering is now your destiny. Fight it if you must, but the algorithm is non-negotiable.",
    f"📋 Exciting update: <@{slack_user_id}> has been selected to organize this month's team gathering! We're confident they'll do a fantastic job, and we promise to have exactly one opinion about the snacks — just kidding, we'll have dozens.",
    f"🏆 Someone has to do it, and that someone is <@{slack_user_id}>. Chosen fairly, chosen randomly, chosen irrevocably. This month's gathering coordination is officially yours. We appreciate you. The algorithm does not accept appeals.",
    f"🔮 The oracle has consulted the spreadsheet and found a name: <@{slack_user_id}>. This month, they shall venture into the realm of venue booking, Doodle polls, and Slack reminders. Godspeed, brave one.",
    f"📬 Good news and good news: <@{slack_user_id}> gets to organize this month's gathering! The first good news is that it's them and not you. The second good news is that it's only once a year. (They might not see it that way yet.)",
    f"⚡️ Breaking: <@{slack_user_id}> has been elected by a committee of one (the random picker) to lead our monthly gathering into existence. Their mandate: find the place, set the date, herd the cats. Term length: 30 days.",
    f"🎯 Direct hit. <@{slack_user_id}> has been selected to organize this month's team gathering. The random picker shows no mercy, but it does show great taste. We'll be cheering you on from the sidelines, silently, while you figure out the logistics.",
    f"🌈 Lovely news, everyone — and by everyone, I mean everyone except <@{slack_user_id}>, who must now organize this month's gathering. The rest of us will be available to provide unhelpful suggestions at any time. You're welcome in advance.",
])
        try:
            self._client.chat_postMessage(channel=channel_id, text=text)
        except SlackApiError as exc:
            raise SlackClientError(f"Failed to post announcement to {channel_id!r}: {exc}") from exc

        logger.info("Posted announcement for user %s in channel %s", slack_user_id, channel_id)
