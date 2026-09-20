"""Conciliação entre XML, escrituração reduzida e parâmetros do caso."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from .calculations import amount, rates

SEVERITY = {
    "CANCELLED_INCLUDED": "critical", "RATE_CONFIGURATION_MISSING": "critical",
    "DOC_MISSING_IN_SPED": "high", "DOC_WITHOUT_XML": "high", "VALUE_MISMATCH": "high",
    "TAX_BASE_MISMATCH": "high", "TAX_VALUE_MISMATCH": "high", "RETURN_NOT_DEDUCTED": "high",
    "DUPLICATE_DOCUMENT": "high", "INVALID_PERIOD": "medium", "ITEM_TOTAL_MISMATCH": "medium",
    "MISSING_REQUIRED_FIELD": "medium",
}


def reconcile(normalized: dict, profile: dict, company: dict, config_source: str = "config/tax_profile.json") -> list[dict]:
    occurrences: list[dict] = []

    def add(rule: str, message: str, *, key: str | None = None, doc: dict | None = None,
            row: dict | None = None, expected: str | None = None, declared: str | None = None,
            extra: dict | None = None) -> None:
        evidence = {
            "access_key": key,
            "xml_path": doc["source_path"] if doc else None,
            "source_record": row["source_record"] if row else None,
            "source_path": row["source_path"] if row else doc["source_path"] if doc else None,
        }
        if doc and doc.get("source_line"):
            evidence["document_line"] = doc["source_line"]
            evidence["document_ref"] = doc.get("document_ref")
        if row and row.get("source_line"):
            evidence["bookkeeping_line"] = row["source_line"]
        if extra:
            evidence.update(extra)
        occurrences.append({
            "rule_id": rule, "severity": SEVERITY[rule], "status": "pending_review",
            "document_id": doc["document_id"] if doc else f"nfe-{key}" if key else None,
            "access_key": key, "message": message, "evidence": evidence,
            "expected_value": expected, "declared_value": declared,
        })

    for error in normalized["errors"]:
        if "obrigatório" in error["message"].lower() or "ausente" in error["message"].lower():
            add("MISSING_REQUIRED_FIELD", error["message"], extra={"source_path": error["source_path"], "stage": error["stage"]})

    configured_rates = rates(profile)
    if configured_rates is None:
        add("RATE_CONFIGURATION_MISSING", "Parâmetros sintéticos ausentes, inválidos ou não suportados.", extra={"source_path": config_source})

    docs_by_key: dict[str, list[dict]] = defaultdict(list)
    rows_by_key: dict[str, list[dict]] = defaultdict(list)
    for doc in normalized["documents"]:
        docs_by_key[doc["access_key"]].append(doc)
    for row in normalized["bookkeeping"]:
        rows_by_key[row["access_key"]].append(row)

    for key in sorted(docs_by_key):
        docs = sorted(docs_by_key[key], key=lambda item: (item["source_path"], item.get("source_line", 0)))
        doc = docs[0]
        rows = rows_by_key.get(key, [])
        row = rows[0] if rows else None
        if len(docs) > 1:
            add("DUPLICATE_DOCUMENT", "Chave de NF-e repetida nos documentos.", key=key, doc=doc,
                extra={"document_sources": [{"path": item["source_path"], "line": item.get("source_line"), "ref": item.get("document_ref")} for item in docs]})
        if doc["issue_date"][:7] != normalized["competencia"]:
            add("INVALID_PERIOD", "NF-e fora da competência do caso.", key=key, doc=doc,
                expected=normalized["competencia"], declared=doc["issue_date"][:7])
        item_total = sum((amount(item["total_value"]) for item in doc["items"]), Decimal("0"))
        document_total = amount(doc["total_value"])
        if item_total != document_total:
            add("ITEM_TOTAL_MISMATCH", "Soma dos itens difere do total da NF-e.", key=key, doc=doc,
                expected=str(document_total), declared=str(item_total))
        if doc["issue_date"][:7] != normalized["competencia"]:
            continue
        if row is None:
            if doc["status"] != "cancelled":
                add("DOC_MISSING_IN_SPED", "NF-e sem lançamento correspondente na escrituração.", key=key, doc=doc,
                    expected=doc["total_value"])
            continue
        if doc["status"] == "cancelled":
            if row["included_in_revenue"]:
                add("CANCELLED_INCLUDED", "NF-e cancelada incluída na receita escriturada.", key=key, doc=doc, row=row,
                    expected="0.00", declared=row["document_total"], extra={"event_paths": [item["source_path"] for item in normalized["events"] if item["access_key"] == key]})
            continue
        cfops = {item["cfop"] for item in doc["items"]}
        if cfops <= set(profile.get("return_cfops", [])):
            if not row["return_deducted"]:
                add("RETURN_NOT_DEDUCTED", "Devolução não abatida na escrituração sintética.", key=key, doc=doc, row=row,
                    expected=doc["total_value"], declared="0.00")
            continue
        if not cfops <= set(profile.get("sale_cfops", [])) or doc["issuer_tax_id"] != company["tax_id"]:
            continue
        if amount(row["document_total"]) != document_total:
            add("VALUE_MISMATCH", "Total da NF-e diverge do lançamento.", key=key, doc=doc, row=row,
                expected=doc["total_value"], declared=row["document_total"])
        if amount(row["pis_base"]) != document_total or amount(row["cofins_base"]) != document_total:
            add("TAX_BASE_MISMATCH", "Base de PIS/Pasep ou Cofins diverge do total elegível da NF-e.", key=key, doc=doc, row=row,
                expected=doc["total_value"], declared=f"PIS {row['pis_base']}; Cofins {row['cofins_base']}")
        if configured_rates:
            scale = Decimal(profile.get("currency_scale", "0.01"))
            expected_pis = (document_total * configured_rates[0]).quantize(scale, rounding=ROUND_HALF_UP)
            expected_cofins = (document_total * configured_rates[1]).quantize(scale, rounding=ROUND_HALF_UP)
            if amount(row["pis_value"]) != expected_pis or amount(row["cofins_value"]) != expected_cofins:
                add("TAX_VALUE_MISMATCH", "Valores de PIS/Pasep ou Cofins divergem do cálculo sintético por NF-e.", key=key, doc=doc, row=row,
                    expected=f"PIS {expected_pis}; Cofins {expected_cofins}",
                    declared=f"PIS {row['pis_value']}; Cofins {row['cofins_value']}",
                    extra={"config_path": config_source})

    for key in sorted(rows_by_key):
        if key not in docs_by_key:
            row = rows_by_key[key][0]
            add("DOC_WITHOUT_XML", "Lançamento na escrituração sem XML correspondente.", key=key, row=row,
                declared=row["document_total"])

    occurrences.sort(key=lambda item: (item["rule_id"], item["access_key"] or "", item["evidence"]["source_path"] or ""))
    for index, occurrence in enumerate(occurrences, start=1):
        occurrence["occurrence_id"] = f"occ-{index:06d}"
    return occurrences
