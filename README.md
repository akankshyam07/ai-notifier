# AI Daily Popup Notifier

A small macOS desktop popup that shows fresh tech/AI news or a bite-sized AI concept. It runs locally on your Mac, uses your own Gemini API key, and shows pastel kawaii-style popups with optional sound.

## Cost Model

This project has no hosted backend, database, or paid server. Each user runs it locally and provides their own Gemini API key.

Possible costs are only:

- Gemini usage if you exceed Google's free allowance
- an optional custom domain later, if you build a website around it

## Requirements

- macOS
- Python 3.10+
- `pip`
- Python with `tkinter` support

Check tkinter:

```bash
python3 -m tkinter
```

## Install

First create a Gemini API key at:

```text
https://aistudio.google.com/app/apikey
```

Then install:

```bash
git clone https://github.com/akankshyam07/ai-notifier.git
cd ai-notifier
python3 install.py
```

The installer will:

- create a local `.venv`
- install Python dependencies
- ask for your Gemini API key without echoing it
- write `.env`
- create and load a `launchd` job
- show a test popup

After install, macOS runs the notifier on the interval in `config.yaml`.

## Uninstall

```bash
python3 uninstall.py
```

The uninstaller unloads the `launchd` job and removes the plist. It asks before deleting local state like `.env`, `seen.txt`, and `progress.txt`.

## Manual Test Commands

Show a popup without RSS or Gemini:

```bash
.venv/bin/python notifier.py --test-popup
```

Force a concept popup:

```bash
.venv/bin/python notifier.py --concept-only
```

Force a news popup:

```bash
.venv/bin/python notifier.py --news-only
```

Normal one-off run:

```bash
.venv/bin/python notifier.py
```

## Configuration

Edit `config.yaml`.

Common settings:

```yaml
cron_minutes: 10
play_sound: true
sound_path: /System/Library/Sounds/Purr.aiff
tone: cute
concept_depth: technical
popup_body_max_chars: 220
theme: random
transparent_window: true
```

Theme options:

```yaml
theme: bubblegum
```

Available themes are `random`, `bubblegum`, `sky`, `lavender`, and `matcha`.

To fully customize colors, uncomment `custom_theme` in `config.yaml`.

## State Files

These are local-only and ignored by git:

- `.env`: your Gemini API key
- `.venv/`: local Python environment
- `seen.txt`: RSS links already shown, trimmed to the latest 200
- `progress.txt`: next concept index
- `pending.txt`: queued popup count if a scheduled run happens while one is open
- `.notifier.lock`: prevents overlapping popup windows

## Logs

The launchd job writes logs to:

```bash
/tmp/ai-news-notifier.out.log
/tmp/ai-news-notifier.err.log
```

## Advanced Manual Setup

The installer handles this automatically. Manual setup is only useful for debugging.

Create `~/Library/LaunchAgents/com.ai-news.notifier.plist` with `.venv/bin/python` and the full path to `notifier.py`, then load it:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ai-news.notifier.plist
```

Unload it:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.ai-news.notifier.plist
```

## Notes

- The script checks `AppleClamshellState` and exits quietly if the laptop lid is closed.
- The popup stays open until you click `close` or `okay`.
- If another scheduled run happens while a popup is open, the current popup shows a small "new note waiting" message.
- If Gemini or the network is unavailable, concept popups use local technical fallback explanations.
- RSS HTTPS requests use `certifi` when available to avoid common macOS Python certificate errors.
