from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from fiscal_engine.service import run_case
from fiscal_engine.triage import client_brief_text


CASE = Path(__file__).resolve().parents[1] / "data/synthetic/case-2026-08-comercial-modelo-csv"


class TriageTests(unittest.TestCase):
    def test_groups_occurrences_and_keeps_internal_findings_out_of_client_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = run_case(CASE, output, "2026-08")
            queue = result["review_queue"]
            draft = (output / "previa-cliente.txt").read_text(encoding="utf-8")
            with (output / "triagem.csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))

        self.assertEqual(len(queue), 6)
        self.assertEqual(len(rows), 6)
        self.assertEqual(sum(item["occurrence_count"] for item in queue), 10)
        self.assertEqual(sum(item["action"] == "solicitar_documento" for item in queue), 1)
        missing = next(item for item in queue if "DOC_WITHOUT_XML" in item["rules"])
        self.assertIn(missing["access_key"], draft)
        self.assertIn("NÃO ENVIAR SEM CONFERÊNCIA", draft)
        self.assertNotIn("Devolução", draft)
        self.assertNotIn("Cofins", draft)
        duplicate = next(item for item in queue if "DUPLICATE_DOCUMENT" in item["rules"])
        self.assertEqual(duplicate["occurrence_count"], 4)
        self.assertEqual(duplicate["action"], "revisar_internamente")
        selected_draft = client_brief_text("Empresa", "2026-08", [missing, duplicate])
        self.assertIn("NF-e duplicada", selected_draft)
        self.assertIn("NÃO ENVIAR SEM CONFERÊNCIA", selected_draft)


if __name__ == "__main__":
    unittest.main()
