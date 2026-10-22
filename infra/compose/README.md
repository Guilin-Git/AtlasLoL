# Docker Compose do AtlasLoL

O perfil `core` contem PostgreSQL e API. A API e construida do repositorio,
recebe sua conexao por `/etc/atlas/api.env`, tem um unico worker Uvicorn e
limite de 256 MiB. Ela publica HTTP somente em `192.168.3.6:8000`, a rede
local do homelab; nenhuma regra de port-forward no roteador e criada.

Este diretório concentra os serviços em contêiner do AtlasLoL. Cada serviço
deve declarar `mem_limit`; o notebook-servidor tem cerca de 3,2 GiB de RAM
útil e não pode depender do OOM killer do host como mecanismo de contenção.

## Perfis planejados

| Perfil | Serviços que entrarão nele | Orçamento aproximado |
| --- | --- | --- |
| `core` | Postgres e API | 600 MiB |
| `ingest` | coletor e NATS JetStream | 300 MiB |
| `lake` | MinIO e jobs de transformação | 1,4 GiB |
| `obs` | Prometheus, Grafana e Loki | 900 MiB |
| `ml` | treino de modelos | 1,5 GiB+ |

O perfil `core` já possui o PostgreSQL do PASSO 15. A API entrará nele no PASSO
16. Os demais perfis receberão serviços quando estes forem implementados nos
passos correspondentes; não há placeholders para API, NATS ou MinIO, porque
subir uma imagem sem configuração real esconderia decisões futuras.

## Teste de contenção de memória

O perfil `test` contém somente `memory-limit-probe`. Ele tenta alocar memória
indefinidamente com limite de 100 MiB e sem swap permitido ao contêiner. O
script `test-memory-limit.sh` espera exit code `137` e `OOMKilled=true`, depois
remove o contêiner de teste. Isso prova que um processo fora do orçamento morre
sem consumir toda a memória do notebook.

O teste usa o projeto Docker isolado `atlaslol-memory-probe`; sua limpeza nunca
remove contêineres dos perfis reais do AtlasLoL.

Execute o teste no servidor somente após o Compose estar instalado:

```bash
cd /home/guilin/AtlasLoL/infra/compose
bash test-memory-limit.sh
```
