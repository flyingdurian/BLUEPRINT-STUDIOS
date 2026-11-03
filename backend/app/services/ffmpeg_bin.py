"""Locate the installed FFmpeg tools and run them without a shell."""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys


class MediaToolError(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def _registered_path_entries() -> list[str]:
    if sys.platform != "win32":
        return []
    import winreg

    entries: list[str] = []
    locations = (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    )
    for hive, subkey in locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                raw, _kind = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        entries.extend(str(raw).split(";"))
    return entries


def find_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    filename = f"{name}.exe" if sys.platform == "win32" else name
    for entry in _registered_path_entries():
        candidate = pathlib.Path(os.path.expandvars(entry.strip())) / filename
        if candidate.is_file():
            return str(candidate)
    raise MediaToolError(f"{name} is required. Install FFmpeg and add it to PATH.")


def run_tool(binary: str, args: list[str], *, cwd: pathlib.Path | None = None, timeout: int = 600) -> str:
    completed = subprocess.run(
        [binary, *args], cwd=cwd, check=False, capture_output=True, text=True,
        timeout=timeout, encoding="utf-8", errors="replace",
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "command failed").strip()
        raise MediaToolError(detail[-2000:])
    return completed.stdout
