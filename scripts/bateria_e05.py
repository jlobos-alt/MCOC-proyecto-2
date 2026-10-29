"""Bateria de verificacion termica E05: correr casos en vivo y cambiar parametros.

Ejemplos:
    python scripts/bateria_e05.py                      # todos los casos por defecto
    python scripts/bateria_e05.py 2d --Lx 1 --Ly 0.6 --n 30 --t_h 48
    python scripts/bateria_e05.py 3d --Lx 1.2 --Ly 0.8 --Lz 0.5 --A 15
    python scripts/bateria_e05.py convergencia --dim 3
    python scripts/bateria_e05.py energia --q0 2000
    python scripts/bateria_e05.py fuente --q0 500 --t_h 72
    python scripts/bateria_e05.py neumann --qn -200
    python scripts/bateria_e05.py robin --h 25 --TD 60 --Tinf 10
    python scripts/bateria_e05.py todos --k 1.39 --rho 1800 --cp 1273   # otro material
    python scripts/bateria_e05.py todos --figuras      # guarda PNG en results/e05/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from mcplan import verificacion as v  # noqa: E402

CASOS = ["todos", "1d", "2d", "3d", "convergencia", "energia", "fuente", "neumann", "robin"]


def argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bateria de verificacion termica E05")
    p.add_argument("caso", nargs="?", default="todos", choices=CASOS)
    p.add_argument("--Lx", type=float, default=1.0)
    p.add_argument("--Ly", type=float, default=1.0)
    p.add_argument("--Lz", type=float, default=1.0)
    p.add_argument("--n", type=int, default=20, help="celdas por eje activo")
    p.add_argument("--dim", type=int, default=1, choices=[1, 2, 3], help="para 'convergencia'")
    p.add_argument("--T0", type=float, default=20.0)
    p.add_argument("--A", type=float, default=10.0, help="amplitud del seno [C]")
    p.add_argument("--t_h", type=float, default=24.0, help="tiempo final [h]")
    p.add_argument("--k", type=float, default=v.CONCRETO["k"])
    p.add_argument("--rho", type=float, default=v.CONCRETO["rho"])
    p.add_argument("--cp", type=float, default=v.CONCRETO["cp"])
    p.add_argument("--q0", type=float, default=1000.0, help="fuente volumetrica [W/m3]")
    p.add_argument("--qn", type=float, default=-100.0, help="flujo Neumann [W/m2], >0 sale calor")
    p.add_argument("--h", type=float, default=10.0, help="coef. de conveccion [W/m2K]")
    p.add_argument("--TD", type=float, default=60.0, help="Dirichlet del caso Robin [C]")
    p.add_argument("--Tinf", type=float, default=20.0, help="T ambiente del caso Robin [C]")
    p.add_argument("--figuras", action="store_true", help="guardar figuras en results/e05/")
    return p.parse_args()


def correr(a: argparse.Namespace) -> list:
    mat = {"k": a.k, "rho": a.rho, "cp": a.cp}
    L = (a.Lx, a.Ly, a.Lz)
    sin_kw = dict(L=L, n=a.n, T0=a.T0, A=a.A, t_h=a.t_h, mat=mat)
    salida = []  # (caso, extra para figuras)

    if a.caso in ("todos", "1d"):
        salida.append(("1d", v.caso_sinusoidal(1, **sin_kw)))
    if a.caso in ("todos", "2d"):
        salida.append(("2d", v.caso_sinusoidal(2, **sin_kw)))
    if a.caso in ("todos", "3d"):
        salida.append(("3d", v.caso_sinusoidal(3, **sin_kw)))
    if a.caso in ("todos", "convergencia"):
        dims = (1, 2, 3) if a.caso == "todos" else (a.dim,)
        for d in dims:
            ns = (8, 16, 32) if d == 3 else (10, 20, 40)
            salida.append(("conv", (v.convergencia(d, ns=ns, L=L, T0=a.T0, A=a.A, t_h=a.t_h, mat=mat),)))
    if a.caso in ("todos", "energia"):
        salida.append(("energia", v.caso_energia_adiabatica(L=L, t_h=a.t_h, mat=mat)))
        salida.append(("energia", v.caso_energia_adiabatica(L=L, t_h=a.t_h, mat=mat, q0=a.q0)))
    if a.caso in ("todos", "fuente"):
        salida.append(("fuente", v.caso_fuente_uniforme(L=L, q0=a.q0, T0=a.T0, t_h=a.t_h, mat=mat)))
    if a.caso in ("todos", "neumann"):
        salida.append(("neumann_b", v.caso_neumann_balance(L=a.Lx, n=a.n, q_n=a.qn, T0=a.T0, t_h=a.t_h, mat=mat)))
        salida.append(("neumann", v.caso_neumann_permanente(L=a.Lx, n=a.n, q_n=a.qn, T_D=a.T0, mat=mat)))
    if a.caso in ("todos", "robin"):
        salida.append(("robin", v.caso_robin_permanente(L=a.Lx, n=a.n, h=a.h, T_D=a.TD, T_inf=a.Tinf, mat=mat)))
        salida.append(("robin_t", v.caso_robin_transitorio(h=min(a.h, 5.0), T_inf=a.Tinf, mat=mat)))
    return salida


def figuras(salida: list, carpeta: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    carpeta.mkdir(parents=True, exist_ok=True)
    convs = [extra[0] for clave, extra in salida if clave == "conv"]

    for clave, extra in salida:
        caso = extra[0]
        if clave in ("1d", "2d", "3d"):
            _, model, result, exacto = extra
            x = model.grid.centers()[0]
            j = model.grid.ny // 2
            k = model.grid.nz // 2
            fig, ax = plt.subplots(1, 2, figsize=(10, 4))
            ax[0].plot(x, exacto[:, j, k], "k-", label="exacta")
            ax[0].plot(x, result.T_final[:, j, k], "o", ms=4, label="numerica")
            ax[0].set(xlabel="x [m]", ylabel="T [C]", title=f"{clave.upper()}: corte en y, z centrales")
            ax[0].legend()
            ax[1].plot(x, (result.T_final - exacto)[:, j, k], "r.-")
            ax[1].set(xlabel="x [m]", ylabel="T num - T exacta [C]", title=caso.nombre)
            fig.tight_layout()
            fig.savefig(carpeta / f"e05_sinusoidal_{clave}.png", dpi=120)
            plt.close(fig)
        elif clave in ("neumann", "robin"):
            d = caso.datos
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.plot(d["x"], d["exacto"], "k-", label="exacta")
            ax.plot(d["x"], d["numerico"], "o", ms=4, label="numerica")
            ax.set(xlabel="x [m]", ylabel="T [C]", title=f"{caso.nombre}: {caso.detalle[:60]}")
            ax.legend()
            fig.tight_layout()
            fig.savefig(carpeta / f"e05_{clave}.png", dpi=120)
            plt.close(fig)
        elif clave in ("fuente", "robin_t"):
            _, model, result = extra
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.plot(result.time_h, caso.datos["exacto_t"], "k-", label="exacta")
            ax.plot(result.time_h, result.T_mean, "o", ms=4, label="numerica (media)")
            ax.set(xlabel="t [h]", ylabel="T [C]", title=caso.nombre)
            ax.legend()
            fig.tight_layout()
            fig.savefig(carpeta / f"e05_{clave}.png", dpi=120)
            plt.close(fig)
        elif clave == "energia" and "fuente" not in caso.nombre:
            _, model, result = extra
            capacidad_total = model.rho_cp_flat.sum() * model.grid.cell_volume
            E = capacidad_total * result.T_mean  # material uniforme: E = C_total * T_media
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.plot(result.time_h, (E - E[0]) / E[0], "o-")
            ax.set(xlabel="t [h]", ylabel="(E - E0)/E0", title="Energia en caja adiabatica")
            ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
            fig.tight_layout()
            fig.savefig(carpeta / "e05_energia.png", dpi=120)
            plt.close(fig)

    if convs:
        fig, ax = plt.subplots(figsize=(6, 4))
        for c in convs:
            ns = np.array(c.datos["ns"])
            ax.loglog(1.0 / ns, c.datos["errores"], "o-", label=f"{c.nombre} (p={c.datos['ordenes'][-1]:.2f})")
        h = 1.0 / ns
        ax.loglog(h, c.datos["errores"][-1] * (h / h[-1]) ** 2, "k--", label="pendiente 2")
        ax.set(xlabel="dx / L", ylabel="max|T - T_ex| / (A e^{-alpha lambda t})", title="Convergencia espacial")
        ax.legend()
        fig.tight_layout()
        fig.savefig(carpeta / "e05_convergencia.png", dpi=120)
        plt.close(fig)
    print(f"Figuras guardadas en {carpeta}")


def main() -> int:
    a = argumentos()
    print(f"Material: k={a.k} W/mK, rho={a.rho} kg/m3, cp={a.cp} J/kgK, "
          f"alpha={a.k / (a.rho * a.cp):.3e} m2/s")
    salida = correr(a)
    for _, extra in salida:
        print(extra[0].linea())
    n_ok = sum(extra[0].ok for _, extra in salida)
    print(f"\n{n_ok}/{len(salida)} casos pasan")
    if a.figuras:
        figuras(salida, RAIZ / "results" / "e05")
    return 0 if n_ok == len(salida) else 1


if __name__ == "__main__":
    sys.exit(main())
