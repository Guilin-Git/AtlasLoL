# ADR-020 — Patch automático, reboot manual

Data: 2026-08-19

## Contexto

O `unattended-upgrades` veio ativo da instalação do Ubuntu Server (`APT::Periodic::Unattended-Upgrade "1"`), instalando correções de segurança sozinho. O reboot automático vem desligado por padrão — todas as diretivas `Unattended-Upgrade::Automatic-Reboot` estão comentadas em `/etc/apt/apt.conf.d/50unattended-upgrades`.

Isso cria um estado intermediário que precisa ser entendido: **instalar não é ativar**. Correção de kernel só passa a valer depois de reboot; até lá, o kernel novo está no disco e o antigo continua na memória. O mesmo vale para bibliotecas compartilhadas — processos já em execução seguem com a versão antiga carregada. O sistema sinaliza isso criando `/var/run/reboot-required`.

Fatos que pesam na decisão hoje:

- O servidor **não é alcançável pela internet**. O NAT do ONT não tem regra de encaminhamento; o acesso vem apenas da rede doméstica, via mapeamento de porta no roteador do homelab (ver [ADR-019](019-roteador-secundario-e-acesso-ao-homelab.md)).
- SSH aceita **apenas chave** — senha e keyboard-interactive desabilitados, root bloqueado.
- O projeto está em fase de construção, com o usuário aprendendo. Reinício inesperado no meio de uma investigação custa mais do que rende.

## Alternativas consideradas

1. **Reboot automático em horário fixo** (ex.: 04:00). Garante kernel efetivamente atualizado. Custo: interrompe execução em andamento e reinicia a máquina sem aviso. Justificável para máquina com IP público sendo varrida continuamente — não é o caso.
2. **Desativar o `unattended-upgrades`.** Descartado: patch de segurança automático é consenso, e o custo de não aplicar é alto demais para o ganho de controle.
3. **Instalar patch automaticamente, reiniciar manualmente.** Escolhida.

## Decisão

Manter o `unattended-upgrades` ativo e o **reboot automático desligado**, adotando a verificação manual como parte da rotina de manutenção:

```bash
ls -la /var/run/reboot-required && cat /var/run/reboot-required.pkgs
```

Nenhum arquivo de configuração foi criado — o comportamento desejado já é o padrão.

## Consequências

- Correções de segurança são aplicadas sem intervenção, mas as que exigem reboot ficam **pendentes por tempo indeterminado**, dependendo da disciplina de quem opera. Esse é o custo aceito conscientemente.
- A verificação de `/var/run/reboot-required` precisa entrar na rotina, e deve ser codificada quando o servidor virar Ansible (PASSO 13) — um `check` que reporta pendência, não uma reza de memória humana.
- Quando o reboot automático for ligado, o timer do coletor (PASSO 11) volta sozinho no boot; o risco é apenas interromper uma execução em andamento, o que a idempotência do PASSO 18 precisa tolerar de qualquer forma.

## Gatilho de revisão

**Ligar o reboot automático quando o servidor deixar de ser exclusivamente doméstico.** Concretamente, qualquer um destes:

- **A API for exposta à internet para amigos testarem** — objetivo declarado do projeto. A partir daí a máquina passa a ser varrida por bots continuamente, e kernel desatualizado deixa de ser risco teórico.
- Dado com valor real acumulado, onde comprometer o servidor custa mais que reiniciá-lo.
- Qualquer serviço com porta encaminhada no ONT (não apenas no roteador do homelab).

Configuração a aplicar nesse momento, em arquivo próprio (`/etc/apt/apt.conf.d/52-atlas-unattended`), nunca editando o arquivo da distribuição:

```
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
```

Número maior que `50` porque, em configuração do APT como no systemd, **o último valor vence** — o oposto do `sshd_config`, onde o primeiro vence.
