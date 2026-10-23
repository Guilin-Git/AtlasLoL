# ADR-023 — Checkpoint do coletor no PostgreSQL, bronze como fonte de verdade

Data: 2026-10-23

## Contexto

O coletor atual evita downloads repetidos pela existência de arquivos em
`/mnt/dados/bronze`. Isso é suficiente para o MVP de uma conta, mas não explica
operacionalmente o que ocorreu com cada `match_id`, não registra tentativas nem
permite distinguir uma falha transitória de um `404` permanente. Também torna
uma expansão para várias contas dependente de varreduras do disco como único
estado de execução.

O servidor já possui PostgreSQL, migrations versionadas e um timer `systemd`
que não sobrepõe execuções da mesma unit. O bronze precisa continuar imutável:
é o dado bruto recuperável que não deve ser substituído por um registro de
controle no banco.

## Alternativas consideradas

1. **Manter somente a existência do arquivo.** Sem schema novo e simples, mas
   não registra tentativas, versão do coletor, erro nem estado de falha
   permanente.
2. **Usar somente o checkpoint do banco.** Descartada: uma linha `complete`
   pode sobreviver a um arquivo removido, disco desconectado ou escrita que
   nunca chegou ao destino.
3. **Criar um SQLite ao lado do bronze.** Mantém o estado no disco externo, mas
   acrescenta outro banco, outra política de backup e uma recuperação menos
   integrada ao restante do produto.
4. **Usar PostgreSQL como checkpoint operacional e o bronze como fonte de
   verdade.** Escolhida.

## Decisão

Criar a tabela `collector_match_checkpoints`, identificada por `match_id`, com:

- `status`: `pending`, `complete` ou `permanent_failure`;
- patch e timestamps de persistência do match e timeline;
- contador e timestamps de tentativas;
- versão do coletor e último erro conhecido.

Para cada partida candidata, o coletor registra uma tentativa. Ele verifica os
arquivos bronze antes de chamar a Riot API e atualiza o checkpoint apenas após
cada escrita atômica. O estado `complete` significa que **match e timeline
existem no bronze** e foram reconhecidos pelo checkpoint. Se uma execução for
interrompida entre os dois sistemas, a execução seguinte reconcilia o arquivo
existente e termina o checkpoint sem baixar novamente.

Um `404` marca `permanent_failure`; erros transitórios preservam `pending`,
registram o erro e podem ser retomados pelo próximo timer. Uma linha marcada
como `complete` não substitui a checagem do arquivo: se ele estiver ausente, o
coletor o considera pendente novamente.

O rate limit será implementado como token bucket local, com um bucket para cada
janela retornada em `X-App-Rate-Limit`. Ele precede toda requisição e trabalha
junto com `Retry-After`; não haverá worker concorrente neste passo.

## Consequências

- O PostgreSQL passa a conter estado operacional leve, não cópias do JSON bruto.
- O bronze continua imutável e pode reconstruir o checkpoint se necessário.
- Uma migration adiciona schema; o coletor recebe a conexão ao PostgreSQL por
  variáveis de ambiente provisionadas pelo Ansible, nunca por segredo no Git.
- As consultas de checkpoint acrescentam pouco I/O ao PostgreSQL e evitam gasto
  desnecessário da cota da Riot API.
- Ainda não há fila distribuída ou coordenação entre vários processos usando a
  mesma chave Riot. O timer atual não sobrepõe a própria unit; concorrência real
  é um gatilho para rever esta decisão.

## Gatilho de revisão

- Mais de uma instância do coletor executando em paralelo.
- Necessidade de distribuir milhares de `match_id` entre workers.
- Necessidade de retentar itens em horários próprios, e não no próximo ciclo
  horário do timer.
- Separação de privilégios do PostgreSQL entre API, coletor e migrations.
