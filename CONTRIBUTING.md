# Contributing to TrackFlow

Thanks for your interest in improving TrackFlow! This guide covers how to set up
a development environment and submit changes.

## Development setup

```bash
git clone https://github.com/murodovdev/Spotify.git trackflow
cd trackflow

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then set BOT_TOKEN
python -m bot.main
```

You'll need [FFmpeg](https://ffmpeg.org/) on your `PATH` and a Telegram bot token
from [@BotFather](https://t.me/BotFather). Spotify credentials are optional — the
bot runs in embed mode without them.

## Project layout

The application lives in the `bot/` package:

- `handlers/` — Telegram update handlers (one router per feature area).
- `services/` — core logic (Spotify client, search, downloads, recognition, …).
- `db/` — SQLite data access.
- `admin/` — admin control panel.
- `web/` — OAuth callback and health endpoint.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a walkthrough.

## Coding style

- Target **Python 3.12** and keep the code fully `async` where I/O is involved.
- Follow the existing style; [Ruff](https://docs.astral.sh/ruff/) config lives in
  `pyproject.toml`. Before opening a PR:

  ```bash
  pip install ruff
  ruff check .
  ruff format .
  ```

- Match the conventions of surrounding code (naming, structure, comment density).
- Keep handlers thin; put reusable logic in `services/`.

## Pull requests

1. Fork the repository and create a feature branch.
2. Keep changes focused — one logical change per PR.
3. Describe **what** changed and **why** in the PR description.
4. Make sure the bot starts (`python -m bot.main`) and `ruff check .` passes.

## Reporting issues

When filing a bug, include:

- What you did and what you expected to happen.
- Relevant log output (redact tokens and cookies).
- Your environment (local vs. Railway, Python version).

Please **never** paste secrets — bot tokens, Spotify secrets, or cookies — into
issues or pull requests.
