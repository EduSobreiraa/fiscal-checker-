"""Materializa a fixture fictícia. Executar apenas ao alterar o caso de teste."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "data/synthetic/case-2026-08-comercial-modelo"
NS = "http://www.portalfiscal.inf.br/nfe"
ET.register_namespace("", NS)
COMPANY = "99999999000199"  # identificador propositalmente fictício
CUSTOMER = "88888888000188"


def tag(name: str) -> str:
    return f"{{{NS}}}{name}"


def child(parent: ET.Element, name: str, value: str | None = None, **attrs: str) -> ET.Element:
    element = ET.SubElement(parent, tag(name), attrs)
    element.text = value
    return element


def access_key(number: int, month: str = "08") -> str:
    # Chaves com formato de 44 dígitos, apenas para correlação entre fontes sintéticas.
    return f"2926{month}{COMPANY}55001{number:09d}1{number:08d}0"


def write_xml(path: Path, element: ET.Element) -> None:
    ET.indent(element, space="  ")
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(element).write(path, encoding="utf-8", xml_declaration=True)


def invoice(number: int, date: str, amount: str, cfop: str, *, item_amount: str | None = None) -> ET.Element:
    key = access_key(number, date[5:7])
    root = ET.Element(tag("nfeProc"), {"versao": "4.00"})
    nfe = child(root, "NFe")
    info = child(nfe, "infNFe", Id=f"NFe{key}", versao="4.00")
    ide = child(info, "ide")
    for name, value in {
        "cUF": "29", "natOp": "OPERACAO SINTETICA", "mod": "55", "serie": "1",
        "nNF": str(number), "dhEmi": f"{date}T10:00:00-03:00", "tpNF": "0" if cfop.startswith("1") else "1",
    }.items():
        child(ide, name, value)
    emit = child(info, "emit")
    child(emit, "CNPJ", COMPANY)
    child(emit, "xNome", "Comercial Modelo Bahia Ltda.")
    dest = child(info, "dest")
    child(dest, "CNPJ", CUSTOMER)
    child(dest, "xNome", "Cliente Ficticio Ltda.")
    det = child(info, "det", nItem="1")
    prod = child(det, "prod")
    for name, value in {
        "cProd": "PROD-001", "xProd": "Produto sintetico A", "NCM": "00000000",
        "CFOP": cfop, "uCom": "UN", "qCom": "1.0000", "vUnCom": item_amount or amount,
        "vProd": item_amount or amount,
    }.items():
        child(prod, name, value)
    total = child(child(info, "total"), "ICMSTot")
    child(total, "vProd", item_amount or amount)
    child(total, "vNF", amount)
    protocol = child(child(root, "protNFe"), "infProt")
    child(protocol, "chNFe", key)
    child(protocol, "cStat", "100")
    child(protocol, "xMotivo", "Autorizado (simulacao)")
    return root


def cancellation(key: str) -> ET.Element:
    root = ET.Element(tag("procEventoNFe"), {"versao": "1.00"})
    info = child(child(root, "evento"), "infEvento")
    child(info, "chNFe", key)
    child(info, "tpEvento", "110111")
    child(info, "dhEvento", "2026-08-16T10:00:00-03:00")
    result = child(child(root, "retEvento"), "infEvento")
    child(result, "cStat", "135")
    child(result, "xMotivo", "Evento registrado (simulacao)")
    return root


def write_json(relative: str, value: object) -> None:
    path = CASE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(relative: str, fields: list[str], rows: list[dict[str, str]]) -> None:
    path = CASE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    notes = CASE / "raw/notas"
    for filename, number, date, amount, cfop, item_amount in [
        ("nfe-venda-001.xml", 1, "2026-08-05", "1250.00", "5102", None),
        ("nfe-venda-002.xml", 2, "2026-08-08", "800.00", "5102", None),
        ("nfe-cancelada-003.xml", 3, "2026-08-15", "400.00", "5102", None),
        ("nfe-devolucao-004.xml", 4, "2026-08-18", "150.00", "1202", None),
        ("nfe-fora-periodo-005.xml", 5, "2026-09-02", "200.00", "5102", "190.00"),
        ("nfe-venda-001-copia.xml", 1, "2026-08-05", "1250.00", "5102", None),
    ]:
        write_xml(notes / filename, invoice(number, date, amount, cfop, item_amount=item_amount))
    write_xml(notes / "evento-cancelamento-003.xml", cancellation(access_key(3)))

    row = lambda number, **values: {"access_key": access_key(number), **values}
    write_csv("raw/escrituracao/lancamentos.csv", [
        "access_key", "source_record", "document_total", "pis_base", "pis_value",
        "cofins_base", "cofins_value", "included_in_revenue", "return_deducted",
    ], [
        row(1, source_record="C100-001", document_total="1200.00", pis_base="1200.00", pis_value="12.00", cofins_base="1200.00", cofins_value="24.00", included_in_revenue="true", return_deducted="false"),
        row(3, source_record="C100-003", document_total="400.00", pis_base="400.00", pis_value="4.00", cofins_base="400.00", cofins_value="8.00", included_in_revenue="true", return_deducted="false"),
        row(4, source_record="C100-004", document_total="150.00", pis_base="0.00", pis_value="0.00", cofins_base="0.00", cofins_value="0.00", included_in_revenue="false", return_deducted="false"),
        row(99, source_record="C100-099", document_total="600.00", pis_base="600.00", pis_value="6.00", cofins_base="600.00", cofins_value="12.00", included_in_revenue="true", return_deducted="false"),
    ])
    write_csv("raw/cadastros/produtos.csv", ["product_code", "description", "ncm", "unit"], [
        {"product_code": "PROD-001", "description": "Produto sintetico A", "ncm": "00000000", "unit": "UN"}
    ])
    write_csv("raw/cadastros/participantes.csv", ["tax_id", "name", "role"], [
        {"tax_id": COMPANY, "name": "Comercial Modelo Bahia Ltda.", "role": "company"},
        {"tax_id": CUSTOMER, "name": "Cliente Ficticio Ltda.", "role": "customer"},
    ])
    write_json("raw/declaracoes/valor_informado.json", {
        "competencia": "2026-08", "pis_pasep": "18.00", "cofins": "35.00",
        "source": "synthetic_case_input",
    })
    write_json("metadata.json", {
        "case_id": CASE.name, "company_id": "empresa-ficticia-001", "company_name": "Comercial Modelo Bahia Ltda.",
        "company_tax_id": COMPANY, "competencia": "2026-08", "reference_date": "2026-09-25",
        "source": "synthetic", "expected_sources": ["nfe_xml", "nfe_event_xml", "escrituracao_reduzida_csv", "produtos_csv", "participantes_csv", "valor_informado_json"],
    })
    write_json("config/company_profile.json", {"company_id": "empresa-ficticia-001", "tax_id": COMPANY, "regime_label": "Lucro Presumido (simulacao)"})
    write_json("config/tax_profile.json", {
        "profile_id": "synthetic-2026-08-v1", "fictional_parameters": True,
        "pis_rate": "0.01", "cofins_rate": "0.02", "sale_cfops": ["5102"], "return_cfops": ["1202"],
        "sale_base_policy": "document_total", "returns_policy": "deduct_document_total",
        "rounding": "ROUND_HALF_UP", "currency_scale": "0.01",
        "note": "Taxas escolhidas apenas para testar o software; não representam orientação tributária.",
    })
    kinds = {
        ".xml": "nfe_xml", ".csv": None, ".json": "valor_informado_json",
    }
    type_by_folder = {
        "raw/escrituracao/lancamentos.csv": "escrituracao_reduzida_csv",
        "raw/cadastros/produtos.csv": "produtos_csv",
        "raw/cadastros/participantes.csv": "participantes_csv",
    }
    files = []
    for path in sorted((CASE / "raw").rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(CASE).as_posix()
        content = path.read_bytes()
        files.append({
            "path": relative,
            "type": "nfe_event_xml" if path.name.startswith("evento-") else type_by_folder.get(relative) or kinds[path.suffix],
            "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content),
        })
    write_json("manifest.json", {
        "case_id": CASE.name, "company_id": "empresa-ficticia-001", "competencia": "2026-08",
        "collected_at": "2026-09-25T12:00:00Z", "source": "synthetic", "files": files,
    })
    write_json("expected_occurrences.json", [
        {"rule_id": "VALUE_MISMATCH", "access_key": access_key(1)},
        {"rule_id": "TAX_BASE_MISMATCH", "access_key": access_key(1)},
        {"rule_id": "TAX_VALUE_MISMATCH", "access_key": access_key(1)},
        {"rule_id": "DOC_MISSING_IN_SPED", "access_key": access_key(2)},
        {"rule_id": "CANCELLED_INCLUDED", "access_key": access_key(3)},
        {"rule_id": "RETURN_NOT_DEDUCTED", "access_key": access_key(4)},
        {"rule_id": "DOC_WITHOUT_XML", "access_key": access_key(99)},
        {"rule_id": "DUPLICATE_DOCUMENT", "access_key": access_key(1)},
        {"rule_id": "INVALID_PERIOD", "access_key": access_key(5, "09")},
        {"rule_id": "ITEM_TOTAL_MISMATCH", "access_key": access_key(5, "09")},
    ])
    print(f"Fixture gerada: {CASE} ({len(files)} arquivos brutos)")


if __name__ == "__main__":
    main()
