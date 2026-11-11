# Kitten for Ctrl+click (mouse_map in kitty.conf): opens what is under the mouse.
#   a hyperlink or URL            -> what kitty opens for it (open_actions.conf sends
#                                    file:// links to ckt-open, the rest to the browser)
#   a file path (src/main.rs:42)  -> your editor, at that line (ckt-open)
#   a file name in the side panel -> the same, through the full paths the panel lists
#   [Image #3] in Claude          -> the image pasted into that Claude session
# Works in Claude Code's fullscreen view too (kitty reads the cell under the mouse
# and the text of that row itself). Relative paths are looked up in the folder of
# the program running in the window (Claude, the shell) and its git root.
# What each click found goes to ~/.cache/custom-kitty-terminal/ctrl-click.log.
import importlib
import os
import subprocess
import sys
import time

from kittens.tui.handler import result_handler
from kitty.boss import Boss

# This file is a symlink into the repository: the shared code is in its lib/.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(os.path.expanduser('~/.config/kitty/open_under_mouse.py'))), '..', 'lib'))

LOG = os.path.expanduser('~/.cache/custom-kitty-terminal/ctrl-click.log')


def main(args: list[str]) -> str:
    return ''


def _fresh(name: str):
    """The module as it is on disk now. kitty keeps imported modules for its whole life,
    so after an update (git pull) a plain import would hand back the old code."""
    module = sys.modules.get(name)
    return importlib.reload(module) if module else importlib.import_module(name)


def _log(msg: str) -> None:
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        if os.path.exists(LOG) and os.path.getsize(LOG) > 100_000:
            os.replace(LOG, LOG + '.old')
        with open(LOG, 'a') as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass


def _folders(window) -> list[str]:
    dirs = []
    try:
        dirs += [p.get('cwd') for p in window.child.foreground_processes if p.get('cwd')]
    except Exception:
        pass
    for d in (getattr(window, 'cwd_of_child', None), getattr(window.child, 'current_cwd', None)):
        if d:
            dirs.append(d)
    roots = []
    for d in dirs:
        try:
            top = subprocess.run(['git', '-C', d, 'rev-parse', '--show-toplevel'],
                                 capture_output=True, text=True, timeout=2).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            top = ''
        if top:
            roots.append(top)
    return list(dict.fromkeys(dirs + roots))


def _claude_session(window, op) -> str | None:
    try:
        pids = [p['pid'] for p in window.child.foreground_processes]
    except Exception:
        pids = []
    return op.claude_session_for(pids)


@result_handler(no_ui=True)
def handle_result(args: list[str], answer: str, target_window_id: int, boss: Boss) -> None:
    try:
        _open(boss, target_window_id)
    except Exception as e:
        _log(f'error: {e!r}')


def _open(boss: Boss, target_window_id: int) -> None:
    ckt = _fresh('ckt')
    op = _fresh('openpath')
    from kitty.fast_data_types import click_mouse_url

    window = boss.window_id_map.get(target_window_id) or boss.active_window
    if window is None:
        _log('no window')
        return
    pos = window.current_mouse_position()
    if not pos:
        _log(f'window {window.id}: no mouse position')
        return
    text = str(window.screen.visual_line(pos['cell_y']) or '')
    target = op.target_at_cell(text, pos['cell_x'])
    _log(f'window {window.id} cell {pos["cell_x"]},{pos["cell_y"]}: {target} in {text.strip()[:120]!r}')
    # Images first: "[Image #3]" is no link, and a URL detector could take part of the row.
    if target is not None and target.kind == 'image':
        session = _claude_session(window, op)
        image = op.image_for(session, target.value) if session else None
        _log(f'  image #{target.value} of session {session}: {image}')
        if image:
            op.desktop_open(image)
        return
    # A hyperlink (OSC 8) or a URL kitty detects: kitty opens it (open_actions.conf).
    if click_mouse_url(window.os_window_id, window.tab_id, window.id):
        _log('  opened by kitty as a link')
        return
    if target is None:
        return
    if target.kind == 'url':
        op.desktop_open(target.value)
        return
    path = op.resolve(target.value, _folders(window))
    if not path:
        session = _claude_session(window, op)
        path = op.match_panel_file(target.value, text, op.panel_files(session)) if session else None
    _log(f'  path: {path}')
    if path:
        op.open_target(path, target.line, ckt.load_settings()['editor'], f'unix:@kitty-{os.getpid()}')
