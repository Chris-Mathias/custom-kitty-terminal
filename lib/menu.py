"""Settings menu state, without any drawing (bin/ct-config draws it with curses).

The menu is a tree: the top level lists the groups (Appearance, Claude Code,
Behavior, Shortcuts) and the language; a group lists its items with their
current values; an item lists its choices. A few items are special: the side
panel order (pick a row up with Enter, move it, drop it with Enter) and the
shortcuts (record new keys, which the front end reads, or reset).
"""
from __future__ import annotations

import copy
from typing import Callable, NamedTuple

import ckt
import shortcuts as sc

LANGUAGE_NAMES = {"en": "English", "pt": "Português", "zh": "中文"}


class Node(NamedTuple):
    kind: str          # "group", "choice", "order", "shortcut", "record", "reset", "reset_all"
    label_key: str
    path: tuple = ()   # where the value lives in the settings ("status_line", "weekly")
    children: tuple = ()
    values: tuple = ()
    restart: bool = False  # kitty must restart for this one


def _choice(path: tuple, values=None, restart=False) -> Node:
    return Node("choice", "menu.item." + ".".join(path), path, values=values or (), restart=restart)


def _toggle(path: tuple, label_key: str | None = None) -> Node:
    return Node("choice", label_key or "menu.item." + ".".join(path), path, values=(True, False))


def _tree() -> Node:
    appearance = Node("group", "menu.group.appearance", children=(
        _choice(("theme",)), _choice(("font_family",)), _choice(("font_size",)), _choice(("line_height",)),
        _choice(("padding",)), _choice(("tab_style",)), _choice(("tab_position",)), _choice(("opacity",)),
        _choice(("cursor_shape",)), _choice(("cursor_blink",)), _choice(("title_bar",), restart=True),
        _choice(("ligatures",)),
    ))
    response = Node("group", "menu.item.response_style", children=(
        _toggle(("response_style", "enabled")),
        _choice(("response_style", "language"), ckt.LANGUAGES),
        _choice(("response_style", "length"), ckt.RESPONSE_LENGTHS),
    ))
    status = Node("group", "menu.item.status_line",
                  children=tuple(_toggle(("status_line", k)) for k in ckt.STATUS_ITEMS))
    panel = Node("group", "menu.item.panel", children=(
        *(Node("choice", f"menu.item.panel.{name}", ("panel", "sections", name), values=(True, False))
          for name in ckt.PANEL_SECTIONS),
        Node("order", "menu.item.panel.order", ("panel", "sections")),
        _toggle(("panel", "auto_open")),
    ))
    claude = Node("group", "menu.group.claude", children=(response, status, _choice(("subagent_rows",)), panel,
                                                            _choice(("spinner",))))
    behavior = Node("group", "menu.group.behavior", children=(
        _choice(("reopen_tabs",)), _choice(("confirm_close",)), _choice(("kitty_ctrl_keys",)),
        _choice(("scrollback",)), _choice(("bell",)),
        _choice(("tab_close_buttons",)), _choice(("panel_close_buttons",)),
    ))
    shortcut_rows = tuple(Node("shortcut", a.label_key, (a.id,), children=(
        Node("record", "menu.shortcut.record", (a.id,)), Node("reset", "menu.shortcut.reset", (a.id,)),
    )) for a in sc.ACTIONS)
    keys = Node("group", "menu.group.shortcuts", children=(*shortcut_rows, Node("reset_all", "menu.shortcut.reset_all")))
    return Node("group", "menu.title", children=(appearance, claude, behavior, keys, _choice(("language",))))


