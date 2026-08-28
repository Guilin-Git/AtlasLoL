# Inventário de rede — Atlas homelab

> Topologia, endereços e procedimentos de recuperação. Decisão e histórico em [`docs/adr/019-roteador-secundario-e-acesso-ao-homelab.md`](adr/019-roteador-secundario-e-acesso-ao-homelab.md).
>
> Última atualização: 2026-08-19

## O fato que determina toda a topologia

**O ONT da operadora não faz ponte entre suas portas LAN.** Cada dispositivo conectado nele fala com o gateway e com a internet, e não fala com os outros. Comprovado nos dois sentidos, com posição de rede verificada:

| Teste | Resultado |
|---|---|
| PC (`192.168.1.53`, LAN1) → gateway `192.168.1.1` | responde, <1 ms |
| PC (LAN1) → Huawei WAN (LAN3), IP **estático** | `Destination host unreachable`, sem entrada ARP |
| PC (LAN1) → Huawei WAN (LAN3), IP **via DHCP do ONT** | `Destination host unreachable`, sem entrada ARP |
| Notebook (atrás do Huawei) → PC (LAN1) | `Destination host unreachable` |

O segundo e o terceiro teste juntos descartam a hipótese de *IP Source Guard* (endereço não reconhecido pelo DHCP do ONT): mesmo com concessão legítima, a comunicação entre portas não acontece.

**Consequência:** qualquer caminho entre PC e homelab que precise atravessar o ONT não funciona. A solução é não atravessá-lo.

## Topologia atual

```
Internet (fibra)
  │
  ▼
ONT ZTE ZXHN F6600P — Canaã Telecom            192.168.1.0/24
  │  gateway 192.168.1.1 · sem admin · portas LAN isoladas entre si
  │
  ├─ LAN1 ──cabo── PC principal                192.168.1.53  (Ethernet, DHCP)
  │                    ▲
  │                    │  internet — rota padrão, banda cheia
  │
  └─ LAN3 ──cabo── WAN do Huawei AX2S          192.168.1.43  (DHCP)
                        │
                        ▼
                   Huawei AX2S                 192.168.3.0/24
                     gateway 192.168.3.1 · admin completo
                        │
                        ├─ Wi-Fi "Guilin-Homelab" ── notebook atlaslol   192.168.3.6  (reservado)
                        │
                        └─ Wi-Fi "Guilin-Homelab" ── PC principal        192.168.3.7  (Wi-Fi, DHCP)
                                                       ▲
                                                       │  acesso ao homelab
```

**O PC está nas duas redes ao mesmo tempo**, com papéis distintos: cabo para internet, Wi-Fi para o homelab. É isso que contorna o isolamento do ONT sem abrir mão da banda do cabo.

### Por que isso funciona — a tabela de rotas

O sistema não escolhe "uma conexão"; decide por destino, com duas regras em ordem:

| Destino | Rota escolhida | Interface | Regra que decidiu |
|---|---|---|---|
| `192.168.3.6` (notebook) | entrega direta em `192.168.3.0/24` | Wi-Fi | prefixo mais específico (/24 vence /0) |
| `192.168.1.x` | entrega direta em `192.168.1.0/24` | Ethernet | prefixo mais específico |
| qualquer outro (internet) | `0.0.0.0/0` via `192.168.1.1` | Ethernet | empate no prefixo → **menor métrica** (25 < 30) |

As duas interfaces ficam em sub-redes **diferentes**, e é isso que torna a decisão inequívoca. Quando ambas estiveram em `192.168.1.x` (o Wi-Fi do PC conectou sozinho no `GUILYN` durante uma madrugada), o resultado foi rota ambígua e falha intermitente.

## Dispositivos sob gestão do projeto

