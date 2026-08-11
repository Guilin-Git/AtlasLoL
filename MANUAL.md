# Manual de Montagem — Projeto Atlas

**Plataforma de análise de performance em League of Legends como laboratório de infraestrutura, engenharia de dados e ciência de dados.**

---

## Como usar este manual

Este documento funciona como instrução de LEGO: **caixas** agrupam peças relacionadas, e dentro de cada caixa os **passos são numerados em ordem**. Cada passo é pequeno o suficiente para caber em uma ou duas sessões de estudo.

Cada passo tem sempre a mesma estrutura:

- **Objetivo** — o que existe no final que não existia antes
- **Estudar antes** — o mínimo necessário, não a bibliografia completa
- **Fazer** — as ações concretas
- **Teste de funcionamento** — prova objetiva de que funciona
- **Teste de aprendizado** — pergunta que você responde sem consultar nada
- **Só avance quando** — a condição de saída

### As cinco regras do manual

1. **Nunca duas coisas novas ao mesmo tempo.** Se você está aprendendo Terraform, use um serviço que já domina. Se está subindo um serviço novo, faça na mão primeiro.
2. **O teste de aprendizado é obrigatório.** Se você não consegue responder, o passo não terminou — mesmo que funcione. Funcionar sem entender é o modo mais fácil de desperdiçar o projeto.
3. **Não pule para a caixa seguinte por ansiedade.** A ordem foi otimizada para que cada peça tenha onde se encaixar. Pular gera retrabalho.
4. **Cada decisão relevante gera um ADR** (arquivo curto: contexto, alternativas, escolha, consequências, o que me faria mudar de ideia). No fim, os ADRs valem mais que o código.
5. **Se travar mais de duas sessões no mesmo ponto,** anote onde parou, pule para o passo seguinte que seja independente, e volte depois. Travar é normal; parar o projeto por travar não.

### Peso dos passos

`LEVE` = uma sessão · `MÉDIO` = duas a quatro sessões · `PESADO` = uma semana ou mais de estudo

---

# CAIXA 0 — Antes de tocar em qualquer hardware

Esta caixa existe porque duas coisas aqui têm prazo externo e travam o resto se ficarem para depois.

---

## PASSO 1 — Solicitar a chave da Riot API `LEVE`

**Faça isto hoje, antes de qualquer outra coisa.**

**Objetivo:** ter uma chave permanente antes de precisar dela.

**Fazer**
1. Criar conta no portal de desenvolvedores da Riot
2. Gerar a **development key** (funciona imediatamente, mas expira a cada 24h e tem limite baixo)
3. Registrar um projeto e solicitar a **personal key** — gratuita, permanente, limite maior

**Por que primeiro:** a aprovação da personal key demora (dias a semanas). Se você deixar para quando o pipeline estiver pronto, vai ficar parado esperando.

**Estudar antes**
- Diferença entre development, personal e production key
- Onde ficam documentados os rate limits (números variam e mudam; não confie em valores decorados)
- Qual a janela de retenção do histórico de partidas na API — **confirme na documentação**, porque partida fora dessa janela deixa de existir para você, permanentemente

**Teste de aprendizado**
- Por que a existência de janela de retenção significa que coletar é urgente mesmo sem pressa no projeto?

**Só avance quando:** a solicitação estiver enviada. Não precisa esperar a aprovação para continuar — a development key serve para os primeiros testes.

---

## PASSO 2 — Diagnóstico do hardware `LEVE`

**Objetivo:** saber se o notebook aguenta o plano ou se precisa de upgrade antes de começar.

**Fazer**

```bash
# Slots de memória — o ES1-572 aparece com 1 e com 2 slots
sudo dmidecode -t memory | grep -E "Size|Locator|Maximum|Speed"

# Saúde do HDD — máquina de 2016 que vai ficar ligada 24/7
sudo apt install smartmontools
sudo smartctl -a /dev/sda | grep -E "Reallocated|Pending|Power_On_Hours"
```

Anote também: o HD externo é **USB 2.0 ou 3.0**, e é **HDD ou SSD**?

**Interpretação**
- Setores realocados ou pendentes > 0 → o disco está morrendo. SSD deixa de ser otimização e passa a ser pré-requisito
- Slot livre → +8 GB DDR3L custa pouco no mercado usado
- HD externo sendo **SSD por USB 3.0** → o Postgres pode morar nele, e o HDD interno fica só com o sistema
- HD externo sendo HDD → Postgres fica no disco interno, e o externo recebe só dado grande e sequencial

**Teste de aprendizado**
- Por que um HDD é ruim para banco de dados e aceitável para arquivos Parquet? (Dica: leitura aleatória contra leitura sequencial)

**Só avance quando:** você souber se vai fazer upgrade e onde cada tipo de dado vai morar.

---

## PASSO 3 — Bancada no PC principal `LEVE`

**Objetivo:** ambiente de trabalho pronto no PC, antes de mexer no servidor.

**Fazer**
1. Repositório Git criado, com `README` e `.gitignore`
2. Estrutura de pastas inicial:
   ```
   atlas/
     collector/
     api/
     infra/
       ansible/
       terraform/
     data/
     notebooks/
     docs/adr/
   ```
3. Python com gerenciador de ambiente (`uv` ou `poetry` — escolha um)
4. Docker Desktop ou Docker Engine funcionando
5. VS Code com a extensão **Remote SSH** instalada
6. Primeiro ADR escrito: **ADR-000 — por que este projeto existe e qual o critério de sucesso**

**Estudar antes**
- Git: branch, commit, PR (se já usa no trabalho, pule)
- Diferença entre imagem e container no Docker

**Teste de aprendizado**
- Por que escrever o ADR-000 antes de qualquer código?

**Só avance quando:** você conseguir dar `git push` e o repositório estar organizado.

---

# CAIXA 1 — O servidor de pé

Nesta caixa você faz tudo **à mão**, de propósito. Na Caixa 3 você vai transformar tudo isso em código Ansible — e só dá valor à automação quem sofreu fazendo manual primeiro.

---

## PASSO 4 — Instalar Ubuntu Server `LEVE`

**Objetivo:** notebook rodando Linux sem interface gráfica.

**Fazer**
1. Ubuntu Server LTS em pendrive
2. Instalação mínima, **sem desktop** — interface gráfica come RAM que você não tem
3. Marcar "instalar OpenSSH Server" durante a instalação
4. Usuário criado, senha anotada

**Estudar antes**
- Por que server e não desktop
- O que é LTS

**Teste de funcionamento:** o notebook liga, você faz login no console e `free -h` mostra menos de 500 MB em uso.

**Só avance quando:** o sistema bootar sozinho até o login.

---

## PASSO 5 — Acesso remoto confortável `LEVE`

**Objetivo:** nunca mais precisar do teclado e da tela do notebook.

**Fazer**
1. Reservar **IP fixo** para o notebook no roteador (por MAC address)
2. No PC: `ssh-keygen -t ed25519`
3. `ssh-copy-id usuario@ip-do-notebook`
4. Criar um atalho em `~/.ssh/config`:
   ```
   Host servidor
     HostName 192.168.0.X
     User seu-usuario
   ```
5. Testar: `ssh servidor` deve entrar sem pedir senha
6. Desabilitar login por senha no `sshd_config` (só chave)
7. Abrir a pasta do servidor pelo VS Code Remote SSH

**Estudar antes**
- Criptografia de chave pública, no nível de intuição: por que a chave privada nunca sai do seu PC
- O que o DHCP faz e por que sem IP fixo você perde o servidor

**Teste de funcionamento:** `ssh servidor` entra direto, e login por senha é recusado.

**Teste de aprendizado**
- Se alguém roubar o arquivo `authorized_keys` do servidor, consegue entrar? Por que não?

