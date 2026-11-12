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
import unicodedata
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


def _cells(ch: str) -> int:
    """Terminal columns a character takes: 2 for wide ones (CJK, most emoji), 0 for combining marks."""
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def index_at_cell(text: str, x: int) -> int:
    """The index in `text` of the character drawn at terminal column `x`.

    A row's text has one character per character, not per column: wide characters
    take two columns, so the mouse's column must be mapped back."""
    cell = 0
    for i, ch in enumerate(text):
        w = _cells(ch)
        if w and cell <= x < cell + w:
            return i
        cell += w
    return len(text) + (x - cell)


def target_at_cell(line: str, x: int) -> Target | None:
    """target_at() for terminal column `x` (what kitty reports for the mouse)."""
    return target_at(line, index_at_cell(line, x))


# kitty's image placeholder: an image drawn with Unicode placeholders (as Claude Code
# draws the side panel's thumbnails) fills its cells with this character.
IMAGE_PLACEHOLDER = "\U0010eeee"


def _cell_of(text: str, index: int) -> int:
    return sum(_cells(ch) for ch in text[:index])


def image_at_cell(rows: list[str], y: int, x: int) -> Target | None:
    """The [Image #N] whose thumbnail covers row `y`, column `x`.

    The side panel draws each pasted image right under its "[Image #N]" label:
    go up through the image's rows, then read the label on the row above."""
    def on_image(row: str) -> bool:
        i = index_at_cell(row, x)
        return i < len(row) and row[i] == IMAGE_PLACEHOLDER

    if not (0 <= y < len(rows)) or not on_image(rows[y]):
        return None
    top = y
    while top > 0 and on_image(rows[top - 1]):
        top -= 1
    if top == 0:
        return None
    label = rows[top - 1]
    best = None
    for m in _IMAGE.finditer(label):
        if _cell_of(label, m.start()) <= x:
            best = m
    return Target("image", best.group(1)) if best else None


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


_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}


def image_from_transcript(session_id: str, number: str, projects: str | None = None,
                          cache: str | None = None) -> str | None:
    """Takes "[Image #N]" out of the session's own transcript and saves it to the cache.

    For images pasted before the side panel kept copies: the transcript holds each
    pasted image (base64) in the message whose text names it as [Image #N]."""
    import base64
    projects = projects or os.path.expanduser("~/.claude/projects")
    cache = cache or os.path.expanduser("~/.cache/custom-kitty-terminal/images")
    found = glob.glob(os.path.join(projects, "*", f"{glob.escape(session_id)}.jsonl"))
    if not found:
        return None
    tag = f"[Image #{number}]"
    try:
        with open(found[0], encoding="utf-8") as f:
            for line in f:
                if tag not in line or '"image"' not in line:
                    continue
                try:
                    msg = json.loads(line).get("message") or {}
                except ValueError:
                    continue
                content = msg.get("content")
                if msg.get("role") != "user" or not isinstance(content, list):
                    continue
                text = " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
                names = _IMAGE.findall(text)
                images = [c for c in content if isinstance(c, dict) and c.get("type") == "image"]
                # Each pasted image comes in the same order as its [Image #N] in the text.
                pairs = dict(zip(names[-len(images):] if images else [], images))
                src = (pairs.get(number) or {}).get("source") or {}
                if src.get("type") != "base64" or not src.get("data"):
                    continue
                folder = os.path.join(cache, session_id)
                os.makedirs(folder, exist_ok=True)
                out = os.path.join(folder, f"{number}.{_EXT.get(src.get('media_type'), 'img')}")
                with open(out, "wb") as img:
                    img.write(base64.b64decode(src["data"]))
                return out
    except OSError:
        return None
    return None


def panel_files(session_id: str, cache: str | None = None) -> list[str]:
    """Full paths of the files the side panel of that Claude session lists (git and files).

    The panel shows only names ("register.tsx hooks"); it writes the full paths to
    ~/.cache/custom-kitty-terminal/panel/<session>.json so a Ctrl+click on a name finds them."""
    cache = cache or os.path.expanduser("~/.cache/custom-kitty-terminal/panel")
    try:
        with open(os.path.join(cache, f"{session_id}.json")) as f:
            files = json.load(f).get("files", [])
    except (OSError, ValueError, AttributeError):
        return []
    return [x for x in files if isinstance(x, str)]


def match_panel_file(name: str, line: str, files: list[str]) -> str | None:
    """The listed file a clicked name means: same name (or ending in it), the one whose
    folder also shows on that row when several share the name ("index.ts api")."""
    name = name.lstrip("./")
    found = [f for f in files if f == name or f.endswith("/" + name)]
    if len(found) > 1:
        words = set(re.findall(r"[\w.@+-]+", line))
        near = [f for f in found if os.path.basename(os.path.dirname(f)) in words]
        found = near or found
    return found[0] if found else None


def is_image(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_SUFFIXES


def project_root(path: str, run=subprocess.run) -> str | None:
    """The folder of the repository (or worktree) the file is in, as git sees it."""
    folder = path if os.path.isdir(path) else os.path.dirname(path) or "."
    try:
        r = run(["git", "-C", folder, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    top = r.stdout.strip() if r.returncode == 0 else ""
    return top or None


def editor_command(path: str, line: int | None, choice: str, which=shutil.which,
                   env: dict | None = None, root: str | None = None) -> list[str] | None:
    """The command that opens `path` (at `line`) in the chosen editor.

    With `root` (the file's repository), VS Code and Zed open that folder too: the
    window that already has it gets the file and comes forward; otherwise a new
    window opens with the whole project. None means "let the desktop open it"
    (xdg-open / gio). "terminal" gives the terminal editor's command; the caller
    runs it in a kitty window."""
    env = os.environ if env is None else env
    at = f"{path}:{line}" if line else path
    folder = [root] if root else []

    def vscode():
        exe = which("code") or which("codium")
        return [exe, *folder, "-g", at] if exe else None

    def zed():
        exe = which("zed") or which("zeditor")
        return [exe, *folder, at] if exe else None

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
    cmd = editor_command(path, line, choice, root=project_root(path))
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
