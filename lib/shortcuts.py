"""The project's kitty shortcuts: defaults, user overrides and kitty's key notation.

Each shortcut is one kitty `map` line. Settings keep only the overrides
(`"shortcuts": {action_id: "ctrl+alt+t"}`); generated/shortcuts.conf is built
from this table by ckt.apply().
"""
from __future__ import annotations

import json
import re
import subprocess
from functools import lru_cache
from typing import NamedTuple


class Action(NamedTuple):
    id: str
    default: str
    kitty_action: str
    label_key: str


_CLAUDE = "sh -c 'exec \"${SHELL:-/bin/bash}\" -ic \"$HOME/.local/bin/claude-panel\"'"

ACTIONS: tuple[Action, ...] = (
    Action("claude_tab", "ctrl+alt+t", f"launch --type=tab --cwd=current {_CLAUDE}", "shortcut.claude_tab"),
    Action("claude_stack", "ctrl+alt+n",
           # "|" separates the combined actions: kitty would also split on the ":" of ${SHELL:-...}
           f"combine | goto_layout stack | launch --type=window --cwd=current {_CLAUDE}", "shortcut.claude_stack"),
    Action("prev_session", "alt+up", "previous_window", "shortcut.prev_session"),
    Action("next_session", "alt+down", "next_window", "shortcut.next_session"),
    Action("toggle_stack", "ctrl+alt+z", "toggle_layout stack", "shortcut.toggle_stack"),
    Action("close_session", "ctrl+alt+w", "kitten close_tab.py window", "shortcut.close_session"),
    Action("close_tab", "ctrl+w", "kitten close_tab.py", "shortcut.close_tab"),
    Action("new_tab", "ctrl+n", "new_tab_with_cwd", "shortcut.new_tab"),
    Action("new_tab_2", "alt+t", "new_tab_with_cwd", "shortcut.new_tab_2"),
    Action("new_tab_3", "ctrl+shift+t", "new_tab_with_cwd", "shortcut.new_tab_3"),
    *(Action(f"tab_{n}", f"alt+{n}", f"goto_tab {n}", f"shortcut.tab_{n}") for n in range(1, 7)),
    Action("prev_tab", "alt+left", "previous_tab", "shortcut.prev_tab"),
    Action("next_tab", "alt+right", "next_tab", "shortcut.next_tab"),
    Action("split_right", "ctrl+shift+enter", "launch --cwd=current --location=vsplit", "shortcut.split_right"),
    Action("split_below", "ctrl+shift+minus", "launch --cwd=current --location=hsplit", "shortcut.split_below"),
    Action("settings", "ctrl+shift+f2", "launch --type=overlay sh -c 'exec \"$HOME/.local/bin/ct-config\"'",
           "shortcut.settings"),
)
BY_ID = {a.id: a for a in ACTIONS}
# Keys handed back to the shell and Claude when "kitty takes Ctrl+W / Ctrl+N" is off.
CTRL_KEYS = ("ctrl+w", "ctrl+n")
# While the menu records a shortcut it pushes this kitty keyboard mode: no
# shortcuts, every key goes to the menu. The odd combo pops it by hand if needed.
CAPTURE_MODE = "ckt-capture"
CAPTURE_ESCAPE = "ctrl+alt+shift+f12"

MODIFIERS = ("ctrl", "alt", "shift", "super")


_VALID_KEYS = re.compile(r"^((ctrl|alt|shift|super)\+)*[a-z0-9_]+$|^((ctrl|alt|shift|super)\+)+[^\s+]$")


def valid_keys(keys: str) -> bool:
    """A combination kitty's map notation can take (letters, names like f2/enter/minus)."""
    return bool(_VALID_KEYS.match(normalize(keys))) if isinstance(keys, str) and keys.strip() else False


def normalize(keys: str) -> str:
    parts = [p.strip().lower() for p in keys.split("+") if p.strip()]
    mods = [m for m in MODIFIERS if m in parts[:-1]]
    return "+".join(mods + parts[-1:])


def keys_for(s: dict) -> dict[str, str]:
    overrides = s.get("shortcuts", {})
    return {a.id: normalize(overrides.get(a.id, a.default)) for a in ACTIONS}


def shortcuts_conf(s: dict) -> str:
    keys = keys_for(s)
    owner: dict[str, str] = {}
    # A user override wins its keys over a default that still sits on them.
    for a in sorted(ACTIONS, key=lambda a: a.id in s.get("shortcuts", {})):
        owner[keys[a.id]] = a.id
    lines = ["# Written by the settings menu (ct config); changes here are overwritten."]
    for a in ACTIONS:
        k = keys[a.id]
        if owner.get(k) != a.id or (not s["kitty_ctrl_keys"] and k in CTRL_KEYS):
            continue
        lines.append(f"map {k} {a.kitty_action}")
    # --timeout: kitty leaves the mode by itself even if the menu never pops it.
    lines.append(f"map --new-mode {CAPTURE_MODE} --on-unknown passthrough --timeout 30 "
                 f"{CAPTURE_ESCAPE} pop_keyboard_mode")
    return "\n".join(lines) + "\n"