**Só avance quando:** você editar um arquivo do servidor pelo VS Code do PC.

---

## PASSO 6 — Sobreviver como servidor `LEVE`

**Objetivo:** tampa fechada, ligado 24/7, sem suspender e sem risco.

**Fazer**
1. `/etc/systemd/logind.conf`: `HandleLidSwitch=ignore` e `HandleLidSwitchExternalPower=ignore`
2. Reiniciar o `systemd-logind`
3. Ativar `unattended-upgrades`
4. Verificar se o kernel expõe limite de carga da bateria:
   ```bash
   ls /sys/class/power_supply/BAT*/charge_control_end_threshold
   ```
   Se existir, limitar a ~60%. Célula de 2016 carregando a 100% eternamente incha — e isso é risco real de incêndio, não exagero
5. Monitorar temperatura (`lm-sensors`) — o chassi não foi feito para 24/7

**Teste de funcionamento:** fechar a tampa, esperar 15 minutos, conectar por SSH do PC.

**Só avance quando:** o servidor sobreviver a uma noite inteira com a tampa fechada.

---

## PASSO 7 — Memória e swap `MÉDIO`

**Objetivo:** que a falta de RAM cause degradação, não congelamento.

**Fazer**
```bash
sudo apt install zram-tools
# /etc/default/zramswap → PERCENT=150, ALGO=zstd
sudo sysctl vm.swappiness=100
```
Mais 4 GB de swap em arquivo, como rede de última instância.

**Estudar antes** — esta é a parte conceitual mais importante da caixa
- O que é swap e por que swap em HDD é catastrófico (não 20% mais lento: **50 a 100 vezes**)
- O que é zram: swap comprimido dentro da RAM, sem tocar no disco
- Por que `swappiness=100` é correto com zram e péssimo com swap em disco
- O que o **OOM killer** faz, e por que ele pode matar o Postgres em vez do processo culpado

**Teste de funcionamento:** `zramctl` mostra o dispositivo ativo e `swapon --show` lista zram com prioridade maior que o arquivo.

**Teste de aprendizado**
- Explique, sem consultar, por que um processo que aloca 3 GB nesta máquina pode travar o servidor inteiro em vez de só morrer.

**Só avance quando:** você conseguir explicar a diferença entre "ficar lento" e "entrar em thrashing".

---

## PASSO 8 — HD externo montado para valer `MÉDIO`

**Objetivo:** armazenamento grande, confiável e que sobrevive a reboot.

**Fazer**
1. Formatar em **ext4** (não deixar NTFS — dá problema de permissão e performance no Linux)
2. Descobrir o UUID: `blkid`
3. Montar **por UUID** no `/etc/fstab`, nunca por `/dev/sdb1` — se a letra trocar num reboot, seus serviços apontam para o vazio
4. Desativar spin-down. HD externo hiberna sozinho depois de minutos parado, e a primeira leitura seguinte trava alguns segundos — em servidor isso vira erro
5. Criar a estrutura:
   ```
   /mnt/dados/
     bronze/     # JSON cru da Riot
     parquet/    # silver e gold
     backups/    # dumps do Postgres
     minio/      # volume do MinIO (Caixa 5)
   ```

**Estudar antes**
- O que é `fstab` e o que a opção `nofail` evita
- Por que UUID e não caminho de dispositivo
- Diferença entre sistema de arquivos e partição

**Teste de funcionamento:** reiniciar o servidor remotamente; após o boot, `df -h` mostra o HD montado no caminho certo, sem intervenção.

**Teste de aprendizado**
- O que acontece com o boot se o HD externo estiver desconectado e o `fstab` não tiver `nofail`?

**Só avance quando:** o disco sobreviver a três reboots seguidos.

**ADR-001** — o que vai no HD externo e o que fica no disco interno, com o motivo

---

# CAIXA 2 — Primeiro dado no disco

Esta caixa **vem antes da infraestruturaboa de propósito**. Motivo: partida que você não coletar hoje pode sair da janela de retenção da Riot e desaparecer para sempre. Todo o resto — Terraform, Kubernetes, modelo — você constrói com calma sobre os arquivos que já estarão lá.

O objetivo aqui é feio e funcional. Vai ser reescrito na Caixa 5.

---

## PASSO 9 — Entender o vocabulário antes de escrever código `LEVE`

**Objetivo:** saber o que você está construindo.

**Estudar** — este passo é só leitura, e vale mais que muitos passos de código

**ETL / ELT** — Extract, Transform, Load. Três responsabilidades separadas:

| Peça | Responsabilidade | O que ela **não** faz |
|---|---|---|
| **Coletor** (Extract) | Falar com a fonte: autenticação, rate limit, paginação, retry, `429`. Traz bytes crus | Não entende o conteúdo. Para ele, um timeline é só um JSON |
| **Ingestor** (Load) | Pousar os bytes no armazenamento: nome previsível, partição, compressão, garantia de não duplicar | Não transforma nem interpreta |
| **Transform** | dbt, depois. Limpa, normaliza, agrega | Nunca toca na fonte original |

**A regra que justifica tudo:** coletar é **caro e irreversível**; transformar é **barato e refazível**. Por isso a camada **bronze** guarda o JSON cru, intocado. Se você errar qualquer transformação daqui a um ano, reprocessa a partir do bronze sem tocar na API. Se você tivesse jogado o JSON fora, o dado estaria perdido.

**Idempotência** — rodar duas vezes produz o mesmo resultado que rodar uma. É o conceito mais importante de todo o projeto, e aparece em Ansible, Terraform, ingestão e fila.

**Checkpoint** — registro persistido de onde você parou, para poder morrer e retomar.

**Teste de aprendizado**
- Por que não gravar direto em Parquet limpo e economizar espaço? (A resposta tem que mencionar a janela de retenção da Riot)
- Qual a diferença entre idempotência e deduplicação depois do fato? Por que a primeira é melhor?

**Só avance quando:** você conseguir explicar as três peças para outra pessoa.

---

## PASSO 10 — Coletor mínimo, 50 linhas `MÉDIO`

**Objetivo:** JSON cru da Riot chegando no HD externo. Nada mais.

**Fazer** — sem MinIO, sem Postgres, sem Docker
1. Script Python que:
   - Lê a chave de uma variável de ambiente (**nunca commitada**)
   - Busca seu `puuid`
   - Lista os IDs das suas últimas partidas
   - Para cada ID ainda não baixado, busca o match e o timeline
   - Grava comprimido: `bronze/match/patch=?/{matchId}.json.zst`
   - Dorme entre requisições, respeitando o rate limit
2. Controle de "já baixei": no começo, a simples existência do arquivo serve
3. Rodar na mão algumas vezes e conferir os arquivos

**Estudar antes**
- `requests` ou `httpx`
- Códigos HTTP: 200, 404, 429, 503
- O header `Retry-After`
- Compressão zstd e por que comprimir na origem

**Teste de funcionamento**
1. Rodar duas vezes seguidas: a segunda não baixa nada de novo e não duplica arquivo
2. Interromper com `Ctrl+C` no meio e rodar de novo: retoma sem perder nada
3. Abrir um arquivo baixado e localizar as coordenadas x/y de um jogador num frame

**Teste de aprendizado**
- O que seu script faz hoje se receber `429`? E se receber `503`? (Se a resposta for "quebra", isso é a Caixa 5, e está tudo bem por enquanto)

**Só avance quando:** você tiver pelo menos 20 partidas suas em disco.

---

## PASSO 11 — Agendar com systemd timer `LEVE`

**Objetivo:** coleta rodando sozinha, para sempre, sem você lembrar.

**Fazer**
1. Um arquivo `.service` que executa o script
2. Um arquivo `.timer` que dispara de hora em hora
3. `systemctl enable --now atlas-collector.timer`
4. Ver os logs com `journalctl -u atlas-collector`

