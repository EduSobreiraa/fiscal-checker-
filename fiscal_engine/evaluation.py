"""Compara as ocorrências encontradas com o gabarito de um caso sintético."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def evaluate(case_dir: Path, occurrences: list[dict]) -> dict | None:
    target = case_dir / "expected_occurrences.json"
    if not target.exists():
        return None
    expected = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(expected, list):
        raise ValueError("Gabarito de ocorrências inválido")
    expected_pairs = Counter((item["rule_id"], item.get("access_key")) for item in expected)
    actual_pairs = Counter((item["rule_id"], item.get("access_key")) for item in occurrences)
    missing = expected_pairs - actual_pairs
    unexpected = actual_pairs - expected_pairs
    matched = sum((expected_pairs & actual_pairs).values())
    evidence_count = sum(bool(item.get("evidence", {}).get("source_path")) for item in occurrences)
    return {
        "expected": sum(expected_pairs.values()), "detected": sum(actual_pairs.values()),
        "matched": matched, "missing": [
            {"rule_id": rule, "access_key": key, "count": count}
            for (rule, key), count in sorted(missing.items())
        ],
        "unexpected": [
            {"rule_id": rule, "access_key": key, "count": count}
            for (rule, key), count in sorted(unexpected.items())
        ],
        "with_source_evidence": evidence_count,
        "passed": not missing and not unexpected and evidence_count == len(occurrences),
    }
