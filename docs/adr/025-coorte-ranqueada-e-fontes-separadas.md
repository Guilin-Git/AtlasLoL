# ADR-025: Coorte ranqueada local e fontes de comparação separadas

- **Status:** Aceito
- **Data:** 2026-10-24

## Contexto

O AtlasLoL quer comparar uma pessoa com jogadores próximos de sua realidade e,
em outra visão, usar dados profissionais para entender meta e tendências. Essas
amostras não têm a mesma finalidade nem devem ser misturadas como benchmark.

## Decisão

1. Descobrir sementes da coorte BR usando League-V4 na fila `RANKED_SOLO_5x5`.
   A coorte inicial é a faixa do jogador e a faixa imediatamente acima (por
   exemplo, `SILVER IV` e `SILVER III`).
2. Guardar PUUID, tier, divisão, LP, vitórias e derrotas como metadados de
   descoberta. PUUID é estável; nomes Riot podem mudar.
3. A descoberta apenas gera uma lista pequena e revisável de sementes. Ela não
   altera o timer atual nem coleta partidas em massa.
4. Dados profissionais entram em carga independente a partir dos CSVs do
   Oracle's Elixir. Eles servem para meta/modelagem, não para recomendar que um
   jogador comum copie diretamente os números de um profissional.
5. Data Dragon será baixado por patch como dimensão estática de campeões, itens
   e runas.

## Consequências

- O timer do coletor permanece responsável pela conta de validação até existir
  um agendador explícito para coorte e contas de usuários.
- A primeira execução de descoberta é limitada a 20 sementes e não consome
  chamadas Match-V5.
- A futura coleta das sementes reutilizará a política de rate limit,
  checkpoint e deduplicação já validada no coletor.
