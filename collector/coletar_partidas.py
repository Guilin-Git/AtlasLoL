from __future__ import annotations

import argparse
import io
import json
import logging
import math
import os
import re
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import zstandard
from dotenv import load_dotenv

from collector.checkpoint import CheckpointStore, CheckpointUnavailable

# --------------------------------------------------------------------------
# Configuração
# --------------------------------------------------------------------------

# Limites da Riot são POR ROUTING VALUE. ACCOUNT-V1 e MATCH-V5 usam a região
# ampla (americas); SUMMONER/LEAGUE usariam br1 — buckets separados, que na
# Caixa 5 poderão rodar em paralelo. Aqui só precisamos de americas.
# Carrega apenas o .env local, se existir. Variáveis já presentes no ambiente
# (incluindo as definidas pelo systemd EnvironmentFile) têm precedência.
load_dotenv()

ROUTING = "americas"
BASE_URL = f"https://{ROUTING}.api.riotgames.com"

BRONZE = Path(os.getenv("ATLAS_BRONZE", "/mnt/dados/bronze"))

# Dev key expira a cada 24h. Nunca commitar: vive em variável de ambiente
# e, no PASSO 11, em EnvironmentFile do systemd.
API_KEY = os.getenv("RIOT_API_KEY")
COLLECTOR_VERSION = os.getenv("ATLAS_COLLECTOR_VERSION", "checkpoint-v1")

log = logging.getLogger("atlas.coletor")


# --------------------------------------------------------------------------
# Log estruturado (pronto — não é o conteúdo do passo)
# --------------------------------------------------------------------------


class FormatadorJson(logging.Formatter):
    """Emite uma linha JSON por evento, com correlation id.

    JSON em vez de texto livre porque no PASSO 38 o Loki vai indexar isso,
    e campo estruturado é consultável — texto livre exige regex frágil.
    """

    def __init__(self, correlation_id: str) -> None:
        super().__init__()
        self.correlation_id = correlation_id

    def format(self, record: logging.LogRecord) -> str:
        evento: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "nivel": record.levelname,
            "correlation_id": self.correlation_id,
            "msg": record.getMessage(),
        }
        # Campos extras passados via logger.info("...", extra={"contexto": {...}})
        contexto = getattr(record, "contexto", None)
        if contexto:
            evento.update(contexto)
        return json.dumps(evento, ensure_ascii=False)


def configurar_log(correlation_id: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FormatadorJson(correlation_id))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


# --------------------------------------------------------------------------
# Classificação de erro
#
# A distinção mais importante do coletor. Ver CLAUDE.md §5:
#   403 -> chave inválida/expirada ou acesso negado. Parar sem retry.
#   429 / 503 -> TRANSITÓRIO. Retentar com backoff, respeitando Retry-After.
#   404 -> PERMANENTE para aquele item. Registrar e seguir para o próximo.
# --------------------------------------------------------------------------


class ChaveExpirada(Exception):
    """403. Falha de autorização fatal; o nome preserva o contrato do coletor."""


class ItemInexistente(Exception):
    """404. Permanente para este item, inofensivo para os demais."""


class ErroTransitorio(Exception):
    """429 / 503 / falha de rede. Vale retentar."""


class RespostaInvalida(ValueError):
    """Resposta incompatível com o contrato do endpoint."""


# --------------------------------------------------------------------------
# Cliente HTTP
# --------------------------------------------------------------------------


