#!/usr/bin/env python3
"""AI news and learning popup notifier."""

from __future__ import annotations

import concurrent.futures
import argparse
import html
import os
import random
import re
import shutil
import ssl
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
    import certifi
except Exception:  # pragma: no cover - fallback for unusual installs.
    certifi = None

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
RSS_TIMEOUT_SECONDS = 5
GEMINI_TIMEOUT_SECONDS = 12

DEFAULT_CONFIG: dict[str, Any] = {
    "cron_minutes": 10,
    "rss_timeout_seconds": RSS_TIMEOUT_SECONDS,
    "gemini_timeout_seconds": GEMINI_TIMEOUT_SECONDS,
    "play_sound": True,
    "sound_path": "/System/Library/Sounds/Purr.aiff",
    "tone": "cute",
    "concept_depth": "technical",
    "popup_body_max_chars": 220,
    "theme": "random",
    "transparent_window": True,
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
Rewrite the following AI, science, or technology news headline and summary as a short, warm popup body.
Rules:
- Max 2 sentences
- Max {max_chars} characters
- Match this tone: {tone}
- Lowercase, casual style, like texting a friend
- Put the most important company, deadline, number, place, or impact near the start
- Include specific company names, numbers, places, or impacts when they are present
- Write it as one flowing note with what happened and why it matters; do not use labels like "key" or "why it matters"
- If space is tight, summarize harder; do not trail off or end mid-thought
- End with one emoji from: ✨ ♡ ✦ ✿ ˚
- No jargon — if a technical term is needed, define it in parentheses immediately after
- Never start with "i" — start with the subject
Return only the popup body text, nothing else.
"""

CONCEPT_PROMPT = """You are a friendly popup writer teaching AI concepts.
Explain the following AI concept as a short, warm popup body.
Rules:
- Max 2 sentences
- Max {max_chars} characters
- Match this tone: {tone}
- Depth: {concept_depth}
- Be technically correct: say what it does, the core mechanism, and why it matters when possible
- Use one simple analogy, but keep the technical definition first
- Lowercase, casual style, like texting a friend
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

LOCAL_CONCEPT_EXPLANATIONS = {
    "what is ai": "ai is software that performs tasks needing perception, language, or reasoning by learning patterns from data; like a study buddy with lots of notes ✨",
    "what is machine learning": "machine learning trains a model (pattern-finding program) on examples so it can predict new cases; like learning cookies from many cookie photos ✨",
    "supervised learning": "supervised learning trains on inputs plus labels (known answers), then predicts labels for new data; like homework with an answer key ✨",
    "unsupervised learning": "unsupervised learning finds structure without labels, often by clustering similar data; like sorting stickers by hidden patterns ✿",
    "reinforcement learning": "reinforcement learning optimizes actions using rewards and penalties from an environment; like learning a game by scoring each move ✨",
    "training vs inference": "training adjusts model weights (learned settings) from data; inference uses those weights to answer new inputs, like practice vs game day ✦",
    "datasets": "a dataset is the examples a model learns from or is tested on; quality and coverage matter, like ingredients deciding a recipe ✨",
    "labels": "labels are target answers attached to examples, such as 'spam' or 'not spam'; they guide supervised learning like answer tags ♡",
    "features": "features are measurable input signals a model uses, like word counts or pixels; they are the clues behind a prediction ✨",
    "overfitting": "overfitting means a model memorizes training data instead of generalizing to new data; like acing practice questions only ✿",
    "underfitting": "underfitting means a model is too simple to capture the real pattern; like using one rule for every problem ✦",
    "bias in ai": "bias is systematic error from skewed data or design choices, causing unfair or wrong outputs; like a tilted measuring scale ♡",
    "neural networks": "a neural network stacks layers of learned weights to transform inputs into predictions; like filters passing signals step by step ✨",
    "tokens": "tokens are chunks of text a language model processes, often words or word pieces; they are the model's puzzle pieces ✦",
    "embeddings": "embeddings map words or items into numeric vectors (lists of numbers) so similar meanings sit nearby; like a meaning map ✨",
    "context windows": "a context window is the maximum tokens a model can read at once; it limits memory for the current request, like desk space ♡",
    "prompt engineering": "prompt engineering shapes instructions and examples so a model gives better outputs; like writing a clear spec for a teammate ✨",
    "fine-tuning": "fine-tuning continues training a model on task-specific data to shift its behavior; like tutoring after general school ✿",
    "rag (retrieval-augmented generation)": "rag retrieves relevant documents before generation so answers can use external facts; like checking notes before replying ✨",
    "ai agents": "ai agents combine a model with planning, memory, and tool use to complete multi-step tasks; like a tiny workflow operator ✦",
    "hallucination": "a hallucination is a fluent but unsupported model output, often caused by guessing beyond evidence; confident wording needs checking ♡",
}


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


def ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def fetch_feed(url: str, timeout: int = RSS_TIMEOUT_SECONDS) -> list[Any]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "ai-news-popup/1.0"})
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context()) as response:
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


