"""Discord REST access for a read-only bot (Windows, macOS, Linux). Only GET, only to BASE, so the token can never be sent anywhere else."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

import keyring

HOST = "discord.com"
BASE = f"https://{HOST}/api/v10"
SERVICE = "discord-readonly"
LEGACY_SERVICE = "discord-bachelor"  # name used by the first version
ACCOUNT = "token"
DISCORD_EPOCH_MS = 1420070400000
USER_AGENT = "DiscordBot (https://github.com/loftspace/discord-readonly, 0.3.0) discord-readonly"
_PATH = re.compile(r"^/[A-Za-z0-9_\-/@]*(\?[A-Za-z0-9_\-=&%.:,]*)?$")


class DiscordError(Exception):
    """A problem the user can act on. Never carries the token."""


def get_token() -> str:
    token = keyring.get_password(SERVICE, ACCOUNT) or keyring.get_password(LEGACY_SERVICE, ACCOUNT)
    if not token:
        raise DiscordError("No saved Discord bot token. Run: discord setup --clipboard")
    return token


def check_path(path: str) -> str:
    """Only relative API paths like /channels/123/messages?limit=100. No hosts, no schemes."""
    if not _PATH.match(path) or ".." in path or "//" in path:
        raise DiscordError(f"Not an allowed API path: {path!r}")
    return path


def _request(url: str, token: str) -> Any:
    if not url.startswith(BASE + "/"):
        raise DiscordError("Refusing to send the token outside the Discord API.")
    req = urllib.request.Request(url, headers={"Authorization": f"Bot {token}", "Accept": "application/json",
                                               "User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # fixed https host, checked above
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 3:
                try:
                    wait = float(json.loads(exc.read().decode("utf-8", "replace")).get("retry_after", 1))
                except (ValueError, AttributeError):
                    wait = 1.0
                time.sleep(min(wait, 10) + 0.1)
                continue
            hint = {401: " (token wrong or reset)", 403: " (the bot cannot see this; check its permissions)",
                    404: " (unknown id, or the bot is not in that server)"}.get(exc.code, "")
            raise DiscordError(f"Discord answered {exc.code} for {url[len(BASE):]}{hint}") from None
        except OSError as exc:
            raise DiscordError(f"Could not reach {HOST}: {exc.__class__.__name__}") from None
    raise DiscordError("Discord rate limit, try again later.")


def get(path: str, token: str | None = None) -> Any:
    return _request(BASE + check_path(path), token or get_token())


def snowflake_time(snowflake: str | int) -> datetime:
    ms = (int(snowflake) >> 22) + DISCORD_EPOCH_MS
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def snowflake_at(when: datetime) -> int:
    """Smallest snowflake at this moment: messages after it are newer."""
    return max(0, int(when.timestamp() * 1000) - DISCORD_EPOCH_MS) << 22


CDN_HOSTS = ("https://cdn.discordapp.com/", "https://media.discordapp.net/")
IMAGE_TYPES = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_IMAGE_BYTES = 25 * 1024 * 1024


def download_attachment(url: str, dest: str) -> int:
    """Save one attachment from Discord's CDN. Never sends the token. Returns the byte count."""
    if not url.startswith(CDN_HOSTS):
        raise DiscordError("Refusing to download from outside Discord's CDN.")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # fixed https CDN host, checked above
            data = resp.read(MAX_IMAGE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise DiscordError(f"CDN answered {exc.code} (the link may have expired; export again)") from None
    except OSError as exc:
        raise DiscordError(f"Could not reach the CDN: {exc.__class__.__name__}") from None
    if len(data) > MAX_IMAGE_BYTES:
        raise DiscordError("Attachment is larger than 25 MB; skipped.")
    with open(dest, "wb") as fh:
        fh.write(data)
    return len(data)


def messages_since(channel_id: str, after: int, token: str | None = None, max_pages: int = 20) -> list[dict[str, Any]]:
    """All messages in a channel newer than snowflake `after`, oldest first (100 per page)."""
    secret = token or get_token()
    out: list[dict[str, Any]] = []
    cursor = after
    for _ in range(max_pages):
        page = get(f"/channels/{int(channel_id)}/messages?limit=100&after={cursor}", token=secret) or []
        if not page:
            break
        page.sort(key=lambda m: int(m["id"]))
        out.extend(page)
        cursor = int(page[-1]["id"])
        if len(page) < 100:
            break
    return out