def requisitar(
    client: ClienteRiot,
    caminho: str,
    tentativa: int = 1,
    *,
    params: dict[str, int] | None = None,
) -> dict[str, Any] | list[str]:
    """Faz um GET autenticado e devolve o JSON decodificado.

    Concentra toda a política de erro e de rate limit num lugar só.

    O histórico retorna uma lista; os demais endpoints retornam objetos.
    O prazo de espera pertence ao cliente e sobrevive à troca de item,
    inclusive quando a última tentativa recebe 429.
    """
    if not 1 <= tentativa <= MAX_TENTATIVAS:
        raise ValueError("tentativa fora do intervalo permitido")

    for numero in range(tentativa, MAX_TENTATIVAS + 1):
        restante = client.proxima_requisicao - time.monotonic()
        if restante > 0:
            time.sleep(restante)
        inicio = time.monotonic()
        resposta = None
        try:
            resposta = client.get(
                BASE_URL + caminho,
                headers={"X-Riot-Token": API_KEY or ""},
                params=params,
            )
        except httpx.TransportError as erro:
            motivo = type(erro).__name__
        else:
            client.atualizar_limites(resposta.headers, inicio)
            status = resposta.status_code
            if status == 200:
                return resposta.json()
            if status == 403:
                raise ChaveExpirada(
                    "chave expirada ou sem autorização — "
                    "regenerar em developer.riotgames.com; se persistir, verificar acesso"
                )
            if status == 404:
                raise ItemInexistente(caminho)
            if status != 429 and not 500 <= status <= 599:
                resposta.raise_for_status()
                raise ValueError(f"status inesperado: {status}")
            motivo = f"HTTP {status}"

        espera = float(2 ** (numero - 1))
        if resposta is not None and "Retry-After" in resposta.headers:
            try:
                indicada = float(resposta.headers["Retry-After"])
                if math.isfinite(indicada) and indicada >= 0:
                    espera = indicada
            except ValueError:
                pass  # Header inválido: mantém o backoff exponencial.
        client.proxima_requisicao = time.monotonic() + espera
        if numero == MAX_TENTATIVAS:
            raise ErroTransitorio(f"{motivo} após {numero} tentativas: {caminho}")
        log.warning(
            "falha transitória; nova tentativa agendada",
            extra={
                "contexto": {"motivo": motivo, "tentativa": numero, "espera_s": espera}
            },
        )


# Fallback conservador baseado nos limites publicados para chaves pessoais:
# https://developer.riotgames.com/docs/portal#web-apis_api-keys
# Os headers da chave utilizada prevalecem sobre esses valores iniciais.
PAUSA_ENTRE_REQUISICOES = max(1 / 20, 120 / 100)  # 1,2 s entre inícios.
MAX_TENTATIVAS = 5
MAX_IDS_POR_PAGINA = 100


def ler_janelas(header: str) -> dict[int, int]:
    """Converte '20:1,100:120' em {1: 20, 120: 100}."""
    janelas = {}
    for par in header.split(","):
        try:
            quantidade, segundos = map(int, par.split(":"))
        except ValueError:
            continue
        if quantidade >= 0 and segundos > 0:
            janelas[segundos] = quantidade
    return janelas


