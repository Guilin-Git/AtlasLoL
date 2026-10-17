# Projeto Atlas — contexto para o Claude Code

> Este arquivo dá contexto ao agente. O passo a passo humano está em `MANUAL.md` (44 passos, 14 caixas). O planejamento completo está em `PROJETO.md`. **Leia o passo atual do `MANUAL.md` antes de propor qualquer coisa.**

---

## 1. O que é este projeto

Plataforma de análise de performance em League of Legends, construída como laboratório de infraestrutura, engenharia de dados e ciência de dados.

**O produto final é secundário. O objetivo real é eu aprender os conceitos.** Toda escolha de tecnologia foi feita para ter equivalente direto na AWS, que é onde trabalho profissionalmente.

Critério de sucesso: não é "está funcionando", é "eu consigo explicar por que funciona sem consultar nada".

---

## 2. A regra mais importante: modo pedagógico

**Não escreva o código inteiro para mim.** Se você resolver tudo, o projeto perde a razão de existir.

### Como me ajudar

- **Explique o conceito antes do código.** Eu preciso entender o "por quê" antes do "como"
- **Prefira esqueleto a solução pronta.** Estrutura, assinaturas de função, `# TODO` nos pontos centrais — eu preencho
- **Quando eu pedir código completo, escreva — mas explique as decisões não óbvias.** Especialmente as que envolvem trade-off
- **Aponte o erro que eu vou cometer**, em vez de silenciosamente evitá-lo por mim
- **Me faça perguntas** quando houver mais de um caminho razoável. A escolha é minha, e vira ADR
- **Discorde de mim** quando eu estiver errado. Não valide ideia ruim por educação
- **Não bloqueie o desenvolvimento esperando respostas a testes de aprendizado.** Explique a resposta e continue; use o teste como revisão, não como portão manual.
- **Se eu pedir algo que pula etapas do `MANUAL.md`, avise.** A ordem foi otimizada; pular gera retrabalho

### O que não fazer

- Não gere 300 linhas de código que eu vou copiar sem entender
- Não instale/configure coisas que estão no anti-escopo (§8)
- Não sugira "para simplificar, use X" quando X é justamente o que eu quero aprender
- Não invente números, limites de API ou nomes de recurso (§12)

---

## 3. Restrições de hardware — invioláveis

**Servidor: Acer Aspire ES1-572 — i3-6100U (2 núcleos / 4 threads, 2.3 GHz, sem turbo), 4 GB DDR3L, HDD 1 TB, Gigabit LAN.**

Depois do SO e do Docker, sobram **~3,2 GB de RAM reais**.

**O gargalo principal é o HDD, não a RAM.** Disco mecânico faz ~80–100 IOPS aleatórios. Se a RAM acabar, o swap está no mesmo disco: a máquina não fica lenta, ela **congela** (50–100× mais lento, thrashing).

### Consequências práticas para qualquer código que você propuser

- **Processamento em streaming, nunca acumulando.** Nada de carregar tudo num DataFrame. Um item por vez, escreve, libera
- **`mem_limit` em todo container**, sem exceção. Sem isso, um vazamento derruba a máquina inteira em vez de só o culpado
- **`memory_limit` explícito no DuckDB.** Spill controlado é degradação; swap é travamento
- **Nunca escanear JSON bruto duas vezes.** Converta para Parquet e leia só as colunas necessárias
- **Nada de JVM no servidor.** Trino, Nessie, Polaris, Temporal estão fora por isso
- Se sua sugestão consumir mais de ~1 GB no servidor, **avise antes**

Consulte a tabela de orçamento de memória em `PROJETO.md` §8.

---

## 4. Topologia — o que roda onde

