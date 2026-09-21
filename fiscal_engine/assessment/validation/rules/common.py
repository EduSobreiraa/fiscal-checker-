from __future__ import annotations

from ...models import CompanyTaxAssessment, DocumentType


def source_value(assessment: CompanyTaxAssessment, document: DocumentType, path: str):
    value = assessment.source_values.get(document, {})
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value
