"""Caso demostrativo 1D: losa de hormigón de 3.3 m con calor de hidratación.

- Cara superior: Robin (convección con aire que oscila día/noche).
- Cara inferior: adiabática (Neumann q=0) como aproximación al suelo.
- Fuente Q(t) = Q0 * exp(-t/tau) (modelo simple de hidratación, provisorio).

Uso:  python scripts/run_1d_demo.py      -> guarda results/demo_1d.png
"""
import sys
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan.thermal1d import BC, Material, solve_1d  # noqa: E402

mat = Material(k=2.5, rho=2400.0, cp=950.0)
L, nx = 3.30, 67
T_col = 18.0                         # temperatura de colocación [°C]
h = 10.0                             # W/(m2 K)
T_air = lambda t: 15.0 + 8.0 * np.sin(2 * np.pi * t / 86400.0)
Q0, tau = 800.0, 1.5 * 86400.0       # W/m3, s   (ΔT_adiabático ≈ Q0 tau/(rho cp) ≈ 45 °C)
Q = lambda t: Q0 * np.exp(-t / tau)

res = solve_1d(L, nx, mat, T_col, 14 * 86400.0,
               left=BC.adiabatic(), right=BC.robin(h, T_air), Q=Q, n_save=300)

Tmax = res.T.max()
dT = (res.T.max(axis=1) - res.T.min(axis=1)).max()
i_peak = np.unravel_index(res.T.argmax(), res.T.shape)
print(f"alpha = {mat.alpha:.3e} m2/s | dx = {res.info['dx']:.3f} m | dt = {res.dt:.0f} s "
      f"| Fo = {res.fo:.3f} | dt_max = {res.dt_max:.0f} s")
print(f"T_max = {Tmax:.1f} °C (límite 70 °C) en t = {res.t[i_peak[0]]/3600:.0f} h, x = {res.x[i_peak[1]]:.2f} m")
print(f"ΔT_max interior-superficie = {dT:.1f} °C (límite 20 °C)")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.5))
    for j in np.linspace(0, len(res.t) - 1, 8).astype(int):
        a1.plot(res.x, res.T[j], label=f"{res.t[j]/86400:.1f} d")
    a1.set(xlabel="z desde la base [m]", ylabel="T [°C]", title="Perfiles")
    a1.legend(fontsize=8)
    a2.plot(res.t / 3600, res.T[:, 0], label="base (adiabática)")
    a2.plot(res.t / 3600, res.T[:, nx // 2], label="centro")
    a2.plot(res.t / 3600, res.T[:, -1], label="superficie (Robin)")
    a2.axhline(70, color="r", ls="--", lw=1, label="70 °C")
    a2.set(xlabel="t [h]", ylabel="T [°C]", title="Historias")
    a2.legend(fontsize=8)
    for a in (a1, a2):
        a.grid(alpha=0.3)
    fig.tight_layout()
    out = ROOT / "resultados" / "demo_1d.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=150)
    print(f"Figura: {out}")
except ImportError:
    print("(matplotlib no instalado: se omite la figura)")
