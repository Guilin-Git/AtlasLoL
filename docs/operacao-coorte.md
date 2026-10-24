# Operação da coorte do MVP

O fluxo de coorte não é ligado ao timer horário da conta de referência. Ele é
uma operação deliberada, limitada e auditável:

```text
descobrir candidatos → aprovar manifesto → coletar até N partidas → bronze/checkpoint
```

## 1. Descobrir e aprovar

No servidor, execute a descoberta com `--status approved` somente depois de
revisar a regra do pool. O parâmetro exige `--output`, evitando uma aprovação
que desapareça na saída do terminal. O `systemd-run` fornece o mesmo ambiente
restrito do coletor (usuário, diretório e segredo fora do repositório).

```bash
sudo systemd-run --wait --pipe --collect \
  --property=User=guilin --property=Group=guilin \
  --property=WorkingDirectory=/home/guilin/AtlasLoL \
  --property=EnvironmentFile=/etc/atlas/collector.env \
  --setenv=HOME=/home/guilin \
  /home/guilin/.local/bin/uv run python -m collector.coletar_coorte \
    "Like Bruce Wayne" "Ligui" --max-seeds 20 --min-games 20 \
    --status approved \
    --cohort-id mvp-br-master-grandmaster-20261024 \
    --output /mnt/dados/bronze/cohorts/aprovadas/mvp-br-master-grandmaster.json.zst
```

O arquivo contém somente metadados de descoberta e PUUIDs. O status
`approved` é a autorização explícita para a etapa seguinte.

## 2. Coletar de forma controlada

O coletor abaixo não instala nem altera timers. Por padrão, consulta uma
partida recente por semente, até 20 partidas únicas no total. Cada partida
reutiliza o rate limit, o checkpoint PostgreSQL e a deduplicação no bronze do
coletor principal.

```bash
sudo systemd-run --wait --pipe --collect \
  --property=User=guilin --property=Group=guilin \
  --property=WorkingDirectory=/home/guilin/AtlasLoL \
  --property=EnvironmentFile=/etc/atlas/collector.env \
  --setenv=HOME=/home/guilin \
  /home/guilin/.local/bin/uv run python -m collector.coletar_partidas_coorte \
    --manifest /mnt/dados/bronze/cohorts/aprovadas/mvp-br-master-grandmaster.json.zst \
    --matches-per-seed 1 --max-matches 20
```

Use valores maiores apenas após observar logs, espaço em disco e consumo da
quota Riot. O limite duro atual é 50 partidas por execução.
