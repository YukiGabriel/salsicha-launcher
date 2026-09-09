"""Descoberta via Modrinth + instalação de modpacks (.mrpack)."""
from __future__ import annotations

from pathlib import Path

import requests

from .modrinth import UA

API = "https://api.modrinth.com/v2"


def search_projects(query: str = "", project_type: str = "modpack", limit: int = 8,
                    loaders: list[str] | None = None, game_version: str = "") -> list[dict]:
    """Busca ordenada por downloads. Retorna dicts com slug, title, description, icon_url, downloads, categories."""
    facets = [[f"project_type:{project_type}"]]
    if loaders:
        facets.append([f"categories:{l}" for l in loaders])
    if game_version:
        facets.append([f"versions:{game_version}"])
    params = {"query": query, "facets": __import__("json").dumps(facets),
              "limit": limit, "index": "downloads"}
    try:
        r = requests.get(f"{API}/search", params=params, headers=UA, timeout=20)
        r.raise_for_status()
        return r.json().get("hits", [])
    except Exception:
        return []


def featured_modpacks(limit: int = 8) -> list[dict]:
    return search_projects("", "modpack", limit)


def download_icon(icon_url: str, cache_dir: Path, slug: str) -> Path | None:
    if not icon_url:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{slug}.png"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    try:
        r = requests.get(icon_url, headers=UA, timeout=20)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return dest
    except Exception:
        return None


def install_mrpack_from_url(url: str, slug: str, minecraft_dir: Path,
                            modpacks_base: Path, log=lambda m: None,
                            progress_cb: dict | None = None, tag: str = "") -> str:
    """Baixa o .mrpack, instala isolado em modpacks/<slug>-<tag>, retorna versão de launch."""
    import re
    import minecraft_launcher_lib
    modpacks_base.mkdir(parents=True, exist_ok=True)
    key = f"{slug}-{tag}" if tag else slug
    key = re.sub(r"[^A-Za-z0-9._-]+", "-", key)
    mrpack_path = modpacks_base / f"{key}.mrpack"
    instance_dir = modpacks_base / key
    instance_dir.mkdir(parents=True, exist_ok=True)
    log(f"⬇ Baixando modpack {slug}…")
    with requests.get(url, headers=UA, timeout=120, stream=True) as r:
        r.raise_for_status()
        with open(mrpack_path, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    log("📦 Instalando modpack…")
    minecraft_launcher_lib.mrpack.install_mrpack(
        str(mrpack_path), str(minecraft_dir), str(instance_dir),
        callback=progress_cb)
    try:
        return minecraft_launcher_lib.mrpack.get_mrpack_launch_version(str(mrpack_path))
    except Exception:
        return ""


def mrpack_release(slug: str, mc_version: str = "") -> dict | None:
    """{'url', 'version', 'mc', 'filename'} do .mrpack mais recente
    (filtrando por MC se informado)."""
    try:
        vers = requests.get(f"{API}/project/{slug}/version",
                            params={"limit": 10}, headers=UA, timeout=20).json()
    except Exception:
        return None
    for v in vers:
        gvs = v.get("game_versions") or []
        if mc_version and mc_version not in gvs:
            continue
        for f in v.get("files", []):
            if f.get("filename", "").endswith(".mrpack"):
                return {"url": f["url"], "version": v.get("version_number", ""),
                        "mc": gvs, "filename": f.get("filename", "")}
    return None


def latest_mrpack_version_url(slug: str, mc_version: str = "") -> str | None:
    """URL do .mrpack mais recente (filtrando por MC se informado)."""
    r = mrpack_release(slug, mc_version)
    return r["url"] if r else None
