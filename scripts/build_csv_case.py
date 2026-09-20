"""Cria a versão tabular do caso sintético a partir da fixture XML validada."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

from fiscal_engine.pipeline import normalize_case


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/synthetic/case-2026-08-comercial-modelo"
TARGET = ROOT / "data/synthetic/case-2026-08-comercial-modelo-csv"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    normalized = normalize_case(SOURCE, "2026-08")
    if normalized["errors"]:
        raise ValueError("Fixture XML contém erros; não é possível gerar CSV equivalente")
    for relative in (
        "raw/escrituracao/lancamentos.csv", "raw/cadastros/produtos.csv",
        "raw/cadastros/participantes.csv",
        "config/company_profile.json", "config/tax_profile.json", "expected_occurrences.json",
    ):
        target = TARGET / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / relative, target)

    notes = []
    for doc in sorted(normalized["documents"], key=lambda item: item["source_path"]):
        for item in doc["items"]:
            notes.append({
                "document_ref": Path(doc["source_path"]).stem,
                "access_key": doc["access_key"], "issue_date": doc["issue_date"],
                "status": doc["status"], "issuer_tax_id": doc["issuer_tax_id"],
                "recipient_tax_id": doc["recipient_tax_id"], "total_value": doc["total_value"],
                "line_number": item["line_number"], "product_code": item["product_code"],
                "description": item["description"], "ncm": item["ncm"], "cfop": item["cfop"],
                "quantity": item["quantity"], "unit_value": item["unit_value"],
                "item_total": item["total_value"],
            })
    write_csv(TARGET / "raw/notas/nfe.csv", [
        "document_ref", "access_key", "issue_date", "status", "issuer_tax_id",
        "recipient_tax_id", "total_value", "line_number", "product_code", "description",
        "ncm", "cfop", "quantity", "unit_value", "item_total",
    ], notes)
    write_csv(TARGET / "raw/notas/eventos.csv", [
        "access_key", "event_type", "event_status", "occurred_at",
    ], [{
        "access_key": event["access_key"], "event_type": event["event_type"],
        "event_status": event["event_status"], "occurred_at": "2026-08-16T10:00:00-03:00",
    } for event in normalized["events"]])
    declared = normalized["declared"]
    write_csv(TARGET / "raw/declaracoes/valor_informado.csv", ["competencia", "pis_pasep", "cofins"], [{
        "competencia": declared["competencia"], "pis_pasep": declared["pis_pasep"],
        "cofins": declared["cofins"],
    }])

    metadata = json.loads((SOURCE / "metadata.json").read_text(encoding="utf-8"))
    metadata["case_id"] = TARGET.name
    metadata["expected_sources"] = [
        "nfe_csv", "nfe_event_csv", "escrituracao_reduzida_csv",
        "produtos_csv", "participantes_csv", "valor_informado_csv",
    ]
    write_json(TARGET / "metadata.json", metadata)

    types = {
        "raw/notas/nfe.csv": "nfe_csv",
        "raw/notas/eventos.csv": "nfe_event_csv",
        "raw/escrituracao/lancamentos.csv": "escrituracao_reduzida_csv",
        "raw/cadastros/produtos.csv": "produtos_csv",
        "raw/cadastros/participantes.csv": "participantes_csv",
        "raw/declaracoes/valor_informado.csv": "valor_informado_csv",
    }
    files = []
    for relative, kind in sorted(types.items()):
        content = (TARGET / relative).read_bytes()
        files.append({"path": relative, "type": kind, "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)})
    write_json(TARGET / "manifest.json", {
        "case_id": TARGET.name, "company_id": metadata["company_id"],
        "competencia": metadata["competencia"], "collected_at": "2026-09-25T12:00:00Z",
        "source": "synthetic", "files": files,
    })
    print(f"Caso CSV gerado: {TARGET} ({len(files)} fontes)")


if __name__ == "__main__":
    main()
