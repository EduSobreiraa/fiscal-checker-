"""CLI de conferência em lote das apurações do Simples."""

from __future__ import annotations

import argparse
from pathlib import Path

from .service import assess_batch, write_result


def money(value: object) -> str:
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> None:
    parser = argparse.ArgumentParser(description="Confere em lote relatórios de apuração do Simples Nacional")
    parser.add_argument("--input", type=Path, required=True, help="Pasta da competência, com uma subpasta por empresa")
    parser.add_argument("--period", help="Competência AAAA-MM; padrão: nome da pasta de entrada")
    parser.add_argument("--output", type=Path, help="Arquivo JSON estruturado")
    args = parser.parse_args()
    result = assess_batch(args.input, args.period)
    if args.output:
        write_result(result, args.output)
    summary = result["summary"]
    print(f"Competência: {result['period']}")
    print(f"Empresas processadas: {summary['total']}")
    print(f"Sem exceções: {summary['withoutExceptions']}")
    print(f"Revisar: {summary['review']}")
    print(f"Erro: {summary['errors']}")
    for title, status in (("Fila de revisão", "REVISAR"), ("Erros", "ERRO")):
        selected = [item for item in result["companies"] if item["status"] == status]
        if not selected:
            continue
        print(f"\n{title}:")
        for item in selected:
            print(f"\n{item['company']['name']}")
            for finding in item["findings"]:
                print(f"- {finding['code']}: {finding['message']}")
                if finding["code"] == "REVENUE_MISMATCH":
                    print(f"  Apuração: {money(finding['expected'])}; demonstrativo: {money(finding['actual'])}; diferença: {money(abs(finding['actual'] - finding['expected']))}")
    if args.output:
        print(f"\nJSON: {args.output}")


if __name__ == "__main__":
    main()
