#!/usr/bin/env python3
"""AI news and learning popup notifier."""

from __future__ import annotations

import concurrent.futures
import html
import os
import random
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.request
from pathlib import Path
from typing import Any

import feedparser
import yaml
from dotenv import load_dotenv
from google import genai

try:
    import tkinter as tk
    from tkinter import font as tkfont
except Exception as exc:  # pragma: no cover - only hit on broken local Python installs.
    tk = None
    tkfont = None
    TK_IMPORT_ERROR = exc
else:
    TK_IMPORT_ERROR = None


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.yaml"
ENV_PATH = BASE_DIR / ".env"
SEEN_PATH = BASE_DIR / "seen.txt"
PROGRESS_PATH = BASE_DIR / "progress.txt"
LOCK_PATH = BASE_DIR / ".notifier.lock"
PENDING_PATH = BASE_DIR / "pending.txt"

MAX_SEEN = 200
RSS_TIMEOUT_SECONDS = 3
GEMINI_TIMEOUT_SECONDS = 4

DEFAULT_CONFIG: dict[str, Any] = {
    "cron_minutes": 10,
    "play_sound": True,
    "sound_path": "/System/Library/Sounds/Purr.aiff",
    "tone": "cute",
    "theme": "random",
    "llm": {
        "provider": "gemini",
        "model": "gemini-3.5-flash",
    },
    "rss_feeds": [
        "https://www.technologyreview.com/feed/",
        "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
        "https://venturebeat.com/ai/feed/",
        "https://feeds.arstechnica.com/arstechnica/technology-lab",
    ],
    "concepts": [
        "what is AI",
        "what is machine learning",
        "supervised learning",
        "unsupervised learning",
        "reinforcement learning",
        "training vs inference",
        "datasets",
        "labels",
        "features",
        "overfitting",
        "underfitting",
        "bias in AI",
        "neural networks",
        "neurons",
        "activation functions",
        "weights",
        "layers",
        "deep learning",
        "gradient descent",
        "loss function",
        "backpropagation",
        "learning rate",
        "batch size",
        "epochs",
        "CNNs (convolutional neural networks)",
        "RNNs (recurrent neural networks)",
        "LSTMs",
        "transformers",
        "attention mechanism",
        "self-attention",
        "positional encoding",
        "tokenization",
        "tokens",
        "embeddings",
        "vector space",
        "cosine similarity",
        "context windows",
        "temperature",
        "top-p sampling",
        "softmax",
        "prompt engineering",
        "few-shot learning",
        "zero-shot learning",
        "chain of thought prompting",
        "in-context learning",
        "fine-tuning",
        "RLHF (reinforcement learning from human feedback)",
        "instruction tuning",
        "LoRA (low-rank adaptation)",
        "quantization",
        "RAG (retrieval-augmented generation)",
        "vector databases",
        "semantic search",
        "knowledge graphs",
        "multimodal models",
        "vision-language models",
        "diffusion models",
        "GANs (generative adversarial networks)",
        "VAEs (variational autoencoders)",
        "text-to-image",
        "text-to-speech",
        "speech-to-text",
        "AI agents",
        "tool use",
        "function calling",
        "planning in agents",
        "memory in agents",
        "multi-agent systems",
        "MCP (model context protocol)",
        "model routing",
        "KV cache",
        "latency vs cost tradeoffs",
        "LLM APIs",
        "system prompts",
        "context management",
        "hallucination",
        "grounding",
        "alignment",
        "AI safety",
        "RLAIF (reinforcement learning from AI feedback)",
        "constitutional AI",
        "red teaming",
        "jailbreaking",
        "prompt injection",
        "adversarial attacks",
        "mechanistic interpretability",
        "superposition in neural nets",
        "circuits in neural nets",
        "sparse autoencoders",
        "emergent abilities",
        "scaling laws",
        "compute-optimal training",
        "mixture of experts",
        "speculative decoding",
    ],
}

NEWS_PROMPT = """You are a friendly popup writer.
Rewrite the following AI news headline and summary as a short, warm popup body.
Rules:
- Max 2 sentences
- Max 140 characters
- Match this tone: {tone}
- Lowercase, casual style, like texting a friend
- End with one emoji from: ✨ ♡ ✦ ✿ ˚
- No jargon — if a technical term is needed, define it in parentheses immediately after
- Never start with "i" — start with the subject
Return only the popup body text, nothing else.
"""

