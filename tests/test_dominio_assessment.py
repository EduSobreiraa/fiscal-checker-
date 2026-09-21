from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fiscal_engine.assessment.extractors import extract
from fiscal_engine.assessment.models import AssessmentStatus, DocumentType
from fiscal_engine.assessment.normalization import normalize
from fiscal_engine.assessment.service import assess_batch, discover_sources
from fiscal_engine.assessment.validation.results import classify
from fiscal_engine.assessment.validation.rules import (accumulators_rule, cancellation_match_rule,
                                                        extraction_status_rule, rbt12_required_rule,
                                                        revenue_match_rule, source_documents_rule)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/dominio-batch/2026-08"


def assessment_for(folder: str):
    sources = discover_sources(FIXTURES)[folder]
    partials = [extract(source) for source in sources]
    return normalize(partials, {"id": folder, "code": None, "name": folder, "document": None}, "2026-08")


class AssessmentRuleTests(unittest.TestCase):
    def test_revenue_rule_preserves_values_and_sources(self):
        finding = revenue_match_rule(assessment_for("002_EMPRESA_B"))[0]
        self.assertEqual((finding.code, finding.expected, finding.actual), ("REVENUE_MISMATCH", 50000, 57500))
        self.assertEqual(finding.sources, [DocumentType.SIMPLES_APURACAO, DocumentType.FATURAMENTO_SIMPLES])

    def test_rbt12_rule(self):
        findings = rbt12_required_rule(assessment_for("003_EMPRESA_C"))
        self.assertEqual([item.code for item in findings], ["RBT12_MISSING"])

    def test_unknown_accumulator_rule(self):
        findings = accumulators_rule(assessment_for("004_EMPRESA_D"))
        self.assertEqual(findings[0].code, "UNKNOWN_ACCUMULATOR")
        self.assertEqual(findings[0].actual, "AJUSTE_NAO_MAPEADO")

    def test_required_document_rule(self):
        findings = source_documents_rule(assessment_for("005_EMPRESA_E"))
        self.assertEqual(findings[0].code, "SOURCE_DOCUMENT_MISSING")
        self.assertEqual(findings[0].sources, [DocumentType.RESUMO_ACUMULADORES])

    def test_extraction_failure_is_error_and_does_not_add_dependent_rbt12_finding(self):
        assessment = assessment_for("006_EMPRESA_F")
        self.assertEqual([item.code for item in extraction_status_rule(assessment)], ["EXTRACTION_FAILED"])
        self.assertFalse(rbt12_required_rule(assessment))

    def test_returns_do_not_create_exception_when_reports_are_consistent(self):
        assessment = assessment_for("007_EMPRESA_G")
        self.assertEqual(assessment.revenue["returns"], 2000)
        self.assertFalse(revenue_match_rule(assessment))
        self.assertFalse(cancellation_match_rule(assessment))

    def test_cancellation_mismatch(self):
        findings = cancellation_match_rule(assessment_for("008_EMPRESA_H"))
        self.assertEqual((findings[0].code, findings[0].expected, findings[0].actual),
                         ("CANCELLATION_MISMATCH", 1000, 1500))

    def test_classification(self):
        self.assertEqual(classify([]), AssessmentStatus.SEM_EXCECOES)
        self.assertEqual(classify(rbt12_required_rule(assessment_for("003_EMPRESA_C"))), AssessmentStatus.REVISAR)
        self.assertEqual(classify(extraction_status_rule(assessment_for("006_EMPRESA_F"))), AssessmentStatus.ERRO)


class AssessmentBatchTests(unittest.TestCase):
    def test_end_to_end_fixture_batch(self):
        result = assess_batch(FIXTURES)
        self.assertEqual(result["summary"], {"total": 8, "withoutExceptions": 2, "review": 5, "errors": 1})
        companies = {item["company"]["name"]: item for item in result["companies"]}
        self.assertEqual(companies["EMPRESA A"]["status"], AssessmentStatus.SEM_EXCECOES)
        self.assertEqual(companies["EMPRESA G"]["status"], AssessmentStatus.SEM_EXCECOES)
        self.assertEqual(companies["EMPRESA F"]["status"], AssessmentStatus.ERRO)
        self.assertEqual([item["code"] for item in companies["EMPRESA B"]["findings"]], ["REVENUE_MISMATCH"])
        self.assertEqual(companies["EMPRESA B"]["assessment"]["sources"][0]["extraction_status"], "complete")
        self.assertEqual(companies["EMPRESA B"]["assessment"]["sources"][0]["company_id"], "empresa-b")
        self.assertEqual(companies["EMPRESA B"]["assessment"]["sources"][0]["period"], "2026-08")
        self.assertEqual(companies["EMPRESA B"]["assessment"]["source_values"]["SIMPLES_APURACAO"]["revenue"]["currentPeriod"], 50000)
        self.assertEqual(companies["EMPRESA B"]["findings"][0]["sources"], ["SIMPLES_APURACAO", "FATURAMENTO_SIMPLES"])
        json.dumps(result, ensure_ascii=False)

    def test_discovery_catalogues_a_future_pdf_without_inferring_its_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "2026-08" / "001_EMPRESA_TESTE"
            folder.mkdir(parents=True)
            (folder / "simples_apuracao.pdf").write_bytes(b"%PDF-synthetic")
            sources = discover_sources(folder.parent)
            self.assertEqual(sources["001_EMPRESA_TESTE"][0].document_type, DocumentType.SIMPLES_APURACAO)
            result = assess_batch(folder.parent)
            item = result["companies"][0]
            self.assertEqual(item["status"], AssessmentStatus.ERRO)
            self.assertIn("EXTRACTION_FAILED", [finding["code"] for finding in item["findings"]])
            self.assertIn("catalogado", item["assessment"]["extraction"]["warnings"][0])

    def test_invalid_json_is_an_extraction_error_without_stopping_batch(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "2026-08"
            target.mkdir()
            good = target / "001_BOA"
            bad = target / "002_RUIM"
            good.mkdir()
            bad.mkdir()
            for source in (FIXTURES / "001_EMPRESA_A").iterdir():
                (good / source.name.replace(".synthetic", "")).write_bytes(source.read_bytes())
            (bad / "simples_apuracao.json").write_text("{invalido", encoding="utf-8")
            result = assess_batch(target)
            self.assertEqual(result["summary"]["total"], 2)
            self.assertEqual(result["summary"]["withoutExceptions"], 1)
            self.assertEqual(result["summary"]["errors"], 1)


if __name__ == "__main__":
    unittest.main()
