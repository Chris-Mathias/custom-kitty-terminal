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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
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


def mono_fonts() -> list[str]:
    try:
        out = subprocess.run(["fc-list", ":spacing=mono", "family"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return sorted({line.split(",")[0].strip() for line in out.splitlines() if line.strip()})
