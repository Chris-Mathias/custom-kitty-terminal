#!/usr/bin/env bash
# Caixa de confirmação do Ctrl+W (aberta por fechar_aba.py por cima da aba).
# Uso: fechar-aba-dialogo.sh aba:<id>|janela:<id> <programa rodando>...
alvo=$1; shift
tipo=${alvo%%:*}; alvo_id=${alvo#*:}
if [[ $tipo == janela ]]; then pergunta="Fechar esta sessão?"; else pergunta="Fechar esta aba?"; fi

R=$'\e[0m'; B=$'\e[1m'; DIM=$'\e[38;2;139;138;144m'
AZUL=$'\e[38;2;81;162;218m'; AMARELO=$'\e[38;2;224;175;104m'; BRANCO=$'\e[38;2;255;255;255m'
FUNDO=$'\e[48;2;28;28;31m'; CAIXA=$'\e[48;2;38;38;44m'; BORDA=$'\e[38;2;60;110;180m'
TECLA_AZUL=$'\e[48;2;60;110;180m\e[38;2;255;255;255m'; TECLA_CINZA=$'\e[48;2;58;58;66m\e[38;2;220;220;220m'

cols=$(tput cols); lines=$(tput lines)
largura=54; (( largura > cols - 4 )) && largura=$(( cols - 4 ))
interno=$(( largura - 2 ))

linhas=()
linhas+=("")
linhas+=("  ${B}${BRANCO}${pergunta}${R}${CAIXA}")
linhas+=("")
linhas+=("  ${DIM}Ainda está rodando:${R}${CAIXA}")
for p in "$@"; do
  (( ${#p} > interno - 6 )) && p="${p:0:interno-7}…"
  linhas+=("   ${AMARELO}●${R}${CAIXA} ${BRANCO}${p}${R}${CAIXA}")
done
linhas+=("")
linhas+=("  ${TECLA_AZUL} Enter ${R}${CAIXA} ${BRANCO}fechar${R}${CAIXA}     ${TECLA_CINZA} Esc ${R}${CAIXA} ${DIM}cancelar${R}${CAIXA}")
linhas+=("")

visivel() { local s; s=$(printf '%s' "$1" | sed $'s/\e\\[[0-9;]*m//g'); printf '%s' "${#s}"; }

altura=$(( ${#linhas[@]} + 2 ))
topo=$(( (lines - altura) / 2 )); (( topo < 0 )) && topo=0
esq=$(( (cols - largura) / 2 )); (( esq < 0 )) && esq=0
pad=$(printf '%*s' "$esq" '')

desenhar() {
  printf '\e[?25l%s\e[2J\e[H' "$FUNDO"
  for ((i = 0; i < topo; i++)); do printf '\n'; done
  printf '%s%s%s╭%s╮%s\n' "$pad" "$CAIXA" "$BORDA" "$(printf '─%.0s' $(seq 1 "$interno"))" "$R$FUNDO"
  for l in "${linhas[@]}"; do
    resto=$(( interno - $(visivel "$l") ))
    (( resto < 0 )) && resto=0
    printf '%s%s%s│%s%s%*s%s│%s\n' "$pad" "$CAIXA" "$BORDA" "$R$CAIXA" "$l" "$resto" '' "$BORDA" "$R$FUNDO"
  done
  printf '%s%s%s╰%s╯%s' "$pad" "$CAIXA" "$BORDA" "$(printf '─%.0s' $(seq 1 "$interno"))" "$R$FUNDO"
}

trap 'printf "\e[?25h%s" "$R"' EXIT
desenhar
while IFS= read -rsn1 tecla; do
  case "$tecla" in
    ""|s|S|y|Y)
      if [[ $tipo == janela ]]; then
        kitten @ close-window --match "id:$alvo_id" >/dev/null 2>&1
      else
        kitten @ close-tab --match "id:$alvo_id" >/dev/null 2>&1
      fi
      exit 0 ;;
    $'\e'|n|N|q|Q)
      exit 0 ;;
  esac
done
