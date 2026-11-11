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
THEMES = ("fedora", "catppuccin", "tokyo-night", "dracula", "gruvbox", "light")
FONT_SIZES = range(8, 25)
DEFAULTS = {"language": "en", "theme": "fedora", "font_family": "Adwaita Mono", "font_size": 12}


def config_dir() -> Path:
    return Path(os.environ.get("CKT_CONFIG_DIR") or Path.home() / ".config/custom-kitty-terminal")


def settings_path() -> Path:
    return config_dir() / "settings.json"


def _valid(key: str, value) -> bool:
    if key == "language":
        return value in LANGUAGES
    if key == "theme":
        return value in THEMES
    if key == "font_size":
        return isinstance(value, int) and not isinstance(value, bool) and value in FONT_SIZES
    if key == "font_family":
        return isinstance(value, str) and bool(value.strip())
    return False


def load_settings() -> dict:
    try:
        raw = json.loads(settings_path().read_text())
    except (OSError, ValueError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return {k: raw[k] if _valid(k, raw.get(k)) else v for k, v in DEFAULTS.items()}


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


def claude_values(s: dict) -> dict:
    """The keys this project owns in ~/.claude/settings.json."""
    return {
        "theme": f"custom:{s['theme']}",
        "outputStyle": t("output_style", s["language"]),
        "spinnerVerbs": {"mode": "replace", "verbs": t("spinner.verbs", s["language"])},
        **STATUS_LINES,
    }


def merge_claude_settings(s: dict) -> bool:
    """Merges our keys into Claude's settings; True if the file changed.

    Raises ValueError when the existing file isn't a JSON object (it is left untouched)."""
    path = claude_settings_path()
    try:
        text = path.read_text()
    except FileNotFoundError:
        text = ""
    data = json.loads(text) if text.strip() else {}
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    merged = {**data, **claude_values(s)}
    if merged == data:
        return False
    write_atomic(path, json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
    return True


def kitty_dir() -> Path:
    return Path.home() / ".config/kitty"


def write_kitty_includes(s: dict) -> None:
    gen = kitty_dir() / "generated"
    write_atomic(gen / "theme.conf", (REPO / "themes" / s["theme"] / "kitty.conf").read_text())
    write_atomic(gen / "font.conf", "# Written by the settings menu (ct config).\n"
                 f"font_family {s['font_family']}\nfont_size {s['font_size']}.0\n")


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
        merge_claude_settings(s)
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
