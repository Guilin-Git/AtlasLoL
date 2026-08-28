# Trabalhar no projeto sem acesso ao servidor

Guia para avançar em outra máquina (faculdade, viagem) sem o notebook servidor por perto.

---

## Por que dá para trabalhar sem o servidor

O coletor lê o destino de gravação de uma variável de ambiente:

```python
BRONZE = Path(os.getenv("ATLAS_BRONZE", "/mnt/dados/bronze"))
```

Isso não é detalhe de conveniência — é o que torna o código **independente da máquina**. Na sua bancada, `ATLAS_BRONZE` aponta para uma pasta local; no servidor, para o HD externo. O código é idêntico nos dois lugares, e é isso que permite escrever e testar em qualquer computador.

Mesmo princípio de "configuração fora do código" que aparece depois em `.tfvars` por ambiente (PASSO 24) e `values.yaml` por ambiente (PASSO 40).

---

## Preparar a máquina nova

Precisa de três coisas: **git**, **Python 3.12+** e **uv**.

```bash
# uv (Linux/macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh

# uv (Windows, PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Clonar e preparar o ambiente:

```bash
git clone https://github.com/Guilin-Git/AtlasLoL.git
cd AtlasLoL
uv sync
```

O `uv sync` lê o `pyproject.toml` e o `uv.lock` e recria exatamente as mesmas versões da sua bancada. É por isso que o `uv.lock` é versionado (ver `.gitignore`).

---

## Criar a branch

```bash
git checkout -b coletor-implementacao
```

Nome descritivo do que a branch faz. Trabalhe nela, não na `main` — assim, se algo ficar pela metade, a `main` continua limpa e você pode voltar ao servidor sem carregar código quebrado.

Ao terminar cada bloco de trabalho:

```bash
git add <arquivos>
git commit -m "coletor: implementa classificação de erro HTTP"
git push -u origin coletor-implementacao
```

Commit pequeno e descritivo, conforme a convenção do `CLAUDE.md` §9.

Quando voltar para a bancada, você mescla — via pull request no GitHub (que já prepara o terreno para o PASSO 17, quando o CI passa a barrar merge com teste vermelho) ou direto:

```bash
git checkout main
git pull
git merge coletor-implementacao
```

---

## O que dá para fazer sem o servidor

### 1. Implementar os `# TODO` do coletor

É o trabalho principal, e o mais valioso. O arquivo é `collector/coletar_partidas.py`, e os pontos abertos são:

| Função | O que resolver |
|---|---|
| `requisitar()` | Classificação de erro (403/404/429/503) e backoff respeitando `Retry-After` |
| `PAUSA_ENTRE_REQUISICOES` | Calcular a partir do limite sustentado, não chutar |
| `obter_puuid()` | Codificação de URL — seu nome tem espaços |
| `listar_match_ids()` | Query params e paginação |
| `extrair_patch()` | Derivar `25.14` de `25.14.633.1234`, tolerando campo ausente |
| `gravar_zst()` | Escrita atômica: temporário + rename |
| `main()` | Orquestração e tratamento das exceções |

Para rodar de verdade, apontando o bronze para uma pasta local:

```bash
export RIOT_API_KEY="RGAPI-..."          # chave nova, expira em 24h
export ATLAS_BRONZE="$PWD/bronze-local"  # fora do repo? não: já está no .gitignore
uv run python collector/coletar_partidas.py "Like Bruce Wayne" "ligui" --count 5
```

No Windows (PowerShell):

```powershell
$env:RIOT_API_KEY = "RGAPI-..."
$env:ATLAS_BRONZE = "$PWD\bronze-local"
uv run python collector/coletar_partidas.py "Like Bruce Wayne" "ligui" --count 5
```

O `.gitignore` já ignora `bronze/`, `.env` e `.env.*`. Ainda assim, **confira `git status` antes de todo commit** — chave de API vazada em repositório é o tipo de erro que não dá para desfazer com `git revert`, porque o histórico permanece.

### 2. Escrever testes

O `CLAUDE.md` §9 pede `pytest`, e as funções puras do coletor são o alvo natural — não precisam de rede nem de servidor:

- `extrair_patch()`: `"25.14.633.1234"` deve virar `"25.14"`; campo ausente não pode levantar exceção; formato inesperado idem
- `caminho_bronze()`: o layout `bronze/match/patch=25.14/BR1_123.json.zst` está correto?
- Classificação de erro: cada status HTTP levanta a exceção certa (dá para simular a resposta sem rede)
- `gravar_zst()`: o conteúdo sobrevive à ida e volta? Sobra arquivo temporário depois de gravar?

Adicionar o pytest ao grupo de desenvolvimento:

```bash
uv add --dev pytest
```

### 3. Escrever o ADR-000

`docs/adr/000-por-que-este-projeto-existe.md` está com o template vazio desde o PASSO 3. É o único ADR que só você pode escrever: por que este projeto existe e qual o critério de sucesso.

### 4. Estudar o que vem

O PASSO 12 (Ansible) é conceitual e o manual pede leitura antes: inventário, playbook, task, role, handler, e por que o módulo `apt` é idempotente e `command` não é.

---

## O que **não** dá para fazer sem o servidor

Para não perder tempo tentando:

- **PASSO 11** (systemd timer) — precisa do servidor rodando a unit
- **Qualquer coisa em `/mnt/dados`** — o HD externo está lá
- **Testar a montagem, o zram, o `sshd`** — configuração de máquina
- **Ansible contra o servidor** (PASSO 12–13) — precisa de SSH até ele

Nota de rede: o acesso ao servidor depende do PC estar conectado ao Wi-Fi `Guilin-Homelab` (ver `docs/inventario-rede.md`). De fora de casa não há acesso — o servidor não está exposto à internet, e por enquanto isso é proposital.

---

## Checklist antes de fechar o notebook

1. `git status` — nada de chave, nada de `bronze-local/`
2. `git push` — trabalho no remoto, não só no disco local
3. Anotar onde parou, se algo ficou pela metade
