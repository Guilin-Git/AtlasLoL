# Docker Compose do AtlasLoL

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

Os perfis só receberão serviços quando estes forem implementados nos passos
correspondentes. Não há placeholders para Postgres, API, NATS ou MinIO: subir
uma imagem sem configuração real esconderia decisões que pertencem aos passos
15, 16, 20 e 30.

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
