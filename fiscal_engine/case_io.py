"""Monta pacotes de entrada CSV sem depender do terminal."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path


UPLOAD_TYPES = {
    "nfe_csv": "raw/notas/nfe.csv",
    "nfe_event_csv": "raw/notas/eventos.csv",
    "escrituracao_reduzida_csv": "raw/escrituracao/lancamentos.csv",
    "produtos_csv": "raw/cadastros/produtos.csv",
    "participantes_csv": "raw/cadastros/participantes.csv",
    "valor_informado_csv": "raw/declaracoes/valor_informado.csv",
}
REQUIRED_TYPES = {"nfe_csv", "escrituracao_reduzida_csv", "valor_informado_csv"}
MAX_FILE_BYTES = 10 * 1024 * 1024


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def create_uploaded_case(
    base_dir: Path, *, case_id: str, company_id: str, company_name: str,
    company_tax_id: str, competencia: str, reference_date: date,
    uploads: dict[str, bytes], synthetic_profile: Path,
) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,63}", case_id):
        raise ValueError("Identificador do caso: use 3 a 64 letras minúsculas, números, _ ou -")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competencia):
        raise ValueError("Competência inválida; use AAAA-MM")
    if not company_id.strip() or not company_name.strip() or not re.fullmatch(r"\d{11}|\d{14}", company_tax_id):
        raise ValueError("Preencha empresa, identificador e CPF/CNPJ com 11 ou 14 dígitos")
    if not REQUIRED_TYPES.issubset(uploads) or set(uploads) - set(UPLOAD_TYPES):
        raise ValueError("Envie NF-e, escrituração e valor informado em CSV")
    for kind, content in uploads.items():
        if not isinstance(content, bytes) or not content or len(content) > MAX_FILE_BYTES:
            raise ValueError(f"Arquivo vazio, inválido ou maior que 10 MiB: {UPLOAD_TYPES[kind]}")
    profile = json.loads(synthetic_profile.read_text(encoding="utf-8"))
    if profile.get("fictional_parameters") is not True:
        raise ValueError("Esta interface aceita somente perfil tributário sintético")

    base = base_dir.resolve()
    base.mkdir(parents=True, exist_ok=True)
    destination = base / case_id
    if destination.exists():
        raise FileExistsError(f"O caso já existe: {destination}")
    staging = Path(tempfile.mkdtemp(prefix=".incoming-", dir=base))
    try:
        files = []
        for kind in sorted(uploads):
            relative = UPLOAD_TYPES[kind]
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(uploads[kind])
            files.append({
                "path": relative, "type": kind,
                "sha256": hashlib.sha256(uploads[kind]).hexdigest(),
                "size_bytes": len(uploads[kind]),
            })
        (staging / "config").mkdir()
        (staging / "config/tax_profile.json").write_bytes(synthetic_profile.read_bytes())
        (staging / "config/company_profile.json").write_bytes(json_bytes({
            "company_id": company_id, "tax_id": company_tax_id,
            "regime_label": "Simulação com parâmetros fictícios",
        }))
        metadata = {
            "case_id": case_id, "company_id": company_id, "company_name": company_name,
            "company_tax_id": company_tax_id, "competencia": competencia,
            "reference_date": reference_date.isoformat(), "source": "local_import",
            "expected_sources": sorted(uploads),
        }
        (staging / "metadata.json").write_bytes(json_bytes(metadata))
        (staging / "manifest.json").write_bytes(json_bytes({
            "case_id": case_id, "company_id": company_id, "competencia": competencia,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "source": "local_import", "files": files,
        }))
        if destination.exists():
            raise FileExistsError(f"O caso já existe: {destination}")
        os.rename(staging, destination)
        return destination
    finally:
        if staging.exists():
            shutil.rmtree(staging)
