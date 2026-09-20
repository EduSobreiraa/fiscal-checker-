"""Agrupa ocorrências em uma fila de revisão por documento."""

from __future__ import annotations

from collections import defaultdict

from .presentation import RULE_LABELS


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def build_review_queue(occurrences: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in occurrences:
        # Uma ocorrência sem chave não deve ser fundida a outras sem chave.
        key = item["access_key"] or item["occurrence_id"]
        grouped[key].append(item)

    queue = []
    for key, items in grouped.items():
        items = sorted(items, key=lambda item: (SEVERITY_ORDER.get(item["severity"], 9), item["rule_id"]))
        rules = {item["rule_id"] for item in items}
        # Pedir XML só faz sentido quando a ausência é a única questão conhecida.
        needs_xml = rules == {"DOC_WITHOUT_XML"} and bool(items[0]["access_key"])
        queue.append({
            "access_key": items[0]["access_key"],
            "priority": items[0]["severity"],
            "occurrence_count": len(items),
            "occurrence_ids": [item["occurrence_id"] for item in items],
            "rules": sorted(rules),
            "reasons": [RULE_LABELS.get(item["rule_id"], item["rule_id"]) for item in items],
            "source_paths": sorted({item["evidence"]["source_path"] for item in items if item["evidence"].get("source_path")}),
            "action": "solicitar_documento" if needs_xml else "revisar_internamente",
            "suggested_request": (
                f"Por favor, envie o XML da NF-e de chave {items[0]['access_key']} "
                "ou confirme onde podemos obtê-lo."
            ) if needs_xml else None,
        })
    return sorted(queue, key=lambda item: (SEVERITY_ORDER.get(item["priority"], 9), item["access_key"] or ""))


def client_request_text(company_name: str, competencia: str, queue: list[dict]) -> str:
    return client_brief_text(company_name, competencia, [item for item in queue if item["suggested_request"]])


def client_brief_text(company_name: str, competencia: str, selected: list[dict]) -> str:
    """Monta uma prévia apenas dos grupos escolhidos pelo analista."""
    lines = [
        "PRÉVIA PARA REVISÃO DO ANALISTA — NÃO ENVIAR SEM CONFERÊNCIA",
        f"Empresa: {company_name}",
        f"Competência: {competencia}",
        "",
        "Pontos para confirmar com o cliente:",
    ]
    for index, item in enumerate(selected, start=1):
        if item["suggested_request"]:
            description = item["suggested_request"]
        else:
            description = (
                f"Pedimos confirmar a NF-e de chave {item['access_key'] or 'não identificada'} "
                f"em relação a: {'; '.join(item['reasons'])}."
            )
        lines.append(f"{index}. {description}")
    if not selected:
        lines.append("Nenhum ponto selecionado nesta análise.")
    lines.extend(["", "Texto sujeito à validação do analista antes de compartilhar."])
    return "\n".join(lines) + "\n"