_TECH_NEWS_KEYWORDS = {
    "ai",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "neural",
    "llm",
    "large language model",
    "language model",
    "foundation model",
    "generative ai",
    "gpt",
    "chatgpt",
    "openai",
    "anthropic",
    "deepmind",
    "google deepmind",
    "gemini",
    "claude",
    "mistral",
    "meta ai",
    "copilot",
    "robot",
    "robotics",
    "autonomous vehicle",
    "autonomous driving",
    "ai agent",
    "agentic",
    "prompt",
    "inference",
    "model training",
    "training data",
    "synthetic data",
    "rag",
    "retrieval-augmented",
    "benchmark",
    "gpu cluster",
    "ai chip",
    "ai accelerator",
    "nvidia ai",
    "nvidia",
    "chip",
    "semiconductor",
    "gpu",
    "cpu",
    "quantum",
    "cybersecurity",
    "security",
    "privacy",
    "hack",
    "breach",
    "vulnerability",
    "encryption",
    "crypto",
    "cloud",
    "server",
    "software",
    "api",
    "open source",
    "startup",
    "funding",
    "vc",
    "regulation",
    "antitrust",
    "processor",
    "compute",
    "data center",
    "datacenter",
    "data centers",
    "datacenters",
    "power plant",
    "power plants",
    "power grid",
    "grid",
    "electricity",
    "energy",
    "heat",
    "extreme heat",
    "water use",
    "water usage",
    "cooling",
    "supply chain",
    "infrastructure",
    "acquired",
    "acquires",
    "acquisition",
    "merger",
    "takeover",
    "ipo",
    "layoffs",
    "bankruptcy",
    "partnership",
    "backs",
    "backing",
    "robot",
    "robotics",
    "space",
    "satellite",
    "battery",
    "energy storage",
    "nuclear",
    "climate tech",
    "electric vehicle",
    "ev",
    "biotech",
    "gene editing",
}

_NOISE_KEYWORDS = {
    "deal", "deals", "discount", "sale", "coupon", "prime day", "amazon prime",
    "shopping", "price drop", "save money", "buy now", "best buy", "black friday",
    "cyber monday", "promo", "offer", "rebate", "clearance",
}


