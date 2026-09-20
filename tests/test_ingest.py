from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fiscal_engine.parsers import parse_nfe
from fiscal_engine.pipeline import normalize_case


CASE = Path(__file__).resolve().parents[1] / "data/synthetic/case-2026-08-comercial-modelo"


class IngestTests(unittest.TestCase):
    def test_fixture_normalizes_with_provenance_and_cancellation(self) -> None:
        manifest = json.loads((CASE / "manifest.json").read_text(encoding="utf-8"))
        hashes_before = {item["path"]: hashlib.sha256((CASE / item["path"]).read_bytes()).hexdigest() for item in manifest["files"]}

        result = normalize_case(CASE, "2026-08")

        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["documents"]), 6)
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(len(result["bookkeeping"]), 4)
        cancelled = [doc for doc in result["documents"] if doc["status"] == "cancelled"]
        self.assertEqual(len(cancelled), 1)
        self.assertIn("nfe-cancelada-003.xml", cancelled[0]["source_path"])
        self.assertEqual(cancelled[0]["total_value"], "400.00")
        self.assertEqual(result["bookkeeping"][0]["source_line"], 2)
        self.assertEqual(hashes_before, {item["path"]: hashlib.sha256((CASE / item["path"]).read_bytes()).hexdigest() for item in manifest["files"]})

    def test_bad_hash_is_traced_without_losing_other_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "case"
            shutil.copytree(CASE, copied)
            bad = copied / "raw/notas/nfe-venda-002.xml"
            bad.write_bytes(bad.read_bytes() + b"\nmodificado")

            result = normalize_case(copied, "2026-08")

            self.assertEqual(len(result["documents"]), 5)
            self.assertEqual(len(result["errors"]), 1)
            self.assertEqual(result["errors"][0]["source_path"], "raw/notas/nfe-venda-002.xml")
            self.assertIn("SHA-256", result["errors"][0]["message"])

    def test_xml_rejects_doctype(self) -> None:
        with self.assertRaisesRegex(ValueError, "DTD"):
            parse_nfe(b'<!DOCTYPE foo [<!ENTITY x "bar">]><foo/>', "raw/notas/falso.xml")

    def test_wrong_period_does_not_process(self) -> None:
        with self.assertRaisesRegex(ValueError, "Competência"):
            normalize_case(CASE, "2026-09")


if __name__ == "__main__":
    unittest.main()