CONCEPT_PROMPT = """You are a friendly popup writer teaching AI concepts.
Explain the following AI concept as a short, warm popup body.
Rules:
- Max 2 sentences
- Max 140 characters
- Match this tone: {tone}
- Lowercase, casual style, like texting a friend
- Use a simple analogy to explain it
- End with one emoji from: ✨ ♡ ✦ ✿ ˚
- No jargon — define any technical term in parentheses immediately after
Return only the popup body text, nothing else.
"""

THEMES = [
    {
        "name": "bubblegum",
        "bg": "#fff7fb",
        "bar": "#f78fbe",
        "border": "#c4588b",
        "text": "#b74783",
        "button": "#f5a3cf",
        "button2": "#ffd0e7",
        "accent": "#ffe8f4",
        "light": "#fff5fb",
    },
    {
        "name": "sky",
        "bg": "#f6fbff",
        "bar": "#9dccf3",
        "border": "#5a9ed8",
        "text": "#4f9ed3",
        "button": "#87c4f2",
        "button2": "#bfe2fb",
        "accent": "#e8f5ff",
        "light": "#f6fbff",
    },
    {
        "name": "lavender",
        "bg": "#fffaff",
        "bar": "#e8a6f1",
        "border": "#8c78ba",
        "text": "#7466a9",
        "button": "#d2b4ff",
        "button2": "#b7dcff",
        "accent": "#fae9ff",
        "light": "#fff7ff",
    },
    {
        "name": "matcha",
        "bg": "#fffdf2",
        "bar": "#b9df7b",
        "border": "#7fab46",
        "text": "#705e43",
        "button": "#a9d66e",
        "button2": "#ffe36f",
        "accent": "#eef8d8",
        "light": "#fffdf5",
    },
]


def log(message: str) -> None:
    print(message, file=sys.stderr)


def is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_lock() -> bool:
    while True:
        try:
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                pid = int(LOCK_PATH.read_text(encoding="utf-8").strip())
            except Exception:
                pid = 0
            if pid and is_pid_running(pid):
                return False
            try:
                LOCK_PATH.unlink()
            except FileNotFoundError:
                pass
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
            lock_file.write(f"{os.getpid()}\n")
        return True


def release_lock() -> None:
    try:
        pid = int(LOCK_PATH.read_text(encoding="utf-8").strip())
    except Exception:
        pid = 0
    if pid == os.getpid():
        try:
            LOCK_PATH.unlink()
        except FileNotFoundError:
            pass


def read_pending_count() -> int:
    try:
        return max(0, int(PENDING_PATH.read_text(encoding="utf-8").strip() or "0"))
    except FileNotFoundError:
        return 0
    except ValueError:
        return 0


def write_pending_count(count: int) -> None:
    if count <= 0:
        try:
            PENDING_PATH.unlink()
        except FileNotFoundError:
            pass
        return
    PENDING_PATH.write_text(f"{count}\n", encoding="utf-8")


def increment_pending_count() -> None:
    write_pending_count(read_pending_count() + 1)


def consume_pending_count() -> bool:
    count = read_pending_count()
    if count <= 0:
        return False
    write_pending_count(count - 1)
    return True


def check_lid_open() -> bool:
    command = "ioreg -r -k AppleClamshellState | grep AppleClamshellState"
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception as exc:
        log(f"warning: lid check failed: {exc}")
        return True

    output = result.stdout.strip()
    if "AppleClamshellState" in output and "Yes" in output:
        return False
    return True


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        log("warning: config.yaml missing; using defaults")
        return DEFAULT_CONFIG.copy()

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            loaded = yaml.safe_load(config_file)
        if not isinstance(loaded, dict):
            raise ValueError("config root must be a mapping")
    except Exception as exc:
        log(f"warning: config.yaml could not be loaded; using defaults: {exc}")
        return DEFAULT_CONFIG.copy()

    config = DEFAULT_CONFIG.copy()
    config.update(loaded)
    if not isinstance(config.get("llm"), dict):
        config["llm"] = DEFAULT_CONFIG["llm"]
    else:
        llm_config = DEFAULT_CONFIG["llm"].copy()
        llm_config.update(config["llm"])
        config["llm"] = llm_config
    if not isinstance(config.get("rss_feeds"), list):
        config["rss_feeds"] = DEFAULT_CONFIG["rss_feeds"]
    if not isinstance(config.get("concepts"), list) or not config["concepts"]:
        config["concepts"] = DEFAULT_CONFIG["concepts"]
    return config


