"""Settings, translations and themes shared by every part of custom-kitty-terminal.

User choices live in ~/.config/custom-kitty-terminal/settings.json (override the
folder with CKT_CONFIG_DIR). Translations are i18n/<lang>.json and themes are
themes/<id>/ in this repository.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LANGUAGES = ("en", "pt")
THEMES = ("fedora", "catppuccin", "tokyo-night", "dracula", "gruvbox", "light", "noctalia")
FONT_SIZES = range(8, 25)
PANEL_SECTIONS = ("sessions", "agents", "tasks", "git", "files")
STATUS_ITEMS = ("context", "five_hour", "weekly", "resets", "model", "worktree")

# Every scalar setting and the values it may take (the first tuple entries are
# not the defaults; DEFAULTS below is).
CHOICES = {
    "language": LANGUAGES,
    "theme": THEMES,
    "font_size": tuple(FONT_SIZES),
    "line_height": tuple(range(100, 131, 5)),
    "padding": ("compact", "normal", "roomy"),
    "tab_style": ("slanted", "round", "angled", "separators"),
    "tab_position": ("top", "bottom"),
    "opacity": tuple(range(70, 101, 5)),
    "cursor_shape": ("block", "beam", "underline"),
    "cursor_blink": (True, False),
    "title_bar": ("system", "kitty", "none"),
    "ligatures": (True, False),
    "spinner": ("ours", "claude"),
    "subagent_rows": (True, False),
    "reopen_tabs": (True, False),
    "confirm_close": ("running", "always", "never"),
    "kitty_ctrl_keys": (True, False),
    "scrollback": (5000, 10000, 20000, 50000, 100000),
    "bell": (False, True),
    "tab_close_buttons": (False, True),
    "panel_close_buttons": (False, True),
}
RESPONSE_LENGTHS = ("short", "balanced", "detailed")

DEFAULTS = {
    "language": "en", "theme": "fedora", "font_family": "Adwaita Mono", "font_size": 12,
    "line_height": 115, "padding": "normal", "tab_style": "slanted", "tab_position": "top",
    "opacity": 100, "cursor_shape": "block", "cursor_blink": True, "title_bar": "system", "ligatures": True,
    "response_style": {"enabled": False, "language": "pt", "length": "short", "previous": None},
    "spinner": "ours",
    "subagent_rows": True,
    "status_line": {k: True for k in STATUS_ITEMS},
    "panel": {"sections": list(PANEL_SECTIONS), "auto_open": True},
    "reopen_tabs": True, "confirm_close": "running", "kitty_ctrl_keys": True, "scrollback": 20000, "bell": False,
    "tab_close_buttons": False, "panel_close_buttons": False,
    "shortcuts": {},
}


def config_dir() -> Path:
    return Path(os.environ.get("CKT_CONFIG_DIR") or Path.home() / ".config/custom-kitty-terminal")


def settings_path() -> Path:
    return config_dir() / "settings.json"


def _same_type(value, default) -> bool:
    # bool is an int in Python: keep True/False and numbers apart.
    return type(value) is type(default)


def _scalar(key: str, value):
    default = DEFAULTS[key]
    if key == "title_bar" and value == "gnome":
        value = "system"  # older settings files
    if key == "font_family":
        return value if isinstance(value, str) and value.strip() else default
    if _same_type(value, default) and value in CHOICES[key]:
        return value
    return default


def _nested(key: str, value):
    default = DEFAULTS[key]
    value = value if isinstance(value, dict) else {}
    if key == "status_line":
        return {k: value[k] if isinstance(value.get(k), bool) else True for k in STATUS_ITEMS}
    if key == "panel":
        sections = value.get("sections")
        if isinstance(sections, list):
            seen = []
            for name in sections:
                if name in PANEL_SECTIONS and name not in seen:
                    seen.append(name)
        else:
            seen = list(PANEL_SECTIONS)
        auto = value.get("auto_open")
        return {"sections": seen, "auto_open": auto if isinstance(auto, bool) else True}
    if key == "response_style":
        rs = dict(default)
        if isinstance(value.get("enabled"), bool):
            rs["enabled"] = value["enabled"]
        if value.get("language") in LANGUAGES:
            rs["language"] = value["language"]
        if value.get("length") in RESPONSE_LENGTHS:
            rs["length"] = value["length"]
        if isinstance(value.get("previous"), str):
            rs["previous"] = value["previous"]
        return rs
    if key == "shortcuts":
        import shortcuts
        return {k: shortcuts.normalize(v) for k, v in value.items()
                if k in shortcuts.BY_ID and shortcuts.valid_keys(v)}
    return default


def load_settings() -> dict:
    try:
        raw = json.loads(settings_path().read_text())
    except (OSError, ValueError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return {k: _nested(k, raw.get(k)) if isinstance(v, dict) else _scalar(k, raw.get(k))
            for k, v in DEFAULTS.items()}


def write_atomic(path: Path, text: str) -> None:
    """Replaces the file in one step, writing through a symlink and keeping its permissions."""
    if path.is_symlink():
        path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    try:
        os.chmod(tmp, path.stat().st_mode & 0o7777)
    except FileNotFoundError:
        pass
    os.replace(tmp, path)


def save_settings(s: dict) -> None:
    write_atomic(settings_path(), json.dumps(s, indent=2, ensure_ascii=False) + "\n")


_strings: dict[str, dict] = {}


def _load_strings(lang: str) -> dict:
    if lang not in _strings:
        try:
            _strings[lang] = json.loads((REPO / "i18n" / f"{lang}.json").read_text())
        except (OSError, ValueError):
            _strings[lang] = {}
    return _strings[lang]


def t(key: str, lang: str | None = None):
    """Text for `key` in `lang` (default: the user's language), falling back to English, then to the key."""
    lang = lang or load_settings()["language"]
    for candidate in (lang, "en"):
        value = _load_strings(candidate).get(key)
        if value is not None:
            return value
    return key


def palette(theme: str) -> dict[str, str]:
    return json.loads((REPO / "themes" / theme / "palette.json").read_text())


def theme_label(theme: str) -> str:
    return json.loads((REPO / "themes" / theme / "claude.json").read_text())["name"]


STATUS_LINES = {
    "statusLine": {"type": "command", "command": "~/.claude/statusline.sh", "refreshInterval": 30},
    "subagentStatusLine": {"type": "command", "command": "~/.claude/subagent-statusline.sh"},
}


def claude_settings_path() -> Path:
    return Path.home() / ".claude/settings.json"


STYLE_FILE = "custom-kitty-terminal.md"


def style_name(rs: dict) -> str:
    lang = rs["language"]
    return t("style.name", lang).format(length=t(f"style.length.{rs['length']}", lang))


def all_style_names() -> set[str]:
    return {style_name({"language": lang, "length": length}) for lang in LANGUAGES for length in RESPONSE_LENGTHS}


def style_file(rs: dict) -> str:
    lang = rs["language"]
    length = t(f"style.length.{rs['length']}", lang)
    return (f"---\nname: {style_name(rs)}\n"
            f"description: {t('style.description', lang).format(length=length)}\n"
            "keep-coding-instructions: true\n---\n\n"
            f"{t('style.body.language', lang)}\n\n{t('style.body.' + rs['length'], lang)}\n\n"
            f"{t('style.body.code', lang)}\n")


def style_path() -> Path:
    return Path.home() / ".claude/output-styles" / STYLE_FILE


def _our_spinners() -> list[dict]:
    return [{"mode": "replace", "verbs": t("spinner.verbs", lang)} for lang in LANGUAGES]


def claude_values(s: dict) -> dict:
    """The keys this project always owns in ~/.claude/settings.json."""
    return {"theme": f"custom:{s['theme']}", **STATUS_LINES}


def _apply_claude_options(s: dict, data: dict) -> None:
    """Opt-in parts: spinner phrases and the response style. Never touches what the user set."""
    if s["spinner"] == "ours":
        data["spinnerVerbs"] = {"mode": "replace", "verbs": t("spinner.verbs", s["language"])}
    elif data.get("spinnerVerbs") in _our_spinners():
        del data["spinnerVerbs"]

    rs = s["response_style"]
    ours = all_style_names()
    current = data.get("outputStyle")
    if rs["enabled"]:
        write_atomic(style_path(), style_file(rs))
        if current not in ours:
            rs["previous"] = current
        data["outputStyle"] = style_name(rs)
    else:
        if current in ours:
            if rs["previous"]:
                data["outputStyle"] = rs["previous"]
            else:
                del data["outputStyle"]
        rs["previous"] = None
        try:
            style_path().unlink()
        except FileNotFoundError:
            pass


def merge_claude_settings(s: dict) -> bool:
    """Merges our keys into Claude's settings; True if the file changed.

    Raises ValueError when the existing file isn't a JSON object (it is left untouched).
    May update s["response_style"]["previous"]; the caller saves s."""
    path = claude_settings_path()
    try:
        text = path.read_text()
    except FileNotFoundError:
        text = ""
    data = json.loads(text) if text.strip() else {}
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    merged = {**data, **claude_values(s)}
    _apply_claude_options(s, merged)
    if merged == data:
        return False
    write_atomic(path, json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
    return True


def kitty_dir() -> Path:
    return Path.home() / ".config/kitty"


PADDING = {"compact": "2 4", "normal": "4 8", "roomy": "8 16"}
def _title_bar(choice: str, desktop: str) -> tuple[str, str]:
    if choice == "none":
        return ("linux_display_server auto", "hide_window_decorations yes")
    if choice == "system" and "GNOME" in desktop.upper():
        # GNOME only draws its own title bar (standard buttons) for X11 windows: run through XWayland.
        return ("linux_display_server x11", "hide_window_decorations no")
    # KDE, Cinnamon and the others draw it for Wayland windows too; "kitty" is kitty's own bar.
    return ("linux_display_server auto", "hide_window_decorations no")


def font_conf_family(family: str, installed: list[str] | None = None) -> str:
    """The font kitty should ask for: the chosen one, or the system's monospace font when it isn't installed."""
    if installed is None:
        try:
            out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            out = ""
        installed = [name.strip() for line in out.splitlines() for name in line.split(",") if name.strip()]
    if not installed or family.lower() in {n.lower() for n in installed}:
        return family
    return "monospace"
HEADER = "# Written by the settings menu (ct config); changes here are overwritten.\n"


def appearance_conf(s: dict, desktop: str | None = None) -> str:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "") if desktop is None else desktop
    # "separators" is drawn by tab_bar.py; kitty only needs a valid powerline style.
    powerline = s["tab_style"] if s["tab_style"] != "separators" else "slanted"
    lines = [
        f"modify_font cell_height {s['line_height']}%",
        f"window_padding_width {PADDING[s['padding']]}",
        f"tab_powerline_style {powerline}",
        f"tab_bar_edge {s['tab_position']}",
        f"background_opacity {s['opacity'] / 100:g}" if s["opacity"] < 100 else "background_opacity 1.0",
        f"cursor_shape {s['cursor_shape']}",
        f"cursor_blink_interval {-1 if s['cursor_blink'] else 0}",
        *_title_bar(s["title_bar"], desktop),
        f"disable_ligatures {'never' if s['ligatures'] else 'always'}",
    ]
    return HEADER + "\n".join(lines) + "\n"


def behavior_conf(s: dict) -> str:
    if s["reopen_tabs"]:
        # Reopens last time's tabs; save_session.py keeps that file up to date.
        lines = ["startup_session last-session.kitty-session", "watcher save_session.py"]
    else:
        lines = ["startup_session none"]
    lines += [f"scrollback_lines {s['scrollback']}", f"enable_audio_bell {'yes' if s['bell'] else 'no'}"]
    return HEADER + "\n".join(lines) + "\n"


def close_decision(confirm_close: str, running: list) -> str:
    """For Ctrl+W: "close" right away or "ask" first, per the confirm_close setting."""
    if confirm_close == "always":
        return "ask"
    if confirm_close == "never":
        return "close"
    return "ask" if running else "close"


def write_kitty_includes(s: dict) -> None:
    gen = kitty_dir() / "generated"
    write_atomic(gen / "theme.conf", (REPO / "themes" / s["theme"] / "kitty.conf").read_text())
    family = font_conf_family(s["font_family"])
    # Symbola (or DejaVu Sans) draws a larger ⚙ than the text font; mapping the gear to a
    # font that isn't installed would leave the button blank, so only installed ones are used.
    gear_font = next((f for f in ("Symbola", "DejaVu Sans") if font_conf_family(f) == f), None)
    gear = f"symbol_map U+2699 {gear_font}\n" if gear_font else ""
    write_atomic(gen / "font.conf", HEADER + f"font_family {family}\nfont_size {s['font_size']}.0\n" + gear)
    write_atomic(gen / "appearance.conf", appearance_conf(s))
    write_atomic(gen / "behavior.conf", behavior_conf(s))
    import shortcuts
    write_atomic(gen / "shortcuts.conf", shortcuts.shortcuts_conf(s))


def reload_kitty() -> None:
    try:
        subprocess.run(["pkill", "-USR1", "-u", str(os.getuid()), "-x", "kitty"], capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass


def apply(s: dict | None = None, reload: bool = True) -> list[str]:
    """Applies the settings to kitty and Claude Code. Returns problems as translated messages."""
    s = s or load_settings()
    problems = []
    write_kitty_includes(s)
    try:
        before = json.dumps(s["response_style"], sort_keys=True)
        merge_claude_settings(s)
        if json.dumps(s["response_style"], sort_keys=True) != before:
            save_settings(s)  # remembers the user's own response style
    except ValueError:
        problems.append(t("apply.claude_settings_invalid", s["language"]).format(path=claude_settings_path()))
    if reload:
        reload_kitty()
    return problems


def mono_fonts() -> list[str]:
    try:
        out = subprocess.run(["fc-list", ":spacing=mono", "family"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    names = {line.split(",")[0].strip() for line in out.splitlines() if line.strip()}
    return sorted(n for n in names if "emoji" not in n.lower())
