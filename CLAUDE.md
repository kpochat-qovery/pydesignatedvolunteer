# CLAUDE.md — Designated Volunteer

## Project Overview

A stateless Slackbot run as a cronjob. Each run:

1. Fetches member email addresses from a Google Workspace group via the Admin SDK.
2. Reads the target Slack channel's history to find messages previously posted by this bot.
3. Extracts already-picked users from those messages via **Slack message metadata** (not text parsing).
4. Picks one email at random that hasn't been picked before.
5. Resolves that email to a Slack user ID and posts an announcement mentioning them.

Stateless means: no database, no files — the channel history is the only state store.

## Architecture

Mirrors https://github.com/kpochat-qovery/pyslackrandomcoffee.

| Module | Responsibility |
|---|---|
| `config.py` | Loads and validates all env vars; raises `ConfigurationError` on failure |
| `slack_client.py` | Slack API wrapper with pagination and error handling; raises `SlackClientError` |
| `google_client.py` | Google Workspace Admin SDK wrapper; raises `GoogleClientError` |
| `picker.py` | Exclusion list logic and random selection; raises `PickerError` |
| `main.py` | Linear `run()` that orchestrates the modules — no business logic |

### Data flow

```
main.run()
  ├─ load_config()
  ├─ GoogleClient.get_group_member_emails(group_email)              → all_emails
  ├─ SlackClient.get_bot_messages(memory_channel_id, lookback_days) → messages
  ├─ extract_picked_emails(messages)                                → already_picked
  ├─ pick_volunteer(all_emails, already_picked)                     → picked_email
  ├─ SlackClient.resolve_email_to_user_id(picked_email)             → slack_user_id
  ├─ SlackClient.post_memory_message(memory_channel_id, picked_email) → tracking record
  └─ SlackClient.post_announcement(channel_id, slack_user_id)       → user-facing mention
```

`memory_channel_id` resolves to `SLACK_BOT_MEMORY_CHANNEL_ID`/`SLACK_BOT_MEMORY_CHANNEL_NAME` when set, otherwise falls back to the main channel. When they are the same, both messages land in the same channel.

## Code Style

- **Type hints** on all functions and class attributes; use `list[T]` / `dict[K, V]` (Python 3.10+ style, no `List`/`Dict` from `typing`).
- **Custom exceptions** per module (`ConfigurationError`, `SlackClientError`, `GoogleClientError`, `PickerError`); propagate unhandled to `main.py` which logs and exits non-zero.
- **Pagination** on every list-returning API call; never assume a single page is the full result.
- **Rate limiting constants** (`RATE_LIMIT_DELAY_SECONDS`, page-size constants) at the top of each API wrapper module.
- **Logging** via `logging.getLogger(__name__)` — never `print()`.
- **No hardcoded values** — everything flows from `Config`.
- **No comments** unless the *why* is non-obvious (a hidden constraint, a workaround, a subtle invariant).

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | — | Bot User OAuth Token (`xoxb-…`) |
| `SLACK_CHANNEL_ID` | Yes* | — | ID of the main channel (user-facing announcements) |
| `SLACK_CHANNEL_NAME` | Yes* | — | Name of the main channel (alternative to `SLACK_CHANNEL_ID`) |
| `SLACK_BOT_USER_ID` | Yes | — | Bot's own user ID (filters its own messages from history) |
| `SLACK_BOT_MEMORY_CHANNEL_ID` | No | main channel | ID of the bot-memory channel (tracking records + metadata) |
| `SLACK_BOT_MEMORY_CHANNEL_NAME` | No | main channel | Name of the bot-memory channel (alternative to `SLACK_BOT_MEMORY_CHANNEL_ID`) |
| `GOOGLE_WORKSPACE_GROUP_EMAIL` | Yes | — | Email address of the Google Workspace group |
| `GOOGLE_SERVICE_ACCOUNT_KEY_FILE` | Yes* | — | Path to service account JSON key file |
| `GOOGLE_SERVICE_ACCOUNT_KEY` | Yes* | — | Inline service account JSON key content (alternative to `KEY_FILE`) |
| `GOOGLE_WORKSPACE_ADMIN_EMAIL` | Yes | — | Admin email to impersonate for domain-wide delegation |
| `HISTORY_LOOKBACK_DAYS` | No | `90` | How far back (days) to search Slack history |
| `BOT_MESSAGE_MARKER` | No | `picked-by-bot` | Fixed string in all bot memory messages used to identify them |

\* At least one of the marked pairs is required.

## Google Auth

Uses a **service account with domain-wide delegation**.

Requirements:
- Admin SDK Directory API enabled on the GCP project.
- The scope `https://www.googleapis.com/auth/admin.directory.group.member.readonly` granted in the Google Workspace Admin Console under Security → API controls → Domain-wide delegation.
- The service account JSON key file path set in `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`.
- `GOOGLE_WORKSPACE_ADMIN_EMAIL` must be an actual Workspace admin — the service account impersonates this identity.

## Slack Scopes Required

| Scope | Purpose |
|---|---|
| `channels:history` | Read channel message history |
| `channels:read` | Verify channel access |
| `chat:write` | Post messages |
| `users:read` | Resolve email → Slack user ID (`users.lookupByEmail`) |
| `users:read.email` | Required alongside `users:read` for email lookup |

## Slack Message Metadata

Bot messages embed the picked email in [Slack's structured metadata](https://api.slack.com/metadata) — **not** in the visible text. This makes the exclusion list robust to message reformatting.

Metadata shape stored per message:
```json
{
  "event_type": "designated_volunteer_picked",
  "event_payload": {
    "picked_email": "user@example.com"
  }
}
```

`extract_picked_emails()` in `picker.py` reads `message["metadata"]["event_payload"]["picked_email"]`.

## Running

```bash
# Local (from repo root)
python src/main.py

# Docker
docker build -t designated-volunteer .
docker run --env-file .env designated-volunteer

# Tests
pytest test/
```

## Session Plan

Implemented across multiple Claude Code sessions to limit context:

| Session | Scope |
|---|---|
| 1 (done) | Scaffold: directory structure, stubs, CLAUDE.md |
| 2 | `config.py` + `test_config.py` |
| 3 | `google_client.py` + `test_google_client.py` |
| 4 | `slack_client.py` + `test_slack_client.py` |
| 5 | `picker.py` + `test_picker.py` |
| 6 (done) | `main.py` + Dockerfile hardening + integration review |

When starting a new session, read this file first, then read the relevant module and its test file before writing any code.

## Reference

- Sister project (same architecture): https://github.com/kpochat-qovery/pyslackrandomcoffee
- Slack message metadata docs: https://api.slack.com/metadata
- Google Admin SDK Directory API: https://developers.google.com/admin-sdk/directory/reference/rest/v1/members/list
