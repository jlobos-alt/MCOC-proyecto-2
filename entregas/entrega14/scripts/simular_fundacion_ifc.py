"""Pipeline completo: IFC -> voxeles -> vertidas -> solver -> resultados y vista 3D (E08).

La secuencia NO esta en el solver: sale del IFC y se puede cambiar por comando, sin tocar
el codigo ni el IFC. Si hay cambios, tambien corre el caso base y compara.

Los parametros termicos de datos/fundacion_ifc.yaml son PROVISORIOS (hidratacion sin
calibrar, clima generico): esto prueba la cadena, no concluye sobre el plan.

Uso:
    python scripts/simular_fundacion_ifc.py                       # caso base del IFC, dx = 0.25 m
    python scripts/simular_fundacion_ifc.py --dx 0.5              # otra malla; imprime el error de volumen
    python scripts/simular_fundacion_ifc.py --inicio 2=12         # la vertida 2 parte a las 12 h
    python scripts/simular_fundacion_ifc.py --tcol 3=12           # la vertida 3 se coloca a 12 C
    python scripts/simular_fundacion_ifc.py --intervalo 8         # una vertida cada 8 h
    python scripts/simular_fundacion_ifc.py --visor               # abre la ventana 3D
    python scripts/simular_fundacion_ifc.py --t 30 --ocultar 5    # imagen 3D a las 30 h, sin la vertida 5

Salidas en results/e08/<caso>/: corrida.json, series.csv, series_fundacion.png,
activacion_cortes.png, vista_3d.png, comparacion.png (si hay cambios) y vti/ (ParaView).
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan import (  # noqa: E402
    aplicar_cambios, build_model, dz_que_calza, evaluar_criterios, extraer_solidos, load_plan,
    plan_desde_solidos, revisar_secuencia, solve, voxelizar,
)
from mcplan import visualization as vis  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _par(texto: str) -> tuple[int, float]:
    """Lee 'vertida=valor', por ejemplo 2=12."""
    try:
        vertida, valor = texto.split("=")
        return int(vertida), float(valor)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Se esperaba vertida=valor, por ejemplo 2=12; se recibio {texto!r}")


@dataclass
class Corrida:
    solidos: list
    plan: object
    vox: object
    modelo: object
    r: object
    veredicto: object


def correr(solidos, plantilla, dx, dz, duracion, campo_cada_h) -> Corrida:
    plan = plan_desde_solidos(plantilla, solidos, dx)
    vox = voxelizar(solidos, dx=dx, dz=dz)
    modelo = build_model(plan, voxeles=vox)
    salida_h = plan.simulacion.intervalo_salida_h
    instantes = np.arange(0.0, duracion + 1e-9, campo_cada_h)
    r = solve(modelo, duracion_h=duracion, intervalo_salida_h=salida_h,
              factor_estabilidad=plan.simulacion.factor_estabilidad, instantes_campo_h=instantes)
    return Corrida(solidos, plan, vox, modelo, r, evaluar_criterios(r, plan.criterios))


def _etiqueta(args) -> str:
    partes = []
    if args.intervalo is not None:
        partes.append(f"intervalo{args.intervalo:g}")
    partes += [f"inicio{v}={h:g}" for v, h in args.inicio]
    partes += [f"tcol{v}={t:g}" for v, t in args.tcol]
    if args.sin_madurez:
        partes.append("sin_madurez")
    nombre = "_".join(partes) or "base"
    return f"{nombre}_dx{args.dx:g}" + (f"_dz{args.dz:g}" if args.dz else "")


def _commit() -> str:
    salida = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return salida.stdout.strip() or "desconocido"


def _resumen(c: Corrida) -> dict:
    t_max, delta = c.veredicto.criterios
    return {"T_max_C": round(t_max.valor, 3), "T_max_h": t_max.instante_h,
            "delta_T_C": round(delta.valor, 3), "delta_T_h": delta.instante_h}


def guardar_datos(c: Corrida, args, cambios: dict, carpeta: Path) -> None:
    g = c.vox.grid
    datos = {
        "ifc": str(args.ifc.name),
        "commit_base": _commit(),
        "cambios_por_comando": cambios,
        "dx_m": g.dx, "dz_m": g.dz, "dt_s": c.r.dt_s,
        "celdas_activas": int(c.vox.mask.sum()),
        "error_volumen_total": c.vox.error_volumen(),
        "vertidas": [
            {"id": s.vertida_id, "nombre": s.nombre, "inicio_h": s.inicio_h,
             "T_colocacion_C": s.temperatura_colocacion_C,
             "V_geom_m3": round(s.volumen, 3), "V_voxel_m3": round(c.vox.volumen_voxel(s.vertida_id), 3),
             "error_volumen": round(c.vox.error_volumen(s.vertida_id), 5)}
            for s in c.solidos
        ],
        "avisos_secuencia": revisar_secuencia(c.solidos),
        "resultado": _resumen(c),
        "aviso": "Parametros termicos provisorios: prueba la cadena, no concluye sobre el plan.",
    }
    (carpeta / "corrida.json").write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(carpeta / "series.csv", "w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(["t_h", "T_max_C", "T_media_C", "T_min_superficie_C", "delta_T_C"])
        for fila in zip(c.r.time_h, c.r.T_max_global, c.r.T_mean, c.r.T_min_surface, c.r.delta_T):
            w.writerow([f"{x:.3f}" for x in fila])


def figura_series(c: Corrida, carpeta: Path) -> None:
    r, crit = c.r, c.plan.criterios
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
    a1.plot(r.time_h, r.T_max_global, label="T máx hormigón", color="#e76f51")
    a1.plot(r.time_h, r.T_mean, label="T media activa", color="#2a9d8f")
    a1.plot(r.time_h, r.T_min_surface, label="T mín superficie final", color="#264653")
    a1.axhline(crit.T_max_C, ls="--", color="#8a8a8a", lw=1, label="70 °C")
    a2.plot(r.time_h, r.delta_T, color="#264653")
    a2.axhline(crit.delta_T_max_C, ls="--", color="#8a8a8a", lw=1, label="20 °C")
    for a in (a1, a2):
        for s in c.solidos:
            if s.inicio_h > 0:
                a.axvline(s.inicio_h, color="#cccccc", lw=0.8, zorder=0)
        a.set_xlabel("t [h] (líneas grises: entra una vertida)")
        a.grid(alpha=0.3)
    a1.set(ylabel="T [°C]", title="Temperaturas (parámetros provisorios)", ylim=(10, 85))
    a1.legend(fontsize=9, loc="upper center", ncol=2)
    a2.set(ylabel="ΔT [°C]", title="Diferencial núcleo–superficie")
    a2.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(carpeta / "series_fundacion.png", dpi=150)
    plt.close(fig)


def figura_activacion(c: Corrida, carpeta: Path) -> None:
    """Cortes en y = 0, en instantes elegidos segun las horas de inicio de este caso."""
    g = c.vox.grid
    _, y, _ = g.centers()
    j = int(np.argmin(np.abs(y)))
    extent = (g.x0, g.x0 + g.nx * g.dx, g.z0, g.z0 + g.nz * g.dz)
    tiempos = sorted(c.r.campos)
    deseados = [s.inicio_h + 3.0 for s in c.solidos] + [tiempos[-1]]
    instantes = [min(tiempos, key=lambda t: abs(t - d)) for d in deseados]
    fig, ejes = plt.subplots(2, 3, figsize=(14, 5.4), sharex=True, sharey=True)
    for a, t in zip(ejes.ravel(), instantes):
        T = c.r.campos[t]
        im = a.imshow(T[:, j, :].T, origin="lower", extent=extent, cmap="inferno", vmin=10, vmax=65)
        a.set_title(f"t = {t:.0f} h · {int(np.isfinite(T).sum())} celdas activas", fontsize=10)
        a.set_facecolor("#e8e8e8")
    fig.supxlabel("x [m]")
    fig.supylabel("z [m]")
    fig.colorbar(im, ax=ejes, fraction=0.02, pad=0.02, label="T [°C] (gris: aún sin hormigón)")
    fig.savefig(carpeta / "activacion_cortes.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def figura_comparacion(base: Corrida, nueva: Corrida, etiqueta: str, carpeta: Path) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
    for c, nombre, color in ((base, "caso base", "#264653"), (nueva, etiqueta, "#e76f51")):
        a1.plot(c.r.time_h, c.r.T_max_global, color=color, label=nombre)
        a2.plot(c.r.time_h, c.r.delta_T, color=color, label=nombre)
    a1.axhline(70.0, ls="--", color="#8a8a8a", lw=1, label="70 °C")
    a2.axhline(20.0, ls="--", color="#8a8a8a", lw=1, label="20 °C")
    a1.set(xlabel="t [h]", ylabel="T máx [°C]", title="Temperatura máxima")
    a2.set(xlabel="t [h]", ylabel="ΔT [°C]", title="Diferencial núcleo–superficie")
    for a in (a1, a2):
        a.grid(alpha=0.3)
        a.legend(fontsize=9)
    fig.suptitle("Efecto del cambio (parámetros provisorios)")
    fig.tight_layout()
    fig.savefig(carpeta / "comparacion.png", dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ifc", type=Path, default=ROOT / "geometry" / "foundation.ifc")
    ap.add_argument("--plantilla", type=Path, default=ROOT / "datos" / "fundacion_ifc.yaml")
    ap.add_argument("--dx", type=float, default=0.25)
    ap.add_argument("--dz", type=float, default=None, help="por defecto, el que calza con las interfaces")
    ap.add_argument("--inicio", type=_par, nargs="*", default=[], metavar="V=H", help="hora de inicio por vertida")
    ap.add_argument("--tcol", type=_par, nargs="*", default=[], metavar="V=C", help="T de colocacion por vertida")
    ap.add_argument("--intervalo", type=float, default=None, help="horas entre vertidas consecutivas")
    ap.add_argument("--duracion-h", type=float, default=None)
    ap.add_argument("--sin-madurez", action="store_true", help="hidratacion sin efecto de la temperatura")
    ap.add_argument("--campo-cada-h", type=float, default=3.0, help="cada cuanto se guarda el campo 3D")
    ap.add_argument("--vti-cada-h", type=float, default=24.0, help="cada cuanto se exporta a .vti (0: nunca)")
    ap.add_argument("--visor", action="store_true", help="abrir la ventana 3D interactiva")
    ap.add_argument("--t", type=float, default=None, help="instante de la imagen 3D [h]")
    ap.add_argument("--ocultar", type=int, nargs="*", default=[], metavar="V", help="vertidas a ocultar en 3D")
    ap.add_argument("--corte", action="store_true", help="imagen 3D cortada en y = 0")
    ap.add_argument("--sin-comparar", action="store_true", help="no correr el caso base para comparar")
    ap.add_argument("--salida", type=Path, default=None)
    args = ap.parse_args()
    if args.campo_cada_h <= 0 or abs(args.campo_cada_h - round(args.campo_cada_h)) > 1e-9:
        ap.error("--campo-cada-h debe ser un numero entero de horas")
    if args.visor and not vis.disponible():
        ap.error("--visor requiere PyVista. Instalalo con: python -m pip install pyvista")

    carpeta = args.salida or ROOT / "results" / "e08" / _etiqueta(args)
    carpeta.mkdir(parents=True, exist_ok=True)

    base = extraer_solidos(args.ifc)
    plantilla = load_plan(str(args.plantilla))
    if args.sin_madurez:
        plantilla.hidratacion.madurez = False
    solidos = aplicar_cambios(base, inicio=dict(args.inicio), tcol=dict(args.tcol), intervalo_h=args.intervalo)
    cambios = {"inicio_h": dict(args.inicio), "T_colocacion_C": dict(args.tcol), "intervalo_h": args.intervalo}
    hay_cambios = bool(args.inicio or args.tcol or args.intervalo is not None)

    duracion = args.duracion_h or plantilla.simulacion.duracion_h
    dz = args.dz or dz_que_calza(solidos, args.dx)
    c = correr(solidos, plantilla, args.dx, dz, duracion, args.campo_cada_h)

    print(f"IFC: {args.ifc.name}  (la secuencia sale de aqui; el solver no la conoce)")
    print(f"{'Vertida':<12}{'Inicio [h]':>11}{'T col [°C]':>12}{'V IFC [m3]':>12}{'V voxel [m3]':>14}{'e_V':>8}")
    for s, s0 in zip(solidos, base):
        marca = " <- cambiada" if (s.inicio_h != s0.inicio_h
                                   or s.temperatura_colocacion_C != s0.temperatura_colocacion_C) else ""
        print(f"{s.nombre:<12}{s.inicio_h:>11.1f}{s.temperatura_colocacion_C:>12.1f}{s.volumen:>12.2f}"
              f"{c.vox.volumen_voxel(s.vertida_id):>14.2f}{100 * c.vox.error_volumen(s.vertida_id):>7.2f}%{marca}")
    for aviso in revisar_secuencia(solidos):
        print(f"AVISO: {aviso}")
    print(f"Malla: dx = {args.dx:g} m, dz = {dz:g} m, {int(c.vox.mask.sum())} celdas activas, "
          f"error de volumen total = {100 * c.vox.error_volumen():.2f} %")
    print(f"dt = {c.r.dt_s:.0f} s, pasos = {c.r.metadata['pasos']}")
    print(c.veredicto.resumen())
    print("(parametros provisorios: resultado para probar la cadena, no para concluir)")

    guardar_datos(c, args, cambios, carpeta)
    figura_series(c, carpeta)
    figura_activacion(c, carpeta)

    if hay_cambios and not args.sin_comparar:
        ref = correr(base, plantilla, args.dx, dz_que_calza(base, args.dx) if not args.dz else args.dz,
                     duracion, args.campo_cada_h)
        figura_comparacion(ref, c, _etiqueta(args), carpeta)
        a, b = _resumen(ref), _resumen(c)
        print("\nEfecto del cambio contra el caso base:")
        print(f"  T máx: {a['T_max_C']:.2f} °C a las {a['T_max_h']:.0f} h  ->  {b['T_max_C']:.2f} °C a las {b['T_max_h']:.0f} h")
        print(f"  ΔT   : {a['delta_T_C']:.2f} °C a las {a['delta_T_h']:.0f} h  ->  {b['delta_T_C']:.2f} °C a las {b['delta_T_h']:.0f} h")

    if not vis.disponible():
        print("\nPyVista no esta instalado: se omiten la vista 3D y los .vti. "
              "Instalalo con: python -m pip install pyvista")
        print(f"Resultados en {carpeta}")
        return

    if args.vti_cada_h > 0:
        paso = max(1, int(round(args.vti_cada_h / args.campo_cada_h)))
        instantes = sorted(c.r.campos)[::paso]
        vis.guardar_serie(carpeta / "vti", c.vox.grid, c.vox.vertida_id, {t: c.r.campos[t] for t in instantes})

    ultimo = max(s.inicio_h for s in solidos)
    visor = vis.VisorVertidas(c.vox.grid, c.vox.vertida_id, c.r.campos, off_screen=not args.visor)
    visor.fijar_tiempo(args.t if args.t is not None else min(ultimo + 12.0, duracion))
    for v in args.ocultar:
        visor.alternar(v, False)
    visor.fijar_corte(args.corte)
    if args.visor:
        print("\nVentana 3D: casillas o teclas 1-5 ocultan/muestran vertidas, x corta en y = 0, la barra cambia t.")
        print(f"Resultados en {carpeta}")
        visor.abrir()
    else:
        visor.captura(carpeta / "vista_3d.png")
        visor.cerrar()
        print(f"Resultados en {carpeta}")


if __name__ == "__main__":
    main()
