"""Volunteer selection logic.

Extracts the exclusion list from previous bot messages and picks a random
eligible volunteer from the remaining candidates.
"""

import logging
import random
from typing import Any


logger = logging.getLogger(__name__)


class PickerError(Exception):
    """Raised when no eligible volunteer can be selected."""


def extract_picked_emails(messages: list[dict[str, Any]]) -> list[str]:
    """Extract previously picked email addresses from Slack message metadata.

    Reads the structured metadata embedded by the bot at post time rather than
    parsing message text, so renaming or reformatting messages never breaks this.

    Args:
        messages: List of Slack message objects (as returned by SlackClient).

    Returns:
        Deduplicated list of email addresses that were picked in prior rounds.
    """
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


def pick_volunteer(all_emails: list[str], already_picked: list[str]) -> str:
    """Pick one email address at random from the eligible candidates.

    Args:
        all_emails: Full membership list from Google Workspace.
        already_picked: Emails excluded because they were picked before.

    Returns:
        A single email address chosen uniformly at random.

    Raises:
        PickerError: If every member has already been picked (exclusion list
            covers the full membership), leaving no eligible candidate.
    """
    excluded = set(already_picked)
    candidates = [e for e in all_emails if e not in excluded]
    if not candidates:
        raise PickerError(
            f"No eligible volunteers — all {len(all_emails)} member(s) have already been picked"
        )
    picked = random.choice(candidates)
    logger.info("Picked volunteer: %s (from %d candidate(s))", picked, len(candidates))
    return picked
