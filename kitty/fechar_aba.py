# Kitten do Ctrl+W: fecha a aba na hora se tudo estiver parado no prompt do
# zsh; se algo estiver rodando (ex.: Claude Code), abre fechar-aba-dialogo.sh
# por cima da aba para confirmar.
import os

from kittens.tui.handler import result_handler
from kitty.boss import Boss
from kitty.constants import config_dir

# O kitty carrega este arquivo sem __file__; a pasta da configuração vem de config_dir.
DIALOGO = os.path.join(config_dir, 'fechar-aba-dialogo.sh')


def main(args: list[str]) -> str:
    return ''


def _nome(window) -> str:
    cmd = window.child.foreground_cmdline or []
    texto = ' '.join(cmd)
    if '/claude/' in texto or (cmd and os.path.basename(cmd[0]) == 'claude'):
        prog = 'Claude Code'
    else:
        prog = os.path.basename(cmd[0]) if cmd else 'programa'
    titulo = (window.title or '').strip().lstrip('✳◐⠂⠐ ').strip()
    return f'{prog} · {titulo}' if titulo and titulo != prog else prog


@result_handler(no_ui=True)
def handle_result(args: list[str], answer: str, target_window_id: int, boss: Boss) -> None:
    # "kitten fechar_aba.py" fecha a aba; "kitten fechar_aba.py janela" fecha só a
    # janela (sessão) da frente, mantendo as outras empilhadas na aba.
    so_janela = len(args) > 1 and args[1] == 'janela'
    tab = boss.active_tab
    if tab is None:
        return
    if so_janela:
        w = boss.active_window
        if w is None:
            return
        if not w.has_running_program:
            boss.mark_window_for_close(w)
            return
        alvo, rodando = f'janela:{w.id}', [_nome(w)]
    else:
        rodando = [_nome(w) for w in tab if w.has_running_program]
        if not rodando:
            boss.close_tab_no_confirm(tab)
            return
        alvo = f'aba:{tab.id}'
    from kitty.launch import launch, parse_launch_args
    titulo = 'Fechar sessão?' if so_janela else 'Fechar aba?'
    spec = parse_launch_args(['--type=overlay', f'--title={titulo}', DIALOGO, alvo, *rodando])
    launch(boss, spec.opts, spec.args, target_tab=tab)
