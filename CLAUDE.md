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

- **Passo atual do MANUAL:** PASSO 5 — acesso remoto confortável (a começar)
- **Último passo concluído:** PASSO 4 — Ubuntu Server minimized instalado no notebook (`guilin@atlaslol`), boot em Legacy/CSM (Secure Boot desligado por limitação da BIOS Acer), Wi-Fi (`GUILYN`), OpenSSH Server instalado, senha SSH liberada temporariamente para o `ssh-copy-id` do PASSO 5. `free -h` pós-boot: 450 Mi usado / 3,2 Gi total — dentro do critério
  - PASSO 3 fechado (repo, pastas, uv+ruff, git push na conta certa, extensão Remote-SSH) exceto o **conteúdo** do ADR-000, que o usuário escreve depois — o template já existe em `docs/adr/000-por-que-este-projeto-existe.md`
- **Travado em:** nada
- **Hardware:** upgrade de SSD/RAM pendente · HD externo: _(confirmar USB 2.0 ou 3.0, HDD ou SSD)_
- **Riot API:** usando **dev key** (expira em 24h, renovação manual com CAPTCHA). Personal key será solicitada mais tarde — decisão consciente.
  - **Consequência:** o PASSO 11 (coleta automática por systemd timer) fica limitado até lá. **Não sugira agendamento que dependa de chave permanente.**
  - Enquanto isso, a coleta é manual: colar a chave nova em `EnvironmentFile` e rodar uma sessão a cada 2–3 dias.
- **Dado em disco:** nenhum

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
