"""Apuração determinística do cenário configurado, sem regras fiscais embutidas."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def amount(value: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("Valor deve ser uma string decimal")
    number = Decimal(value)
    if not number.is_finite():
        raise ValueError("Valor não finito")
    return number


def rates(profile: dict) -> tuple[Decimal, Decimal] | None:
    try:
        if (profile.get("fictional_parameters") is not True
                or profile.get("sale_base_policy") != "document_total"
                or profile.get("returns_policy") != "deduct_document_total"):
            return None
        pis = amount(profile["pis_rate"])
        cofins = amount(profile["cofins_rate"])
        if pis < 0 or cofins < 0:
            return None
        return pis, cofins
    except (KeyError, TypeError, InvalidOperation, ValueError):
        return None


def calculate(normalized: dict, profile: dict, company: dict, config_source: str = "config/tax_profile.json") -> dict:
    currency_scale = Decimal(profile.get("currency_scale", "0.01"))
    if currency_scale <= 0 or profile.get("rounding") != "ROUND_HALF_UP":
        raise ValueError("Escala monetária ou arredondamento não suportado")
    sale_cfops = set(profile.get("sale_cfops", []))
    return_cfops = set(profile.get("return_cfops", []))
    company_id = company["tax_id"]
    seen: set[str] = set()
    contributions: list[dict] = []
    gross = Decimal("0")
    returns = Decimal("0")
    for doc in sorted(normalized["documents"], key=lambda item: (item["access_key"], item["source_path"])):
        key = doc["access_key"]
        if key in seen:
            contributions.append({"access_key": key, "source_path": doc["source_path"], "treatment": "duplicate", "amount": "0.00"})
            continue
        seen.add(key)
        if doc["issue_date"][:7] != normalized["competencia"]:
            treatment = "outside_period"
        elif doc["status"] == "cancelled":
            treatment = "cancelled"
        elif doc["issuer_tax_id"] != company_id:
            treatment = "other_issuer"
        else:
            cfops = {item["cfop"] for item in doc["items"]}
            if cfops <= sale_cfops:
                treatment = "sale"
                gross += amount(doc["total_value"])
            elif cfops <= return_cfops:
                treatment = "return"
                returns += amount(doc["total_value"])
            else:
                treatment = "unclassified"
        contributions.append({
            "access_key": key, "source_path": doc["source_path"],
            "treatment": treatment,
            "amount": doc["total_value"] if treatment in {"sale", "return"} else "0.00",
        })
    base = gross - returns
    if base < 0:
        raise ValueError("Devoluções excedem as vendas no cenário")
    configured_rates = rates(profile)
    declared = normalized["declared"]
    computed = None
    difference = None
    if configured_rates and declared is not None and not normalized["errors"]:
        pis_rate, cofins_rate = configured_rates
        computed = {
            "pis_pasep": str((base * pis_rate).quantize(currency_scale, rounding=ROUND_HALF_UP)),
            "cofins": str((base * cofins_rate).quantize(currency_scale, rounding=ROUND_HALF_UP)),
        }
        difference = {
            name: str((amount(computed[name]) - amount(declared[name])).quantize(currency_scale, rounding=ROUND_HALF_UP))
            for name in computed
        }
    return {
        "status": "complete" if computed else "incomplete",
        "profile_id": profile.get("profile_id"),
        "fictional_parameters": profile.get("fictional_parameters") is True,
        "config_source": config_source,
        "gross_sales": str(gross.quantize(currency_scale, rounding=ROUND_HALF_UP)),
        "returns": str(returns.quantize(currency_scale, rounding=ROUND_HALF_UP)),
        "eligible_revenue": str(base.quantize(currency_scale, rounding=ROUND_HALF_UP)),
        "rates": {"pis_pasep": str(configured_rates[0]), "cofins": str(configured_rates[1])} if configured_rates else None,
        "computed": computed,
        "declared": {name: declared[name] for name in ("pis_pasep", "cofins")} if declared else None,
        "difference": difference,
        "contributions": contributions,
        "limitations": [
            "Parâmetros e documentos são sintéticos; resultado não representa apuração fiscal real.",
            *(["Há erros de ingestão ou parsing; o cálculo ficou incompleto."] if normalized["errors"] else []),
            *(["Parâmetros de apuração ausentes, inválidos ou não suportados."] if not configured_rates else []),
            *(["Valor informado ausente."] if declared is None else []),
        ],
    }
