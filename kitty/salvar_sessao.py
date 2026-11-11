# Watcher do kitty: guarda as abas abertas em ultima-sessao.kitty-session para
# que, ao abrir o kitty de novo, tudo volte igual (startup_session no kitty.conf).
#
# Para cada janela guarda a pasta e, se nela roda o Claude Code, qual conversa
# (pelo registro em ~/.claude/sessions/<pid>.json). Na volta, essa janela
# retoma a mesma conversa com claude-restaurar.
#
# Salva um pouco depois de cada mudança (foco, título, comando que começa ou
# termina, janela fechada). Quando a janela inteira do kitty é fechada pelo botão,
# não sobra nada aberto e o salvamento é pulado, então a última foto é mantida.
import json
import os
import shlex

from kitty.fast_data_types import add_timer, get_boss, remove_timer

ARQUIVO = os.path.expanduser('~/.config/kitty/ultima-sessao.kitty-session')
SESSOES = os.path.expanduser('~/.claude/sessions')
RESTAURAR = os.path.expanduser('~/.local/bin/claude-restaurar')
SHELL = os.environ.get('SHELL', '/usr/bin/zsh')
ESPERA = 1.5  # segundos

_timer = None


def _conversa_claude(window):
    """sessionId do Claude Code rodando nesta janela, se houver."""
    try:
        procs = window.child.foreground_processes
    except Exception:
        return None
    for p in procs:
        try:
            with open(os.path.join(SESSOES, f"{p['pid']}.json")) as f:
                return json.load(f).get('sessionId')
        except Exception:
            continue
    return None


def _pasta(window):
    try:
        return window.cwd_of_child or window.child.current_cwd or os.path.expanduser('~')
    except Exception:
        return os.path.expanduser('~')


def _salvar(timer_id=None):
    global _timer
    _timer = None
    boss = get_boss()
    os_windows = [tm for tm in boss.os_window_map.values() if len(tm.tabs)]
    if not os_windows:
        return  # kitty fechando: mantém a última foto
    linhas = ['# Gerado por salvar_sessao.py — as abas abertas da última vez.']
    for n, tm in enumerate(os_windows):
        if n:
            linhas.append('new_os_window')
        ativa = tm.active_tab
        for tab in tm.tabs:
            janelas = [w for w in tab if not w.overlay_parent]
            if not janelas:
                continue
            linhas.append('')
            linhas.append('new_tab')
            linhas.append(f'layout {tab.current_layout.name}')
            for w in janelas:
                linhas.append(f'cd {shlex.quote(_pasta(w))}')
                conversa = _conversa_claude(w)
                if conversa:
                    cmd = f'{RESTAURAR} {conversa}'
                    linhas.append(f'launch {shlex.quote(SHELL)} -ic {shlex.quote(cmd)}')
                else:
                    linhas.append('launch')
                # "focus" marca a aba e a janela que estavam na frente
                if tab is ativa and w is tab.active_window:
                    linhas.append('focus')
    texto = '\n'.join(linhas) + '\n'
    tmp = ARQUIVO + '.tmp'
    with open(tmp, 'w') as f:
        f.write(texto)
    os.replace(tmp, ARQUIVO)


def _agendar():
    global _timer
    if _timer is not None:
        remove_timer(_timer)
    _timer = add_timer(_salvar, ESPERA, False)


def on_focus_change(boss, window, data):
    if data.get('focused'):
        _agendar()


def on_title_change(boss, window, data):
    _agendar()


def on_cmd_startstop(boss, window, data):
    _agendar()


def on_close(boss, window, data):
    _agendar()
