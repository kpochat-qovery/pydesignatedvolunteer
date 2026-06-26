"""Tests for picker.py."""

import pytest

from src.picker import PickerError, extract_picked_emails, pick_volunteer


def test_extract_picked_emails_reads_metadata() -> None:
    """extract_picked_emails returns emails stored in message metadata."""
    messages = [
        {"metadata": {"event_payload": {"picked_email": "a@example.com"}}},
        {"metadata": {"event_payload": {"picked_email": "b@example.com"}}},
    ]
    assert extract_picked_emails(messages) == ["a@example.com", "b@example.com"]


def test_extract_picked_emails_ignores_messages_without_metadata() -> None:
    """extract_picked_emails skips messages that carry no bot metadata."""
    messages = [
        {},
        {"metadata": {}},
        {"metadata": {"event_payload": {}}},
        {"metadata": {"event_payload": {"picked_email": "a@example.com"}}},
    ]
    assert extract_picked_emails(messages) == ["a@example.com"]


def test_extract_picked_emails_deduplicates() -> None:
    """extract_picked_emails returns each email only once."""
    messages = [
        {"metadata": {"event_payload": {"picked_email": "a@example.com"}}},
        {"metadata": {"event_payload": {"picked_email": "b@example.com"}}},
        {"metadata": {"event_payload": {"picked_email": "a@example.com"}}},
    ]
    assert extract_picked_emails(messages) == ["a@example.com", "b@example.com"]


def test_extract_picked_emails_empty_history() -> None:
    """extract_picked_emails returns an empty list when no messages are provided."""
    assert extract_picked_emails([]) == []


def test_pick_volunteer_excludes_already_picked() -> None:
    """pick_volunteer never returns an email in the already_picked list."""
    result = pick_volunteer(
        all_emails=["a@example.com", "b@example.com", "c@example.com"],
        already_picked=["a@example.com", "b@example.com"],
    )
    assert result == "c@example.com"


def test_pick_volunteer_raises_when_all_picked() -> None:
    """pick_volunteer raises PickerError when every member has been picked."""
    with pytest.raises(PickerError):
        pick_volunteer(
            all_emails=["a@example.com", "b@example.com"],
            already_picked=["a@example.com", "b@example.com"],
        )


def test_pick_volunteer_selects_uniformly() -> None:
    """pick_volunteer returns every eligible email with roughly equal probability."""
    all_emails = ["a@example.com", "b@example.com", "c@example.com"]
    counts: dict[str, int] = {e: 0 for e in all_emails}
    for _ in range(300):
        result = pick_volunteer(all_emails=all_emails, already_picked=[])
        counts[result] += 1
    for email in all_emails:
        assert counts[email] > 50


def test_pick_volunteer_single_eligible_candidate() -> None:
    """pick_volunteer returns the only remaining candidate deterministically."""
    result = pick_volunteer(
        all_emails=["a@example.com", "b@example.com"],
        already_picked=["a@example.com"],
    )
    assert result == "b@example.com"
