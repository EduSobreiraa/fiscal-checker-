"""Rótulos em português para as saídas destinadas ao analista."""

from __future__ import annotations

import json


RULE_LABELS = {
    "CANCELLED_INCLUDED": "NF-e cancelada incluída na receita",
    "RATE_CONFIGURATION_MISSING": "Parâmetros de cálculo ausentes",
    "DOC_MISSING_IN_SPED": "NF-e ausente na escrituração",
    "DOC_WITHOUT_XML": "Lançamento sem NF-e correspondente",
    "VALUE_MISMATCH": "Valor da NF-e divergente",
    "TAX_BASE_MISMATCH": "Base de PIS/Pasep ou Cofins divergente",
    "TAX_VALUE_MISMATCH": "Valor de PIS/Pasep ou Cofins divergente",
    "RETURN_NOT_DEDUCTED": "Devolução não abatida",
    "DUPLICATE_DOCUMENT": "NF-e duplicada",
    "INVALID_PERIOD": "NF-e fora da competência",
    "ITEM_TOTAL_MISMATCH": "Soma dos itens divergente",
    "MISSING_REQUIRED_FIELD": "Campo obrigatório ausente",
}

SEVERITY_LABELS = {"critical": "Crítica", "high": "Alta", "medium": "Média", "low": "Baixa"}
STATUS_LABELS = {"complete": "concluído", "incomplete": "incompleto", "pending_review": "pendente de revisão"}
TREATMENT_LABELS = {
    "duplicate": "Duplicada", "outside_period": "Fora da competência",
    "cancelled": "Cancelada", "other_issuer": "Outro emitente",
    "sale": "Venda", "return": "Devolução", "unclassified": "Não classificada",
}


def user_error(exc: Exception) -> str:
    """Converte falhas técnicas comuns em mensagens legíveis na interface."""
    if isinstance(exc, json.JSONDecodeError):
        return f"Arquivo JSON inválido (linha {exc.lineno}, coluna {exc.colno})."
    if isinstance(exc, FileNotFoundError):
        return f"Arquivo necessário não encontrado: {exc.filename or 'verifique os arquivos do caso'}."
    if isinstance(exc, FileExistsError):
        return str(exc)
    if isinstance(exc, PermissionError):
        return f"Sem permissão para acessar: {exc.filename or 'arquivo ou pasta do caso'}."
    if isinstance(exc, UnicodeDecodeError):
        return "Arquivo com codificação inválida; use UTF-8."
    if isinstance(exc, KeyError):
        return f"Campo obrigatório ausente nos dados do caso: {exc.args[0]}."
    if isinstance(exc, OSError):
        return "Não foi possível acessar os arquivos do caso. Verifique a pasta e tente novamente."
    return str(exc)
