"""Leitores de XML e fontes auxiliares sintéticas."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO
from xml.etree import ElementTree as ET

NFE_NS = "http://www.portalfiscal.inf.br/nfe"
N = {"n": NFE_NS}


def money(value: str | None, field: str) -> str:
    if value is None or value == "":
        raise ValueError(f"Campo monetário ausente: {field}")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Valor monetário inválido: {field}") from exc
    if not parsed.is_finite():
        raise ValueError(f"Valor monetário não finito: {field}")
    return str(parsed)


def safe_xml(data: bytes) -> ET.Element:
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("XML maior que 10 MiB")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("DTD e entidades não são permitidos")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        line, column = exc.position
        raise ValueError(f"XML malformado (linha {line}, coluna {column})") from exc


def required(element: ET.Element, query: str, field: str) -> str:
    value = element.findtext(query, namespaces=N)
    if not value:
        raise ValueError(f"Campo obrigatório ausente: {field}")
    return value.strip()


def parse_nfe(data: bytes, source_path: str) -> dict:
    root = safe_xml(data)
    if root.tag != f"{{{NFE_NS}}}nfeProc":
        raise ValueError("Raiz não é nfeProc")
    info = root.find("n:NFe/n:infNFe", N)
    if info is None:
        raise ValueError("infNFe ausente")
    key = required(root, "n:protNFe/n:infProt/n:chNFe", "chNFe")
    if len(key) != 44 or not key.isdigit() or info.get("Id") != f"NFe{key}":
        raise ValueError("Chave de acesso estruturalmente inválida")
    issue_date = required(info, "n:ide/n:dhEmi", "dhEmi")[:10]
    try:
        date.fromisoformat(issue_date)
    except ValueError as exc:
        raise ValueError("Data de emissão inválida") from exc
    if required(root, "n:protNFe/n:infProt/n:cStat", "cStat") != "100":
        raise ValueError("NF-e sem protocolo de autorização no caso sintético")
    items = []
    for item in info.findall("n:det", N):
        product = item.find("n:prod", N)
        if product is None:
            raise ValueError("Item sem produto")
        number = item.get("nItem")
        if not number or not number.isdigit():
            raise ValueError("Item sem número")
        items.append({
            "line_number": int(number),
            "product_code": required(product, "n:cProd", "cProd"),
            "description": required(product, "n:xProd", "xProd"),
            "ncm": required(product, "n:NCM", "NCM"),
            "cfop": required(product, "n:CFOP", "CFOP"),
            "quantity": money(required(product, "n:qCom", "qCom"), "qCom"),
            "unit_value": money(required(product, "n:vUnCom", "vUnCom"), "vUnCom"),
            "total_value": money(required(product, "n:vProd", "vProd"), "vProd"),
        })
    if not items:
        raise ValueError("NF-e sem itens")
    return {
        "document_id": f"nfe-{key}", "access_key": key, "document_type": "NFE",
        "issue_date": issue_date, "status": "authorized",
        "issuer_tax_id": required(info, "n:emit/n:CNPJ", "emit/CNPJ"),
        "recipient_tax_id": required(info, "n:dest/n:CNPJ", "dest/CNPJ"),
        "total_value": money(required(info, "n:total/n:ICMSTot/n:vNF", "vNF"), "vNF"),
        "items": items, "source_path": source_path,
    }


def parse_event(data: bytes, source_path: str) -> dict:
    root = safe_xml(data)
    if root.tag != f"{{{NFE_NS}}}procEventoNFe":
        raise ValueError("Raiz não é procEventoNFe")
    key = required(root, "n:evento/n:infEvento/n:chNFe", "chNFe")
    event_type = required(root, "n:evento/n:infEvento/n:tpEvento", "tpEvento")
    status = required(root, "n:retEvento/n:infEvento/n:cStat", "cStat")
    return {"access_key": key, "event_type": event_type, "event_status": status, "source_path": source_path}


def parse_csv(data: bytes, required_fields: set[str], source_path: str) -> list[dict]:
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV não está em UTF-8") from exc
    reader = csv.DictReader(StringIO(content))
    if not required_fields.issubset(set(reader.fieldnames or [])):
        raise ValueError(f"Colunas obrigatórias ausentes em {source_path}")
    rows = []
    for line, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(f"CSV com colunas excedentes na linha {line}")
        if any(value is None for value in row.values()):
            raise ValueError(f"CSV com campos ausentes na linha {line}")
        rows.append({**row, "source_path": source_path, "source_line": line})
    return rows


def normalize_bookkeeping(rows: list[dict]) -> list[dict]:
    result = []
    for row in rows:
        key = row.get("access_key", "")
        if len(key) != 44 or not key.isdigit():
            raise ValueError(f"Chave inválida na linha {row['source_line']}")
        normalized = {**row}
        for field in ("document_total", "pis_base", "pis_value", "cofins_base", "cofins_value"):
            normalized[field] = money(row.get(field), f"{field} na linha {row['source_line']}")
        for field in ("included_in_revenue", "return_deducted"):
            if row.get(field) not in {"true", "false"}:
                raise ValueError(f"Booleano inválido: {field} na linha {row['source_line']}")
            normalized[field] = row[field] == "true"
        result.append(normalized)
    return result


def parse_nfe_csv(data: bytes, source_path: str) -> list[dict]:
    fields = {
        "document_ref", "access_key", "issue_date", "status", "issuer_tax_id",
        "recipient_tax_id", "total_value", "line_number", "product_code",
        "description", "ncm", "cfop", "quantity", "unit_value", "item_total",
    }
    rows = parse_csv(data, fields, source_path)
    grouped: dict[str, dict] = {}
    for row in rows:
        reference = row["document_ref"]
        key = row["access_key"]
        if not reference or len(key) != 44 or not key.isdigit():
            raise ValueError(f"Referência ou chave inválida na linha {row['source_line']}")
        try:
            date.fromisoformat(row["issue_date"])
        except ValueError as exc:
            raise ValueError(f"Data inválida na linha {row['source_line']}") from exc
        if row["status"] not in {"authorized", "cancelled"}:
            raise ValueError(f"Situação inválida na linha {row['source_line']}")
        if not row["line_number"].isdigit() or not row["product_code"] or not row["cfop"]:
            raise ValueError(f"Item inválido na linha {row['source_line']}")
        header = {
            "document_id": f"nfe-{key}", "access_key": key, "document_type": "NFE",
            "issue_date": row["issue_date"], "status": row["status"],
            "issuer_tax_id": row["issuer_tax_id"], "recipient_tax_id": row["recipient_tax_id"],
            "total_value": money(row["total_value"], "total_value"),
            "source_path": source_path, "source_line": row["source_line"],
            "document_ref": reference,
        }
        if reference not in grouped:
            grouped[reference] = {**header, "items": []}
        else:
            existing = grouped[reference]
            for field in ("access_key", "issue_date", "status", "issuer_tax_id", "recipient_tax_id", "total_value"):
                if existing[field] != header[field]:
                    raise ValueError(f"Cabeçalho inconsistente em {reference}, linha {row['source_line']}")
        item = {
            "line_number": int(row["line_number"]), "product_code": row["product_code"],
            "description": row["description"], "ncm": row["ncm"], "cfop": row["cfop"],
            "quantity": money(row["quantity"], "quantity"),
            "unit_value": money(row["unit_value"], "unit_value"),
            "total_value": money(row["item_total"], "item_total"),
            "source_line": row["source_line"],
        }
        if any(existing["line_number"] == item["line_number"] for existing in grouped[reference]["items"]):
            raise ValueError(f"Item duplicado em {reference}, linha {row['source_line']}")
        grouped[reference]["items"].append(item)
    return list(grouped.values())


def parse_events_csv(data: bytes, source_path: str) -> list[dict]:
    rows = parse_csv(data, {"access_key", "event_type", "event_status", "occurred_at"}, source_path)
    result = []
    for row in rows:
        if len(row["access_key"]) != 44 or not row["access_key"].isdigit():
            raise ValueError(f"Chave de evento inválida na linha {row['source_line']}")
        result.append({
            "access_key": row["access_key"], "event_type": row["event_type"],
            "event_status": row["event_status"], "occurred_at": row["occurred_at"],
            "source_path": source_path, "source_line": row["source_line"],
        })
    return result
