#!/usr/bin/env python3
"""Guided installer for AI Daily Popup Notifier."""

from __future__ import annotations

import argparse
import getpass
import os
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
VENV_DIR = PROJECT_DIR / ".venv"
ENV_PATH = PROJECT_DIR / ".env"
CONFIG_PATH = PROJECT_DIR / "config.yaml"
REQUIREMENTS_PATH = PROJECT_DIR / "requirements.txt"
PLIST_LABEL = "com.ai-news.notifier"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
OUT_LOG = "/tmp/ai-news-notifier.out.log"
ERR_LOG = "/tmp/ai-news-notifier.err.log"


def print_step(message: str) -> None:
    print(f"==> {message}")


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, text=True)


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_macos() -> None:
    if platform.system() != "Darwin":
        fail("this installer currently supports macOS only")


def require_python() -> None:
    if sys.version_info < (3, 10):
        fail("python 3.10+ is required")


def require_command(name: str) -> str:
    path = shutil.which(name)
    if not path:
        fail(f"required command not found: {name}")
    return path


def require_tkinter() -> None:
    try:
        import tkinter  # noqa: F401
    except Exception as exc:
        fail(f"python tkinter support is missing: {exc}")


def load_config() -> dict[str, Any]:
    config: dict[str, Any] = {}
    if not CONFIG_PATH.exists():
        return config

    for raw_line in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() == "cron_minutes":
            config["cron_minutes"] = value.strip()
            break
    return config


def cron_minutes(config: dict[str, Any]) -> int:
    try:
        minutes = int(config.get("cron_minutes", 10))
    except (TypeError, ValueError):
        minutes = 10
    return max(1, minutes)


def venv_python() -> Path:
    return VENV_DIR / "bin" / "python"


def create_venv() -> None:
    if VENV_DIR.exists():
        print_step("using existing .venv")
        return
    print_step("creating .venv")
    run([sys.executable, "-m", "venv", str(VENV_DIR)])


def install_requirements() -> None:
    if not REQUIREMENTS_PATH.exists():
        fail("requirements.txt is missing")
    python_path = venv_python()
    if not python_path.exists():
        fail(f"venv python not found: {python_path}")
    print_step("installing dependencies into .venv")
    run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(python_path), "-m", "pip", "install", "-r", str(REQUIREMENTS_PATH)])


def prompt_gemini_key(force: bool) -> None:
    if ENV_PATH.exists() and not force:
        print_step("using existing .env")
        return

    while True:
        key = getpass.getpass("Gemini API key: ").strip()
        if key:
            break
        print("Gemini API key cannot be empty.")

    ENV_PATH.write_text(f"GEMINI_API_KEY={key}\n", encoding="utf-8")
    os.chmod(ENV_PATH, 0o600)
    print_step("wrote .env")


def plist_data(config: dict[str, Any]) -> dict[str, Any]:
    interval_seconds = cron_minutes(config) * 60
    return {
        "Label": PLIST_LABEL,
        "ProgramArguments": [
            str(venv_python()),
            str(PROJECT_DIR / "notifier.py"),
        ],
        "WorkingDirectory": str(PROJECT_DIR),
        "StartInterval": interval_seconds,
        "RunAtLoad": True,
        "StandardOutPath": OUT_LOG,
        "StandardErrorPath": ERR_LOG,
    }


def write_plist(config: dict[str, Any]) -> None:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PLIST_PATH.open("wb") as plist_file:
        plistlib.dump(plist_data(config), plist_file)
    print_step(f"wrote {PLIST_PATH}")


def unload_existing(launchctl: str) -> None:
    gui_target = f"gui/{os.getuid()}"
    run([launchctl, "bootout", gui_target, str(PLIST_PATH)], check=False)
    run([launchctl, "unload", str(PLIST_PATH)], check=False)


def load_launch_agent(skip_load: bool) -> None:
    if skip_load:
        print_step("skipping launchd load")
        return

    launchctl = require_command("launchctl")
    unload_existing(launchctl)
    gui_target = f"gui/{os.getuid()}"
    print_step("loading launch agent")
    result = run([launchctl, "bootstrap", gui_target, str(PLIST_PATH)], check=False)
    if result.returncode != 0:
        run([launchctl, "load", str(PLIST_PATH)])


def show_test_popup(skip_popup: bool) -> None:
    if skip_popup:
        print_step("skipping test popup")
        return
    print_step("showing test popup")
    run([str(venv_python()), str(PROJECT_DIR / "notifier.py"), "--test-popup"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install AI Daily Popup Notifier.")
    parser.add_argument("--force-key", action="store_true", help="overwrite .env with a newly entered Gemini key")
    parser.add_argument("--no-load", action="store_true", help="write the launchd plist but do not load it")
    parser.add_argument("--no-test-popup", action="store_true", help="skip the test popup after install")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print_step("checking system")
    require_macos()
    require_python()
    require_command("launchctl")
    require_tkinter()
    config = load_config()

    create_venv()
    install_requirements()
    prompt_gemini_key(args.force_key)
    write_plist(config)
    load_launch_agent(args.no_load)
    show_test_popup(args.no_test_popup)

    print("\ninstalled. logs:")
    print(f"  stdout: {OUT_LOG}")
    print(f"  stderr: {ERR_LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
