"""Tests del round-trip IFC (E02): modificar -> guardar -> Python lo detecta.

Verifica el flujo minimo Bonsai->IFC->Python sin depender de Bonsai en si:
el IFC es la fuente de verdad, asi que basta con leerlo, editarlo y re-leerlo
con IfcOpenShell (el mismo motor que usa Bonsai).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from mcplan.bim import load_vertidas  # noqa: E402

IFC = ROOT / "geometry" / "foundation.ifc"

try:
    import ifcopenshell  # noqa: F401
    import ifcopenshell.api  # noqa: F401
    HAS_IFC = True
except ImportError:
    HAS_IFC = False


class TestIdentificacion(unittest.TestCase):
    """La actividad pide identificar >= 3 objetos en el IFC."""

    def test_al_menos_tres_objetos(self):
        self.assertGreaterEqual(len(load_vertidas(IFC)), 3)

    def test_nombres_y_guids_unicos(self):
        v = load_vertidas(IFC)
        self.assertEqual([x.name for x in v], [f"Vertida_0{i}" for i in range(1, 6)])
        self.assertEqual(len({x.guid for x in v}), 5)

    def test_clase_de_objeto(self):
        for x in load_vertidas(IFC):
            self.assertEqual(x.ifc_class, "IfcFooting")


@unittest.skipUnless(HAS_IFC, "IfcOpenShell no instalado")
class TestRoundTrip(unittest.TestCase):
    """Modificar una propiedad, guardar y comprobar que Python detecta el cambio."""

    def setUp(self):
        self.out = ROOT / "resultados" / "_tmp_roundtrip.ifc"
        self.out.parent.mkdir(exist_ok=True)

    def tearDown(self):
        self.out.unlink(missing_ok=True)

    def _edit(self, vertida, prop, value):
        import ifcopenshell
        import ifcopenshell.api
        import ifcopenshell.util.element as ue

        model = ifcopenshell.open(str(IFC))
        el = model.by_type("IfcElement")
        el = next(e for e in el if e.Name == vertida)
        pset = model.by_id(ue.get_psets(el)["Pset_HormigonMasivo"]["id"])
        ifcopenshell.api.run("pset.edit_pset", model, pset=pset, properties={prop: value})
        model.write(str(self.out))
        return model

    def test_modifica_temperatura_y_python_lo_detecta(self):
        self._edit("Vertida_03", "TemperaturaColocacion_C", 21.5)
        d = {v.name: v.properties for v in load_vertidas(self.out)}
        self.assertEqual(d["Vertida_03"]["TemperaturaColocacion_C"], 21.5)
        self.assertEqual(d["Vertida_01"]["TemperaturaColocacion_C"], 18.0)  # intactas

    def test_modifica_propiedad_de_texto(self):
        self._edit("Vertida_02", "Moldaje", "Acero")
        d = {v.name: v.properties for v in load_vertidas(self.out)}
        self.assertEqual(d["Vertida_02"]["Moldaje"], "Acero")

    def test_identidad_bim_se_preserva(self):
        guids_antes = {v.name: v.guid for v in load_vertidas(IFC)}
        self._edit("Vertida_05", "TemperaturaColocacion_C", 20.0)
        guids_despues = {v.name: v.guid for v in load_vertidas(self.out)}
        self.assertEqual(guids_antes, guids_despues)

    def test_no_altera_el_original(self):
        original = IFC.read_bytes()
        self._edit("Vertida_01", "TemperaturaColocacion_C", 99.0)
        self.assertEqual(IFC.read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
