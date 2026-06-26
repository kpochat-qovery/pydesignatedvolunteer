# Designated Volunteer

A stateless Slackbot run as a cronjob. It picks one person from a Google Workspace group who hasn't been picked recently and announces them in a Slack channel.

## How it works

1. Fetches member emails from a Google Workspace group via the Admin SDK.
2. Reads the target Slack channel's history to find messages previously posted by this bot.
3. Extracts already-picked users from Slack message metadata (not text parsing).
4. Picks one email at random that hasn't been picked before.
5. Posts a message in the channel mentioning the picked user.

## Setup

```bash
cp .env.template .env
# Fill in all values in .env
pip install -r requirements.txt
```

## Running

```bash
# Local
python src/main.py

# Docker
docker build -t designated-volunteer .
docker run --env-file .env designated-volunteer
```

## Tests

```bash
pytest test/
```

## Google Auth

Uses a service account with domain-wide delegation. See CLAUDE.md for required scopes.
