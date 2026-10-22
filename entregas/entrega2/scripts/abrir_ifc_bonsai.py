"""Abre el IFC de la entrega 2 en Blender + Bonsai (modo GUI).

Bonsai necesita la interfaz grafica (en --background falla al inicializar
metadatos). Este script:
    1. activa la extension Bonsai,
    2. limpia la escena,
    3. carga el proyecto IFC indicado.

Uso (desde Blender):
    blender --python abrir_ifc_bonsai.py -- <ruta.ifc>
o dentro de Blender: Scripting > Open > este archivo > Run.
"""
import sys
from pathlib import Path

import bpy

DEFAULT_IFC = Path(__file__).resolve().parent / "foundation.ifc"

argv = sys.argv
if "--" in argv:
    args = argv[argv.index("--") + 1:]
    ifc_path = Path(args[0]).resolve() if args else DEFAULT_IFC
else:
    ifc_path = DEFAULT_IFC

if not ifc_path.exists():
    raise SystemExit(f"No existe el IFC: {ifc_path}")


def activar_bonsai():
    for module in ("bl_ext.blender_org.bonsai", "bonsai"):
        try:
            bpy.ops.preferences.addon_enable(module=module)
            print(f"[Bonsai] extension activada: {module}")
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[Bonsai] no se pudo activar '{module}': {e}")
    return False


print(f"[IFC] cargando: {ifc_path}")
activar_bonsai()

try:
    bpy.ops.bim.load_project(filepath=str(ifc_path))
    print("[IFC] proyecto cargado con Bonsai")
except Exception as e:  # noqa: BLE001
    print(f"[IFC] bim.load_project fallo ({e}); usando ifcopenshell + import generico")
    bpy.ops.import_scene.ifc(filepath=str(ifc_path))
    print("[IFC] importado (import_scene.ifc)")

objetos = [o for o in bpy.data.objects if o.type == "MESH"]
print(f"[IFC] objetos importados: {len(objetos)}")
for o in objetos:
    print(f"   - {o.name}")
