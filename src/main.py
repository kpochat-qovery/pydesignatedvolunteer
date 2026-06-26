"""Entry point for the Designated Volunteer Slackbot.

Orchestrates config loading, Google group member fetch, Slack history analysis,
volunteer picking, and message posting. No business logic lives here.
"""

import logging
import sys

from src.config import ConfigurationError, load_config
from src.google_client import GoogleClient, GoogleClientError
from src.picker import PickerError, extract_picked_emails, pick_volunteer
from src.slack_client import SlackClient, SlackClientError

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
        messages = slack_client.get_bot_messages(config.slack_channel_id, config.history_lookback_days)

        picked_emails = extract_picked_emails(messages)
        picked_email = pick_volunteer(all_emails=member_emails, already_picked=picked_emails)

        slack_user_id = slack_client.resolve_email_to_slack_user_id(picked_email)
        if slack_user_id is None:
            logger.warning(
                "Picked email %r has no matching Slack user; skipping post", picked_email
            )
            return

        slack_client.post_pick_message(config.slack_channel_id, slack_user_id, picked_email)

    except (GoogleClientError, SlackClientError, PickerError) as exc:
        logger.error("Bot run failed: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error("Unexpected error during bot run: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
