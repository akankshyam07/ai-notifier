# Agent Setup Runbook

Use this file when Codex, Claude, or another local coding agent needs to set up this repo for a new person on macOS.

## Goal

Install and verify Tech Daily Popup Notifier: a local macOS `launchd` job that runs `notifier.py` every `cron_minutes`, checks whether the laptop lid is open, then shows a custom tkinter popup with either important technology news or an AI concept.

Technology news is intentionally broad. Relevant items can include AI, chips, cybersecurity, data centers, power grids, acquisitions, IPOs, funding, infrastructure, space, biotech, energy, climate-tech, and other company or technology updates worth knowing.

## Repo Contents

- `notifier.py` - main app, RSS fetcher, Gemini caller, popup UI, lock/pending handling
- `config.yaml` - user settings, RSS feeds, concepts, popup theme
- `.env.example` - template for the user-owned Gemini key
- `requirements.txt` - Python dependencies
- `install.py` - guided macOS installer
- `uninstall.py` - removes the launch agent
- `README.md` - user-facing instructions

Runtime files are intentionally ignored by git:

- `.env`
- `.venv/`
- `seen.txt`
- `progress.txt`
- `pending.txt`
- `.notifier.lock`

Sensitive data rule: the real Gemini key must live only in `.env`. Never print it in logs, paste it into docs, or commit it.

## Prerequisites

Confirm the machine is macOS and has Python with tkinter:

```bash
python3 --version
python3 -m tkinter
```

If `python3 -m tkinter` fails, install a Python build with tkinter support before continuing.

## Fast Setup

From the repo root:

```bash
python3 install.py
```

The installer will:

1. create `.venv`
2. install `google-genai`, `feedparser`, `pyyaml`, and `python-dotenv`
3. prompt for `GEMINI_API_KEY` and write `.env`
4. write `~/Library/LaunchAgents/com.ai-news.notifier.plist`
5. load the launch agent into the active GUI session
6. show a test popup

Use these flags when needed:

```bash
python3 install.py --force-key
python3 install.py --no-load
python3 install.py --no-test-popup
```

## Manual Setup

Only use this if the installer is not appropriate.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env`:

```text
GEMINI_API_KEY=the_user_key_here
```

Run a local popup test:

```bash
.venv/bin/python notifier.py --test-popup
```

## Gemini Key

Have the user create a free Gemini API key at:

```text
https://aistudio.google.com/app/apikey
```

Keep the key only in `.env`. Do not commit `.env`.

## Verification

Run these from the repo root:

```bash
.venv/bin/python -m py_compile notifier.py install.py uninstall.py
.venv/bin/python notifier.py --help
.venv/bin/python notifier.py --test-popup
```

Optional live checks:

```bash
.venv/bin/python notifier.py --concept-only
.venv/bin/python notifier.py --news-only
```

`--concept-only` and `--news-only` may call Gemini and RSS feeds. If Gemini fails, the notifier should still show a fallback body instead of silently dropping the popup.

Expected news fallback shape when Gemini is unavailable:

```text
key: <what happened>. why it matters: <impact or context> ✨
```

## Launchd Commands

The installer writes:

```text
~/Library/LaunchAgents/com.ai-news.notifier.plist
```

Load:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ai-news.notifier.plist
```

Unload:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.ai-news.notifier.plist
```

Fallback for older macOS behavior:

```bash
launchctl load ~/Library/LaunchAgents/com.ai-news.notifier.plist
launchctl unload ~/Library/LaunchAgents/com.ai-news.notifier.plist
```

Logs:

```text
/tmp/ai-news-notifier.out.log
/tmp/ai-news-notifier.err.log
```

## Configuration

Edit `config.yaml`.

Important fields:

- `cron_minutes`: app interval. If changed, rerun `python3 install.py --no-test-popup` so the launchd `StartInterval` also updates.
- `play_sound`: enable or disable popup sound.
- `sound_path`: macOS sound path, for example `/System/Library/Sounds/Purr.aiff`.
- `tone`: passed into the Gemini rewrite prompt.
- `concept_depth`: passed into the concept explanation prompt.
- `popup_body_max_chars`: compact body target.
- `theme`: `random`, `bubblegum`, `sky`, `lavender`, or `matcha`.
- `custom_theme`: optional color overrides.
- `rss_feeds`: feeds to scan for important tech and tech-adjacent headlines.
- `concepts`: ordered learning progression.

Reset concept progress:

```bash
printf "0\n" > progress.txt
```

Clear seen news:

```bash
printf "" > seen.txt
```

## Troubleshooting

If no popup appears from the scheduler, use `launchd`, not cron. GUI popups need the active macOS user session.

If a stale lock blocks popups, check whether the PID in `.notifier.lock` is still running. If it is not running, `notifier.py` should clean it automatically on the next run.

If multiple scheduled runs happen while a popup is open, the app increments `pending.txt` and the current popup shows a "new note waiting" message. After the user closes the popup, the next pending popup is shown.

If RSS fails for one feed, the app logs a warning and continues with other feeds.

If Gemini fails or times out, the app logs a warning and uses a local fallback. This is expected behavior, not a setup failure.

## Uninstall

```bash
python3 uninstall.py
```

The uninstaller removes the launch agent and asks before deleting local `.env` and state files.

## Agent Safety Rules

- Do not commit `.env`, `.env.*`, `.venv`, `seen.txt`, `progress.txt`, `pending.txt`, `.notifier.lock`, logs, or local scheduler output.
- Before handoff, run `git status --short --ignored` and confirm sensitive runtime files are ignored, not tracked.
- Before handoff, run a secret scan such as `rg -n "AIza[0-9A-Za-z_-]{20,}|api[_-]?key\\s*=|secret\\s*=|password\\s*=|BEGIN .*PRIVATE" -S .`.
- Do not replace the custom tkinter popup with macOS Notification Center.
- Keep paths relative to `notifier.py`; launchd may run from another working directory.
- Keep dependencies limited to `google-genai`, `feedparser`, `pyyaml`, `python-dotenv`, and the Python standard library.
- Prefer `launchd` for scheduled GUI popups.