def read_seen_links() -> set[str]:
    if not SEEN_PATH.exists():
        SEEN_PATH.write_text("", encoding="utf-8")
        return set()
    return {line.strip() for line in SEEN_PATH.read_text(encoding="utf-8").splitlines() if line.strip()}


def append_seen_link(link: str) -> None:
    links = []
    if SEEN_PATH.exists():
        links = [line.strip() for line in SEEN_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    links.append(link)
    SEEN_PATH.write_text("\n".join(links[-MAX_SEEN:]) + "\n", encoding="utf-8")


def fetch_feed(url: str) -> list[Any]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "ai-news-popup/1.0"})
        with urllib.request.urlopen(request, timeout=RSS_TIMEOUT_SECONDS) as response:
            data = response.read()
        parsed = feedparser.parse(data)
    except Exception as exc:
        log(f"warning: rss fetch failed for {url}: {exc}")
        return []

    if getattr(parsed, "bozo", False):
        log(f"warning: rss parse issue for {url}: {getattr(parsed, 'bozo_exception', 'unknown error')}")
    return list(getattr(parsed, "entries", []))


def entry_timestamp(entry: Any) -> float:
    parsed_time = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed_time:
        try:
            return time.mktime(parsed_time)
        except Exception:
            return 0
    return 0


def choose_fresh_entry(config: dict[str, Any]) -> Any | None:
    seen = read_seen_links()
    entries = []
    feed_urls = [str(url) for url in config.get("rss_feeds", [])]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, max(1, len(feed_urls)))) as executor:
        futures = [executor.submit(fetch_feed, url) for url in feed_urls]
        for future in concurrent.futures.as_completed(futures):
            try:
                entries.extend(future.result())
            except Exception as exc:
                log(f"warning: rss worker failed: {exc}")

    fresh = []
    for entry in entries:
        link = str(getattr(entry, "link", "")).strip()
        if link and link not in seen:
            fresh.append(entry)

    if not fresh:
        return None
    return max(fresh, key=entry_timestamp)


def read_progress() -> int:
    if not PROGRESS_PATH.exists():
        PROGRESS_PATH.write_text("0\n", encoding="utf-8")
        return 0
    try:
        return int(PROGRESS_PATH.read_text(encoding="utf-8").strip() or "0")
    except ValueError:
        log("warning: progress.txt was malformed; resetting to 0")
        PROGRESS_PATH.write_text("0\n", encoding="utf-8")
        return 0


def write_progress(index: int) -> None:
    PROGRESS_PATH.write_text(f"{index}\n", encoding="utf-8")


def next_concept(config: dict[str, Any]) -> tuple[str, int]:
    concepts = [str(concept) for concept in config.get("concepts", []) if str(concept).strip()]
    if not concepts:
        concepts = DEFAULT_CONFIG["concepts"]

    index = read_progress()
    if index >= len(concepts) or index < 0:
        index = 0
        write_progress(index)
    return concepts[index], index


def compact_text(value: str, max_chars: int) -> str:
    cleaned = " ".join(html.unescape(value).split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def generate_with_gemini(config: dict[str, Any], prompt: str, fallback: str) -> str:
    load_dotenv(ENV_PATH)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    model_name = str(config.get("llm", {}).get("model", DEFAULT_CONFIG["llm"]["model"]))

    def call_model() -> str:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model_name, contents=prompt)
        return str(getattr(response, "text", "") or "").strip()

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(call_model)
    try:
        text = future.result(timeout=GEMINI_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise RuntimeError("Gemini call timed out") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if not text:
        raise RuntimeError("Gemini returned an empty response")
    return compact_text(text, 140) or compact_text(fallback, 140)


def rounded_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: Any) -> int:
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def pick_font(root: tk.Tk, size: int, weight: str = "normal") -> tkfont.Font:
    families = set(tkfont.families(root))
    for family in ("Avenir Next Rounded", "Avenir Next", "Arial Rounded MT Bold", "Helvetica Neue", "Arial"):
        if family in families:
            return tkfont.Font(root=root, family=family, size=size, weight=weight)
    return tkfont.Font(root=root, size=size, weight=weight)


