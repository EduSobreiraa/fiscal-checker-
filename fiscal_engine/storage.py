"""Pastas portáteis para os dados locais da interface."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping


def _absolute_path(value: str, setting: str, home: Path) -> Path:
    expanded = value.replace("~", str(home), 1) if value.startswith(("~/", "~\\")) or value == "~" else value
    path = Path(expanded)
    if not path.is_absolute():
        raise ValueError(f"{setting} deve indicar um caminho absoluto")
    return path.resolve()


def storage_paths(
    *, environ: Mapping[str, str] | None = None, platform: str | None = None,
    home: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Retorna (dados, casos, relatórios), sem depender da pasta do projeto."""
    env = os.environ if environ is None else environ
    system = sys.platform if platform is None else platform
    user_home = Path.home() if home is None else home

    if env.get("FISCAL_DATA_ROOT"):
        data_root = _absolute_path(env["FISCAL_DATA_ROOT"], "FISCAL_DATA_ROOT", user_home)
    elif system == "win32":
        data_root = _absolute_path(env.get("LOCALAPPDATA") or str(user_home / "AppData/Local"),
                                   "LOCALAPPDATA", user_home) / "Fiscal Checker"
    elif system == "darwin":
        data_root = user_home / "Library/Application Support/Fiscal Checker"
    else:
        xdg = env.get("XDG_DATA_HOME")
        base = _absolute_path(xdg, "XDG_DATA_HOME", user_home) if xdg else user_home / ".local/share"
        data_root = base / "fiscal-checker"

    cases = (_absolute_path(env["FISCAL_UPLOAD_ROOT"], "FISCAL_UPLOAD_ROOT", user_home)
             if env.get("FISCAL_UPLOAD_ROOT") else data_root / "casos")
    reports = (_absolute_path(env["FISCAL_OUTPUT_ROOT"], "FISCAL_OUTPUT_ROOT", user_home)
               if env.get("FISCAL_OUTPUT_ROOT") else data_root / "relatorios")
    return data_root, cases, reports
