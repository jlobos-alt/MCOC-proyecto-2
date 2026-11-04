"""E07: voxeliza el IFC real y mide el error de volumen y de area al refinar dx.

Uso:
    python scripts/voxelizar_ifc.py                     # tabla, CSV y figuras
    python scripts/voxelizar_ifc.py --dx 1 0.5 0.25     # otras resoluciones
    python scripts/voxelizar_ifc.py --corte-dx 0.5      # dx de la figura de cortes
    python scripts/voxelizar_ifc.py --ifc otro.ifc

Compara dos grillas: dz = dx y dz ajustado para que las interfaces entre vertidas caigan
en caras de celda (dz_que_calza).

Salidas en results/e07/: volumen_vs_dx.csv, volumen_vs_dx.png, voxeles_cortes.png
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan import area_expuesta, area_exterior, dz_que_calza, extraer_solidos, voxelizar  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402

COLORES = ["#ffffff", "#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51"]


def estudio(solidos, lista_dx, calzar=False):
    area_real = area_exterior(solidos)
    filas = []
    for dx in lista_dx:
        dz = dz_que_calza(solidos, dx) if calzar else dx
        vox = voxelizar(solidos, dx=dx, dz=dz)
        fila = {
            "dx_m": dx,
            "dz_m": dz,
            "celdas_activas": int(vox.mask.sum()),
            "V_voxel_m3": vox.volumen_voxel(),
            "V_geom_m3": vox.volumen_geometrico(),
            "e_V": vox.error_volumen(),
            "signo": np.sign(vox.volumen_voxel() - vox.volumen_geometrico()),
            "A_voxel_m2": area_expuesta(vox.mask, vox.grid),
            "A_real_m2": area_real,
        }
        for s in solidos:
            fila[f"e_V{s.vertida_id}"] = vox.error_volumen(s.vertida_id)
        fila["e_V_peor"] = max(fila[f"e_V{s.vertida_id}"] for s in solidos)
        filas.append(fila)
    return filas


def imprimir(filas, solidos):
    print(f"{'dx [m]':>8}{'dz [m]':>8}{'celdas':>11}{'V_h [m3]':>11}{'V [m3]':>9}{'e_V':>9}"
          f"{'A_h [m2]':>11}{'A [m2]':>9}{'A_h/A':>7}")
    for f in filas:
        print(f"{f['dx_m']:>8.4f}{f['dz_m']:>8.4f}{f['celdas_activas']:>11d}{f['V_voxel_m3']:>11.2f}{f['V_geom_m3']:>9.2f}"
              f"{100 * f['e_V']:>8.2f}%{f['A_voxel_m2']:>11.1f}{f['A_real_m2']:>9.1f}"
              f"{f['A_voxel_m2'] / f['A_real_m2']:>7.3f}")
    dx = np.array([f["dx_m"] for f in filas])
    ev = np.array([f["e_V"] for f in filas])
    p = np.polyfit(np.log(dx), np.log(np.maximum(ev, 1e-12)), 1)[0]
    print(f"\nOrden observado del error de volumen (ajuste log-log): p = {p:.2f}")
    print("Error de volumen por vertida:")
    print(f"{'dx [m]':>8}" + "".join(f"{s.nombre:>12}" for s in solidos))
    for f in filas:
        print(f"{f['dx_m']:>8.4f}" + "".join(f"{100 * f[f'e_V{s.vertida_id}']:>11.2f}%" for s in solidos))
    return p


def graficar_estudio(filas, filas_calzadas, ruta):
    dx = np.array([f["dx_m"] for f in filas])
    ev = np.array([f["e_V"] for f in filas])
    peor = np.array([f["e_V_peor"] for f in filas])
    peor_4 = np.array([max(f[f"e_V{v}"] for v in (1, 2, 3, 4)) for f in filas_calzadas])
    razon = np.array([f["A_voxel_m2"] / f["A_real_m2"] for f in filas])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    a1.loglog(dx, 100 * ev, "o-", color="#264653", label="error de volumen total")
    a1.loglog(dx, 100 * peor, "s-", color="#e76f51", label="peor vertida, Δz = Δx")
    a1.loglog(dx, 100 * peor_4, "^-", color="#2a9d8f", label="peor de las vertidas 1 a 4, Δz calzado")
    a1.loglog(dx, 100 * ev[0] * (dx / dx[0]) ** 2, ":", color="#8a8a8a", label="pendiente 2 (referencia)")
    a1.set(xlabel="Δx [m]", ylabel="e_V [%]", title="Error de volumen: total y por vertida")
    a2.semilogx(dx, razon, "o-", color="#e76f51")
    a2.axhline(1.0, color="#8a8a8a", ls=":", label="área real")
    a2.set(xlabel="Δx [m]", ylabel="A escalera / A real", title="El área expuesta no converge a la real")
    for a in (a1, a2):
        a.grid(alpha=0.3, which="both")
        a.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def graficar_cortes(solidos, dx, ruta):
    vox = voxelizar(solidos, dx=dx)
    x, y, z = vox.grid.centers()
    g = vox.grid
    ids = np.where(vox.vertida_id < 0, 0, vox.vertida_id)
    cmap = ListedColormap(COLORES)
    norm = BoundaryNorm(np.arange(-0.5, 6.5), cmap.N)
    j = int(np.argmin(np.abs(y)))
    extent_xz = (g.x0, g.x0 + g.nx * g.dx, g.z0, g.z0 + g.nz * g.dz)
    extent_xy = (g.x0, g.x0 + g.nx * g.dx, g.y0, g.y0 + g.ny * g.dy)
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.2), gridspec_kw={"width_ratios": [1.5, 1, 1]})
    im = ax[0].imshow(ids[:, j, :].T, origin="lower", extent=extent_xz, cmap=cmap, norm=norm)
    ax[0].set(xlabel="x [m]", ylabel="z [m]", title=f"Corte vertical y ≈ {y[j]:.2f} m (Δx = {dx} m)")
    for a, z_obj in zip(ax[1:], (0.3, 2.75)):
        k = int(np.argmin(np.abs(z - z_obj)))
        a.imshow(ids[:, :, k].T, origin="lower", extent=extent_xy, cmap=cmap, norm=norm)
        a.set(xlabel="x [m]", ylabel="y [m]", title=f"Planta z ≈ {z[k]:.2f} m")
    barra = fig.colorbar(im, ax=ax, ticks=[1, 2, 3, 4, 5], fraction=0.015, pad=0.02)
    barra.set_label("vertida_id")
    barra.ax.set_ylim(0.5, 5.5)
    fig.savefig(ruta, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ifc", type=Path, default=ROOT / "geometry" / "foundation.ifc")
    ap.add_argument("--dx", type=float, nargs="+", default=[1.0, 0.5, 0.25, 0.125, 0.0625])
    ap.add_argument("--corte-dx", type=float, default=0.25)
    ap.add_argument("--salida", type=Path, default=ROOT / "results" / "e07")
    args = ap.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)

    solidos = extraer_solidos(args.ifc)
    print(f"IFC: {args.ifc.name}")
    print(f"{'Vertida':<12}{'id':>3}{'z [m]':>13}{'V [m3]':>9}{'inicio [h]':>12}{'T col [C]':>11}")
    for s in solidos:
        z = f"{s.verts[:, 2].min():.2f}-{s.verts[:, 2].max():.2f}"
        print(f"{s.nombre:<12}{s.vertida_id:>3}{z:>13}{s.volumen:>9.2f}{s.inicio_h:>12.1f}"
              f"{s.temperatura_colocacion_C:>11.1f}")
    print()

    print("--- Grilla con dz = dx ---")
    filas = estudio(solidos, sorted(args.dx, reverse=True))
    imprimir(filas, solidos)
    print("\n--- Grilla con dz calzado a las interfaces entre vertidas ---")
    calzadas = estudio(solidos, sorted(args.dx, reverse=True), calzar=True)
    imprimir(calzadas, solidos)
    with open(args.salida / "volumen_vs_dx.csv", "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas + calzadas)
    graficar_estudio(filas, calzadas, args.salida / "volumen_vs_dx.png")
    graficar_cortes(solidos, args.corte_dx, args.salida / "voxeles_cortes.png")
    print(f"\nResultados en {args.salida}")


if __name__ == "__main__":
    main()