| Máquina | Papel | Roda o quê |
|---|---|---|
| **PC principal** | Bancada. Onde escrevo, experimento e erro | Editor, testes, k3d, treino de modelo, análise exploratória, backfill pesado, LocalStack |
| **Notebook** (`ssh servidor`) | Servidor 24/7, headless | Coletor, Postgres, API, MinIO, jobs incrementais |
| **HD externo** | Armazém | Bronze (JSON cru), Parquet, backups, volume do MinIO |
| **Oracle Cloud** (opcional, Caixa 12) | Nuvem de verdade | Terraform provisionando, IAM, VCN |

**Regras de alocação:**
- Trabalho pesado e pontual → PC
- Trabalho leve e contínuo → notebook
- **Postgres fica no disco interno**, não no HD externo por USB (latência + risco de desconexão silenciosa corromper escrita)
- Kubernetes é no PC via k3d, não no notebook (control plane come 500–800 MB)

---

## 5. Fontes de dados

| Fonte | Acesso | Característica crítica |
|---|---|---|
| **Riot API** | Chave de dev, expira em 24h | **Tem janela de retenção — dado que sai dela não volta** |
| **Oracle's Elixir** | CSV, download direto | Estático, sem pressa, sem rate limit |
| **Data Dragon** | HTTP aberto | Catálogo versionado por patch |

### Sobre a Riot API

- Rate limit da dev key: **20 req/s E 100 req/2min simultaneamente**. O segundo é 24× mais restritivo → ~50 req/min sustentados
- Limites são **por routing value**: `br1` (SUMMONER/LEAGUE) e `americas` (MATCH) são buckets separados e podem rodar em paralelo
- **Leia os headers** (`X-App-Rate-Limit-Count`, `Retry-After`) em vez de decorar números
- `403` = chave expirada. Erro **permanente**, não transitório. Parar e logar de forma inequívoca, sem retry infinito
- A chave vive em `EnvironmentFile`, nunca no código nem no Git

### Quatro bases, quatro papéis

