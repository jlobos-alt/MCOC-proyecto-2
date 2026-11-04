"""
Genera geometry/foundation_base.ifc (IFC4) con las 5 vertidas de la geometría docente.

Escribe el archivo STEP (ISO-10303-21) directamente, sin dependencias, para que
el entorno sea reproducible aun sin internet. El archivo resultante se abre en
Blender + Bonsai (File > Open IFC Project) y con IfcOpenShell en Python.

Cada vertida es un IfcFooting con:
  - geometría (IfcExtrudedAreaSolid o IfcFacetedBrep),
  - material Hormigon_M1,
  - Pset_HormigonMasivo (VertidaID, TipoHormigon, InicioPlanificado, ...).

GlobalId deterministas (uuid5): regenerar el archivo NO cambia la identidad BIM.

Uso:  python geometry/make_foundation_ifc.py
"""
from __future__ import annotations

import json
import math
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "foundation_base.ifc"   # semilla; Bonsai la abre y guarda foundation.ifc
NS = uuid.UUID("6f1f3d2e-6c5b-4b8e-9a3e-0c2f6a1d0b11")

# Pset provisorio (se ajustará con el plan de vertidas real)
PSET = {
    1: dict(Inicio="2026-11-27T04:00:00", Tcol=18.0),
    2: dict(Inicio="2026-11-28T04:00:00", Tcol=18.0),
    3: dict(Inicio="2026-11-29T04:00:00", Tcol=18.0),
    4: dict(Inicio="2026-11-30T04:00:00", Tcol=18.0),
    5: dict(Inicio="2026-12-01T04:00:00", Tcol=18.0),
}

_CH = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"


