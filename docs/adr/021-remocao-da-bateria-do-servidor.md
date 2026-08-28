# ADR-021 — Remoção da bateria do servidor

Data: 2026-08-20

## Contexto

O notebook (Acer Aspire ES1-572, 2016) passou a operar 24/7 ligado à tomada. Medições em 2026-08-19:

```
charge_full         1.966.000 µAh   ← capacidade real
charge_full_design  3.220.000 µAh   ← capacidade de fábrica
```

**39% de desgaste.** Célula de lítio degradada, mantida permanentemente em carga máxima, é o perfil clássico de inchaço — risco físico real, que o manual do projeto classifica explicitamente como risco de incêndio, não exagero.

O kernel **não expõe** `charge_control_end_threshold` para esse hardware — a listagem de `/sys/class/power_supply/BAT1/` não tem nenhum controle de limite de carga. Não há como limitar a carga a ~60% por software.

## Alternativas consideradas

1. **Limitar a carga pela BIOS.** A BIOS Acer desse modelo já demonstrou ser limitada (exigiu desativar Secure Boot e usar Legacy/CSM na instalação). Não verificada, e não confiável como aposta.
2. **Manter a bateria e inspecionar fisicamente** a cada poucos meses, procurando saliência no teclado ou touchpad. Preserva ~1 h de autonomia como no-break parcial, mas depende de disciplina humana num equipamento que fica ligado sem supervisão.
3. **Remover a bateria.** Escolhida.

## Decisão

Remover fisicamente a bateria e operar exclusivamente na tomada.

## Consequências

- **Queda de energia passa a ser corte instantâneo.** Não há mais janela para desligamento gracioso. Some a possibilidade de escrever um timer de shutdown em bateria baixa (que estava planejado como primeiro exercício do PASSO 11).
- **O risco de corrupção aumenta**, e não só pela ausência de buffer. O HD externo reporta:
  ```
  [sdb] Disabling FUA
  [sdb] Write cache: enabled ... doesn't support DPO or FUA
  ```
  Sem FUA, o sistema não consegue forçar uma escrita até o prato; o disco pode confirmar dado que ainda está no cache volátil dele. Queda de energia perde essa escrita silenciosamente.
- **Reforça o ADR-001**: Postgres permanece no disco interno. Colocá-lo no externo por USB somaria latência, desconexão silenciosa e agora ausência de FUA — três formas independentes de corromper.
- O risco físico de inchaço é eliminado.

## Gatilho de revisão

**Comprar um nobreak.** É a substituição correta — faz o que a bateria fazia, sem risco de inchaço, e ainda protege o HD externo e o roteador. A partir daí:

- Configurar desligamento gracioso ao detectar falta de energia (com `nut` ou equivalente), retomando o exercício previsto para o PASSO 11
- Reavaliar se alguma parte do dado quente pode voltar para o disco externo

Enquanto não houver nobreak, tratar toda queda de energia como evento de risco: verificar integridade do Postgres e dos Parquet mais recentes depois de cada uma.