- **Minhas partidas** → diagnóstico pessoal. Janela: tudo que existir
- **Elo+1** → benchmark acionável. Janela: patch atual + anterior
- **Challenger** → meta, builds, dado limpo de treino. Janela: patch atual + anterior
- **Profissional (Oracle's Elixir)** → volume para modelagem. Janela: multi-ano. **Não tem timeline**

**Regra:** o coletor não conhece janela nenhuma. Baixa tudo, nunca apaga. Janela é filtro no dbt, não constante no código.

### Tratamento de erro obrigatório desde o PASSO 10

Como estou usando dev key, o `403` vai acontecer **todo dia**. Ele não é
erro transitório — não retentar.

- `403` → parar imediatamente e logar:
  `CRITICAL: chave expirada — regenerar em developer.riotgames.com`
- `429` / `503` → transitório, retentar com backoff e respeitar `Retry-After`
- `404` → permanente, registrar e seguir para o próximo item

O log precisa ser inequívoco no `journalctl`, não stack trace.

---

## 6. Stack e equivalência AWS

| Camada | Aqui | AWS |
|---|---|---|
| Object storage | MinIO | S3 |
| OLTP | PostgreSQL | RDS |
| Mensageria | NATS **JetStream** (não core) | SQS / Kinesis |
| Table format | Iceberg (catálogo SQL no Postgres) | Glue Data Catalog |
| Query engine | DuckDB | Athena |
| Transformação | dbt | dbt sobre Athena |
| Agendamento | systemd timers | EventBridge Scheduler |
| Config de máquina | Ansible | (SSM / AMI) |
| IaC | Terraform | Terraform + provider AWS |
| Orquestração | k3d / k3s | EKS |
| Métricas / logs | Prometheus / Loki | CloudWatch |
| ML tracking | MLflow | SageMaker Registry |
| LLM | API Claude | Bedrock |

Quando fizer sentido, **mencione o equivalente AWS** — é parte do objetivo de aprendizado.

**Lacunas conhecidas** (não transferem do lab caseiro): IAM real, VPC/rede, custo/FinOps.

---

## 7. Decisões já tomadas

Não reabra sem motivo novo. Cada uma tem ADR em `docs/adr/`.

| ADR | Decisão |
|---|---|
| 001 | HD externo para bronze/Parquet; Postgres no disco interno |
| 002 | zram + `swappiness=100` (correto com zram, péssimo com swap em disco) |
| 003 | **Ansible configura máquina, Terraform gerencia API.** Não misturar |
| 004 | Perfis do Compose + `mem_limit` em tudo |
| 005 | systemd timer no lugar de orquestrador |
| 006 | Least privilege no MinIO: um usuário por serviço, root só para admin |
| 007 | Terraform sobre serviços locais (MinIO, Postgres, Grafana, GitHub) |
| 009 | pyiceberg com catálogo SQL, não Nessie/Polaris (JVM) |
| 011 | DuckDB agora, Trino só quando doer |
| 012 | JetStream, não NATS core |
| 013 | Temporal fora do escopo |
| 014 | Backfill pesado no PC, incremental no notebook |
| 015 | Não usar métrica de profissional como benchmark pessoal |
| 016 | Kubernetes no PC via k3d |
| 018 | LLM narra, nunca calcula |
| 019 | Roteador próprio atrás do ONT; PC em duas interfaces (cabo=internet, Wi-Fi=homelab) |
| 020 | Patch automático sim, reboot automático não — até a API ser exposta |
| 021 | Bateria removida do servidor; nobreak como substituição |

### Conceitos que estruturam tudo

- **Idempotência** — rodar duas vezes = rodar uma. Vale para Ansible, Terraform, ingestão e consumidor de fila
- **Bronze é seguro, não desperdício** — JSON cru intocado. Coletar é caro e irreversível; transformar é barato e refazível
- **Erro transitório ≠ permanente** — 429/503 retenta; 403/404 não

---

## 8. Anti-escopo — não sugira

| Item | Por quê | Gatilho de entrada |
|---|---|---|
| Trino | 2 GB+ de heap JVM | Quando o DuckDB não aguentar |
| Temporal | 1 GB+ e banco próprio | Workflow durável de verdade |
| Ollama | 2,5 GB+, sem GPU | Se houver GPU |
| Dagster | 600–900 MB | Depois do upgrade de RAM |
| Nessie / Polaris | JVM | Catálogo compartilhado entre engines |
| Tracing (Tempo) | Traces triviais com 2 serviços | A partir de 3–4 serviços |
| Frontend elaborado | Foco é backend/infra/dados | Provavelmente nunca |

Se você achar que um destes resolve meu problema, **argumente antes de assumir** — o gatilho pode ter sido atingido.

---

## 9. Convenções

**Python** — 3.11+, gerenciador de ambiente definido no repo, `ruff` para lint, type hints, `pytest`. Log **estruturado em JSON com correlation id**, nunca `print`.

**Terraform** — módulos em `infra/terraform/modules/`, state remoto no MinIO (bucket `tf-state`), `.tfvars` por ambiente. Recursos se referenciam entre si (`minio_iam_policy.x.policy`), nunca strings digitadas — é isso que monta o grafo de dependências.

**Ansible** — roles por responsabilidade, `ansible-vault` para segredo, **módulo `command` é último recurso** (quebra idempotência).

**Git** — commit pequeno e descritivo, PR barrado por CI vermelho, segredo nunca commitado.

**Dado** — camadas `bronze` / `silver` / `gold`. Bronze é imutável. Particionamento por `patch` (extraído de `gameVersion`, ex.: `"25.14.633.1234"` → `25.14`).

**ADR** — arquivo curto em `docs/adr/NNN-titulo.md`: contexto, alternativas, decisão, consequências, gatilho de revisão.

---

## 10. Estrutura do repositório

```
atlas/
  collector/        # extract: falar com a Riot API
  ingestion/        # load: pousar no armazenamento
  api/              # FastAPI
  workers/          # consumidores de evento
  dbt/              # staging → intermediate → marts
  ml/               # features, treino, avaliação (roda no PC)
  infra/
    ansible/        # configura o notebook
    terraform/      # gerencia APIs de serviço
    compose/        # perfis: core, ingest, lake, obs, ml
  notebooks/        # exploratório
  docs/adr/
  MANUAL.md         # passo a passo (44 passos)
  PROJETO.md        # planejamento completo
  CLAUDE.md         # este arquivo
```

---


## 11. Estado atual

> **Mantenha esta seção atualizada. É o primeiro lugar que você deve olhar.**

- **Passos em andamento:** PASSO 11 e PASSO 13
  - `atlas-collector.service` e `atlas-collector.timer` configurados manualmente no servidor, como exige a etapa pedagógica anterior ao Ansible.
  - Timer horário habilitado e ativo; coleta manual, idempotência, coleta incremental e retorno após reboot já validados.
  - Período de observação de 48 horas ainda em andamento; não declarar o PASSO 11 concluído antes desse teste.
-  PASSO 13 pode avançar em paralelo: transformar a configuração manual do servidor em roles Ansible.
- **Último passo concluído:** PASSO 12 — primeiro playbook Ansible validado em 2026-10-17
  - Controlador: WSL do PC; host gerenciado: `atlaslol` (`192.168.3.6`) via SSH como `guilin`.
  - `infra/ansible/install-docker.yml` garantiu `docker.io` com o módulo idempotente `apt`.
  - Testes concluídos: instalação inicial (`changed=1`), segunda execução (`changed=0`), remoção manual seguida de reinstalação (`changed=1`) e simulação com `--check` (`changed=0`).
  - Ubuntu 26.04 usa `sudo-rs`, incompatível com a detecção de prompt do Ansible Core 2.17; o inventário fixa `/usr/bin/sudo.ws` somente para `become`.
- **Passo anterior:** PASSO 10 — coletor mínimo validado localmente em 2026-10-16
  - Coletadas **20 partidas** e seus **20 timelines** em `bronze-local/`, todos como JSON bruto comprimido em zstd e particionado por patch.
  - Idempotência validada: a primeira execução completou 15 itens pendentes e pulou 5 existentes; a segunda pulou as 20, sem novo download ou falha.
  - Retomada após interrupção e escrita atômica são cobertas pela suíte offline; os 20 testes e o lint (`ruff`) passaram antes da coleta real.
  - O bronze local é dado de desenvolvimento, ignorado pelo Git. O destino definitivo no servidor será `/mnt/dados/bronze`.
- **Passo anterior:** PASSO 8 — HD externo em `/mnt/dados`, ext4, montado por UUID
  - `/etc/fstab`: `UUID=b1b39d70-2712-436b-a7b8-aa1e80a1c0a0 /mnt/dados ext4 defaults,nofail,x-systemd.device-timeout=45 0 2`
  - **O timeout de 45 s não é enfeite:** com 10 s a montagem falhava no boot. O `udev` leva mais de 15 s para criar o link em `/dev/disk/by-uuid/` depois que o kernel anexa o disco, porque HDD por USB 2.0 é lento para sondar
  - Spin-down desativado de forma persistente em `/etc/hdparm.conf`, referenciando o disco por `/dev/disk/by-id/usb-JMicron_Generic_DD202505051001-0:0`
  - Estrutura criada: `bronze/`, `parquet/`, `backups/`, `minio/`, com dono `guilin`
  - **Pendência crítica para o PASSO 11:** todo `.service` que escreva em `/mnt/dados` precisa de `RequiresMountsFor=/mnt/dados`. Sem isso, se a montagem falhar (o `nofail` falha em silêncio), o job grava num diretório vazio **no disco interno** e enche o `sda` sem gerar erro
- **Passo anterior:** PASSO 7 — zram ativo e swap hierarquizado
  - `/dev/zram0`, algoritmo `zstd`, 4,8 GB (150% da RAM), **prioridade 100**; `/swap.img` de 3,7 GB no disco interno com prioridade `-1` como última instância. O kernel esgota a RAM comprimida antes de encostar no HDD
  - `/etc/sysctl.d/99-atlas-memoria.conf` com `vm.swappiness=100` e `vm.page-cluster=0` (desliga readahead de swap, que só faz sentido para amortizar seek de disco mecânico)
  - Número **alto** de propósito: em `sysctl.d`, como no systemd, o último valor vence — oposto do `sshd_config`
- **Passo anterior:** PASSO 6 — servidor sobrevivendo de tampa fechada. Validado com folga: **vários dias sem intervenção**, e `ssh servidor` funcionando de primeira depois
  - Drop-in `/etc/systemd/logind.conf.d/10-atlas-lid.conf` com as três diretivas `HandleLidSwitch*=ignore`; `unattended-upgrades` ativo com reboot manual (ADR-020); `lm-sensors` instalado — 44 °C em repouso, crítico em 100 °C, com folga enorme (revisitar sob carga real de containers)
  - **Pendência anotada para o Ansible (PASSO 13):** considerar `HandlePowerKey=ignore` no mesmo drop-in, para evitar desligamento acidental — hoje está no padrão (`poweroff`)
- **Último passo concluído:** PASSO 5 — `ssh servidor` entra só com passphrase; login por senha recusado (`Permission denied (publickey)`); VS Code Remote-SSH editando arquivo no servidor; teste de aprendizado respondido
  - Hardening em `/etc/ssh/sshd_config.d/01-atlas-hardening.conf`: senha, keyboard-interactive e root desabilitados. **Número baixo de propósito** — no `sshd_config` o *primeiro* valor vence, e o `50-cloud-init.conf` trazia `PasswordAuthentication yes`
  - **Cuidado com o VS Code Remote-SSH:** o VS Code Server roda no notebook (200–400 MB + extensões). Serve para editar config do servidor, **não** para hospedar a IDE de Python — o language server rodando em 2 núcleos e HDD é inviável. Código Python se escreve no PC (§4)
- **Rede — resolvido com hardware novo.** O ONT da operadora (ZTE F6600P, Canaã Telecom) não permite reserva de DHCP nem acesso admin (condicionado a plano pago). Solução: roteador **Huawei AX2S** como secundário atrás do ONT, com NAT duplo. Notebook em `192.168.3.6` (reserva de DHCP), acessado do PC via mapeamento de porta 22 na WAN do Huawei (`192.168.1.231`). Topologia completa em `docs/inventario-rede.md`, decisão em `docs/adr/019-roteador-secundario-e-acesso-ao-homelab.md`
  - **Consequência para os próximos passos:** todo serviço do homelab que precise ser acessado do PC (MinIO, Grafana, Postgres, FastAPI, Prometheus) exigirá uma **regra de mapeamento de porta** no Huawei, registrada no inventário. Isso vale até o ONT ir para modo bridge
  - O notebook fica alcançável na porta 22 por qualquer aparelho da rede doméstica — **não pela internet**. Torna obrigatórios: chave-só no SSH e `ufw` no notebook (hoje inativo)
- **Último passo concluído:** PASSO 4 — Ubuntu Server 26.04 minimized no notebook (`guilin@atlaslol`), boot em Legacy/CSM (Secure Boot desligado por limitação da BIOS Acer), OpenSSH Server instalado. `free -h` pós-boot: 450 Mi usado / 3,2 Gi total — dentro do critério
  - PASSO 3 fechado (repo, pastas, uv+ruff, git push na conta certa, extensão Remote-SSH) exceto o **conteúdo** do ADR-000, que o usuário escreve depois — o template já existe em `docs/adr/000-por-que-este-projeto-existe.md`
- **Objetivo declarado para o futuro:** **expor a API na internet para amigos testarem.** Isso ainda não existe, mas muda a postura de segurança quando acontecer — o servidor deixa de ser exclusivamente doméstico e passa a ser varrido por bots. Gatilho explícito no ADR-020 (ligar reboot automático) e implica encaminhamento de porta também no ONT, DNS dinâmico e revisão do ADR-019
- **Travado em:** nada
- **Hardware:** upgrade de SSD/RAM pendente · roteador Huawei AX2S adquirido para a rede do homelab
  - **Disco interno:** `sda`, 931,5 GB (ST1000LM024), SATA — onde o Postgres mora (ADR-001)
  - **HD externo:** `sdb`, **465,8 GB, HDD, USB 2.0** — perguntas do Apêndice D respondidas. O ADR-001 **não se inverte**: continua bronze/Parquet/backups no externo, Postgres no interno. Atenção ao tamanho: 500 GB é restrição real para a camada bronze
    - A gaveta é JMicron `152d:0578` (família JMS578, **capaz de USB 3.0**) e mesmo assim negociou `high-speed`. Provável limitação do cabo ou da porta usada — **vale testar uma porta azul antes de assumir 2.0 como teto**
    - Reporta `Disabling FUA` e `Write cache: enabled`: o sistema não consegue forçar escrita até o prato, e queda de energia pode perder dado já confirmado
  - **Bateria removida** em 2026-08-20 (ADR-021). Estava com 39% de desgaste e o kernel não expõe controle de carga. Consequência: **queda de energia agora é corte instantâneo**, sem desligamento gracioso. Próxima compra de infraestrutura é um **nobreak**
- **Riot API:** usando **personal key**, com limite informado de 20 requisições por segundo e 100 por 2 minutos.
  - O coletor usa ritmo conservador (~1,2 s entre inícios de requisição) e trata `429`, `503` e `Retry-After`.
  - **PASSO 11 liberado:** a chave pode ser guardada em `EnvironmentFile` do systemd, fora do repositório, para coleta automática.
- **Dado em disco:** na bancada local, 20 matches e 20 timelines em `bronze-local/`; no servidor, o timer já gravou a coleta inicial e incrementos em `/mnt/dados/bronze`.

---

## 12. Não invente — verifique

Estes pontos mudam com o tempo ou eu não tenho certeza. **Se forem relevantes, diga que precisam ser confirmados na documentação oficial em vez de afirmar um valor:**

- Janela de retenção do histórico de partidas na Riot API
- Data inicial de cobertura do MATCH-V5 e disponibilidade de timelines antigos
- Rate limits por método (podem ser mais restritivos que o de aplicação)
- Namespaces e versões de providers Terraform (`aminueza/minio`, `cyrilgdn/postgresql`)
- Suporte a state locking no backend S3 sem DynamoDB (mudou recentemente)
- Limites atuais do Oracle Cloud Always Free
- Quais serviços a edição community do LocalStack cobre
- Se o objeto `challenges` do MATCH-V5 já traz métricas por 10 min (isso decidiria se preciso de timeline para a coorte)

---

## 13. Erros que custam caro

1. Jogar o JSON bruto fora depois de converter — a janela de retenção não perdoa
2. Acumular tudo em memória num job de conversão → swap thrashing
3. Rodar os perfis `lake` e `ml` juntos → não cabe, e o OOM killer pode matar o Postgres
4. Container sem `mem_limit`
5. Criar coisas na UI e não importar para o Terraform → drift
6. `matchId` como label do Prometheus → explosão de cardinalidade
7. Split aleatório em dado temporal → vazamento
8. Backup nunca restaurado não é backup
9. Retry infinito em erro permanente (403/404)
10. Pular o teste de aprendizado porque "funcionou"

---

## 14. Formato de resposta que eu prefiro

- **Direto.** Sem preâmbulo, sem elogio à pergunta
- **Conceito primeiro, código depois**
- **Nomeie o trade-off** quando houver escolha
- **Diga quando não souber.** Prefiro "confirme na documentação" a um número inventado
- **Corrija-me quando eu estiver errado**, inclusive sobre decisões que já tomei
- Respostas curtas para perguntas curtas
