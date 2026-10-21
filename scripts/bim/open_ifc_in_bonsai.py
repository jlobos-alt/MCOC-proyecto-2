"""Abre un archivo IFC en Blender + Bonsai.

Uso:
    blender --python scripts/bim/open_ifc_in_bonsai.py -- <ruta.ifc>
"""

import os
import sys

import bpy

try:
    if "bl_ext.blender_org.bonsai" not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module="bl_ext.blender_org.bonsai")
except Exception as exc:  # pragma: no cover
    print("No se pudo activar Bonsai:", exc)

if "--" in sys.argv:
    args = sys.argv[sys.argv.index("--") + 1 :]
else:
    args = []

if args:
    ruta = args[0]
else:
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ruta = os.path.join(raiz, "modelo", "foundation_bonsai.ifc")

ruta = os.path.abspath(ruta)
bpy.ops.bim.load_project(filepath=ruta)
print("IFC cargado en Bonsai:", ruta)
