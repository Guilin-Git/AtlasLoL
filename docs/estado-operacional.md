# Estado operacional do AtlasLoL

> Documento vivo. Atualize-o após cada mudança que altere serviços em execução,
> dados persistidos, rede, automações, segredos ou o fluxo entre componentes.
>
> Última atualização: 2026-10-23 — checkpoint do coletor validado no servidor.

## 1. Visão atual

O AtlasLoL é um homelab de análise de League of Legends. O PC com WSL é a
bancada de desenvolvimento e o controlador do Ansible; o notebook `atlaslol`
é o servidor local que coleta dados, executa PostgreSQL e entrega a API.

```text
PC / WSL                         GitHub                  atlaslol (192.168.3.6)
────────                         ──────                  ─────────────────────
código + Ansible ──────────────► main ────────────────► /home/guilin/AtlasLoL
                                                            │
                                                            ├─ timer: coletor Riot
                                                            │     └─ /mnt/dados/bronze
                                                            │
                                                            ├─ Compose, perfil core
                                                            │     ├─ PostgreSQL :5432
                                                            │     └─ FastAPI :8000
                                                            │
                                                            └─ timer: backup PostgreSQL
                                                                  └─ /mnt/dados/backups/postgres
```

## 2. Infraestrutura e armazenamento

| Recurso | Local | Uso atual | Estado |
| --- | --- | --- | --- |
| Bancada | PC principal com WSL | Código, testes e execução do Ansible | Ativo |
| Servidor | Notebook `atlaslol`, IP `192.168.3.6` | Coletor, containers e timers | Ativo |
| Repositório no servidor | `/home/guilin/AtlasLoL` | Cópia de `main` sincronizada pelo Ansible | Ativo |
| Disco externo | `/mnt/dados` | Bronze, Parquet futuro, backups e MinIO futuro | Ativo |
| Disco interno | volume Docker `postgres-data` | Dados persistentes do PostgreSQL | Ativo |
| zram + swap em disco | `/dev/zram0` e `/swap.img` | Proteção contra falta de memória | Ativo |

O PostgreSQL permanece no disco interno por demandar I/O aleatório de baixa
latência. Os dados grandes e sequenciais permanecem no disco externo.

## 3. Serviços em execução

| Serviço | Tecnologia | Inicialização | Responsabilidade | Limites/observações |
| --- | --- | --- | --- | --- |
| Coletor | Python + `uv` + systemd | `atlas-collector.timer`, a cada hora | Consulta partidas recentes da Riot e grava dados crus | Até 20 partidas do Riot ID configurado; chave pessoal |
| PostgreSQL | `postgres:17.11-alpine3.24` em Compose | `restart: unless-stopped` | Banco transacional e catálogo local | 384 MiB, 0,75 CPU, 20 conexões |
| API | FastAPI/Uvicorn em Compose | `restart: unless-stopped` | Healthcheck e consultas ao catálogo local | 256 MiB, 0,50 CPU, um worker |
| Backup PostgreSQL | systemd | diariamente às 03:15 UTC, com até 10 min de atraso aleatório | Backup lógico e retenção no disco externo | `atlas-postgres-backup.timer` |

Os containers pertencem ao perfil Compose `core`. A API só inicia depois que o
healthcheck do PostgreSQL está saudável. Antes de subir a API, o Ansible aplica
as migrations Alembic.

## 4. Fluxo de dados atual

```text
Riot API
   │
   ▼
coletor horário ──► checkpoint operacional no PostgreSQL
   │
   └─────────────► partidas e timelines `.json.zst` ──► bronze no disco externo

cliente na rede local ──► FastAPI :8000 ──► PostgreSQL
```

O fluxo analítico entre bronze e PostgreSQL ainda não existe. Atualmente:

1. O coletor busca partidas recentes do Riot ID configurado.
2. Partidas e timelines inéditas são gravadas em `/mnt/dados/bronze` no formato
   JSON comprimido com Zstandard (`.json.zst`).
3. Antes de baixar uma partida, o coletor registra sua tentativa em
   `collector_match_checkpoints`. Ao concluir ambos os artefatos, marca o item
   como `complete`; um `404` é marcado como `permanent_failure`.
4. O bronze continua sendo a fonte de verdade: se um artefato faltar, ele é
   baixado novamente mesmo que o checkpoint anterior exista.
5. A API consulta somente PostgreSQL; ela não consome o bronze e não chama a
   Riot API por requisição.
6. Portanto, uma conta Riot ainda precisa ser inserida no catálogo local para
   que uma busca pela API não retorne `404`.

## 5. Banco e API

Migration atual: `20261023_002`.

