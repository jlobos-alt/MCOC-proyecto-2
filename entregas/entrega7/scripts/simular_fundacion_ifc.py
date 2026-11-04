"""E07: corre la cadena IFC -> voxeles -> vertidas -> solver y muestra la activacion.

Los parametros termicos de datos/fundacion_ifc.yaml son PROVISORIOS (hidratacion sin
calibrar, clima generico): esto prueba que la cadena funciona, no concluye sobre el plan.

Uso:
    python scripts/simular_fundacion_ifc.py                 # dx = 0.25 m, dz calzado, 14 dias
    python scripts/simular_fundacion_ifc.py --dz 0.25       # dz sin calzar a las interfaces
    python scripts/simular_fundacion_ifc.py --dx 0.5 --duracion-h 168
    python scripts/simular_fundacion_ifc.py --sin-madurez

Salidas en results/e07/: activacion_cortes.png, series_fundacion.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan import (  # noqa: E402
    build_model, dz_que_calza, evaluar_criterios, extraer_solidos, load_plan, plan_desde_solidos, solve,
    voxelizar,
)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ifc", type=Path, default=ROOT / "geometry" / "foundation.ifc")
    ap.add_argument("--plantilla", type=Path, default=ROOT / "datos" / "fundacion_ifc.yaml")
    ap.add_argument("--dx", type=float, default=0.25)
    ap.add_argument("--dz", type=float, default=None, help="por defecto, el que calza con las interfaces")
    ap.add_argument("--duracion-h", type=float, default=None)
    ap.add_argument("--sin-madurez", action="store_true", help="hidratacion sin efecto de la temperatura")
    ap.add_argument("--salida", type=Path, default=ROOT / "results" / "e07")
    args = ap.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)

    solidos = extraer_solidos(args.ifc)
    plantilla = load_plan(str(args.plantilla))
    if args.sin_madurez:
        plantilla.hidratacion.madurez = False
    plan = plan_desde_solidos(plantilla, solidos, args.dx)
    duracion = args.duracion_h or plan.simulacion.duracion_h

    dz = args.dz or dz_que_calza(solidos, args.dx)
    vox = voxelizar(solidos, dx=args.dx, dz=dz)
    modelo = build_model(plan, voxeles=vox)
    print(f"Grilla {vox.grid.shape}, {int(vox.mask.sum())} celdas activas, dx = {args.dx} m, dz = {dz:g} m, "
          f"e_V = {100 * vox.error_volumen():.2f} %")
    print("e_V por vertida: " + ", ".join(f"{s.vertida_id}: {100 * vox.error_volumen(s.vertida_id):.1f} %"
                                          for s in solidos))
    print(f"Nucleo: {int(modelo.is_core.sum())} celdas · superficie: {int(modelo.is_surface.sum())} celdas")
    print("Inicio de vertidas [h]: " + ", ".join(f"{s.vertida_id}: {s.inicio_h:.0f}" for s in solidos))

    r = solve(modelo, duracion_h=duracion, intervalo_salida_h=plan.simulacion.intervalo_salida_h,
              factor_estabilidad=plan.simulacion.factor_estabilidad)
    print(f"dt = {r.dt_s:.0f} s, pasos = {r.metadata['pasos']}")
    print(evaluar_criterios(r, plan.criterios).resumen())
    print("(parametros provisorios: resultado para probar la cadena, no para concluir)")

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
    a1.plot(r.time_h, r.T_max_global, label="T máx hormigón", color="#e76f51")
    a1.plot(r.time_h, r.T_mean, label="T media activa", color="#2a9d8f")
    a1.plot(r.time_h, r.T_min_surface, label="T mín superficie final", color="#264653")
    a1.axhline(plan.criterios.T_max_C, ls="--", color="#8a8a8a", lw=1, label="70 °C")
    a2.plot(r.time_h, r.delta_T, color="#264653")
    a2.axhline(plan.criterios.delta_T_max_C, ls="--", color="#8a8a8a", lw=1, label="20 °C")
    for a in (a1, a2):
        for s in solidos[1:]:
            a.axvline(s.inicio_h, color="#cccccc", lw=0.8, zorder=0)
        a.set_xlabel("t [h] (líneas grises: entra una vertida)")
        a.grid(alpha=0.3)
        a.legend(fontsize=9)
    a1.set(ylabel="T [°C]", title="Temperaturas (parámetros provisorios)", ylim=(10, 85))
    a1.legend(fontsize=9, loc="upper center", ncol=2)
    a2.set(ylabel="ΔT [°C]", title="Diferencial núcleo–superficie")
    fig.tight_layout()
    fig.savefig(args.salida / "series_fundacion.png", dpi=150)
    plt.close(fig)

    # Cortes: se re-simula hasta cada instante para ver quien esta activo y a que T
    instantes = [t for t in (12.0, 36.0, 60.0, 84.0, 108.0, duracion) if t <= duracion]
    g = vox.grid
    _, y, _ = g.centers()
    j = int(np.argmin(np.abs(y)))
    extent = (g.x0, g.x0 + g.nx * g.dx, g.z0, g.z0 + g.nz * g.dz)
    fig, ejes = plt.subplots(2, 3, figsize=(14, 5.4), sharex=True, sharey=True)
    for a, t in zip(ejes.ravel(), instantes):
        rt = solve(modelo, duracion_h=t, intervalo_salida_h=plan.simulacion.intervalo_salida_h,
                   factor_estabilidad=plan.simulacion.factor_estabilidad)
        im = a.imshow(rt.T_final[:, j, :].T, origin="lower", extent=extent, cmap="inferno", vmin=10, vmax=65)
        a.set_title(f"t = {t:.0f} h · {int(rt.active_final.sum())} celdas activas", fontsize=10)
        a.set_facecolor("#e8e8e8")
    fig.supxlabel("x [m]")
    fig.supylabel("z [m]")
    fig.colorbar(im, ax=ejes, fraction=0.02, pad=0.02, label="T [°C] (gris: aún sin hormigón)")
    fig.savefig(args.salida / "activacion_cortes.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Resultados en {args.salida}")


if __name__ == "__main__":
    main()
