# AI Daily Notifier — AGENTS.md

## Project overview

Build a lightweight macOS desktop popup notifier that fires every 10 minutes and delivers either a recent AI news headline or an AI concept explanation — in a warm, kawaii-inspired tone. Completely free to run. Only fires when the laptop lid is open.

The popup does not need to be a native macOS Notification Center notification. It should be a custom pastel, kawaii-style popup window inspired by soft streamer reminder cards: rounded window, colored title bar, small decorative controls, friendly text, and cute `close` / `okay` buttons.

---

## File structure to create

Create these files directly in this current project folder, not inside a nested
`ai-notifier/` directory.

```
notifier.py      # main script and custom popup UI
config.yaml      # user-editable settings, RSS feeds, concepts list
.env.example     # template for GEMINI_API_KEY
README.md        # setup + scheduler instructions
seen.txt         # auto-created on first run
progress.txt     # auto-created on first run
```

---

## notifier.py — full logic

Build the script in this exact order:

### Step 1 — lid check
Run this shell command and parse the output. If `AppleClamshellState = Yes` (lid closed), exit 0 immediately with no notification and no API call.

```bash
ioreg -r -k AppleClamshellState | grep AppleClamshellState
```

### Step 2 — load config
Read `config.yaml` using pyyaml. If file is missing or malformed, fall back to hardcoded defaults (see config.yaml section below) and print a warning to stderr.

### Step 3 — try news fetch
- Parse each RSS feed URL from config using `feedparser`
- Collect all entries across all feeds
- Filter out any whose `.link` is already in `seen.txt`
- If fresh entries exist: pick the most recent one, go to Step 4a
- If no fresh entries: go to Step 4b (concept fallback)

### Step 4a — news popup
- Pass the entry's title + summary to Gemini with this system prompt:
  ```
  You are a friendly kawaii-style popup writer.
  Rewrite the following AI news headline and summary as a short, warm popup body.
  Rules:
  - Max 2 sentences
  - Lowercase, casual tone, like texting a friend
  - End with one emoji from: ✨ ♡ ✦ ✿ ˚
  - No jargon — if a technical term is needed, define it in parentheses immediately after
  - Never start with "i" — start with the subject
  Return only the popup body text, nothing else.
  ```
- Popup title: `✦ ai corner`
- Popup body: Gemini's response
- Append the entry's `.link` to `seen.txt`

### Step 4b — concept popup
- Read `progress.txt` (single integer). If missing, create it with value `0`.
- Get `concepts[index]` from config. If index >= len(concepts), reset to 0 and rewrite progress.txt.
- Pass the concept to Gemini with this system prompt:
  ```
  You are a friendly kawaii-style popup writer teaching AI concepts.
  Explain the following AI concept as a short, warm popup body.
  Rules:
  - Max 2 sentences
  - Lowercase, casual tone, like texting a friend
  - Use a simple analogy to explain it
  - End with one emoji from: ✨ ♡ ✦ ✿ ˚
  - No jargon — define any technical term in parentheses immediately after
  Return only the popup body text, nothing else.
  ```
- Popup title: `✿ learn something!`
- Popup body: Gemini's response
- Write `index + 1` back to `progress.txt`

### Step 5 — show custom popup
Use Python `tkinter` from the standard library to show a custom popup window. Do not use native macOS Notification Center styling.

Popup requirements:
- Pastel kawaii style inspired by the reference image
- Rounded-card feel where practical with tkinter primitives
- Colored title bar
- Small decorative title-bar controls
- Friendly centered body text
- `close` and `okay` buttons
- Stay visible until the user clicks `close` or `okay`
- Smooth fade-in and fade-out transitions
- Calm subtle sound when the popup appears, configurable in `config.yaml`
- Configurable tone and colors through `tone`, `theme`, and optional `custom_theme`
- If another scheduled run happens while a popup is already open, do not open a second window. Mark a pending popup and show a small "new note waiting" message in the current popup, then show the next popup after the user clicks a button.
- Randomly rotate between pastel themes, for example pink, blue, lavender, and green
- Keep popup compact and readable
- Window should stay on top briefly so it is visible

### Step 6 — error handling
- Wrap Gemini API call in try/except. On failure: send the raw RSS title or concept name as the notification body without tone rewriting — never silently drop the notification.
- Wrap RSS fetch in try/except per feed. If one feed fails, skip it and try the next.
- Wrap popup display in try/except. On failure: print error to stderr, exit 1.
- Never crash silently — always log errors to stderr.

---

## config.yaml