def _entry_is_relevant(entry: Any) -> bool:
    text = (str(getattr(entry, "title", "")) + " " + str(getattr(entry, "summary", ""))).lower()
    if any(kw in text for kw in _NOISE_KEYWORDS):
        return False
    return any(re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", text) for kw in _TECH_NEWS_KEYWORDS)


def choose_fresh_entry(config: dict[str, Any]) -> Any | None:
    seen = read_seen_links()
    entries = []
    feed_urls = [str(url) for url in config.get("rss_feeds", [])]
    timeout = int(config.get("rss_timeout_seconds", RSS_TIMEOUT_SECONDS))
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, max(1, len(feed_urls)))) as executor:
        futures = [executor.submit(fetch_feed, url, timeout) for url in feed_urls]
        for future in concurrent.futures.as_completed(futures):
            try:
                entries.extend(future.result())
            except Exception as exc:
                log(f"warning: rss worker failed: {exc}")

    fresh = []
    for entry in entries:
        link = str(getattr(entry, "link", "")).strip()
        if link and link not in seen and _entry_is_relevant(entry):
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
    cleaned = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(value)).split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def clip_at_word(value: str, max_chars: int) -> str:
    cleaned = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(value)).split())
    if len(cleaned) <= max_chars:
        return trim_dangling_words(cleaned)
    if max_chars <= 0:
        return ""
    clipped = cleaned[:max_chars].rsplit(" ", 1)[0].strip(" ,;:-")
    return trim_dangling_words(clipped or cleaned[:max_chars].strip(" ,;:-"))


def trim_dangling_words(value: str) -> str:
    dangling = {
        "a",
        "an",
        "and",
        "as",
        "at",
        "but",
        "by",
        "for",
        "from",
        "in",
        "meaning",
        "could",
        "would",
        "should",
        "can",
        "may",
        "might",
        "will",
        "of",
        "on",
        "or",
        "so",
        "the",
        "to",
        "while",
        "with",
    }
    words = value.split()
    while words and words[-1].lower().strip(".,;:!?") in dangling:
        words.pop()
    return " ".join(words).strip(" ,;:-")


def first_summary_sentence(summary: str, title: str) -> str:
    cleaned = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(summary)).split())
    if not cleaned:
        return ""
    title_words = set(re.findall(r"[a-z0-9]+", title.lower()))
    for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
        sentence = sentence.strip()
        if len(sentence) < 24:
            continue
        sentence_words = set(re.findall(r"[a-z0-9]+", sentence.lower()))
        if title_words and len(title_words & sentence_words) / max(1, len(title_words)) > 0.8:
            continue
        return sentence
    return cleaned


