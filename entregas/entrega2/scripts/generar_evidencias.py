"""Genera TODAS las evidencias graficas de la E02 con un solo comando.

No abre ninguna aplicacion: usa matplotlib con backend 'Agg' (sin ventana).
Salida: resultados/demo_1d.png (+ una version comparando Delta x).

Uso:
    python scripts/generar_evidencias.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan.thermal1d import BC, Material, solve_1d  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")            # backend sin ventana: guarda a archivo
import matplotlib.pyplot as plt  # noqa: E402

OUT = ROOT / "resultados"
OUT.mkdir(exist_ok=True)


def _save(fig, out: Path, dpi: int = 150):
    """Guarda la figura venciendo bloqueos de OneDrive (guardar + reintentar mover)."""
    tmp = out.with_name(out.stem + ".tmp.png")
    fig.savefig(tmp, dpi=dpi)
    for _ in range(10):
        try:
            out.unlink(missing_ok=True)
            os.replace(tmp, out)
            return
        except OSError:
            time.sleep(0.4)
    print(f"[aviso] no se pudo sobrescribir {out.name}; quedo como {tmp.name}")

MAT = Material(k=2.5, rho=2400.0, cp=950.0)
L, NX = 3.30, 67
T_COL = 18.0
H = 10.0
T_AIR = lambda t: 15.0 + 8.0 * np.sin(2 * np.pi * t / 86400.0)
Q0, TAU = 800.0, 1.5 * 86400.0
Q = lambda t: Q0 * np.exp(-t / TAU)
T_END = 14 * 86400.0


def run(nx=NX, dt=None):
    return solve_1d(L, nx, MAT, T_COL, T_END,
                    left=BC.adiabatic(), right=BC.robin(H, T_AIR),
                    Q=Q, dt=dt, n_save=300)


def fig_principal():
    res = run()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.5))
    for j in np.linspace(0, len(res.t) - 1, 8).astype(int):
        a1.plot(res.x, res.T[j], label=f"{res.t[j]/86400:.1f} d")
    a1.set(xlabel="z desde la base [m]", ylabel="T [°C]", title="Perfiles de temperatura")
    a1.legend(fontsize=8)
    a2.plot(res.t / 3600, res.T[:, 0], label="base (adiabática)")
    a2.plot(res.t / 3600, res.T[:, NX // 2], label="centro")
    a2.plot(res.t / 3600, res.T[:, -1], label="superficie (Robin)")
    a2.axhline(70, color="r", ls="--", lw=1, label="70 °C")
    a2.set(xlabel="t [h]", ylabel="T [°C]", title="Historias en el tiempo")
    a2.legend(fontsize=8)
    for a in (a1, a2):
        a.grid(alpha=0.3)
    fig.tight_layout()
    out = OUT / "demo_1d.png"
    _save(fig, out)
    plt.close(fig)
    print(f"[OK] {out}  (T_max={res.T.max():.1f} °C, "
          f"Fo={res.fo:.3f}, dt_max={res.dt_max:.0f} s)")
    return out


def fig_dx_convergencia():
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for nx in (21, 41, 81, 161):
        r = run(nx)
        ax.plot(r.x, r.T_final, marker=".", ms=4, label=f"nx={nx} (dx={r.info['dx']:.3f} m)")
    ax.axhline(70, color="r", ls="--", lw=1, label="70 °C")
    ax.set(xlabel="z desde la base [m]", ylabel="T final [°C]",
           title="Efecto de Δx: refinamiento de malla (t = 14 d)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = OUT / "demo_1d_dx.png"
    _save(fig, out)
    plt.close(fig)
    print(f"[OK] {out}  (convergencia con Δx, orden O(dx^2))")
    return out


def main():
    print("Generando evidencias E02 (sin abrir aplicaciones)...")
    imgs = [fig_principal(), fig_dx_convergencia()]
    print(f"\nListo. Imagenes en: {OUT}")

    # Abrir las imagenes automaticamente con el visor de Windows
    for img in imgs:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", str(img)], shell=False)
        except Exception:
            try:
                os.startfile(str(img))  # noqa: S606
            except Exception as e:  # noqa: BLE001
                print(f"[aviso] no se pudo abrir {img.name}: {e}")


if __name__ == "__main__":
    main()
