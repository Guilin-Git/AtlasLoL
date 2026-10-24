"""Coleta controlada de partidas de uma coorte explicitamente aprovada.

Este comando não é acionado pelo timer da conta de referência. Ele existe para
transformar uma lista revisada de PUUIDs em artefatos bronze, reutilizando os
mesmos limites Riot e checkpoints duráveis do coletor principal.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
import zstandard

from collector.checkpoint import CheckpointStore, CheckpointUnavailable
from collector.coletar_partidas import (
    API_KEY,
    BASE_URL,
    COLLECTOR_VERSION,
    ChaveExpirada,
    ClienteRiot,
    ErroTransitorio,
    ItemInexistente,
    abrir_checkpoint_store,
    buscar_match,
    buscar_timeline,
    caminho_bronze,
    configurar_log,
    extrair_patch,
    gravar_zst,
    indexar_matches,
    ja_baixado,
    listar_match_ids,
    log,
)

LIMITE_SEMENTES = 50
LIMITE_PARTIDAS = 50


@dataclass
class ResultadoColeta:
    baixadas: int = 0
    puladas: int = 0
    falharam: int = 0
    descartadas: int = 0


def ler_manifesto_aprovado(caminho: Path) -> tuple[str, list[str]]:
    """Lê um manifesto JSON (opcionalmente zstd) e extrai PUUIDs únicos."""
    try:
        if caminho.suffix == ".zst":
            with (
                caminho.open("rb") as arquivo,
                zstandard.ZstdDecompressor().stream_reader(arquivo) as leitor,
            ):
                payload = json.load(io.TextIOWrapper(leitor, encoding="utf-8"))
        else:
            with caminho.open(encoding="utf-8") as arquivo:
                payload = json.load(arquivo)
    except (OSError, json.JSONDecodeError, zstandard.ZstdError) as erro:
        raise ValueError("não foi possível ler o manifesto da coorte") from erro

    if not isinstance(payload, dict) or payload.get("status") != "approved":
        raise ValueError("o manifesto precisa ter status 'approved'")
    cohort_id = payload.get("cohort_id")
    sementes = payload.get("seeds")
    if not isinstance(cohort_id, str) or not cohort_id:
        raise ValueError("manifesto sem cohort_id válido")
    if not isinstance(sementes, list) or not sementes:
        raise ValueError("manifesto sem sementes aprovadas")

    puuids: list[str] = []
    vistos: set[str] = set()
    for semente in sementes:
        puuid = semente.get("puuid") if isinstance(semente, dict) else None
        if not isinstance(puuid, str) or not puuid:
            raise ValueError("manifesto contém semente sem puuid válido")
        if puuid not in vistos:
            vistos.add(puuid)
            puuids.append(puuid)
    if len(puuids) > LIMITE_SEMENTES:
        raise ValueError(f"manifesto excede o limite de {LIMITE_SEMENTES} sementes")
    return cohort_id, puuids


def coletar_ids(
    client: ClienteRiot,
    checkpoints: CheckpointStore,
    ids: list[str],
) -> ResultadoColeta:
    """Materializa IDs no bronze com o mesmo checkpoint do coletor principal."""
    resultado = ResultadoColeta()
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
                        checkpoints.registrar_tentativa(match_id, COLLECTOR_VERSION)
                        checkpoints.marcar_artefatos(
                            match_id,
                            patch=patch_existente,
                            match_pronto=True,
                            timeline_pronta=True,
                        )
                    resultado.puladas += 1
                    continue

            estado = checkpoints.obter(match_id)
            if estado is not None and estado.status == "permanent_failure":
                resultado.descartadas += 1
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
                existentes[match_id] = destino_match
            else:
                patch = destino_match.parent.name.removeprefix("patch=")

            destino_timeline = caminho_bronze("timeline", patch, match_id)
            if not ja_baixado(destino_timeline):
                gravar_zst(destino_timeline, buscar_timeline(client, match_id))
            checkpoints.marcar_artefatos(
                match_id,
                patch=patch,
                match_pronto=ja_baixado(destino_match),
                timeline_pronta=ja_baixado(destino_timeline),
            )
            resultado.baixadas += 1
            log.info(
                "partida de coorte coletada",
                extra={"contexto": {"match_id": match_id, "patch": patch}},
            )
        except ItemInexistente:
            resultado.falharam += 1
            checkpoints.marcar_falha(match_id, "HTTP 404", permanente=True)
        except (ErroTransitorio, httpx.HTTPStatusError, ValueError) as erro:
            resultado.falharam += 1
            checkpoints.marcar_falha(match_id, str(erro), permanente=False)
            log.error(str(erro), extra={"contexto": {"match_id": match_id}})
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description="Coleta controlada de uma coorte AtlasLoL")
    parser.add_argument("--manifest", type=Path, required=True, help="Manifesto aprovado JSON ou JSON.ZST")
    parser.add_argument("--matches-per-seed", type=int, default=1)
    parser.add_argument("--max-matches", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.matches_per_seed <= 10:
        parser.error("--matches-per-seed deve estar entre 1 e 10")
    if not 1 <= args.max_matches <= LIMITE_PARTIDAS:
        parser.error(f"--max-matches deve estar entre 1 e {LIMITE_PARTIDAS}")

    configurar_log(uuid.uuid4().hex[:12])
    if not API_KEY:
        log.error("RIOT_API_KEY não definida no ambiente")
        return 1

    inicio = time.monotonic()
    resultado = ResultadoColeta()
    codigo = 0
    checkpoints: CheckpointStore | None = None
    try:
        cohort_id, puuids = ler_manifesto_aprovado(args.manifest)
        checkpoints = abrir_checkpoint_store()
        with ClienteRiot(base_url=BASE_URL, timeout=15.0) as client:
            ids: list[str] = []
            vistos: set[str] = set()
            for puuid in puuids:
                for match_id in listar_match_ids(client, puuid, count=args.matches_per_seed):
                    if match_id not in vistos:
                        vistos.add(match_id)
                        ids.append(match_id)
                    if len(ids) == args.max_matches:
                        break
                if len(ids) == args.max_matches:
                    break
            resultado = coletar_ids(client, checkpoints, ids)
        log.info(
            "coorte coletada",
            extra={
                "contexto": {
                    "cohort_id": cohort_id,
                    "sementes": len(puuids),
                    "partidas_planejadas": len(ids),
                    **resultado.__dict__,
                }
            },
        )
    except ChaveExpirada as erro:
        log.critical(str(erro))
        codigo = 1
    except (
        CheckpointUnavailable,
        ErroTransitorio,
        ItemInexistente,
        httpx.HTTPError,
        OSError,
        ValueError,
    ) as erro:
        log.error("coleta de coorte abortada: %s", erro)
        codigo = 1
    finally:
        if checkpoints is not None:
            checkpoints.close()
        log.info(
            "coleta de coorte encerrada",
            extra={
                "contexto": {
                    **resultado.__dict__,
                    "duracao_s": round(time.monotonic() - inicio, 1),
                    "codigo_saida": codigo or int(resultado.falharam > 0),
                }
            },
        )
    return codigo or int(resultado.falharam > 0)


if __name__ == "__main__":
    sys.exit(main())
