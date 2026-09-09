"""Amigos locais (sem backend — caderno do jogador)."""
from __future__ import annotations

import json
from pathlib import Path

FILE = Path.home() / ".salsicha-launcher" / "friends.json"


def load() -> list[dict]:
    try:
        if FILE.exists():
            return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def save(friends: list[dict]) -> None:
    FILE.write_text(json.dumps(friends, indent=2, ensure_ascii=False), encoding="utf-8")


def shots_dir() -> Path:
    d = Path.home() / ".salsicha-launcher" / "minecraft" / "screenshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_shots() -> list[Path]:
    d = shots_dir()
    files = [f for f in d.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg")]
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


def avatar_path(nick: str) -> Path:
    d = Path.home() / ".salsicha-launcher" / "icons" / "avatars"
    d.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in nick if c.isalnum() or c in ("_", "-"))[:16] or "steve"
    return d / f"{safe}.png"


def fetch_avatar(nick: str, size: int = 64) -> Path | None:
    """Baixa a cabeça do skin (Minotar). Nicks offline ganham o Steve padrão."""
    import requests

    nick = (nick or "").strip()
    if not nick:
        return None
    dest = avatar_path(nick)
    try:
        if dest.exists() and dest.stat().st_size > 0:
            return dest
    except Exception:
        pass
    try:
        r = requests.get(f"https://minotar.net/helm/{nick}/{size}.png",
                         headers={"User-Agent": "Salsicha-Launcher/0.1.0"}, timeout=15)
        r.raise_for_status()
        if r.content[:8] == b"\x89PNG\r\n\x1a\n":
            dest.write_bytes(r.content)
            return dest
    except Exception:
        pass
    return dest if dest.exists() else None
