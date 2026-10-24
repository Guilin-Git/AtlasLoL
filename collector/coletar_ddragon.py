"""Baixa dados estáticos versionados do Data Dragon para a camada bronze."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from collector.coletar_partidas import BRONZE, gravar_zst

BASE_URL = "https://ddragon.leagueoflegends.com"
RECURSOS = ("champion", "item", "runesReforged", "summoner")


def validar_versao(versao: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", versao):
        raise ValueError("versão Data Dragon inválida")
    return versao


def validar_locale(locale: str) -> str:
    if not re.fullmatch(r"[a-z]{2}_[A-Z]{2}", locale):
        raise ValueError("locale Data Dragon inválido")
    return locale


def caminho_ddragon(versao: str, locale: str, recurso: str) -> Path:
    if recurso not in RECURSOS and recurso != "manifest":
        raise ValueError("recurso Data Dragon inválido")
    return BRONZE / "static" / "ddragon" / f"version={versao}" / f"locale={locale}" / f"{recurso}.json.zst"


def requisitar_json(client: httpx.Client, caminho: str) -> Any:
    resposta = client.get(caminho)
    resposta.raise_for_status()
    try:
        return resposta.json()
    except ValueError as erro:
        raise ValueError("resposta Data Dragon não contém JSON válido") from erro


def resolver_versao(client: httpx.Client, versao: str) -> str:
    if versao != "latest":
        return validar_versao(versao)
    disponiveis = requisitar_json(client, "/api/versions.json")
    if not isinstance(disponiveis, list) or not disponiveis or not isinstance(disponiveis[0], str):
        raise ValueError("lista de versões Data Dragon inválida")
    return validar_versao(disponiveis[0])


def artefatos_completos(versao: str, locale: str) -> bool:
    return all(caminho_ddragon(versao, locale, recurso).is_file() for recurso in (*RECURSOS, "manifest"))


def coletar_com_client(
    client: httpx.Client, versao_solicitada: str, locale: str
) -> tuple[str, bool]:
    """Baixa uma versão uma única vez; retorna versão e se houve escrita."""
    locale = validar_locale(locale)
    versao = resolver_versao(client, versao_solicitada)
    if artefatos_completos(versao, locale):
        return versao, False

    for recurso in RECURSOS:
        payload = requisitar_json(client, f"/cdn/{versao}/data/{locale}/{recurso}.json")
        gravar_zst(caminho_ddragon(versao, locale, recurso), payload)
    gravar_zst(
        caminho_ddragon(versao, locale, "manifest"),
        {
            "source": "riot-data-dragon",
            "version": versao,
            "locale": locale,
            "resources": list(RECURSOS),
            "collected_at": datetime.now(UTC).isoformat(),
        },
    )
    return versao, True


def coletar(versao_solicitada: str, locale: str) -> tuple[str, bool]:
    with httpx.Client(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as client:
        return coletar_com_client(client, versao_solicitada, locale)


def main() -> int:
    parser = argparse.ArgumentParser(description="Coleta Data Dragon versionado no bronze")
    parser.add_argument("--version", default="latest", help="Versão X.Y.Z ou latest")
    parser.add_argument("--locale", default="pt_BR", help="Locale no formato pt_BR")
    args = parser.parse_args()
    try:
        versao, baixado = coletar(args.version, args.locale)
    except (httpx.HTTPError, OSError, ValueError) as erro:
        print(f"coleta Data Dragon abortada: {erro}", file=sys.stderr)
        return 1
    acao = "baixada" if baixado else "já presente; ignorada"
    print(f"versão Data Dragon {versao}: {acao}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