| Hostname | MAC | IP | Rede | Como é fixado |
|---|---|---|---|---|
| atlaslol (notebook) | `5c:c9:d3:6d:c4:63` | `192.168.3.6` | homelab | **reserva de DHCP no Huawei** |
| PC — Ethernet | `30:c5:99:81:19:a5` | variável | ONT | DHCP do ONT (não importa) |
| PC — Wi-Fi | `48:45:e6:c1:68:2f` | variável | homelab | DHCP do Huawei (não importa) |
| Huawei — WAN | `48:ef:61:5b:9d:f9` | variável | ONT | DHCP do ONT (não importa) |

Só **um** endereço precisa ser estável: o do notebook. Ele é garantido por reserva no DHCP do próprio Huawei — par MAC↔IP legítimo por construção, diferente do estático que quebrou no ONT.

## Acesso ao servidor

```
Host servidor
  HostName 192.168.3.6
  User guilin
  IdentityFile ~/.ssh/id_ed25519_atlaslol_servidor
```

Caminho: PC (Wi-Fi, `192.168.3.7`) → Huawei → notebook (`192.168.3.6`). Rede local, sem NAT, sem tradução, sem passar pelo ONT.

## O que foi desativado e não deve voltar

Peças da topologia anterior, que dependia de atravessar o ONT. Todas obsoletas:

| Peça | Estado | Por quê |
|---|---|---|
| Mapeamento de porta 22 no Huawei | pode ser removido | o acesso não passa mais pela WAN |
| Rota estática no PC (`192.168.3.0/24` via `192.168.1.231`) | **removida** | apontava para endereço inexistente e tinha métrica menor que a rota real do Wi-Fi, sequestrando o tráfego |
| IP estático `192.168.1.231` na WAN do Huawei | trocado por DHCP | endereço que o ONT nunca concedeu; ver histórico abaixo |
| Entrada ARP estática no PC para `.231` | remover se ainda existir | `netsh interface ip delete neighbors "Ethernet" 192.168.1.231` |

## Modos de falha conhecidos

Ordenados por probabilidade. Os dois primeiros agem sozinhos, sem ninguém mexer em nada.

| # | Falha | Sintoma | Estado |
|---|---|---|---|
| 1 | PC conecta sozinho no `GUILYN` (Wi-Fi do ONT) | duas interfaces em `192.168.1.x`, rota ambígua, falha intermitente | **mitigado** — perfil `GUILYN` removido do Windows; perfil salvo conecta automaticamente por padrão, mesmo sem marcação explícita |
| 2 | Métrica das interfaces inverter | tudo funciona, mas a internet passa a sair pelo Wi-Fi (banda menor) — falha silenciosa | monitorar; fixar métrica se ocorrer |
| 3 | Wi-Fi do PC não reconecta após reboot/suspensão | internet normal, homelab inacessível | garantir conexão automática no `Guilin-Homelab` |
| 4 | Huawei perde estado após reinício | DHCP ou WAN param de funcionar | já ocorreu uma vez; reiniciar novamente resolveu |

**Descartado:** cheguei a registrar "notebook cai do Wi-Fi por economia de energia do rádio" como falha comprovada, baseado no painel do Huawei mostrar 33 minutos de associação após uma noite. Estava errado — o **roteador** é que tinha reiniciado 50 minutos antes (durante o próprio diagnóstico), e o notebook apenas reconectou depois. O `iw dev wlp2s0 get power_save` confirma `off`. Efeito do diagnóstico interpretado como sintoma.

## Estabilidade observada

Em 2026-08-20, após **vários dias sem intervenção**, `ssh servidor` funcionou de primeira. A topologia sobreviveu a renovações de concessão DHCP nas três interfaces variáveis (Ethernet do PC, Wi-Fi do PC, WAN do Huawei) sem quebrar — confirmando que nenhuma delas está no caminho crítico. O único endereço que precisa ser estável, o do notebook, é garantido por reserva.

## Procedimentos de recuperação

**`ssh servidor` não responde:**

1. No painel do Huawei (`192.168.3.1`), verificar se `atlaslol` aparece conectado e há quanto tempo. Tempo curto = ele caiu e voltou (modo de falha 1)
2. Verificar a posição do PC antes de qualquer teste — `ipconfig` deve mostrar Wi-Fi em `192.168.3.x`. **Todo diagnóstico feito da posição errada mente**
3. `ping 192.168.3.6` — se responder, o problema é o `sshd`, não a rede
4. Se o Wi-Fi do PC estiver em `192.168.1.x`, ele conectou na rede errada (modo de falha 2)

