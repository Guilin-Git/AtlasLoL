# ADR-024: PostgreSQL acessível somente no host via localhost

- **Status:** Aceito
- **Data:** 2026-10-23

## Contexto

O PostgreSQL atende dois consumidores distintos no AtlasLoL:

1. a API, que roda na mesma rede interna do Docker e acessa o serviço pelo
   nome `postgres`;
2. o coletor, que roda como serviço `systemd` no host e usa
   `127.0.0.1:5432`.

Inicialmente a porta foi publicada em `192.168.3.6:5432` para permitir um
teste de conexão a partir do PC. Isso abriu o banco para toda a rede local e
deixou o coletor apontando para uma interface diferente da publicada. O
resultado foi a falha de conexão do checkpoint antes de qualquer requisição
à Riot API.

## Decisão

Publicar a porta do PostgreSQL somente em `127.0.0.1:5432` no servidor.

- A API continua usando `postgres:5432` na rede Docker, sem depender da porta
  publicada no host.
- O coletor usa `127.0.0.1:5432`, que passa a coincidir com a publicação.
- A administração remota, quando necessária, deve usar um túnel SSH, por
  exemplo: `ssh -L 5432:127.0.0.1:5432 guilin@192.168.3.6`.

## Consequências

- A senha do banco deixa de estar acessível a outros equipamentos da rede
  doméstica pela porta 5432.
- O coletor pode persistir checkpoints sem depender do IP LAN do servidor.
- Clientes externos não conectam mais diretamente a `192.168.3.6:5432`; o
  túnel SSH passa a ser a rota administrativa explícita e autenticada.
- O Compose recriará somente o container PostgreSQL quando esta configuração
  for aplicada. O volume `postgres-data` não é removido.
