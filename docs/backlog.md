# Backlog do AtlasLoL

> Itens que melhoram o produto, mas não devem bloquear a primeira versão
> funcional. Atualize o status quando um item passar a fazer parte do MVP.

## Regra do MVP atual

Para colocar a comparação de pé, o AtlasLoL começa com um **pool simples de
candidatos**: jogadores da fila Solo/Duo na faixa ranqueada do jogador-semente
e na faixa imediatamente acima. Isso é uma regra operacional de coleta, não
uma afirmação de que todos possuem a mesma habilidade.

O MVP precisa provar este fluxo ponta a ponta:

```text
descobrir candidatos → coletar partidas → transformar métricas → comparar → exibir
```

## Próximos itens do MVP

- [ ] Coletar partidas das sementes aprovadas, reutilizando rate limit e
  checkpoint do coletor atual.
- [ ] Baixar Data Dragon por patch para interpretar campeões, itens e runas.
- [ ] Transformar um recorte bronze em métricas básicas por jogador, rota e
  campeão.
- [ ] Expor uma primeira comparação pela API: partidas, vitórias, KDA, CS/min e
  ouro/min, sempre indicando tamanho da amostra e patch.
- [ ] Criar uma interface mínima que apresente essa comparação.

## Melhorias da coorte após o MVP

- [ ] Substituir a regra fixa de faixa por uma coorte dinâmica filtrada por
  rota, campeão ou classe, patch, LP, recência e quantidade de partidas.
- [ ] Amostrar jogadores de forma estratificada, evitando selecionar apenas os
  maiores LP de uma página League-V4.
- [ ] Medir estabilidade da métrica e mostrar intervalo de confiança/tamanho da
  amostra em vez de produzir recomendações com poucos jogos.
- [ ] Avaliar proxies de habilidade além de tier/divisão/LP. MMR oculto não é
  fornecido pela API, portanto não será tratado como dado conhecido.
- [ ] Diferenciar estatísticas de Solo/Duo, Flex, normal e outros modos.

## Produto e contas de usuários

- [ ] Login por provedor (Google, Discord ou equivalente).
- [ ] Permitir que cada usuário vincule até duas contas Riot ativas.
- [ ] Criar atualização por demanda e agendamento para contas vinculadas, sem
  misturá-las com a coleta de coorte.
- [ ] Permitir busca pública de Riot IDs, com limites e política de privacidade.

## Dados profissionais e modelagem

- [ ] Ingerir CSVs do Oracle's Elixir como fonte profissional separada.
- [ ] Mostrar dados profissionais como contexto de meta, nunca como benchmark
  pessoal automático.
- [ ] Converter bronze em Parquet e criar camada analítica incremental.
- [ ] Desenvolver recomendações e modelos apenas depois de validar as métricas
  descritivas e a qualidade das amostras.

## Operação e segurança

- [ ] Automatizar deploy aprovado via GitHub Actions e runner interno.
- [ ] Adicionar métricas e alertas para erros de coleta, rate limit e espaço em
  disco.
- [ ] Rotacionar a senha PostgreSQL que foi exposta durante a depuração inicial.
