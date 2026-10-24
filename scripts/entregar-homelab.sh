#!/usr/bin/env bash
# Cria/acompanha um PR e, mediante uma unica confirmacao, aplica a main no homelab.
# Uso: bash scripts/entregar-homelab.sh --deploy

set -Eeuo pipefail

uso() {
  cat <<'EOF'
Uso: bash scripts/entregar-homelab.sh [--deploy]

Execute a partir de uma branch de trabalho ja commitada e com a arvore limpa.
O script envia a branch, cria ou reutiliza o PR, espera o CI e pede uma unica
confirmacao antes do merge. Com --deploy, executa o playbook apos o merge.
EOF
}

deploy=false
case "${1:-}" in
  "") ;;
  --deploy) deploy=true ;;
  -h|--help) uso; exit 0 ;;
  *) uso >&2; exit 2 ;;
esac

raiz="$(git rev-parse --show-toplevel)"
cd "$raiz"
branch="$(git branch --show-current)"

if [[ -z "$branch" || "$branch" == "main" ]]; then
  echo "Erro: execute em uma branch de trabalho, nunca diretamente na main." >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Erro: ha alteracoes nao commitadas. Revise e crie o commit antes da entrega." >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Erro: GitHub CLI nao autenticado. Execute: gh auth login" >&2
  exit 1
fi

echo "Enviando branch $branch..."
git push -u origin "$branch"

if pr_url="$(gh pr view "$branch" --json url --jq .url 2>/dev/null)"; then
  echo "PR existente: $pr_url"
else
  echo "Criando PR para main..."
  pr_url="$(gh pr create --base main --head "$branch" --fill)"
  echo "PR criado: $pr_url"
fi

echo "Aguardando os checks obrigatorios do CI..."
if ! gh pr checks "$pr_url" --watch; then
  echo "CI nao aprovado. Corrija a branch antes de fazer merge." >&2
  exit 1
fi

read -r -p "CI aprovado. Fazer merge de $branch em main? [y/N] " resposta
if [[ ! "$resposta" =~ ^[Yy]$ ]]; then
  echo "Merge cancelado. O PR continua aberto em: $pr_url"
  exit 0
fi

gh pr merge "$pr_url" --merge --delete-branch
git fetch origin
git switch main
git pull --ff-only origin main

if [[ "$deploy" == true ]]; then
  echo "Aplicando main no servidor com Ansible..."
  cd "$raiz/infra/ansible"
  ansible-playbook -i inventory.ini site.yml --ask-vault-pass --ask-become-pass
else
  echo "Merge concluido. Para sincronizar o homelab, execute o playbook do Ansible."
fi
