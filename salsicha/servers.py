"""Servidores: lista curada + próprios + ping real (mcstatus)."""
from __future__ import annotations

import json
import re
from pathlib import Path

CUSTOM_FILE = Path.home() / ".salsicha-launcher" / "custom_servers.json"

DEFAULT_SERVERS = [
    {"id": "hypixel", "name": "Hypixel", "host": "mc.hypixel.net", "port": 25565,
     "desc": "Minigames • BedWars, SkyBlock", "color": "#e8a33d"},
    {"id": "cubecraft", "name": "CubeCraft", "host": "play.cubecraft.net", "port": 25565,
     "desc": "Minigames • EggWars, SkyWars", "color": "#4aa8ff"},
    {"id": "wynncraft", "name": "Wynncraft", "host": "play.wynncraft.com", "port": 25565,
     "desc": "MMORPG completo no Minecraft", "color": "#4ade80"},
    {"id": "2b2t", "name": "2b2t", "host": "connect.2b2t.org", "port": 25565,
     "desc": "Anarquia hardcore • fila longa", "color": "#ff6b6b"},
]

def load_custom() -> list[dict]:
    try:
        if CUSTOM_FILE.exists():
            data = json.loads(CUSTOM_FILE.read_text(encoding="utf-8"))
            return [s for s in data if isinstance(s, dict) and s.get("host")]
    except Exception:
        pass
    return []


def save_custom(servers: list[dict]) -> None:
    CUSTOM_FILE.parent.mkdir(parents=True, exist_ok=True)
    CUSTOM_FILE.write_text(json.dumps(servers, indent=2, ensure_ascii=False), encoding="utf-8")


def add_custom(name: str, host: str, port: int = 25565) -> list[dict]:
    servers = [s for s in load_custom() if s.get("host") != host]
    servers.append({"id": f"custom-{host}", "name": name or host,
                    "host": host, "port": port, "desc": "seu servidor",
                    "color": "#9d7bff"})
    save_custom(servers)
    return servers


def remove_custom(host: str) -> list[dict]:
    servers = [s for s in load_custom() if s.get("host") != host]
    save_custom(servers)
    return servers


def all_servers() -> list[dict]:
    seen = {s["host"] for s in DEFAULT_SERVERS}
    return list(DEFAULT_SERVERS) + [s for s in load_custom() if s.get("host") not in seen]


_FMT = re.compile(r"§[0-9a-fk-or]")


def clean_motd(text) -> str:
    if text is None:
        return ""
    if isinstance(text, dict):  # componentes novos
        text = text.get("text", "") + "".join(
            (e.get("text", "") if isinstance(e, dict) else str(e))
            for e in text.get("extra", []))
    s = _FMT.sub("", str(text)).replace("\n", " • ")
    return s[:90]


def ping(host: str, port: int = 25565, timeout: float = 5.0) -> dict:
    """{'online': bool, 'players': int, 'max': int, 'version': str, 'motd': str}"""
    try:
        from mcstatus import JavaServer
        st = JavaServer.lookup(f"{host}:{port}", timeout=timeout).status()
        return {"online": True, "players": st.players.online, "max": st.players.max,
                "version": getattr(st.version, "name", "?"), "motd": clean_motd(st.description)}
    except Exception as e:
        return {"online": False, "players": 0, "max": 0, "version": "—",
                "motd": f"offline ({type(e).__name__})"}
