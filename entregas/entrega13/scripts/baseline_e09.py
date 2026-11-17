"""E09 - Baseline 3D con hidratacion: geometria del curso, vertidas y clima simple.

Corre el caso de la fundacion del IFC (18 x 18 m, 5 vertidas) y guarda las
evidencias del informe: T_max(t), temperaturas en puntos, cortes 3D, error de
volumen y un resumen en JSON.

Uso (desde entregas/entrega9):
    python scripts/baseline_e09.py
    python scripts/baseline_e09.py --dx 0.5            # malla mas gruesa
    python scripts/baseline_e09.py --duracion-h 168    # una semana

Los parametros de hidratacion y clima son PROVISORIOS y estan declarados en
datos/fundacion_ifc.yaml. Este script no calibra nada: mide el baseline.
"""
from __future__ import annotations

import argparse
import csv
import json
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
    build_model, dz_que_calza, evaluar_criterios, extraer_solidos, load_plan,
    plan_desde_solidos, solve, voxelizar,
)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

K_HORMIGON = 2.22      # W/(m K), Ju & Lei (2019)
H_SUPERFICIE = 12.0    # W/(m2 K), conveccion declarada en el YAML
PROFUNDIDAD_DT_M = 0.025


def _punto(xc, yc, zc, x, y, z):
    return (int(np.argmin(np.abs(xc - x))), int(np.argmin(np.abs(yc - y))),
            int(np.argmin(np.abs(zc - z))))


def _nanmax(valores):
    valores = np.asarray(valores, dtype=float)
    return float(np.nanmax(valores)) if np.isfinite(valores).any() else float("nan")


def _max_finito(serie, tiempos):
    valores = np.asarray(serie, dtype=float)
    validos = np.isfinite(valores)
    if not validos.any():
        return float("nan"), float("nan")
    return float(np.nanmax(valores)), float(tiempos[validos][int(np.nanargmax(valores[validos]))])


def _campo_superficie_25mm(T, act, core3, grid, t_h, ambiente):
    """T del hormigon a 25 mm de la cara superior, por conduccion 1D.

    La primera celda activa esta a dz/2 de la cara. Con resistencia
    R = dz/(2k) + 1/h se obtiene el flujo q y se extrapola:
        T_s = T_c - q dz/(2k);   T_25mm = T_s - q (0.025)/k
    """
    iz = np.where(act.any(axis=2), grid.nz - 1 - np.argmax(act[:, :, ::-1], axis=2), 0)
    top = act.any(axis=2)
    ii, jj = np.indices(top.shape)
    Tc = T[ii, jj, iz]
    R = grid.dz / (2 * K_HORMIGON) + 1.0 / H_SUPERFICIE
    q = (Tc - ambiente) / R
    Ts = Tc - q * grid.dz / (2 * K_HORMIGON)
    T25 = Ts - q * PROFUNDIDAD_DT_M / K_HORMIGON
    T25 = np.where(top, T25, np.nan)
    nucleo = _nanmax(np.where(act & core3, T, np.nan))
    return nucleo + _nanmax(-T25), float(np.nanmin(T25)), Ts, T25


