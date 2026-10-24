#!/usr/bin/env bash
# Cria/acompanha um PR e, mediante uma unica confirmacao, aplica a main no homelab.
# Credenciais locais opcionais: ~/.config/atlaslol/deploy.env

set -Eeuo pipefail

uso() {
  cat <<'EOF'
Uso: bash scripts/entregar-homelab.sh [--deploy]

Execute a partir de uma branch de trabalho ja commitada e com a arvore limpa.
O script envia a branch, cria ou reutiliza o PR, espera o CI e pede uma unica
confirmacao antes do merge. Com --deploy, executa o playbook apos o merge.
EOF
}

validar_arquivo_privado() {
  local caminho="$1"
  local permissoes
  permissoes="$(stat -c '%a' "$caminho")"
  if (( (8#$permissoes & 8#077) != 0 )); then
    echo "Erro: $caminho deve ser acessivel apenas pelo seu usuario (chmod 600)." >&2
    exit 1
  fi
}

deploy=false
case "${1:-}" in
  "") ;;
  --deploy) deploy=true ;;
  -h|--help) uso; exit 0 ;;
  *) uso >&2; exit 2 ;;
esac

config_deploy="${ATLAS_DEPLOY_CONFIG:-$HOME/.config/atlaslol/deploy.env}"
if [[ -f "$config_deploy" ]]; then
  validar_arquivo_privado "$config_deploy"
  # Arquivo local, fora do repositório; contém somente caminhos e opções.
  # shellcheck disable=SC1090
  source "$config_deploy"
fi

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

echo "Aguardando o GitHub registrar os checks do CI..."
checks_registrados=false
for tentativa in {1..12}; do
  quantidade_checks="$(gh pr view "$pr_url" --json statusCheckRollup --jq '.statusCheckRollup | length')"
  if [[ "$quantidade_checks" -gt 0 ]]; then
    checks_registrados=true
    break
  fi

  sleep 5
done

if [[ "$checks_registrados" != true ]]; then
  echo "O GitHub nao registrou checks no PR apos 60 segundos: $pr_url" >&2
  exit 1
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
  if [[ -n "${ATLAS_SSH_KEY:-}" ]]; then
    if [[ -z "${SSH_AUTH_SOCK:-}" ]]; then
      echo "Erro: ssh-agent nao esta ativo. Execute: eval \"\$(ssh-agent -s)\"" >&2
      exit 1
    fi
    ssh-add "$ATLAS_SSH_KEY" >/dev/null 2>&1 || true
  fi

  echo "Aplicando main no servidor com Ansible..."
  cd "$raiz/infra/ansible"
  argumentos_ansible=(-i inventory.ini site.yml)
  if [[ -n "${ATLAS_VAULT_PASSWORD_FILE:-}" ]]; then
    if [[ ! -r "$ATLAS_VAULT_PASSWORD_FILE" ]]; then
      echo "Erro: arquivo de senha do Vault nao pode ser lido." >&2
      exit 1
    fi
    validar_arquivo_privado "$ATLAS_VAULT_PASSWORD_FILE"
    argumentos_ansible+=(--vault-password-file "$ATLAS_VAULT_PASSWORD_FILE")
  else
    argumentos_ansible+=(--ask-vault-pass)
  fi
  if [[ "${ATLAS_AUTOMATED_BECOME:-false}" != true ]]; then
    argumentos_ansible+=(--ask-become-pass)
  fi
  ansible-playbook "${argumentos_ansible[@]}"
else
  echo "Merge concluido. Para sincronizar o homelab, execute o playbook do Ansible."
fi
