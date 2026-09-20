from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from fiscal_engine.parsers import safe_xml
from fiscal_engine.presentation import user_error
from fiscal_engine.service import run_case


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "data/synthetic/case-2026-08-comercial-modelo-csv"


class PortugueseErrorsTests(unittest.TestCase):
    def test_report_and_csv_show_portuguese_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = run_case(CASE, output, "2026-08")
            html = (output / "report.html").read_text(encoding="utf-8")
            rows = list(csv.DictReader(io.StringIO((output / "occurrences.csv").read_text(encoding="utf-8"))))
        self.assertEqual(result["status"], "complete")
        self.assertIn("Estado do processamento: concluído", html)
        self.assertIn("NF-e duplicada", html)
        self.assertIn("Severidade: Crítica:", html)
        duplicate = next(row for row in rows if row["rule_id"] == "DUPLICATE_DOCUMENT")
        self.assertEqual(duplicate["regra"], "NF-e duplicada")
        self.assertEqual(duplicate["gravidade"], "Alta")
        self.assertEqual(duplicate["situacao"], "pendente de revisão")

    def test_technical_errors_are_presented_in_portuguese(self) -> None:
        with self.assertRaisesRegex(ValueError, r"XML malformado \(linha 1, coluna"):
            safe_xml(b"<nfe>")
        error = json.JSONDecodeError("Expecting value", "{", 1)
        self.assertEqual(user_error(error), "Arquivo JSON inválido (linha 1, coluna 2).")
        self.assertIn("não encontrado", user_error(FileNotFoundError(2, "No such file", "metadata.json")))
        self.assertEqual(user_error(FileExistsError("O caso já existe")), "O caso já existe")


if __name__ == "__main__":
    unittest.main()
