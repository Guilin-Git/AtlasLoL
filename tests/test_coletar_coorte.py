import unittest
from unittest.mock import patch

import httpx

from collector import coletar_coorte as coorte
from collector import coletar_partidas as partidas


class TestColetarCoorte(unittest.TestCase):
    def setUp(self):
        self.agora = 1000.0
        self.esperas = []
        self.pedidos = []
        self.enterContext(patch.object(partidas, "API_KEY", "chave-ficticia"))
        self.enterContext(patch.object(partidas.time, "monotonic", lambda: self.agora))
        self.enterContext(patch.object(partidas.time, "sleep", self.dormir))

    def dormir(self, segundos):
        self.esperas.append(segundos)
        self.agora += segundos

    def cliente(self, responder):
        def handler(request):
            self.pedidos.append(request)
            return responder(request)

        return partidas.ClienteRiot(transport=httpx.MockTransport(handler))

    def test_faixa_imediatamente_acima(self):
        self.assertEqual(coorte.faixa_imediatamente_acima("silver", "IV"), ("SILVER", "III"))
        self.assertEqual(coorte.faixa_imediatamente_acima("SILVER", "I"), ("GOLD", "IV"))
        self.assertEqual(coorte.faixa_imediatamente_acima("DIAMOND", "I"), ("MASTER", None))
        self.assertEqual(coorte.faixa_imediatamente_acima("MASTER", "I"), ("GRANDMASTER", None))
        self.assertEqual(coorte.faixa_imediatamente_acima("GRANDMASTER", "I"), ("CHALLENGER", None))
        self.assertIsNone(coorte.faixa_imediatamente_acima("CHALLENGER", "I"))

    def test_aprovacao_sem_cohort_id_e_rejeitada_pelo_parser(self):
        with (
            patch(
            "sys.argv",
            [
                "coletar_coorte.py",
                "Nome",
                "BR1",
                "--status",
                "approved",
                "--output",
                "coorte.json.zst",
            ],
            ),
            self.assertRaisesRegex(SystemExit, "2"),
        ):
            coorte.main()

    def test_seleciona_puuids_unicos_com_partidas_suficientes(self):
        seeds = coorte.selecionar_sementes(
            [
                {"puuid": "proprio", "wins": 30, "losses": 20, "leaguePoints": 99},
                {"puuid": "poucas", "wins": 2, "losses": 3, "leaguePoints": 100},
                {"puuid": "baixo", "wins": 10, "losses": 10, "leaguePoints": 5, "tier": "SILVER", "rank": "IV"},
                {"puuid": "alto", "wins": 20, "losses": 20, "leaguePoints": 30, "tier": "SILVER", "rank": "III"},
                {"puuid": "alto", "wins": 20, "losses": 20, "leaguePoints": 1},
            ],
            puuid_excluido="proprio",
            minimo_partidas=20,
            limite=10,
        )
        self.assertEqual([seed["puuid"] for seed in seeds], ["alto", "baixo"])
        self.assertEqual(seeds[0]["league_points"], 30)

    def test_descoberta_usa_americas_para_conta_e_br1_para_liga(self):
        def responder(request):
            caminho = request.url.path
            if "/riot/account/" in caminho:
                return httpx.Response(200, json={"puuid": "puuid-proprio"})
            if caminho.endswith("/by-puuid/puuid-proprio"):
                return httpx.Response(
                    200,
                    json=[{"queueType": "RANKED_SOLO_5x5", "tier": "SILVER", "rank": "IV"}],
                )
            if caminho.endswith("/SILVER/IV"):
                return httpx.Response(
                    200,
                    json=[{"puuid": "semente-iv", "wins": 15, "losses": 10, "leaguePoints": 20, "tier": "SILVER", "rank": "IV"}],
                )
            if caminho.endswith("/SILVER/III"):
                return httpx.Response(
                    200,
                    json=[{"puuid": "semente-iii", "wins": 22, "losses": 12, "leaguePoints": 30, "tier": "SILVER", "rank": "III"}],
                )
            self.fail(f"rota inesperada: {caminho}")

        with self.cliente(responder) as client:
            plano = coorte.descobrir_coorte(
                client,
                game_name="Nome",
                tag_line="BR1",
                platform="BR1",
                pagina=1,
                minimo_partidas=20,
                max_sementes=20,
            )

        self.assertEqual([seed["puuid"] for seed in plano["seeds"]], ["semente-iii", "semente-iv"])
        self.assertEqual(self.pedidos[0].url.host, "americas.api.riotgames.com")
        self.assertTrue(all(pedido.url.host == "br1.api.riotgames.com" for pedido in self.pedidos[1:]))
        self.assertEqual(self.pedidos[-1].url.params["page"], "1")

    def test_descoberta_elite_usa_endpoint_proprio_sem_divisao(self):
        def responder(request):
            caminho = request.url.path
            if "/riot/account/" in caminho:
                return httpx.Response(200, json={"puuid": "puuid-proprio"})
            if caminho.endswith("/by-puuid/puuid-proprio"):
                return httpx.Response(
                    200,
                    json=[{"queueType": "RANKED_SOLO_5x5", "tier": "MASTER", "rank": "I"}],
                )
            if caminho.endswith("/masterleagues/by-queue/RANKED_SOLO_5x5"):
                return httpx.Response(
                    200,
                    json={"entries": [{"puuid": "master", "wins": 20, "losses": 10, "leaguePoints": 1}]},
                )
            if caminho.endswith("/grandmasterleagues/by-queue/RANKED_SOLO_5x5"):
                return httpx.Response(
                    200,
                    json={"entries": [{"puuid": "grandmaster", "wins": 25, "losses": 10, "leaguePoints": 2}]},
                )
            self.fail(f"rota inesperada: {caminho}")

        with self.cliente(responder) as client:
            plano = coorte.descobrir_coorte(
                client,
                game_name="Nome",
                tag_line="BR1",
                platform="BR1",
                pagina=1,
                minimo_partidas=20,
                max_sementes=20,
            )

        self.assertEqual(
            plano["faixas"],
            [{"tier": "MASTER", "division": None}, {"tier": "GRANDMASTER", "division": None}],
        )
        self.assertEqual([seed["puuid"] for seed in plano["seeds"]], ["grandmaster", "master"])


if __name__ == "__main__":
    unittest.main()
