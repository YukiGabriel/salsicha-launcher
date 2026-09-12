"""Trava de regressão do Salsicha Launcher (stdlib unittest, sem rede).

Roda com:  .venv/bin/python -m unittest discover -s tests -v
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from salsicha.java_utils import (  # noqa: E402
    modpack_mc,
    required_java_major,
)
from salsicha.modrinth import perf_mods_for, reconcile_mods_for_launch  # noqa: E402


class JavaMajorTest(unittest.TestCase):
    def test_classicas(self):
        self.assertEqual(required_java_major("1.12.2"), 8)
        self.assertEqual(required_java_major("1.8"), 8)
        self.assertEqual(required_java_major("1.16.5"), 8)

    def test_intermediarias(self):
        self.assertEqual(required_java_major("1.17.1"), 17)
        self.assertEqual(required_java_major("1.20.1"), 17)
        self.assertEqual(required_java_major("1.20.4"), 17)

    def test_modernas(self):
        self.assertEqual(required_java_major("1.20.5"), 21)
        self.assertEqual(required_java_major("1.21.1"), 21)
        self.assertEqual(required_java_major("26.2"), 21)

    def test_vazio(self):
        self.assertEqual(required_java_major(""), 21)
        self.assertEqual(required_java_major("?"), 21)

    def test_nunca_8_para_moderna(self):
        for mc in ("1.17", "1.20.1", "1.21.1", "26.2"):
            self.assertNotEqual(required_java_major(mc), 8, mc)


class ModpackMcTest(unittest.TestCase):
    def test_ficha_manda(self):
        self.assertEqual(modpack_mc("1.21.1", "neoforge-21.1.228"), "1.21.1")

    def test_neoforge_nao_e_mc(self):
        # "21.1" é o NeoForge; sem ficha, não pode virar "1.1" (o bug do Java 8)
        guess = modpack_mc("?", "neoforge-21.1.228")
        self.assertFalse(guess.startswith("1."),
                         f"adivinhou MC clássica de id NeoForge: {guess}")
        self.assertNotEqual(required_java_major(guess), 8)

    def test_fabric_loader(self):
        self.assertEqual(modpack_mc("", "fabric-loader-0.19.5-26.2"), "26.2")

    def test_forge(self):
        self.assertEqual(modpack_mc("?", "1.12.2-forge-14.23.5.2860"), "1.12.2")

    def test_vazio(self):
        self.assertEqual(modpack_mc("", ""), "")
        self.assertEqual(modpack_mc("?", ""), "")


class ModpackDoneParseTest(unittest.TestCase):
    def test_ok(self):
        from salsicha.app import MainWindow
        self.assertEqual(
            MainWindow.parse_modpack_done("__MODPACK_DONE__:meu-pack:fabric-loader-0.19.5-26.2"),
            ("meu-pack", "fabric-loader-0.19.5-26.2"))
        self.assertEqual(
            MainWindow.parse_modpack_done("__MODPACK_DONE__:pack:neoforge-21.1.228"),
            ("pack", "neoforge-21.1.228"))

    def test_malformado_nunca_silent_ok(self):
        from salsicha.app import MainWindow
        self.assertIsNone(MainWindow.parse_modpack_done("__MODPACK_DONE__:sem-versao"))
        self.assertIsNone(MainWindow.parse_modpack_done("__MODPACK_DONE__:"))
        self.assertIsNone(MainWindow.parse_modpack_done("lixo"))


class LoaderGuessTest(unittest.TestCase):
    def test_loaders(self):
        from salsicha.app import MainWindow
        f = MainWindow._loader_from_launch
        self.assertEqual(f("fabric-loader-0.19.3-26.2"), "fabric")
        self.assertEqual(f("1.12.2-forge-14.23.5.2860"), "forge")
        self.assertEqual(f("neoforge-21.1.228"), "neoforge")
        self.assertEqual(f("minecraft-1.21"), "")


class PerfPackTest(unittest.TestCase):
    def test_forge_tem_pack_proprio(self):
        pack = perf_mods_for("forge")
        self.assertIn("foamfix", pack)
        self.assertNotIn("sodium", pack)

    def test_fabric_moderno(self):
        pack = perf_mods_for("fabric")
        self.assertIn("sodium", pack)
        self.assertNotIn("foamfix", pack)


class ReconcileTest(unittest.TestCase):
    def _mods(self, *names):
        td = tempfile.mkdtemp()
        m = Path(td) / "mods"
        m.mkdir()
        for n in names:
            (m / n).write_text("x")
        return m

    def test_forge_mantem(self):
        m = self._mods("foamfix-0.10.15-1.12.2.jar", "aleatorio.jar")
        n = reconcile_mods_for_launch({"foamfix": True}, [], "forge", m, log=lambda x: None)
        rest = sorted(p.name for p in m.glob("*.jar"))
        self.assertIn("foamfix-0.10.15-1.12.2.jar", rest)
        self.assertEqual(n, 1)  # só o estranho foi guardado

    def test_vanilla_guarda_tudo(self):
        m = self._mods("algum-mod.jar")
        n = reconcile_mods_for_launch({}, [], "vanilla", m, log=lambda x: None)
        self.assertEqual(n, 1)
        self.assertEqual(list(m.glob("*.jar")), [])


class RealJavaTest(unittest.TestCase):
    def test_binario_real(self):
        from salsicha.java_utils import get_java_for_mc, java_major
        j8 = get_java_for_mc("1.12.2")
        if j8 and Path(j8).exists():
            self.assertEqual(java_major(j8), 8)
        j21 = get_java_for_mc("1.21.1")
        if j21 and Path(j21).exists():
            self.assertEqual(java_major(j21), 21)
        if not shutil.which("java"):
            self.skipTest("sem java no PATH")


if __name__ == "__main__":
    unittest.main()
