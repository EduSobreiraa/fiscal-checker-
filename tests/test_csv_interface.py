from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from fiscal_engine.case_io import create_uploaded_case
from fiscal_engine.service import run_case


ROOT = Path(__file__).resolve().parents[1]
XML_CASE = ROOT / "data/synthetic/case-2026-08-comercial-modelo"
CSV_CASE = ROOT / "data/synthetic/case-2026-08-comercial-modelo-csv"


class CsvCaseTests(unittest.TestCase):
    def test_csv_and_xml_cases_find_same_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            xml_result = run_case(XML_CASE, Path(temporary) / "xml", "2026-08")
            csv_result = run_case(CSV_CASE, Path(temporary) / "csv", "2026-08")
        xml_pairs = {(item["rule_id"], item["access_key"]) for item in xml_result["occurrences"]}
        csv_pairs = {(item["rule_id"], item["access_key"]) for item in csv_result["occurrences"]}
        self.assertEqual(csv_pairs, xml_pairs)
        self.assertEqual(csv_result["calculation"]["computed"], xml_result["calculation"]["computed"])
        self.assertEqual(csv_result["calculation"]["eligible_revenue"], "1900.00")
        self.assertTrue(csv_result["evaluation"]["passed"])
        self.assertEqual(csv_result["evaluation"]["with_source_evidence"], 10)
        duplicate = next(item for item in csv_result["occurrences"] if item["rule_id"] == "DUPLICATE_DOCUMENT")
        refs = {source["ref"] for source in duplicate["evidence"]["document_sources"]}
        self.assertEqual(refs, {"nfe-venda-001", "nfe-venda-001-copia"})
        self.assertTrue(all(source["line"] for source in duplicate["evidence"]["document_sources"]))

    def test_upload_creates_manifest_and_does_not_overwrite_case(self) -> None:
        inputs = {
            item["type"]: (CSV_CASE / item["path"]).read_bytes()
            for item in json.loads((CSV_CASE / "manifest.json").read_text(encoding="utf-8"))["files"]
        }
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "inbox"
            options = dict(
                case_id="teste-csv-2026-08", company_id="empresa-ficticia-001",
                company_name="Empresa Fictícia", company_tax_id="99999999000199",
                competencia="2026-08", reference_date=date(2026, 9, 25),
                uploads=inputs, synthetic_profile=CSV_CASE / "config/tax_profile.json",
            )
            case = create_uploaded_case(base, **options)
            raw_before = {(case / path).read_bytes() for path in ("raw/notas/nfe.csv", "raw/escrituracao/lancamentos.csv")}
            result = run_case(case, Path(temporary) / "reports", "2026-08")

            self.assertEqual(result["summary"]["occurrences"], 10)
            self.assertEqual(result["summary"]["input_errors"], 0)
            self.assertEqual(result["calculation"]["computed"]["pis_pasep"], "19.00")
            self.assertEqual(raw_before, {(case / path).read_bytes() for path in ("raw/notas/nfe.csv", "raw/escrituracao/lancamentos.csv")})
            with self.assertRaises(FileExistsError):
                create_uploaded_case(base, **options)

    def test_upload_rejects_path_like_case_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "Identificador"):
                create_uploaded_case(
                    Path(temporary), case_id="../outro", company_id="x", company_name="Empresa",
                    company_tax_id="99999999000199", competencia="2026-08",
                    reference_date=date(2026, 9, 25), uploads={},
                    synthetic_profile=CSV_CASE / "config/tax_profile.json",
                )


if __name__ == "__main__":
    unittest.main()
