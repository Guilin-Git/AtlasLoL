"""Testes offline: HTTP simulado, relógio virtual e bronze temporário.

Executar: python -m unittest discover -s tests -v
Também podem ser executados pelo pytest quando ele for adicionado ao projeto.
"""

import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import zstandard

from collector import coletar_partidas as c


class CheckpointEmMemoria:
    """Dublê que preserva as transições do checkpoint sem exigir PostgreSQL."""

    def __init__(self):
        self.itens = {}

    def obter(self, match_id):
        item = self.itens.get(match_id)
        return None if item is None else SimpleNamespace(**item)

    def registrar_tentativa(self, match_id, _versao):
        item = self.itens.setdefault(match_id, {"status": "pending", "patch": None})
        item["status"] = "pending"

    def marcar_artefatos(self, match_id, *, patch, match_pronto, timeline_pronta):
        self.itens[match_id] = {
            "status": "complete" if match_pronto and timeline_pronta else "pending",
            "patch": patch,
        }

    def marcar_falha(self, match_id, _erro, *, permanente):
        item = self.itens.setdefault(match_id, {"status": "pending", "patch": None})
        item["status"] = "permanent_failure" if permanente else "pending"

    def close(self):
        pass


class TestColetor(unittest.TestCase):
    def setUp(self):
        self.agora = 1000.0
        self.esperas = []
        self.pedidos = []
        self.tempos = []
        temporario = tempfile.TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.bronze = Path(temporario.name)
        self.checkpoints = CheckpointEmMemoria()
        for alvo, valor in (
            ("API_KEY", "chave-ficticia"),
            ("BRONZE", self.bronze),
            ("log", Mock()),
            ("configurar_log", Mock()),
            ("abrir_checkpoint_store", Mock(return_value=self.checkpoints)),
        ):
            self.enterContext(patch.object(c, alvo, valor))
        self.enterContext(patch.object(c.time, "monotonic", lambda: self.agora))
        self.enterContext(patch.object(c.time, "sleep", self.dormir))
        self.enterContext(patch.object(c.random, "uniform", return_value=0.0))

    def dormir(self, segundos):
        self.esperas.append(segundos)
        self.agora += segundos

    def assert_esperas(self, esperadas):
        self.assertEqual(len(self.esperas), len(esperadas))
        for atual, esperada in zip(self.esperas, esperadas, strict=True):
            self.assertAlmostEqual(atual, esperada)

    def cliente(self, responder):
        def handler(request):
            self.pedidos.append(request)
            self.tempos.append(self.agora)
            return responder(request)

        return c.ClienteRiot(transport=httpx.MockTransport(handler))

    def ler_zst(self, caminho):
        with (
            caminho.open("rb") as arquivo,
            zstandard.ZstdDecompressor().stream_reader(arquivo) as leitor,
            io.TextIOWrapper(leitor, encoding="utf-8") as texto,
        ):
            return json.load(texto)

    def executar_main(self, responder, count=2):
        client = self.cliente(responder)
        with (
            patch.object(c, "ClienteRiot", return_value=client),
            patch("sys.argv", ["coletor", "Nome", "BR1", "--count", str(count)]),
        ):
            return c.main()

    def resposta_fluxo(self, request):
        caminho = request.url.path
        if "/accounts/" in caminho:
            return httpx.Response(200, json={"puuid": "puuid-teste"})
        if caminho.endswith("/ids"):
            return httpx.Response(200, json=["BR1_1", "BR1_2"])
        if caminho.endswith("/timeline"):
            return httpx.Response(
                200, json={"info": {"frames": [{"x": 123, "y": 456}]}}
            )
        return httpx.Response(200, json={"info": {"gameVersion": "25.14.633.1234"}})

    def test_autenticacao_e_codificacao_de_segmentos(self):
        with self.cliente(
            lambda _: httpx.Response(200, json={"puuid": "abc"})
        ) as client:
            self.assertEqual(c.obter_puuid(client, "João / #", "BR 1"), "abc")
        pedido = self.pedidos[0]
        self.assertEqual(pedido.headers["X-Riot-Token"], "chave-ficticia")
        self.assertIn(b"Jo%C3%A3o%20%2F%20%23/BR%201", pedido.url.raw_path)

    def test_erros_permanentes_nao_retentam(self):
        for status, excecao in (
            (403, c.ChaveExpirada),
            (404, c.ItemInexistente),
            (400, httpx.HTTPStatusError),
            (401, httpx.HTTPStatusError),
        ):
            with self.subTest(status=status):
                self.pedidos.clear()
                with (
                    self.cliente(
                        lambda _, codigo=status: httpx.Response(codigo)
                    ) as client,
                    self.assertRaises(excecao),
                ):
                    c.requisitar(client, "/teste")
                self.assertEqual(len(self.pedidos), 1)
        self.assertEqual(self.esperas, [])

    def test_backoff_exponencial_e_limite_de_tentativas(self):
        with (
            self.cliente(lambda _: httpx.Response(503)) as client,
            self.assertRaises(c.ErroTransitorio),
        ):
            c.requisitar(client, "/teste")
        self.assertEqual(len(self.pedidos), 5)
        self.assert_esperas([1, 0.2, 2, 4, 8])

    def test_retry_after_prevalece_sobre_backoff(self):
        respostas = iter(
            [
                httpx.Response(429, headers={"Retry-After": "7"}),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        with self.cliente(lambda _: next(respostas)) as client:
            self.assertEqual(c.requisitar(client, "/teste"), {"ok": True})
        self.assertEqual(self.esperas, [7])

    def test_backoff_adiciona_jitter_quando_retry_after_nao_foi_informado(self):
        respostas = iter([httpx.Response(503), httpx.Response(200, json={})])
        with (
            patch.object(c.random, "uniform", return_value=0.25),
            self.cliente(lambda _: next(respostas)) as client,
        ):
            self.assertEqual(c.requisitar(client, "/teste"), {})
        self.assert_esperas([1.25])

    def test_retry_after_invalido_usa_backoff(self):
        for header in ("inválido", "nan", "inf", "-1"):
            with self.subTest(header=header):
                self.esperas.clear()
                respostas = iter(
                    [
                        httpx.Response(
                            503, headers={"Retry-After": header.encode("utf-8")}
                        ),
                        httpx.Response(200, json={}),
                    ]
                )
                with self.cliente(lambda _, itens=respostas: next(itens)) as client:
                    c.requisitar(client, "/teste")
                self.assert_esperas([1, 0.2])

    def test_ultima_tentativa_preserva_espera_para_proximo_item(self):
        respostas = iter(
            [
                httpx.Response(429, headers={"Retry-After": "30"}),
                httpx.Response(200, json={}),
            ]
        )
        with self.cliente(lambda _: next(respostas)) as client:
            with self.assertRaises(c.ErroTransitorio):
                c.requisitar(client, "/primeiro", tentativa=c.MAX_TENTATIVAS)
            c.requisitar(client, "/segundo")
        self.assertEqual(self.esperas, [30])

    def test_timeout_pode_recuperar(self):
        def responder(request):
            if len(self.pedidos) == 1:
                raise httpx.ReadTimeout("timeout simulado", request=request)
            return httpx.Response(200, json={})

        with self.cliente(responder) as client:
            self.assertEqual(c.requisitar(client, "/teste"), {})
        self.assert_esperas([1, 0.2])

    def test_headers_ajustam_ritmo_e_latencia_conta_como_espera(self):
        def responder(_):
            self.agora += 0.25
            return httpx.Response(
                200, json={}, headers={"X-App-Rate-Limit": "10:1,30:120"}
            )

        with self.cliente(responder) as client:
            c.requisitar(client, "/primeiro")
            c.requisitar(client, "/segundo")
        self.assertEqual(self.tempos, [1000, 1004])
        self.assertEqual(self.esperas, [3.75])

    def test_token_bucket_aplica_a_janela_lenta_do_limite_padrao(self):
        with self.cliente(lambda _: httpx.Response(200, json={})) as client:
            c.requisitar(client, "/primeiro")
            c.requisitar(client, "/segundo")
        self.assert_esperas([1.2])

    def test_janela_esgotada_aguarda_reposicao(self):
        with self.cliente(
            lambda _: httpx.Response(
                200,
                json={},
                headers={
                    "X-App-Rate-Limit": "20:1,100:120",
                    "X-App-Rate-Limit-Count": "1:1,100:120",
                },
            )
        ) as client:
            c.requisitar(client, "/primeiro")
            c.requisitar(client, "/segundo")
        self.assertEqual(self.esperas, [120])

    def test_paginacao_respeita_start_e_para_no_fim(self):
        def responder(request):
            inicio = int(request.url.params["start"])
            quantidade = int(request.url.params["count"])
            return httpx.Response(
                200,
                json=[f"BR1_{i}" for i in range(inicio, min(inicio + quantidade, 137))],
            )

        with self.cliente(responder) as client:
            ids = c.listar_match_ids(client, "abc", start=7, count=250)
        self.assertEqual(len(ids), 130)
        self.assertEqual(
            [dict(p.url.params) for p in self.pedidos],
            [
                {"start": "7", "count": "100"},
                {"start": "107", "count": "100"},
            ],
        )

    def test_paginacao_pede_somente_quantidade_restante(self):
        def responder(request):
            inicio = int(request.url.params["start"])
            quantidade = int(request.url.params["count"])
            return httpx.Response(
                200, json=[f"BR1_{i}" for i in range(inicio, inicio + quantidade)]
            )

        with self.cliente(responder) as client:
            self.assertEqual(len(c.listar_match_ids(client, "abc", count=125)), 125)
        self.assertEqual(self.pedidos[-1].url.params["count"], "25")

    def test_patch_defensivo(self):
        for payload in (
            {},
            {"info": None},
            {"info": []},
            {"info": {"gameVersion": 25}},
            {"info": {"gameVersion": "25"}},
            {"info": {"gameVersion": "../../fora"}},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(c.extrair_patch(payload), "desconhecido")
        self.assertEqual(
            c.extrair_patch({"info": {"gameVersion": "25.14.633.1234"}}), "25.14"
        )

    def test_gravacao_preserva_json_e_nao_deixa_temporarios(self):
        caminho = c.caminho_bronze("match", "25.14", "BR1_1")
        payload = {"nome": "João", "info": {"frames": [{"x": 1, "y": 2}]}}
        c.gravar_zst(caminho, payload)
        self.assertEqual(self.ler_zst(caminho), payload)
        self.assertEqual(list(caminho.parent.iterdir()), [caminho])

    def test_interrupcao_nao_publica_arquivo_parcial(self):
        caminho = c.caminho_bronze("match", "25.14", "BR1_1")
        with (
            patch.object(c.json, "dump", side_effect=KeyboardInterrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            c.gravar_zst(caminho, {})
        self.assertFalse(caminho.exists())
        self.assertEqual(list(caminho.parent.iterdir()), [])

    def test_falha_ao_publicar_preserva_arquivo_anterior(self):
        caminho = c.caminho_bronze("match", "25.14", "BR1_1")
        c.gravar_zst(caminho, {"original": True})
        with (
            patch.object(c.os, "replace", side_effect=OSError("disco indisponível")),
            self.assertRaises(OSError),
        ):
            c.gravar_zst(caminho, {"original": False})
        self.assertEqual(self.ler_zst(caminho), {"original": True})
        self.assertEqual(list(caminho.parent.iterdir()), [caminho])

    def test_segunda_execucao_consulta_apenas_conta_e_historico(self):
        self.assertEqual(self.executar_main(self.resposta_fluxo), 0)
        self.assertEqual(len(list(self.bronze.rglob("*.json.zst"))), 4)
        self.pedidos.clear()
        self.assertEqual(self.executar_main(self.resposta_fluxo), 0)
        self.assertEqual(len(self.pedidos), 2)
        resumo = c.log.info.call_args.kwargs["extra"]["contexto"]
        self.assertEqual(
            (resumo["baixadas"], resumo["puladas"], resumo["falharam"]), (0, 2, 0)
        )

    def test_retomada_baixa_so_timeline_que_faltou(self):
        def responder(request):
            if request.url.path.endswith("BR1_1/timeline"):
                raise KeyboardInterrupt
            return self.resposta_fluxo(request)

        self.assertEqual(self.executar_main(responder), 130)
        self.assertTrue(c.caminho_bronze("match", "25.14", "BR1_1").exists())
        self.pedidos.clear()
        self.assertEqual(self.executar_main(self.resposta_fluxo), 0)
        caminhos = [p.url.path for p in self.pedidos]
        self.assertNotIn("/lol/match/v5/matches/BR1_1", caminhos)
        self.assertIn("/lol/match/v5/matches/BR1_1/timeline", caminhos)

    def test_404_nao_impede_partida_seguinte(self):
        def responder(request):
            if request.url.path.endswith("BR1_1"):
                return httpx.Response(404)
            return self.resposta_fluxo(request)

        self.assertEqual(self.executar_main(responder), 1)
        self.assertTrue(c.caminho_bronze("timeline", "25.14", "BR1_2").exists())

    def test_404_fica_no_checkpoint_e_nao_consulta_item_novamente(self):
        def responder(request):
            if request.url.path.endswith("BR1_1"):
                return httpx.Response(404)
            return self.resposta_fluxo(request)

        self.assertEqual(self.executar_main(responder), 1)
        self.assertEqual(self.checkpoints.obter("BR1_1").status, "permanent_failure")
        self.pedidos.clear()
        self.assertEqual(self.executar_main(self.resposta_fluxo), 0)
        self.assertEqual(len(self.pedidos), 2)

    def test_403_aborta_imediatamente(self):
        def responder(request):
            if request.url.path.endswith("BR1_1"):
                return httpx.Response(403)
            return self.resposta_fluxo(request)

        self.assertEqual(self.executar_main(responder), 1)
        self.assertEqual(len(self.pedidos), 3)
        c.log.critical.assert_called_once()

    def test_5xx_esgotado_nao_impede_partida_seguinte(self):
        def responder(request):
            if request.url.path.endswith("BR1_1"):
                return httpx.Response(502)
            return self.resposta_fluxo(request)

        self.assertEqual(self.executar_main(responder), 1)
        tentativas = [p for p in self.pedidos if p.url.path.endswith("BR1_1")]
        self.assertEqual(len(tentativas), c.MAX_TENTATIVAS)
        self.assertTrue(c.caminho_bronze("timeline", "25.14", "BR1_2").exists())


if __name__ == "__main__":
    unittest.main()
