# Integração contínua

O workflow [CI](../.github/workflows/ci.yml) é o portão automático de qualidade
do AtlasLoL. Ele não faz deploy, não acessa o servidor e não recebe segredos.
Sua única responsabilidade é responder se uma revisão pode seguir para merge.

## Quando executa

- em todo *pull request* cujo destino é `main`;
- em todo *push* para `main`.

O segundo gatilho protege a `main` durante a transição inicial, quando ainda há
push direto. Após a proteção da branch ser ativada, o fluxo normal passa a ser:

```text
branch de trabalho -> pull request -> CI verde -> merge em main -> Ansible aplica no servidor
```

## Jobs

| Job | O que verifica | Por que é separado |
| --- | --- | --- |
| `lint` | `ruff check collector api tests` | Detecta problemas de estilo, imports e erros estáticos rapidamente. |
| `test` | `pytest -q` | Confirma o comportamento esperado sem depender do servidor ou da Riot API. |
| `build-api` | `docker build` da imagem FastAPI | Garante que o Dockerfile e as dependências ainda produzem uma imagem executável. |

Os jobs rodam em paralelo, em runners efêmeros `ubuntu-24.04` do GitHub. O
`uv sync --locked --dev` instala exatamente as dependências registradas em
`uv.lock`; se o lock estiver incoerente com o projeto, a execução falha em vez
de alterá-lo silenciosamente. O cache do `uv` reduz downloads em execuções
posteriores, sem mudar o lockfile.

As actions são fixadas por hash de commit, não apenas por uma tag mutável. Isso
reduz a chance de uma atualização inesperada de action alterar o CI.

## O que este workflow deliberadamente não faz

- não executa `ansible-playbook`;
- não aplica migrations no PostgreSQL do servidor;
- não usa `RIOT_API_KEY`, senha do PostgreSQL ou conteúdo do Ansible Vault;
- não publica imagem nem faz deploy;
- não testa a Riot API real.

Essas operações mudam infraestrutura ou gastam rate limit. Elas continuam sob
controle explícito do operador e são executadas depois do merge, a partir do
WSL, pelo Ansible.

## Entrega assistida no WSL

Depois de revisar e criar o commit em uma branch de trabalho, o fluxo inteiro
de PR pode ser feito por um comando:

```bash
bash scripts/entregar-homelab.sh --deploy
```

O script exige uma árvore Git limpa, envia a branch, cria ou reutiliza o pull
request, espera os checks de CI e pede **uma única confirmação** antes do
merge. Após o merge, ele sincroniza `main` localmente e executa o playbook
Ansible. As senhas do Vault, do `sudo` e a frase da chave SSH continuam sendo
solicitadas de forma interativa; o script não armazena credenciais.

Sem `--deploy`, o mesmo script para após o merge. Isso é útil para mudanças
apenas de documentação ou para revisar o deploy separadamente.

## Proteção da branch: etapa posterior à primeira execução verde

Quando a primeira execução deste workflow estiver verde, configurar uma regra
para `main` no GitHub para exigir os checks `lint`, `test` e `build-api` antes
de merge. Só então deixar de fazer push direto na `main`.
