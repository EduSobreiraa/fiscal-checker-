"""Executa o fluxo completo para CLI e interface local."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .calculations import calculate
from .evaluation import evaluate
from .pipeline import normalize_case
from .reconciliation import reconcile
from .reports import build_result, write_outputs
from .triage import build_review_queue


def analyze_case(input_dir: Path, competencia: str, config_dir: Path | None = None) -> dict:
    """Analisa em memória; a interface decide quais resultados precisa persistir."""
    normalized = normalize_case(input_dir, competencia)
    config = config_dir or input_dir / "config"
    company_file = config / "company_profile.json"
    tax_file = config / "tax_profile.json"
    company = json.loads(company_file.read_text(encoding="utf-8"))
    profile = json.loads(tax_file.read_text(encoding="utf-8")) if tax_file.exists() else {}
    metadata = json.loads((input_dir / "metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    profile_source = str(tax_file)
    calculation = calculate(normalized, profile, company, profile_source)
    occurrences = reconcile(normalized, profile, company, profile_source)
    result = build_result(normalized, calculation, occurrences, metadata, manifest)
    result["review_queue"] = build_review_queue(occurrences)
    result["config_hashes"] = {
        str(company_file): hashlib.sha256(company_file.read_bytes()).hexdigest(),
        profile_source: hashlib.sha256(tax_file.read_bytes()).hexdigest() if tax_file.exists() else None,
    }
    result["evaluation"] = evaluate(input_dir, occurrences)
    return result


def run_case(input_dir: Path, output_dir: Path, competencia: str, config_dir: Path | None = None) -> dict:
    result = analyze_case(input_dir, competencia, config_dir)
    write_outputs(output_dir, result["normalized"], result)
    return result
