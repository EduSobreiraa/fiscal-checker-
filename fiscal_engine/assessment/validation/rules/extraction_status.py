from __future__ import annotations

from ...models import CompanyTaxAssessment, ExtractionStatus, ValidationFinding


def extraction_status_rule(assessment: CompanyTaxAssessment) -> list[ValidationFinding]:
    if assessment.extraction["status"] != ExtractionStatus.FAILED:
        return []
    failed = [source.document_type for source in assessment.sources if source.extraction_status == ExtractionStatus.FAILED]
    return [ValidationFinding("EXTRACTION_FAILED", "error", "Não foi possível produzir uma análise confiável porque houve falha de extração.",
                              "extraction.status", sources=failed)]