class ClienteRiot(httpx.Client):
    """Conexões reutilizáveis e ritmo compartilhado pela coleta sequencial.

    Usa prazo monotônico: tempo gasto em rede/disco já conta como espera.
    Não coordena processos concorrentes usando a mesma chave (PASSO 18).
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.pausa = PAUSA_ENTRE_REQUISICOES
        self.proxima_requisicao = 0.0

    def atualizar_limites(self, headers: httpx.Headers, inicio: float) -> None:
        limites = ler_janelas(headers.get("X-App-Rate-Limit", ""))
        consumos = ler_janelas(headers.get("X-App-Rate-Limit-Count", ""))
        intervalos = [s / n for s, n in limites.items() if n > 0]
        if intervalos:
            self.pausa = max(intervalos)
        self.proxima_requisicao = inicio + self.pausa
        for segundos, limite in limites.items():
            if limite > 0 and consumos.get(segundos, 0) >= limite:
                # O header não informa quando a janela começou. Esperar uma
                # janela inteira é conservador, mas evita insistir no limite.
                self.proxima_requisicao = max(
                    self.proxima_requisicao, time.monotonic() + segundos
                )


# --------------------------------------------------------------------------
# Chamadas específicas
#
# Referência: https://developer.riotgames.com/apis#match-v5
# Revalidar caminhos e parâmetros ao atualizar a versão da API.
# --------------------------------------------------------------------------


def obter_puuid(client: ClienteRiot, game_name: str, tag_line: str) -> str:
    """Resolve um Riot ID (nome#tag) para o puuid.

    Endpoint: ACCOUNT-V1, /riot/account/v1/accounts/by-riot-id/{name}/{tag}

    Codifica cada segmento, inclusive '/' e '#', sem alterar a rota.
    """
    nome, tag = quote(game_name, safe=""), quote(tag_line, safe="")
    conta = requisitar(client, f"/riot/account/v1/accounts/by-riot-id/{nome}/{tag}")
    if not isinstance(conta, dict) or not isinstance(conta.get("puuid"), str):
        raise RespostaInvalida("resposta de conta sem puuid válido")
    return conta["puuid"]


def listar_match_ids(
    client: ClienteRiot, puuid: str, start: int = 0, count: int = 20
) -> list[str]:
    """Lista IDs das partidas mais recentes do jogador.

    Endpoint: MATCH-V5, /lol/match/v5/matches/by-puuid/{puuid}/ids

    Pagina em blocos de até 100 IDs, parando quando o histórico termina.

    Nota de escopo: o coletor NÃO conhece janela nenhuma (CLAUDE.md §5).
    Ele baixa o que existir. Filtrar por patch é trabalho do dbt.
    """
    if start < 0 or count < 0:
        raise ValueError("start e count devem ser não negativos")
    ids: list[str] = []
    caminho = f"/lol/match/v5/matches/by-puuid/{quote(puuid, safe='')}/ids"
    while len(ids) < count:
        tamanho = min(MAX_IDS_POR_PAGINA, count - len(ids))
        pagina = requisitar(
            client, caminho, params={"start": start + len(ids), "count": tamanho}
        )
        if not isinstance(pagina, list) or any(not isinstance(i, str) for i in pagina):
            raise RespostaInvalida("resposta de histórico não é uma lista de IDs")
        ids.extend(pagina)
        if len(pagina) < tamanho:
            break
    return ids


def buscar_match(client: ClienteRiot, match_id: str) -> dict[str, Any]:
    """Busca o detalhe de uma partida. Endpoint: /lol/match/v5/matches/{id}"""
    payload = requisitar(client, f"/lol/match/v5/matches/{quote(match_id, safe='')}")
    if not isinstance(payload, dict):
        raise RespostaInvalida("resposta de partida não é um objeto JSON")
    return payload


def buscar_timeline(client: ClienteRiot, match_id: str) -> dict[str, Any]:
    """Busca o timeline (frames com coordenadas x/y).

    Endpoint: /lol/match/v5/matches/{id}/timeline

    É o timeline que viabiliza a Caixa 9 (heatmap de mortes, DBSCAN,
    win probability por minuto). Sem ele o projeto perde metade da graça.
    """
    payload = requisitar(
        client, f"/lol/match/v5/matches/{quote(match_id, safe='')}/timeline"
    )
    if not isinstance(payload, dict):
        raise RespostaInvalida("resposta de timeline não é um objeto JSON")
    return payload


# --------------------------------------------------------------------------
# Escrita no bronze
# --------------------------------------------------------------------------


def extrair_patch(match: dict[str, Any]) -> str:
    """Deriva a partição de patch a partir do gameVersion da partida.

    Ex.: "25.14.633.1234" -> "25.14"

    Esta é a ÚNICA leitura de conteúdo que o coletor faz, e é uma exceção
    consciente à regra de "coletor não parseia": particionar exige conhecer
    um campo. Por isso ela precisa ser defensiva.

    Formatos inesperados vão para 'desconhecido', preservando a coleta.
    """
    info = match.get("info")
    versao = info.get("gameVersion") if isinstance(info, dict) else None
    if isinstance(versao, str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", versao):
        return ".".join(versao.split(".", 2)[:2])
    return "desconhecido"


def caminho_bronze(tipo: str, patch: str, match_id: str) -> Path:
    """Monta o caminho de destino.

    Layout: bronze/{tipo}/patch={patch}/{matchId}.json.zst
    onde tipo é "match" ou "timeline".

    O formato "patch=25.14" é partição estilo Hive — o DuckDB e o dbt
    conseguem podar partições lendo o próprio nome do diretório (PASSO 27).
    """
    if tipo not in {"match", "timeline"}:
        raise ValueError("tipo de arquivo bronze inválido")
    if patch != "desconhecido" and not re.fullmatch(r"[0-9]+\.[0-9]+", patch):
        raise ValueError("patch inválido")
    if not re.fullmatch(r"[A-Za-z0-9]+_[0-9]+", match_id):
        raise ValueError("match_id inválido")
    return BRONZE / tipo / f"patch={patch}" / f"{match_id}.json.zst"


def ja_baixado(caminho: Path) -> bool:
    """Controle primitivo de 'já processei': o arquivo existe?

    Suficiente para este passo. No PASSO 18 vira checkpoint no Postgres,
    com matchId, timestamp e versão do coletor.

    Cuidado: isso só é confiável se a escrita for atômica (ver gravar_zst).
    Arquivo pela metade de uma execução interrompida pareceria "já baixado".
    """
    return caminho.is_file()


def gravar_zst(caminho: Path, payload: dict[str, Any]) -> None:
    """Grava o JSON comprimido com zstd, de forma atômica.

    Serializa em streaming para não criar outra cópia completa do JSON.
    Só publica o nome final depois de fechar o frame zstd e sincronizar.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=caminho.parent, prefix=f".{caminho.name}.", suffix=".tmp", delete=False
        ) as arquivo:
            temporario = Path(arquivo.name)
            with (
                zstandard.ZstdCompressor().stream_writer(arquivo, closefd=False) as zst,
                io.TextIOWrapper(zst, encoding="utf-8") as texto,
            ):
                json.dump(payload, texto, ensure_ascii=False, separators=(",", ":"))
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def indexar_matches(ids: set[str]) -> dict[str, Path]:
    """Uma varredura de nomes; guarda somente as partidas desta execução.

    A partição no caminho funciona como checkpoint sem outro banco/arquivo
    para sincronizar. Temporários não terminam em .json.zst e são ignorados.
    """
    encontrados = {}
    if ids:
        for caminho in (BRONZE / "match").glob("patch=*/*.json.zst"):
            match_id = caminho.name.removesuffix(".json.zst")
            if match_id in ids and caminho.is_file():
                encontrados[match_id] = caminho
    return encontrados


