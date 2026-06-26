"""Tests for google_client.py."""

from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from src.google_client import GoogleClient, GoogleClientError


GROUP_EMAIL = "team@example.com"


def _make_config(key_file: str = "/fake/key.json", admin_email: str = "admin@example.com") -> MagicMock:
    config = MagicMock()
    config.google_service_account_key_file = key_file
    config.google_workspace_admin_email = admin_email
    return config


def _make_client() -> GoogleClient:
    """Return a GoogleClient with all Google SDK calls patched out."""
    with (
        patch("src.google_client.service_account.Credentials.from_service_account_file"),
        patch("src.google_client.build"),
    ):
        return GoogleClient(_make_config())


def _members_list_response(members: list[dict], next_page_token: str | None = None) -> dict:
    response: dict = {"members": members}
    if next_page_token:
        response["nextPageToken"] = next_page_token
    return response


# ---------------------------------------------------------------------------
# Successful single-page fetch
# ---------------------------------------------------------------------------

def test_get_group_member_emails_success() -> None:
    client = _make_client()
    members = [
        {"email": "alice@example.com", "status": "ACTIVE"},
        {"email": "bob@example.com", "status": "ACTIVE"},
    ]
    client._service.members().list().execute.return_value = _members_list_response(members)

    result = client.get_group_member_emails(GROUP_EMAIL)

    assert result == ["alice@example.com", "bob@example.com"]


# ---------------------------------------------------------------------------
# Pagination: two pages
# ---------------------------------------------------------------------------

def test_get_group_member_emails_paginates() -> None:
    client = _make_client()

    page1 = _members_list_response(
        [{"email": "alice@example.com", "status": "ACTIVE"}],
        next_page_token="tok123",
    )
    page2 = _members_list_response(
        [{"email": "bob@example.com", "status": "ACTIVE"}],
    )

    list_mock = client._service.members().list.return_value
    list_mock.execute.side_effect = [page1, page2]

    with patch("src.google_client.time.sleep") as mock_sleep:
        result = client.get_group_member_emails(GROUP_EMAIL)

    assert result == ["alice@example.com", "bob@example.com"]
    mock_sleep.assert_called_once()


# ---------------------------------------------------------------------------
# Inactive members are filtered out
# ---------------------------------------------------------------------------

def test_get_group_member_emails_filters_inactive() -> None:
    client = _make_client()
    members = [
        {"email": "alice@example.com", "status": "ACTIVE"},
        {"email": "suspended@example.com", "status": "SUSPENDED"},
        {"email": "unknown@example.com", "status": "UNKNOWN"},
    ]
    client._service.members().list().execute.return_value = _members_list_response(members)

    result = client.get_group_member_emails(GROUP_EMAIL)

    assert result == ["alice@example.com"]


# ---------------------------------------------------------------------------
# Empty group
# ---------------------------------------------------------------------------

def test_get_group_member_emails_empty_group() -> None:
    client = _make_client()
    client._service.members().list().execute.return_value = {"members": []}

    result = client.get_group_member_emails(GROUP_EMAIL)

    assert result == []


# ---------------------------------------------------------------------------
# HttpError → GoogleClientError
# ---------------------------------------------------------------------------

def test_get_group_member_emails_raises_on_http_error() -> None:
    client = _make_client()

    fake_resp = MagicMock()
    fake_resp.status = 403
    fake_resp.reason = "Forbidden"
    http_err = HttpError(resp=fake_resp, content=b"Forbidden")
    client._service.members().list().execute.side_effect = http_err

    with pytest.raises(GoogleClientError, match="API error"):
        client.get_group_member_emails(GROUP_EMAIL)


# ---------------------------------------------------------------------------
# Auth / init failure → GoogleClientError
# ---------------------------------------------------------------------------

def test_get_group_member_emails_raises_on_auth_failure() -> None:
    with (
        patch(
            "src.google_client.service_account.Credentials.from_service_account_file",
            side_effect=ValueError("invalid key file"),
        ),
        patch("src.google_client.build"),
    ):
        with pytest.raises(GoogleClientError, match="Failed to initialise"):
            GoogleClient(_make_config(key_file="/nonexistent/key.json"))
