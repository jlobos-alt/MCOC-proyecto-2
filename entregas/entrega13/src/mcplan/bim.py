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
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

import numpy as np


# Set de propiedades del curso. El segundo nombre se lee solo por compatibilidad con
# IFC antiguos del grupo: el prefijo Pset_ esta reservado a los sets de buildingSMART.
PSET_NOMBRES = ("UANDES_HormigonMasivo", "Pset_HormigonMasivo")


def _pset_del_curso(psets: dict) -> dict | None:
    for nombre in PSET_NOMBRES:
        if nombre in psets:
            return psets[nombre]
    return None


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
            props = dict(_pset_del_curso(psets) or {})
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
            if ps_cls != "IFCPROPERTYSET" or ps[2].strip("'") not in PSET_NOMBRES:
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


def inicios_en_horas(props: list[dict]) -> list[float]:
    """Hora de inicio de cada vertida: InicioPlanificado (fecha ISO) o Inicio_h (horas)."""
    if all("InicioPlanificado" in p for p in props):
        return horas_desde_primera([p["InicioPlanificado"] for p in props])
    if all("Inicio_h" in p for p in props):
        return [float(p["Inicio_h"]) for p in props]
    raise ValueError("Cada vertida debe tener InicioPlanificado o Inicio_h en su set de propiedades")


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
        props = _pset_del_curso(ue.get_psets(el))
        if props and "VertidaID" in props:
            elementos.append((el, props))
    if not elementos:
        raise ValueError(f"{path}: no hay elementos con {PSET_NOMBRES[0]}.VertidaID")

    inicios = inicios_en_horas([p for _, p in elementos])
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


def aplicar_cambios(
    solidos: list[SolidoVertida],
    inicio: dict[int, float] | None = None,
    tcol: dict[int, float] | None = None,
    intervalo_h: float | None = None,
) -> list[SolidoVertida]:
    """Copia de los solidos con otra secuencia: el IFC y los originales no cambian.

    `intervalo_h` reparte las vertidas cada tantas horas, en orden. Despues se aplican
    `inicio` {id: hora} y `tcol` {id: temperatura}, que mandan sobre el intervalo.
    """
    inicio, tcol = inicio or {}, tcol or {}
    ids = {s.vertida_id for s in solidos}
    for nombre, cambios in (("inicio", inicio), ("tcol", tcol)):
        for vertida in cambios:
            if vertida not in ids:
                raise KeyError(f"{nombre}: la vertida {vertida} no existe; hay {sorted(ids)}")
    if intervalo_h is not None and intervalo_h < 0 or any(h < 0 for h in inicio.values()):
        raise ValueError("Las horas de inicio y el intervalo no pueden ser negativos")
    nuevos = []
    for orden, solido in enumerate(sorted(solidos, key=lambda s: s.vertida_id)):
        hora = orden * intervalo_h if intervalo_h is not None else solido.inicio_h
        nuevos.append(replace(
            solido,
            inicio_h=float(inicio.get(solido.vertida_id, hora)),
            temperatura_colocacion_C=float(tcol.get(solido.vertida_id, solido.temperatura_colocacion_C)),
        ))
    return nuevos


def revisar_secuencia(solidos: list[SolidoVertida]) -> list[str]:
    """Avisos si una vertida se coloca antes que la que queda debajo: no se puede construir.

    Es un aviso y no un error: el solver lo calcula igual, pero el resultado no representa
    una obra posible.
    """
    avisos = []
    por_altura = sorted(solidos, key=lambda s: float(s.verts[:, 2].min()))
    for abajo, arriba in zip(por_altura, por_altura[1:]):
        if arriba.inicio_h < abajo.inicio_h:
            avisos.append(f"{arriba.nombre} ({arriba.inicio_h:g} h) se coloca antes que {abajo.nombre} "
                          f"({abajo.inicio_h:g} h), que va debajo: esa secuencia no es construible.")
    return avisos


def load_vertidas(path, backend: str = "auto") -> list[VertidaInfo]:
    path = Path(path)
    if backend in ("auto", "ifcopenshell"):
        try:
            return _with_ifcopenshell(path)
        except ImportError:
            if backend == "ifcopenshell":
                raise
    return _with_step_text(path)
