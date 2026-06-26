"""Environment variable loading and validation.

Raises ConfigurationError on any missing or invalid required variable.
"""

import logging
import os
from dataclasses import dataclass

DEFAULT_HISTORY_LOOKBACK_DAYS = 90
DEFAULT_BOT_MESSAGE_MARKER = "picked-by-bot"

_REQUIRED_VARS = [
    "SLACK_BOT_TOKEN",
    "SLACK_CHANNEL_ID",
    "SLACK_BOT_USER_ID",
    "GOOGLE_WORKSPACE_GROUP_EMAIL",
    "GOOGLE_WORKSPACE_ADMIN_EMAIL",
]

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass
class Config:
    slack_bot_token: str
    slack_channel_id: str
    slack_bot_user_id: str
    google_workspace_group_email: str
    google_workspace_admin_email: str
    google_service_account_key_content: str
    history_lookback_days: int = DEFAULT_HISTORY_LOOKBACK_DAYS
    bot_message_marker: str = DEFAULT_BOT_MESSAGE_MARKER


def load_config() -> Config:
    """Load and validate all required environment variables.

    Returns:
        A fully populated Config instance.

    Raises:
        ConfigurationError: If any required variable is absent or invalid.
    """
    missing = [var for var in _REQUIRED_VARS if not os.environ.get(var)]
    if missing:
        raise ConfigurationError(f"Missing required environment variable(s): {', '.join(missing)}")

    key_content = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
    key_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY_FILE")

    if key_content:
        if key_file:
            logger.warning(
                "Both GOOGLE_SERVICE_ACCOUNT_KEY and GOOGLE_SERVICE_ACCOUNT_KEY_FILE are set; "
                "GOOGLE_SERVICE_ACCOUNT_KEY_FILE will not be used."
            )
        google_service_account_key_content = key_content
    elif key_file:
        with open(key_file) as f:
            google_service_account_key_content = f.read()
    else:
        raise ConfigurationError(
            "Missing required environment variable(s): "
            "GOOGLE_SERVICE_ACCOUNT_KEY or GOOGLE_SERVICE_ACCOUNT_KEY_FILE"
        )

    raw_lookback = os.environ.get("HISTORY_LOOKBACK_DAYS", str(DEFAULT_HISTORY_LOOKBACK_DAYS))
    try:
        history_lookback_days = int(raw_lookback)
        if history_lookback_days <= 0:
            raise ValueError
    except ValueError:
        raise ConfigurationError(
            f"HISTORY_LOOKBACK_DAYS must be a positive integer, got: {raw_lookback!r}"
        )

    return Config(
        slack_bot_token=os.environ["SLACK_BOT_TOKEN"],
        slack_channel_id=os.environ["SLACK_CHANNEL_ID"],
        slack_bot_user_id=os.environ["SLACK_BOT_USER_ID"],
        google_workspace_group_email=os.environ["GOOGLE_WORKSPACE_GROUP_EMAIL"],
        google_workspace_admin_email=os.environ["GOOGLE_WORKSPACE_ADMIN_EMAIL"],
        google_service_account_key_content=google_service_account_key_content,
        history_lookback_days=history_lookback_days,
        bot_message_marker=os.environ.get("BOT_MESSAGE_MARKER", DEFAULT_BOT_MESSAGE_MARKER),
    )
