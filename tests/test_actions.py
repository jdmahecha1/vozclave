import subprocess
from types import SimpleNamespace

import psutil
import pytest

from vozclave import actions
from vozclave.config import Command


class FakeProc:
    def __init__(self, name, fail=False):
        self.info = {"name": name}
        self.killed = False
        self.fail = fail

    def kill(self):
        if self.fail:
            raise psutil.AccessDenied()
        self.killed = True


@pytest.mark.parametrize(
    "name, target, expected",
    [
        ("Spotify.exe", "spotify", True),
        ("Spotify.exe", "Spotify.exe", True),
        ("spotify", "Spotify.exe", True),
        ("SpotifyHelper.exe", "spotify", False),
        ("notepad.exe", "spotify", False),
    ],
)
def test_process_name_matching(name, target, expected):
    assert actions._process_name_matches(name, target) is expected


def test_close_kills_only_matching_processes(monkeypatch):
    procs = [FakeProc("Spotify.exe"), FakeProc("Spotify.exe"), FakeProc("code.exe")]
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: procs)
    assert actions.close_processes("spotify") == 2
    assert [p.killed for p in procs] == [True, True, False]


def test_close_survives_access_denied(monkeypatch):
    procs = [FakeProc("app.exe", fail=True), FakeProc("app.exe")]
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: procs)
    assert actions.close_processes("app") == 1


def test_run_never_uses_a_shell(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: calls.append((args, kw)))
    actions.run_command_line('notepad "my notes.txt"')
    args, kwargs = calls[0]
    assert isinstance(args, list) and args[0] == "notepad"
    assert "shell" not in kwargs


def test_execute_dispatches(monkeypatch):
    seen = []
    monkeypatch.setattr(actions, "open_target", lambda t: seen.append(("open", t)))
    monkeypatch.setattr(actions, "close_processes", lambda t: seen.append(("close", t)) or 1)
    monkeypatch.setattr(actions, "run_command_line", lambda t: seen.append(("run", t)))
    for action in ("open", "close", "run"):
        actions.execute(Command(action, ("x",), action, f"{action}-target"))
    assert seen == [("open", "open-target"), ("close", "close-target"), ("run", "run-target")]


def test_execute_rejects_unknown_action():
    with pytest.raises(ValueError):
        actions.execute(SimpleNamespace(action="format-disk", target="C:"))