def play_popup_sound(sound_path: str | None) -> None:
    if not sound_path:
        return
    afplay = shutil.which("afplay")
    if not afplay:
        log("warning: afplay not found; skipping popup sound")
        return
    if not Path(sound_path).exists():
        log(f"warning: popup sound not found: {sound_path}")
        return
    try:
        subprocess.Popen(
            [afplay, "-v", "0.35", sound_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        log(f"warning: popup sound failed: {exc}")


def select_theme(config: dict[str, Any]) -> dict[str, str]:
    custom_theme = config.get("custom_theme")
    if isinstance(custom_theme, dict):
        theme = THEMES[0].copy()
        theme.update({str(key): str(value) for key, value in custom_theme.items()})
        theme["name"] = "custom"
        return theme

    theme_name = str(config.get("theme", DEFAULT_CONFIG["theme"])).lower()
    if theme_name == "random":
        return random.choice(THEMES)

    for theme in THEMES:
        if theme["name"] == theme_name:
            return theme

    log(f"warning: unknown theme '{theme_name}'; using random theme")
    return random.choice(THEMES)


def show_popup(
    title: str,
    body: str,
    config: dict[str, Any] | str | int | None = None,
    sound_path: str | None = None,
) -> None:
    if tk is None or tkfont is None:
        raise RuntimeError(f"tkinter is unavailable: {TK_IMPORT_ERROR}")

    if isinstance(config, dict):
        popup_config = config
    else:
        popup_config = load_config()
        if isinstance(config, str) and sound_path is None:
            sound_path = config

    theme = select_theme(popup_config)
    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.0)
    root.configure(bg=theme["accent"])

    width = 520
    height = 245
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = max(20, screen_width - width - 42)
    y = max(40, screen_height - height - 92)
    root.geometry(f"{width}x{height}+{x}+{y}")

    canvas = tk.Canvas(root, width=width, height=height, bg=theme["accent"], highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    margin = 13
    card_x1, card_y1 = margin, margin
    card_x2, card_y2 = width - margin, height - 34
    bar_h = 62

    rounded_rect(canvas, card_x1 + 5, card_y1 + 6, card_x2 + 5, card_y2 + 6, 30, fill="#000000", outline="")
    canvas.itemconfigure("all", stipple="")
    rounded_rect(canvas, card_x1, card_y1, card_x2, card_y2, 30, fill=theme["bg"], outline=theme["border"], width=3)
    rounded_rect(canvas, card_x1, card_y1, card_x2, card_y1 + bar_h, 30, fill=theme["bar"], outline=theme["border"], width=3)
    canvas.create_rectangle(card_x1 + 2, card_y1 + 30, card_x2 - 2, card_y1 + bar_h, fill=theme["bar"], outline="")
    canvas.create_line(card_x1 + 2, card_y1 + bar_h, card_x2 - 2, card_y1 + bar_h, fill=theme["border"], width=3)

    title_font = pick_font(root, 19, "bold")
    body_font = pick_font(root, 17, "bold")
    button_font = pick_font(root, 14, "bold")
    pending_font = pick_font(root, 12, "bold")

    canvas.create_text(card_x1 + 130, card_y1 + 32, text=compact_text(title, 42), fill="white", font=title_font, anchor="w")
    rounded_rect(canvas, card_x1 + 32, card_y1 + 24, card_x1 + 78, card_y1 + 39, 8, fill=theme["light"], outline=theme["border"], width=3)
    canvas.create_oval(card_x1 + 88, card_y1 + 23, card_x1 + 105, card_y1 + 40, fill=theme["light"], outline=theme["border"], width=3)
    for idx in range(3):
        cx = card_x2 - 84 + idx * 26
        canvas.create_oval(cx, card_y1 + 25, cx + 12, card_y1 + 37, fill=theme["accent"], outline=theme["border"], width=2)

    canvas.create_line(card_x2 - 135, card_y1 + 88, card_x2 - 52, card_y1 + 88, fill=theme["accent"], width=10, capstyle="round")
    canvas.create_oval(card_x2 - 35, card_y1 + 82, card_x2 - 22, card_y1 + 95, fill=theme["accent"], outline="")

    wrapped = "\n".join(textwrap.wrap(compact_text(body, 140), width=42))
    canvas.create_text(
        width // 2,
        card_y1 + 122,
        text=wrapped,
        fill=theme["text"],
        font=body_font,
        justify="center",
        width=390,
    )

    pending_text = canvas.create_text(
        width // 2,
        card_y2 - 44,
        text="",
        fill=theme["border"],
        font=pending_font,
        justify="center",
    )

    button_y1 = card_y2 - 25
    button_y2 = card_y2 + 18
    close_x1, close_x2 = width // 2 - 135, width // 2 - 18
    ok_x1, ok_x2 = width // 2 + 18, width // 2 + 135

    is_closing = {"value": False}

    def fade_in(step: int = 0) -> None:
        alpha = min(1.0, step / 10)
        root.attributes("-alpha", alpha)
        if alpha < 1.0:
            root.after(18, lambda: fade_in(step + 1))

    def fade_out(step: int = 10) -> None:
        if step <= 0:
            root.destroy()
            return
        root.attributes("-alpha", step / 10)
        root.after(18, lambda: fade_out(step - 1))

    def close_with_animation(_event: Any | None = None) -> None:
        if is_closing["value"]:
            return
        is_closing["value"] = True
        fade_out()

    def update_pending_notice() -> None:
        count = read_pending_count()
        if count == 1:
            canvas.itemconfigure(pending_text, text="new note waiting after this ♡")
        elif count > 1:
            canvas.itemconfigure(pending_text, text=f"{count} new notes waiting after this ♡")
        else:
            canvas.itemconfigure(pending_text, text="")
        if not is_closing["value"]:
            root.after(1000, update_pending_notice)

    for tag, x1, x2, fill, label in (
        ("close_button", close_x1, close_x2, theme["button"], "close"),
        ("ok_button", ok_x1, ok_x2, theme["button2"], "okay"),
    ):
        rounded_rect(canvas, x1, button_y1, x2, button_y2, 20, fill=fill, outline=theme["border"], width=3, tags=(tag,))
        canvas.create_text((x1 + x2) // 2, (button_y1 + button_y2) // 2, text=label.upper(), fill="white" if tag == "close_button" else theme["text"], font=button_font, tags=(tag,))
        canvas.tag_bind(tag, "<Button-1>", close_with_animation)

    root.deiconify()
    root.lift()
    play_popup_sound(sound_path)
    fade_in()
    update_pending_notice()
    root.mainloop()


def build_news_popup(config: dict[str, Any], entry: Any) -> tuple[str, str, str | None]:
    title = "✦ ai corner"
    raw_title = compact_text(str(getattr(entry, "title", "fresh ai news")), 140)
    summary = compact_text(str(getattr(entry, "summary", "")), 500)
    prompt = f"{NEWS_PROMPT.format(tone=config.get('tone', DEFAULT_CONFIG['tone']))}\nheadline: {raw_title}\nsummary: {summary}"
    try:
        body = generate_with_gemini(config, prompt, raw_title)
    except Exception as exc:
        log(f"warning: Gemini rewrite failed for news; using raw title: {exc}")
        body = compact_text(raw_title, 140)
    return title, body, str(getattr(entry, "link", "")).strip() or None


def build_concept_popup(config: dict[str, Any]) -> tuple[str, str, int]:
    concept, index = next_concept(config)
    title = "✿ learn something!"
    prompt = f"{CONCEPT_PROMPT.format(tone=config.get('tone', DEFAULT_CONFIG['tone']))}\nconcept: {concept}"
    try:
        body = generate_with_gemini(config, prompt, concept)
    except Exception as exc:
        log(f"warning: Gemini rewrite failed for concept; using concept name: {exc}")
        body = compact_text(concept, 140)
    return title, body, index


def main() -> int:
    if not check_lid_open():
        return 0

    if not acquire_lock():
        increment_pending_count()
        return 0

    try:
        while True:
            config = load_config()
            sound_path = str(config.get("sound_path", DEFAULT_CONFIG["sound_path"]))
            if not bool(config.get("play_sound", DEFAULT_CONFIG["play_sound"])):
                sound_path = None

            entry = choose_fresh_entry(config)
            seen_link = None
            concept_index = None

            if entry is not None:
                title, body, seen_link = build_news_popup(config, entry)
            else:
                title, body, concept_index = build_concept_popup(config)

            try:
                show_popup(compact_text(title, 80), compact_text(body, 140), config, sound_path)
            except Exception as exc:
                log(f"error: popup display failed: {exc}")
                return 1

            if seen_link:
                append_seen_link(seen_link)
            if concept_index is not None:
                write_progress(concept_index + 1)

            if not consume_pending_count():
                return 0

    finally:
        release_lock()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"error: unexpected failure: {exc}")
        raise SystemExit(1)
