"""Novidades do Minecraft (manifesto oficial da Mojang, com cache de 24h)."""
from __future__ import annotations

import json
import time
from pathlib import Path

CACHE = Path.home() / ".salsicha-launcher" / "news.json"
MANIFEST = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
TTL = 24 * 3600


def _load_cache() -> dict | None:
    try:
        if CACHE.exists() and time.time() - CACHE.stat().st_mtime < TTL:
            return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def fetch_news() -> dict:
    """{'release': str, 'snapshot': str, 'recent': [(id, type, date)], 'stale': bool}"""
    import requests

    cached = _load_cache()
    try:
        data = requests.get(MANIFEST, timeout=20).json()
        latest = data.get("latest", {})
        recent = [(v.get("id", "?"), v.get("type", "?"), (v.get("releaseTime", "") or "")[:10])
                  for v in (data.get("versions") or [])[:6]]
        out = {"release": latest.get("release", "?"), "snapshot": latest.get("snapshot", "?"),
               "recent": recent, "stale": False}
        try:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        return out
    except Exception:
        if cached:
            cached["stale"] = True
            return cached
        return {"release": "?", "snapshot": "?", "recent": [], "stale": True}