**Regra aprendida na marra:** antes de interpretar qualquer teste de rede, confirmar em qual rede o PC está. Três diagnósticos desta investigação foram invalidados por esse descuido.

**Leitura das mensagens de erro** — cada uma aponta uma camada diferente:

| Mensagem | Significado |
|---|---|
| `Destination host unreachable` (vinda do próprio IP) | ARP falhou; ninguém respondeu no segmento local |
| `Request timed out` | o pacote saiu e não voltou resposta; o caminho existe, algo descartou |
| `Connection refused` | alguém atendeu e recusou; máquina viva, serviço ausente |

## Plano de faixas — rede do homelab (`192.168.3.0/24`)

| Faixa | Uso |
|---|---|
| `.2`–`.49` | Infraestrutura fixa: servidores, nós de cluster, NAS |
| `.50`–`.99` | VMs e experimentos |
| `.100`–`.199` | Dispositivos de teste, descartáveis |
| `.200`–`.254` | Pool dinâmico, não catalogado |

## Como adicionar um dispositivo ao homelab

1. Conecta na rede `Guilin-Homelab` e deixa pegar IP dinâmico
2. Identifica o MAC em **Gerenciar dispositivo** no painel do Huawei
3. Cria a reserva em **Configurações de rede → LAN → Lista de associações de endereço IP estático**, com um IP da faixa correspondente ao papel
4. Registra na tabela de dispositivos acima **antes** de colocar em uso

Nenhum mapeamento de porta é necessário: o PC está na mesma rede.

## Configurações do Huawei alteradas em relação à fábrica

| Configuração | Padrão | Agora | Motivo |
|---|---|---|---|
| Modo de rede | Adaptável | **Roteador primário** | "Adaptável" o colocava como nó mesh secundário, sem NAT/DHCP próprios |
| WAN | DHCP | DHCP | voltou ao padrão; o estático foi revertido |
| Desativar ping da porta WAN | Ligado | Desligado | permite diagnosticar a cadeia com `ping` |
| Segurança Wi-Fi | WPA2-PSK/WPA3-SAE | **WPA2-PSK** | o modo misto causava falha de associação em alguns aparelhos |
| Controle de acesso Wi-Fi | Ligado (lista vazia) | Desligado | sem função com lista vazia; removido para eliminar variável |
| Reserva de DHCP | — | `5c:c9:d3:6d:c4:63` → `192.168.3.6` | o motivo pelo qual o roteador foi comprado |

## Histórico: o IP estático que quebrou sozinho

Vale registrar porque o padrão vai se repetir.

Configuramos manualmente `192.168.1.231` na WAN do Huawei — um endereço dentro do pool do ONT, que ele **nunca concedeu a ninguém**. Funcionou por algumas horas e parou durante a noite, sem ninguém alterar nada. A investigação levantou e descartou, com teste, as hipóteses de loop de camada 2, colisão de IP e IP Source Guard, até concluir que o ONT não faz ponte entre portas — e que o acesso funcionando antes provavelmente dependia de estado transitório do equipamento.

**Regra:** endereço fixo só via reserva no servidor DHCP que atende aquela rede. Nunca por atribuição manual numa rede que não é sua.

## Alvo futuro: modo bridge no ONT

A topologia atual funciona, mas existe por limitação. O destino desejado é o ONT em **modo bridge**, com o Huawei fazendo PPPoE direto e virando o roteador principal de tudo.

O que isso resolveria: uma rede só, sem isolamento, sem PC em duas interfaces, sem NAT duplo, e o cabo do PC ligado ao Huawei com banda cheia.

Bloqueio atual: o menu `Internet` do ONT não expõe configuração de modo WAN, e a operadora condiciona acesso administrativo a plano pago.