**Estudar antes**
- systemd: unit, service, timer
- Por que systemd timer em vez de cron (log integrado, dependências, estado)
- Por que **não** Dagster agora: 600–900 MB de RAM que você não tem, e systemd ensina a mesma disciplina de retry e agendamento

**Teste de funcionamento**
1. `systemctl list-timers` mostra o próximo disparo
2. Reiniciar o servidor: o timer volta sozinho
3. Depois de 24h, o `journalctl` mostra 24 execuções e há arquivos novos

**Teste de aprendizado**
- O que acontece se uma execução demorar mais que o intervalo do timer? Como se evita sobreposição?

**Só avance quando:** o timer rodar por 48h sem intervenção.

**ADR-005** — systemd timer no lugar de orquestrador, e o gatilho que me faria trocar

> **Marco importante.** A partir daqui você está acumulando dado enquanto estuda. Tudo o que vem depois é construído sobre um acervo que só cresce. Pode ir devagar sem perder nada.

---

# CAIXA 3 — Transformar o servidor em código

Você fez a Caixa 1 à mão. Agora escreve tudo aquilo como código — e sente a diferença.

---

## PASSO 12 — Ansible, o primeiro playbook `MÉDIO`

**Objetivo:** ter o clique de idempotência.

**Fazer** — comece ridiculamente pequeno
1. Instalar Ansible **no PC** (ele roda do PC contra o servidor, via SSH)
2. Inventário com um host
3. Playbook que faz **uma coisa só**: instalar Docker
4. Rodar
5. **Rodar de novo** — e olhar com atenção para o `changed=0`

**Estudar antes**
- Por que Ansible e não Terraform aqui: Terraform cria recursos conversando com uma API. Seu notebook não tem API — ele já existe, está na mesa. Não há nada para criar. Ansible **converge o estado** de uma máquina que já existe
- Idempotência aplicada: por que o módulo `apt` é idempotente e `command` não é
- Inventário, playbook, task, role, handler

**Teste de funcionamento**
1. Segunda execução: `changed=0`, tudo verde
2. Desinstalar o Docker à mão e rodar o playbook: ele reinstala
3. `--check` mostra o que mudaria sem mudar nada

**Teste de aprendizado**
- Explique idempotência com um exemplo do seu próprio playbook
- Por que `command` é o último recurso? O que se perde ao usá-lo?

**Só avance quando:** você conseguir explicar por que `changed=0` é o resultado desejado.

**ADR-003** — Ansible para máquina, Terraform para API de serviço

---

## PASSO 13 — Playbook que reconstrói o servidor inteiro `MÉDIO`

**Objetivo:** se o notebook queimar, um comando reconstrói tudo.

**Fazer** — transformar em código cada passo da Caixa 1: usuário e chave SSH, `logind.conf`, zram e `sysctl`, montagem do HD por UUID, estrutura de pastas, `unattended-upgrades`, Docker, o service e o timer do coletor.

Organizar em **roles** por responsabilidade. Segredos com `ansible-vault`.

**Teste de funcionamento**
1. Playbook completo roda duas vezes: segunda com `changed=0`
2. Apagar à mão o arquivo do timer e rodar: ele volta
3. **O teste de verdade:** ler o playbook e não encontrar nada do servidor que esteja só na sua cabeça

**Teste de aprendizado**
- Se você pegasse um notebook novo agora, quanto tempo até estar tudo de pé? Se a resposta não for "o tempo de rodar um playbook", o passo não terminou

**Só avance quando:** o playbook cobrir 100% do que você fez à mão.

---

# CAIXA 4 — Aplicação, banco e portão de qualidade

---

## PASSO 14 — Docker Compose com perfis e limites `MÉDIO`

**Objetivo:** conseguir subir só o que precisa, sem derrubar a máquina.

**Fazer**
1. `docker-compose.yml` com **perfis**:
   - `core` — Postgres + API (~600 MB)
   - `ingest` — coletor + NATS (~300 MB)
   - `lake` — MinIO + jobs (~1,4 GB)
   - `obs` — Prometheus + Grafana + Loki (~900 MB)
   - `ml` — treino (1,5 GB+) — **nunca junto com `lake`**
2. **`mem_limit` em todo container, sem exceção**
3. Volumes apontando para o HD externo onde faz sentido

**Estudar antes**
- Perfis do Compose
- `mem_limit`, `cpus`, e o que o OOM killer faz sem limite: sem limite, um serviço vazando derruba a máquina inteira; com limite, morre só o culpado
- Orçamento de memória: sobram ~3,2 GB reais dos 4 GB

**Teste de funcionamento**
1. `docker compose --profile lake up -d` sobe só o que é do lake
2. Criar um container com `mem_limit=100m` e um script que aloca 500 MB: ele morre sozinho, e o servidor continua respondendo ao SSH

**Teste de aprendizado**
- Por que rodar `lake` e `ml` juntos travaria a máquina? Faça a conta

**ADR-004** — perfis do Compose e limites de memória

---

## PASSO 15 — PostgreSQL tunado para pouca memória `MÉDIO`

**Objetivo:** banco confiável em 4 GB.

**Fazer**
1. Postgres em container, com volume no **disco interno** (ver ADR-001)
2. `shared_buffers=128MB`, `work_mem` baixo, `max_connections` modesto
3. Conectar do PC pela rede
4. Backup automático (`pg_dump`) para `/mnt/dados/backups`
5. **Restaurar o backup e cronometrar**

**Estudar antes**
- O que `shared_buffers` faz, e por que 128 MB em vez dos 25% da RAM que a recomendação padrão manda
- Por que Postgres em HDD sofre (leitura aleatória) e por que `max_connections` alto é armadilha
- Diferença entre `pg_dump` e backup físico

**Teste de funcionamento**
1. Conectar do PC e criar uma tabela
2. **Restaurar de um backup em menos de 10 minutos, com o procedimento escrito.** Backup nunca restaurado não é backup
3. Postgres sobe sozinho depois de reboot

**Teste de aprendizado**
- Por que a recomendação padrão de `shared_buffers` é ruim na sua máquina?

---

## PASSO 16 — FastAPI, migrations e log estruturado `MÉDIO`

**Objetivo:** aplicação com fundação profissional.

**Fazer**
1. FastAPI com endpoint de health e alguns endpoints de leitura
2. **Alembic** para migrations
3. Log estruturado em JSON, com **correlation id** por requisição
4. Um worker de uvicorn só (é o que a memória permite)

**Estudar antes**
- Por que migration versionada e nunca `ALTER TABLE` manual
- Migration reversível e irreversível, e o impacto disso em deploy
- Log estruturado: por que JSON e não texto livre; o que é correlation id

**Teste de funcionamento**
1. Aplicar migration, reverter, reaplicar — sem perda de dado
2. Uma requisição gera log com correlation id rastreável
3. Health endpoint responde de fora do servidor

**Teste de aprendizado**
- Você precisa renomear uma coluna sem downtime. Quantas migrations e quantos deploys isso exige, e em que ordem?

---

## PASSO 17 — CI desde já `MÉDIO`

**Objetivo:** portão de qualidade automático antes de o projeto crescer.

**Fazer**
1. GitHub Actions com `lint` (ruff), `test` (pytest) e `build` da imagem
2. Rodando em todo pull request
3. Branch protection: não dá merge com CI vermelho
4. Segredos no GitHub Secrets, jamais no código

**Estudar antes**
- Workflow, job, step, runner
- Por que CI agora e não depois: retrofit em código que já existe dói, e é uma das habilidades mais transferíveis do projeto

**Teste de funcionamento**
1. PR com erro de lint proposital: o CI barra e o merge fica bloqueado
2. Teste que falha barra o merge