class Menu:
    def __init__(self, settings: dict, fonts: list[str],
                 kitty_action: Callable[[str], str | None] = sc.kitty_default_action):
        self.settings = copy.deepcopy(settings)
        self.fonts = fonts
        self.kitty_action = kitty_action
        self.root = _tree()
        self.stack: list[tuple[Node, int]] = [(self.root, 0)]
        self.message = ""
        self.moving = False      # the panel order editor holds a row
        self.pending: str | None = None  # keys waiting for "swap?" confirmation
        self.capturing: str | None = None  # action id being recorded

    # ---------- text ----------
    def _t(self, key: str) -> str:
        return ckt.t(key, self.settings["language"])

    def _get(self, path: tuple):
        if path[:2] == ("panel", "sections") and len(path) == 3:
            return path[2] in self.settings["panel"]["sections"]
        value = self.settings
        for p in path:
            value = value[p]
        return value

    def _set(self, path: tuple, value) -> None:
        if path[:2] == ("panel", "sections") and len(path) == 3:
            sections = [x for x in self.settings["panel"]["sections"] if x != path[2]]
            self.settings["panel"]["sections"] = sections + [path[2]] if value else sections
            return
        target = self.settings
        for p in path[:-1]:
            target = target[p]
        target[path[-1]] = value

    def _choices(self, node: Node) -> list:
        if node.values:
            return list(node.values)
        key = node.path[-1]
        if key == "font_family":
            current = self.settings["font_family"]
            return sorted(set(self.fonts) | {current})
        return list(ckt.CHOICES[key])

    def _value_label(self, node: Node, value) -> str:
        key = node.path[-1] if node.path else ""
        if isinstance(value, bool):
            return self._t("value.on" if value else "value.off")
        if key == "language":
            return LANGUAGE_NAMES[value]
        if key == "theme":
            return ckt.theme_label(value)
        if key in ("line_height", "opacity"):
            return f"{value}%"
        if key == "scrollback":
            return f"{value:,}".replace(",", " ")
        if isinstance(value, str) and key not in ("font_family",):
            label = self._t(f"value.{key}.{value}")
            return label if label != f"value.{key}.{value}" else value
        return str(value)

    def _current_label(self, node: Node) -> str:
        if node.kind == "choice":
            return self._value_label(node, self._get(node.path))
        if node.kind == "shortcut":
            keys = sc.keys_for(self.settings)[node.path[0]]
            if not self.settings["kitty_ctrl_keys"] and keys in sc.CTRL_KEYS:
                return self._t("menu.shortcut.given_to_shell")
            return keys
        if node.kind == "order":
            return " · ".join(self._t(f"menu.item.panel.{s}") for s in self.settings["panel"]["sections"])
        if node.path == () and node.label_key == "menu.item.response_style":
            rs = self.settings["response_style"]
            return ckt.style_name(rs) if rs["enabled"] else self._t("value.claude_default")
        if node.label_key == "menu.item.status_line":
            on = sum(self.settings["status_line"].values())
            return f"{on}/{len(ckt.STATUS_ITEMS)}"
        return ""

    # ---------- view ----------
    def labels(self) -> list[str]:
        node, _ = self.stack[-1]
        return [self._t(c.label_key) for c in node.children]

    def view(self) -> dict:
        node, cursor = self.stack[-1]
        title = self._t(node.label_key)
        if node.kind in ("group", "shortcut"):
            rows = self.labels()
            values = [self._current_label(c) for c in node.children]
            level = "list"
        elif node.kind == "order":
            rows = [self._t(f"menu.item.panel.{s}") for s in self.settings["panel"]["sections"]]
            values = ["" for _ in rows]
            level = "order"
        else:
            current = self._get(node.path)
            rows = [f"{'●' if c == current else '○'} {self._value_label(node, c)}" for c in self._choices(node)]
            values = ["" for _ in rows]
            level = "choice"
        return {"level": level, "title": title, "rows": rows, "values": values, "cursor": cursor,
                "message": self.message, "moving": self.moving, "confirm": self.pending is not None,
                "capturing": self.capturing is not None}

    # ---------- keys ----------
    def _size(self) -> int:
        node, _ = self.stack[-1]
        if node.kind in ("group", "shortcut"):
            return len(node.children)
        if node.kind == "order":
            return len(self.settings["panel"]["sections"])
        return len(self._choices(node))

    def _open(self, child: Node) -> str | None:
        if child.kind in ("group", "shortcut"):
            self.stack.append((child, 0))
        elif child.kind == "order":
            if self.settings["panel"]["sections"]:
                self.stack.append((child, 0))
        elif child.kind == "choice":
            choices = self._choices(child)
            current = self._get(child.path)
            self.stack.append((child, choices.index(current) if current in choices else 0))
        elif child.kind == "record":
            self.capturing = child.path[0]
            self.message = self._t("menu.shortcut.press")
            return "capture"
        elif child.kind == "reset":
            self.settings = sc.reset(self.settings, child.path[0])
            self.stack.pop()
            return "apply"
        elif child.kind == "reset_all":
            self.settings = sc.reset_all(self.settings)
            return "apply"
        return None

    def key(self, k: str) -> str | None:
        node, cursor = self.stack[-1]
        if self.pending is not None:
            return self._confirm(k == "enter")
        if k == "quit":
            return "quit"
        if k == "back":
            self.message = ""
            if self.moving:
                self.moving = False
                return "apply"
            if len(self.stack) == 1:
                return "quit"
            self.stack.pop()
            return None
        size = self._size()
        if k in ("up", "down") and size:
            step = 1 if k == "down" else -1
            new = (cursor + step) % size
            if self.moving:
                sections = self.settings["panel"]["sections"]
                sections.insert(new, sections.pop(cursor))
            self.stack[-1] = (node, new)
            return None
        if k != "enter":
            return None
        self.message = ""
        if node.kind in ("group", "shortcut"):
            return self._open(node.children[cursor])
        if node.kind == "order":
            self.moving = not self.moving
            return None if self.moving else "apply"
        value = self._choices(node)[cursor]
        self.stack.pop()
        if value == self._get(node.path):
            return None
        self._set(node.path, value)
        if node.restart:
            self.message = self._t("menu.restart_needed")
        return "apply"

    # ---------- recording shortcuts ----------
    def captured(self, keys: str | None) -> str | None:
        """The keys the front end read while capturing (None = cancelled)."""
        action = self.capturing
        self.capturing = None
        if action is None or keys is None:
            self.message = ""
            return None
        keys = sc.normalize(keys)
        if not self.settings["kitty_ctrl_keys"] and keys in sc.CTRL_KEYS:
            self.message = self._t("menu.shortcut.refused_ctrl")
            return None
        owner = next((i for i, k in sc.keys_for(self.settings).items() if k == keys and i != action), None)
        self.pending = keys
        self._pending_action = action
        if owner:
            self.message = self._t("menu.shortcut.used_by").format(
                keys=keys, name=self._t(sc.BY_ID[owner].label_key))
            return "confirm"
        kitty = self.kitty_action(keys)
        if kitty:
            self.message = self._t("menu.shortcut.used_by_kitty").format(keys=keys, name=kitty)
            return "confirm"
        return self._confirm(True)

    def _confirm(self, yes: bool) -> str | None:
        keys, action = self.pending, self._pending_action
        self.pending = None
        if not yes:
            self.message = ""
            return None
        self.settings, _ = sc.assign(self.settings, action, keys)
        self.message = ""
        self.stack.pop()  # back to the shortcut list
        return "apply"
