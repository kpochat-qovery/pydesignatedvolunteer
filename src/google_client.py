"""Google Workspace Admin SDK wrapper.

Uses a service account with domain-wide delegation to read group membership.
All public methods raise GoogleClientError on API failures.
"""

import logging
import time

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import Config

PAGE_REQUEST_DELAY_SECONDS: float = 0.5
MEMBERS_PAGE_SIZE: int = 200
SCOPES: list[str] = [
    "https://www.googleapis.com/auth/admin.directory.group.member.readonly",
]

logger = logging.getLogger(__name__)


class GoogleClientError(Exception):
    """Raised when a Google Admin SDK call fails or returns unexpected data."""


class GoogleClient:
    def __init__(self, config: Config) -> None:
        try:
            credentials = service_account.Credentials.from_service_account_file(
                config.google_service_account_key_file,
                scopes=SCOPES,
            ).with_subject(config.google_workspace_admin_email)
            self._service = build("admin", "directory_v1", credentials=credentials)
        except Exception as exc:
            raise GoogleClientError(f"Failed to initialise Google Admin SDK client: {exc}") from exc

    def get_group_member_emails(self, group_email: str) -> list[str]:
        """Fetch all member email addresses from a Google Workspace group.

        Follows pagination to return the complete membership list.
        Only ACTIVE members are returned.

        Args:
            group_email: The group's email address (e.g. team@example.com).

        Returns:
            List of member email addresses.

        Raises:
            GoogleClientError: On API error, auth failure, or empty/invalid response.
        """
        emails: list[str] = []
        page_token: str | None = None
        page_num = 0

        try:
            while True:
                page_num += 1
                logger.debug(
                    "Fetching members page %d for group %s (pageToken=%s)",
                    page_num,
                    group_email,
                    page_token,
                )
                response = (
                    self._service.members()
                    .list(
                        groupKey=group_email,
                        maxResults=MEMBERS_PAGE_SIZE,
                        pageToken=page_token,
                    )
                    .execute()
                )

                for member in response.get("members", []):
                    if member.get("status") == "ACTIVE" and member.get("email"):
                        emails.append(member["email"])

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

                time.sleep(PAGE_REQUEST_DELAY_SECONDS)

        except HttpError as exc:
            raise GoogleClientError(
                f"Google Admin SDK API error for group {group_email!r}: {exc}"
            ) from exc
        except Exception as exc:
            raise GoogleClientError(
                f"Unexpected error fetching members for group {group_email!r}: {exc}"
            ) from exc

        logger.info("Fetched %d active member(s) from group %s", len(emails), group_email)
        return emails
