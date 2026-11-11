# Ctrl+W kitten: closes the tab right away when everything in it is idle at
# the shell prompt; if something is still running (e.g. Claude Code), opens
# close-tab-dialog.sh as an overlay on the tab to ask for confirmation.
import os

from kittens.tui.handler import result_handler
from kitty.boss import Boss
from kitty.constants import config_dir

# kitty loads this file without __file__; the config folder comes from config_dir.
DIALOG = os.path.join(config_dir, 'close-tab-dialog.sh')


def main(args: list[str]) -> str:
    return ''


def _label(window) -> str:
    cmd = window.child.foreground_cmdline or []
    text = ' '.join(cmd)
    if '/claude/' in text or (cmd and os.path.basename(cmd[0]) == 'claude'):
        prog = 'Claude Code'
    else:
        prog = os.path.basename(cmd[0]) if cmd else 'programa'
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
        if not w.has_running_program:
            boss.mark_window_for_close(w)
            return
        target, running = f'window:{w.id}', [_label(w)]
    else:
        running = [_label(w) for w in tab if w.has_running_program]
        if not running:
            boss.close_tab_no_confirm(tab)
            return
        target = f'tab:{tab.id}'
    from kitty.launch import launch, parse_launch_args
    title = 'Fechar sessão?' if window_only else 'Fechar aba?'
    spec = parse_launch_args(['--type=overlay', f'--title={title}', DIALOG, target, *running])
    launch(boss, spec.opts, spec.args, target_tab=tab)
