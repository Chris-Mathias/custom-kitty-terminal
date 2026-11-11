# Kitten for Ctrl+click (mouse_map in kitty.conf): opens what is under the mouse.
#   a file path (src/main.rs:42)  -> your editor, at that line (ckt-open)
#   [Image #3] in Claude          -> the image pasted into that Claude session
#   a URL                         -> the browser
# Works in Claude Code's fullscreen view too (kitty reads the cell under the mouse
# and the text of that row itself). Relative paths are looked up in the folder of
# the program running in the window (Claude, the shell) and its git root.
import os
import subprocess
import sys

from kittens.tui.handler import result_handler
from kitty.boss import Boss

# This file is a symlink into the repository: the shared code is in its lib/.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(os.path.expanduser('~/.config/kitty/open_under_mouse.py'))), '..', 'lib'))


def main(args: list[str]) -> str:
    return ''


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


@result_handler(no_ui=True)
def handle_result(args: list[str], answer: str, target_window_id: int, boss: Boss) -> None:
    import ckt
    import openpath as op

    window = boss.window_id_map.get(target_window_id) or boss.active_window
    if window is None:
        return
    pos = window.current_mouse_position()
    if not pos:
        return
    text = str(window.screen.visual_line(pos['cell_y']) or '')
    target = op.target_at(text, pos['cell_x'])
    if target is None:
        return
    socket = f'unix:@kitty-{os.getpid()}'
    if target.kind == 'url':
        op.desktop_open(target.value)
    elif target.kind == 'image':
        try:
            pids = [p['pid'] for p in window.child.foreground_processes]
        except Exception:
            pids = []
        session = op.claude_session_for(pids)
        image = op.image_for(session, target.value) if session else None
        if image:
            op.desktop_open(image)
    else:
        path = op.resolve(target.value, _folders(window))
        if path:
            op.open_target(path, target.line, ckt.load_settings()['editor'], socket)