```yaml
cron_minutes: 10
play_sound: true
sound_path: /System/Library/Sounds/Purr.aiff
tone: cute
theme: random

# Theme options: random, bubblegum, sky, lavender, matcha.
# Optional custom_theme may override bg, bar, border, text, button,
# button2, accent, and light colors.

llm:
  provider: gemini
  model: gemini-3.5-flash

rss_feeds:
  - https://www.technologyreview.com/feed/
  - https://www.theverge.com/ai-artificial-intelligence/rss/index.xml
  - https://venturebeat.com/ai/feed/
  - https://feeds.arstechnica.com/arstechnica/technology-lab

concepts:
  # beginner — foundations
  - what is AI
  - what is machine learning
  - supervised learning
  - unsupervised learning
  - reinforcement learning
  - training vs inference
  - datasets
  - labels
  - features
  - overfitting
  - underfitting
  - bias in AI
  - neural networks
  - neurons
  - activation functions
  - weights
  - layers
  - deep learning
  - gradient descent
  - loss function
  # intermediate — how models work
  - backpropagation
  - learning rate
  - batch size
  - epochs
  - CNNs (convolutional neural networks)
  - RNNs (recurrent neural networks)
  - LSTMs
  - transformers
  - attention mechanism
  - self-attention
  - positional encoding
  - tokenization
  - tokens
  - embeddings
  - vector space
  - cosine similarity
  - context windows
  - temperature
  - top-p sampling
  - softmax
  # applied — modern AI
  - prompt engineering
  - few-shot learning
  - zero-shot learning
  - chain of thought prompting
  - in-context learning
  - fine-tuning
  - RLHF (reinforcement learning from human feedback)
  - instruction tuning
  - LoRA (low-rank adaptation)
  - quantization
  - RAG (retrieval-augmented generation)
  - vector databases
  - semantic search
  - knowledge graphs
  - multimodal models
  - vision-language models
  - diffusion models
  - GANs (generative adversarial networks)
  - VAEs (variational autoencoders)
  - text-to-image
  - text-to-speech
  - speech-to-text
  # agents & systems
  - AI agents
  - tool use
  - function calling
  - planning in agents
  - memory in agents
  - multi-agent systems
  - MCP (model context protocol)
  - model routing
  - KV cache
  - latency vs cost tradeoffs
  - LLM APIs
  - system prompts
  - context management
  # safety & frontier
  - hallucination
  - grounding
  - alignment
  - AI safety
  - RLAIF (reinforcement learning from AI feedback)
  - constitutional AI
  - red teaming
  - jailbreaking
  - prompt injection
  - adversarial attacks
  - mechanistic interpretability
  - superposition in neural nets
  - circuits in neural nets
  - sparse autoencoders
  - emergent abilities
  - scaling laws
  - compute-optimal training
  - mixture of experts
  - speculative decoding
```

---

## .env.example

```
GEMINI_API_KEY=your_key_here
```

Load with `python-dotenv`. The actual `.env` should never be committed.

---

## Dependencies

Install all with:
```bash
pip install google-genai feedparser pyyaml python-dotenv
```

Use the `google-genai` SDK to call Gemini. Initialize like:
```python
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
response = client.models.generate_content(
    model=config["llm"]["model"],
    contents=prompt,
)
```

---

## README.md — must include

1. Prerequisites (Python 3.9+, pip, tkinter support)
2. Clone + install deps command
3. How to get a free Gemini API key (console.cloud.google.com)
4. Copy `.env.example` to `.env` and fill in key
5. Test run: `python notifier.py`
6. How to schedule it, with `launchd` preferred for GUI popups:
   ```bash
   mkdir -p ~/Library/LaunchAgents
   # create ~/Library/LaunchAgents/com.ai-news.notifier.plist pointing to notifier.py
   launchctl load ~/Library/LaunchAgents/com.ai-news.notifier.plist
   ```
7. Optional cron fallback if launchd is not wanted:
   ```bash
   crontab -e
   # add this line (update path):
   */10 * * * * /path/to/python3 /path/to/ai-notifier/notifier.py
   ```
8. How to change interval: update cron_minutes in config.yaml AND update the scheduler interval
9. How to customize concepts: edit the concepts list in config.yaml — order = progression order
10. How to reset concept progress: delete progress.txt or set it to 0
11. Note: if launched from cron and the popup does not appear, use launchd instead because GUI apps need the active user session

---

## Constraints

- No external libraries beyond the four listed above + stdlib
- No database — only flat files (seen.txt, progress.txt)
- Use a lock file and pending counter so scheduled runs do not create stacked popup windows
- No menu bar icon, no web server
- GUI is allowed only for the lightweight popup window
- Script should target under 5 seconds on a normal run by using network timeouts;
  RSS or Gemini network latency can occasionally exceed this
- seen.txt should not grow unboundedly — trim to last 200 entries max on each write
- All user-facing strings (popup title, body) should be kept compact; body should target under 140 chars

## Implementation notes

- Use paths relative to `notifier.py`, not the shell's current working directory,
  because cron may run from the user's home directory.
- Load `.env` explicitly from the script directory.
- Use short network timeouts for RSS and Gemini calls.
- Parse feed timestamps defensively; not every RSS entry provides the same date fields.
- Prefer `launchd` over cron for the final scheduled setup if cron cannot reliably show GUI windows in the active macOS user session.
