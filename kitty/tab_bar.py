# Custom drawing for kitty's tabs (tab_bar_style custom).
# STYLE picks the look: "pills" or "dots".
from kitty.fast_data_types import Screen
from kitty.tab_bar import DrawData, ExtraData, TabBarData, as_rgb, draw_title
from kitty.utils import color_as_int

STYLE = "dots"

LEFT, RIGHT = "", ""  # rounded caps (kitty draws them itself)
BLUE = as_rgb(0x51A2DA)
YELLOW = as_rgb(0xE0AF68)
GRAY = as_rgb(0x5E5C64)


def _pill(draw_data: DrawData, screen: Screen, tab: TabBarData, index: int, max_len: int) -> None:
    tab_bg, tab_fg = screen.cursor.bg, screen.cursor.fg
    bar_bg = as_rgb(color_as_int(draw_data.default_bg))
    screen.cursor.fg, screen.cursor.bg = tab_bg, bar_bg
    screen.draw(LEFT)
    screen.cursor.fg, screen.cursor.bg = tab_fg, tab_bg
    draw_title(draw_data, screen, tab, index, max_len)
    screen.cursor.fg, screen.cursor.bg = tab_bg, bar_bg
    screen.draw(RIGHT)
    screen.cursor.fg = tab_fg
    screen.draw(" ")


def _dot(draw_data: DrawData, screen: Screen, tab: TabBarData, index: int, max_len: int) -> None:
    tab_fg = screen.cursor.fg
    screen.cursor.bg = as_rgb(color_as_int(draw_data.default_bg))
    if tab.is_active:
        screen.cursor.fg, mark = BLUE, "●"
    elif tab.has_activity_since_last_focus or tab.needs_attention:
        screen.cursor.fg, mark = YELLOW, "●"
    else:
        screen.cursor.fg, mark = GRAY, "○"
    screen.draw(" " + mark)
    screen.cursor.fg = tab_fg
    draw_title(draw_data, screen, tab, index, max_len)
    screen.draw("  ")


def draw_tab(
    draw_data: DrawData, screen: Screen, tab: TabBarData,
    before: int, max_tab_length: int, index: int, is_last: bool,
    extra_data: ExtraData,
) -> int:
    if screen.cursor.x == 0:
        screen.cursor.bg = as_rgb(color_as_int(draw_data.default_bg))
        screen.draw(" ")
    if STYLE == "dots":
        _dot(draw_data, screen, tab, index, max_tab_length)
    else:
        _pill(draw_data, screen, tab, index, max_tab_length)
    return screen.cursor.x
