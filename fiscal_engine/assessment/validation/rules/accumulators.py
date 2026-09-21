from __future__ import annotations

from ...models import CompanyTaxAssessment, DocumentType, ValidationFinding


KNOWN_ACCUMULATORS = {"RECEITA_BRUTA", "DEVOLUCOES", "CANCELAMENTOS", "SERVICOS"}


def accumulators_rule(assessment: CompanyTaxAssessment) -> list[ValidationFinding]:
    findings = []
    for item in assessment.accumulators:
        code = item.get("code")
        if code and code not in KNOWN_ACCUMULATORS:
            findings.append(ValidationFinding("UNKNOWN_ACCUMULATOR", "warning", f"Acumulador não reconhecido: {code}.",
                                              "accumulators.code", expected=sorted(KNOWN_ACCUMULATORS), actual=code,
                                              sources=[DocumentType.RESUMO_ACUMULADORES]))
    return findings
