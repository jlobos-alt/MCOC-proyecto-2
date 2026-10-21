"""
Capa BIM: lee el IFC y devuelve objetos Python simples (sin detalles del esquema).

    IFC  --(IfcOpenShell)-->  [VertidaInfo(guid, name, properties, ...)]

Si IfcOpenShell está instalado se usa (camino oficial del curso).
Si no, un lector mínimo del texto STEP permite listar vertidas y Psets
(útil para tests y CI sin dependencias pesadas).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


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
            elems[i] = VertidaInfo(a[0].strip("'"), name, cls.title().replace("Ifc", "Ifc"), {})
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


def load_vertidas(path, backend: str = "auto") -> list[VertidaInfo]:
    path = Path(path)
    if backend in ("auto", "ifcopenshell"):
        try:
            return _with_ifcopenshell(path)
        except ImportError:
            if backend == "ifcopenshell":
                raise
    return _with_step_text(path)
