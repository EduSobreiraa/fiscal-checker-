"""Primeiro estágio: ingestão e normalização auditável."""

from __future__ import annotations

import json
from pathlib import Path

from .ingest import load_case
from .parsers import money, normalize_bookkeeping, parse_csv, parse_event, parse_events_csv, parse_nfe, parse_nfe_csv


CSV_FIELDS = {
    "escrituracao_reduzida_csv": {"access_key", "source_record", "document_total", "pis_base", "pis_value", "cofins_base", "cofins_value"},
    "produtos_csv": {"product_code", "description"},
    "participantes_csv": {"tax_id", "name", "role"},
}


def normalize_case(case_dir: Path, competencia: str) -> dict:
    metadata, manifest, files, errors = load_case(case_dir, competencia)
    result = {
        "case_id": metadata["case_id"], "company_id": metadata["company_id"],
        "competencia": competencia, "source": manifest["source"],
        "documents": [], "events": [], "bookkeeping": [], "products": [],
        "participants": [], "declared": None, "errors": errors,
    }
    for entry, data in files:
        source_path = entry["path"]
        kind = entry.get("type")
        try:
            if kind == "nfe_xml":
                result["documents"].append(parse_nfe(data, source_path))
            elif kind == "nfe_csv":
                result["documents"].extend(parse_nfe_csv(data, source_path))
            elif kind == "nfe_event_xml":
                result["events"].append(parse_event(data, source_path))
            elif kind == "nfe_event_csv":
                result["events"].extend(parse_events_csv(data, source_path))
            elif kind in CSV_FIELDS:
                rows = parse_csv(data, CSV_FIELDS[kind], source_path)
                if kind == "escrituracao_reduzida_csv":
                    rows = normalize_bookkeeping(rows)
                target = {
                    "escrituracao_reduzida_csv": "bookkeeping",
                    "produtos_csv": "products",
                    "participantes_csv": "participants",
                }[kind]
                result[target].extend(rows)
            elif kind == "valor_informado_json":
                result["declared"] = json.loads(data)
                if result["declared"].get("competencia") != competencia:
                    raise ValueError("Competência do valor informado divergente")
                for field in ("pis_pasep", "cofins"):
                    result["declared"][field] = money(result["declared"].get(field), field)
                result["declared"]["source_path"] = source_path
            elif kind == "valor_informado_csv":
                rows = parse_csv(data, {"competencia", "pis_pasep", "cofins"}, source_path)
                if len(rows) != 1 or rows[0]["competencia"] != competencia:
                    raise ValueError("Valor informado deve ter uma linha da competência do caso")
                result["declared"] = rows[0]
                for field in ("pis_pasep", "cofins"):
                    result["declared"][field] = money(result["declared"].get(field), field)
            else:
                raise ValueError(f"Tipo de arquivo desconhecido: {kind}")
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            if isinstance(exc, json.JSONDecodeError):
                message = f"Arquivo JSON inválido (linha {exc.lineno}, coluna {exc.colno})"
            else:
                message = str(exc)
            result["errors"].append({"stage": "parsing", "source_path": source_path, "message": message})
    cancellations = {
        event["access_key"] for event in result["events"]
        if event["event_type"] == "110111" and event["event_status"] in {"135", "136", "155"}
    }
    for document in result["documents"]:
        if document["access_key"] in cancellations:
            document["status"] = "cancelled"
    return result
