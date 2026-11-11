"""Settings menu state, without any drawing (bin/ct-config draws it with curses).

Top level: one row per setting with its current value. Enter opens the list of
choices for that row; Enter on a choice changes the setting and goes back.
"""
from __future__ import annotations

import ckt

LANGUAGE_NAMES = {"en": "English", "pt": "Português"}
ITEMS = ("language", "theme", "font_family", "font_size")
LABEL_KEYS = {"language": "menu.language", "theme": "menu.theme",
              "font_family": "menu.font", "font_size": "menu.font_size"}


class Menu:
    def __init__(self, settings: dict, fonts: list[str]):
        self.settings = dict(settings)
        self.fonts = fonts
        self.level = "top"
        self.cursor = 0
        self.item = 0
        self.message = ""

    def _t(self, key: str) -> str:
        return ckt.t(key, self.settings["language"])

    def _choices(self, item: str) -> list:
        if item == "language":
            return list(ckt.LANGUAGES)
        if item == "theme":
            return list(ckt.THEMES)
        if item == "font_size":
            return list(ckt.FONT_SIZES)
        fonts = list(self.fonts)
        if self.settings["font_family"] not in fonts:
            fonts = sorted(fonts + [self.settings["font_family"]])
        return fonts

    def _label(self, item: str, value) -> str:
        if item == "language":
            return LANGUAGE_NAMES[value]
        if item == "theme":
            return ckt.theme_label(value)
        return str(value)

    def items(self) -> list[tuple[str, str]]:
        return [(self._t(LABEL_KEYS[i]), self._label(i, self.settings[i])) for i in ITEMS]

    def view(self) -> dict:
        if self.level == "top":
            title = self._t("menu.title")
            rows = [label for label, _ in self.items()]
        else:
            item = ITEMS[self.item]
            title = self._t(LABEL_KEYS[item])
            current = self.settings[item]
            rows = [f"{'●' if c == current else '○'} {self._label(item, c)}" for c in self._choices(item)]
        return {"level": self.level, "title": title, "rows": rows, "cursor": self.cursor, "message": self.message}

    def key(self, k: str) -> str | None:
        """Handles up, down, enter, back or quit. Returns "apply" after a change, "quit" to close."""
        size = len(ITEMS) if self.level == "top" else len(self._choices(ITEMS[self.item]))
        if k == "quit" or (k == "back" and self.level == "top"):
            return "quit"
        if k in ("up", "down"):
            self.cursor = (self.cursor + (1 if k == "down" else -1)) % size
        elif k == "back":
            self.level, self.cursor = "top", self.item
        elif k == "enter" and self.level == "top":
            self.item, self.level = self.cursor, "sub"
            choices = self._choices(ITEMS[self.item])
            self.cursor = choices.index(self.settings[ITEMS[self.item]])
        elif k == "enter":
            item = ITEMS[self.item]
            value = self._choices(item)[self.cursor]
            self.level, self.cursor = "top", self.item
            if value != self.settings[item]:
                self.settings[item] = value
                return "apply"
        return None
