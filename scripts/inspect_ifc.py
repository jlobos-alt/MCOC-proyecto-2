"""Lista las vertidas del IFC con su GUID y Pset (guía G03).

Uso:  python scripts/inspect_ifc.py [geometry/foundation.ifc]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan.bim import load_vertidas  # noqa: E402

path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "geometry" / "foundation.ifc"
try:
    import ifcopenshell  # noqa: F401
    backend = "IfcOpenShell"
except ImportError:
    backend = "lector STEP mínimo (IfcOpenShell no instalado)"
print(f"Archivo: {path}\nBackend: {backend}\n")
print(f"{'Vertida':<12}{'GUID':<25}{'Inicio':<22}{'Tcol[°C]':>9}{'V[m3]':>10}")
for v in load_vertidas(path):
    p = v.properties
    print(f"{v.name:<12}{v.guid:<25}{str(p.get('InicioPlanificado')):<22}"
          f"{p.get('TemperaturaColocacion_C', float('nan')):>9.1f}"
          f"{p.get('VolumenGeometrico_m3', float('nan')):>10.2f}")
