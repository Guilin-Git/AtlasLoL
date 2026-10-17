# ADR-003 — Ansible para máquina, Terraform para API de serviço

Data: 2026-10-17

## Contexto

O AtlasLoL roda inicialmente em um notebook-servidor já existente na rede local.
Ele não é criado por uma API de nuvem: possui sistema operacional, discos,
usuários e acesso SSH configurados manualmente durante as primeiras caixas do
manual.

Essa configuração manual precisa se tornar reproduzível. Sem código, uma troca
de disco, reinstalação do sistema ou erro humano deixa conhecimento operacional
espalhado em comandos, memória e arquivos fora do repositório.

O primeiro experimento usou Ansible no WSL do PC como controlador e o servidor
`atlaslol` como host gerenciado por SSH. O playbook declarou apenas que
`docker.io` deve estar presente. A primeira execução instalou o pacote; a
segunda não produziu mudança; após remoção manual, uma nova execução o
reinstalou; e `--check` não encontrou mudança pendente.

O servidor usa Ubuntu 26.04, cujo `sudo` padrão é `sudo-rs`. Essa implementação
envolve o prompt informado pelo Ansible e impede que o Ansible Core 2.17
reconheça o momento de enviar a senha de privilégio. O Ubuntu mantém o sudo
tradicional em `/usr/bin/sudo.ws`, que foi configurado somente como executável
de `become` do Ansible.

## Alternativas consideradas

1. **Continuar a configurar por SSH manual.** Funciona para um servidor, mas
   não é uma especificação executável nem prova que a máquina pode ser
   reconstruída.
2. **Terraform para configurar o notebook.** Terraform é apropriado para criar
   e alterar recursos por APIs declarativas. O notebook físico já existe e não
   oferece uma API de provisionamento para Terraform chamar.
3. **Ansible sem agente, via SSH.** Escolhida: usa a conexão já existente, não
   adiciona processo residente ao servidor e descreve o estado da máquina.
4. **Instalar um agente permanente de gerenciamento.** Descartado no MVP:
   aumenta consumo de memória, superfície operacional e não oferece benefício
   para um único host acessível por SSH.

## Decisão

Usar Ansible a partir do WSL para convergir a configuração do notebook-servidor
por SSH. O inventário versionado identifica host, usuário, chave local e
interpretador Python; as chaves privadas continuam fora do repositório.

Os playbooks devem preferir módulos declarativos, como `ansible.builtin.apt`,
em vez de `command`. Um módulo conhece o estado desejado e pode reportar
corretamente se houve mudança; `command` só executa algo e normalmente não
consegue inferir idempotência.

Enquanto o servidor usar Ubuntu 26.04 com Ansible Core 2.17, o inventário fixa
`ansible_become_exe=/usr/bin/sudo.ws`. Isso preserva a exigência de senha de
sudo e contorna apenas a incompatibilidade de prompt do `sudo-rs`.

Terraform permanece reservado para a etapa em que o projeto administrar
recursos expostos por API — por exemplo, VM, rede, IP, bucket ou banco gerenciado
em uma nuvem.

## Consequências

- O estado do servidor deixa de depender exclusivamente de memória e comandos
  manuais; o PASSO 13 poderá transformar serviço, timer, montagem e diretórios
  em roles reutilizáveis.
- Uma execução repetida deve convergir para `changed=0`. Esse é o resultado
  desejado, não ausência de trabalho do playbook.
- A conta `guilin` continua exigindo senha para elevação; a senha não é gravada
  no inventário. Execuções interativas usam `--ask-become-pass`; automação futura
  tratará segredos com `ansible-vault`.
- No WSL, o repositório sob `/mnt/c` é visto como gravável por todos. Por
  segurança, o Ansible não carrega automaticamente `ansible.cfg` dessa pasta;
  os comandos indicam explicitamente `-i inventory.ini`.
- O grupo Docker não foi concedido a `guilin`. Acesso ao socket Docker equivale
  na prática a privilégios administrativos e exige decisão explícita posterior.

## Gatilho de revisão

- Ansible Core passar a suportar o prompt de `sudo-rs`: remover a dependência de
  `/usr/bin/sudo.ws` após teste de `become` bem-sucedido.
- Mais de um servidor ou responsabilidades distintas: separar inventários,
  variáveis e roles por ambiente.
- Entrada em AWS ou outra nuvem: usar Terraform/OpenTofu para os recursos de API
  e manter Ansible para configurar os sistemas operacionais criados.
- Necessidade de execuções não interativas: introduzir `ansible-vault` e uma
  estratégia de credenciais revisada, sem versionar senhas.
