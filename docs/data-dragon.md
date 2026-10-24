# Catálogo Data Dragon

O Data Dragon é uma fonte estática oficial da Riot, independente da API de
partidas e sem chave pessoal. O coletor consulta `versions.json` diariamente e
baixa o catálogo completo apenas quando encontra uma versão ainda ausente.

## Armazenamento

```text
/mnt/dados/bronze/static/ddragon/
  version=16.21.1/
    locale=pt_BR/
      champion.json.zst
      item.json.zst
      runesReforged.json.zst
      summoner.json.zst
      manifest.json.zst
```

O catálogo nunca é sobrescrito por uma versão posterior. A camada analítica
deve resolver a versão da partida `16.21` para o catálogo `16.21.x` baixado,
preservando o significado de itens e campeões no patch original.

## Atualização

O `atlas-ddragon.timer` roda diariamente às 04:15 no horário do servidor,
com `Persistent=true`. Se o servidor estiver desligado nesse horário, o
systemd executa a verificação no próximo boot.

Para testar sob demanda:

```bash
sudo systemctl start atlas-ddragon.service
sudo journalctl -u atlas-ddragon.service -n 30 --no-pager
```

O primeiro teste baixa uma versão; execuções posteriores escrevem
`já presente; ignorada` até que a Riot publique um patch novo.
