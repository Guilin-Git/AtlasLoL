# API — Passo 16

Esta pasta contém a API FastAPI e as migrations do PostgreSQL.

## O que já está preparado

- `atlas_api/main.py`: aplicação HTTP e `GET /health`;
- `atlas_api/logging.py`: uma linha JSON por requisição, com `X-Correlation-ID`;
- `atlas_api/database.py`: conexão curta ao PostgreSQL para o healthcheck;
- `migrations/`: estrutura do Alembic e a primeira migration de identidade e
  catálogo Riot.

## Próxima prática do passo

1. Aplicar, reverter e reaplicar a migration no banco de desenvolvimento.
2. Criar endpoints de leitura para o catálogo público de contas Riot.
3. Executar a API localmente e verificar `GET /health`.

O endereço do banco usa `ATLAS_DATABASE_URL`. Ele fica no `.env` local ou,
no servidor, em um arquivo de segredo provisionado pelo Ansible. A senha nunca
entra neste README, no compose ou no Git.