def smooth_news_text(value: str) -> str:
    cleaned = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(value)).split())
    replacements = {
        "has drastically shortened the deadline for federal agencies to stop using": "moved up the deadline for agencies to replace",
        "drastically shortened the deadline for federal agencies to stop using": "moved up the deadline for agencies to replace",
        "quantum-vulnerable cryptography": "quantum-vulnerable encryption",
        "security teams have less time to replace encryption that future quantum computers could break": "security teams have less time to protect encryption before future quantum computers can break it",
        ", meaning ": ", so ",
        "; meaning ": ", so ",
        " meaning ": " so ",
        " in order to ": " to ",
        " due to the fact that ": " because ",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    return cleaned


def config_int(config: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(config.get(key, default))
    except (TypeError, ValueError):
        return default


def local_concept_fallback(concept: str, max_chars: int) -> str:
    normalized = concept.strip().lower()
    if normalized in LOCAL_CONCEPT_EXPLANATIONS:
        return compact_text(LOCAL_CONCEPT_EXPLANATIONS[normalized], max_chars)
    short_concept = compact_text(concept, 54)
    return compact_text(
        f"{short_concept} is an ai technique that helps models represent data, retrieve facts, or make decisions; like a labeled tool in a kit ✨",
        max_chars,
    )


def local_news_fallback(title: str, max_chars: int, summary: str = "") -> str:
    clean_title = clip_at_word(title, 120)
    clean_summary = smooth_news_text(first_summary_sentence(summary, clean_title))
    if not clean_summary:
        return f"{clip_at_word(clean_title, max_chars - 3)} ✨"

    suffix = " ✨"
    body_budget = max_chars - len(suffix)
    title_words = set(re.findall(r"[a-z0-9]+", clean_title.lower()))
    summary_words = set(re.findall(r"[a-z0-9]+", clean_summary.lower()))
    overlap = len(title_words & summary_words) / max(1, len(title_words))

    if overlap >= 0.5:
        return f"{clip_at_word(clean_summary, body_budget)}{suffix}"

    combined = f"{clean_title}. {clean_summary}"
    return f"{clip_at_word(combined, body_budget)}{suffix}"


def generate_with_gemini(config: dict[str, Any], prompt: str, fallback: str, max_chars: int) -> str:
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
    timeout = config_int(config, "gemini_timeout_seconds", GEMINI_TIMEOUT_SECONDS)
    try:
        text = future.result(timeout=timeout)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise RuntimeError("Gemini call timed out") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if not text:
        raise RuntimeError("Gemini returned an empty response")
    return clip_at_word(text, max_chars) or clip_at_word(fallback, max_chars)


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


def apply_transparent_background(root: tk.Tk, canvas: tk.Canvas, config: dict[str, Any], fallback_bg: str) -> None:
    if not bool(config.get("transparent_window", DEFAULT_CONFIG["transparent_window"])):
        root.configure(bg=fallback_bg)
        canvas.configure(bg=fallback_bg)
        return

    for setter in (
        lambda: root.configure(bg="systemTransparent"),
        lambda: canvas.configure(bg="systemTransparent"),
        lambda: root.attributes("-transparent", True),
    ):
        try:
            setter()
        except Exception as exc:
            log(f"warning: transparent popup background option failed: {exc}")


def show_popup(
    title: str,
    body: str,
    config: dict[str, Any] | str | int | None = None,
    sound_path: str | None = None,
    link: str | None = None,
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

    width = 560
    height = 285
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = max(20, screen_width - width - 42)
    y = max(40, screen_height - height - 92)
    root.geometry(f"{width}x{height}+{x}+{y}")

    canvas = tk.Canvas(root, width=width, height=height, bg=theme["accent"], highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    apply_transparent_background(root, canvas, popup_config, theme["accent"])

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
    body_font = pick_font(root, 15, "bold")
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

    max_chars = config_int(popup_config, "popup_body_max_chars", DEFAULT_CONFIG["popup_body_max_chars"])
    wrapped = "\n".join(textwrap.wrap(compact_text(body, max_chars), width=48))
    canvas.create_text(
        width // 2,
        card_y1 + 136,
        text=wrapped,
        fill=theme["text"],
        font=body_font,
        justify="center",
        width=450,
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

    def open_link_and_close(_event: Any | None = None) -> None:
        if link:
            try:
                subprocess.Popen(["open", link])
            except Exception as exc:
                log(f"warning: could not open link: {exc}")
        close_with_animation()

    right_label = "learn more" if link else "okay"
    right_handler = open_link_and_close if link else close_with_animation

    for tag, x1, x2, fill, label, handler in (
        ("close_button", close_x1, close_x2, theme["button"], "close", close_with_animation),
        ("ok_button", ok_x1, ok_x2, theme["button2"], right_label, right_handler),
    ):
        rounded_rect(canvas, x1, button_y1, x2, button_y2, 20, fill=fill, outline=theme["border"], width=3, tags=(tag,))
        canvas.create_text((x1 + x2) // 2, (button_y1 + button_y2) // 2, text=label.upper(), fill="white" if tag == "close_button" else theme["text"], font=button_font, tags=(tag,))
        canvas.tag_bind(tag, "<Button-1>", handler)

    root.deiconify()
    root.lift()
    play_popup_sound(sound_path)
    fade_in()
    update_pending_notice()
    root.mainloop()


def build_news_popup(config: dict[str, Any], entry: Any) -> tuple[str, str, str | None]:
    title = "✦ tech corner"
    max_chars = config_int(config, "popup_body_max_chars", DEFAULT_CONFIG["popup_body_max_chars"])
    raw_title = compact_text(str(getattr(entry, "title", "fresh tech news")), max_chars)
    summary = compact_text(str(getattr(entry, "summary", "")), 500)
    prompt = (
        f"{NEWS_PROMPT.format(tone=config.get('tone', DEFAULT_CONFIG['tone']), max_chars=max_chars)}"
        f"\nheadline: {raw_title}\nsummary: {summary}"
    )
    try:
        body = generate_with_gemini(config, prompt, raw_title, max_chars)
    except Exception as exc:
        log(f"warning: Gemini rewrite failed for news; using raw title: {exc}")
        body = local_news_fallback(raw_title, max_chars, summary)
    return title, body, str(getattr(entry, "link", "")).strip() or None


def build_concept_popup(config: dict[str, Any]) -> tuple[str, str, int]:
    concept, index = next_concept(config)
    title = "✿ learn something!"
    max_chars = config_int(config, "popup_body_max_chars", DEFAULT_CONFIG["popup_body_max_chars"])
    prompt = (
        f"{CONCEPT_PROMPT.format(tone=config.get('tone', DEFAULT_CONFIG['tone']), concept_depth=config.get('concept_depth', DEFAULT_CONFIG['concept_depth']), max_chars=max_chars)}"
        f"\nconcept: {concept}"
    )
    try:
        body = generate_with_gemini(config, prompt, concept, max_chars)
    except Exception as exc:
        log(f"warning: Gemini rewrite failed for concept; using local explanation: {exc}")
        body = local_concept_fallback(concept, max_chars)
    return title, body, index


def sound_path_for_config(config: dict[str, Any]) -> str | None:
    if not bool(config.get("play_sound", DEFAULT_CONFIG["play_sound"])):
        return None
    return str(config.get("sound_path", DEFAULT_CONFIG["sound_path"]))


def build_popup_for_mode(config: dict[str, Any], mode: str) -> tuple[str, str, str | None, int | None]:
    seen_link = None
    concept_index = None

    if mode == "concept":
        title, body, concept_index = build_concept_popup(config)
        return title, body, seen_link, concept_index

    entry = choose_fresh_entry(config)
    if entry is not None:
        title, body, seen_link = build_news_popup(config, entry)
        return title, body, seen_link, concept_index

    if mode == "news":
        max_chars = config_int(config, "popup_body_max_chars", DEFAULT_CONFIG["popup_body_max_chars"])
        return "✦ ai corner", compact_text("no fresh tech or ai news right now; try again soon ✨", max_chars), None, None

    title, body, concept_index = build_concept_popup(config)
    return title, body, seen_link, concept_index


def show_built_popup(config: dict[str, Any], title: str, body: str, link: str | None = None) -> int:
    try:
        max_chars = config_int(config, "popup_body_max_chars", DEFAULT_CONFIG["popup_body_max_chars"])
        show_popup(compact_text(title, 80), compact_text(body, max_chars), config, sound_path_for_config(config), link)
    except Exception as exc:
        log(f"error: popup display failed: {exc}")
        return 1
    return 0


def run_notifier(mode: str = "normal") -> int:
    if not check_lid_open():
        return 0

    if not acquire_lock():
        increment_pending_count()
        return 0

    try:
        while True:
            config = load_config()
            title, body, seen_link, concept_index = build_popup_for_mode(config, mode)
            result = show_built_popup(config, title, body, seen_link)
            if result:
                return result

            if seen_link:
                append_seen_link(seen_link)
            if concept_index is not None:
                write_progress(concept_index + 1)

            if not consume_pending_count():
                return 0
            mode = "normal"

    finally:
        release_lock()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show AI news and learning popups.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--test-popup", action="store_true", help="show a test popup without RSS or Gemini")
    group.add_argument("--concept-only", action="store_true", help="force concept mode for this run")
    group.add_argument("--news-only", action="store_true", help="force news mode for this run")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config()

    if args.test_popup:
        return show_built_popup(
            config,
            "✦ ai corner",
            "installer test: your soft little ai popup is working ✨",
        )
    if args.concept_only:
        return run_notifier("concept")
    if args.news_only:
        return run_notifier("news")
    return run_notifier("normal")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"error: unexpected failure: {exc}")
        raise SystemExit(1)
