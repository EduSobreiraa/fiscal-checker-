"""Saídas determinísticas para integração e revisão humana."""

from __future__ import annotations

import csv
import json
from collections import Counter
from html import escape
from pathlib import Path

from .presentation import RULE_LABELS, SEVERITY_LABELS, STATUS_LABELS, TREATMENT_LABELS
from .triage import client_request_text


CSV_FIELDS = [
    "occurrence_id", "rule_id", "severity", "status", "document_id", "access_key",
    "message", "expected_value", "declared_value", "source_path",
    "regra", "gravidade", "situacao",
]


def as_text(value: object) -> str:
    return "" if value is None else str(value)


def html_text(value: object) -> str:
    return escape(as_text(value), quote=True)


def csv_cell(value: object) -> str:
    text = as_text(value)
    # Protege a planilha de interpretar um dado de origem como fórmula.
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def build_result(normalized: dict, calculation: dict, occurrences: list[dict], metadata: dict, manifest: dict) -> dict:
    severity_counts = Counter(item["severity"] for item in occurrences)
    return {
        "case_id": normalized["case_id"], "company_id": normalized["company_id"],
        "company_name": metadata["company_name"], "competencia": normalized["competencia"],
        "reference_date": metadata["reference_date"],
        "status": "complete" if calculation["status"] == "complete" and not normalized["errors"] else "incomplete",
        "sources": [{"path": entry["path"], "type": entry["type"], "sha256": entry["sha256"]} for entry in manifest["files"]],
        "summary": {
            "documents": len(normalized["documents"]), "events": len(normalized["events"]),
            "bookkeeping_rows": len(normalized["bookkeeping"]), "input_errors": len(normalized["errors"]),
            "occurrences": len(occurrences), "by_severity": dict(sorted(severity_counts.items())),
        },
        "calculation": calculation, "occurrences": occurrences,
        "input_errors": normalized["errors"], "normalized": normalized,
    }


