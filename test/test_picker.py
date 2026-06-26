"""Tests for picker.py."""

import pytest

from src.picker import PickerError, pick_volunteer


def test_pick_volunteer_excludes_already_picked() -> None:
    result, list_reset = pick_volunteer(
        all_emails=["a@example.com", "b@example.com", "c@example.com"],
        already_picked=["a@example.com", "b@example.com"],
    )
    assert result == "c@example.com"
    assert list_reset is False


def test_pick_volunteer_resets_when_all_picked() -> None:
    """When every member has been picked, the candidate list resets to all members."""
    all_emails = ["a@example.com", "b@example.com"]
    result, list_reset = pick_volunteer(
        all_emails=all_emails,
        already_picked=all_emails,
    )
    assert result in all_emails
    assert list_reset is True


def test_pick_volunteer_selects_uniformly() -> None:
    """pick_volunteer returns every eligible email with roughly equal probability."""
    all_emails = ["a@example.com", "b@example.com", "c@example.com"]
    counts: dict[str, int] = {e: 0 for e in all_emails}
    for _ in range(300):
        result, _ = pick_volunteer(all_emails=all_emails, already_picked=[])
        counts[result] += 1
    for email in all_emails:
        assert counts[email] > 50


def test_pick_volunteer_single_eligible_candidate() -> None:
    """pick_volunteer returns the only remaining candidate deterministically."""
    result, list_reset = pick_volunteer(
        all_emails=["a@example.com", "b@example.com"],
        already_picked=["a@example.com"],
    )
    assert result == "b@example.com"
    assert list_reset is False
