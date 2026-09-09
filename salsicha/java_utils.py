"""Java + diretórios."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path.home() / ".salsicha-launcher"
MINECRAFT_DIR = BASE_DIR / "minecraft"

BASE_DIR.mkdir(parents=True, exist_ok=True)
MINECRAFT_DIR.mkdir(parents=True, exist_ok=True)


def get_minecraft_dir() -> str:
    return str(MINECRAFT_DIR)


def find_java() -> str | None:
    """Acha um java usável. A lib instala o runtime sozinha p/ versões novas,
    mas versões antigas precisam de Java 8/17 do sistema."""
    candidates = [
        shutil.which("java"),
        "/usr/lib/jvm/default-runtime/bin/java",
        "/usr/lib/jvm/java-21-openjdk/bin/java",
        "/usr/lib/jvm/java-17-openjdk/bin/java",
        "/usr/lib/jvm/java-8-openjdk/bin/java",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def required_java_major(mc_version: str) -> int:
    """Java exigido pela versão do Minecraft."""
    try:
        parts = (mc_version or "").strip().split(".")
        nums = [int(p) for p in parts if p.isdigit()]
        if not nums:
            return 21
        if nums[0] >= 20 and len(nums) == 1:
            return 21  # 26.x, 27.x... (novo esquema de versão)
        if nums[0] == 1 and len(nums) >= 2:
            minor = nums[1]
            if minor <= 16:
                return 8
            if minor < 20:
                return 17
            if minor == 20:
                patch = nums[2] if len(nums) >= 3 else 0
                return 21 if patch >= 5 else 17
            return 21
        return 21
    except Exception:
        return 21


def _runtime_java_candidates(major: int) -> list[str]:
    """Binários dentro de ~/.salsicha-launcher/minecraft/runtime (a lib baixa sozinha)."""
    names = {8: ("jre-legacy",), 17: ("java-runtime-beta", "java-runtime-gamma"),
             21: ("java-runtime-gamma", "java-runtime-delta", "java-runtime-epsilon")}.get(major, ())
    out: list[str] = []
    for n in names:
        for p in (MINECRAFT_DIR / "runtime" / n).rglob("bin/java"):
            if p.is_file():
                out.append(str(p))
    return sorted(out)


def get_java_for_mc(mc_version: str) -> str | None:
    """Melhor java para a MC: runtime da Mojang primeiro, depois sistema."""
    major = required_java_major(mc_version)
    for p in _runtime_java_candidates(major):
        return p
    system = {
        8: ["/usr/lib/jvm/java-8-openjdk/bin/java"],
        17: ["/usr/lib/jvm/java-17-openjdk/bin/java",
             "/usr/lib/jvm/java-21-openjdk/bin/java", shutil.which("java") or ""],
        21: ["/usr/lib/jvm/java-21-openjdk/bin/java",
             "/usr/lib/jvm/java-26-openjdk/bin/java",
             "/usr/lib/jvm/default-runtime/bin/java", shutil.which("java") or ""],
    }.get(major, [])
    for c in system:
        if c and Path(c).exists():
            return c
    return find_java()


def java_version(java_path: str) -> str:
    try:
        out = subprocess.run([java_path, "-version"], capture_output=True, text=True, timeout=5)
        return (out.stderr or out.stdout).splitlines()[0] if (out.stderr or out.stdout) else "?"
    except Exception as e:
        return str(e)
