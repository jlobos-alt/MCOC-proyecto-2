"""E07: curva adiabatica, calor volumetrico y efecto de la temperatura (madurez).

Resuelve una celda adiabatica: sin perdidas, dT/dt = qdot/(rho cp), con la edad
equivalente de Arrhenius. Muestra que el calor total es el mismo y solo cambia cuando
se libera. Parametros de datos/fundacion_ifc.yaml (provisorios).

Uso:
    python scripts/curva_hidratacion.py
    python scripts/curva_hidratacion.py --theta 50 --tau 24 --ea-r 5000

Salida: results/e07/hidratacion.png
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
from mcplan.hydration import HydrationModel  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RHO_CP = 2400.0 * 970.0   # J/(m3 K), hormigon de Ju & Lei


def celda_adiabatica(modelo: HydrationModel, T0: float, horas: float, dt_h: float = 0.05):
    """Devuelve t [h], T [C] y qdot [W/m3] de una celda sin perdidas."""
    n = int(horas / dt_h)
    t, T, q = np.arange(n + 1) * dt_h, np.empty(n + 1), np.empty(n + 1)
    T[0] = T0
    edad = 0.0
    for i in range(n + 1):
        m = float(modelo.maturity_factor(T[i]))
        q[i] = RHO_CP * float(modelo.dtheta_dage(edad)) * m / 3600.0
        if i < n:
            nueva = edad + dt_h * m
            T[i + 1] = T[i] + float(modelo.theta(nueva) - modelo.theta(edad))
            edad = nueva
    return t, T, q


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theta", type=float, default=45.0, help="elevacion adiabatica final [C]")
    ap.add_argument("--tau", type=float, default=30.0, help="constante de tiempo [h]")
    ap.add_argument("--ea-r", type=float, default=4000.0, help="Ea/R [K]")
    ap.add_argument("--salida", type=Path, default=ROOT / "results" / "e07")
    args = ap.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)

    base = HydrationModel(theta_inf_1_C=args.theta, tau_1_h=args.tau)
    modelo = HydrationModel(theta_inf_1_C=args.theta, tau_1_h=args.tau, activation_temperature_K=args.ea_r)
    print(f"qdot(0) sin madurez = rho cp * theta/tau = {float(base.heat_rate(0.0, volumetric_heat_capacity=RHO_CP)):.0f} W/m3")
    print(f"Energia total por m3 = rho cp * theta = {RHO_CP * args.theta / 1e6:.1f} MJ/m3")
    print(f"{'T [C]':>6}{'m(T)':>8}")
    for T in (5, 10, 20, 30, 40, 50, 60):
        print(f"{T:>6}{float(modelo.maturity_factor(T)):>8.2f}")

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    colores = {5.0: "#264653", 18.0: "#2a9d8f", 30.0: "#e76f51"}
    print(f"\n{'T col [C]':>10}{'subida 24 h':>13}{'subida 300 h':>14}{'qdot max [W/m3]':>17}")
    for T0, color in colores.items():
        t, T, q = celda_adiabatica(modelo, T0, 300.0)
        k24 = int(round(24.0 / (t[1] - t[0])))
        print(f"{T0:>10.0f}{T[k24] - T0:>11.1f} C{T[-1] - T0:>12.1f} C{q.max():>17.0f}")
        a1.plot(t, T - T0, color=color, label=f"colocación {T0:.0f} °C")
        a2.plot(t, q, color=color, label=f"colocación {T0:.0f} °C")
    t = np.linspace(0.0, 300.0, 601)
    a1.plot(t, base.theta(t), "k:", label="sin madurez")
    a2.plot(t, base.heat_rate(t, volumetric_heat_capacity=RHO_CP), "k:", label="sin madurez")
    a1.set(xlabel="t [h]", ylabel="θ = T − T col [°C]", title="Subida adiabática: el total es igual")
    a2.set(xlabel="t [h]", ylabel="Q̇h [W/m³]", title="Calor generado: caliente libera antes", xlim=(0, 96))
    for a in (a1, a2):
        a.grid(alpha=0.3)
        a.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(args.salida / "hidratacion.png", dpi=150)
    plt.close(fig)
    print(f"\nResultados en {args.salida}")


if __name__ == "__main__":
    main()
