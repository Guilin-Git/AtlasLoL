# Credenciais locais para entrega ao homelab

O deploy automatizado não lê o `.env` do projeto. A chave Riot e os segredos
do servidor continuam fora do repositório; estas instruções só reduzem prompts
repetidos no computador WSL de administração.

## Configuração única

1. Adicione a senha `sudo` do servidor ao arquivo **já criptografado** pelo
   Ansible Vault. No diretório `infra/ansible`, execute:

   ```bash
   ansible-vault edit group_vars/atlas_server/vault.yml
   ```

   Inclua a variável abaixo. O nome é especial para o Ansible; não a coloque em
   arquivo não criptografado.

   ```yaml
   ansible_become_password: "SUA_SENHA_SUDO_DO_SERVIDOR"
   ```

2. Crie um arquivo local para a senha do Vault, fora do projeto:

   ```bash
   mkdir -p ~/.config/atlaslol
   umask 077
   nano ~/.config/atlaslol/ansible-vault.pass
   ```

   Cole somente a senha do Vault, em uma linha. Depois confirme:

   ```bash
   chmod 600 ~/.config/atlaslol/ansible-vault.pass
   ```

3. Crie a configuração local, que contém somente caminhos e opções — não
   senhas:

   ```bash
   nano ~/.config/atlaslol/deploy.env
   ```

   Conteúdo:

   ```bash
   ATLAS_SSH_KEY="$HOME/.ssh/id_ed25519_atlaslol_servidor"
   ATLAS_VAULT_PASSWORD_FILE="$HOME/.config/atlaslol/ansible-vault.pass"
   ATLAS_AUTOMATED_BECOME=true
   ```

   E restrinja o arquivo:

   ```bash
   chmod 600 ~/.config/atlaslol/deploy.env
   ```

## Por sessão de terminal

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519_atlaslol_servidor
```

Você informa a passphrase SSH uma vez. O agente a mantém somente em memória
até ser encerrado ou até o WSL reiniciar.

Depois disso, `bash scripts/entregar-homelab.sh --deploy` não pedirá
passphrase SSH, senha do Vault nem senha sudo. O script continua pedindo a
confirmação explícita antes do merge.