def assign(s: dict, action_id: str, keys: str) -> tuple[dict, str | None]:
    """Gives `keys` to the action; the action that had them gets its old keys (a swap)."""
    keys = normalize(keys)
    current = keys_for(s)
    other = next((i for i, k in current.items() if k == keys and i != action_id), None)
    overrides = {i: k for i, k in s.get("shortcuts", {}).items() if i in BY_ID}
    if other:
        overrides[other] = current[action_id]
    overrides[action_id] = keys
    overrides = {i: k for i, k in overrides.items() if k != BY_ID[i].default}
    return dict(s, shortcuts=overrides), other


def reset(s: dict, action_id: str) -> dict:
    """Back to the default keys; whoever holds them now gets this action's keys (a swap)."""
    return assign(s, action_id, BY_ID[action_id].default)[0]


def reset_all(s: dict) -> dict:
    return dict(s, shortcuts={})


# ---------- reading a key press (kitty keyboard protocol) ----------
_TRAILERS = {"A": "up", "B": "down", "C": "right", "D": "left", "H": "home", "F": "end",
             "P": "f1", "Q": "f2", "R": "f3", "S": "f4"}
_TILDE = {2: "insert", 3: "delete", 5: "page_up", 6: "page_down", 15: "f5", 17: "f6", 18: "f7",
          19: "f8", 20: "f9", 21: "f10", 23: "f11", 24: "f12"}
_CODES = {13: "enter", 9: "tab", 27: "escape", 127: "backspace", 32: "space"}
_FUNCTIONAL = {57344: "escape", 57345: "enter", 57346: "tab", 57347: "backspace", 57348: "insert",
               57349: "delete", 57350: "left", 57351: "right", 57352: "up", 57353: "down", 57354: "page_up",
               57355: "page_down", 57356: "home", 57357: "end",
               **{57364 + i: f"f{i + 1}" for i in range(12)}}
_CHAR_NAMES = {"-": "minus", "=": "equal", "+": "plus", ",": "comma", ".": "period", "/": "slash",
               ";": "semicolon", "'": "apostrophe", "[": "left_bracket", "]": "right_bracket",
               "\\": "backslash", "`": "grave_accent"}
_CSI = re.compile(rb"^\x1b\[(\d*)(?::\d*)*(?:;(\d+)(?::\d+)?)?([~uA-DHFPQRS])$")


def _key_name(code: int) -> str | None:
    if code in _CODES:
        return _CODES[code]
    if code in _FUNCTIONAL:
        return _FUNCTIONAL[code]
    if code >= 57344:
        return None  # modifier, lock and other keys that can't be a shortcut on their own
    ch = chr(code).lower()
    return _CHAR_NAMES.get(ch, ch) if ch.isprintable() else None


def _notation(mods: int, key: str) -> str:
    bits = {"shift": 1, "alt": 2, "ctrl": 4, "super": 8}
    return "+".join([m for m in MODIFIERS if mods & bits[m]] + [key])


def from_csi_u(seq: bytes) -> str | None:
    """A key press encoded by kitty's keyboard protocol, in kitty's map notation."""
    m = _CSI.match(seq)
    if not m:
        return None
    number, mods, final = m.group(1), m.group(2), m.group(3).decode()
    mods = int(mods) - 1 if mods else 0
    if final == "u":
        key = _key_name(int(number or 0))
    elif final == "~":
        key = _TILDE.get(int(number or 0))
    else:
        key = _TRAILERS[final]
    return _notation(mods, key) if key else None


# ---------- kitty's own shortcuts ----------
_DEFAULTS_SCRIPT = r"""
import json
from kitty.config import load_config
km = load_config().keyboard_modes[''].keymap
out = {}
for trigger, defs in km.items():
    out.setdefault(f"{trigger.mods}:{trigger.key}", defs[-1].definition)
print(json.dumps(out))
"""


@lru_cache(1)
def _kitty_defaults() -> dict[str, str]:
    try:
        r = subprocess.run(["kitty", "+runpy", _DEFAULTS_SCRIPT], capture_output=True, text=True, timeout=20)
        raw = json.loads(r.stdout.strip().splitlines()[-1])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return {}
    out = {}
    for spec, action in raw.items():
        mods, code = (int(x) for x in spec.split(":"))
        key = _key_name(code)
        if key:
            out[_notation(mods, key)] = action
    return out


def kitty_default_action(keys: str) -> str | None:
    """What kitty itself does with these keys by default, if anything."""
    return _kitty_defaults().get(normalize(keys))
