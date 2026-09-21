"""Classificação sem alegar correção ou certificação da apuração."""

from __future__ import annotations

from ..models import AssessmentStatus, ValidationFinding


def classify(findings: list[ValidationFinding]) -> AssessmentStatus:
    if any(item.severity == "error" for item in findings):
        return AssessmentStatus.ERRO
    if any(item.severity == "warning" for item in findings):
        return AssessmentStatus.REVISAR
    return AssessmentStatus.SEM_EXCECOES
