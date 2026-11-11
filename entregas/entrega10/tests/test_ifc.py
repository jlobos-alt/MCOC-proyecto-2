"""Tests del modelo BIM: el IFC contiene las 5 vertidas con identidad y Pset."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "geometry"))
from mcplan.bim import load_vertidas  # noqa: E402

IFC = ROOT / "geometry" / "foundation.ifc"            # guardado por Bonsai
IFC_BASE = ROOT / "geometry" / "foundation_base.ifc"  # semilla generada por script


class TestIFC(unittest.TestCase):
    def setUp(self):
        self.v = load_vertidas(IFC, backend="auto")

    def test_five_vertidas(self):
        self.assertEqual([x.name for x in self.v], [f"Vertida_0{i}" for i in range(1, 6)])

    def test_unique_guids(self):
        g = [x.guid for x in self.v]
        self.assertEqual(len(set(g)), 5)
        self.assertTrue(all(len(x) == 22 for x in g))

    def test_pset(self):
        for i, x in enumerate(self.v, start=1):
            self.assertEqual(x.properties["VertidaID"], i)
            self.assertIn("InicioPlanificado", x.properties)
            self.assertIn("TemperaturaColocacion_C", x.properties)

    def test_total_volume(self):
        V = sum(x.properties["VolumenGeometrico_m3"] for x in self.v)
        a = lambda ap: 8 * ap * ap * math.tan(math.pi / 8)
        A0, A1, A2 = a(9.0), a(6.25), a(3.5)
        frus = lambda Aa, Ab, H: H / 3 * (Aa + Ab + math.sqrt(Aa * Ab))
        expected = A0 * 1.10 + frus(A0, A1, 1.1) + frus(A1, A2, 1.1) + math.pi * 3.5**2 * 1.0
        self.assertAlmostEqual(V, expected, places=3)

    def test_bonsai_preserves_identity(self):
        base = {x.name: x.guid for x in load_vertidas(IFC_BASE, backend="step")}
        self.assertEqual(base, {x.name: x.guid for x in self.v})

    def test_saved_by_bonsai(self):
        self.assertIn("Bonsai", IFC.read_text(encoding="utf-8", errors="replace")[:600])

    def test_regeneration_is_deterministic(self):
        import json
        import make_foundation_ifc as m
        geom = json.loads((ROOT / "geometry" / "course_geometry.json").read_text(encoding="utf-8"))
        txt, _ = m.build(geom)
        self.assertEqual(txt, IFC_BASE.read_text(encoding="ascii"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
