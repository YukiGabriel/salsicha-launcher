"""Mods de performance via Modrinth (estilo Lunar: FPS boost)."""
from __future__ import annotations

import json
from pathlib import Path

import requests

API = "https://api.modrinth.com/v2"
UA = {"User-Agent": "Salsicha-Launcher/0.1.0 (contact: local)"}

# slug -> (nome bonito, descrição)
PERF_MODS: dict[str, tuple[str, str]] = {
    "sodium": ("Sodium", "Render moderno — o maior ganho de FPS"),
    "lithium": ("Lithium", "Otimiza física e ticks do jogo"),
    "ferrite-core": ("FerriteCore", "Corta o uso de RAM"),
    "iris": ("Iris Shaders", "Shaders; combine com Sodium"),
    "fabric-api": ("Fabric API", "Obrigatório p/ a maioria dos mods Fabric"),
}

# Pack de otimização para Forge (1.12.2 e afins — testado no Modrinth).
# Sodium/Lithium/Iris não existem p/ Forge 1.12.2; estes sim.
FORGE_PERF_MODS: dict[str, tuple[str, str]] = {
    "foamfix": ("FoamFix", "Menos RAM e loading mais rápido (o essencial da 1.12.2)"),
    "vanillafix": ("VanillaFix", "Corrige crashes e melhora o desempenho vanilla"),
    "texfix": ("TexFix", "Otimiza texturas e o uso de memória"),
    "surge": ("Surge", "Acelera loading e recarregamentos"),
    "clumps": ("Clumps", "Agrupa orbes de XP — menos lag"),
}

SUPPORTED_LOADERS = ("fabric", "quilt", "forge", "neoforge")


def perf_mods_for(loader: str) -> dict[str, tuple[str, str]]:
    """Pack certo p/ cada loader. Forge usa o pack legado; resto usa o moderno."""
    if (loader or "vanilla") == "forge":
        return FORGE_PERF_MODS
    return PERF_MODS


