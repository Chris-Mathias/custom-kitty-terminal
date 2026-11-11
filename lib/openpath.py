"""Opening what a click points at: a file (in the editor, at its line), an image
pasted into Claude ("[Image #3]") or a URL.

Used by kitty's Ctrl+click (kitty/open_under_mouse.py), by bin/ckt-open (which the
side panel and yazi call) and by the tests. Pure functions first, the launching
at the end.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

EDITORS = ("auto", "vscode", "zed", "sublime", "system", "terminal")

# Characters a path or URL may be made of when it is found in a line of text.
_TOKEN_CHARS = re.compile(r"[\w./~@+%=?&#:-]")
_URL = re.compile(r"^(https?|file)://\S+$")
_IMAGE = re.compile(r"\[Image #(\d+)\]")
_PATH_LINE = re.compile(r"^(?P<path>.+?)(?::(?P<line>\d+))?(?::(?P<col>\d+))?$")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".tiff", ".tif", ".avif", ".heic"}


class Target(NamedTuple):
    kind: str            # "path", "image" or "url"
    value: str           # the path as written, the image number or the URL
    line: int | None = None
    col: int | None = None


def target_at(line: str, x: int) -> Target | None:
    """What sits under column `x` of `line`: an [Image #N], a URL or a path-looking word."""
    for m in _IMAGE.finditer(line):
        if m.start() <= x < m.end():
            return Target("image", m.group(1))
    if not (0 <= x < len(line)) or not _TOKEN_CHARS.match(line[x]):
        return None
    start, end = x, x + 1
    while start > 0 and _TOKEN_CHARS.match(line[start - 1]):
        start -= 1
    while end < len(line) and _TOKEN_CHARS.match(line[end]):
        end += 1
    word = line[start:end].strip(".,:;'\"`")
    # "(src/a.rs:3)" or a diff's "a/src/a.rs" are trimmed by the callers' lookups.
    if not word:
        return None
    if _URL.match(word):
        return Target("url", word)
    m = _PATH_LINE.match(word)
    path = m.group("path") if m else word
    if "/" not in path and "." not in path:
        return None  # a plain word, not a file
    num = lambda g: int(m.group(g)) if m and m.group(g) else None  # noqa: E731
    return Target("path", path, num("line"), num("col"))


def resolve(path: str, dirs: list[str]) -> str | None:
    """The existing file `path` names, looked up as written and in each folder of `dirs`."""
    candidates = [path]
    if path.startswith(("a/", "b/")):  # git diff headers
        candidates.append(path[2:])
    for c in candidates:
        c = os.path.expanduser(c)
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
            continue
        for d in dirs:
            if d and os.path.exists(os.path.join(d, c)):
                return os.path.normpath(os.path.join(d, c))
    return None


def image_for(session_id: str, number: str, cache: str | None = None, uid: int | None = None) -> str | None:
    """The file of "[Image #N]" pasted into the Claude session `session_id`.

    The side panel keeps a copy in ~/.cache/custom-kitty-terminal/images/<session>/;
    Claude Code's own copy under /tmp/claude-<uid>/ is the fallback."""
    cache = cache or os.path.expanduser("~/.cache/custom-kitty-terminal/images")
    found = sorted(glob.glob(os.path.join(cache, glob.escape(session_id), f"{number}.*")))
    if found:
        return found[0]
    uid = os.getuid() if uid is None else uid
    found = sorted(glob.glob(f"/tmp/claude-{uid}/*/{glob.escape(session_id)}/images/{number}.*"))
    return found[0] if found else None


def is_image(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_SUFFIXES


def editor_command(path: str, line: int | None, choice: str, which=shutil.which,
                   env: dict | None = None) -> list[str] | None:
    """The command that opens `path` (at `line`) in the chosen editor.

    None means "let the desktop open it" (xdg-open / gio). "terminal" gives the
    terminal editor's command; the caller runs it in a kitty window."""
    env = os.environ if env is None else env
    at = f"{path}:{line}" if line else path

    def vscode():
        exe = which("code") or which("codium")
        return [exe, "-g", at] if exe else None

    def zed():
        exe = which("zed") or which("zeditor")
        return [exe, at] if exe else None

    def sublime():
        exe = which("subl")
        return [exe, at] if exe else None

    def terminal():
        editor = env.get("VISUAL") or env.get("EDITOR") or "nano"
        return [editor, f"+{line}", path] if line else [editor, path]

    pick = {"vscode": vscode, "zed": zed, "sublime": sublime, "terminal": terminal}
    if choice == "system":
        return None
    if choice in pick:
        return pick[choice]()
    for f in (vscode, zed, sublime):  # auto: the first installed graphical editor
        cmd = f()
        if cmd:
            return cmd
    return None


# ---------- launching ----------
def _spawn(cmd: list[str], cwd: str | None = None) -> None:
    subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def desktop_open(path: str) -> None:
    opener = shutil.which("xdg-open") or shutil.which("gio")
    if opener:
        _spawn([opener, "open", path] if opener.endswith("gio") else [opener, path])


def open_target(path: str, line: int | None, choice: str, kitty_socket: str | None = None) -> None:
    """Opens a file: images in the desktop's viewer, the rest in the editor."""
    if is_image(path):
        desktop_open(path)
        return
    cmd = editor_command(path, line, choice)
    if cmd is None:
        desktop_open(path)
    elif choice == "terminal":
        folder = os.path.dirname(path) or None
        if kitty_socket and shutil.which("kitten"):
            _spawn(["kitten", "@", "--to", kitty_socket, "launch", "--type=tab", "--cwd", folder or os.getcwd(), *cmd])
        elif shutil.which("kitty"):
            _spawn(["kitty", "--single-instance", "--session=none", "--directory", folder or os.getcwd(), *cmd])
    else:
        _spawn(cmd)


def claude_session_for(pids: list[int], sessions_dir: str | None = None) -> str | None:
    """The Claude Code session id of the first of `pids` that is a Claude process."""
    sessions_dir = sessions_dir or os.path.expanduser("~/.claude/sessions")
    for pid in pids:
        try:
            with open(os.path.join(sessions_dir, f"{pid}.json")) as f:
                sid = json.load(f).get("sessionId")
            if sid:
                return sid
        except (OSError, ValueError):
            continue
    return None
