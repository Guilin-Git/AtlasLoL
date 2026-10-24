"""Descobre uma pequena coorte ranqueada sem iniciar coleta de partidas.

Esta etapa apenas produz sementes (PUUIDs) para revisao humana. A coleta das
partidas dessas sementes sera uma etapa posterior, separada do timer da conta
de teste e, no futuro, da atualizacao de contas vinculadas por usuarios.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from collector.coletar_partidas import (
    API_KEY,
    ChaveExpirada,
    ClienteRiot,
    ErroTransitorio,
    ItemInexistente,
    RespostaInvalida,
    configurar_log,
    gravar_zst,
    log,
    obter_puuid,
    requisitar,
)

FILA_RANQUEADA_SOLO = "RANKED_SOLO_5x5"
TIERS_COM_DIVISAO = (
    "IRON",
    "BRONZE",
    "SILVER",
    "GOLD",
    "PLATINUM",
    "EMERALD",
    "DIAMOND",
)
TIERS_ELITE = ("MASTER", "GRANDMASTER", "CHALLENGER")
DIVISOES = ("IV", "III", "II", "I")
ROTAS_ELITE = {
    "MASTER": "/lol/league/v4/masterleagues/by-queue/{queue}",
    "GRANDMASTER": "/lol/league/v4/grandmasterleagues/by-queue/{queue}",
    "CHALLENGER": "/lol/league/v4/challengerleagues/by-queue/{queue}",
}


def base_plataforma(platform: str) -> str:
    """Converte BR1 em sua origem de API de plataforma."""
    platform_normalizada = platform.upper()
    if platform_normalizada != "BR1":
        raise ValueError("a descoberta inicial de coorte suporta somente BR1")
    return f"https://{platform_normalizada.lower()}.api.riotgames.com"


def faixa_imediatamente_acima(tier: str, divisao: str | None) -> tuple[str, str | None] | None:
    """Retorna a proxima faixa ranqueada, por exemplo SILVER IV -> SILVER III."""
    tier = tier.upper()
    divisao = divisao.upper() if isinstance(divisao, str) else None
    if tier in TIERS_ELITE:
        indice_elite = TIERS_ELITE.index(tier)
        if indice_elite == len(TIERS_ELITE) - 1:
            return None
        return TIERS_ELITE[indice_elite + 1], None
    if tier not in TIERS_COM_DIVISAO or divisao not in DIVISOES:
        raise ValueError("tier ou divisao nao suportados para a coorte inicial")
    indice_divisao = DIVISOES.index(divisao)
    if indice_divisao < len(DIVISOES) - 1:
        return tier, DIVISOES[indice_divisao + 1]
    indice_tier = TIERS_COM_DIVISAO.index(tier)
    if indice_tier == len(TIERS_COM_DIVISAO) - 1:
        return "MASTER", None
    return TIERS_COM_DIVISAO[indice_tier + 1], DIVISOES[0]


def obter_faixa_ranqueada(
    client: ClienteRiot, puuid: str, platform: str
) -> tuple[str, str | None]:
    """Obtém tier e divisão Solo/Duo diretamente pelo PUUID estável."""
    payload = requisitar(
        client,
        f"/lol/league/v4/entries/by-puuid/{quote(puuid, safe='')}",
        base_url=base_plataforma(platform),
    )
    if not isinstance(payload, list):
        raise RespostaInvalida("resposta de liga nao e uma lista")
    for entrada in payload:
        if (
            isinstance(entrada, dict)
            and entrada.get("queueType") == FILA_RANQUEADA_SOLO
            and isinstance(entrada.get("tier"), str)
            and isinstance(entrada.get("rank"), str)
        ):
            tier = entrada["tier"].upper()
            divisao = entrada["rank"].upper()
            return tier, None if tier in TIERS_ELITE else divisao
    raise RespostaInvalida("jogador sem classificacao RANKED_SOLO_5x5")


def listar_entradas(
    client: ClienteRiot,
    *,
    platform: str,
    tier: str,
    divisao: str | None,
    pagina: int,
) -> list[dict[str, Any]]:
    """Lista entradas League-V4, inclusive nos endpoints próprios dos elos elite."""
    if tier in TIERS_ELITE:
        payload = requisitar(
            client,
            ROTAS_ELITE[tier].format(queue=FILA_RANQUEADA_SOLO),
            base_url=base_plataforma(platform),
        )
        entradas = payload.get("entries") if isinstance(payload, dict) else None
        if not isinstance(entradas, list) or any(not isinstance(item, dict) for item in entradas):
            raise RespostaInvalida("resposta de entradas elite da liga invalida")
        return [{**entrada, "tier": tier, "rank": None} for entrada in entradas]

    if divisao not in DIVISOES:
        raise ValueError("divisao ausente para tier com divisao")
    payload = requisitar(
        client,
        f"/lol/league/v4/entries/{FILA_RANQUEADA_SOLO}/{tier}/{divisao}",
        params={"page": pagina},
        base_url=base_plataforma(platform),
    )
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise RespostaInvalida("resposta de entradas da liga invalida")
    return payload


def selecionar_sementes(
    entradas: list[dict[str, Any]],
    *,
    puuid_excluido: str,
    minimo_partidas: int,
    limite: int,
) -> list[dict[str, Any]]:
    """Filtra e ordena PUUIDs estáveis sem depender de nome de invocador."""
    por_puuid: dict[str, dict[str, Any]] = {}
    for entrada in entradas:
        puuid = entrada.get("puuid")
        vitorias = entrada.get("wins")
        derrotas = entrada.get("losses")
        pontos = entrada.get("leaguePoints", 0)
        if (
            not isinstance(puuid, str)
            or not puuid
            or puuid == puuid_excluido
            or not isinstance(vitorias, int)
            or not isinstance(derrotas, int)
            or vitorias + derrotas < minimo_partidas
        ):
            continue
        candidata = {
            "puuid": puuid,
            "tier": entrada.get("tier"),
            "division": entrada.get("rank"),
            "league_points": pontos if isinstance(pontos, int) else 0,
            "wins": vitorias,
            "losses": derrotas,
        }
        anterior = por_puuid.get(puuid)
        if anterior is None or (
            candidata["league_points"],
            candidata["wins"] + candidata["losses"],
        ) > (
            anterior["league_points"],
            anterior["wins"] + anterior["losses"],
        ):
            por_puuid[puuid] = candidata
    ordenadas = sorted(
        por_puuid.values(),
        key=lambda item: (-item["league_points"], -(item["wins"] + item["losses"]), item["puuid"]),
    )
    return ordenadas[:limite]


def descobrir_coorte(
    client: ClienteRiot,
    *,
    game_name: str,
    tag_line: str,
    platform: str,
    pagina: int,
    minimo_partidas: int,
    max_sementes: int,
) -> dict[str, Any]:
    """Resolve o jogador, sua faixa e uma faixa imediatamente acima."""
    puuid = obter_puuid(client, game_name, tag_line)
    tier, divisao = obter_faixa_ranqueada(client, puuid, platform)
    faixa_acima = faixa_imediatamente_acima(tier, divisao)
    faixas = [(tier, divisao)]
    if faixa_acima is not None:
        faixas.append(faixa_acima)
    entradas = [
        entrada
        for faixa_tier, faixa_divisao in faixas
        for entrada in listar_entradas(
            client,
            platform=platform,
            tier=faixa_tier,
            divisao=faixa_divisao,
            pagina=pagina,
        )
    ]
    sementes = selecionar_sementes(
        entradas,
        puuid_excluido=puuid,
        minimo_partidas=minimo_partidas,
        limite=max_sementes,
    )
    return {
        "source": "riot-league-v4",
        "platform": platform.upper(),
        "queue": FILA_RANQUEADA_SOLO,
        "seed_account": {"game_name": game_name, "tag_line": tag_line, "puuid": puuid},
        "faixas": [
            {"tier": faixa_tier, "division": faixa_divisao}
            for faixa_tier, faixa_divisao in faixas
        ],
        "pagina": pagina,
        "minimo_partidas": minimo_partidas,
        "seeds": sementes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Descobre sementes da coorte AtlasLoL")
    parser.add_argument("game_name", help="Nome do Riot ID, sem a tag")
    parser.add_argument("tag_line", help="Tag do Riot ID, sem o #")
    parser.add_argument("--platform", default="BR1", help="Plataforma Riot (inicialmente BR1)")
    parser.add_argument("--page", default=1, type=int, help="Pagina League-V4")
    parser.add_argument("--min-games", default=20, type=int, help="Partidas ranqueadas minimas")
    parser.add_argument("--max-seeds", default=20, type=int, help="Maximo de PUUIDs para revisao")
    parser.add_argument("--output", type=Path, help="Arquivo .json.zst opcional para a descoberta")
    args = parser.parse_args()
    if args.page <= 0 or args.min_games < 0 or not 1 <= args.max_seeds <= 50:
        parser.error("--page > 0, --min-games >= 0 e --max-seeds entre 1 e 50")

    configurar_log(uuid.uuid4().hex[:12])
    if not API_KEY:
        log.error("RIOT_API_KEY nao definida no ambiente")
        return 1
    inicio = time.monotonic()
    try:
        with ClienteRiot(timeout=15.0) as client:
            plano = descobrir_coorte(
                client,
                game_name=args.game_name,
                tag_line=args.tag_line,
                platform=args.platform,
                pagina=args.page,
                minimo_partidas=args.min_games,
                max_sementes=args.max_seeds,
            )
        if args.output is None:
            print(json.dumps(plano, ensure_ascii=False, indent=2))
        else:
            gravar_zst(args.output, plano)
        log.info(
            "coorte descoberta",
            extra={
                "contexto": {
                    "seeds": len(plano["seeds"]),
                    "faixas": plano["faixas"],
                    "duracao_s": round(time.monotonic() - inicio, 1),
                }
            },
        )
        return 0
    except (ChaveExpirada, ItemInexistente, ErroTransitorio, httpx.HTTPError, ValueError) as erro:
        log.error("descoberta de coorte abortada: %s", erro)
        return 1


if __name__ == "__main__":
    sys.exit(main())
