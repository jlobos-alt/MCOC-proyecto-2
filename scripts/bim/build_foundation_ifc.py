"""Genera el modelo IFC de la fundacion del capstone (geometria docente oficial).

Geometria (guia Blender + Bonsai del curso), planta octagonal:
    - 18 m entre caras opuestas (apotema a = 9 m) -> R_borde = 9/cos(pi/8) = 9.74153 m
    - plataforma central de 7 m entre caras -> R_int = 3.5/cos(pi/8) = 3.78837 m
    - R_medio = (R_borde + R_int)/2 = 6.76495 m

Vertidas (IfcFooting):
    V1  z 0.00-0.55   prisma octagonal R_borde
    V2  z 0.55-1.10   prisma octagonal R_borde
    V3  z 1.10-2.20   tronco octagonal R_borde -> R_medio
    V4  z 2.20-3.30   tronco octagonal R_medio -> R_int
    V5  z 3.30-4.30   cilindro central R 3.5

El octagono se orienta con cara (no vertice) hacia los ejes: vertices a 22.5 grados.

Uso:
    python scripts/bim/build_foundation_ifc.py [salida.ifc]
"""

from __future__ import annotations

import math
import os
import sys

import ifcopenshell
import ifcopenshell.api


LADO = 18.0
APOTEMA = LADO / 2.0
R_BORDE = APOTEMA / math.cos(math.pi / 8.0)      # 9.74153
R_INT = 3.5 / math.cos(math.pi / 8.0)            # 3.78837
R_MEDIO = (R_BORDE + R_INT) / 2.0                # 6.76495
LADOS_OCT = 8
LADOS_CIL = 48
ROTACION_Z_GADOS = 22.5

T_COLOCACION = 18.0
HORAS_ENTRE_VERTIDAS = 6.0
RETIRO_MOLDAJE = 72.0
NOMBRE_MATERIAL = "M1"
PSET_NAME = "UANDES_HormigonMasivo"

# Hormigon M1 (ver datos/caso_fundacion.yaml).
K = 2.222
CP = 970.0
RHO = 2400.0


def _vertices_poligono(n: int, radio: float, rot_deg: float = ROTACION_Z_GADOS):
    """Coordenadas 2D de un poligono regular de n lados, orientado por rot_deg."""
    rot = math.radians(rot_deg)
    return [
        (
            radio * math.cos(2.0 * math.pi * i / n + rot),
            radio * math.sin(2.0 * math.pi * i / n + rot),
        )
        for i in range(n)
    ]


def _perfil_poligono(model, n: int, radio: float):
    puntos = _vertices_poligono(n, radio)
    ifc_puntos = [model.create_entity("IfcCartesianPoint", Coordinates=(x, y)) for x, y in puntos]
    ifc_puntos.append(ifc_puntos[0])
    polyline = model.create_entity("IfcPolyline", Points=ifc_puntos)
    return model.create_entity("IfcArbitraryClosedProfileDef", ProfileType="AREA", OuterCurve=polyline)


def _perfil_circulo(model, radio: float):
    return model.create_entity("IfcCircleProfileDef", ProfileType="AREA", Radius=radio)


def _solido(model, body, perfil, z_min: float, profundidad: float, perfil_final=None):
    eje = model.create_entity(
        "IfcAxis2Placement3D",
        Location=model.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, z_min)),
    )
    direccion = model.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    if perfil_final is None:
        item = model.create_entity(
            "IfcExtrudedAreaSolid",
            SweptArea=perfil,
            Position=eje,
            ExtrudedDirection=direccion,
            Depth=profundidad,
        )
    else:
        item = model.create_entity(
            "IfcExtrudedAreaSolidTapered",
            SweptArea=perfil,
            Position=eje,
            ExtrudedDirection=direccion,
            Depth=profundidad,
            EndSweptArea=perfil_final,
        )
    forma = model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=body,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[item],
    )
    return model.create_entity("IfcProductDefinitionShape", Representations=[forma])


