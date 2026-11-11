# Custom tab bar (tab_bar_style custom): kitty's own tab drawing (powerline or
# separators, per the settings menu)
# plus a ⚙ button at the right end that opens the settings menu (ct-config).
#
# kitty has no API for extra tab bar buttons, so the click is caught by wrapping
# TabManager.handle_tab_bar_mouse. The wrapper passes every argument through
# untouched and only steps in for a click on a ⚙ that is actually drawn; if
# kitty's internals change, it gets out of the way and the tabs work as usual.
import os

from kitty.fast_data_types import Screen
from kitty.tab_bar import (DrawData, ExtraData, TabBarData, as_rgb, draw_tab_with_powerline,
                           draw_tab_with_separator)
from kitty.utils import color_as_int

# The plain ⚙ is spread over three cells (narrow_symbols in tabs.conf), so it is
# easier to see and click; the space after it gives it room.
GEAR = " ⚙   "
GEAR_CELLS = 5
MENU = os.path.expanduser("~/.local/bin/ct-config")
GEAR_ENABLED = False

# kitty runs this file more than once (every config reload makes a new module), and the
# click hook outlives each run, so the state shared by drawing and clicking lives in
# builtins instead of in the module.
import builtins

# Whether the ⚙ is on screen, per tab bar (it isn't when the tabs fill the bar).
_gear_drawn: dict[int, bool] = builtins.__dict__.setdefault("_ckt_gear_drawn", {})


def _set_gear_drawn(screen, drawn: bool) -> None:
    _gear_drawn[id(screen)] = drawn


def gear_start(columns: int) -> int:
    """First cell of the ⚙ button; the last cell of the bar stays blank."""
    return columns - GEAR_CELLS - 1


def _open_menu(tab_manager) -> None:
    from kitty.fast_data_types import get_boss
    from kitty.launch import launch, parse_launch_args
    spec = parse_launch_args(["--type=overlay", MENU])
    launch(get_boss(), spec.opts, spec.args, target_tab=tab_manager.active_tab)


def _gear_click(self, args) -> bool:
    """True when this mouse event is on a drawn ⚙ (and opens the menu on release)."""
    from kitty.fast_data_types import GLFW_MOUSE_BUTTON_LEFT, GLFW_RELEASE
    x, _y, button, _modifiers, action = args[:5]
    bar = self.tab_bar
    if button == -1 or not _gear_drawn.get(id(bar.screen)):
        return False
    if (int(x) - bar.window_geometry.left) // bar.cell_width < gear_start(bar.screen.columns):
        return False
    if button == GLFW_MOUSE_BUTTON_LEFT and action == GLFW_RELEASE:
        _open_menu(self)
    return True


# The close mark at the end of each tab title (settings: "Close button on tabs").
CLOSE_MARK = "×"
# Cell of each drawn close mark -> its tab, per tab bar.
_close_cells: dict[int, dict[int, int]] = builtins.__dict__.setdefault("_ckt_close_cells", {})


def _set_close_cells(screen, cells: dict[int, int]) -> None:
    _close_cells[id(screen)] = cells


def _close_cell(text: str, start: int, end: int) -> int | None:
    """Where the close mark sits in a drawn tab (None when the title was cut before it)."""
    at = text.rfind(CLOSE_MARK, start, end)
    return at if at >= 0 else None


def _close_tab(tab_manager, tab_id: int) -> None:
    import runpy
    from kitty.constants import config_dir
    from kitty.fast_data_types import get_boss
    boss = get_boss()
    tab = boss.tab_for_id(tab_id)
    if tab is not None:
        # The same path as Ctrl+W: asks first when something is running.
        runpy.run_path(os.path.join(config_dir, "close_tab.py"))["close_tab"](boss, tab)


def _close_click(self, args) -> bool:
    """True when this mouse event is on a drawn close mark (and closes that tab on release)."""
    from kitty.fast_data_types import GLFW_MOUSE_BUTTON_LEFT, GLFW_RELEASE
    x, _y, button, _modifiers, action = args[:5]
    bar = self.tab_bar
    cells = _close_cells.get(id(bar.screen))
    if button == -1 or not cells:
        return False
    tab_id = cells.get((int(x) - bar.window_geometry.left) // bar.cell_width)
    if tab_id is None:
        return False
    if button == GLFW_MOUSE_BUTTON_LEFT and action == GLFW_RELEASE:
        _close_tab(self, tab_id)
    return True


def _install_click_hook() -> bool:
    try:
        from kitty.tabs import TabManager
        original = getattr(TabManager, "_ckt_original_mouse", None) or TabManager.handle_tab_bar_mouse

        def handle_tab_bar_mouse(self, *args, **kwargs):
            try:
                if not kwargs and (_gear_click(self, args) or _close_click(self, args)):
                    return None
            except Exception:
                pass
            return original(self, *args, **kwargs)

        TabManager._ckt_original_mouse = original
        TabManager.handle_tab_bar_mouse = handle_tab_bar_mouse
        return True
    except Exception:
        return False


GEAR_ENABLED = os.path.exists(MENU) and _install_click_hook()


def _settings() -> dict:
    """The settings from the menu (read again on every config reload)."""
    try:
        import sys
        lib = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lib")
        if lib not in sys.path:
            sys.path.insert(0, lib)
        import ckt
        return ckt.load_settings()
    except Exception:
        return {}


_SETTINGS = _settings()
CLOSE_ENABLED = bool(_SETTINGS.get("tab_close_buttons"))


# slanted, round and angled are kitty's powerline styles (tab_powerline_style);
# separators uses kitty's separator drawing.
TAB_DRAW = draw_tab_with_separator if _SETTINGS.get("tab_style") == "separators" else draw_tab_with_powerline


def draw_tab(
    draw_data: DrawData, screen: Screen, tab: TabBarData,
    before: int, max_tab_length: int, index: int, is_last: bool,
    extra_data: ExtraData,
) -> int:
    if index == 1 and not extra_data.for_layout:
        # New pass: if the tabs overflow, kitty stops before the last one.
        _set_gear_drawn(screen, False)
        _set_close_cells(screen, {})
    closable = CLOSE_ENABLED and tab.tab_id > 0  # not the "+" button
    if closable:
        tab = tab._replace(title=f"{tab.title} {CLOSE_MARK}")
    end = TAB_DRAW(draw_data, screen, tab, before, max_tab_length, index, is_last, extra_data)
    if closable and not extra_data.for_layout:
        cell = _close_cell(str(screen.line(screen.cursor.y)), before, end + 1)
        if cell is not None:
            _close_cells.setdefault(id(screen), {})[cell] = tab.tab_id
    if GEAR_ENABLED and is_last and not extra_data.for_layout:
        start = gear_start(screen.columns)
        drawn = screen.cursor.x < start
        if drawn:
            fg, bg = screen.cursor.fg, screen.cursor.bg
            screen.cursor.bg = as_rgb(color_as_int(draw_data.default_bg))
            # A shortened title leaves its overflow past the "…"; kitty clears it
            # only from where the cursor ends, so clear it here before jumping ahead.
            screen.erase_in_line(0, False)
            screen.cursor.x = start
            screen.cursor.fg = as_rgb(color_as_int(draw_data.inactive_fg))
            screen.draw(GEAR)
            # kitty clears the row after the cursor once the last tab is drawn,
            # so the cursor is left past the button.
            screen.cursor.fg, screen.cursor.bg = fg, bg
        _set_gear_drawn(screen, drawn)
    return end
