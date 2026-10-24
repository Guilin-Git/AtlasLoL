import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from collector import coletar_ddragon as ddragon


class TestColetarDataDragon(unittest.TestCase):
    def cliente(self):
        def responder(request):
            if request.url.path == "/api/versions.json":
                return httpx.Response(200, json=["16.21.1"])
            recurso = request.url.path.rsplit("/", 1)[-1].removesuffix(".json")
            return httpx.Response(200, json={"resource": recurso})

        return httpx.Client(
            base_url=ddragon.BASE_URL,
            transport=httpx.MockTransport(responder),
        )

    def test_baixa_uma_versao_e_nao_sobrescreve(self):
        with tempfile.TemporaryDirectory() as diretorio, patch.object(
            ddragon, "BRONZE", Path(diretorio)
        ):
            with self.cliente() as client:
                self.assertEqual(
                    ddragon.coletar_com_client(client, "latest", "pt_BR"),
                    ("16.21.1", True),
                )
            with self.cliente() as client:
                self.assertEqual(
                    ddragon.coletar_com_client(client, "latest", "pt_BR"),
                    ("16.21.1", False),
                )
            self.assertTrue(
                (Path(diretorio) / "static/ddragon/version=16.21.1/locale=pt_BR/manifest.json.zst").is_file()
            )

    def test_rejeita_versao_e_locale_invalidos(self):
        with self.assertRaises(ValueError):
            ddragon.validar_versao("16.21")
        with self.assertRaises(ValueError):
            ddragon.validar_locale("pt-br")


if __name__ == "__main__":
    unittest.main()