**Teste de aprendizado**
- Por que `apply` automático de infraestrutura em PR é má ideia, mas `plan` automático é ótimo?

---

# CAIXA 5 — Coletor profissional e object storage

Agora você reescreve o coletor feio da Caixa 2 do jeito certo — com o dado antigo preservado.

---

## PASSO 18 — Coletor resiliente `PESADO`

**Objetivo:** ingestão que aguenta rate limit, queda e reprocessamento.

**Fazer**
1. **Token bucket** respeitando os dois limites da Riot (por segundo e por janela)
2. **Backoff exponencial** com jitter
3. Respeitar `Retry-After` em vez de adivinhar
4. **Checkpoint no Postgres:** quais `matchId` já processei, quando, com que versão do coletor
5. Idempotência por `matchId` — reingestão nunca duplica
6. Distinguir erro transitório (429, 503) de permanente (404) — o segundo não deve ser retentado eternamente
7. Métrica de progresso e taxa de erro

**Estudar antes**
- Token bucket vs leaky bucket
- Backoff exponencial e por que jitter existe
- Retry só em erro idempotente
- Dead letter: o que fazer com o que falha sempre

**Teste de funcionamento**
1. Coletar 500 partidas sem nenhum `429` não tratado
2. Matar o processo no meio e reiniciar: retoma exatamente de onde parou, nada duplica
3. Rodar duas vezes o mesmo intervalo: a contagem não muda
4. Simular `429` com `Retry-After: 30` e verificar que ele espera 30s, não 1s

**Teste de aprendizado**
- Qual serviço AWS você usaria para agendar isso, e qual para guardar o checkpoint?
- Por que retry sem jitter causa thundering herd?

---

## PASSO 19 — Ampliar a coleta para a coorte `MÉDIO`

**Objetivo:** ter com quem se comparar.

**Fazer**
1. Via LEAGUE-V4, listar jogadores do **seu elo** e do **elo imediatamente acima**
2. Usar esses jogadores como sementes e coletar partidas deles
3. Baixar o CSV do **Oracle's Elixir** (dado profissional) como carga separada
4. Dimensões do Data Dragon, versionadas por patch

**Estudar antes** — o raciocínio, que é mais importante que o código

Dado profissional **não** diz como subir de elo. Pro play é outro jogo: cinco pessoas coordenadas por voz, draft preparado, jungle tracking coletivo. Copiar CS@10 de um mid da LCK não transfere — o gargalo dele é execução em teamfight, o seu provavelmente é morrer sozinho na lane.

Por isso as bases têm papéis **diferentes**:
- **Seu elo + elo acima** → diagnóstico acionável. O benchmark útil é quem está um degrau à frente
- **Dado profissional** → volume para modelagem, meta e drift de patch

**Teste de aprendizado**
- Por que comparar com o elo imediatamente acima e não com o Challenger?

**ADR-015** — por que não usar métrica de jogador profissional como benchmark pessoal

---

## PASSO 20 — MinIO como seu S3 `MÉDIO`

**Objetivo:** object storage de verdade, com permissão séria.

**Fazer**
1. MinIO em container, volume em `/mnt/dados/minio`, com `mem_limit`
2. Buckets: `bronze`, `silver`, `gold`, `tf-state`, `mlflow-artifacts`
3. **Um usuário de serviço por consumidor**, com policy mínima:
   - coletor: escreve só em `bronze/`
   - dbt: lê `silver/`, escreve `gold/`
   - treino: lê `gold/`, escreve em `mlflow-artifacts/`
4. Credencial root só para administração, **nunca** em aplicação
5. Lifecycle: bronze expira em 90 dias, gold nunca
6. Migrar o bronze da Caixa 2 para dentro do MinIO
7. Layout de prefixos particionado por patch e data

**Estudar antes**
- Modelo de object storage: bucket, objeto, prefixo. Por que "pasta" não existe de verdade
- **Policy no formato IAM** — o MinIO usa a mesma sintaxe da AWS: `Version`, `Statement`, `Effect`, `Action`, `Resource`, até o formato de ARN
- Least privilege
- Lifecycle rule
- Presigned URL

**Teste de funcionamento**
1. Com a credencial do coletor, tentar escrever em `gold/` — **deve ser negado**
2. Ler um objeto de bronze do PC, via DuckDB `httpfs`, pela rede
3. Lifecycle apagar um objeto de teste com data antiga

**Teste de aprendizado**
- Escreva de memória uma policy que permita `GetObject` em `silver/*` e negue o resto. Compare com a sintaxe de IAM da AWS: o que é igual?
- Por que particionar por patch e não só por data?

**ADR-006** — least privilege no MinIO como substituto parcial do treino de IAM

---

# CAIXA 6 — Terraform

Você tem MinIO, Postgres e GitHub de pé. Agora aprende a gerenciá-los por código.

**A separação que importa:**

| O que aprender | Onde está | Valor |
|---|---|---|
| State, `plan`/`apply`, drift, `import`, módulos, variáveis, outputs, dependências | Independente de provider | **90% do trabalho real** |
| Que atributo o `aws_s3_bucket` tem, sintaxe exata de policy | Catálogo do provider | Decoreba consultável |

Quase todo mundo acha que precisa da AWS para aprender Terraform. Não precisa.

---

## PASSO 21 — Primeiro `apply`, com o provider mais fácil `LEVE`

**Objetivo:** ver `plan`, `apply` e state funcionando, hoje, sem depender de infra.

**Fazer** — comece pelo **provider GitHub**, que só precisa da sua conta e um token
1. Gerenciar o próprio repositório: branch protection, required checks, secrets
2. `terraform init`, `plan`, `apply`
3. **`apply` de novo** — e olhar para o `No changes`
4. Abrir o arquivo de state e ler

**Estudar antes**
- **O que é provider:** o Terraform sozinho não sabe nada. Ele só lê seu código, compara com o state e pede a alguém para criar a diferença. Esse alguém é o provider — um plugin que sabe conversar com a API de um serviço
- Diferença entre o **bloco** `provider` (configuração: endereço, credencial) e `resource` (cada coisa que deve existir). O prefixo do nome diz de qual provider vem: `github_repository`, `minio_s3_bucket`, `aws_s3_bucket`
- O que é **state** e por que não é opcional
- `plan` vs `apply`

**Teste de funcionamento**
1. Segundo `apply` diz `No changes`
2. Mudar branch protection pela UI do GitHub e rodar `plan`: ele detecta o desvio e quer corrigir

**Teste de aprendizado**
- Explique de memória o que é state e o que quebra se ele for perdido
- Se o Terraform é o motorista, o provider é o quê?

---

## PASSO 22 — Terraform sobre MinIO e Postgres `MÉDIO`

**Objetivo:** infraestrutura de dados declarada em código.

**Fazer** (confirme os namespaces no Terraform Registry antes de fixar versões)
1. Provider **MinIO** (`aminueza/minio`): buckets, service accounts, policies, lifecycle
2. Provider **PostgreSQL** (`cyrilgdn/postgresql`): roles por serviço (`api_rw`, `dbt_ro`, `iceberg_catalog`) com grants explícitos
3. Referenciar recursos entre si em vez de digitar nomes:
   ```hcl
   resource "minio_iam_service_account" "layer_user" {
     policy = minio_iam_policy.layer_writer.policy
   }
   ```
   Isso monta o **grafo de dependências**, e o Terraform descobre sozinho a ordem de criação

**Teste de funcionamento**
1. `destroy` seguido de `apply` reconstrói buckets, usuários e policies, e a aplicação volta a funcionar sem nada manual (o dado no HD externo não some — só a estrutura administrativa)
2. A policy criada por Terraform realmente nega o que deveria negar