| Grupo | Tabelas | Finalidade |
| --- | --- | --- |
| Identidade interna | `app_users`, `user_emails`, `auth_identities` | Usuários, e-mails e futuros provedores como Google ou Discord |
| Catálogo Riot | `riot_accounts` | Perfil pesquisável por PUUID ou Riot ID |
| Vínculos | `user_riot_account_links` | Relação entre um usuário Atlas e contas Riot que ele adiciona ao dashboard |
| Operação do coletor | `collector_match_checkpoints` | Estado persistente por partida para retomar coleta, deduplicar e registrar falhas permanentes |

Endpoints atualmente implantados:

| Método e rota | Uso | Estado |
| --- | --- | --- |
| `GET /health` | Confirma saúde da API e conectividade com PostgreSQL | Validado: `{"status":"ok","database":"ok"}` |
| `GET /riot-accounts/search?game_name=...&tag_line=...` | Busca conta no catálogo local | Implementado; retorna `404` enquanto não catalogada |
| `GET /riot-accounts/{puuid}` | Busca conta pelo identificador Riot estável | Implementado; retorna `404` enquanto não catalogada |

Não há autenticação de usuário, sessão ou OAuth implementados ainda. O schema
foi desenhado para receber esses recursos sem redesenhar as entidades centrais.

## 6. Rede e acesso

| Serviço | Endereço atual | Escopo |
| --- | --- | --- |
| SSH | `192.168.3.6:22` | Rede doméstica; somente chave SSH |
| PostgreSQL | `127.0.0.1:5432` no servidor | Não exposto à rede; administração remota somente por túnel SSH |
| FastAPI | `192.168.3.6:8000` | Rede local; healthcheck validado |

Não há exposição pública da API. Antes de qualquer port-forward para a
internet, revisar autenticação, firewall, TLS, banco exposto e a política de
reboot automático descrita no ADR-020.

## 7. Automação, configuração e segredos

O Ansible roda sob demanda no WSL do PC e configura o servidor por SSH. Ele não
é um serviço residente no notebook.

| Item | Origem | Destino no servidor | Proteção |
| --- | --- | --- | --- |
| Chave Riot | Ansible Vault | `/etc/atlas/collector.env` | `root:root`, `0600` |
| Senha PostgreSQL | Ansible Vault | `/etc/atlas/postgres.env` | `root:root`, `0600` |
| Conexão da API | Ansible Vault | `/etc/atlas/api.env` | `root:root`, `0600` |
| Código | GitHub, branch `main` | `/home/guilin/AtlasLoL` | Atualizado pela role `runtime` |

O playbook principal é `infra/ansible/site.yml`. Ele garante acesso, memória,
armazenamento, Docker, atualizações, runtime, PostgreSQL, API, Compose e
coletor.

## 8. Evidências de validação

| Data | Validação | Resultado |
| --- | --- | --- |
| 2026-10-16 | Timer do coletor executado por horas consecutivas | Coletou somente partidas inéditas; sem falhas |
| 2026-10-18 | Backup e restauração de PostgreSQL | Teste concluído pelo playbook sob demanda |
| 2026-10-22 | Migration `upgrade → downgrade base → upgrade` | Terminou em `20261022_001 (head)` no PostgreSQL do servidor |
| 2026-10-22 | API local com Uvicorn | `/health` e `/docs` validados contra o banco do servidor |
| 2026-10-22 | Implantação da API via Ansible | Migration, container e healthcheck concluídos; `/health` validado pela rede local |
| 2026-10-23 | Checkpoint do coletor e bind local do PostgreSQL | Migration `20261023_002` aplicada; coleta automática e controlada encerraram com `codigo_saida: 0` |

## 9. Próximas evoluções

1. Criar ingestão do bronze para o catálogo `riot_accounts` e para a camada
   analítica.
2. Definir a descoberta e atualização de contas de proplayers, respeitando os
   limites da Riot API.
3. Criar tabelas analíticas de partidas e métricas, preferencialmente com
   Parquet para dados volumosos.
4. Implementar autenticação e autorização quando houver fluxos reais de
   usuário, incluindo a escolha de Google, Discord ou outro provedor.
5. Adicionar observabilidade antes de aumentar o número de serviços.

## 10. Como atualizar este documento

Ao concluir uma mudança, atualize apenas as seções afetadas e acrescente uma
linha em **Evidências de validação** quando a mudança for aplicada e testada no
servidor. Registre também:

- serviço novo, removido ou alterado;
- porta, limite de memória/CPU ou dependência alterada;
- novo local de dado persistente ou política de backup;
- mudança no fluxo de dados;
- requisito de segurança ou exposição de rede;
- decisão que muda as próximas etapas.

Detalhes de decisões ficam nos ADRs; este arquivo descreve o estado operacional
atual, não substitui os ADRs nem o plano do projeto.
