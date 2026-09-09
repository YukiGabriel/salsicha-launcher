"""Diretório de jogo por instalação — mundos isolados por versão.

Cada instalação ganha ~/.salsicha-launcher/instances/<id>/ com saves,
mods, resourcepacks, shaderpacks e screenshots próprios. Bibliotecas,
assets e runtimes continuam compartilhados em minecraft/.
Na primeira vez, saves/fotos/texturas do diretório compartilhado antigo
são copiados (nunca movidos) para dentro da instância.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from .java_utils import get_minecraft_dir

BASE = Path.home() / ".salsicha-launcher" / "instances"
COPY_DIRS = ("saves", "screenshots", "resourcepacks", "shaderpacks")
MAKE_DIRS = COPY_DIRS + ("mods", "logs", "config")


def _safe_id(inst_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", inst_id or "default")[:64] or "default"


def game_dir_for(inst: dict) -> Path:
    return BASE / _safe_id(inst.get("id", "default"))


def ensure_instance(inst: dict, log=lambda m: None) -> Path:
    """Garante a pasta da instância + migração única do compartilhado."""
    gdir = game_dir_for(inst)
    gdir.mkdir(parents=True, exist_ok=True)
    for d in MAKE_DIRS:
        (gdir / d).mkdir(parents=True, exist_ok=True)
    marker = gdir / ".migrated"
    if not marker.exists():
        shared = Path(get_minecraft_dir())
        n = 0
        for d in COPY_DIRS:
            src = shared / d
            dst = gdir / d
            if src.exists() and not any(dst.iterdir()):
                try:
                    for item in src.iterdir():
                        t = dst / item.name
                        if t.exists():
                            continue
                        if item.is_dir():
                            shutil.copytree(item, t)
                        else:
                            shutil.copy2(item, t)
                        n += 1
                except Exception:
                    pass
        try:
            marker.write_text("1", encoding="utf-8")
        except Exception:
            pass
        if n:
            log(f"📦 {n} item(ns) migrados para esta versão (originais mantidos).")
    return gdir


def modpack_dir(slug: str) -> Path:
    key = re.sub(r"[^A-Za-z0-9._-]+", "-", slug)
    return Path.home() / ".salsicha-launcher" / "modpacks" / key
