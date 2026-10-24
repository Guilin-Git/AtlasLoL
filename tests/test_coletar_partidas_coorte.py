import json
import tempfile
import unittest
from pathlib import Path

import zstandard

from collector.coletar_partidas_coorte import ler_manifesto_aprovado


class TestManifestoCoorte(unittest.TestCase):
    def escrever(self, diretorio: Path, nome: str, payload: dict) -> Path:
        caminho = diretorio / nome
        if caminho.suffix == ".zst":
            with (
                caminho.open("wb") as arquivo,
                zstandard.ZstdCompressor().stream_writer(arquivo) as escritor,
            ):
                escritor.write(json.dumps(payload).encode())
        else:
            caminho.write_text(json.dumps(payload), encoding="utf-8")
        return caminho

    def test_le_manifesto_aprovado_e_deduplica_puuids(self):
        payload = {
            "status": "approved",
            "cohort_id": "teste-br",
            "seeds": [{"puuid": "a"}, {"puuid": "a"}, {"puuid": "b"}],
        }
        with tempfile.TemporaryDirectory() as diretorio:
            caminho = self.escrever(Path(diretorio), "coorte.json.zst", payload)
            self.assertEqual(ler_manifesto_aprovado(caminho), ("teste-br", ["a", "b"]))

    def test_rejeita_manifesto_nao_aprovado(self):
        payload = {"status": "candidate", "cohort_id": "teste", "seeds": [{"puuid": "a"}]}
        with tempfile.TemporaryDirectory() as diretorio:
            caminho = self.escrever(Path(diretorio), "coorte.json", payload)
            with self.assertRaisesRegex(ValueError, "status 'approved'"):
                ler_manifesto_aprovado(caminho)


if __name__ == "__main__":
    unittest.main()
