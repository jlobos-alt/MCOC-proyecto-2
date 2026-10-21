"""
Ejecutar DENTRO de Blender (con la extensión Bonsai instalada):

    Scripting > Python Console:
    exec(open(r"<ruta>/geometry/bonsai_open_and_save.py", encoding="utf-8").read())

1. Abre foundation_base.ifc como proyecto IFC de Bonsai (File > Open IFC Project).
2. Lo guarda con Bonsai como foundation.ifc (fuente de verdad del BIM).
3. Valida con IfcOpenShell (el mismo motor de Bonsai): clases, nombres, GUID,
   Pset y volumen real de cada vertida calculado de la geometría triangulada.
El reporte queda en geometry/bonsai_report.txt.
"""
import os
import bpy

GEO = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else GEO_DIR  # noqa: F821
SRC = os.path.join(GEO, "foundation_base.ifc")
DST = os.path.join(GEO, "foundation.ifc")
REPORT = os.path.join(GEO, "bonsai_report.txt")

bpy.ops.bim.load_project(filepath=SRC)
bpy.ops.bim.save_project(filepath=DST)

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import ifcopenshell.util.shape as us

m = ifcopenshell.open(DST)
st = ifcopenshell.geom.settings()
lines = [f"IfcOpenShell {ifcopenshell.version} | Blender {bpy.app.version_string}",
         f"Archivo: {DST}", f"Schema: {m.schema}", ""]
lines.append(f"{'Vertida':<12}{'Clase':<11}{'GUID':<24}{'V_geom[m3]':>11}{'V_pset[m3]':>11}")
tot = 0.0
for el in sorted(m.by_type("IfcFooting"), key=lambda e: e.Name):
    sh = ifcopenshell.geom.create_shape(st, el)
    V = us.get_volume(sh.geometry)
    tot += V
    p = ue.get_psets(el).get("Pset_HormigonMasivo", {})
    lines.append(f"{el.Name:<12}{el.is_a():<11}{el.GlobalId:<24}{V:>11.3f}{p.get('VolumenGeometrico_m3', 0):>11.3f}")
lines.append(f"{'TOTAL':<47}{tot:>11.3f}")
lines.append("")
lines.append("Objetos en la escena de Blender: " + ", ".join(sorted(o.name for o in bpy.data.objects)))
open(REPORT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
