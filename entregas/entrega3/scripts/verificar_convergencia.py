"""E03 - Verificacion cuantitativa y convergencia del solver 1D (FTCS).

Se verifica contra una solucion exacta conocida para la ecuacion del calor
con condiciones Dirichlet homogéneas:
    T(x,0)=A*sin(pi*x/L), T(0,t)=T(L,t)=0
Solucion exacta:
    T_exact(x,t)=A*sin(pi*x/L)*exp(-alpha*(pi/L)^2*t)

Se realiza:
- Comparacion exacto vs numerico (perfil)
- Convergencia espacial (refinar dx, dt proporcional a dx^2 o con Fo fijo)
- Convergencia temporal (refinar dt, dx fijo)
- Condicion de estabilidad: Fo = alpha*dt/dx^2 <= 0.5
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan.thermal1d import BC, Material, solve_1d, stable_dt_1d  # noqa: E402

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)

# Material / parametros de verificacion
MAT = Material(k=1.0, rho=1.0, cp=1.0e4)  # alpha = 1e-4 m^2/s
L, A, T0 = 1.0, 10.0, 0.0
t_end = 1500.0


def exact(x, t):
    return T0 + A * np.sin(np.pi * x / L) * np.exp(-MAT.alpha * (np.pi / L) ** 2 * t)


def save_fig(fig, name):
    p = OUT / name
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"[OK] {p}")
    return p


def exact_vs_numerico():
    nx = 81
    res = solve_1d(L, nx, MAT, lambda x: T0 + A * np.sin(np.pi * x / L),
                   t_end, BC.dirichlet(T0), BC.dirichlet(T0), safety=0.4)
    Te = exact(res.x, t_end)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    a1.plot(res.x, Te, label="Exacta", lw=2)
    a1.plot(res.x, res.T_final, "o--", ms=4, label="Numérica (FTCS)")
    a1.set(xlabel="x [m]", ylabel="T [°C]", title="Exacta vs Numérica")
    a1.legend(); a1.grid(alpha=0.3)
    a2.plot(res.x, res.T_final - Te, label="Error (num-exact)")
    a2.axhline(0, color="k", lw=0.5)
    a2.set(xlabel="x [m]", ylabel="Error [°C]", title="Error absoluto")
    a2.legend(); a2.grid(alpha=0.3)
    fig.tight_layout()
    save_fig(fig, "e03_exact_vs_num.png")


def conv_espacial():
    nxs = [21, 41, 81, 161]
    errs = []
    for nx in nxs:
        res = solve_1d(L, nx, MAT, lambda x: T0 + A * np.sin(np.pi * x / L),
                       t_end, BC.dirichlet(T0), BC.dirichlet(T0), safety=0.4)
        Te = exact(res.x, t_end)
        errs.append(np.max(np.abs(res.T_final - Te)))
        print(f"  nx={nx:3d} dx={res.info['dx']:.5f} dt={res.dt:.2f} Fo={res.fo:.3f} err_max={errs[-1]:.3e}")
    # plot
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    dxs = [L/(n-1) for n in nxs]
    a1.loglog(dxs, errs, "o-", label="error máx")
    # referencia O(dx^2)
    c = errs[0]/(dxs[0]**2)
    a1.loglog(dxs, [c*d**2 for d in dxs], "--", label="O(dx^2)")
    a1.set(xlabel="Δx [m]", ylabel="||e||_∞ [°C]")
    a1.set_title("Convergencia espacial")
    a1.invert_xaxis(); a1.legend(); a1.grid(True, which="both", alpha=0.3)
    # orden
    orders = [np.log2(errs[i]/errs[i+1]) for i in range(len(errs)-1)]
    a2.bar(range(len(orders)), orders)
    a2.set_xticks(range(len(orders)), [f"{nxs[i]}→{nxs[i+1]}" for i in range(len(orders))])
    a2.axhline(2, color="r", ls="--", label="orden 2")
    a2.set_ylabel("Orden observado")
    a2.set_title("Orden de convergencia")
    a2.legend(); a2.grid(alpha=0.3)
    fig.tight_layout()
    save_fig(fig, "e03_conv_espacial.png")
    return nxs, dxs, errs


def conv_temporal():
    nx = 81
    dx = L/(nx-1)
    dt_max = stable_dt_1d(MAT, dx, BC.dirichlet(T0), BC.dirichlet(T0))
    factors = [0.1, 0.25, 0.5, 0.8]
    errs = []
    print(f"  dt_max (estable) = {dt_max:.2f} s, Fo_max={MAT.alpha*dt_max/dx**2:.3f}")
    for f in factors:
        dt = f*dt_max
        res = solve_1d(L, nx, MAT, lambda x: T0 + A * np.sin(np.pi * x / L),
                       t_end, BC.dirichlet(T0), BC.dirichlet(T0), dt=dt)
        Te = exact(res.x, t_end)
        errs.append(np.max(np.abs(res.T_final - Te)))
        print(f"  dt/dt_max={f:.2f} dt={dt:.2f} Fo={res.fo:.3f} err_max={errs[-1]:.3e}")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(factors, errs, "o-", label="error máx vs dt/dt_max")
    ax.set_xlabel("dt / dt_max")
    ax.set_ylabel("||e||_∞ [°C]")
    ax.set_title("Convergencia temporal (dx fijo)")
    ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout()
    save_fig(fig, "e03_conv_temporal.png")
    return factors, errs


def main():
    print("E03 - Verificacion contra solucion exacta y convergencia")
    print("="*60)
    print(f"Material: k={MAT.k}, rho={MAT.rho}, cp={MAT.cp}, alpha={MAT.alpha:.1e} m^2/s")
    print(f"Caso: L={L} m, A={A} °C, t_end={t_end} s, Dirichlet homogéneas\n")
    print("[1] Exacta vs numérica")
    exact_vs_numerico()
    print("\n[2] Convergencia espacial (Fo~constante / seguridad)")
    conv_espacial()
    print("\n[3] Convergencia temporal (dx fijo)")
    conv_temporal()
    print("\n" + "="*60)
    print(f"Evidencias guardadas en {OUT}")


if __name__ == "__main__":
    main()
