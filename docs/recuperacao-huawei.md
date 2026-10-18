# Recuperação do Huawei AX2S após reset

Use este documento somente se a senha administrativa do Huawei AX2S não puder
ser recuperada e o reset de fábrica for inevitável. O reset apaga a configuração
do roteador, mas não altera o servidor, os discos, o repositório ou o Ansible.

## Antes de resetar

- Garanta acesso físico ao notebook-servidor `atlaslol`, caso seja preciso
  identificar o IP temporário que ele receberá.
- Mantenha este repositório disponível no PC; `infra/ansible/` reconstrói o
  software do servidor depois que o acesso SSH for recuperado.
- Não copie senhas neste arquivo. Use o gerenciador de senhas ou a credencial
  inicial indicada no equipamento para entrar após o reset.

## Estado a restaurar

| Item | Valor desejado |
| --- | --- |
| Equipamento | Huawei AX2S (WS7000-42), roteador primário da rede do homelab |
| WAN | DHCP pelo ONT, conectado à LAN3 do ONT |
| LAN do homelab | `192.168.3.0/24` |
| Painel administrativo | `http://192.168.3.1` |
| Wi-Fi | `Guilin-Homelab` |
| Segurança Wi-Fi | WPA2-PSK |
| Controle de acesso Wi-Fi | desativado |
| Ping da porta WAN | habilitado para diagnóstico |
| Reserva DHCP de `atlaslol` | MAC `5c:c9:d3:6d:c4:63` → `192.168.3.6` |

## Ordem de recuperação

1. Conecte o PC ao Wi-Fi padrão do Huawei e entre no painel, configurando uma
   nova senha administrativa.
2. Defina o modo de rede como **roteador primário** e a WAN como **DHCP**.
3. Configure a LAN `192.168.3.0/24`, com gateway `192.168.3.1`.
4. Recrie o Wi-Fi `Guilin-Homelab` com WPA2-PSK e conecte PC e notebook a ele.
5. Crie a reserva DHCP do notebook pelo MAC indicado acima.
6. Confirme que o PC recebe `192.168.3.x` no Wi-Fi e que o notebook volta a
   `192.168.3.6`.
7. Teste `ssh servidor`. Só depois execute o playbook Ansible, se necessário.

## O que não recriar

O PC e o notebook já estão na mesma rede Wi-Fi do Huawei. Logo, **não é
necessário redirecionamento de porta para SSH, PostgreSQL ou outros serviços
internos**. O PC alcança diretamente `192.168.3.6` pela interface Wi-Fi.

Não crie encaminhamento no ONT e não exponha PostgreSQL à internet.

## Referências

- Topologia e endereços: `docs/inventario-rede.md`.
- Decisão arquitetural: `docs/adr/019-roteador-secundario-e-acesso-ao-homelab.md`.
