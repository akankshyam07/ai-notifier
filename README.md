# AI Daily Popup Notifier

A small macOS desktop popup that shows either a fresh AI news item or a bite-sized AI concept. It uses RSS feeds first, falls back to a concept lesson when nothing fresh is available, and presents the result in a pastel kawaii-style popup with a soft sound and smooth fade animation.

## Prerequisites

- macOS
- Python 3.9+
- pip
- Python with `tkinter` support

Check tkinter:

```bash
python3 -m tkinter
```

## Install

From this folder:

```bash
python3 -m pip install google-genai feedparser pyyaml python-dotenv
```

## Gemini API Key

1. Go to <https://aistudio.google.com/app/apikey>.
2. Create a free Gemini API key.
3. Copy the env template:

```bash
cp .env.example .env
```

4. Edit `.env` in the project folder and replace `your_key_here`:

```bash
GEMINI_API_KEY=your_real_key
```

## Test Run

```bash
python3 notifier.py
```

If Gemini is not configured or fails, the app still shows a popup using the raw RSS title or concept name.

## Scheduling With launchd

`launchd` is preferred over cron for this app because it shows a GUI popup in the active macOS user session more reliably.

Create `~/Library/LaunchAgents/com.ai-news.notifier.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.ai-news.notifier</string>

  <key>ProgramArguments</key>
  <array>
    <string>/path/to/python3</string>
    <string>/path/to/ai-notifier/notifier.py</string>
  </array>

  <key>StartInterval</key>
  <integer>600</integer>

  <key>RunAtLoad</key>
  <true/>

  <key>StandardOutPath</key>
  <string>/tmp/ai-news-notifier.out.log</string>

  <key>StandardErrorPath</key>
  <string>/tmp/ai-news-notifier.err.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.ai-news.notifier.plist
```

Unload it:

```bash
launchctl unload ~/Library/LaunchAgents/com.ai-news.notifier.plist
```

## Optional Cron Fallback

Cron may not reliably show GUI windows. If you still want to try it:

```bash
crontab -e
```

Add:

```bash
*/10 * * * * /path/to/python3 /path/to/ai-notifier/notifier.py
```

## Change The Interval

Update both places:

- `cron_minutes` in `config.yaml`
- your scheduler interval:
  - launchd `StartInterval` is seconds, so 10 minutes is `600`
  - cron uses `*/10`

## Customize Concepts

Edit the `concepts` list in `config.yaml`.

The order matters: the app walks through the list from top to bottom.

## Popup Behavior

The popup stays open until you click `close` or `okay`.

If another scheduled run happens while a popup is already open, the current popup shows a small “new note waiting” message. After you click a button, the next note opens immediately.

To disable the sound, edit `config.yaml`:

```yaml
play_sound: false
```

To use a different macOS system sound, change `sound_path`. Available sounds are in:

```bash
/System/Library/Sounds
```

To change the tone, edit:

```yaml
tone: cute
```

To change colors, choose a built-in theme:

```yaml
theme: bubblegum
```

Theme options are `random`, `bubblegum`, `sky`, `lavender`, and `matcha`. For full control, uncomment `custom_theme` in `config.yaml` and edit the hex colors.

## Reset Concept Progress

Either delete `progress.txt` or set it to:

```txt
0
```

## State Files

The app creates these automatically:

- `seen.txt`: RSS links already shown, trimmed to the latest 200 links
- `progress.txt`: the next concept index
- `pending.txt`: queued popup count if a scheduled run happens while a popup is open
- `.notifier.lock`: prevents overlapping popup windows

## Notes

- The script checks `AppleClamshellState` and exits quietly if the laptop lid is closed.
- The popup fades in, fades out after a button click, and plays the configured subtle sound.
- If a feed fails, the app logs the error and tries the next feed.
- If Gemini fails, the app still shows a popup.
