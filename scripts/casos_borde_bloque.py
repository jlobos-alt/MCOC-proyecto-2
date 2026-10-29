"""Tres condiciones de borde en un bloque de 3 x 3 x 0.6 m (solver 3D).

El bloque mide Lx = Ly = 3 m y H = 0.6 m de alto (eje z). Las caras laterales
son adiabaticas en los tres casos, asi el problema varia solo en z y tiene
solucion exacta para comparar.

  Caso 1 - Dirichlet:  T(base) = 20 C, T(cara superior) = 30 C.
           Permanente: T(z) = T_base + (T_sup - T_base) z / H   (recta)

  Caso 2 - Neumann dT/dn = 0 (adiabatico) en todas las caras.
           Parte con un perfil 20 -> 30 C en z; el calor no sale, la energia
           se conserva y todo termina en el promedio, 25 C.

  Caso 3 - Robin en la cara superior: -k dT/dn = h (T - 20 C), con h = k*beta
           (la forma dT/dn = -beta (T - T_inf), beta = h/k [1/m]); base a 30 C.
           Permanente: q = (T_base - T_inf) / (H/k + 1/h),  T(z) = T_base - q z / k

Uso:
    python scripts/casos_borde_bloque.py
    python scripts/casos_borde_bloque.py --beta 20 --nz 24 --figura
    python scripts/casos_borde_bloque.py --Tbase 20 --Tsup 30 --Tinf 20 --TbaseRobin 30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from mcplan.plan import plan_from_dict  # noqa: E402
from mcplan.thermal import build_model, solve  # noqa: E402
from mcplan.verificacion import CONCRETO, Caso, difusividad, plan_caja  # noqa: E402


def _cara(nombre: str, signo: str, **kw) -> dict:
    """Frontera sobre una cara z: signo '-' = base (z=0), '+' = cara superior (z=H)."""
    return {"name": nombre, "direccion": "ejes", "ejes": [2], "signo": signo, **kw}


def _bloque(a, fronteras, T0, T_amb=20.0):
    plan = plan_caja((a.L, a.L, a.H), (a.nxy, a.nxy, a.nz), CONCRETO, fronteras, T0, T_ambiente=T_amb)
    return build_model(plan_from_dict(plan))


def _perfil_z(result) -> np.ndarray:
    """T a lo largo de z en la columna central (en estos casos todas las columnas son iguales)."""
    nx, ny, _ = result.T_final.shape
    return result.T_final[nx // 2, ny // 2, :]


def _t_permanente_h(a) -> float:
    # el modo mas lento decae como exp(-t alpha (pi/2H)^2); 8 H^2/alpha lo deja en ~e^-20
    return 8.0 * a.H ** 2 / difusividad(CONCRETO) / 3600.0


def caso_dirichlet(a):
    fronteras = [
        _cara("base", "-", tipo="dirichlet", valor_dirichlet_C=a.Tbase),
        _cara("sup", "+", tipo="dirichlet", valor_dirichlet_C=a.Tsup),
    ]
    model = _bloque(a, fronteras, T0=a.Tbase)
    t_h = _t_permanente_h(a)
    result = solve(model, duracion_h=t_h, intervalo_salida_h=t_h / 50)
    z = model.grid.centers()[2]
    exacto = a.Tbase + (a.Tsup - a.Tbase) * z / a.H
    num = _perfil_z(result)
    caso = Caso("1 Dirichlet 20/30 C", float(np.max(np.abs(num - exacto))), 1e-3,
                f"T(z) recta {a.Tbase} -> {a.Tsup} C, t = {t_h:.0f} h hasta regimen")
    return caso, z, num, exacto, result


def caso_adiabatico(a):
    model = _bloque(a, [], T0=a.Tbase)  # sin fronteras declaradas: todas las caras adiabaticas
    z = model.grid.centers()[2]
    perfil = a.Tbase + (a.Tsup - a.Tbase) * z / a.H
    inicial = np.broadcast_to(perfil, model.grid.shape).ravel()
    t_h = _t_permanente_h(a)
    result = solve(model, duracion_h=t_h, intervalo_salida_h=t_h / 50, temperatura_inicial=inicial)
    capacidad = model.rho_cp_flat * model.grid.cell_volume
    E0 = float(np.sum(capacidad * inicial))
    E1 = float(np.sum(capacidad * result.T_final.ravel()))
    media = float(np.mean(perfil))
    num = _perfil_z(result)
    exacto = np.full_like(z, media)
    caso = Caso("2 Neumann dT/dn = 0", abs(E1 - E0) / E0, 1e-12,
                f"energia: E0={E0:.4e} J, E1={E1:.4e} J; T final {num.min():.3f}-{num.max():.3f} C "
                f"(promedio exacto {media:.2f} C)")
    return caso, z, num, exacto, result


def caso_robin(a):
    h = CONCRETO["k"] * a.beta
    fronteras = [
        _cara("base", "-", tipo="dirichlet", valor_dirichlet_C=a.TbaseRobin),
        _cara("aire", "+", tipo="convectiva", h=h),
    ]
    model = _bloque(a, fronteras, T0=a.TbaseRobin, T_amb=a.Tinf)
    t_h = _t_permanente_h(a)
    result = solve(model, duracion_h=t_h, intervalo_salida_h=t_h / 50)
    z = model.grid.centers()[2]
    k = CONCRETO["k"]
    q = (a.TbaseRobin - a.Tinf) / (a.H / k + 1.0 / h)
    exacto = a.TbaseRobin - q * z / k
    num = _perfil_z(result)
    caso = Caso(f"3 Robin beta={a.beta:g} 1/m", float(np.max(np.abs(num - exacto))), 1e-3,
                f"h = k*beta = {h:.2f} W/m2K, q = {q:.2f} W/m2, T superficie = {a.TbaseRobin - q * a.H / k:.3f} C")
    return caso, z, num, exacto, result


def main() -> int:
    p = argparse.ArgumentParser(description="Tres condiciones de borde en un bloque 3 x 3 x 0.6 m")
    p.add_argument("--L", type=float, default=3.0, help="largo y ancho [m]")
    p.add_argument("--H", type=float, default=0.6, help="alto [m]")
    p.add_argument("--nxy", type=int, default=6, help="celdas en x e y")
    p.add_argument("--nz", type=int, default=12, help="celdas en z")
    p.add_argument("--Tbase", type=float, default=20.0, help="Dirichlet en la base [C]")
    p.add_argument("--Tsup", type=float, default=30.0, help="Dirichlet en la cara superior [C]")
    p.add_argument("--beta", type=float, default=5.0, help="Robin: beta = h/k [1/m]")
    p.add_argument("--Tinf", type=float, default=20.0, help="Robin: T del aire [C]")
    p.add_argument("--TbaseRobin", type=float, default=30.0, help="Robin: T de la base [C]")
    p.add_argument("--figura", action="store_true", help="guardar results/casos_borde/perfiles.png")
    a = p.parse_args()

    print(f"Bloque {a.L} x {a.L} x {a.H} m, celdas {a.nxy} x {a.nxy} x {a.nz} "
          f"(dz = {a.H / a.nz * 100:.1f} cm), hormigon k={CONCRETO['k']} W/mK")
    casos = [caso_dirichlet(a), caso_adiabatico(a), caso_robin(a)]
    for caso, *_ in casos:
        print(caso.linea())
    n_ok = sum(c[0].ok for c in casos)
    print(f"\n{n_ok}/{len(casos)} casos pasan")

    if a.figura:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(1, 3, figsize=(13, 4.2), sharey=True)
        for eje, (caso, z, num, exacto, _) in zip(ax, casos):
            eje.plot(exacto, z, "k-", label="exacta")
            eje.plot(num, z, "o", ms=5, label="solver 3D")
            eje.set(xlabel="T [C]", title=caso.nombre, xlim=(min(a.Tbase, a.Tinf) - 1, max(a.Tsup, a.TbaseRobin) + 1))
            eje.grid(alpha=0.3)
        ax[0].set_ylabel("z [m] (0 = base)")
        ax[0].legend()
        fig.suptitle(f"Bloque {a.L} x {a.L} x {a.H} m: perfil T(z) al final")
        fig.tight_layout()
        carpeta = RAIZ / "results" / "casos_borde"
        carpeta.mkdir(parents=True, exist_ok=True)
        fig.savefig(carpeta / "perfiles.png", dpi=120)
        print(f"Figura: {carpeta / 'perfiles.png'}")
    return 0 if n_ok == len(casos) else 1


if __name__ == "__main__":
    sys.exit(main())
