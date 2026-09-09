"""Config persistente do launcher."""
from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".salsicha-launcher"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "ram_gb": 4,
    "snapshots": False,
    "close_on_launch": True,
    "mods": {"sodium": True, "lithium": True, "fabric-api": True,
             "ferrite-core": False, "iris": False},
    "installations": [],
    "last_installation": "",
    "nick": "",
    "mode": "Offline",
    "ms_client_id": "",
    "ms_redirect": "http://localhost:8000",
}

CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        if CONFIG_FILE.exists():
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


def save(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
