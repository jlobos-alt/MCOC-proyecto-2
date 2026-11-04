"""
Capa BIM: lee el IFC y devuelve objetos Python simples (sin detalles del esquema).

    IFC  --(IfcOpenShell)-->  [VertidaInfo(guid, name, properties, ...)]
    IFC  --(IfcOpenShell)-->  [SolidoVertida(verts, faces, inicio_h, ...)]

Si IfcOpenShell está instalado se usa (camino oficial del curso).
Si no, un lector mínimo del texto STEP permite listar vertidas y Psets
(útil para tests y CI sin dependencias pesadas).

La geometría sí requiere IfcOpenShell: un IFC puede describir un sólido como
extrusión, B-rep o malla, y es su motor el que convierte todo eso en triángulos.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np


@dataclass
class VertidaInfo:
    guid: str
    name: str
    ifc_class: str
    properties: dict = field(default_factory=dict)


def _with_ifcopenshell(path: Path) -> list[VertidaInfo]:
    import ifcopenshell
    import ifcopenshell.util.element as ue

    model = ifcopenshell.open(str(path))
    out = []
    for el in model.by_type("IfcElement"):
        if el.Name and el.Name.startswith("Vertida"):
            psets = ue.get_psets(el)
            props = dict(psets.get("Pset_HormigonMasivo", {}))
            props.pop("id", None)
            out.append(VertidaInfo(el.GlobalId, el.Name, el.is_a(), props))
    return sorted(out, key=lambda v: v.name)


_CLASS_NAMES = {"IFCFOOTING": "IfcFooting", "IFCSLAB": "IfcSlab",
                "IFCBUILDINGELEMENTPROXY": "IfcBuildingElementProxy"}

_ENT = re.compile(r"^#(\d+)=([A-Z0-9]+)\((.*)\);\s*$")


def _split_args(s: str) -> list[str]:
    out, depth, cur, q = [], 0, "", False
    for ch in s:
        if ch == "'":
            q = not q
        if not q and ch == "(":
            depth += 1
        if not q and ch == ")":
            depth -= 1
        if not q and ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def _parse_value(v: str):
    m = re.match(r"IFC[A-Z]+\((.*)\)$", v)
    if m:
        v = m.group(1)
    if v.startswith("'"):
        return v.strip("'")
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def _with_step_text(path: Path) -> list[VertidaInfo]:
    ents = {}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = _ENT.match(line.strip())
        if m:
            ents[int(m.group(1))] = (m.group(2), _split_args(m.group(3)))
    ref = lambda s: int(s.strip("#"))
    refs = lambda s: [ref(x) for x in s.strip("()").split(",") if x]
    elems = {}
    for i, (cls, a) in ents.items():
        name = a[2].strip("'") if len(a) > 2 else ""
        if cls in ("IFCFOOTING", "IFCSLAB", "IFCBUILDINGELEMENTPROXY") and name.startswith("Vertida"):
            elems[i] = VertidaInfo(a[0].strip("'"), name, _CLASS_NAMES[cls], {})
    for cls, a in ents.values():
        if cls == "IFCRELDEFINESBYPROPERTIES":
            ps_cls, ps = ents[ref(a[5])]
            if ps_cls != "IFCPROPERTYSET" or ps[2].strip("'") != "Pset_HormigonMasivo":
                continue
            props = {}
            for pid in refs(ps[4]):
                _, pa = ents[pid]
                props[pa[0].strip("'")] = _parse_value(pa[2])
            for eid in refs(a[4]):
                if eid in elems:
                    elems[eid].properties.update(props)
    return sorted(elems.values(), key=lambda v: v.name)


@dataclass
class SolidoVertida:
    """Una vertida del IFC: su malla de triángulos y lo que necesita el solver."""

    vertida_id: int
    nombre: str
    guid: str
    verts: np.ndarray                  # (N, 3) en coordenadas de mundo [m]
    faces: np.ndarray                  # (M, 3) índices de vértices
    inicio_h: float                    # horas desde la primera vertida
    temperatura_colocacion_C: float
    tipo_hormigon: str
    moldaje: str
    aislacion: str
    retiro_moldaje_h: float
    volumen_pset_m3: float | None = None

    @property
    def volumen(self) -> float:
        return volumen_malla(self.verts, self.faces)


def volumen_malla(verts: np.ndarray, faces: np.ndarray) -> float:
    """Volumen de una malla cerrada: suma de tetraedros contra el origen."""
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum())) / 6.0


def horas_desde_primera(fechas: list[str]) -> list[float]:
    """Convierte fechas ISO en horas contadas desde la más temprana."""
    tiempos = [datetime.fromisoformat(f) for f in fechas]
    cero = min(tiempos)
    return [(t - cero).total_seconds() / 3600.0 for t in tiempos]


def extraer_solidos(path) -> list[SolidoVertida]:
    """Lee del IFC la geometría triangulada y las propiedades de cada vertida."""
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.element as ue

    model = ifcopenshell.open(str(path))
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)   # aplica los IfcLocalPlacement

    elementos = []
    for el in model.by_type("IfcElement"):
        props = ue.get_psets(el).get("Pset_HormigonMasivo")
        if props and "VertidaID" in props:
            elementos.append((el, props))
    if not elementos:
        raise ValueError(f"{path}: no hay elementos con Pset_HormigonMasivo.VertidaID")

    inicios = horas_desde_primera([p["InicioPlanificado"] for _, p in elementos])
    solidos = []
    for (el, props), inicio_h in zip(elementos, inicios):
        geo = ifcopenshell.geom.create_shape(settings, el).geometry
        solidos.append(
            SolidoVertida(
                vertida_id=int(props["VertidaID"]),
                nombre=el.Name,
                guid=el.GlobalId,
                verts=np.array(geo.verts, dtype=float).reshape(-1, 3),
                faces=np.array(geo.faces, dtype=int).reshape(-1, 3),
                inicio_h=inicio_h,
                temperatura_colocacion_C=float(props["TemperaturaColocacion_C"]),
                tipo_hormigon=str(props["TipoHormigon"]),
                moldaje=str(props["Moldaje"]),
                aislacion=str(props["Aislacion"]),
                retiro_moldaje_h=float(props["RetiroMoldaje_h"]),
                volumen_pset_m3=props.get("VolumenGeometrico_m3"),
            )
        )
    return sorted(solidos, key=lambda s: s.vertida_id)


def load_vertidas(path, backend: str = "auto") -> list[VertidaInfo]:
    path = Path(path)
    if backend in ("auto", "ifcopenshell"):
        try:
            return _with_ifcopenshell(path)
        except ImportError:
            if backend == "ifcopenshell":
                raise
    return _with_step_text(path)