def figura_3d(r, mask3, grid, carpeta, t_h=72.0, paso=2):
    """Vista 3D por voxeles, cortada en y = 0 y coloreada por temperatura."""
    from matplotlib.colors import Normalize

    t = min(r.campos, key=lambda ti: abs(ti - t_h))
    m = mask3[::paso, ::paso, ::paso]
    T = r.campos[t][::paso, ::paso, ::paso]
    j0 = m.shape[1] // 2
    visible = m.copy()
    visible[:, j0:, :] = False
    colores = np.zeros(visible.shape + (4,), dtype=float)
    cmap = plt.get_cmap("inferno")
    norm = Normalize(vmin=10, vmax=65)
    colores[visible] = cmap(norm(np.clip(T[visible], 10, 65)))

    fig = plt.figure(figsize=(9, 7.2))
    ax = fig.add_subplot(projection="3d")
    ax.voxels(visible, facecolors=colores, edgecolor="none", shade=False)
    ax.set_box_aspect((m.shape[0] * grid.dx, m.shape[1] * grid.dy, m.shape[2] * grid.dz))
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.set_zlabel("z [m]")
    ax.set_title(f"Voxeles activos a t = {t:.0f} h (corte en y = 0)")
    ax.view_init(elev=22, azim=-60)
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    fig.colorbar(sm, ax=ax, shrink=0.6, pad=0.08, label="T [°C]")
    fig.tight_layout()
    fig.savefig(carpeta / "e09_vista3d.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ifc", type=Path, default=ROOT / "geometry" / "foundation.ifc")
    ap.add_argument("--plantilla", type=Path, default=ROOT / "datos" / "fundacion_ifc.yaml")
    ap.add_argument("--dx", type=float, default=0.25)
    ap.add_argument("--dz", type=float, default=None)
    ap.add_argument("--duracion-h", type=float, default=None)
    ap.add_argument("--campo-cada-h", type=float, default=3.0)
    ap.add_argument("--salida", type=Path, default=ROOT / "results" / "e09")
    args = ap.parse_args()

    plantilla = load_plan(str(args.plantilla))
    solidos = extraer_solidos(args.ifc)
    dx = args.dx
    dz = args.dz or dz_que_calza(solidos, dx)
    plan = plan_desde_solidos(plantilla, solidos, dx)
    vox = voxelizar(solidos, dx=dx, dz=dz)
    modelo = build_model(plan, voxeles=vox)
    grid = modelo.grid
    mask3 = modelo.mask.reshape(grid.shape)
    core3 = modelo.is_core.reshape(grid.shape)

    duracion = args.duracion_h or plantilla.simulacion.duracion_h
    instantes = np.arange(0.0, duracion + 1e-9, args.campo_cada_h)
    r = solve(modelo, duracion_h=duracion, intervalo_salida_h=plantilla.simulacion.intervalo_salida_h,
              factor_estabilidad=plantilla.simulacion.factor_estabilidad,
              instantes_campo_h=instantes)
    veredicto = evaluar_criterios(r, plan.criterios)

    xc, yc, zc = grid.centers()
    ic = int(np.argmin(np.abs(xc)))
    jc = int(np.argmin(np.abs(yc)))
    t = np.asarray(sorted(r.campos), dtype=float)
    Tmax = np.interp(t, r.time_h, r.T_max_global)
    nucleo = np.interp(t, r.time_h, r.T_max_core)
    superficie = np.interp(t, r.time_h, r.T_min_surface)
    dT_celda = np.interp(t, r.time_h, r.delta_T)
    dT25 = []
    T25_centro = []
    for ti in t:
        T = r.campos[ti]
        act = mask3 & np.isfinite(T)
        d25, _, _, T25 = _campo_superficie_25mm(T, act, core3, grid, ti, float(modelo.ambient(ti)))
        dT25.append(d25)
        T25_centro.append(T25[ic, jc])
    dT25 = np.asarray(dT25)
    T25_centro = np.asarray(T25_centro)

    # Puntos de control: nucleo, superficie superior, base y borde.
    pts = {
        "Nucleo (0.0, 0.0, 2.06 m)": _punto(xc, yc, zc, 0.0, 0.0, 2.06),
        "Superficie superior (0.0, 0.0, 4.26 m)": _punto(xc, yc, zc, 0.0, 0.0, 4.26),
        "Base (0.0, 0.0, 0.14 m)": _punto(xc, yc, zc, 0.0, 0.0, 0.14),
        "Borde lateral (-6.1, 0.0, 2.06 m)": _punto(xc, yc, zc, -6.125, 0.0, 2.06),
    }
    series = {}
    tabla_puntos = []
    for nombre, (i, j, k) in pts.items():
        s = np.array([r.campos[ti][i, j, k] if np.isfinite(r.campos[ti][i, j, k]) else np.nan for ti in t])
        series[nombre] = s
        imax = int(np.nanargmax(s)) if np.isfinite(s).any() else 0
        tabla_puntos.append({"punto": nombre, "T_max_C": round(_nanmax(s), 2),
                             "t_max_h": float(t[imax]), "T_final_C": round(float(s[-1]), 2)})
    series["Superficie a 25 mm (0.0, 0.0)"] = T25_centro
    imax25 = int(np.nanargmax(T25_centro))
    tabla_puntos.append({"punto": "Superficie a 25 mm (0.0, 0.0)", "T_max_C": round(_nanmax(T25_centro), 2),
                         "t_max_h": float(t[imax25]), "T_final_C": round(float(T25_centro[-1]), 2)})

    carpeta = args.salida
    carpeta.mkdir(parents=True, exist_ok=True)

    # ---- CSV de series ----
    with open(carpeta / "series_e09.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["t_h", "T_max_C", "T_nucleo_C", "T_min_superficie_C", "delta_T_celda_C",
                    "delta_T_25mm_C"] + [n for n in pts])
        for idx, ti in enumerate(t):
            fila = [ti, Tmax[idx], nucleo[idx], superficie[idx], dT_celda[idx], dT25[idx]] + [series[n][idx] for n in pts]
            w.writerow([f"{x:.3f}" if np.isfinite(x) else "" for x in fila])

    # ---- resumen ----
    tmax_global, t_tmax = float(r.T_max_abs), float(r.time_of_max(r.T_max_global))
    resumen = {
        "entrega": "E09 - Baseline 3D con hidratacion",
        "commit_base": "7773d10",
        "ifc": args.ifc.name,
        "malla": {"dx_m": grid.dx, "dz_m": grid.dz, "nx": grid.nx, "ny": grid.ny, "nz": grid.nz,
                  "celdas_activas": int(vox.mask.sum()), "error_volumen_total": vox.error_volumen()},
        "vertidas": [{"id": s.vertida_id, "inicio_h": s.inicio_h,
                      "T_colocacion_C": s.temperatura_colocacion_C,
                      "V_ifc_m3": round(s.volumen, 3), "V_voxel_m3": round(vox.volumen_voxel(s.vertida_id), 3),
                      "error_volumen": round(vox.error_volumen(s.vertida_id), 4)} for s in solidos],
        "hidratacion": {"theta_inf_C": plantilla.hidratacion.elevacion_adibatica_C,
                        "tau_h": plantilla.hidratacion.tau_h,
                        "Ea_R_K": plantilla.hidratacion.energia_activacion_K,
                        "madurez": bool(plantilla.hidratacion.madurez)},
        "ambiente": {"media_C": plantilla.ambiente.media_C, "amplitud_C": plantilla.ambiente.amplitud_C,
                     "periodo_h": plantilla.ambiente.periodo_h, "suelo_C": plantilla.suelo.mean_C,
                     "h_superficie_W_m2K": H_SUPERFICIE},
        "resultado": {"T_max_C": round(tmax_global, 2), "T_max_h": t_tmax,
                      "delta_T_celda_max_C": round(float(r.delta_T_max), 2),
                      "delta_T_celda_h": float(r.time_of_max(r.delta_T)),
                      "delta_T_25mm_max_C": round(float(np.nanmax(dT25)), 2),
                      "delta_T_25mm_h": float(t[int(np.nanargmax(dT25))]),
                      "veredicto": veredicto.resumen()},
        "puntos": tabla_puntos,
        "dt_s": r.dt_s, "pasos": r.metadata.get("pasos"),
        "aviso": "Hidratacion y clima provisorios: baseline para interpretar, no para aprobar el plan.",
    }
    (carpeta / "resumen_e09.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- Figura 1: T_max(t) y Delta T ----
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 4.4))
    a1.plot(r.time_h, r.T_max_global, color="#e76f51", lw=2, label="T máx del hormigón")
    a1.plot(r.time_h, r.T_max_core, color="#f4a261", lw=1.4, ls="--", label="T núcleo (erosión 2)")
    a1.plot(r.time_h, r.T_min_surface, color="#264653", lw=1.4, label="T mín superficie")
    a1.axhline(70, color="#8a8a8a", ls=":", lw=1.2, label="Límite 70 °C")
    a1.fill_between(t, 0, 1, where=(t <= 24), transform=a1.get_xaxis_transform(),
                    color="#d9d9d9", alpha=0.5, zorder=0)
    a1.text(11, 0.06, "vertidas 1–5\n(0–24 h)", ha="center", fontsize=8, color="#555",
            transform=a1.get_xaxis_transform())
    a1.set(xlabel="t [h]", ylabel="T [°C]", ylim=(5, 75), title="T_max(t) y temperaturas de control")
    a1.grid(alpha=0.3); a1.legend(fontsize=8, loc="lower right")

    a2.plot(r.time_h, r.delta_T, color="#264653", lw=2, label="ΔT en centros de celda")
    a2.plot(t, dT25, color="#e76f51", lw=2, label="ΔT a 25 mm de la superficie")
    for y, txt in ((20, "20 °C"), (30, "30 °C (ICH >25 MPa)")):
        a2.axhline(y, color="#8a8a8a", ls=":", lw=1)
        a2.text(330, y + 1, txt, ha="right", fontsize=7, color="#666")
    a2.set(xlabel="t [h]", ylabel="ΔT [°C]", title="Diferencial núcleo–superficie")
    a2.grid(alpha=0.3); a2.legend(fontsize=8, loc="upper left")
    fig.tight_layout(); fig.savefig(carpeta / "e09_tmax.png", dpi=160); plt.close(fig)

    # ---- Figura 2: temperatura en puntos ----
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    for nombre, s in series.items():
        ax.plot(t, s, lw=1.8, label=nombre)
    ax.axvspan(0, 24, color="#d9d9d9", alpha=0.45, zorder=0)
    ax.set(xlabel="t [h]", ylabel="T [°C]", title="Temperatura en puntos de control")
    ax.grid(alpha=0.3); ax.legend(fontsize=8); fig.tight_layout()
    fig.savefig(carpeta / "e09_puntos.png", dpi=160); plt.close(fig)

    # ---- Figura 3: cortes 3D (plano y = 0) ----
    j = int(np.argmin(np.abs(yc)))
    extent = (grid.x0, grid.x0 + grid.nx * grid.dx, grid.z0, grid.z0 + grid.nz * grid.dz)
    elegidos = [24, 48, 72, 120, 168, 336]
    instantes_corte = [min(t, key=lambda ti: abs(ti - d)) for d in elegidos]
    fig, ejes = plt.subplots(2, 3, figsize=(14.5, 5.6), sharex=True, sharey=True)
    for ax, ti in zip(ejes.ravel(), instantes_corte):
        T = r.campos[ti]
        im = ax.imshow(T[:, j, :].T, origin="lower", extent=extent, cmap="inferno", vmin=10, vmax=65)
        ax.set_title(f"t = {ti:.0f} h", fontsize=10)
        ax.set_facecolor("#e8e8e8")
    fig.supxlabel("x [m]"); fig.supylabel("z [m]")
    fig.colorbar(im, ax=ejes, fraction=0.02, pad=0.02, label="T [°C] (gris: sin hormigón)")
    fig.savefig(carpeta / "e09_cortes.png", dpi=160, bbox_inches="tight"); plt.close(fig)

    # ---- Figura 4: vista 3D ----
    figura_3d(r, mask3, grid, carpeta)

    print(f"IFC {args.ifc.name}: dx={grid.dx:g} m, dz={grid.dz:g} m, "
          f"{int(vox.mask.sum())} celdas, error de volumen {100 * vox.error_volumen():.2f} %")
    print(f"dt = {r.dt_s:.0f} s, pasos = {r.metadata.get('pasos')}")
    print(f"T max = {tmax_global:.2f} °C a las {t_tmax:.0f} h")
    print(f"Delta T centros = {r.delta_T_max:.2f} °C a {r.time_of_max(r.delta_T):.0f} h; "
          f"Delta T a 25 mm = {np.nanmax(dT25):.2f} °C")
    for fila in tabla_puntos:
        print(f"  {fila['punto']:<44} T max {fila['T_max_C']:6.2f} °C a {fila['t_max_h']:3.0f} h")
    print(veredicto.resumen())
    print(f"Resultados en {carpeta}")


if __name__ == "__main__":
    main()
