# Custom tab bar (tab_bar_style custom): kitty's own slanted powerline tabs
# plus a ⚙ button at the right end that opens the settings menu (ct-config).
#
# kitty has no API for extra tab bar buttons, so the click is caught by wrapping
# TabManager.handle_tab_bar_mouse. If kitty changes that internal API, the
# wrapper isn't installed, no ⚙ is drawn and the tabs keep working as usual.
import os

from kitty.fast_data_types import Screen
from kitty.tab_bar import DrawData, ExtraData, TabBarData, as_rgb, draw_tab_with_powerline
from kitty.utils import color_as_int

GEAR = " ⚙ "
MENU = os.path.expanduser("~/.local/bin/ct-config")
GEAR_ENABLED = False


def gear_start(columns: int) -> int:
    """First cell of the ⚙ button; the last cell of the bar stays blank."""
    return columns - len(GEAR) - 1


def _open_menu(tab_manager) -> None:
    from kitty.fast_data_types import get_boss
    from kitty.launch import launch, parse_launch_args
    spec = parse_launch_args(["--type=overlay", "--title=Settings", MENU])
    launch(get_boss(), spec.opts, spec.args, target_tab=tab_manager.active_tab)


def _install_click_hook() -> bool:
    try:
        from kitty.fast_data_types import GLFW_MOUSE_BUTTON_LEFT, GLFW_RELEASE
        from kitty.tabs import TabManager
        original = getattr(TabManager, "_ckt_original_mouse", None) or TabManager.handle_tab_bar_mouse

        def handle_tab_bar_mouse(self, x, y, button, modifiers, action):
            try:
                bar = self.tab_bar
                cell = (int(x) - bar.window_geometry.left) // bar.cell_width
                if button != -1 and cell >= gear_start(bar.screen.columns):
                    if button == GLFW_MOUSE_BUTTON_LEFT and action == GLFW_RELEASE:
                        _open_menu(self)
                    return None
            except Exception:
                pass
            return original(self, x, y, button, modifiers, action)

        TabManager._ckt_original_mouse = original
        TabManager.handle_tab_bar_mouse = handle_tab_bar_mouse
        return True
    except Exception:
        return False


GEAR_ENABLED = os.path.exists(MENU) and _install_click_hook()


def draw_tab(
    draw_data: DrawData, screen: Screen, tab: TabBarData,
    before: int, max_tab_length: int, index: int, is_last: bool,
    extra_data: ExtraData,
) -> int:
    end = draw_tab_with_powerline(draw_data, screen, tab, before, max_tab_length, index, is_last, extra_data)
    if GEAR_ENABLED and is_last and not extra_data.for_layout:
        start = gear_start(screen.columns)
        if screen.cursor.x < start:
            fg, bg = screen.cursor.fg, screen.cursor.bg
            screen.cursor.bg = as_rgb(color_as_int(draw_data.default_bg))
            screen.cursor.x = start
            screen.cursor.fg = as_rgb(color_as_int(draw_data.inactive_fg))
            screen.draw(GEAR)
            # kitty clears the row after the cursor once the last tab is drawn,
            # so the cursor is left past the button.
            screen.cursor.fg, screen.cursor.bg = fg, bg
    return end