def ifc_guid(name: str) -> str:
    """GUID IFC comprimido (22 caracteres), mismo algoritmo que ifcopenshell.guid.compress."""
    bs = uuid.uuid5(NS, name).bytes

    def b64(v, n):
        return "".join(_CH[(v // 64**i) % 64] for i in range(n))[::-1]

    return b64(bs[0], 2) + "".join(
        b64((bs[i] << 16) + (bs[i + 1] << 8) + bs[i + 2], 4) for i in range(1, 16, 3)
    )


def R_from_apothem(a: float) -> float:
    return a / math.cos(math.pi / 8)


def octagon(a: float, z: float | None = None):
    """Vértices CCW de un octágono regular con apotema a y caras alineadas a los ejes."""
    R = R_from_apothem(a)
    pts = []
    for k in range(8):
        th = math.pi / 8 + k * math.pi / 4
        p = (R * math.cos(th), R * math.sin(th))
        pts.append(p if z is None else (*p, z))
    return pts


def oct_area(a: float) -> float:
    return 8 * a * a * math.tan(math.pi / 8)


class Step:
    def __init__(self):
        self.lines: list[str] = []

    def add(self, txt: str) -> str:
        self.lines.append(txt)
        ref = f"#{len(self.lines)}"
        self.lines[-1] = f"{ref}={txt};"
        return ref


def f(v: float) -> str:
    s = repr(float(v))
    return s if ("." in s or "E" in s or "e" in s) else s + "."


def pt(s: Step, p) -> str:
    return s.add("IFCCARTESIANPOINT((" + ",".join(f(c) for c in p) + "))")


def lst(refs) -> str:
    return "(" + ",".join(refs) + ")"


def build(geom: dict) -> tuple[str, dict]:
    s = Step()
    a_ext = geom["entre_caras_ext_m"] / 2
    a_int = geom["entre_caras_int_m"] / 2
    a_mid = (a_ext + a_int) / 2     # R_medio = (R_ext+R_int)/2 equivale a apotema media
    resolve = lambda a: a_mid if a == "medio" else float(a)

    # --- unidades y contexto ------------------------------------------------
    u_len = s.add("IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.)")
    u_area = s.add("IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.)")
    u_vol = s.add("IFCSIUNIT(*,.VOLUMEUNIT.,$,.CUBIC_METRE.)")
    u_ang = s.add("IFCSIUNIT(*,.PLANEANGLEUNIT.,$,.RADIAN.)")
    units = s.add(f"IFCUNITASSIGNMENT({lst([u_len, u_area, u_vol, u_ang])})")
    o = pt(s, (0.0, 0.0, 0.0))
    dz = s.add("IFCDIRECTION((0.,0.,1.))")
    dx = s.add("IFCDIRECTION((1.,0.,0.))")
    world = s.add(f"IFCAXIS2PLACEMENT3D({o},{dz},{dx})")
    ctx = s.add(f"IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,{world},$)")
    body = s.add(f"IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,{ctx},$,.MODEL_VIEW.,$)")

    proj = s.add(f"IFCPROJECT('{ifc_guid('project')}',$,'MCOC Proyecto 2 - Hormigon Masivo',"
                 f"'Fundacion eolica docente (Ju & Lei 2019)',$,$,$,({ctx}),{units})")
    lp_site = s.add(f"IFCLOCALPLACEMENT($,{world})")
    site = s.add(f"IFCSITE('{ifc_guid('site')}',$,'Sitio',$,$,{lp_site},$,$,.ELEMENT.,$,$,$,$,$)")
    lp_bld = s.add(f"IFCLOCALPLACEMENT({lp_site},{world})")
    bld = s.add(f"IFCBUILDING('{ifc_guid('building')}',$,'Aerogenerador',$,$,{lp_bld},$,$,.ELEMENT.,$,$,$)")
    lp_sto = s.add(f"IFCLOCALPLACEMENT({lp_bld},{world})")
    sto = s.add(f"IFCBUILDINGSTOREY('{ifc_guid('storey')}',$,'Fundacion',$,$,{lp_sto},$,$,.ELEMENT.,0.)")
    s.add(f"IFCRELAGGREGATES('{ifc_guid('agg1')}',$,$,$,{proj},({site}))")
    s.add(f"IFCRELAGGREGATES('{ifc_guid('agg2')}',$,$,$,{site},({bld}))")
    s.add(f"IFCRELAGGREGATES('{ifc_guid('agg3')}',$,$,$,{bld},({sto}))")

    footings, volumes = [], {}
    for idx, v in enumerate(geom["vertidas"], start=1):
        name, z0, z1 = v["name"], v["z0"], v["z1"]
        H = z1 - z0
        if v["forma"] == "prisma_oct":
            a = resolve(v["a0"])
            poly_pts = [pt(s, p) for p in octagon(a)]
            poly = s.add(f"IFCPOLYLINE({lst(poly_pts + [poly_pts[0]])})")
            prof = s.add(f"IFCARBITRARYCLOSEDPROFILEDEF(.AREA.,'oct_{a:g}',{poly})")
            pos = s.add(f"IFCAXIS2PLACEMENT3D({pt(s, (0, 0, z0))},$,$)")
            solid = s.add(f"IFCEXTRUDEDAREASOLID({prof},{pos},{dz},{f(H)})")
            rtype = "SweptSolid"
            vol = oct_area(a) * H
        elif v["forma"] == "tronco_oct":
            a0, a1 = resolve(v["a0"]), resolve(v["a1"])
            bot, top = octagon(a0, z0), octagon(a1, z1)
            pb = [pt(s, p) for p in bot]
            pt_ = [pt(s, p) for p in top]
            faces = []

            def face(refs):
                loop = s.add(f"IFCPOLYLOOP({lst(refs)})")
                bnd = s.add(f"IFCFACEOUTERBOUND({loop},.T.)")
                faces.append(s.add(f"IFCFACE(({bnd}))"))

            face(list(reversed(pb)))           # base: normal -z
            face(pt_)                          # tapa: normal +z
            for k in range(8):                 # caras laterales inclinadas
                k2 = (k + 1) % 8
                face([pb[k], pb[k2], pt_[k2], pt_[k]])
            shell = s.add(f"IFCCLOSEDSHELL({lst(faces)})")
            solid = s.add(f"IFCFACETEDBREP({shell})")
            rtype = "Brep"
            A0, A1 = oct_area(a0), oct_area(a1)
            vol = H / 3 * (A0 + A1 + math.sqrt(A0 * A1))
        elif v["forma"] == "cilindro":
            r = v["r"]
            p2 = s.add(f"IFCAXIS2PLACEMENT2D({s.add('IFCCARTESIANPOINT((0.,0.))')},$)")
            prof = s.add(f"IFCCIRCLEPROFILEDEF(.AREA.,'circ_{r:g}',{p2},{f(r)})")
            pos = s.add(f"IFCAXIS2PLACEMENT3D({pt(s, (0, 0, z0))},$,$)")
            solid = s.add(f"IFCEXTRUDEDAREASOLID({prof},{pos},{dz},{f(H)})")
            rtype = "SweptSolid"
            vol = math.pi * r * r * H
        else:
            raise ValueError(v["forma"])

        rep = s.add(f"IFCSHAPEREPRESENTATION({body},'Body','{rtype}',({solid}))")
        pds = s.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({rep}))")
        lp = s.add(f"IFCLOCALPLACEMENT({lp_sto},{world})")
        el = s.add(f"IFCFOOTING('{ifc_guid(name)}',$,'{name}','Vertida {idx} de hormigon masivo',"
                   f"'Vertida',{lp},{pds},'V{idx:02d}',.PAD_FOOTING.)")
        footings.append(el)
        volumes[name] = vol

        p = PSET[idx]
        props = [
            s.add(f"IFCPROPERTYSINGLEVALUE('VertidaID',$,IFCINTEGER({idx}),$)"),
            s.add("IFCPROPERTYSINGLEVALUE('TipoHormigon',$,IFCLABEL('M1'),$)"),
            s.add(f"IFCPROPERTYSINGLEVALUE('InicioPlanificado',$,IFCDATETIME('{p['Inicio']}'),$)"),
            s.add(f"IFCPROPERTYSINGLEVALUE('TemperaturaColocacion_C',$,IFCREAL({f(p['Tcol'])}),$)"),
            s.add("IFCPROPERTYSINGLEVALUE('Moldaje',$,IFCLABEL('Madera'),$)"),
            s.add("IFCPROPERTYSINGLEVALUE('Aislacion',$,IFCLABEL('Ninguna'),$)"),
            s.add("IFCPROPERTYSINGLEVALUE('RetiroMoldaje_h',$,IFCREAL(72.),$)"),
            s.add(f"IFCPROPERTYSINGLEVALUE('VolumenGeometrico_m3',$,IFCVOLUMEMEASURE({f(round(vol, 6))}),$)"),
        ]
        ps = s.add(f"IFCPROPERTYSET('{ifc_guid(name + '_pset')}',$,'Pset_HormigonMasivo',$,{lst(props)})")
        s.add(f"IFCRELDEFINESBYPROPERTIES('{ifc_guid(name + '_rdp')}',$,$,$,({el}),{ps})")

    mat = s.add("IFCMATERIAL('Hormigon_M1',$,'Concrete')")
    s.add(f"IFCRELASSOCIATESMATERIAL('{ifc_guid('relmat')}',$,$,$,{lst(footings)},{mat})")
    s.add(f"IFCRELCONTAINEDINSPATIALSTRUCTURE('{ifc_guid('contain')}',$,$,$,{lst(footings)},{sto})")

    header = (
        "ISO-10303-21;\nHEADER;\n"
        "FILE_DESCRIPTION(('ViewDefinition [DesignTransferView]'),'2;1');\n"
        "FILE_NAME('foundation_base.ifc','2026-10-21T00:00:00',('MCOC Grupo'),(''),"
        "'mcplan make_foundation_ifc.py','mcplan','');\n"
        "FILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\n"
    )
    return header + "\n".join(s.lines) + "\nENDSEC;\nEND-ISO-10303-21;\n", volumes


def main():
    geom = json.loads((HERE / "course_geometry.json").read_text(encoding="utf-8"))
    txt, vols = build(geom)
    OUT.write_text(txt, encoding="ascii")
    print(f"Escrito {OUT}")
    for k, v in vols.items():
        print(f"  {k}: V = {v:9.3f} m^3")
    print(f"  TOTAL     : V = {sum(vols.values()):9.3f} m^3")


if __name__ == "__main__":
    main()
