"""Entry point for the Designated Volunteer Slackbot.

Orchestrates config loading, Google group member fetch, Slack history analysis,
volunteer picking, and message posting. No business logic lives here.
"""

import logging
import sys

from config import ConfigurationError, load_config
from google_client import GoogleClient, GoogleClientError
from picker import PickerError, pick_volunteer
from slack_client import SlackClient, SlackClientError

logger = logging.getLogger(__name__)


def run() -> None:
    """Execute one full bot cycle: fetch → analyse → pick → post."""
    try:
        config = load_config()
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    try:
        google_client = GoogleClient(config)
        member_emails = google_client.get_group_member_emails(config.google_workspace_group_email)

        slack_client = SlackClient(config)
        channel_id = config.slack_channel_id or slack_client.resolve_channel_name_to_id(
            config.slack_channel_name  # type: ignore[arg-type]
        )
        memory_channel_id = config.slack_bot_memory_channel_id or slack_client.resolve_channel_name_to_id(
            config.slack_bot_memory_channel_name  # type: ignore[arg-type]
        )

        messages = slack_client.get_bot_messages(memory_channel_id, config.history_lookback_days)

        picked_emails = slack_client.extract_picked_emails_from_messages(messages)
        picked_email, list_reset = pick_volunteer(all_emails=member_emails, already_picked=picked_emails)

        slack_user_id = slack_client.resolve_email_to_slack_user_id(picked_email)
        if slack_user_id is None:
            logger.warning(
                "Picked email %r has no matching Slack user; skipping post", picked_email
            )
            return

        slack_client.post_memory_message(memory_channel_id, picked_email, slack_user_id, list_reset)
        slack_client.post_announcement(channel_id, slack_user_id)

    except (GoogleClientError, SlackClientError, PickerError) as exc:
        logger.error("Bot run failed: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error("Unexpected error during bot run: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
