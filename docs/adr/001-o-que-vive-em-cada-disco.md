# ADR-001 — O que vive em cada disco

Data: 2026-08-22

## Contexto

O servidor tem dois discos, ambos mecânicos, com características bem diferentes:

| | Interno | Externo |
|---|---|---|
| Dispositivo | `sda` | `sdb` |
| Modelo | ST1000LM024 HN-M | Toshiba MQ01ABD050V |
| Capacidade | 931,5 GB (861 GB livres) | 465,8 GB (453 GB livres) |
| Barramento | SATA | **USB 2.0** (`high-speed`) |
| Ponte | — | JMicron JMS578 (`152d:0578`) |
| Montagem | `/` | `/mnt/dados`, por UUID |

Fatos relevantes levantados durante o PASSO 8:

- **O externo não suporta FUA.** O kernel reporta `Disabling FUA` e `Write cache: enabled ... doesn't support DPO or FUA`. Sem *Force Unit Access*, o sistema não consegue exigir que uma escrita chegue ao prato — o disco pode confirmar dado que ainda está no cache volátil dele.
- **O servidor não tem mais bateria** (ver [ADR-021](021-remocao-da-bateria-do-servidor.md)). Queda de energia é corte instantâneo, sem desligamento gracioso.
- **A ponte JMicron é capaz de USB 3.0** e mesmo assim negociou `high-speed`. Provável limitação de cabo ou de porta — não testado ainda.
- Ambos os discos são mecânicos, com ~80–100 IOPS aleatórios. Nenhum dos dois é bom para acesso aleatório; o externo é pior por somar latência de USB.

## Alternativas consideradas

1. **Postgres no HD externo.** Liberaria o disco interno e concentraria o dado num lugar só. Descartada por três razões independentes e cumulativas: latência de USB sobre carga aleatória, risco de desconexão silenciosa do cabo durante escrita ativa, e ausência de FUA — cada uma sozinha já desaconselha banco de dados.
2. **Tudo no disco interno**, usando o externo só para backup. Descartada: 861 GB parecem muitos hoje, mas a camada bronze é a que mais cresce e é imutável por design. Encher o disco do sistema é o modo de falha que derruba tudo de uma vez.
3. **Divisão por perfil de acesso.** Escolhida.

## Decisão

**Disco interno (`sda`, SATA):**

- Sistema operacional
- Postgres — dado quente, acesso aleatório, integridade crítica
- `/swap.img` (última instância, atrás do zram — ver PASSO 7)

**HD externo (`sdb`, `/mnt/dados`):**

```
/mnt/dados/
  bronze/     # JSON cru da Riot — grande, sequencial, imutável
  parquet/    # silver e gold
  backups/    # dumps do Postgres
  minio/      # volume do MinIO (Caixa 5)
```

O critério é o **padrão de acesso**, não o tamanho: acesso aleatório e sensível a latência fica no interno; escrita e leitura sequencial de arquivos grandes vai para o externo, onde a penalidade do USB 2.0 é amortizada pelo tamanho das transferências.

Montagem por UUID no `/etc/fstab`, com `nofail` e `x-systemd.device-timeout=45`.

## Consequências

- **A camada bronze tem teto de ~450 GB.** É restrição real, não teórica: JSON de timeline comprimido acumula rápido. Precisa de monitoramento de espaço e, mais adiante, da regra de ciclo de vida prevista no PASSO 20.
- **`nofail` cria risco de escrita silenciosa no lugar errado.** Se a montagem falhar, `/mnt/dados` continua existindo como diretório vazio no disco interno, e qualquer job que escreva ali enche o `sda` sem gerar erro. **Mitigação obrigatória:** todo `.service` que grave em `/mnt/dados` deve declarar `RequiresMountsFor=/mnt/dados` (PASSO 11), para falhar alto em vez de gravar no lugar errado.
- **Backup no mesmo host não é backup externo.** Ter os dumps num disco físico diferente protege contra falha de disco, não contra roubo, incêndio ou apagamento acidental. O PASSO 15 exige restaurar e cronometrar; a cópia para fora da casa continua em aberto.
- O externo, sem FUA e sem nobreak, **não deve receber dado que não possa ser reconstruído**. Bronze é reconstruível apenas dentro da janela de retenção da Riot — fora dela, não é. Isso reforça a prioridade do backup.

## Gatilho de revisão

- **HD externo virar SSD por USB 3.0.** Nesse caso a decisão se inverte parcialmente, como o Apêndice D do manual antecipa: o Postgres passaria a caber no externo e o interno ficaria só com o sistema. **Testar antes uma porta USB 3.0** — a ponte já suporta, e a limitação atual pode ser só o cabo.
- **Compra de nobreak.** Elimina a exposição a corte de energia e permite reavaliar o que pode viver no externo.
- **Bronze passando de ~350 GB.** Momento de decidir entre expandir armazenamento, aplicar ciclo de vida mais agressivo, ou mover o histórico frio para outro lugar.
- **Upgrade para SSD interno.** Muda a premissa de IOPS de toda a Caixa 7 e permitiria reconsiderar o que hoje é evitado por causa de disco mecânico.
