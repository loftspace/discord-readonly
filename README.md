# discord-readonly

Les meldinger og bilder fra en Discord-server i terminalen, gjennom en bot som **bare kan lese**.
Laget for bachelorgruppa vår, så vi kan hente det vi skriver på Discord inn i notater og KI-verktøy.

- Bare `GET`, og bare mot `https://discord.com/api/v10`. Tokenet kan ikke sendes noe annet sted.
- Tokenet lagres i operativsystemets nøkkelring (Windows Credential Manager, macOS Keychain, Linux Secret Service).
  Det skrives aldri ut og havner aldri i en fil.
- Virker på Windows, macOS og Linux. Krever Python 3.10 eller nyere.

## Installer

Enklest med [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/loftspace/discord-readonly
```

Eller med pip: `pip install git+https://github.com/loftspace/discord-readonly`

## Kom i gang

1. Få bot-tokenet fra Max (aldri over Discord, bruk en engangslenke eller gi det direkte).
2. Kopier tokenet og kjør:

   ```bash
   discord setup --clipboard
   ```

   Virker ikke utklippstavlen, kjør `discord setup` og lim inn tokenet (det vises ikke).
3. Sjekk at det virker:

   ```bash
   discord check       # botens navn og hvilke servere den er i
   discord channels    # kanaler den kan lese, med ID
   ```

## Bruk

```bash
discord export --since 7d                        # siste 7 dager som Markdown, norsk tid
discord export --since 2026-11-18                # fra en dato
discord export --since 3d --channel 123456789    # bare én kanal
discord export --since 7d --images bilder        # lagre bilder (skjermbilder) i mappa «bilder»
discord export --since 7d --out discord.md       # skriv til fil
discord get "/channels/123456789/messages?limit=10"   # rå API-kall (GET)
```

Sett `DISCORD_GUILD_ID` til serverens ID, så leser `export` og `channels` bare den serveren.

## Viktig

- **Ikke del tokenet videre.** Den som har det, kan lese alle servere boten er med i.
- **Ikke legg ut konfidensielt materiale fra oppdragsgiveren på serveren.** Det som eksporteres kan havne i KI-verktøy.
- Hold bildemappa utenfor git. Skjermbilder kan inneholde ting som ikke skal deles.
- Lekker tokenet: si fra til Max, som lager et nytt i Discord Developer Portal. Da må alle kjøre `discord setup` på nytt.

## Utvikling

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"   # Windows: .venv\Scripts\pip
.venv/bin/python -m pytest -q
```

Lisens: MIT.
