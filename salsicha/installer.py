"""Instalação + comando de launch."""
from __future__ import annotations

import subprocess

import minecraft_launcher_lib

from .java_utils import get_minecraft_dir


def list_versions(kind: str = "release") -> list[dict]:
    """kind: release | snapshot | all"""
    all_versions = minecraft_launcher_lib.utils.get_version_list()
    if kind == "all":
        return all_versions
    return [v for v in all_versions if v.get("type") == kind]


def latest_release() -> str:
    return minecraft_launcher_lib.utils.get_latest_version()["release"]


def install_version(version: str, callback: dict | None = None) -> str:
    minecraft_launcher_lib.install.install_minecraft_version(
        version, get_minecraft_dir(), callback=callback
    )
    return version


LOADERS = ["vanilla", "fabric", "forge", "neoforge", "quilt"]


def list_loaders() -> list[str]:
    try:
        return ["vanilla"] + minecraft_launcher_lib.mod_loader.list_mod_loader()
    except Exception:
        return LOADERS


def loader_versions(loader_id: str, mc_version: str, stable_only: bool = True) -> list[str]:
    if loader_id == "vanilla":
        return []
    loader = minecraft_launcher_lib.mod_loader.get_mod_loader(loader_id)
    try:
        return loader.get_loader_versions(mc_version, stable_only)
    except TypeError:
        # assinaturas antigas sem stable_only
        return loader.get_loader_versions(mc_version)


def install_with_loader(version: str, loader_id: str = "vanilla",
                        loader_version: str | None = None,
                        callback: dict | None = None) -> str:
    """Instala e retorna o ID real da versão a lançar (loaders criam versão própria)."""
    if loader_id == "vanilla" or not loader_id:
        return install_version(version, callback)
    loader = minecraft_launcher_lib.mod_loader.get_mod_loader(loader_id)
    return loader.install(version, get_minecraft_dir(),
                          loader_version=loader_version or None,
                          callback=callback)


def build_command(version: str, options: dict, ram_gb: int = 4,
                  server: str | None = None, port: int | None = None,
                  game_dir: str | None = None) -> list[str]:
    opts = dict(options)
    opts.setdefault("jvmArguments", [f"-Xmx{ram_gb}G", f"-Xms{ram_gb}G"])
    opts.setdefault("launcherName", "Salsicha Launcher")
    opts.setdefault("launcherVersion", "0.1.0")
    opts.setdefault("gameDirectory", game_dir or get_minecraft_dir())
    if server:
        opts["server"] = server
        opts["port"] = str(port or 25565)
    return minecraft_launcher_lib.command.get_minecraft_command(
        version, get_minecraft_dir(), opts
    )


def launch(version: str, options: dict, ram_gb: int = 4,
           server: str | None = None, port: int | None = None,
           game_dir: str | None = None) -> subprocess.Popen:
    import datetime
    from pathlib import Path

    cmd = build_command(version, options, ram_gb, server, port, game_dir)
    logdir = Path.home() / ".salsicha-launcher" / "logs"
    try:
        logdir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        logf = open(logdir / f"game-{ts}.log", "w", encoding="utf-8", errors="replace")
    except Exception:
        logf = None  # type: ignore[assignment]
    if logf is None:
        return subprocess.Popen(cmd, cwd=game_dir or get_minecraft_dir())
    return subprocess.Popen(cmd, cwd=game_dir or get_minecraft_dir(),
                            stdout=logf, stderr=subprocess.STDOUT)