**Teste de aprendizado**
- Como o Terraform soube que precisava criar a policy antes do service account? Você disse a ordem em algum lugar?

---

## PASSO 23 — Drift e import — o passo mais valioso da caixa `MÉDIO`

**Objetivo:** entender o problema que mais aparece no trabalho real.

**Fazer** — nesta ordem, de propósito
1. Criar um bucket **pela UI** do MinIO. Rodar `plan`. O Terraform não sabe dele
2. `terraform import` desse bucket. Rodar `plan`: agora está sob gestão
3. Apagar **pela UI** um bucket que o Terraform gerencia. Rodar `plan`: ele quer recriar
4. Mudar uma policy pela UI e ver o `plan` querendo desfazer
5. Documentar o que aprendeu

**Estudar antes**
- O que é drift e por que ele é inevitável em equipe
- `import` contra criar do zero
- `terraform state mv`, `rm`, `list`
- `lifecycle { prevent_destroy }` e quando usar

**Teste de aprendizado**
- Qual a diferença entre `import` e mover recurso no state? Quando usa cada um?
- Alguém do time criou um bucket na mão em produção. Quais são suas três opções e o trade-off de cada uma?

---

## PASSO 24 — Módulos, state remoto e CI `MÉDIO`

**Objetivo:** Terraform como se usa em equipe.

**Fazer**
1. **Módulo `data_layer`** que recebe o nome da camada e cria bucket + policy + service account + lifecycle + role no Postgres. Chamar três vezes: bronze, silver, gold. Adicionar uma quarta camada deve ser uma linha:
   ```hcl
   module "platinum" {
     source         = "./modules/data_layer"
     layer_name     = "platinum"
     retention_days = 180
   }
   ```
2. **State remoto no próprio MinIO** (backend S3, bucket `tf-state`). O bucket de state você cria à mão — é o clássico **problema de bootstrap**
3. Sobre locking: versões recentes do Terraform suportam lockfile nativo no bucket, sem DynamoDB. **Confirme na documentação da sua versão** — isso mudou recentemente
4. Ambientes: `dev` (k3d no PC) e `prod` (notebook), mesmo código, `.tfvars` diferentes
5. CI: `fmt -check`, `validate` e `plan` no PR; `apply` só manual

**Teste de funcionamento**
1. Adicionar uma camada nova com uma chamada de módulo
2. State no MinIO, e dois `apply` simultâneos: o segundo é bloqueado pelo lock
3. PR mostra o `plan` como comentário

**Teste de aprendizado**
- O que é o problema de bootstrap do backend remoto, e por que ele não tem solução elegante?
- Por que módulo em vez de copiar e colar o bloco três vezes?

**ADR-007** — Terraform sobre serviços locais para aprender mecânica sem nuvem paga
**ADR-008** — Terraform ou OpenTofu: HCL, state e comandos são iguais; a diferença é licença e governança. O mercado pede "Terraform" em vaga; OpenTofu roda o mesmo código. Escolha um, registre o motivo, siga

---

## PASSO 25 — Grafana como código `LEVE`

**Objetivo:** nunca mais perder um dashboard.

**Fazer**
1. Grafana em container
2. Provider Grafana: datasources, folders, dashboards, alert rules
3. Primeiro dashboard: partidas coletadas por hora, taxa de erro do coletor
4. **Nunca criar painel pela UI.** Se criar, faça `import`

**Teste de funcionamento:** apagar todos os dashboards e recriar com `terraform apply`.

**Teste de aprendizado**
- Por que dashboard clicado na UI é dívida técnica?

---

# CAIXA 7 — Lakehouse

Aqui o dado cru vira dado consultável. Esta caixa é o coração do projeto.

---

## PASSO 26 — Bronze para Parquet `MÉDIO`

**Objetivo:** JSON virando colunar, sem travar a máquina.

**Fazer**
1. Job que lê JSON do bronze e escreve Parquet em silver, particionado por patch
2. **Em streaming, nunca acumulando.** Um JSON por vez, escreve, libera. Pico de memória em dezenas de MB
3. **Lote por patch**, não por partida — cada lote cabe na RAM e sai como um Parquet de tamanho decente. Isso evita gerar 10 mil arquivinhos e ter que reler tudo para agrupar
4. Compressão zstd
5. `nice` e `ionice` no job, para o coletor ter prioridade no disco
6. **O backfill histórico roda no PC principal**, não no notebook

**Estudar antes** — a parte conceitual mais importante da caixa
- Parquet: formato colunar, row groups, projeção de colunas, predicate pushdown
- Por que **nunca escanear JSON bruto duas vezes**: 10 mil timelines são 10–30 GB, e um scan completo em HDD leva minutos. Em Parquet, o mesmo dado cabe em 1–2 GB e você lê só as colunas necessárias
- **Amplificação de escrita:** gravar um arquivo por partida força uma segunda passada de agrupamento. Sem caber na RAM, isso vira ordenação externa — várias passadas de leitura e escrita no disco. Pode custar mais que a conversão inteira
- Por que acumular tudo num DataFrame causa **swap thrashing**: 3,5 milhões de linhas em objetos Python não cabem em 4 GB, o kernel manda páginas para o swap, o swap está no **mesmo HDD** que você está lendo, e o job fica 50 a 100 vezes mais lento

**Teste de funcionamento**
1. Converter 1.000 partidas no notebook com pico de memória abaixo de 500 MB (medir com `systemd-cgtop` ou `/usr/bin/time -v`)
2. O coletor continua funcionando durante a conversão, sem timeout
3. Parquet resultante ocupa uma fração do JSON original

**Teste de aprendizado**
- Por que a versão ingênua desse job travaria a máquina inteira, e não só ficaria lenta?
- O que é predicate pushdown, e como o Athena cobra por isso?

**ADR-014** — backfill pesado no PC, incremental no notebook

---

## PASSO 27 — DuckDB `MÉDIO`

**Objetivo:** SQL sobre o object storage, como Athena.

**Fazer**
1. DuckDB com `memory_limit` explícito (ex.: `1GB`)
2. Extensão `httpfs` lendo Parquet direto do MinIO
3. Primeiras consultas: seu CS@10 médio por role e patch
4. Consultar do PC apontando para o MinIO do notebook, pela rede

**Estudar antes**
- Por que DuckDB e não Trino: Trino quer 2 GB+ de heap JVM e não cabe nem com upgrade. DuckDB cobre 90% do aprendizado sobre Athena com uma fração do peso
- `memory_limit` e spill controlado para disco — a diferença entre **degradar** e **travar**: o DuckDB decide fazer spill; o kernel via swap não avisa ninguém
- Partition pruning

**Teste de funcionamento**
1. Consulta agregando milhões de linhas sem estourar memória
2. Comparar tempo de consulta com e sem filtro de partição

**Teste de aprendizado**
- Por que `memory_limit` no DuckDB é mais seguro que confiar no swap?

**ADR-011** — DuckDB agora, Trino só quando doer

---

## PASSO 28 — Iceberg `PESADO`

**Objetivo:** tabela de verdade sobre object storage.

**Fazer**
1. **pyiceberg com catálogo SQL no Postgres** — zero serviço extra. Nessie e Polaris são JVM e não cabem em 4 GB. Migrar para catálogo REST depois é troca de configuração
2. Criar tabelas Iceberg sobre o silver
3. Exercitar: snapshot, time travel, schema evolution, partition spec
4. Rotina de **compactação** de small files, agendada

**Estudar antes**
- **O catálogo é a decisão importante do Iceberg, não o formato de arquivo.** É onde a maioria se perde
- Snapshot e time travel
- Schema evolution — a Riot **vai** mudar campos entre patches, e você **vai** quebrar em algum
- `copy-on-write` vs `merge-on-read`
- Compactação: 5 partidas/dia gravadas individualmente dão ~150 arquivinhos/mês, milhares por ano. Em HDD isso dói de verdade

