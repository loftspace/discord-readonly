from datetime import datetime, timezone

import pytest

from discordro import cli, client
from discordro.client import DiscordError


@pytest.mark.parametrize("bad", ["https://evil.example/x", "//evil.example/x", "/x/../../y",
                                 "channels/1", "/users/@me\nHost: x", "/a?b=<script>"])
def test_rejects_paths_that_could_leak_the_token(bad: str) -> None:
    with pytest.raises(DiscordError):
        client.check_path(bad)


def test_accepts_api_paths() -> None:
    for ok in ("/users/@me", "/users/@me/guilds", "/channels/123/messages?limit=100&after=456",
               "/guilds/789/threads/active"):
        assert client.check_path(ok) == ok


def test_request_refuses_other_hosts() -> None:
    with pytest.raises(DiscordError):
        client._request("https://evil.example/api/v10/x", "t")


def test_snowflake_round_trip() -> None:
    when = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
    sf = client.snowflake_at(when)
    assert client.snowflake_time(sf) == when
    assert client.snowflake_time("175928847299117063") == datetime(2016, 4, 30, 11, 18, 25, 796000, tzinfo=timezone.utc)


def test_messages_since_pages_oldest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    first = [{"id": str(i)} for i in range(200, 100, -1)]  # 100 messages, newest first like Discord
    second = [{"id": "300"}]

    def fake_get(path: str, token: str | None = None):
        calls.append(path)
        return first if "after=50" in path else second

    monkeypatch.setattr(client, "get", fake_get)
    out = client.messages_since("1", 50, token="t")
    assert [m["id"] for m in out][:2] == ["101", "102"] and out[-1]["id"] == "300"
    assert calls[1].endswith("after=200")


def test_parse_since() -> None:
    now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
    assert cli.parse_since("7d", now) == datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
    assert cli.parse_since("2026-11-17", now).date().isoformat() == "2026-11-17"
    with pytest.raises(DiscordError):
        cli.parse_since("last week", now)


def test_export_formats_and_warns_on_missing_content(monkeypatch: pytest.MonkeyPatch) -> None:
    since = datetime(2026, 11, 18, 8, 0, tzinfo=timezone.utc)
    msg_id = str(client.snowflake_at(datetime(2026, 11, 18, 9, 30, tzinfo=timezone.utc)) + 1)
    answers = {
        "/guilds/1/channels": [{"id": "10", "type": 0, "name": "generelt", "position": 0, "last_message_id": msg_id},
                               {"id": "11", "type": 2, "name": "voice"}],
        "/guilds/1/threads/active": {"threads": []},
    }
    monkeypatch.setattr(client, "get", lambda path, **kw: answers[path])
    monkeypatch.setattr(client, "messages_since", lambda cid, after, **kw: [
        {"id": msg_id, "type": 0, "content": "Møte fredag kl 10",
         "author": {"username": "billal"}, "attachments": [{"filename": "plan.pdf"}]}])
    out = cli.export(["1"], since)
    assert "## #generelt" in out and "voice" not in out
    assert "2026-11-18 10:30 **billal**: Møte fredag kl 10 [vedlegg: plan.pdf]" in out

    monkeypatch.setattr(client, "messages_since", lambda cid, after, **kw: [
        {"id": msg_id, "type": 0, "content": "", "author": {"username": "x"}}])
    assert "Message Content Intent" in cli.export(["1"], since)


def test_export_skips_quiet_channels(monkeypatch: pytest.MonkeyPatch) -> None:
    since = datetime(2026, 11, 18, tzinfo=timezone.utc)
    old = str(client.snowflake_at(datetime(2026, 11, 1, tzinfo=timezone.utc)))
    monkeypatch.setattr(client, "get", lambda path, **kw: (
        [{"id": "10", "type": 0, "name": "stille", "last_message_id": old}] if path.endswith("channels")
        else {"threads": []}))

    def boom(*a, **kw):
        raise AssertionError("should not fetch a channel with no new messages")

    monkeypatch.setattr(client, "messages_since", boom)
    assert "Ingen nye meldinger" in cli.export(["1"], since)


def test_download_refuses_non_cdn_hosts(tmp_path) -> None:
    with pytest.raises(DiscordError):
        client.download_attachment("https://evil.example/x.png", str(tmp_path / "x.png"))
    with pytest.raises(DiscordError):
        client.download_attachment("https://discord.com/api/v10/x.png", str(tmp_path / "x.png"))


def test_export_downloads_images_and_shows_local_path(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    since = datetime(2026, 11, 18, 8, 0, tzinfo=timezone.utc)
    msg_id = str(client.snowflake_at(datetime(2026, 11, 18, 9, 30, tzinfo=timezone.utc)) + 1)
    monkeypatch.setattr(client, "get", lambda path, **kw: (
        [{"id": "10", "type": 0, "name": "generelt", "last_message_id": msg_id}] if path.endswith("channels")
        else {"threads": []}))
    monkeypatch.setattr(client, "messages_since", lambda cid, after, **kw: [
        {"id": msg_id, "type": 0, "content": "se her", "author": {"username": "mahrukh"},
         "attachments": [{"id": "a1", "filename": "skjerm.PNG", "url": "https://cdn.discordapp.com/a/skjerm.PNG"},
                         {"id": "a2", "filename": "plan.pdf", "url": "https://cdn.discordapp.com/a/plan.pdf"}]}])
    fetched = []

    def fake_download(url: str, dest: str) -> int:
        fetched.append(url)
        with open(dest, "wb") as fh:
            fh.write(b"img")
        return 3

    monkeypatch.setattr(client, "download_attachment", fake_download)
    out = cli.export(["1"], since, image_dir=str(tmp_path / "bilder"))
    assert fetched == ["https://cdn.discordapp.com/a/skjerm.PNG"]  # pdf is not downloaded
    assert f"[bilde: {str(tmp_path / 'bilder').replace(chr(92), '/')}/{msg_id}-0.png]" in out
    assert "[vedlegg: plan.pdf]" in out


def test_failed_image_download_is_reported_not_fatal(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    def boom(url: str, dest: str) -> int:
        raise DiscordError("CDN answered 404")

    monkeypatch.setattr(client, "download_attachment", boom)
    out = cli.save_images({"id": "5", "attachments": [{"id": "a", "filename": "x.jpg", "url": "u"}]}, str(tmp_path))
    assert out["a"].startswith("ikke lastet ned")


def test_guild_defaults_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_GUILD_ID", "42")
    assert cli._guilds(None) == ["42"]
    assert cli._guilds("7") == ["7"]


def test_clipboard_tries_next_tool_and_gives_up_quietly(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd[0])
        if cmd[0] == "wl-paste":
            raise FileNotFoundError
        return type("R", (), {"stdout": " tok en \n" if cmd[0] == "xclip" else ""})()

    monkeypatch.setattr(cli.sys, "platform", "linux")
    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    assert cli._clipboard() == "token"
    assert calls == ["wl-paste", "xclip"]


def test_token_falls_back_to_legacy_service(monkeypatch: pytest.MonkeyPatch) -> None:
    store = {(client.LEGACY_SERVICE, client.ACCOUNT): "old"}
    monkeypatch.setattr(client.keyring, "get_password", lambda s, a: store.get((s, a)))
    assert client.get_token() == "old"
