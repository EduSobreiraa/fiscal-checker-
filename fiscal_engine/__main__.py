"""CLI do caso fiscal sintético."""

from __future__ import annotations

import argparse
from pathlib import Path

from .service import run_case


def main() -> None:
    parser = argparse.ArgumentParser(description="Processa um fechamento fiscal sintético")
    parser.add_argument("--input", type=Path, default=Path("data/synthetic/case-2026-08-comercial-modelo-csv"))
    parser.add_argument("--config", type=Path, help="Pasta de perfis; padrão: <input>/config")
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--competencia", required=True)
    args = parser.parse_args()
    result = run_case(args.input, args.output, args.competencia, args.config)
    summary = result["summary"]
    print(f"{summary['documents']} NF-e, {summary['occurrences']} ocorrências, {summary['input_errors']} erros de entrada. Relatório: {args.output / 'report.html'}")


if __name__ == "__main__":
    main()
