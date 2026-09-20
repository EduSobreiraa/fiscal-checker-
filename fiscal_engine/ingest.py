"""Leitura do contrato de entrada e verificação de integridade."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def load_case(case_dir: Path, competencia: str) -> tuple[dict, dict, list[tuple[dict, bytes]], list[dict]]:
    root = case_dir.resolve()
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for field in ("case_id", "company_id", "competencia", "source"):
        if not metadata.get(field) or metadata[field] != manifest.get(field):
            raise ValueError(f"Metadados e manifesto divergem em {field}")
    if metadata["competencia"] != competencia:
        raise ValueError("Competência solicitada diverge do caso")
    if not isinstance(manifest.get("files"), list):
        raise ValueError("Manifesto sem lista de arquivos")

    verified: list[tuple[dict, bytes]] = []
    errors: list[dict] = []
    seen: set[str] = set()
    for entry in manifest["files"]:
        relative = entry.get("path", "")
        try:
            if not isinstance(relative, str) or not relative.startswith("raw/") or ".." in Path(relative).parts:
                raise ValueError("Caminho fora de raw/")
            if relative in seen:
                raise ValueError("Arquivo duplicado no manifesto")
            seen.add(relative)
            file = (root / relative).resolve()
            if not file.is_relative_to(root / "raw") or not file.is_file():
                raise ValueError("Arquivo ausente ou fora do caso")
            data = file.read_bytes()
            if len(data) != entry.get("size_bytes") or hashlib.sha256(data).hexdigest() != entry.get("sha256"):
                raise ValueError("Tamanho ou SHA-256 divergente")
            verified.append((entry, data))
        except (OSError, ValueError, TypeError) as exc:
            errors.append({"stage": "ingestion", "source_path": relative, "message": str(exc)})
    return metadata, manifest, verified, errors