def abrir_checkpoint_store() -> CheckpointStore:
    """Abre o estado durável antes de qualquer chamada que consuma a Riot API."""
    return CheckpointStore.from_environment()


# --------------------------------------------------------------------------
# Fluxo principal
# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Coletor mínimo do Atlas")
    parser.add_argument("game_name", help="Nome do Riot ID, sem a tag")
    parser.add_argument("tag_line", help="Tag do Riot ID, sem o #")
    parser.add_argument("--count", type=int, default=20, help="Quantas partidas")
    args = parser.parse_args()
    if args.count <= 0:
        parser.error("--count deve ser maior que zero")

    correlation_id = uuid.uuid4().hex[:12]
    configurar_log(correlation_id)

    if not API_KEY:
        log.error("RIOT_API_KEY não definida no ambiente")
        return 1

    inicio = time.monotonic()

    baixadas = puladas = falharam = descartadas = 0
    codigo = 0
    checkpoints: CheckpointStore | None = None
    try:
        checkpoints = abrir_checkpoint_store()
        with ClienteRiot(base_url=BASE_URL, timeout=15.0) as client:
            puuid = obter_puuid(client, args.game_name, args.tag_line)
            # Deduplica preservando a ordem, caso o histórico mude ao paginar.
            ids = list(dict.fromkeys(listar_match_ids(client, puuid, count=args.count)))
            existentes = indexar_matches(set(ids))
            for match_id in ids:
                try:
                    destino_match = existentes.get(match_id)
                    if destino_match is not None:
                        patch_existente = destino_match.parent.name.removeprefix("patch=")
                        destino_timeline_existente = caminho_bronze(
                            "timeline", patch_existente, match_id
                        )
                        if ja_baixado(destino_timeline_existente):
                            estado = checkpoints.obter(match_id)
                            if estado is None or estado.status != "complete":
                                checkpoints.registrar_tentativa(
                                    match_id, COLLECTOR_VERSION
                                )
                                checkpoints.marcar_artefatos(
                                    match_id,
                                    patch=patch_existente,
                                    match_pronto=True,
                                    timeline_pronta=True,
                                )
                            puladas += 1
                            continue

                    estado = checkpoints.obter(match_id)
                    if estado is not None and estado.status == "permanent_failure":
                        descartadas += 1
                        log.info(
                            "item permanentemente indisponível; ignorado",
                            extra={"contexto": {"match_id": match_id}},
                        )
                        continue

                    checkpoints.registrar_tentativa(match_id, COLLECTOR_VERSION)
                    if destino_match is None:
                        match = buscar_match(client, match_id)
                        patch = extrair_patch(match)
                        destino_match = caminho_bronze("match", patch, match_id)
                        gravar_zst(destino_match, match)
                        del match  # Libera o detalhe antes de receber a timeline.
                        existentes[match_id] = destino_match
                    else:
                        patch = destino_match.parent.name.removeprefix("patch=")

                    destino_timeline = caminho_bronze("timeline", patch, match_id)
                    timeline_pronta = ja_baixado(destino_timeline)
                    if not timeline_pronta:
                        gravar_zst(destino_timeline, buscar_timeline(client, match_id))
                    checkpoints.marcar_artefatos(
                        match_id,
                        patch=patch,
                        match_pronto=ja_baixado(destino_match),
                        timeline_pronta=ja_baixado(destino_timeline),
                    )
                    baixadas += 1
                    log.info(
                        "partida coletada",
                        extra={"contexto": {"match_id": match_id, "patch": patch}},
                    )
                except ItemInexistente:
                    falharam += 1
                    checkpoints.marcar_falha(match_id, "HTTP 404", permanente=True)
                    log.warning(
                        "item inexistente", extra={"contexto": {"match_id": match_id}}
                    )
                except (ErroTransitorio, httpx.HTTPStatusError, ValueError) as erro:
                    falharam += 1
                    checkpoints.marcar_falha(match_id, str(erro), permanente=False)
                    log.error(str(erro), extra={"contexto": {"match_id": match_id}})
    except ChaveExpirada as erro:
        log.critical(str(erro))
        codigo = 1
    except (
        ItemInexistente,
        ErroTransitorio,
        CheckpointUnavailable,
        httpx.HTTPStatusError,
        ValueError,
        OSError,
    ) as erro:
        log.error("coleta abortada: %s", erro)
        codigo = 1
    except KeyboardInterrupt:
        log.warning("coleta interrompida; arquivos completos serão reutilizados")
        codigo = 130
    finally:
        if checkpoints is not None:
            checkpoints.close()
        log.info(
            "coleta encerrada",
            extra={
                "contexto": {
                    "baixadas": baixadas,
                    "puladas": puladas,
                    "falharam": falharam,
                    "descartadas": descartadas,
                    "duracao_s": round(time.monotonic() - inicio, 1),
                    "codigo_saida": codigo or int(falharam > 0),
                }
            },
        )
    return codigo or int(falharam > 0)


if __name__ == "__main__":
    sys.exit(main())