**Teste de funcionamento**
1. Adicionar coluna nova sem reescrever o histórico
2. Time travel: consultar o estado da tabela antes do último insert
3. Antes e depois da compactação: contar arquivos e cronometrar a mesma consulta

**Teste de aprendizado**
- Por que o catálogo importa mais que o formato?
- Qual o análogo AWS do seu catálogo?

**ADR-009** — catálogo SQL em vez de Nessie/Polaris
**ADR-010** — Iceberg e não Delta Lake

---

## PASSO 29 — dbt e incremental `PESADO`

**Objetivo:** transformações versionadas, testadas e incrementais.

**Fazer**
1. dbt com camadas `staging` → `intermediate` → `marts`
2. Modelo **incremental** com marca d'água: processa só o que chegou desde a última execução
3. **Janela de retrocesso:** todo dia reprocessar também os últimos 3 dias. Você joga às 23h58, o job roda à meia-noite, a partida ainda não apareceu na API — se o job só olha "de ontem", ela se perde para sempre. Isso **só funciona porque a ingestão é idempotente** (Passo 18)
4. dbt tests: unicidade, not null, relacionamento, freshness
5. Dimensões versionadas por patch
6. Marts que respondem perguntas concretas: percentis meus contra a coorte, por role e campeão

**Estudar antes**
- Materialização: view, table, incremental
- Marca d'água e dado que chega atrasado
- Por que reprocessar uma janela é mais robusto que confiar em "só o novo"
- Modelagem dimensional: fato e dimensão
- Contrato de dados e teste de qualidade

**Teste de funcionamento**
1. Responder em SQL: "CS@10 médio por role e patch, meu versus a coorte do elo acima"
2. Responder: "quantos jogadores tiveram 3+ partidas por semana em cada mês do último ano"
3. Inserir uma partida com data retroativa: a janela de retrocesso a captura
4. Quebrar um teste de propósito: o dbt falha e o CI barra
5. Fazer backfill de um mês e obter resultado idêntico ao original

**Teste de aprendizado**
- Por que a janela de retrocesso exige idempotência? O que aconteceria sem ela?
- Diferença entre teste de schema e teste de dado?

---

# CAIXA 8 — Eventos

---

## PASSO 30 — NATS JetStream e workers `PESADO`

**Objetivo:** arquitetura orientada a eventos com garantias explícitas.

**Fazer**
1. **JetStream**, não NATS core, com stream persistido
2. Fluxo: partida ingerida → evento publicado → worker recalcula features → atualiza marts
3. Consumer group, ack/nack explícito
4. **DLQ** para o que falha repetidamente
5. Limite de redelivery e análogo a visibility timeout
6. Idempotência no consumidor

**Estudar antes**
- **Correção importante:** NATS core é fire-and-forget e **não** equivale a SQS. Quem se aproxima de SQS/Kinesis é o **JetStream**, com persistência e ack. Se o objetivo é mentalidade AWS, é JetStream que transfere
- at-least-once vs exactly-once — qual você tem, e como compensa
- Visibility timeout, ack, nack, redelivery
- Por que idempotência do consumidor é obrigatória em at-least-once

**Teste de funcionamento**
1. Matar o worker no meio do processamento: o evento é reprocessado e **nada duplica**
2. Mensagem malformada vai para a DLQ depois de N tentativas, sem travar a fila
3. Dois workers no mesmo consumer group: carga dividida, nenhuma mensagem processada duas vezes

**Teste de aprendizado**
- Explique visibility timeout e o problema que ele resolve
- Por que exactly-once é praticamente impossível, e por que isso não é problema?

**ADR-012** — JetStream e não NATS core
**ADR-013** — Temporal fora do escopo (1 GB+, banco próprio, e resolve problema que você ainda não tem)

---

# CAIXA 9 — Ciência de dados

Esta caixa roda no **PC principal**. Dois núcleos sem turbo treinando gradient boosting em milhões de linhas é sofrimento sem aprendizado.

---

## PASSO 31 — Descritiva `MÉDIO`

**Objetivo:** primeiro diagnóstico útil.

**Fazer:** percentis seus contra a coorte, por role e campeão — CS@10, gold diff@10, mortes antes do min 10, participação em objetivos, tempo morto por jogo, wards por minuto.

**Estudar antes:** percentil contra média, e por que agregação esconde variância.

**Teste de funcionamento:** um relatório que te diz algo que você não sabia.

---

## PASSO 32 — Espacial `MÉDIO`

**Objetivo:** usar as coordenadas x/y do timeline — a parte que nenhum site te dá.

**Fazer**
1. Heatmap de onde você morre, por minuto de jogo e por role inimigo
2. **DBSCAN** nas mortes → padrões como "morro no rio inimigo entre 8 e 14 min empurrando wave"
3. Distância média do seu jungle/suporte no momento da morte → proxy para "morri isolado"

**Estudar antes:** DBSCAN contra k-means (e por que DBSCAN aqui: você não sabe quantos clusters existem).

**Teste de funcionamento:** identificar um padrão de morte que você reconhece como verdadeiro.

**Teste de aprendizado**
- Por que DBSCAN e não k-means para este problema?

---

## PASSO 33 — Win probability `PESADO`

**Objetivo:** o modelo central do projeto.

**Fazer**
1. Gradient boosting (LightGBM ou XGBoost) sobre frames: `P(vitória | gold diff, xp diff, torres, dragões, minuto t)`
2. Treinar no dado profissional (volume), aplicar no seu (transferência) — e analisar a diferença entre domínios
3. **Throw detection:** em que minuto sua win prob caiu mais, e qual evento coincidiu
4. **Win probability added** por partida: quanto você agregou além do baseline
5. Avaliação séria: log loss, **Brier score**, **curva de calibração**

**Estudar antes**
- Gradient boosting, no nível de intuição
- **Calibração** — e por que ela importa mais que acurácia aqui: um modelo pode acertar muito e ainda dizer "70%" quando a taxa real é 40%
- Brier score
- Split temporal, não aleatório: dado de LoL tem ordem, e embaralhar causa vazamento

**Teste de funcionamento**
1. Curva de calibração plotada
2. Brier score medido e registrado
3. Identificar o momento de throw de uma partida específica que você lembra

**Teste de aprendizado**
- O que significa boa acurácia com má calibração? Por que isso importa aqui?
- Por que split aleatório vazaria informação?

---

## PASSO 34 — A armadilha causal `MÉDIO`

**Objetivo:** o passo que separa análise de leitura de gráfico.

**Estudar e aplicar**

"Kills correlacionam com vitória" é quase inútil: kills são **consequência** de estar ganhando — colisor clássico. Mortes têm componente causal mais defensável.

Concretamente: **controle por gold diff@10 antes de afirmar que qualquer coisa "causa" vitória.**

**Estudar antes:** confundidor, mediador, colisor. DAG causal. Por que "controlar por tudo" é errado.

**Teste de funcionamento:** desenhe o DAG do seu problema e mostre uma conclusão que muda quando você controla pela variável certa.

**Teste de aprendizado**
- Por que kills são colisor e mortes não?
- Cite uma variável do seu dado que é mediador, e explique por que controlar por ela esconderia o efeito que você quer medir

---

## PASSO 35 — Amostra pequena `MÉDIO`

**Objetivo:** parar de se enganar com 8 jogos.

**Fazer:** beta-binomial com prior empírico tirado do dado profissional/coorte, encolhendo sua estimativa de winrate por campeão para a média.

**Estudar antes:** bayesiano empírico, shrinkage, prior e posterior. Por que 5 de 8 não é 62%.

