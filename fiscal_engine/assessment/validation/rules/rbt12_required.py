from __future__ import annotations

from ...models import CompanyTaxAssessment, DocumentType, ExtractionStatus, ValidationFinding
from .common import source_value


def rbt12_required_rule(assessment: CompanyTaxAssessment) -> list[ValidationFinding]:
    source = next((item for item in assessment.sources if item.document_type == DocumentType.SIMPLES_APURACAO), None)
    if source is None or source.extraction_status == ExtractionStatus.FAILED:
        return []
    if source_value(assessment, DocumentType.SIMPLES_APURACAO, "revenue.rbt12") is not None:
        return []
    return [ValidationFinding("RBT12_MISSING", "warning", "RBT12 não está disponível no relatório de apuração.",
                              "revenue.rbt12", sources=[DocumentType.SIMPLES_APURACAO])]
