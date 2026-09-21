from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fiscal_engine.case_io import UPLOAD_TYPES
from fiscal_engine.workspace import Workspace, csv_download

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data/synthetic/case-2026-08-comercial-modelo-csv"


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ws = Workspace(self.root / "data", self.root / "cases")
        self.company_id = self.ws.save_company("Empresa A", "99.999.999/0001-99", "42", "Salvador / BA")
        self.inputs = {kind: (DEMO / path).read_bytes() for kind, path in UPLOAD_TYPES.items()}

    def import_case(self, inputs=None, company_id=None):
        return self.ws.import_files(company_id or self.company_id, "2026-08", self.inputs if inputs is None else inputs,
                                    [], DEMO / "config/tax_profile.json", "Domínio — exportação CSV", "exportação-42")

    def test_reference_inventory_and_batch_do_not_copy_source(self):
        identifier = self.ws.register_reference(self.company_id, "2026-08", DEMO, "Demonstração")
        rows, errors = self.ws.inventory(identifier)
        self.assertFalse(errors)
        self.assertEqual(len(rows), 5)
        self.assertEqual(sum(row["Registros"] for row in rows), 6)
        self.assertEqual(sum(row["Fora da competência"] for row in rows), 1)
        batch = self.ws.run_batch([self.company_id], "2026-08", [])
        item = batch["items"][0]
        self.assertEqual(item["status"], "Com divergências")
        self.assertEqual(len(item["result"]["occurrences"]), 10)
        self.assertTrue(item["result"]["evaluation"]["passed"])
        self.assertNotIn("normalized", item["result"])
        self.assertFalse((self.root / "cases").exists())
        self.assertEqual(self.ws.batch(batch["id"]), batch)

    def test_identical_upload_is_reused_and_new_version_can_be_activated(self):
        first = self.import_case()
        again = self.import_case()
        self.assertEqual(first, again)
        self.assertEqual(len(list((self.root / "cases").iterdir())), 1)
        changed = dict(self.inputs)
        changed["valor_informado_csv"] = changed["valor_informado_csv"].replace(b"18.00", b"17.00")
        second = self.import_case(changed)
        self.assertNotEqual(first, second)
        self.assertEqual(sum(row["active"] for row in self.ws.snapshots(self.company_id, "2026-08")), 1)
        self.assertEqual(self.ws.run_batch([self.company_id], "2026-08", [])["items"][0]["snapshot_id"], second)
        self.ws.activate(first)
        self.assertEqual(self.ws.run_batch([self.company_id], "2026-08", [])["items"][0]["snapshot_id"], first)

    def test_company_failure_does_not_stop_other_companies(self):
        other = self.ws.save_company("Empresa B", "77777777000177")
        self.import_case()
        calls = []
        batch = self.ws.run_batch([other, self.company_id, self.company_id], "2026-08", [], lambda done, total: calls.append((done, total)))
        self.assertEqual(len(batch["items"]), 2)
        self.assertEqual(batch["items"][0]["status"], "Incompleta")
        self.assertIn("Nenhum inventário", batch["items"][0]["error"])
        self.assertEqual(batch["items"][1]["status"], "Com divergências")
        self.assertEqual(calls, [(1, 2), (2, 2)])

    def test_two_company_inventories_and_reviews_stay_separate(self):
        self.import_case()
        other = self.ws.save_company("Empresa B", "77777777000177")
        inputs = {kind: data.replace(b"99999999000199", b"77777777000177") for kind, data in self.inputs.items()}
        self.import_case(inputs, other)
        batch = self.ws.run_batch([self.company_id, other], "2026-08", [])
        first, second = batch["items"]
        self.assertTrue(all(item["status"] == "Com divergências" for item in batch["items"]))
        self.assertNotEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertEqual(len(first["result"]["occurrences"]), len(second["result"]["occurrences"]))
        for finding in second["result"]["occurrences"]:
            if finding["access_key"]:
                self.assertIn("77777777000177", finding["access_key"])
        finding_id = first["result"]["occurrences"][0]["occurrence_id"]
        self.ws.save_review(first["snapshot_id"], finding_id, "Resolvido", "Conferido")
        self.assertEqual(self.ws.review(second["snapshot_id"], finding_id)["status"], "Pendente")

    def test_unavailable_portals_never_appear_as_successful_queries(self):
        self.import_case()
        item = self.ws.run_batch([self.company_id], "2026-08", ["Domínio", "Prefeitura"])["items"][0]
        self.assertEqual(item["status"], "Incompleta")
        self.assertEqual(len(item["result"]["occurrences"]), 10)
        self.assertTrue(all(source["status"] == "Pendente de integração" for source in item["coverage"][1:]))
        self.assertIn("Salvador / BA", item["coverage"][-1]["detail"])

    def test_missing_complements_allow_inventory_but_not_complete_analysis(self):
        identifier = self.import_case({"nfe_csv": self.inputs["nfe_csv"]})
        self.assertEqual(len(self.ws.inventory(identifier)[0]), 5)
        item = self.ws.run_batch([self.company_id], "2026-08", [])["items"][0]
        self.assertEqual(item["status"], "Incompleta")
        self.assertEqual(item["result"]["status"], "incomplete")
        self.assertIn("Faltam", item["error"])

    def test_missing_bookkeeping_even_with_declared_values_is_incomplete(self):
        self.import_case({"nfe_csv": self.inputs["nfe_csv"], "valor_informado_csv": self.inputs["valor_informado_csv"]})
        item = self.ws.run_batch([self.company_id], "2026-08", [])["items"][0]
        self.assertEqual(item["status"], "Incompleta")
        self.assertEqual(item["result"]["calculation"]["status"], "incomplete")

    def test_wrong_company_rejected_without_leaving_uploaded_files(self):
        other = self.ws.save_company("Empresa B", "77777777000177")
        with self.assertRaisesRegex(ValueError, "outra empresa"):
            self.import_case(company_id=other)
        self.assertEqual(list((self.root / "cases").iterdir()), [])
        with self.assertRaisesRegex(ValueError, "CNPJ"):
            self.ws.register_reference(other, "2026-08", DEMO, "Teste")

    def test_wrong_period_and_malformed_inputs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Competência"):
            self.ws.run_batch([self.company_id], "2026-99", [])
        with self.assertRaisesRegex(ValueError, "Competência"):
            self.ws.register_reference(self.company_id, "2026-07", DEMO, "Teste")
        with self.assertRaisesRegex(ValueError, "Colunas"):
            self.import_case({"nfe_csv": b"invalid\n12\n"})

    def test_source_changes_and_hash_tampering_block_reuse(self):
        identifier = self.import_case()
        source = Path(self.ws.snapshot(identifier)["path"])
        profile = source / "config/tax_profile.json"
        profile.write_text(profile.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "mudou"):
            self.ws.inventory(identifier)
        item = self.ws.run_batch([self.company_id], "2026-08", [])["items"][0]
        self.assertIsNone(item["result"])
        self.assertEqual(item["status"], "Incompleta")

    def test_malformed_source_does_not_abort_batch(self):
        identifier = self.import_case()
        source = Path(self.ws.snapshot(identifier)["path"])
        (source / "metadata.json").write_text("[]")
        other = self.ws.save_company("Empresa B", "77777777000177")
        inputs = {kind: data.replace(b"99999999000199", b"77777777000177") for kind, data in self.inputs.items()}
        self.import_case(inputs, other)
        first, second = self.ws.run_batch([self.company_id, other], "2026-08", [])["items"]
        self.assertEqual(first["status"], "Incompleta")
        self.assertIn("objetos JSON", first["error"])
        self.assertEqual(second["status"], "Com divergências")

    def test_truncated_csv_row_is_reported_as_validation_error(self):
        header = self.inputs["nfe_csv"].splitlines()[0]
        with self.assertRaisesRegex(ValueError, "campos ausentes"):
            self.import_case({"nfe_csv": header + b"\nonly-one-cell\n"})

    def test_review_survives_restart_and_rerun_but_not_a_new_version(self):
        identifier = self.import_case()
        finding = self.ws.run_batch([self.company_id], "2026-08", [])["items"][0]["result"]["occurrences"][0]["occurrence_id"]
        self.ws.save_review(identifier, finding, "Em revisão", "Conferindo")
        with self.assertRaisesRegex(ValueError, "Registre"):
            self.ws.save_review(identifier, finding, "Resolvido", "")
        self.ws.save_review(identifier, finding, "Resolvido", "Correção conferida na origem")
        restarted = Workspace(self.root / "data", self.root / "cases")
        rerun = restarted.run_batch([self.company_id], "2026-08", [])
        self.assertEqual(restarted.review(rerun["items"][0]["snapshot_id"], finding)["status"], "Resolvido")
        self.assertEqual(len(restarted.review_history(identifier, finding)), 2)
        changed = dict(self.inputs)
        changed["valor_informado_csv"] += b"\n"
        second = self.import_case(changed)
        self.assertEqual(self.ws.review(second, finding)["status"], "Pendente")

    def test_xml_import_retains_cancellation_event(self):
        xml_case = ROOT / "data/synthetic/case-2026-08-comercial-modelo"
        xmls = [(path.name, path.read_bytes()) for path in sorted((xml_case / "raw/notas").glob("*.xml"))]
        identifier = self.ws.import_files(self.company_id, "2026-08", {}, xmls, DEMO / "config/tax_profile.json", "Importação local")
        rows, errors = self.ws.inventory(identifier)
        self.assertFalse(errors)
        self.assertTrue(any(row["Situação"] == "Cancelada" for row in rows))

    def test_csv_export_neutralizes_spreadsheet_formulas(self):
        data = csv_download([{"Empresa": "=1+1", "CNPJ": "99999999000199"}], ["Empresa", "CNPJ"]).decode("utf-8-sig")
        self.assertIn("'=1+1", data)


if __name__ == "__main__":
    unittest.main()