def _get(url: str, params: dict | None = None, timeout: int = 20):
    r = requests.get(url, params=params, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.json()


def latest_file_url(slug: str, mc_version: str, loader: str = "fabric") -> tuple[str, str] | None:
    """Retorna (filename, download_url) do build mais novo compatível, ou None."""
    return latest_compat_file(slug, mc_version, [loader])


def latest_compat_file(slug: str, mc_version: str, loaders: list[str] | tuple[str, ...] = ("fabric",)) -> tuple[str, str] | None:
    """Igual ao acima, mas com lista de loaders.

    loaders vazia/None = qualquer loader (uso para shaders: iris/optifine/etc).
    resourcepacks usam ["minecraft"], mods usam [loader] (fabric/quilt/forge...).
    """
    try:
        params: dict = {"limit": 5}
        if mc_version:
            params["game_versions"] = f'["{mc_version}"]'
        if loaders:
            params["loaders"] = json.dumps(list(loaders))
        data = _get(f"{API}/project/{slug}/version", params)
    except Exception:
        return None
    for v in data:
        files = v.get("files") or []
        prim = [f for f in files if f.get("primary")] or files
        if prim:
            return prim[0]["filename"], prim[0]["url"]
    return None


def compat_status(slug: str, mc_version: str,
                  loaders: list[str] | tuple[str, ...] = ("fabric",)) -> bool | None:
    """True se há build p/ (mc, loaders); False se não há; None se offline/erro."""
    try:
        params: dict = {"limit": 5}
        if mc_version:
            params["game_versions"] = f'["{mc_version}"]'
        if loaders:
            params["loaders"] = json.dumps(list(loaders))
        data = _get(f"{API}/project/{slug}/version", params)
    except Exception:
        return None
    for v in data:
        files = v.get("files") or []
        prim = [f for f in files if f.get("primary")] or files
        if prim:
            return True
    return False


def supported_versions(slug: str, limit: int = 10) -> list[str]:
    """Últimas game_versions suportadas pelo projeto (para mensagem de erro)."""
    try:
        data = _get(f"{API}/project/{slug}/version", {"limit": limit})
    except Exception:
        return []
    seen: list[str] = []
    for v in data:
        for g in v.get("game_versions") or []:
            if g not in seen:
                seen.append(g)
    return seen[:20]


def reconcile_mods_for_launch(selection: dict[str, bool], store_files: list[str],
                              loader: str, mods_dir: Path, log=lambda m: None) -> int:
    """Isola mods por instalação: move para .salsicha-disabled/ o que não é da versão.

    selection: perf-mods marcados na instalação. store_files: filenames de mods
    da loja vinculados à instalação. Vanilla: guarda tudo. Retorna nº movidos.
    """
    try:
        mods_dir.mkdir(parents=True, exist_ok=True)
        disabled = mods_dir / ".salsicha-disabled"
        disabled.mkdir(parents=True, exist_ok=True)
        if loader == "vanilla" or not loader:
            moved = 0
            for f in mods_dir.glob("*.jar"):
                try:
                    f.rename(disabled / f.name)
                    moved += 1
                except Exception:
                    pass
            if moved:
                log(f"🧹 {moved} mod(s) guardados (versão sem loader).")
            return moved
        keep_prefixes = {s for s, w in (selection or {}).items() if w}
        keep_files = set(store_files or [])
        moved = 0
        for f in mods_dir.glob("*.jar"):
            if f.name in keep_files:
                continue
            if any(f.name.lower().startswith(s.lower()) for s in keep_prefixes):
                continue
            # store-mods com nome real diferente do slug: mantém se o slug aparece no nome
            if any(s.lower() in f.name.lower() for s in keep_files if s):
                continue
            try:
                f.rename(disabled / f.name)
                moved += 1
            except Exception:
                pass
        # restaura o que é desta versão mas estava guardado
        for f in disabled.glob("*.jar"):
            if f.name in keep_files or any(f.name.lower().startswith(s.lower()) for s in keep_prefixes):
                try:
                    f.rename(mods_dir / f.name)
                except Exception:
                    pass
        if moved:
            log(f"🧹 {moved} mod(s) de outra versão guardados.")
        return moved
    except Exception as e:
        log(f"ℹ reconciliação pulada: {e}")
        return 0


def check_mod_updates(slug: str, mc_version: str, loader: str,
                      installed_name: str) -> dict | None:
    """Compara o instalado com o mais novo. Retorna {slug, old, new, url} ou None."""
    found = latest_compat_file(slug, mc_version, [loader])
    if not found:
        return None
    fname, url = found
    if fname != installed_name:
        return {"slug": slug, "old": installed_name, "new": fname, "url": url}
    return None


def download_url_to(url: str, dest: Path, log=lambda m: None) -> bool:
    """Baixa uma URL para dest. Retorna True se ok."""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        log(f"⬇ {dest.name}…")
        with requests.get(url, headers=UA, timeout=120, stream=True) as r:
            r.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
        return True
    except Exception as e:
        log(f"⚠ falha no download: {e}")
        return False


def ensure_mods(mc_version: str, loader: str, selection: dict[str, bool],
               mods_dir: Path, log=lambda m: None) -> int:
    """Baixa os mods marcados. Retorna quantos instalados/atualizados."""
    if loader not in SUPPORTED_LOADERS:
        log("ℹ Mods automáticos valem para Fabric/Quilt/Forge/NeoForge nesta versão.")
        return 0
    # Forge tem pack próprio; ignora chaves do pack Fabric que sobraram no save.
    want_pack = perf_mods_for(loader)
    mods_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    for slug, want in selection.items():
        if slug not in want_pack and slug != "fabric-api":
            continue
        if loader == "forge" and slug == "fabric-api":
            continue
        target = mods_dir / f"{slug}.jar"  # marcador; nome real varia
        if not want:
            # remove versões antigas desse mod
            for f in mods_dir.glob(f"{slug}*.jar"):
                try:
                    f.unlink()
                except Exception:
                    pass
            try:
                target.unlink()
            except Exception:
                pass
            continue
        found = latest_file_url(slug, mc_version, loader)
        if not found:
            log(f"ℹ {slug}: sem build para {mc_version}.")
            continue
        fname, url = found
        dest = mods_dir / fname
        if dest.exists():
            done += 1
            continue
        # limpa builds antigas do mesmo mod
        for f in mods_dir.glob(f"{slug}*.jar"):
            try:
                f.unlink()
            except Exception:
                pass
        try:
            log(f"⬇ {fname}…")
            with requests.get(url, headers=UA, timeout=60, stream=True) as r:
                r.raise_for_status()
                with open(dest, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
            done += 1
        except Exception as e:
            log(f"⚠ falha em {slug}: {e}")
    return done