VERTIDAS = [
    {"id": 1, "tipo": "oct", "r1": R_BORDE, "r2": None, "z0": 0.00, "z1": 0.55},
    {"id": 2, "tipo": "oct", "r1": R_BORDE, "r2": None, "z0": 0.55, "z1": 1.10},
    {"id": 3, "tipo": "oct", "r1": R_BORDE, "r2": R_MEDIO, "z0": 1.10, "z1": 2.20},
    {"id": 4, "tipo": "oct", "r1": R_MEDIO, "r2": R_INT, "z0": 2.20, "z1": 3.30},
    {"id": 5, "tipo": "cil", "r1": 3.5, "r2": None, "z0": 3.30, "z1": 4.30},
]


def build(salida: str) -> str:
    model = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="Proyecto2")
    ifcopenshell.api.run("unit.assign_unit", model, length={"is_metric": True, "raw": "METERS"})

    model3d = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body = ifcopenshell.api.run(
        "context.add_context",
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model3d,
    )

    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Pahuil_Chanco")
    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Aerogenerador")
    storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Fundacion")
    proyecto = model.by_type("IfcProject")[0]
    ifcopenshell.api.run("aggregate.assign_object", model, products=[site], relating_object=proyecto)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[building], relating_object=site)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[storey], relating_object=building)

    material_m1 = ifcopenshell.api.run("material.add_material", model, name=NOMBRE_MATERIAL, category="concrete")
    pset_mat = ifcopenshell.api.run("pset.add_pset", model, product=material_m1, name="Pset_MaterialThermal")
    ifcopenshell.api.run(
        "pset.edit_pset",
        model,
        pset=pset_mat,
        properties={"ThermalConductivity": K, "SpecificHeatCapacity": CP, "Density": RHO},
    )

    for spec in VERTIDAS:
        nombre = f"Vertida_{spec['id']:02d}"
        z0, z1 = spec["z0"], spec["z1"]
        prof = z1 - z0

        if spec["tipo"] == "cil":
            perfil = _perfil_circulo(model, spec["r1"])
            perfil_final = None
        else:
            perfil = _perfil_poligono(model, LADOS_OCT, spec["r1"])
            perfil_final = _perfil_poligono(model, LADOS_OCT, spec["r2"]) if spec["r2"] else None

        vertida = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcFooting", name=nombre)
        vertida.Description = f"Vertida {spec['id']}/5, z de {z0:.2f} a {z1:.2f} m"
        vertida.Representation = _solido(model, body, perfil, z0, prof, perfil_final)
        ifcopenshell.api.run("spatial.assign_container", model, products=[vertida], relating_structure=storey)
        ifcopenshell.api.run("material.assign_material", model, products=[vertida], material=material_m1)

        pset_v = ifcopenshell.api.run("pset.add_pset", model, product=vertida, name=PSET_NAME)
        ifcopenshell.api.run(
            "pset.edit_pset",
            model,
            pset=pset_v,
            properties={
                "VertidaID": spec["id"],
                "Inicio_h": (spec["id"] - 1) * HORAS_ENTRE_VERTIDAS,
                "TemperaturaColocacion_C": T_COLOCACION,
                "TipoHormigon": NOMBRE_MATERIAL,
                "Moldaje": "TBD",
                "Aislacion": "TBD",
                "RetiroMoldaje_h": RETIRO_MOLDAJE,
                "Z_min_m": round(z0, 3),
                "Z_max_m": round(z1, 3),
            },
        )
        print(f"{nombre}: z {z0:.2f}-{z1:.2f} m, R {spec['r1']:.5f}" + (f" -> {spec['r2']:.5f}" if spec["r2"] else ""))

    model.write(salida)
    print("IFC exportado:", salida)
    return salida


def main() -> None:
    if len(sys.argv) > 1:
        salida = sys.argv[1]
    else:
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        salida = os.path.join(raiz, "modelo", "foundation.ifc")
    build(os.path.abspath(salida))


if __name__ == "__main__":
    main()
