"""Round-trip IFC: modificacion de propiedades y verificacion desde Python (E02).

Demuestra el flujo minimo  Bonsai -> IFC -> Python  que pide la actividad:

    1. leer el IFC e identificar los objetos (vertidas),
    2. modificar una propiedad (p.ej. TemperaturaColocacion_C),
    3. guardar el IFC modificado,
    4. re-leerlo desde Python y comprobar que el cambio se detecto.

La modificacion se hace con IfcOpenShell (camino oficial del curso), el mismo
motor que usa Bonsai. El script escribe en un archivo de SALIDA, para no tocar
el `geometry/foundation.ifc` original.

Round-trip REAL con Bonsai (lo que pide el ayudante):
    python scripts/roundtrip_ifc.py --antes      # 1) foto del IFC antes de editar
    ... abrir geometry/foundation.ifc en Bonsai, cambiar una propiedad o mover
        una vertida, y guardar (File > Save IFC Project) ...
    python scripts/roundtrip_ifc.py --despues    # 2) Python muestra qué cambió
    python scripts/roundtrip_ifc.py --comparar A.ifc B.ifc   # comparar dos archivos

Uso (modificación por script, sin Bonsai):
    python scripts/roundtrip_ifc.py --list
    python scripts/roundtrip_ifc.py --set TemperaturaColocacion_C=21.5 --vertida Vertida_03
    python scripts/roundtrip_ifc.py --set TemperaturaColocacion_C=21.5 --vertida Vertida_03 -o geometry/foundation_editado.ifc
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan.bim import load_vertidas  # noqa: E402
from mcplan.ifc_diff import compare, load_snapshot, save_snapshot, snapshot  # noqa: E402

FOTO = ROOT / "resultados" / "foto_ifc_antes.json"

PSET = "Pset_HormigonMasivo"


def _load_model(path: Path):
    import ifcopenshell
    return ifcopenshell.open(str(path))


def _find_element(model, name: str):
    for el in model.by_type("IfcElement"):
        if el.Name == name:
            return el
    raise SystemExit(f"No se encontro el objeto '{name}' en el IFC")


def _get_property(model, element, prop_name: str):
    import ifcopenshell.util.element as ue
    psets = ue.get_psets(element)
    return psets.get(PSET, {}).get(prop_name)


def _set_property(model, element, prop_name: str, value):
    import ifcopenshell.api
    import ifcopenshell.util.element as ue

    psets = ue.get_psets(element)
    if PSET not in psets:
        raise SystemExit(f"El objeto no tiene el Pset '{PSET}'")
    pset = model.by_id(psets[PSET]["id"])
    existed = any(p.Name == prop_name for p in pset.HasProperties)
    ifcopenshell.api.run("pset.edit_pset", model, pset=pset, properties={prop_name: value})
    return "actualizada" if existed else "agregada"


def _coerce(value: str):
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def cmd_list(path: Path):
    print(f"Objetos identificables en {path}:")
    print(f"{'#':>2}  {'Vertida':<12}{'GUID':<25}{'Clase':<12}{'Tcol[°C]':>9}")
    for i, v in enumerate(load_vertidas(path), start=1):
        tcol = v.properties.get("TemperaturaColocacion_C", float("nan"))
        print(f"{i:>2}  {v.name:<12}{v.guid:<25}{v.ifc_class:<12}{tcol:>9.1f}")
    print(f"\nTotal: {len(load_vertidas(path))} objetos (>=3 requeridos por la actividad)")


def cmd_set(path: Path, vertida: str, prop: str, raw_value: str, out: Path):
    model = _load_model(path)
    el = _find_element(model, vertida)
    before = _get_property(model, el, prop)
    value = _coerce(raw_value)
    status = _set_property(model, el, prop, value)
    model.write(str(out))
    print(f"[1] Leido      : {path}")
    print(f"[2] Objeto     : {vertida} (GUID {el.GlobalId})")
    print(f"[3] Propiedad  : {PSET}.{prop}  ({status})")
    print(f"[4] Antes  -> Despues : {before!r} -> {value!r}")
    print(f"[5] Guardado   : {out}")

    # Re-leer con el MISMO lector que usa el resto del proyecto
    after = None
    for v in load_vertidas(out):
        if v.name == vertida:
            after = v.properties.get(prop)
    print(f"[6] Verificacion (Python detecta el cambio): {after!r}")
    if after == value:
        print("    OK: el round-trip cerro correctamente.")
    else:
        print(f"    ERROR: se esperaba {value!r} y se leyo {after!r}")


def _print_snapshot(snap):
    print(f"{'Vertida':<12}{'GUID':<25}{'Clase':<12}{'z [m]':>13}{'V [m3]':>10}  ubicación [m]")
    for o in snap["objetos"].values():
        z = f"{o['z_min_m']:.2f}–{o['z_max_m']:.2f}" if o["z_min_m"] is not None else "-"
        v = f"{o['volumen_m3']:.2f}" if o["volumen_m3"] is not None else "-"
        loc = ", ".join(f"{c:.2f}" for c in o["ubicacion_m"])
        print(f"{o['name']:<12}{o['guid']:<25}{o['clase']:<12}{z:>13}{v:>10}  ({loc})")


def cmd_antes(path: Path):
    snap = snapshot(path)
    save_snapshot(snap, FOTO)
    print(f"Foto ANTES de editar: {path}")
    _print_snapshot(snap)
    print(f"\nGuardada en {FOTO}")
    print("Ahora abre el IFC en Bonsai, cambia una propiedad o mueve una vertida,")
    print("guarda (File > Save IFC Project) y corre:  python scripts/roundtrip_ifc.py --despues")


def _report(antes, despues, ref_label, new_label):
    cambios = compare(antes, despues)
    print(f"Referencia : {ref_label}")
    print(f"Actual     : {new_label}\n")
    _print_snapshot(despues)
    print()
    if cambios:
        print(f"Python detectó {len(cambios)} cambio(s):")
        for c in cambios:
            print(f"  * {c}")
        same = set(antes["objetos"]) & set(despues["objetos"])
        print(f"\nIdentidad BIM: {len(same)} objetos conservan su GUID.")
    else:
        print("Sin cambios: el IFC es igual a la referencia (¿guardaste en Bonsai?).")
    return cambios


def cmd_despues(path: Path):
    if FOTO.exists():
        antes, ref = load_snapshot(FOTO), f"foto guardada con --antes ({FOTO.name})"
    else:
        base = ROOT / "geometry" / "foundation_base.ifc"
        antes, ref = snapshot(base), f"{base.name} (no había foto --antes)"
    _report(antes, snapshot(path), ref, str(path))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ifc", type=Path, default=ROOT / "geometry" / "foundation.ifc")
    ap.add_argument("--list", action="store_true", help="solo listar objetos y salir")
    ap.add_argument("--antes", action="store_true", help="guardar foto del IFC antes de editarlo en Bonsai")
    ap.add_argument("--despues", action="store_true", help="comparar el IFC actual con la foto --antes")
    ap.add_argument("--comparar", nargs=2, type=Path, metavar=("A", "B"), help="comparar dos archivos IFC")
    ap.add_argument("--set", nargs=2, metavar=("PROPIEDAD", "VALOR"),
                    help="modificar una propiedad, p.ej. --set TemperaturaColocacion_C 21.5")
    ap.add_argument("--vertida", default="Vertida_01", help="nombre del objeto a modificar")
    ap.add_argument("-o", "--out", type=Path,
                    default=ROOT / "geometry" / "foundation_editado.ifc")
    args = ap.parse_args()

    if args.comparar:
        a, b = args.comparar
        _report(snapshot(a), snapshot(b), str(a), str(b))
        return
    if not args.ifc.exists():
        raise SystemExit(f"No existe el IFC: {args.ifc}")
    if args.antes:
        cmd_antes(args.ifc)
        return
    if args.despues:
        cmd_despues(args.ifc)
        return
    if args.list or not args.set:
        cmd_list(args.ifc)
        return
    cmd_set(args.ifc, args.vertida, args.set[0], args.set[1], args.out)


if __name__ == "__main__":
    main()
