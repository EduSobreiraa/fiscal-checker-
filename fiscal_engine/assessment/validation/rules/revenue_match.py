from __future__ import annotations

from ...models import CompanyTaxAssessment, DocumentType, ValidationFinding
from .common import source_value


def revenue_match_rule(assessment: CompanyTaxAssessment) -> list[ValidationFinding]:
    assessed = source_value(assessment, DocumentType.SIMPLES_APURACAO, "revenue.currentPeriod")
    billed = source_value(assessment, DocumentType.FATURAMENTO_SIMPLES, "revenue.currentPeriod")
    if assessed is None or billed is None or assessed == billed:
        return []
    return [ValidationFinding("REVENUE_MISMATCH", "warning", "Faturamento da apuração diverge do demonstrativo de faturamento.",
                              "revenue.currentPeriod", expected=assessed, actual=billed,
                              sources=[DocumentType.SIMPLES_APURACAO, DocumentType.FATURAMENTO_SIMPLES])]
