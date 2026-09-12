"""Galeria de ícones de blocos — extraídos do jar do cliente (offline).

O launcher já baixa os jars do Minecraft; as texturas moram dentro deles
(assets/minecraft/textures/...). Extraímos uma cópia para
~/.salsicha-launcher/icons/blocks/ e usamos como ícone de versão.
"""
from __future__ import annotations

from pathlib import Path
import zipfile

BASE = Path.home() / ".salsicha-launcher"
CACHE = BASE / "icons" / "blocks"

# (id, nome bonito, [candidatos modernos..., candidatos 1.12...])
BLOCKS: list[tuple[str, str, list[str]]] = [
    ("grama", "Bloco de Grama", ["assets/minecraft/textures/block/grass_block_side.png",
                                 "assets/minecraft/textures/blocks/grass_side.png"]),
    ("terra", "Terra", ["assets/minecraft/textures/block/dirt.png",
                        "assets/minecraft/textures/blocks/dirt.png"]),
    ("pedra", "Pedra", ["assets/minecraft/textures/block/stone.png",
                        "assets/minecraft/textures/blocks/stone.png"]),
    ("tabuas", "Tábuas de Carvalho", ["assets/minecraft/textures/block/oak_planks.png",
                                      "assets/minecraft/textures/blocks/planks_oak.png"]),
    ("tronco", "Tronco de Carvalho", ["assets/minecraft/textures/block/oak_log.png",
                                      "assets/minecraft/textures/blocks/log_oak.png"]),
    ("diamante", "Bloco de Diamante", ["assets/minecraft/textures/block/diamond_block.png",
                                       "assets/minecraft/textures/blocks/diamond_block.png"]),
    ("ouro", "Bloco de Ouro", ["assets/minecraft/textures/block/gold_block.png",
                               "assets/minecraft/textures/blocks/gold_block.png"]),
    ("ferro", "Bloco de Ferro", ["assets/minecraft/textures/block/iron_block.png",
                                 "assets/minecraft/textures/blocks/iron_block.png"]),
    ("esmeralda", "Bloco de Esmeralda", ["assets/minecraft/textures/block/emerald_block.png",
                                         "assets/minecraft/textures/blocks/emerald_block.png"]),
    ("redstone", "Bloco de Redstone", ["assets/minecraft/textures/block/redstone_block.png",
                                       "assets/minecraft/textures/blocks/redstone_block.png"]),
    ("lapis", "Bloco de Lápis-lazúli", ["assets/minecraft/textures/block/lapis_block.png",
                                        "assets/minecraft/textures/blocks/lapis_block.png"]),
    ("obsidian", "Obsidiana", ["assets/minecraft/textures/block/obsidian.png",
                               "assets/minecraft/textures/blocks/obsidian.png"]),
    ("glowstone", "Pedra Luminosa", ["assets/minecraft/textures/block/glowstone.png",
                                     "assets/minecraft/textures/blocks/glowstone.png"]),
    ("tnt", "TNT", ["assets/minecraft/textures/block/tnt_side.png",
                    "assets/minecraft/textures/blocks/tnt_side.png"]),
    ("crafting", "Bancada de Trabalho", ["assets/minecraft/textures/block/crafting_table_side.png",
                                         "assets/minecraft/textures/blocks/crafting_table_side.png"]),
    ("fornalha", "Fornalha", ["assets/minecraft/textures/block/furnace_front.png",
                              "assets/minecraft/textures/blocks/furnace_front_off.png"]),
    ("bau", "Baú", ["assets/minecraft/textures/entity/chest/normal.png",
                    "assets/minecraft/textures/entity/chest/chest.png"]),
    ("abobora", "Abóbora", ["assets/minecraft/textures/block/pumpkin_side.png",
                            "assets/minecraft/textures/blocks/pumpkin_side.png"]),
    ("melancia", "Melancia", ["assets/minecraft/textures/block/melon_side.png",
                              "assets/minecraft/textures/blocks/melon_side.png"]),
    ("estante", "Estante", ["assets/minecraft/textures/block/bookshelf.png",
                            "assets/minecraft/textures/blocks/bookshelf.png"]),
    ("vidro", "Vidro", ["assets/minecraft/textures/block/glass.png",
                        "assets/minecraft/textures/blocks/glass.png"]),
    ("bedrock", "Rocha Matriz", ["assets/minecraft/textures/block/bedrock.png",
                                 "assets/minecraft/textures/blocks/bedrock.png"]),
    ("netherrack", "Netherrack", ["assets/minecraft/textures/block/netherrack.png",
                                  "assets/minecraft/textures/blocks/netherrack.png"]),
    ("bolo", "Bolo", ["assets/minecraft/textures/block/cake_side.png",
                      "assets/minecraft/textures/blocks/cake_side.png"]),
]


def client_jars() -> list[Path]:
    """Jars de cliente baixados, puros primeiro (têm as texturas)."""
    vdir = BASE / "minecraft" / "versions"
    if not vdir.exists():
        return []
    jars: list[tuple[int, Path]] = []
    for ver in vdir.iterdir():
        j = ver / f"{ver.name}.jar"
        if j.exists() and j.stat().st_size > 1_000_000:
            pure = 0 if ver.name[0].isdigit() else 1
            jars.append((pure, j))
    jars.sort(key=lambda t: (t[0], t[1].name))
    return [j for _, j in jars]


def ensure_block_icons() -> dict[str, Path]:
    """Extrai (uma vez) e retorna {id: png}. Vazio se ainda não há jar."""
    CACHE.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    missing: list[tuple[str, str, list[str]]] = []
    for bid, _pretty, _cands in BLOCKS:
        hit = CACHE / f"{bid}.png"
        if hit.exists() and hit.stat().st_size > 0:
            out[bid] = hit
        else:
            missing.append((bid, _pretty, _cands))
    if not missing:
        return out
    jars = client_jars()
    if not jars:
        return out
    for jar in jars:
        if not missing:
            break
        try:
            zf = zipfile.ZipFile(jar)
        except Exception:
            continue
        try:
            names = set(zf.namelist())
            for bid, _pretty, cands in list(missing):
                for cand in cands:
                    if cand in names:
                        try:
                            (CACHE / f"{bid}.png").write_bytes(zf.read(cand))
                            out[bid] = CACHE / f"{bid}.png"
                            missing.remove((bid, _pretty, cands))
                        except Exception:
                            pass
                        break
        finally:
            try:
                zf.close()
            except Exception:
                pass
    return out