def render_html(result: dict) -> str:
    calc = result["calculation"]
    summary = result["summary"]
    source_rows = "".join(
        f"<tr><td>{html_text(item['path'])}</td><td>{html_text(item['type'])}</td><td><code>{html_text(item['sha256'])}</code></td></tr>"
        for item in result["sources"]
    )
    occurrence_rows = "".join(
        "<tr>" + "".join(f"<td>{html_text(value)}</td>" for value in (
            item["occurrence_id"], SEVERITY_LABELS.get(item["severity"], item["severity"]),
            RULE_LABELS.get(item["rule_id"], item["rule_id"]), item["message"],
            item["access_key"], item["expected_value"], item["declared_value"],
            item["evidence"].get("xml_path"), item["evidence"].get("source_path"),
            item["evidence"].get("source_record"),
            json.dumps(item["evidence"], ensure_ascii=False, sort_keys=True),
        )) + "</tr>"
        for item in result["occurrences"]
    )
    triage_rows = "".join(
        "<tr>" + "".join(f"<td>{html_text(value)}</td>" for value in (
            item["access_key"], SEVERITY_LABELS.get(item["priority"], item["priority"]),
            item["occurrence_count"], "; ".join(item["reasons"]),
            "Solicitar documento" if item["action"] == "solicitar_documento" else "Revisar internamente",
        )) + "</tr>"
        for item in result.get("review_queue", [])
    )
    contribution_rows = "".join(
        "<tr>" + "".join(f"<td>{html_text(value)}</td>" for value in (
            item["access_key"], TREATMENT_LABELS.get(item["treatment"], item["treatment"]),
            item["amount"], item["source_path"],
        )) + "</tr>"
        for item in calc["contributions"]
    )
    limitations = "".join(f"<li>{html_text(item)}</li>" for item in calc["limitations"])
    errors = "".join(f"<li>{html_text(item['source_path'])}: {html_text(item['message'])}</li>" for item in result["input_errors"])
    computed = calc["computed"] or {}
    declared = calc["declared"] or {}
    difference = calc["difference"] or {}
    severity = ", ".join(f"{html_text(SEVERITY_LABELS.get(name, name))}: {count}" for name, count in summary["by_severity"].items()) or "nenhuma"
    evaluation = result.get("evaluation")
    evaluation_section = (
        f"<h2>7. Avaliação do caso de teste</h2><p>Ocorrências esperadas: {evaluation['expected']}; detectadas: {evaluation['detected']}; correspondentes: {evaluation['matched']}; com fonte de evidência: {evaluation['with_source_evidence']}. Resultado: <strong>{'aprovado' if evaluation['passed'] else 'revisar'}</strong>.</p>"
        f"<p>Ausentes: {html_text(json.dumps(evaluation['missing'], ensure_ascii=False))}. Não previstas: {html_text(json.dumps(evaluation['unexpected'], ensure_ascii=False))}.</p>"
        if evaluation else ""
    )
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fiscal Checker — {html_text(result['case_id'])}</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#20242a}}h1,h2{{line-height:1.2}}table{{border-collapse:collapse;width:100%;margin:1rem 0}}th,td{{border:1px solid #c9ced4;padding:.5rem;text-align:left;vertical-align:top;overflow-wrap:anywhere}}th{{background:#eef2f5}}code{{font-size:.85em}}.notice{{padding:1rem;background:#fff4dc;border-left:4px solid #ad6a00}}.scroll{{overflow-x:auto}}small{{color:#555}}</style>
</head><body>
<h1>Fiscal Checker — fechamento mensal simulado</h1>
<p class="notice"><strong>Pendente de revisão humana.</strong> Este resultado usa documentos e parâmetros sintéticos; não constitui apuração fiscal real.</p>
<h2>1. Identificação</h2><p>Empresa: <strong>{html_text(result['company_name'])}</strong> ({html_text(result['company_id'])})<br>Competência: {html_text(result['competencia'])}<br>Data de referência: {html_text(result['reference_date'])}<br>Caso: {html_text(result['case_id'])}<br>Estado do processamento: {html_text(STATUS_LABELS.get(result['status'], result['status']))}</p>
<h2>2. Fontes analisadas</h2><div class="scroll"><table><thead><tr><th>Caminho</th><th>Tipo</th><th>SHA-256</th></tr></thead><tbody>{source_rows}</tbody></table></div>
<h2>3. Volume e ocorrências</h2><p>{summary['documents']} NF-e, {summary['events']} eventos e {summary['bookkeeping_rows']} lançamentos. {summary['occurrences']} ocorrências; {summary['input_errors']} erros de entrada. Severidade: {severity}.</p>
<h2>4. Apuração simulada</h2><p>Vendas brutas elegíveis: {html_text(calc['gross_sales'])}<br>Devoluções: {html_text(calc['returns'])}<br>Base resultante: <strong>{html_text(calc['eligible_revenue'])}</strong><br>Perfil: {html_text(calc['profile_id'])} ({html_text(calc['config_source'])})<br>Taxas fictícias: PIS/Pasep {html_text((calc['rates'] or {}).get('pis_pasep'))}; Cofins {html_text((calc['rates'] or {}).get('cofins'))}</p>
<div class="scroll"><table><thead><tr><th>Tributo</th><th>Calculado</th><th>Informado</th><th>Diferença (calculado − informado)</th></tr></thead><tbody><tr><td>PIS/Pasep</td><td>{html_text(computed.get('pis_pasep'))}</td><td>{html_text(declared.get('pis_pasep'))}</td><td>{html_text(difference.get('pis_pasep'))}</td></tr><tr><td>Cofins</td><td>{html_text(computed.get('cofins'))}</td><td>{html_text(declared.get('cofins'))}</td><td>{html_text(difference.get('cofins'))}</td></tr></tbody></table></div>
<h2>5. Memória de cálculo</h2><p>Tratamento por documento, após deduplicação e aplicação do perfil sintético:</p><div class="scroll"><table><thead><tr><th>Chave</th><th>Tratamento</th><th>Valor considerado</th><th>Arquivo de origem</th></tr></thead><tbody>{contribution_rows}</tbody></table></div>
<h2>6. Divergências e evidências</h2><div class="scroll"><table><thead><tr><th>ID</th><th>Severidade</th><th>Regra</th><th>Descrição</th><th>Chave</th><th>Esperado</th><th>Encontrado</th><th>XML</th><th>Fonte</th><th>Registro</th><th>Evidência completa</th></tr></thead><tbody>{occurrence_rows}</tbody></table></div>
<h2>6.1. Triagem por documento</h2><p>As ações abaixo são sugestões para revisão do analista antes de qualquer contato com o cliente.</p><div class="scroll"><table><thead><tr><th>Chave</th><th>Prioridade</th><th>Ocorrências</th><th>Motivos</th><th>Ação sugerida</th></tr></thead><tbody>{triage_rows}</tbody></table></div>
{evaluation_section}
<h2>8. Erros e limitações</h2><ul>{errors or '<li>Nenhum erro de entrada.</li>'}</ul><ul>{limitations}</ul>
<h2>9. Conclusão</h2><p>Resultado auxiliar para investigação. Todas as ocorrências permanecem pendentes de revisão por um analista contábil.</p>
<small>Os caminhos e hashes permitem reproduzir a análise a partir dos arquivos originais do caso.</small>
</body></html>"""


def write_outputs(output: Path, normalized: dict, result: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for filename, value in (
        ("normalized.json", normalized), ("calculation.json", result["calculation"]), ("result.json", result),
    ):
        (output / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "occurrences.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in result["occurrences"]:
            row = {
                field: item["evidence"].get("source_path") if field == "source_path" else item.get(field)
                for field in CSV_FIELDS
            }
            row.update({
                "regra": RULE_LABELS.get(item["rule_id"], item["rule_id"]),
                "gravidade": SEVERITY_LABELS.get(item["severity"], item["severity"]),
                "situacao": STATUS_LABELS.get(item["status"], item["status"]),
            })
            writer.writerow({field: csv_cell(value) for field, value in row.items()})
    (output / "report.html").write_text(render_html(result), encoding="utf-8")
    queue = result.get("review_queue", [])
    with (output / "triagem.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = ["chave", "prioridade", "ocorrencias", "motivos", "acao_sugerida", "fontes"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in queue:
            writer.writerow({field: csv_cell(value) for field, value in {
                "chave": item["access_key"],
                "prioridade": SEVERITY_LABELS.get(item["priority"], item["priority"]),
                "ocorrencias": item["occurrence_count"],
                "motivos": "; ".join(item["reasons"]),
                "acao_sugerida": "Solicitar documento" if item["action"] == "solicitar_documento" else "Revisar internamente",
                "fontes": "; ".join(item["source_paths"]),
            }.items()})
    (output / "previa-cliente.txt").write_text(
        client_request_text(result["company_name"], result["competencia"], queue), encoding="utf-8"
    )
