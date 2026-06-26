#!/usr/bin/env python3
"""Uninstaller for AI Daily Popup Notifier."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
PLIST_LABEL = "com.ai-news.notifier"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
STATE_FILES = [
    PROJECT_DIR / ".env",
    PROJECT_DIR / "seen.txt",
    PROJECT_DIR / "progress.txt",
    PROJECT_DIR / "pending.txt",
    PROJECT_DIR / ".notifier.lock",
]


def print_step(message: str) -> None:
    print(f"==> {message}")


def run(command: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, text=True)


def unload_launch_agent() -> None:
    launchctl = shutil.which("launchctl")
    if not launchctl:
        print("warning: launchctl not found; skipping unload")
        return

    gui_target = f"gui/{os.getuid()}"
    print_step("unloading launch agent")
    result = run([launchctl, "bootout", gui_target, str(PLIST_PATH)])
    if result.returncode != 0:
        run([launchctl, "unload", str(PLIST_PATH)])


def remove_plist() -> None:
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
        print_step(f"removed {PLIST_PATH}")
    else:
        print_step("launchd plist was already absent")


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    answer = input(prompt + suffix).strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def remove_state_files() -> None:
    if not ask_yes_no("Remove local .env and state files?", default=False):
        return
    for path in STATE_FILES:
        if path.exists():
            path.unlink()
            print_step(f"removed {path.name}")


def main() -> int:
    unload_launch_agent()
    remove_plist()
    remove_state_files()
    print("uninstalled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
