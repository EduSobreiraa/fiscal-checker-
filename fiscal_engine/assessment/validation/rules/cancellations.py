from __future__ import annotations

from ...models import CompanyTaxAssessment, DocumentType, ValidationFinding
from .common import source_value


def cancellation_match_rule(assessment: CompanyTaxAssessment) -> list[ValidationFinding]:
    assessed = source_value(assessment, DocumentType.SIMPLES_APURACAO, "revenue.cancellations")
    billed = source_value(assessment, DocumentType.FATURAMENTO_SIMPLES, "revenue.cancellations")
    if assessed is None or billed is None or assessed == billed:
        return []
    return [ValidationFinding("CANCELLATION_MISMATCH", "warning", "Cancelamentos da apuração divergem do demonstrativo de faturamento.",
                              "revenue.cancellations", expected=assessed, actual=billed,
                              sources=[DocumentType.SIMPLES_APURACAO, DocumentType.FATURAMENTO_SIMPLES])]
