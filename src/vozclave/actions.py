"""What a command does: open something, close a program, or run a command line."""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import sys

from vozclave.config import Command

log = logging.getLogger(__name__)


def open_target(target: str) -> None:
    """Open a file, folder, URL or app the same way double-clicking it would."""
    if os.name == "nt":
        # Also accepts URIs like spotify: and shell:AppsFolder\<AppID> for Store apps
        os.startfile(target)
    elif sys.platform == "darwin":
        args = (
            ["open", target] if os.path.exists(target) or ":" in target else ["open", "-a", target]
        )
        subprocess.Popen(args)
    elif shutil.which(target):
        subprocess.Popen([target], start_new_session=True)
    else:
        subprocess.Popen(["xdg-open", target])


def _process_name_matches(name: str, target: str) -> bool:
    name, target = name.lower(), target.lower()
    return name == target or name.removesuffix(".exe") == target.removesuffix(".exe")


def close_processes(target: str) -> int:
    """Kill every process whose executable name matches `target` ('Spotify' or 'Spotify.exe')."""
    import psutil

    closed = 0
    for proc in psutil.process_iter(["name"]):
        if _process_name_matches(proc.info["name"] or "", target):
            try:
                proc.kill()
                closed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                log.warning("could not close %s: %s", proc.info["name"], e)
    return closed


def run_command_line(target: str) -> None:
    """Run a command line without a shell, so phrases can never inject extra commands."""
    subprocess.Popen(shlex.split(target, posix=os.name != "nt"))


def execute(command: Command) -> None:
    if command.action == "open":
        open_target(command.target)
    elif command.action == "close":
        count = close_processes(command.target)
        log.info("closed %d process(es) named %s", count, command.target)
    elif command.action == "run":
        run_command_line(command.target)
    else:  # validated in config, kept as a guard
        raise ValueError(f"unknown action {command.action!r}")
