from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from fiscal_engine.calculations import calculate
from fiscal_engine.pipeline import normalize_case
from fiscal_engine.reconciliation import reconcile
from fiscal_engine.reports import build_result, write_outputs


CASE = Path(__file__).resolve().parents[1] / "data/synthetic/case-2026-08-comercial-modelo"


def context() -> tuple[dict, dict, dict, dict, dict]:
    metadata = json.loads((CASE / "metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((CASE / "manifest.json").read_text(encoding="utf-8"))
    profile = json.loads((CASE / "config/tax_profile.json").read_text(encoding="utf-8"))
    company = json.loads((CASE / "config/company_profile.json").read_text(encoding="utf-8"))
    normalized = normalize_case(CASE, "2026-08")
    return metadata, manifest, profile, company, normalized


class FullCaseTests(unittest.TestCase):
    def test_all_expected_occurrences_have_source_evidence(self) -> None:
        metadata, manifest, profile, company, normalized = context()
        expected = json.loads((CASE / "expected_occurrences.json").read_text(encoding="utf-8"))
        occurrences = reconcile(normalized, profile, company)

        self.assertEqual(
            Counter((item["rule_id"], item["access_key"]) for item in occurrences),
            Counter((item["rule_id"], item["access_key"]) for item in expected),
        )
        source_paths = {item["path"] for item in manifest["files"]}
        for item in occurrences:
            self.assertEqual(item["status"], "pending_review")
            self.assertIn(item["evidence"]["source_path"], source_paths)
            self.assertTrue(item["message"])
            if item["evidence"].get("source_record"):
                self.assertTrue(any(
                    row["source_record"] == item["evidence"]["source_record"]
                    and row["access_key"] == item["access_key"]
                    for row in normalized["bookkeeping"]
                ))
        cancelled = next(item for item in occurrences if item["rule_id"] == "CANCELLED_INCLUDED")
        self.assertEqual(cancelled["evidence"]["event_paths"], ["raw/notas/evento-cancelamento-003.xml"])
        self.assertEqual(cancelled["expected_value"], "0.00")
        self.assertEqual(cancelled["declared_value"], "400.00")

    def test_calculation_and_report_outputs_are_reproducible(self) -> None:
        metadata, manifest, profile, company, normalized = context()
        calculation = calculate(normalized, profile, company)
        occurrences = reconcile(normalized, profile, company)
        result = build_result(normalized, calculation, occurrences, metadata, manifest)

        self.assertEqual(calculation["gross_sales"], "2050.00")
        self.assertEqual(calculation["returns"], "150.00")
        self.assertEqual(calculation["eligible_revenue"], "1900.00")
        self.assertEqual(calculation["computed"], {"pis_pasep": "19.00", "cofins": "38.00"})
        self.assertEqual(calculation["difference"], {"pis_pasep": "1.00", "cofins": "3.00"})
        self.assertEqual(result["status"], "complete")

        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            write_outputs(first, normalized, result)
            write_outputs(second, normalized, result)
            for filename in ("normalized.json", "calculation.json", "result.json", "occurrences.csv", "report.html"):
                self.assertEqual((first / filename).read_bytes(), (second / filename).read_bytes())
            with (first / "occurrences.csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), len(occurrences))
            self.assertTrue(all(row["source_path"] for row in rows))
            html = (first / "report.html").read_text(encoding="utf-8")
            self.assertIn("Pendente de revisão humana", html)
            self.assertIn("1900.00", html)
            self.assertIn("raw/notas/evento-cancelamento-003.xml", html)
            self.assertIn("raw/notas/evento-cancelamento-003.xml", (first / "result.json").read_text(encoding="utf-8"))

    def test_missing_rate_blocks_calculation_and_creates_occurrence(self) -> None:
        _, _, profile, company, normalized = context()
        del profile["pis_rate"]

        calculation = calculate(normalized, profile, company)
        occurrences = reconcile(normalized, profile, company)

        self.assertEqual(calculation["status"], "incomplete")
        self.assertIsNone(calculation["computed"])
        self.assertEqual(sum(item["rule_id"] == "RATE_CONFIGURATION_MISSING" for item in occurrences), 1)
        self.assertTrue(all(item["rule_id"] != "TAX_VALUE_MISMATCH" for item in occurrences))


if __name__ == "__main__":
    unittest.main()
