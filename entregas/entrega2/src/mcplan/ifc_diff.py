"""
Round-trip IFC: "foto" de un IFC y comparación antes/después (E02).

Sirve para demostrar que Python detecta lo que se cambió en Bonsai:

    foto_antes = snapshot("foundation.ifc")     # antes de editar en Bonsai
    ... editar en Bonsai y guardar ...
    cambios = compare(foto_antes, snapshot("foundation.ifc"))

Para cada objeto identificable (por nombre y GUID) registra:
  - propiedades de sus Psets,
  - ubicación (suma de los IfcLocalPlacement, sin rotaciones),
  - rango en z y volumen calculados de la geometría IFC,
  - una huella (hash) de su geometría y ubicación completas.

Lee el texto STEP directamente: no necesita IfcOpenShell. Los números de
entidad (#123) se resuelven recursivamente, así que renumerar el archivo al
guardar no cuenta como cambio.

Geometrías con volumen calculado: IfcExtrudedAreaSolid (perfil poligonal,
IfcIndexedPolyCurve, círculo o rectángulo), IfcFacetedBrep,
IfcTriangulatedFaceSet e IfcPolygonalFaceSet.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

_ENT = re.compile(r"^#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*)\)\s*;\s*$")
_NUM = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")
ELEMENT_CLASSES = {
    "IFCFOOTING": "IfcFooting", "IFCSLAB": "IfcSlab", "IFCWALL": "IfcWall",
    "IFCBEAM": "IfcBeam", "IFCCOLUMN": "IfcColumn", "IFCPILE": "IfcPile",
    "IFCBUILDINGELEMENTPROXY": "IfcBuildingElementProxy", "IFCMEMBER": "IfcMember",
    "IFCPLATE": "IfcPlate", "IFCCOVERING": "IfcCovering",
}


# ---------------------------------------------------------------- parser STEP
def _split(s: str) -> list[str]:
    """Divide los argumentos de nivel superior respetando paréntesis y strings."""
    out, depth, cur, q = [], 0, [], False
    for ch in s:
        if ch == "'":
            q = not q
        if not q:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                out.append("".join(cur).strip())
                cur = []
                continue
        cur.append(ch)
    out.append("".join(cur).strip())
    return out


def _read_entities(path) -> dict[int, tuple[str, list[str]]]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    data = text.split("DATA;", 1)[-1]
    ents: dict[int, tuple[str, list[str]]] = {}
    buf = ""
    for line in data.splitlines():
        buf += line.strip()
        if not buf.endswith(";"):
            continue                      # entidad que ocupa varias líneas
        m = _ENT.match(buf)
        if m:
            ents[int(m.group(1))] = (m.group(2).upper(), _split(m.group(3)))
        buf = ""
    return ents


def _ref(s: str) -> int:
    return int(s.strip().lstrip("#"))


def _items(s: str) -> list[str]:
    s = s.strip()
    if s.startswith("(") and s.endswith(")"):
        inner = s[1:-1].strip()
        return _split(inner) if inner else []
    return [s]


def _num(s: str) -> float:
    s = s.strip()
    m = re.match(r"^IFC[A-Z]+\((.*)\)$", s)
    if m:
        s = m.group(1)
    return float(s)


def _value(s: str):
    s = s.strip()
    m = re.match(r"^IFC[A-Z]+\((.*)\)$", s)
    if m:
        s = m.group(1).strip()
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1].replace("''", "'")
    if s in ("$", "*"):
        return None
    if s in (".T.", ".F."):
        return s == ".T."
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


# --------------------------------------------------------- huella canónica
def _canon(ents, s: str, depth: int = 0) -> str:
    s = s.strip()
    if depth > 60:
        return "…"
    if s.startswith("#"):
        cls, args = ents.get(_ref(s), ("?", []))
        return cls + "(" + ",".join(_canon(ents, a, depth + 1) for a in args) + ")"
    if s.startswith("(") and s.endswith(")"):
        return "(" + ",".join(_canon(ents, a, depth + 1) for a in _items(s)) + ")"
    m = re.match(r"^(IFC[A-Z]+)\((.*)\)$", s)
    if m:
        return m.group(1) + "(" + _canon(ents, m.group(2), depth + 1) + ")"
    if _NUM.match(s):
        v = round(float(s), 6)
        return repr(0.0 if v == 0 else v)
    return s


# ------------------------------------------------------------- ubicación
def _point(ents, ref: str) -> tuple[float, float, float]:
    cls, args = ents[_ref(ref)]
    c = [float(v) for v in _items(args[0])]
    return (c + [0.0, 0.0, 0.0])[:3]


def _placement_offset(ents, ref: str) -> tuple[float, float, float]:
    """Suma las traslaciones de la cadena de IfcLocalPlacement (ignora rotaciones)."""
    off = [0.0, 0.0, 0.0]
    seen = 0
    while ref and ref.startswith("#") and seen < 50:
        cls, args = ents[_ref(ref)]
        if cls != "IFCLOCALPLACEMENT":
            break
        rel = args[1]
        if rel.startswith("#"):
            acls, aargs = ents[_ref(rel)]
            if aargs and aargs[0].startswith("#"):
                p = _point(ents, aargs[0])
                off = [o + v for o, v in zip(off, p)]
        ref = args[0]
        seen += 1
    return tuple(off)


# --------------------------------------------------------------- geometría
def _poly_area(pts2d) -> float:
    a = 0.0
    n = len(pts2d)
    for i in range(n):
        x1, y1 = pts2d[i][:2]
        x2, y2 = pts2d[(i + 1) % n][:2]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def _pointlist(ents, ref: str):
    cls, args = ents[_ref(ref)]
    return [[float(v) for v in _items(p)] for p in _items(args[0])]


def _profile_area(ents, ref: str):
    cls, args = ents[_ref(ref)]
    if cls == "IFCCIRCLEPROFILEDEF":
        return math.pi * float(args[3]) ** 2
    if cls == "IFCRECTANGLEPROFILEDEF":
        return float(args[3]) * float(args[4])
    if cls in ("IFCARBITRARYCLOSEDPROFILEDEF", "IFCARBITRARYPROFILEDEFWITHVOIDS"):
        ccls, cargs = ents[_ref(args[2])]
        if ccls == "IFCPOLYLINE":
            pts = [_point(ents, p)[:2] for p in _items(cargs[0])]
        elif ccls == "IFCINDEXEDPOLYCURVE":
            pts = [p[:2] for p in _pointlist(ents, cargs[0])]
        else:
            return None
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts = pts[:-1]
        area = _poly_area(pts)
        if cls == "IFCARBITRARYPROFILEDEFWITHVOIDS":
            for inner in _items(args[3]):
                icls, iargs = ents[_ref(inner)]
                if icls == "IFCPOLYLINE":
                    ip = [_point(ents, p)[:2] for p in _items(iargs[0])]
                    area -= _poly_area(ip[:-1] if ip[0] == ip[-1] else ip)
        return area
    return None


def _mesh_volume(tris) -> float:
    v = 0.0
    for a, b, c in tris:
        v += (a[0] * (b[1] * c[2] - b[2] * c[1])
              - a[1] * (b[0] * c[2] - b[2] * c[0])
              + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return abs(v) / 6.0


def _fan(poly):
    return [(poly[0], poly[i], poly[i + 1]) for i in range(1, len(poly) - 1)]


def _item_geometry(ents, ref: str):
    """Devuelve (volumen, zmin, zmax) en coordenadas del objeto, o (None, zmin, zmax)."""
    cls, args = ents[_ref(ref)]
    if cls == "IFCEXTRUDEDAREASOLID":
        area = _profile_area(ents, args[0])
        z0 = 0.0
        if args[1].startswith("#"):
            pcls, pargs = ents[_ref(args[1])]
            if pargs and pargs[0].startswith("#"):
                z0 = _point(ents, pargs[0])[2]
        d = [float(v) for v in _items(ents[_ref(args[2])][1][0])]
        d = (d + [0, 0, 0])[:3]
        norm = math.sqrt(sum(c * c for c in d)) or 1.0
        depth = float(args[3])
        dz = depth * d[2] / norm
        vol = None if area is None else area * depth * abs(d[2]) / norm
        return vol, min(z0, z0 + dz), max(z0, z0 + dz)
    if cls == "IFCFACETEDBREP":
        tris, zs = [], []
        _, sargs = ents[_ref(args[0])]
        for face in _items(sargs[0]):
            _, fargs = ents[_ref(face)]
            for bound in _items(fargs[0]):
                bcls, bargs = ents[_ref(bound)]
                _, largs = ents[_ref(bargs[0])]
                poly = [_point(ents, p) for p in _items(largs[0])]
                if bargs[1].strip() == ".F.":
                    poly = poly[::-1]
                zs += [p[2] for p in poly]
                if bcls == "IFCFACEOUTERBOUND":
                    tris += _fan(poly)
        return _mesh_volume(tris), min(zs), max(zs)
    if cls in ("IFCTRIANGULATEDFACESET", "IFCPOLYGONALFACESET"):
        pts = _pointlist(ents, args[0])
        zs = [p[2] for p in pts]
        tris = []
        if cls == "IFCTRIANGULATEDFACESET":
            for t in _items(args[3]):
                i, j, k = [int(v) - 1 for v in _items(t)]
                tris.append((pts[i], pts[j], pts[k]))
        else:
            for f in _items(args[2]):
                _, fa = ents[_ref(f)]
                idx = [int(v) - 1 for v in _items(fa[0])]
                tris += _fan([pts[i] for i in idx])
        return _mesh_volume(tris), min(zs), max(zs)
    return None, None, None


def _element_geometry(ents, rep_ref: str):
    if not rep_ref.startswith("#"):
        return None, None, None
    _, pargs = ents[_ref(rep_ref)]
    vol, zmin, zmax, ok = 0.0, math.inf, -math.inf, True
    for rep in _items(pargs[2]):
        _, rargs = ents[_ref(rep)]
        ident = _value(rargs[1])
        if ident not in (None, "Body"):
            continue
        for it in _items(rargs[3]):
            v, z0, z1 = _item_geometry(ents, it)
            if v is None:
                ok = False
            else:
                vol += v
            if z0 is not None:
                zmin, zmax = min(zmin, z0), max(zmax, z1)
    if zmin == math.inf:
        zmin = zmax = None
    return (vol if ok else None), zmin, zmax


# --------------------------------------------------------------- snapshot
def snapshot(path) -> dict:
    """Foto de los objetos del IFC: identidad, propiedades, ubicación y geometría."""
    ents = _read_entities(path)
    objs = {}
    for eid, (cls, args) in ents.items():
        if cls not in ELEMENT_CLASSES or len(args) < 7:
            continue
        name = _value(args[2]) or f"#{eid}"
        off = _placement_offset(ents, args[5]) if args[5].startswith("#") else (0.0, 0.0, 0.0)
        vol, zmin, zmax = _element_geometry(ents, args[6])
        geom_txt = _canon(ents, args[5]) + "|" + _canon(ents, args[6])
        objs[eid] = {
            "name": name,
            "guid": _value(args[0]),
            "clase": ELEMENT_CLASSES[cls],
            "ubicacion_m": [round(c, 6) for c in off],
            "volumen_m3": None if vol is None else round(vol, 6),
            "z_min_m": None if zmin is None else round(zmin + off[2], 6),
            "z_max_m": None if zmax is None else round(zmax + off[2], 6),
            "huella_geometria": hashlib.sha1(geom_txt.encode()).hexdigest()[:12],
            "propiedades": {},
        }
    for cls, args in ents.values():
        if cls != "IFCRELDEFINESBYPROPERTIES":
            continue
        pcls, pargs = ents.get(_ref(args[5]), ("", []))
        if pcls != "IFCPROPERTYSET":
            continue
        pset = _value(pargs[2])
        props = {}
        for pid in _items(pargs[4]):
            vcls, vargs = ents.get(_ref(pid), ("", []))
            if vcls == "IFCPROPERTYSINGLEVALUE":
                props[f"{pset}.{_value(vargs[0])}"] = _value(vargs[2])
        for e in _items(args[4]):
            if e.startswith("#") and _ref(e) in objs:
                objs[_ref(e)]["propiedades"].update(props)
    out = {o["guid"]: o for o in objs.values()}
    return {"archivo": str(path), "objetos": dict(sorted(out.items(), key=lambda kv: kv[1]["name"]))}


def save_snapshot(snap: dict, path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")


def load_snapshot(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.4g}"
    if isinstance(v, list):
        return "(" + ", ".join(f"{c:.3f}" for c in v) + ")"
    return repr(v)


def compare(antes: dict, despues: dict) -> list[str]:
    """Lista legible de diferencias entre dos fotos (vacía si no hay cambios)."""
    a, b = antes["objetos"], despues["objetos"]
    cambios = []
    for guid in sorted(set(a) | set(b), key=lambda g: (a.get(g) or b.get(g))["name"]):
        if guid not in b:
            cambios.append(f"{a[guid]['name']}: ELIMINADO (GUID {guid})")
            continue
        if guid not in a:
            cambios.append(f"{b[guid]['name']}: NUEVO objeto (GUID {guid})")
            continue
        oa, ob = a[guid], b[guid]
        n = ob["name"]
        if oa["name"] != ob["name"]:
            cambios.append(f"{oa['name']}: nombre {oa['name']!r} -> {ob['name']!r} (mismo GUID)")
        for k in sorted(set(oa["propiedades"]) | set(ob["propiedades"])):
            va, vb = oa["propiedades"].get(k), ob["propiedades"].get(k)
            if va != vb:
                cambios.append(f"{n}: propiedad {k}: {_fmt(va)} -> {_fmt(vb)}")
        if oa["ubicacion_m"] != ob["ubicacion_m"]:
            cambios.append(f"{n}: ubicación {_fmt(oa['ubicacion_m'])} -> {_fmt(ob['ubicacion_m'])} m")
        for k, label in (("z_min_m", "z mínimo"), ("z_max_m", "z máximo"), ("volumen_m3", "volumen")):
            va, vb = oa[k], ob[k]
            if va is not None and vb is not None and abs(va - vb) > 1e-6:
                unidad = "m³" if k == "volumen_m3" else "m"
                cambios.append(f"{n}: {label} {va:.3f} -> {vb:.3f} {unidad}")
        if oa["huella_geometria"] != ob["huella_geometria"] and not any(
                c.startswith(f"{n}: ubicación") or c.startswith(f"{n}: z ") or c.startswith(f"{n}: volumen")
                for c in cambios):
            cambios.append(f"{n}: la geometría cambió (huella {oa['huella_geometria']} -> {ob['huella_geometria']})")
    return cambios