**Teste de funcionamento:** comparar winrate cru e encolhido para seus campeões, e ver a ordenação mudar.

**Teste de aprendizado**
- Por que encolher para a média não é "trapaça"?

---

## PASSO 36 — Séries temporais e sessão `MÉDIO`

**Fazer**
1. Winrate móvel com intervalo de confiança honesto
2. **Changepoint detection:** sua performance mudou no patch X?
3. **Análise de sessão:** seu desempenho decai no 4º jogo seguido? Modelo hierárquico com `jogo_na_sessão` como feature

Se decair, a recomendação mais valiosa que o app pode dar é **"pare de jogar"** — e é bonito ter derivado isso de dados.

**Teste de funcionamento:** um gráfico de performance por posição na sessão, com incerteza.

---

## PASSO 37 — MLflow e drift `PESADO`

**Objetivo:** MLOps, não notebook solto.

**Fazer**
1. MLflow para experimentos e registry, artefatos no MinIO
2. Features versionadas, definidas em código
3. Promoção explícita de staging para produção
4. Modelo servido pela API do notebook
5. **Retreino agendado** e comparação entre métrica de produção e de treino
6. Alerta se divergir

**Estudar antes**
- Data drift contra concept drift — qual acontece quando a Riot lança um patch?
- Training-serving skew
- Por que reprodutibilidade exige versionar dado, código e parâmetro juntos

**Teste de funcionamento**
1. Reproduzir um experimento antigo pelo MLflow e obter a mesma métrica
2. Modelo respondendo inferência pela API
3. Métrica de produção comparada à de treino, com alerta configurado

**Teste de aprendizado**
- Diferença entre data drift e concept drift, com um exemplo do seu projeto de cada
- Por que o modelo do patch 25.1 degrada mesmo sem nada quebrar?

---

# CAIXA 10 — Observabilidade

Roda **em ciclo** (sobe, valida, desce) até haver upgrade de RAM.

---

## PASSO 38 — Métricas, logs e alertas `PESADO`

**Fazer**
1. Prometheus, retenção de 7 dias
2. Loki para o log estruturado do Passo 16
3. Grafana com dois tipos de painel: **sistema** (CPU, RAM, disco, latência) e **negócio** (partidas por hora, sua winrate, drift do modelo)
4. Alerting rules: falha de ingestão, `429` acima do normal, disco cheio, modelo divergindo
5. Todos os dashboards via Terraform (Passo 25)
6. **Tempo/tracing fica postergado:** com um FastAPI e um worker os traces são triviais. Vale a partir de 3–4 serviços

**Estudar antes**
- **Cardinalidade** em Prometheus, e por que um label errado (ex.: `matchId`) derruba o servidor
- Métrica, log e trace: qual pergunta cada um responde
- **Alertar em sintoma, não em causa.** "Latência do usuário acima de 2s" é útil; "CPU em 90%" gera alarme falso
- Os quatro sinais dourados

**Teste de funcionamento**
1. Derrubar a ingestão de propósito: receber alerta antes de notar manualmente
2. Encher o disco artificialmente: alerta antes de 100%
3. Rastrear uma requisição do log até a métrica pelo correlation id
4. Recriar todos os dashboards com `terraform apply`

**Teste de aprendizado**
- Por que usar `matchId` como label do Prometheus seria um desastre?
- Por que alertar em sintoma e não em causa?

---

# CAIXA 11 — Kubernetes

Roda no **PC principal**, com k3d. Não no notebook.

**Por quê:** o control plane do k3s come 500–800 MB dos seus 4 GB. E mais importante — IaC só ensina quando você **destrói e recria**. É no segundo `apply` que descobre que o código não era idempotente, e no `destroy` que descobre a dependência não declarada. O notebook não pode ser destruído toda tarde. O k3d sobe um cluster de 3 nós em containers em ~30 segundos.

---

## PASSO 39 — Kubernetes na mão `PESADO`

**Objetivo:** entender os objetos antes de abstrair.

**Fazer** — YAML puro, sofrendo um pouco de propósito
1. Cluster k3d criado por script
2. Deploy da API: Deployment, Service, ConfigMap, Secret
3. Liveness e readiness probes
4. Resource requests e limits
5. PVC
6. Destruir o cluster e recriar

**Estudar antes**
- Pod, ReplicaSet, Deployment, Service, Ingress
- Liveness contra readiness — e o que acontece se você trocar as duas
- Requests contra limits: CPU throttling contra OOMKill

**Teste de funcionamento**
1. Destruir e recriar o cluster por script, com a aplicação de pé, em menos de 10 minutos
2. Matar um pod: o Deployment recria e não há indisponibilidade
3. Configurar readiness errada de propósito e ver o pod nunca receber tráfego

**Teste de aprendizado**
- Diferença entre liveness e readiness. O que acontece se trocar?
- Diferença entre requests e limits. O que é throttling e o que é OOMKill?
- Por que Service e não IP de pod?

---

## PASSO 40 — Helm e GitOps `MÉDIO`

**Fazer**
1. Empacotar sua aplicação em chart Helm próprio — e sentir a diferença em relação ao YAML puro
2. `values.yaml` por ambiente
3. Namespaces e quotas via provider Kubernetes do Terraform
4. HPA, mesmo que didático
5. **Flux** para GitOps (mais leve que ArgoCD)

**Teste de funcionamento**
1. Instalar e desinstalar o chart sem deixar resíduo
2. Commit no Git provoca deploy automático via Flux

**Teste de aprendizado**
- O que o Helm resolve que YAML puro não resolve?
- Qual a diferença entre CI empurrando deploy e GitOps puxando?

**ADR-016** — Kubernetes no PC via k3d, não no notebook

---

# CAIXA 12 — Nuvem (opcional)

**Se você tirar esta caixa, nada quebra.** As Caixas 0 a 11 rodam inteiras em casa, e você já terá aprendido Terraform, Kubernetes, lakehouse e ML.

O que falta sem ela é bem delimitado, e são três coisas que aparecem muito em vaga:

1. **Provisionar infraestrutura** — criar uma máquina ou uma rede que não existia. Em casa o Terraform sempre configura algo que já está de pé
2. **Identidade sem credencial** — a máquina prova quem é pelo fato de ser aquela máquina, recebe token temporário, e não há chave nenhuma em disco para roubar. É `instance principal` na Oracle e `IAM role for EC2` na AWS
3. **Rede segmentada** — subnet privada, security list, NAT. Em casa tudo está na mesma LAN e tudo se enxerga, então você nunca sente o problema

**Faça esta caixa depois da Caixa 6.** Nessa altura você já sabe Terraform, e a nuvem vira "o mesmo raciocínio, agora contra uma API que cria máquinas" — em vez de duas coisas novas ao mesmo tempo.

---

## PASSO 41 — Escolher o alvo `LEVE`

| Opção | Vantagem | Desvantagem |
|---|---|---|
| **Oracle Cloud Always Free** | Instâncias ARM gratuitas permanentes (ordem de 4 OCPUs / 24 GB — **confirmar limites atuais**), IAM e rede reais | Disponibilidade de ARM é notoriamente disputada; erro de capacidade é comum; exige imagem `arm64` |
| **AWS free tier** | Sintaxe exata que você usa no trabalho, 12 meses | Exige cartão e disciplina de custo |
| **LocalStack no PC** | HCL com provider `aws` real, sem risco | Emulação de IAM frequentemente **não nega** o que a AWS negaria — treina sintaxe, não segurança. Athena e Glue são pagos. **Confirmar a divisão atual de features** |

Em qualquer caso: configure **alerta de orçamento**. "Always free" não é o mesmo que "impossível gerar cobrança".

---

## PASSO 42 — Terraform contra API de verdade `PESADO`

