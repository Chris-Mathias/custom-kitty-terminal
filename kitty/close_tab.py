# Ctrl+W kitten: closes the tab right away when everything in it is idle at
# the shell prompt; if something is still running (e.g. Claude Code), opens
# close-tab-dialog.sh as an overlay on the tab to ask for confirmation.
import os

from kittens.tui.handler import result_handler
from kitty.boss import Boss
from kitty.constants import config_dir

# kitty loads this file without __file__; the config folder comes from config_dir.
DIALOG = os.path.join(config_dir, 'close-tab-dialog.sh')
LIB = os.path.join(os.path.dirname(os.path.realpath(DIALOG)), '..', 'lib')


def _ckt():
    import sys
    if LIB not in sys.path:
        sys.path.insert(0, LIB)
    import ckt
    return ckt


def _t(key: str) -> str:
    try:
        return _ckt().t(key)
    except Exception:
        return key


def _decision(running: list) -> str:
    try:
        ckt = _ckt()
        return ckt.close_decision(ckt.load_settings()["confirm_close"], running)
    except Exception:
        return "ask" if running else "close"


def main(args: list[str]) -> str:
    return ''


def _label(window) -> str:
    cmd = window.child.foreground_cmdline or []
    text = ' '.join(cmd)
    if '/claude/' in text or (cmd and os.path.basename(cmd[0]) == 'claude'):
        prog = 'Claude Code'
    else:
        prog = os.path.basename(cmd[0]) if cmd else _t('cli.program')
    title = (window.title or '').strip().lstrip('✳◐⠂⠐ ').strip()
    return f'{prog} · {title}' if title and title != prog else prog


@result_handler(no_ui=True)
def handle_result(args: list[str], answer: str, target_window_id: int, boss: Boss) -> None:
    # "kitten close_tab.py" closes the tab; "kitten close_tab.py window" closes only
    # the front window (session), keeping the others stacked in the tab.
    window_only = len(args) > 1 and args[1] == 'window'
    tab = boss.active_tab
    if tab is None:
        return
    if window_only:
        w = boss.active_window
        if w is None:
            return
        running = [_label(w)] if w.has_running_program else []
        if _decision(running) == 'close':
            boss.mark_window_for_close(w)
            return
        target = f'window:{w.id}'
    else:
        running = [_label(w) for w in tab if w.has_running_program]
        if _decision(running) == 'close':
            boss.close_tab_no_confirm(tab)
            return
        target = f'tab:{tab.id}'
    from kitty.launch import launch, parse_launch_args
    title = _t('dialog.title_session' if window_only else 'dialog.title_tab')
    spec = parse_launch_args(['--type=overlay', f'--title={title}', DIALOG, target, *running])
    launch(boss, spec.opts, spec.args, target_tab=tab)
