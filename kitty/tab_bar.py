# Desenho personalizado das abas do kitty (tab_bar_style custom).
# ESTILO escolhe o desenho: "pilulas" ou "pontos".
from kitty.fast_data_types import Screen
from kitty.tab_bar import DrawData, ExtraData, TabBarData, as_rgb, draw_title
from kitty.utils import color_as_int

ESTILO = "pontos"

ESQ, DIR = "", ""  # pontas arredondadas (o kitty desenha sozinho)
AZUL = as_rgb(0x51A2DA)
AMARELO = as_rgb(0xE0AF68)
CINZA = as_rgb(0x5E5C64)


def _pilula(draw_data: DrawData, screen: Screen, tab: TabBarData, index: int, max_len: int) -> None:
    tab_bg, tab_fg = screen.cursor.bg, screen.cursor.fg
    bar_bg = as_rgb(color_as_int(draw_data.default_bg))
    screen.cursor.fg, screen.cursor.bg = tab_bg, bar_bg
    screen.draw(ESQ)
    screen.cursor.fg, screen.cursor.bg = tab_fg, tab_bg
    draw_title(draw_data, screen, tab, index, max_len)
    screen.cursor.fg, screen.cursor.bg = tab_bg, bar_bg
    screen.draw(DIR)
    screen.cursor.fg = tab_fg
    screen.draw(" ")


def _ponto(draw_data: DrawData, screen: Screen, tab: TabBarData, index: int, max_len: int) -> None:
    tab_fg = screen.cursor.fg
    screen.cursor.bg = as_rgb(color_as_int(draw_data.default_bg))
    if tab.is_active:
        screen.cursor.fg, mark = AZUL, "●"
    elif tab.has_activity_since_last_focus or tab.needs_attention:
        screen.cursor.fg, mark = AMARELO, "●"
    else:
        screen.cursor.fg, mark = CINZA, "○"
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
    if ESTILO == "pontos":
        _ponto(draw_data, screen, tab, index, max_tab_length)
    else:
        _pilula(draw_data, screen, tab, index, max_tab_length)
    return screen.cursor.x
