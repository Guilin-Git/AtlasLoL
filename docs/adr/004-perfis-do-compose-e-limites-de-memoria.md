# ADR-004 — Perfis do Compose e limites de memória

Data: 2026-10-17

## Contexto

O servidor AtlasLoL possui cerca de 3,2 GiB de RAM útil e swap em zram antes
de recorrer ao HDD. Subir todos os componentes ao mesmo tempo transforma um
vazamento ou pico de memória de um serviço em risco para o host inteiro.

Os componentes planejados têm naturezas e orçamentos muito diferentes:
aplicação e banco (`core`), ingestão (`ingest`), lake (`lake`), observabilidade
(`obs`) e treino de modelos (`ml`). Em particular, `lake` e `ml` não cabem
juntos no orçamento do notebook.

## Alternativas consideradas

1. **Um Compose sem perfis, sempre subindo tudo.** Simples no começo, mas
   consome memória desnecessariamente e torna provável a disputa entre
   componentes incompatíveis.
2. **Um arquivo Compose por componente.** Evita subir tudo, mas duplica rede,
   variáveis e convenções; também dificulta enxergar o orçamento total.
3. **Um único Compose com perfis e limites explícitos.** Escolhida: centraliza
   a topologia e permite ativar apenas o conjunto necessário.
4. **Sem limites, confiando no OOM killer do host.** Descartada: quando o host
   fica sem memória, ele pode matar um processo saudável ou perder
   responsividade antes de escolher uma vítima.

## Decisão

Usar a Compose Specification em `infra/compose/compose.yaml`. Todo serviço
deve declarar `mem_limit`; limites de CPU e processos são adicionados quando
forem pertinentes ao serviço.

Os perfis planejados são `core`, `ingest`, `lake`, `obs` e `ml`. Eles recebem
serviços reais nos passos em que cada componente for implementado, em vez de
imagens-placeholder. O perfil temporário `test` contém apenas uma sonda que
tenta exceder 100 MiB; o teste só passa se o Docker informar `OOMKilled=true`.

`lake` e `ml` não devem ser ativados na mesma execução no notebook atual.

## Consequências

- `docker compose --profile <perfil> up -d` seleciona apenas o conjunto
  necessário.
- Um processo que excede seu orçamento é contido no cgroup do contêiner, sem
  transformar o host inteiro em swap thrashing.
- Cada novo serviço exige decisão explícita de orçamento antes de entrar no
  Compose.
- O arquivo começa pequeno e cresce junto com os passos 15, 16, 20, 30, 37 e
  38; nenhum serviço futuro é simulado agora.

## Gatilho de revisão

- Upgrade de RAM ou migração para servidor com recursos suficientes para
  `lake` e `ml` coexistirem.
- Migração dos serviços para Kubernetes, quando os limites passarão a ser
  declarados como requests e limits por workload.
