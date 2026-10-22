"""Demo 1D interactivo: efecto de Delta x y Delta t (E02).

Ejecuta el solver 1D sobre la losa de hormigon de 3.3 m (calor de hidratacion)
y permite variar el numero de nodos nx (=Delta x) y el paso de tiempo dt
(=Delta t) para EXPLICAR el efecto observado, que es lo que pide la actividad:

  * Delta x (nx): malla mas fina -> solucion mas precisa (error O(dx^2)).
  * Delta t (dt): si Fo = alpha*dt/dx^2 > 0.5 el esquema explicito es INESTABLE.

Uno de los bordes es Robin con aire dia/noche; el otro adiabatico.

Uso:
    python scripts/demo_1d_dx_dt.py                 # malla de referencia
    python scripts/demo_1d_dx_dt.py --nx 21         # Delta x mas grueso
    python scripts/demo_1d_dx_dt.py --nx 131        # Delta x mas fino
    python scripts/demo_1d_dx_dt.py --dt 3600       # Delta t sobre el limite: el solver lo rechaza
    python scripts/demo_1d_dx_dt.py --dt 3600 --forzar   # correrlo igual y ver como diverge
    python scripts/demo_1d_dx_dt.py --sweep         # tabla comparativa nx y dt
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
from mcplan.thermal1d import BC, Material, solve_1d, stable_dt_1d  # noqa: E402

MAT = Material(k=2.5, rho=2400.0, cp=950.0)
L = 3.30                       # espesor de la losa [m]
H = 10.0                       # coef. conveccion [W/m2 K]
T_COL = 18.0                   # temperatura de colocacion [°C]
Q0, TAU = 800.0, 1.5 * 86400.0
T_AIR = lambda t: 15.0 + 8.0 * np.sin(2 * np.pi * t / 86400.0)
Q = lambda t: Q0 * np.exp(-t / TAU)
T_END = 14 * 86400.0


def solve(nx: int, dt=None, allow_unstable=False):
    dx = L / (nx - 1)
    return solve_1d(L, nx, MAT, T_COL, T_END,
                    left=BC.adiabatic(), right=BC.robin(H, T_AIR),
                    Q=Q, dt=dt, n_save=20, allow_unstable=allow_unstable)


def report(res, label: str):
    Tmax = res.T.max()
    dT = (res.T.max(axis=1) - res.T.min(axis=1)).max()
    print(f"{label:<22} dx={res.info['dx']:.4f} m  dt={res.dt:8.1f} s  "
          f"Fo={res.fo:6.3f}  dt_max={res.dt_max:8.1f} s  "
          f"T_max={Tmax:8.2f} °C  dT={dT:6.2f} °C")
    return Tmax


def sweep():
    print("Efecto de Delta x (dx = L/(nx-1)), dt automatico estable:")
    sols = {}
    for nx in (21, 41, 81, 161):
        res = solve(nx)
        sols[nx] = res
        report(res, f"nx={nx}")
    coarse = sols[21].T_final
    fine = sols[161].T_final
    interp = np.interp(sols[161].x, sols[21].x, coarse)
    err = np.max(np.abs(interp - fine))
    print(f"  -> error maximo malla gruesa vs fina interpolada = {err:.3f} °C")
    print("  -> al refinar dx el perfil converge (error O(dx^2)).")

    print("\nEfecto de Delta t (nx=67 fijo), variando dt:")
    dx = L / 66
    dt_est = stable_dt_1d(MAT, dx, BC.adiabatic(), BC.robin(H, T_AIR))
    for factor in (0.25, 0.5, 0.9):
        dt = factor * dt_est
        report(solve(67, dt=dt), f"dt={factor:.2f}*dt_max")
    print(f"  -> dt_max estable = {dt_est:.1f} s (Fo<=0.5).")
    print("  -> con dt<=dt_max la solucion no cambia (solo es mas/menos costosa).")
    try:
        res = solve(67, dt=1.3 * dt_est, allow_unstable=True)
        amax = np.max(np.abs(res.T_final - T_COL))
        print(f"  -> dt=1.30*dt_max  -> Fo={res.fo:.3f}  amplitud |T-T0|max={amax:.1f} °C  "
              f"({'INESTABLE: diverge' if amax > 100 else 'estable'})")
    except ValueError as e:
        print(f"  -> dt=1.30*dt_max rechazado por el solver: {e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nx", type=int, default=67, help="numero de nodos (controla Delta x)")
    ap.add_argument("--dt", type=float, default=None, help="paso de tiempo en s (controla Delta t)")
    ap.add_argument("--sweep", action="store_true", help="tabla comparativa de nx y dt")
    ap.add_argument("--forzar", action="store_true",
                    help="correr aunque dt supere el limite de estabilidad (para ver la divergencia)")
    args = ap.parse_args()

    if args.sweep:
        sweep()
        return

    dx = L / (args.nx - 1)
    dt_max = stable_dt_1d(MAT, dx, BC.adiabatic(), BC.robin(H, T_AIR))
    if args.dt is not None and args.dt > dt_max and not args.forzar:
        print(f"dx = {dx:.4f} m  ->  dt_max estable = {dt_max:.1f} s  (Fo efectivo pedido = "
              f"{MAT.alpha * args.dt / dx**2:.3f})")
        print(f"dt = {args.dt:.1f} s supera el limite: el solver se NIEGA a correr (ValueError).")
        print("El limite sale de dt <= C_i/(sum G_ij + G_borde): Fo <= 0.5 en el interior y")
        print("algo menos en el borde Robin. Usa --forzar para ver como diverge.")
        return
    res = solve(args.nx, dt=args.dt, allow_unstable=args.forzar)
    if args.forzar and (not np.all(np.isfinite(res.T_final)) or np.nanmax(np.abs(res.T_final)) > 1e3):
        print(f"INESTABLE: dt = {res.dt:.1f} s > dt_max = {res.dt_max:.1f} s  (Fo = {res.fo:.3f})")
        print(f"La temperatura llega a |T| ~ {np.nanmax(np.abs(res.T_final)):.3g} °C: oscilacion que crece")
        print("en cada paso (peso 1-2Fo negativo). Resultado sin sentido fisico.")
        return
    print(f"Material : k={MAT.k} W/mK  rho={MAT.rho} kg/m3  cp={MAT.cp} J/kgK  "
          f"alpha={MAT.alpha:.3e} m2/s")
    report(res, "caso")
    print(f"T_max = {res.T.max():.2f} °C (limite 70 °C)  |  "
          f"dT interior-superficie = {(res.T.max(axis=1) - res.T.min(axis=1)).max():.2f} °C (limite 20 °C)")
    print("\nInterpretacion:")
    print("  Delta x: dx = L/(nx-1). Mas nodos -> dx menor -> solucion mas precisa (O(dx^2)).")
    print("  Delta t: dt <= dt_max para Fo<=0.5; sobre eso el esquema explicito diverge.")


if __name__ == "__main__":
    main()
