"""Catálogo local: referências de documentos, execuções e decisões do analista.

O Domínio continua sendo uma referência externa. Este módulo não afirma consultar
seus portais e não duplica documentos normalizados a cada execução.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
from uuid import uuid4

from .case_io import MAX_FILE_BYTES, UPLOAD_TYPES, json_bytes
from .pipeline import normalize_case
from .presentation import user_error
from .reports import csv_cell
from .service import analyze_case

PORTALS = ["Domínio", "SEFAZ", "Portal Nacional", "Prefeitura"]
REVIEW_STATUSES = ["Pendente", "Em revisão", "Aguardando cliente", "Resolvido"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_period(period: str) -> None:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        raise ValueError("Competência inválida; use AAAA-MM")


def csv_download(rows: list[dict], fields: list[str]) -> bytes:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: csv_cell(row.get(key)) for key in fields})
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


class Workspace:
    def __init__(self, root: Path, cases_root: Path):
        self.root = root
        self.cases_root = cases_root
        root.mkdir(parents=True, exist_ok=True)
        self.db_path = root / "catalogo.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS companies (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, tax_id TEXT NOT NULL UNIQUE,
                    domain_ref TEXT NOT NULL, municipality TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id),
                    period TEXT NOT NULL, path TEXT NOT NULL, origin TEXT NOT NULL,
                    reference TEXT NOT NULL, fingerprint TEXT NOT NULL, created_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(company_id, period, fingerprint)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_snapshot
                    ON snapshots(company_id, period) WHERE active = 1;
                CREATE TABLE IF NOT EXISTS batches (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    snapshot_id TEXT NOT NULL REFERENCES snapshots(id), finding_id TEXT NOT NULL,
                    status TEXT NOT NULL, note TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(snapshot_id, finding_id)
                );
                CREATE TABLE IF NOT EXISTS review_history (
                    snapshot_id TEXT NOT NULL, finding_id TEXT NOT NULL,
                    status TEXT NOT NULL, note TEXT NOT NULL, updated_at TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def companies(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM companies ORDER BY name, tax_id")]

    def save_company(self, name: str, tax_id: str, domain_ref: str = "", municipality: str = "") -> str:
        tax_id = re.sub(r"[.\-/\s]", "", tax_id)
        if not name.strip() or not re.fullmatch(r"\d{14}", tax_id):
            raise ValueError("Preencha o nome e um CNPJ com 14 dígitos")
        with self.connect() as db:
            existing = db.execute("SELECT id FROM companies WHERE tax_id=?", (tax_id,)).fetchone()
            identifier = existing[0] if existing else uuid4().hex
            db.execute("""INSERT INTO companies VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tax_id) DO UPDATE SET name=excluded.name,
                domain_ref=excluded.domain_ref, municipality=excluded.municipality""",
                       (identifier, name.strip(), tax_id, domain_ref.strip(), municipality.strip()))
        return identifier

    def company(self, identifier: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM companies WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise ValueError("Empresa não encontrada")
        return dict(row)

    def snapshots(self, company_id: str, period: str) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM snapshots WHERE company_id=? AND period=? ORDER BY created_at DESC",
                (company_id, period))]

    def snapshot(self, identifier: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM snapshots WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise ValueError("Importação não encontrada")
        return dict(row)

    def activate(self, identifier: str) -> None:
        item = self.snapshot(identifier)
        with self.connect() as db:
            db.execute("UPDATE snapshots SET active=0 WHERE company_id=? AND period=?",
                       (item["company_id"], item["period"]))
            db.execute("UPDATE snapshots SET active=1 WHERE id=?", (identifier,))

    def _inspect(self, path: Path, company_id: str, period: str) -> tuple[dict, str]:
        validate_period(period)
        company = self.company(company_id)
        metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        config = json.loads((path / "config/company_profile.json").read_text(encoding="utf-8"))
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        profile = (path / "config/tax_profile.json").read_bytes()
        if not all(isinstance(value, dict) for value in (metadata, config, manifest, json.loads(profile))):
            raise ValueError("Metadados, manifesto e perfis devem ser objetos JSON")
        if not isinstance(manifest.get("files"), list) or any(not isinstance(entry, dict) for entry in manifest["files"]):
            raise ValueError("Manifesto sem lista válida de arquivos")
        if any(not isinstance(entry.get("path"), str) or not isinstance(entry.get("type"), str) for entry in manifest["files"]):
            raise ValueError("Arquivo do manifesto sem caminho ou tipo válido")
        if metadata.get("company_tax_id") != company["tax_id"] or config.get("tax_id") != company["tax_id"]:
            raise ValueError("O CNPJ da fonte não corresponde à empresa selecionada")
        normalized = normalize_case(path, period)
        for doc in normalized["documents"]:
            if company["tax_id"] not in (doc["issuer_tax_id"], doc["recipient_tax_id"]):
                raise ValueError("A fonte contém uma NF-e de outra empresa; confira o CNPJ selecionado")
        # Inclui conteúdo e parâmetros; a identidade não depende do nome da pasta.
        hashes = []
        for entry in manifest["files"]:
            relative = Path(entry["path"])
            source = (path / relative).resolve()
            if not str(relative).startswith("raw/") or not source.is_relative_to((path / "raw").resolve()):
                raise ValueError("Caminho de arquivo fora da fonte")
            data = source.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest != entry["sha256"] or len(data) != entry["size_bytes"]:
                raise ValueError("A fonte foi modificada; confira o manifesto e importe novamente")
            hashes.append((entry["type"], digest))
        fingerprint = hashlib.sha256(json_bytes([sorted(hashes), hashlib.sha256(profile).hexdigest()])).hexdigest()
        return normalized, fingerprint

    def register_reference(self, company_id: str, period: str, path: Path,
                           origin: str, reference: str = "") -> str:
        path = path.resolve()
        _, fingerprint = self._inspect(path, company_id, period)
        with self.connect() as db:
            existing = db.execute("SELECT id FROM snapshots WHERE company_id=? AND period=? AND fingerprint=?",
                                  (company_id, period, fingerprint)).fetchone()
            identifier = existing[0] if existing else uuid4().hex
            db.execute("UPDATE snapshots SET active=0 WHERE company_id=? AND period=?", (company_id, period))
            if existing:
                db.execute("UPDATE snapshots SET active=1 WHERE id=?", (identifier,))
            else:
                db.execute("INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
                           (identifier, company_id, period, str(path), origin, reference, fingerprint, now()))
        return identifier

    def import_files(self, company_id: str, period: str, uploads: dict[str, bytes],
                     xmls: list[tuple[str, bytes]], profile: Path, origin: str, reference: str = "") -> str:
        validate_period(period)
        company = self.company(company_id)
        if set(uploads) - set(UPLOAD_TYPES):
            raise ValueError("Tipo de CSV não suportado")
        if not uploads.get("nfe_csv") and not xmls:
            raise ValueError("Envie as notas em CSV ou XML")
        if uploads.get("nfe_csv") and xmls:
            raise ValueError("Escolha CSV ou XML para as notas nesta importação")
        if len(xmls) > 200:
            raise ValueError("Envie até 200 XMLs por importação")
        contents = list(uploads.values()) + [data for _, data in xmls]
        if any(not isinstance(data, bytes) or not data or len(data) > MAX_FILE_BYTES for data in contents):
            raise ValueError("Arquivo vazio ou maior que 10 MiB")
        if sum(map(len, contents)) > 50 * 1024 * 1024:
            raise ValueError("A importação deve ter até 50 MiB")
        self.cases_root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".incoming-", dir=self.cases_root))
        destination = self.cases_root / ("importacao-" + uuid4().hex)
        try:
            entries = []
            files = [(UPLOAD_TYPES[kind], kind, data) for kind, data in uploads.items()]
            from .parsers import NFE_NS, parse_event, parse_nfe, safe_xml
            for index, (name, data) in enumerate(xmls):
                root = safe_xml(data)
                if root.tag == f"{{{NFE_NS}}}procEventoNFe":
                    parse_event(data, name)
                    kind = "nfe_event_xml"
                else:
                    parse_nfe(data, name)
                    kind = "nfe_xml"
                files.append((f"raw/notas/{index:04d}.xml", kind, data))
            for relative, kind, data in files:
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                entries.append({"path": relative, "type": kind, "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)})
            metadata = dict(case_id=destination.name, company_id=company_id, company_name=company["name"],
                            company_tax_id=company["tax_id"], competencia=period, reference_date=date.today().isoformat(),
                            source="local_import", expected_sources=sorted({entry["type"] for entry in entries}))
            (staging / "metadata.json").write_bytes(json_bytes(metadata))
            (staging / "manifest.json").write_bytes(json_bytes({**metadata, "files": entries, "collected_at": now()}))
            (staging / "config").mkdir()
            (staging / "config/company_profile.json").write_bytes(json_bytes({"company_id": company_id, "tax_id": company["tax_id"]}))
            (staging / "config/tax_profile.json").write_bytes(profile.read_bytes())
            normalized, fingerprint = self._inspect(staging, company_id, period)
            if normalized["errors"]:
                raise ValueError("; ".join(error["message"] for error in normalized["errors"]))
            if not normalized["documents"]:
                raise ValueError("Nenhuma NF-e encontrada nos arquivos")
            for existing in self.snapshots(company_id, period):
                if existing["fingerprint"] == fingerprint:
                    self.activate(existing["id"])
                    return existing["id"]
            staging.rename(destination)
            try:
                identifier = self.register_reference(company_id, period, destination, origin, reference)
                if Path(self.snapshot(identifier)["path"]) != destination:
                    shutil.rmtree(destination)
                return identifier
            except Exception:
                shutil.rmtree(destination)
                raise
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    def inventory(self, snapshot_id: str) -> tuple[list[dict], list[dict]]:
        snapshot = self.snapshot(snapshot_id)
        normalized, fingerprint = self._inspect(Path(snapshot["path"]), snapshot["company_id"], snapshot["period"])
        if fingerprint != snapshot["fingerprint"]:
            raise ValueError("A fonte mudou desde o vínculo. Registre a nova versão antes de continuar")
        grouped: dict[str, dict] = {}
        for doc in normalized["documents"]:
            key = doc["access_key"]
            if key not in grouped:
                grouped[key] = {"Chave": key, "Emissão": doc["issue_date"], "Situação": "Cancelada" if doc["status"] == "cancelled" else "Autorizada",
                                "Valor": doc["total_value"], "Emitente": doc["issuer_tax_id"], "Destinatário": doc["recipient_tax_id"],
                                "Registros": 0, "Origem": snapshot["origin"], "Referência": snapshot["reference"], "Arquivos": set(),
                                "Competência": snapshot["period"], "Fora da competência": doc["issue_date"][:7] != snapshot["period"]}
            grouped[key]["Registros"] += 1
            grouped[key]["Arquivos"].add(doc["source_path"])
            if grouped[key]["Valor"] != doc["total_value"] or grouped[key]["Emissão"] != doc["issue_date"]:
                grouped[key]["Situação"] = "Dados conflitantes — revisar"
        for item in grouped.values():
            item["Arquivos"] = "; ".join(sorted(item["Arquivos"]))
        return sorted(grouped.values(), key=lambda item: item["Chave"]), normalized["errors"]

    def run_batch(self, company_ids: list[str], period: str, portals: list[str], progress=None) -> dict:
        validate_period(period)
        if not company_ids:
            raise ValueError("Selecione pelo menos uma empresa")
        if set(portals) - set(PORTALS):
            raise ValueError("Fonte de consulta desconhecida")
        companies = [self.company(identifier) for identifier in dict.fromkeys(company_ids)]
        batch = {"id": uuid4().hex, "created_at": now(), "period": period, "items": []}
        for index, company in enumerate(companies):
            coverage = [{"source": portal, "status": "Pendente de integração", "detail":
                         "Consulta não executada. " + ((company["municipality"] or "Informe o município da empresa") if portal == "Prefeitura" else "Conector ainda não configurado.")}
                        for portal in portals]
            item = {"company_id": company["id"], "company_name": company["name"], "tax_id": company["tax_id"],
                    "domain_ref": company["domain_ref"], "coverage": coverage, "snapshot_id": None,
                    "result": None, "status": "Incompleta", "error": ""}
            try:
                snapshot = next((row for row in self.snapshots(company["id"], period) if row["active"]), None)
                if not snapshot:
                    raise ValueError("Nenhum inventário ativo para esta empresa e competência")
                item["snapshot_id"] = snapshot["id"]
                _, fingerprint = self._inspect(Path(snapshot["path"]), company["id"], period)
                if fingerprint != snapshot["fingerprint"]:
                    raise ValueError("A fonte mudou desde o vínculo; registre a nova versão")
                result = analyze_case(Path(snapshot["path"]), period)
                normalized = result.pop("normalized")
                if not normalized["documents"] or not normalized["bookkeeping"] or normalized["declared"] is None:
                    result["status"] = "incomplete"
                    item["error"] = "Faltam notas, escrituração ou valores informados para concluir a análise"
                    result["calculation"]["status"] = "incomplete"
                    result["calculation"]["limitations"].append(item["error"])
                elif result["input_errors"]:
                    item["error"] = "Há erros de entrada; consulte as evidências e corrija a fonte"
                item["result"] = result
                item["coverage"].insert(0, {"source": snapshot["origin"], "status": "Arquivos disponíveis analisados",
                                           "detail": snapshot["reference"] or "Importação local; sem confirmação de consulta ao portal"})
                if result["status"] == "complete" and not portals:
                    item["status"] = "Com divergências" if result["occurrences"] else "Sem divergências detectadas"
            except (OSError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
                item["error"] = user_error(exc)
            batch["items"].append(item)
            if progress:
                progress(index + 1, len(companies))
        with self.connect() as db:
            db.execute("INSERT INTO batches VALUES (?, ?, ?)", (batch["id"], batch["created_at"], json.dumps(batch, ensure_ascii=False)))
        return batch

    def batches(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT id, created_at FROM batches ORDER BY created_at DESC")]

    def batch(self, identifier: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM batches WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise ValueError("Execução não encontrada")
        return json.loads(row[0])

    def review(self, snapshot_id: str, finding_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM reviews WHERE snapshot_id=? AND finding_id=?", (snapshot_id, finding_id)).fetchone()
        return dict(row) if row else {"status": "Pendente", "note": ""}

    def reviews(self, snapshot_id: str) -> dict[str, dict]:
        with self.connect() as db:
            return {row["finding_id"]: dict(row) for row in db.execute(
                "SELECT * FROM reviews WHERE snapshot_id=?", (snapshot_id,))}

    def save_review(self, snapshot_id: str, finding_id: str, status: str, note: str) -> None:
        self.snapshot(snapshot_id)
        if status not in REVIEW_STATUSES:
            raise ValueError("Situação de revisão inválida")
        if status == "Resolvido" and not note.strip():
            raise ValueError("Registre como a pendência foi resolvida")
        values = (snapshot_id, finding_id, status, note.strip(), now())
        with self.connect() as db:
            db.execute("INSERT INTO reviews VALUES (?, ?, ?, ?, ?) ON CONFLICT(snapshot_id, finding_id) DO UPDATE SET status=excluded.status, note=excluded.note, updated_at=excluded.updated_at", values)
            db.execute("INSERT INTO review_history VALUES (?, ?, ?, ?, ?)", values)

    def review_history(self, snapshot_id: str, finding_id: str) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT status, note, updated_at FROM review_history WHERE snapshot_id=? AND finding_id=? ORDER BY rowid", (snapshot_id, finding_id))]
