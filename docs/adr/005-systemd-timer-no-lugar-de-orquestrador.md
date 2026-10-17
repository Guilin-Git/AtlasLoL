# ADR-005 — Systemd timer no lugar de orquestrador

Data: 2026-10-16

## Contexto

O coletor da Riot API precisa executar de forma recorrente no notebook servidor,
sem depender de uma pessoa lembrar de iniciá-lo. O servidor tem 4 GB de RAM, dois
núcleos físicos e HDD mecânico; serviços residentes precisam justificar o custo.

No MVP atual existe um único job sequencial: consultar as partidas recentes da
conta pessoal, baixar apenas match e timeline ausentes e terminar. O coletor já é
idempotente, trata rate limit e grava de forma atômica em `/mnt/dados/bronze`.

O agendamento também é um exercício de infraestrutura: entender unit, service,
timer, dependências, logs e recuperação após reboot. Neste laboratório, o
systemd timer ocupa o papel conceitual do EventBridge Scheduler na AWS.

## Alternativas consideradas

1. **Execução manual.** Simples, mas depende de memória humana e não garante que
   o acervo cresça continuamente.
2. **Cron.** Leve e suficiente para disparar um comando, mas exigiria soluções
   adicionais para logs, dependência do mount, recuperação de horários perdidos
   e prevenção de sobreposição.
3. **Systemd timer.** Integra estado, journal, dependências, boot e execução sob
   usuário específico sem manter outro processo residente.
4. **Dagster.** Oferece orquestração, assets, sensores e backfills, mas esse
   problema ainda não tem um grafo de jobs que justifique o consumo de memória e
   a complexidade operacional.
5. **Fila de mensagens.** Será útil quando requisições de múltiplos usuários
   produzirem trabalho assíncrono, mas uma fila não substitui por si só um
   agendador e hoje não há produtores ou consumidores concorrentes.

## Decisão

Adotar um `systemd timer` horário para acionar o coletor da conta pessoal no MVP.
O serviço é `oneshot`, executa como `guilin`, lê a chave de um `EnvironmentFile`
fora do repositório e declara `RequiresMountsFor=/mnt/dados` antes de escrever no
bronze.

É a menor solução que cobre o problema atual por inteiro: agenda, volta após
reboot, registra logs, conhece o estado da execução e não inicia outra instância
da mesma unit enquanto ela ainda está ativa. Se uma coleta ultrapassar o próximo
horário, aquele disparo não cria uma segunda coleta concorrente; ele também não
fica enfileirado para execução posterior.

Esta decisão vale apenas para a coleta recorrente de uma conta conhecida no MVP.
Ela não define a arquitetura final de múltiplos usuários, que exigirá trabalho
sob demanda e provavelmente uma fila. A base profissional de campeonatos terá
pipeline separado, alimentado principalmente pelo Oracle's Elixir.

## Consequências

- Não há daemon adicional consumindo memória; o coletor mediu cerca de 43 MB no
  pico e termina após cada execução.
- Logs e códigos de saída ficam centralizados no journal. O timer voltou ativo
  após reboot e a coleta incremental foi observada no servidor.
- `RequiresMountsFor=/mnt/dados` faz a execução falhar em vez de gravar
  silenciosamente no disco interno quando o HD externo não estiver montado.
- A mesma unit não é executada em paralelo. Em troca, um disparo ocorrido durante
  uma execução longa não representa uma mensagem durável e pode ser perdido.
- Mesmo sem partida nova, cada hora consome as chamadas de resolução da conta e
  consulta do histórico. O custo é pequeno para a personal key, mas a frequência
  deve ser revista se a quantidade de contas crescer.
- A configuração foi feita manualmente de propósito. Até o PASSO 13 existe risco
  de drift; depois, service, timer e segredo serão gerenciados por Ansible, com o
  segredo protegido por `ansible-vault`.

## Gatilho de revisão

- Entrada de múltiplos usuários ou necessidade de coleta sob demanda.
- Picos de solicitações que precisem ser amortecidos e distribuídos entre workers.
- Execuções frequentemente maiores que o intervalo, tornando perda de disparos
  um problema real.
- Vários pipelines com dependências, backfills coordenados, sensores ou interface
  operacional — momento de avaliar um orquestrador.
- Necessidade de garantia durável por item — momento de introduzir NATS JetStream
  ou equivalente, sem confundir fila com agendador.
