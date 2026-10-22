"""Round-trip antes/después (E02): Python detecta lo que se edita en Bonsai.

Se simulan sobre el texto del IFC las tres ediciones típicas que se hacen en
Bonsai (cambiar una propiedad del Pset, mover una vertida y cambiar el espesor
de otra) y se comprueba que `mcplan.ifc_diff` las detecta. No necesita
IfcOpenShell ni Blender.
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan.ifc_diff import compare, snapshot  # noqa: E402

IFC = ROOT / "geometry" / "foundation.ifc"


def _write(txt: str) -> Path:
    tmp = Path(tempfile.mkdtemp()) / "editado.ifc"
    tmp.write_text(txt, encoding="utf-8")
    return tmp


def _footing_line(txt: str, name: str) -> str:
    return next(l for l in txt.splitlines() if "IFCFOOTING(" in l and f"'{name}'" in l)


class TestRoundTripBonsai(unittest.TestCase):
    def setUp(self):
        self.txt = IFC.read_text(encoding="utf-8")
        self.antes = snapshot(IFC)

    def test_sin_cambios(self):
        self.assertEqual(compare(self.antes, snapshot(IFC)), [])

    def test_cambio_de_propiedad(self):
        # Pset de Vertida_03: TemperaturaColocacion_C 18 -> 12.5
        footing = _footing_line(self.txt, "Vertida_03")
        fid = footing.split("=")[0]
        rel = next(l for l in self.txt.splitlines()
                   if "IFCRELDEFINESBYPROPERTIES(" in l and f"({fid})" in l)
        pset_id = rel.rstrip(");").split(",")[-1]
        pset = next(l for l in self.txt.splitlines() if l.startswith(pset_id + "="))
        prop_ids = re.search(r"\((#[\d,#]+)\)\);$", pset).group(1).split(",")
        tcol = next(l for l in self.txt.splitlines()
                    if l.split("=")[0] in prop_ids and "'TemperaturaColocacion_C'" in l)
        nuevo = self.txt.replace(tcol, tcol.replace("IFCREAL(18.)", "IFCREAL(12.5)").replace("IFCREAL(18.0)", "IFCREAL(12.5)"))
        cambios = compare(self.antes, snapshot(_write(nuevo)))
        self.assertEqual(len(cambios), 1, cambios)
        self.assertIn("Vertida_03: propiedad Pset_HormigonMasivo.TemperaturaColocacion_C", cambios[0])
        self.assertIn("-> 12.5", cambios[0])

    def test_mover_vertida(self):
        # Bonsai crea un IfcLocalPlacement propio para el objeto movido (+0.5 m en z)
        footing = _footing_line(self.txt, "Vertida_05")
        args = footing.split("(", 1)[1]
        parts = args.split(",")
        old_lp = parts[5]
        rel_to = re.search(r"IFCLOCALPLACEMENT\((#\d+),", next(
            l for l in self.txt.splitlines() if l.startswith(old_lp + "="))).group(1)
        nmax = max(int(l.split("=")[0][1:]) for l in self.txt.splitlines() if re.match(r"^#\d+=", l))
        nuevas = (f"#{nmax+1}=IFCCARTESIANPOINT((0.,0.,0.5));\n"
                  f"#{nmax+2}=IFCAXIS2PLACEMENT3D(#{nmax+1},$,$);\n"
                  f"#{nmax+3}=IFCLOCALPLACEMENT({rel_to},#{nmax+2});\n")
        nueva_linea = footing.replace(f",{old_lp},", f",#{nmax+3},", 1)
        nuevo = self.txt.replace(footing, nueva_linea).replace("ENDSEC;\nEND-ISO", nuevas + "ENDSEC;\nEND-ISO")
        cambios = compare(self.antes, snapshot(_write(nuevo)))
        texto = "\n".join(cambios)
        self.assertIn("Vertida_05: ubicación", texto)
        self.assertIn("z mínimo 3.300 -> 3.800", texto)
        self.assertIn("z máximo 4.300 -> 4.800", texto)
        self.assertNotIn("volumen", texto)          # mover no cambia el volumen
        self.assertTrue(all(c.startswith("Vertida_05") for c in cambios))

    def test_cambiar_espesor(self):
        # Extrusión de Vertida_01 de 0.55 a 0.60 m: cambia z máximo y volumen
        line = next(l for l in self.txt.splitlines()
                    if "IFCEXTRUDEDAREASOLID(" in l and l.rstrip(");").endswith(",0.55"))
        nuevo = self.txt.replace(line, line[:-len("0.55);")] + "0.6);", 1)
        cambios = compare(self.antes, snapshot(_write(nuevo)))
        texto = "\n".join(cambios)
        self.assertIn("z máximo 0.550 -> 0.600", texto)
        self.assertIn("volumen 147.626 -> 161.046", texto)

    def test_identidad_guid_se_conserva(self):
        despues = snapshot(IFC)
        self.assertEqual(set(self.antes["objetos"]), set(despues["objetos"]))
        self.assertEqual(len(despues["objetos"]), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
