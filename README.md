# custom-kitty-terminal

Configuração do terminal [kitty](https://sw.kovidgoyal.net/kitty/) e do [Claude Code](https://code.claude.com) para trabalhar com várias sessões e vários repositórios ao mesmo tempo, no Fedora (GNOME).

- **kitty com cara de Ptyxis**: paleta GNOME, fonte Adwaita Mono, barra de título do GNOME.
- **Abas em diagonal** no topo, com o título que o Claude dá a cada sessão e um botão `+`.
- **Abre como você deixou**: ao abrir o kitty, as abas da última vez voltam, e cada Claude retoma a mesma conversa.
- **Várias sessões do Claude na mesma aba**, empilhadas, trocando pelo painel lateral.
- **Fechar com confirmação** só quando há algo rodando, numa caixa própria.
- **Claude Code**: barra de status em uma linha (projeto, branch, worktree, modelo, contexto e limites de 5h/semana), linhas de subagentes com a branch/worktree de cada um, tema azul, frases em português e um estilo de resposta "Português conciso".
- **Painel lateral** (mod `painel-sessao`): sessões abertas, git (com worktrees), tarefas e arquivos tocados.

## Instalar

Dependências:

```sh
sudo dnf install kitty jq git
# Claude Code 2.1.287 ou mais novo (o painel lateral precisa disso)
```

Depois:

```sh
git clone https://github.com/Chris-Mathias/custom-kitty-terminal.git
cd custom-kitty-terminal
./install.sh
```

O `install.sh` liga cada arquivo deste repositório no lugar certo (links simbólicos), guarda o que já existia com o sufixo `.bak-<data>` e mescla só os itens visuais em `~/.claude/settings.json`. Para atualizar depois: `git pull`.

Feche e abra o kitty. Na primeira vez ele abre uma aba vazia; daí em diante, guarda e reabre as abas sozinho.

## Atalhos do kitty

| Atalho | O que faz |
|---|---|
| `Ctrl+Alt+T` | Sessão nova do Claude numa aba nova |
| `Ctrl+Alt+N` | Sessão nova do Claude na mesma aba (empilhada) |
| `Alt+↑` / `Alt+↓` | Sessão anterior / próxima dentro da aba |
| `Ctrl+Alt+Z` | Alterna entre pilha (uma por vez) e tela dividida |
| `Ctrl+Alt+W` | Fecha a sessão da frente (confirma se algo estiver rodando) |
| `Ctrl+W` | Fecha a aba (confirma se algo estiver rodando) |
| `Ctrl+N`, `Alt+T`, botão `+` | Aba nova só com o shell |
| `Alt+1…6`, `Alt+←/→` | Troca de aba |
| `Ctrl+Shift+Enter` / `Ctrl+Shift+-` | Divide a tela ao lado / embaixo |
| `Ctrl+Shift+H` | Histórico inteiro com busca |
| `Ctrl+Shift+F5` | Recarrega a configuração |

`Ctrl+W` e `Ctrl+N` ficam com o kitty: para apagar a palavra anterior no shell ou no Claude, use `Alt+Backspace`.

## Comandos

- `ct [pasta]`: abre o Claude (com o painel) numa aba nova.
- `ct -a [pasta]`: abre na mesma aba, empilhado.
- `ct [pasta] -- -w nome`: passa argumentos ao `claude` (aqui, uma worktree nova chamada "nome").
- `claude-painel`: roda o Claude com o painel na aba atual.

## Arquivos

```
kitty/      kitty.conf, abas.conf (estilo das abas), tab_bar.py,
            fechar_aba.py + fechar-aba-dialogo.sh (Ctrl+W), salvar_sessao.py (reabrir abas)
bin/        ct, claude-painel, claude-restaurar
claude/     statusline.sh, subagent-statusline.sh, themes/fedora.json,
            output-styles/portugues-conciso.md, settings.json (itens mesclados),
            painel-sessao/ (o mod do painel lateral)
```

A lista de abas salvas (`~/.config/kitty/ultima-sessao.kitty-session`) é de cada computador e fica fora do repositório.

## Observações

- O kitty roda pelo XWayland (`linux_display_server x11`) para o GNOME desenhar a barra de título com os botões padrão. Para a barra própria do kitty, apague essa linha.
- Os atalhos do Claude chamam o seu `$SHELL` em modo interativo, para carregar o seu `~/.zshrc`.
- O painel lateral roda dentro do Claude Code com as permissões do seu usuário; ele lê `git`, `claude agents --json` e `~/.claude/sessions` e fala com o kitty pelo socket de controle (`allow_remote_control socket-only`).
