#!/usr/bin/env bash
# Instala esta configuração (kitty + Claude Code) no seu usuário.
#
# Cada arquivo vira um link simbólico para este repositório, então um
# `git pull` aqui já atualiza tudo. O que existia antes é guardado com o
# sufixo .bak-<data>. O settings.json do Claude Code não é substituído:
# só recebe (mesclados) os itens visuais de claude/settings.json.
#
# Uso: ./install.sh
set -euo pipefail

REPO=$(cd "$(dirname "$0")" && pwd)
DATA=$(date +%Y%m%d-%H%M%S)

verde=$'\e[32m'; amarelo=$'\e[33m'; dim=$'\e[2m'; r=$'\e[0m'
ok()    { printf '%s✓%s %s\n' "$verde" "$r" "$1"; }
aviso() { printf '%s!%s %s\n' "$amarelo" "$r" "$1"; }

# Liga $2 -> $1 (arquivo do repositório), guardando o que já existia.
ligar() {
  local origem=$1 destino=$2
  mkdir -p "$(dirname "$destino")"
  if [[ -L $destino && $(readlink -f "$destino") == "$(readlink -f "$origem")" ]]; then
    printf '%s  já ligado: %s%s\n' "$dim" "$destino" "$r"; return
  fi
  if [[ -e $destino || -L $destino ]]; then
    mv "$destino" "$destino.bak-$DATA"
    aviso "guardei o anterior em $destino.bak-$DATA"
  fi
  ln -s "$origem" "$destino"
  ok "$destino"
}

echo "== Dependências"
for cmd in kitty jq git claude; do
  if command -v "$cmd" >/dev/null; then ok "$cmd"; else aviso "$cmd não encontrado (veja o README)"; fi
done
fc-list : family 2>/dev/null | grep -qi "adwaita mono" || aviso "fonte Adwaita Mono não encontrada; troque font_family em kitty/kitty.conf"

echo; echo "== kitty (~/.config/kitty)"
for f in kitty.conf abas.conf tab_bar.py fechar_aba.py fechar-aba-dialogo.sh salvar_sessao.py; do
  ligar "$REPO/kitty/$f" "$HOME/.config/kitty/$f"
done
sessao="$HOME/.config/kitty/ultima-sessao.kitty-session"
if [[ ! -e $sessao ]]; then
  printf '# Gerado por salvar_sessao.py — as abas abertas da última vez.\nnew_tab\nlaunch\n' > "$sessao"
  ok "$sessao (vazia; o kitty preenche sozinho)"
fi

echo; echo "== Comandos (~/.local/bin)"
for f in ct claude-painel claude-restaurar; do
  chmod +x "$REPO/bin/$f"
  ligar "$REPO/bin/$f" "$HOME/.local/bin/$f"
done
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) aviso "~/.local/bin não está no PATH; adicione no ~/.zshrc";; esac

echo; echo "== Claude Code (~/.claude)"
chmod +x "$REPO/claude/statusline.sh" "$REPO/claude/subagent-statusline.sh"
ligar "$REPO/claude/statusline.sh" "$HOME/.claude/statusline.sh"
ligar "$REPO/claude/subagent-statusline.sh" "$HOME/.claude/subagent-statusline.sh"
ligar "$REPO/claude/themes/fedora.json" "$HOME/.claude/themes/fedora.json"
ligar "$REPO/claude/output-styles/portugues-conciso.md" "$HOME/.claude/output-styles/portugues-conciso.md"
ligar "$REPO/claude/painel-sessao" "$HOME/.local/share/claude-mods/painel-sessao"

settings="$HOME/.claude/settings.json"
mkdir -p "$HOME/.claude"
if [[ -f $settings ]]; then
  cp "$settings" "$settings.bak-$DATA"
  jq -s '.[0] * .[1]' "$settings.bak-$DATA" "$REPO/claude/settings.json" > "$settings"
  ok "$settings (mesclado; anterior em $settings.bak-$DATA)"
else
  cp "$REPO/claude/settings.json" "$settings"
  ok "$settings (criado)"
fi

echo
ok "Pronto. Feche e abra o kitty. Para abrir o Claude com o painel: ct (ou Ctrl+Alt+T no kitty)."