**Fazer** — um recurso por vez
1. Só um bucket. `apply`, `destroy`, `apply`
2. Rede: VCN/VPC, subnet, security list
3. Uma VM
4. **IAM:** policy, compartment, dynamic group. A máquina acessando o bucket **sem credencial em disco**
5. A cadeia completa: **Terraform cria a VM → Ansible configura → Helm sobe os apps**

**Uma fricção real e instrutiva:** o endpoint compatível com S3 da Oracle não aceita instance principal — exige chave estática. Para usar identidade sem credencial você precisa do SDK nativo. Ou seja, você escolhe entre "meu código não muda entre MinIO e Oracle" e "não tenho credencial no disco". Essa tensão é um ADR excelente. **Confirme na documentação atual.**

**Teste de funcionamento**
1. `destroy` e `apply` reconstroem o ambiente em menos de 1 hora
2. Uma policy restritiva nega uma ação — e você explica por quê
3. A instância não é acessível de fora exceto nas portas que você abriu
4. Você vai bater no muro de não conseguir SSH numa subnet privada, e vai ter que decidir: bastion? NAT gateway? subnet pública com regra restrita? **Esse muro é o conteúdo**

**Teste de aprendizado**
- Explique least privilege com um exemplo do seu projeto
- Diferença entre subnet pública e privada, e por que NAT existe
- Qual o análogo AWS de cada recurso que você criou?
- Se este ambiente fosse pago, onde estaria seu maior custo? (FinOps — a habilidade que o lab gratuito esconde)

**ADR-017** — arquitetura de dois tiers: local quente, nuvem para o que não cabe

---

# CAIXA 13 — LLM no papel certo

---

## PASSO 43 — Narrativa ancorada em números `PESADO`

**A regra:** a LLM **não** faz a análise. Ela narra o que os modelos calcularam.

Saída correta: *"nos últimos 20 jogos, 60% das suas mortes ocorrem entre 8 e 14 min no lado inferior do mapa; sua win probability média cai 18 pontos nesse intervalo."* Todos os números vêm de SQL e Python.

**Fazer**
1. Servidor **MCP** expondo suas métricas como tools
2. Abstração de provider (trocar modelo alterando configuração)
3. RAG sobre seu histórico com **pgvector**
4. Versionamento de prompt e registro de custo por token
5. **Ollama fora do escopo:** 2,5 GB+, e sem GPU com swap em HDD é travamento

**Estudar antes**
- Grounding e por que ele é diferente de "pedir para a LLM analisar"
- RAG: chunking, embedding, recuperação
- O que MCP resolve que uma chamada de API não resolve

**Teste de funcionamento**
1. Perguntar "por que perdi meus últimos 5 jogos de tal campeão" e receber resposta ancorada
2. **Verificar cada número da resposta contra uma consulta SQL — zero número inventado**
3. Trocar de provider mudando só configuração
4. Perguntar sobre dado que não existe: o sistema diz que não sabe

**Teste de aprendizado**
- Como você detectaria que o modelo inventou um número?

**ADR-018** — LLM como camada de narrativa, nunca de cálculo

---

# CAIXA 14 — Tempo real (opcional, e divertido)

---

## PASSO 44 — Win probability ao vivo `PESADO`

**Fazer:** a **Live Client Data API** roda em `localhost:2999` **no PC onde você joga**. O notebook só recebe e serve — zero custo de CPU no servidor. Overlay mostrando sua probabilidade de vitória durante a partida.

**Estudar antes**
- Batch, micro-batch e streaming
- **Training-serving skew:** por que a mesma feature calculada em batch e em tempo real pode divergir

**Teste de funcionamento**
1. Ver a probabilidade atualizando durante uma partida real
2. Perda de conexão com o servidor não trava o jogo nem o overlay

---

# Apêndice A — Mapa de progresso

| Caixa | Passos | O que você domina ao terminar |
|---|---|---|
| 0 | 1–3 | Bancada pronta, chave solicitada, hardware diagnosticado |
| 1 | 4–8 | Linux server, SSH, systemd, memória, disco |
| 2 | 9–11 | Vocabulário de ETL, coleta rodando sozinha |
| 3 | 12–13 | Ansible e idempotência |
| 4 | 14–17 | Docker, Postgres, FastAPI, migrations, CI |
| 5 | 18–20 | Ingestão resiliente, object storage, least privilege |
| 6 | 21–25 | **Terraform completo** — o mais transferível do projeto |
| 7 | 26–29 | Parquet, DuckDB, Iceberg, dbt, incremental |
| 8 | 30 | Mensageria com garantias |
| 9 | 31–37 | Estatística aplicada, causalidade, MLOps |
| 10 | 38 | Observabilidade e cultura de alerta |
| 11 | 39–40 | Kubernetes e Helm |
| 12 | 41–42 | IAM, rede, provisionamento (opcional) |
| 13 | 43 | LLM com grounding, MCP |
| 14 | 44 | Streaming |

---

# Apêndice B — Anti-escopo

Cada item tem gatilho de entrada. Anti-escopo não é desistência, é sequenciamento.

| Item | Por que fora | Quando entra |
|---|---|---|
| **Trino** | 2 GB+ de heap JVM | Quando o DuckDB não aguentar — e aí o aprendizado será genuíno |
| **Temporal** | 1 GB+ e banco próprio; resolve problema que você não tem | Quando houver workflow longo e durável de verdade |
| **Ollama** | 2,5 GB+; sem GPU e com swap em HDD, inviabiliza iteração | Se houver GPU disponível |
| **Tempo / tracing** | Traces triviais com dois serviços | A partir de 3–4 serviços |
| **Dagster** | 600–900 MB | Depois do upgrade de RAM, ou na nuvem |
| **Nessie / Polaris** | JVM | Se precisar de catálogo compartilhado entre engines |
| **Frontend elaborado** | O foco é backend, infra e dados | Nunca, provavelmente |

---

# Apêndice C — Erros que custam caro

1. **Jogar o JSON bruto fora depois de converter.** A Riot tem janela de retenção; partida fora dela não existe mais. Bronze é seguro, não desperdício
2. **Acumular tudo em memória num job de conversão.** Causa swap thrashing em HDD: 50 a 100 vezes mais lento, com a máquina congelada
3. **Rodar `lake` e `ml` juntos.** Não cabe. O OOM killer pode escolher o Postgres como vítima
4. **Container sem `mem_limit`.** Um vazamento derruba a máquina inteira em vez de só o culpado
5. **Criar coisas na UI e não importar.** Vira drift e, mais tarde, um `apply` destrutivo
6. **`matchId` como label do Prometheus.** Explosão de cardinalidade
7. **Split aleatório em dado temporal.** Vazamento, e métrica boa que não se sustenta
8. **Confiar em backup nunca restaurado.** Não é backup, é esperança
9. **Postgres no HD externo por USB.** Latência e desconexão silenciosa; perder o disco no meio de uma escrita corrompe
10. **Pular o teste de aprendizado porque "funcionou".** É o único jeito garantido de desperdiçar o projeto inteiro

---

# Apêndice D — Decisões ainda abertas

1. **Upgrade de SSD e/ou RAM?** Com SSD + 12 GB, as Caixas 10 e 11 podem viver de pé no notebook
2. **HD externo é USB 3.0 ou 2.0, HDD ou SSD?** Se for SSD por USB 3.0, o Postgres vai para ele e o ADR-001 se inverte
3. **Qual seu elo e role principal?** Define a coorte e o volume de coleta
4. **Já usou Ansible ou Terraform?** Se nunca, o Passo 12 é seu ponto de partida real
5. **Terraform ou OpenTofu?** ADR-008
6. **Cartão internacional disponível?** Muda a Caixa 12 de Oracle para AWS free tier
