# ADR-019 — Roteador secundário e como o PC alcança o homelab

Data: 2026-08-19

## Contexto

O PASSO 5 do manual exige que o PC alcance o notebook por SSH com endereço estável. Isso esbarrou em duas limitações do equipamento da operadora, descobertas em sequência:

1. **O ONT não permite reserva de DHCP.** O aparelho é um ZTE ZXHN F6600P fornecido pela Canaã Telecom. O login disponível (`user`) tem os campos de LAN/DHCP em somente leitura. Após três interações, o suporte confirmou que acesso administrativo — mesmo para configuração puramente local — está condicionado à contratação de um serviço pago que o plano atual não contempla.
2. **Sem reserva, o IP do notebook muda.** O lease do ONT é de 24h e foi observado renovando com endereços diferentes ao longo dos testes (o PC passou por `.34`, `.40`, `.46`, `.47`, `.48`).

### Diagnóstico incorreto ao longo do caminho — registrado de propósito

Durante a investigação, concluiu-se erroneamente que o ONT fazia **isolamento de cliente** (bloqueio de comunicação entre dispositivos da própria LAN). Dois testes sustentavam essa conclusão, e **ambos eram inválidos**:

- `ping` para a WAN do roteador secundário falhava porque o Huawei vem com **"Desativar o ping da porta WAN" ligado de fábrica** — comportamento normal de segurança, não falha de rede.
- `ping` para o notebook falhava porque ele estava com **IP estático manual**, e depois porque **faltava a rota estática no PC** para a sub-rede nova.

A pista que corrigiu o diagnóstico foi a mudança de mensagem de `Destination host unreachable` (falha de ARP) para `Request timed out` (pacote saiu, sem resposta) — a segunda prova que o caminho existe. **Não há isolamento no ONT.**

Lição registrada: mensagem de erro de rede carrega informação de camada. Tratar "não funciona" como um único sintoma levou a uma conclusão errada que quase motivou uma decisão de arquitetura desnecessária.

## Alternativas consideradas

1. **Contratar o serviço pago da operadora.** Custo recorrente, prazo de 72h úteis, e resolve apenas este dispositivo — todo equipamento futuro do homelab dependeria de novo pedido.
2. **Modo bridge no ONT.** Seria a solução mais limpa (elimina o NAT duplo). O menu `Internet` do ONT expõe apenas `Estado`, `Segurança`, `DDNS` e `SNTP` — não existe configuração de modo WAN acessível. Bridge em ONT de operadora normalmente é ativado remotamente pelo backend deles.
3. **IP estático manual no notebook, sem roteador novo.** Foi implementado temporariamente (`192.168.1.230`). Funciona, mas não escala: cada dispositivo futuro exigiria o mesmo contorno manual, e o DHCP do ONT poderia entregar o mesmo endereço a outro aparelho.
4. **Roteador próprio atrás do ONT.** Escolhida.
5. **Host DMZ** apontando para o notebook. Encaminharia todas as portas de uma vez, mas só um host pode ser DMZ — quebra na segunda máquina física do homelab.

## Decisão

**Roteador Huawei AX2S (WS7000-42) operando como roteador secundário atrás do ONT, com NAT duplo, e mapeamento de porta por serviço para o que precisa ser alcançado do PC.**

Topologia e endereçamento em [`docs/inventario-rede.md`](../inventario-rede.md).

Pontos da decisão:

- **O PC permanece direto no ONT.** Havia relato de queda de banda (900 → 500 Mbps) com o PC atrás do roteador novo. Essa medição nunca foi conduzida de forma controlada (não se distinguiu cabo de Wi-Fi, nem se comparou medições em sequência), então **não é fato estabelecido** — apenas a razão pela qual a topologia "tudo atrás do roteador novo" não foi adotada.
- **Mapeamento de porta em vez de DMZ.** Menos exposição: apenas a porta 22 encaminhada hoje. Custo: cada serviço futuro do homelab exigirá uma regra própria.
- **Firewall do Huawei permanece ligado.** O mapeamento de porta cria a exceção necessária; não há motivo para desativar a proteção inteira.

## Consequências

- O PC alcança o notebook por `192.168.1.231:22` (WAN do Huawei), não pelo IP real dele (`192.168.3.6`). O alias `servidor` no `~/.ssh/config` abstrai isso.
- **Cada serviço novo do homelab que precise ser acessado do PC exigirá uma regra de mapeamento de porta.** MinIO, Grafana, Postgres, FastAPI, Prometheus — todos passarão por isso enquanto esta topologia durar. É burocracia previsível, e é o principal custo da decisão.
- A cadeia depende de três configurações; se qualquer uma mudar sem a outra, o acesso quebra silenciosamente:
  1. IP estático da WAN do Huawei (`192.168.1.231`)
  2. Reserva de DHCP do notebook no Huawei (`192.168.3.6`)
  3. Regra de mapeamento de porta 22 → `192.168.3.6:22`
- O notebook fica alcançável na porta 22 por qualquer dispositivo da rede doméstica (`192.168.1.0/24`). **Não fica exposto à internet** — o NAT do ONT não tem regra de encaminhamento. Ainda assim, isso torna obrigatórias as camadas de segurança no próprio host: autenticação só por chave e `ufw` no notebook.
- Rota estática persistente no PC (`192.168.3.0/24` via `192.168.1.231`) permite alcançar a sub-rede do homelab diretamente — hoje ainda bloqueada pelo NAT do Huawei para tráfego inbound não mapeado.

## Gatilho de revisão

- **Modo bridge no ONT** (via operadora, ou trocando de plano/operadora): elimina o NAT duplo. O Huawei passaria a fazer PPPoE direto, viraria o roteador principal, e as regras de mapeamento de porta deixariam de ser necessárias — tudo na mesma rede se enxergando. **É o alvo desejado.**
- **Segunda máquina física no homelab**: o custo do mapeamento por serviço dobra. Nesse momento, reconsiderar mover o PC para trás do roteador novo — depois de medir a banda de forma controlada (cabo, mesma ferramenta, medições em sequência).
- **Medição controlada de banda** desmentindo a perda relatada: adotar a topologia com tudo atrás do roteador novo, que é arquiteturalmente mais limpa e elimina toda a burocracia de port forward.
- **Homelab com mais de 3–4 dispositivos de infraestrutura**: considerar segmentação por VLAN com firewall dedicado (pfSense/OPNsense), padrão usado em homelabs maduros. Exige switch gerenciável e hardware próprio — fora de escopo hoje.
