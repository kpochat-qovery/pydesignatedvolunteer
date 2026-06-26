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


def pick_volunteer(all_emails: list[str], already_picked: list[str]) -> tuple[str, bool]:
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
    list_reset = False
    excluded = set(already_picked)
    candidates = [e for e in all_emails if e not in excluded]
    if not candidates:
        logger.info("Empty candidates list after history filtering. Reseting to all members.")
        list_reset = True
        candidates = [e for e in all_emails]
    picked = random.choice(candidates)
    logger.info("Picked volunteer: %s (from %d candidate(s))", picked, len(candidates))
    return picked, list_reset
