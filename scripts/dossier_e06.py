"""E06: genera toda la evidencia del dossier de verificacion con un solo comando.

Uso:
    python scripts/dossier_e06.py

Salidas en results/e06/:
    matriz_verificacion.md / .csv   tabla Test | Que verifica | Error | Resultado
    convergencia.md                 errores y ordenes de cada refinamiento
    convergencia_espacial.png       error vs dx con dt fijo
    convergencia_temporal.png       error vs dt con malla fija
    energia_fuente.png              conservacion y subida lineal
    robin.png                       perfil permanente y transitorio contra la exacta
    bim_base.png, bim_base_3d.png   fundacion leida del IFC: 3D, planta y corte
    bim_dimensiones.md              dimensiones y volumen medidos en el IFC
"""
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from mcplan import build_model, extraer_solidos, solve  # noqa: E402
from mcplan import verificacion as v  # noqa: E402
from mcplan.plan import plan_from_dict  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SALIDA = RAIZ / "results" / "e06"
IFC = RAIZ / "geometry" / "foundation.ifc"
COLORES = ["#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51"]


def _fila(test, que, metrica, ok):
    return [test, que, metrica, "PASA" if ok else "FALLA"]


def _adiabatico_con_hidratacion():
    """Caja adiabatica con hidratacion: la subida final debe ser theta_inf, con y sin madurez."""
    errores = []
    for madurez in (False, True):
        plan = plan_from_dict(v.plan_caja((1.0, 1.0, 1.0), (2, 2, 2), T0=18.0))
        plan.hidratacion.elevacion_adibatica_C = 45.0
        plan.hidratacion.tau_h = 30.0
        plan.hidratacion.madurez = madurez
        r = solve(build_model(plan), duracion_h=800.0, intervalo_salida_h=100.0, dt_s=600.0)
        errores.append(abs(r.T_mean[-1] - 18.0 - 45.0))
    return max(errores)


def _dt_inestable():
    """Sobre el limite de Fo la solucion debe diverger; bajo el limite, no."""
    plan = plan_from_dict(v.plan_caja(
        (1.0, 0.05, 0.05), (20, 1, 1),
        fronteras=[{"name": "d", "direccion": "ejes", "ejes": [0], "signo": "ambos", "tipo": "dirichlet",
                    "valor_dirichlet_C": 20.0}]))
    modelo = build_model(plan)
    X = v._centros(modelo)
    inicial = (20.0 + 10.0 * np.sin(np.pi * X[0]) + 0.01 * np.sin(19 * np.pi * X[0])).ravel()
    limite = 0.05 ** 2 / (2.0 * v.difusividad(v.CONCRETO))
    amplitud = {}
    for fo in (0.45, 0.60):
        dt = fo / 0.5 * limite
        r = solve(modelo, duracion_h=dt * 400 / 3600.0, intervalo_salida_h=dt * 400 / 3600.0, dt_s=dt,
                  temperatura_inicial=inicial)
        amplitud[fo] = float(np.max(np.abs(r.T_final - 20.0)))
    return amplitud


def matriz():
    filas = []
    for dim, n in ((1, 20), (2, 20), (3, 20)):
        caso = v.caso_sinusoidal(dim, n=n)[0]
        filas.append(_fila(f"Seno {dim}D, Dirichlet", "Difusión contra solución exacta",
                           f"error rel. {caso.error:.2e}", caso.ok))
    espaciales = {}
    for dim, ns, dt in ((1, (10, 20, 40, 80), 20.0), (2, (10, 20, 40), 40.0), (3, (8, 16, 32), 40.0)):
        caso = v.convergencia_espacial(dim, ns=ns, dt_s=dt)
        espaciales[dim] = caso
        filas.append(_fila(f"Convergencia espacial {dim}D", f"Orden con Δt fijo = {dt:g} s (Richardson)",
                           f"p = {caso.datos['ordenes'][-1]:.2f}", caso.ok))
    temporales = {}
    for dim, n in ((1, 20), (3, 12)):
        caso = v.convergencia_temporal(dim, n=n)
        temporales[dim] = caso
        filas.append(_fila(f"Convergencia temporal {dim}D", f"Orden con n = {n} fijo",
                           f"p = {caso.datos['ordenes'][-1]:.2f}", caso.ok))
    caso, _, r_e = v.caso_energia_adiabatica()
    filas.append(_fila("Energía sin fuente", "Caja adiabática, campo aleatorio: ΣCT constante",
                       f"error rel. {caso.error:.1e}", caso.ok))
    caso = v.caso_energia_adiabatica(q0=1000.0)[0]
    filas.append(_fila("Energía con fuente", "E = E₀ + q₀·V·t", f"error rel. {caso.error:.1e}", caso.ok))
    caso_f, _, r_f = v.caso_fuente_uniforme()
    filas.append(_fila("Fuente uniforme", "Subida lineal T₀ + q₀·t/(ρ·cp)", f"{caso_f.error:.1e} °C", caso_f.ok))
    err_h = _adiabatico_con_hidratacion()
    filas.append(_fila("Hidratación adiabática", "Subida final θ∞ = 45 °C, con y sin madurez",
                       f"{err_h:.1e} °C", err_h < 1e-6))
    caso = v.caso_neumann_balance()[0]
    filas.append(_fila("Neumann, balance", "ΔE = −q_n·A·t", f"error rel. {caso.error:.1e}", caso.ok))
    caso = v.caso_neumann_permanente()[0]
    filas.append(_fila("Neumann + Dirichlet", "Perfil permanente lineal", f"{caso.error:.1e} °C", caso.ok))
    caso_r, _, _ = v.caso_robin_permanente()
    filas.append(_fila("Robin permanente", "q = ΔT/(L/k + 1/h), perfil exacto", f"{caso_r.error:.1e} °C", caso_r.ok))
    caso_t, _, r_t = v.caso_robin_transitorio()
    filas.append(_fila("Robin transitorio", "Capacidad agrupada, Bi ≪ 1", f"error rel. {caso_t.error:.2e}", caso_t.ok))
    h_grande = v.caso_robin_permanente(h=1e6)[0]
    filas.append(_fila("Robin con h → ∞", "Tiende a Dirichlet", f"{h_grande.error:.1e} °C", h_grande.ok))
    amp = _dt_inestable()
    ok = amp[0.45] < 11.0 and amp[0.60] > 100.0
    filas.append(_fila("Estabilidad 1D", "Fo = 0,45 estable; Fo = 0,60 diverge",
                       f"amplitud final: {amp[0.45]:.1f} y {amp[0.60]:.1e} °C", ok))

    tabla = ["| Refinamiento | Dimensión | Valores | Error relativo máximo | Orden p |", "|---|---:|---|---|---|"]
    for dim, caso in espaciales.items():
        tabla.append(f"| Espacial (n) | {dim}D | {', '.join(str(n) for n in caso.datos['ns'])} | "
                     f"{', '.join(f'{e:.2e}' for e in caso.datos['errores'])} | "
                     f"{', '.join(f'{p:.2f}' for p in caso.datos['ordenes'])} |")
    for dim, caso in temporales.items():
        tabla.append(f"| Temporal (Δt, s) | {dim}D | {', '.join(f'{d:g}' for d in caso.datos['dts'])} | "
                     f"{', '.join(f'{e:.2e}' for e in caso.datos['errores'])} | "
                     f"{', '.join(f'{p:.2f}' for p in caso.datos['ordenes'])} |")
    (SALIDA / "convergencia.md").write_text("\n".join(tabla) + "\n", encoding="utf-8")

    # Figuras
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    for (dim, caso), color in zip(espaciales.items(), COLORES):
        dx = np.array(caso.datos["dx"])
        err = np.array(caso.datos["errores"])
        ax.loglog(dx, err, "o-", color=color, label=f"{dim}D, p = {caso.datos['ordenes'][-1]:.2f}")
    dx = np.array(espaciales[1].datos["dx"])
    ax.loglog(dx, espaciales[1].datos["errores"][0] * (dx / dx[0]) ** 2, ":", color="#777777", label="pendiente 2")
    ax.set(xlabel="Δx [m]", ylabel="error relativo máximo", title="Convergencia espacial, Δt fijo")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(SALIDA / "convergencia_espacial.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    for (dim, caso), color in zip(temporales.items(), COLORES):
        ax.loglog(caso.datos["dts"], caso.datos["errores"], "o-", color=color,
                  label=f"{dim}D, p = {caso.datos['ordenes'][-1]:.2f}")
    dts = np.array(temporales[1].datos["dts"])
    ax.loglog(dts, temporales[1].datos["errores"][0] * (dts / dts[0]), ":", color="#777777", label="pendiente 1")
    ax.set(xlabel="Δt [s]", ylabel="error relativo máximo", title="Convergencia temporal, malla fija")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(SALIDA / "convergencia_temporal.png", dpi=150)
    plt.close(fig)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 3.9))
    a1.plot(r_f.time_h, r_f.T_mean, "o", ms=4, color="#264653", label="numérica")
    a1.plot(r_f.time_h, caso_f.datos["exacto_t"], "-", color="#e76f51", label="T₀ + q₀·t/(ρ·cp)")
    a1.set(xlabel="t [h]", ylabel="T media [°C]", title="Fuente uniforme, q₀ = 1000 W/m³")
    a2.plot(r_e.time_h, r_e.T_mean, "o-", ms=4, color="#264653")
    a2.set(xlabel="t [h]", ylabel="T media [°C]", title="Caja adiabática sin fuente: T media constante",
           ylim=(r_e.T_mean[0] - 1, r_e.T_mean[0] + 1))
    for a in (a1, a2):
        a.grid(alpha=0.3)
    a1.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(SALIDA / "energia_fuente.png", dpi=150)
    plt.close(fig)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 3.9))
    a1.plot(caso_r.datos["x"], caso_r.datos["numerico"], "o", ms=4, color="#264653", label="numérica")
    a1.plot(caso_r.datos["x"], caso_r.datos["exacto"], "-", color="#e76f51", label="exacta")
    a1.set(xlabel="x [m]", ylabel="T [°C]", title="Robin permanente (h = 10 W/m²K)")
    a2.plot(r_t.time_h, r_t.T_mean, "o", ms=4, color="#264653", label="numérica")
    a2.plot(r_t.time_h, caso_t.datos["exacto_t"], "-", color="#e76f51", label="capacidad agrupada")
    a2.set(xlabel="t [h]", ylabel="T media [°C]", title="Robin transitorio (Bi ≪ 1)")
    for a in (a1, a2):
        a.grid(alpha=0.3)
        a.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(SALIDA / "robin.png", dpi=150)
    plt.close(fig)
    return filas


def _vista_3d(solidos, ruta):
    """Render 3D de los solidos del IFC, con las vertidas separadas en altura para distinguirlas."""
    import pyvista as pv

    plotter = pv.Plotter(off_screen=True, window_size=(1200, 900))
    plotter.set_background("white")
    for i, (s, color) in enumerate(zip(solidos, COLORES)):
        caras = np.hstack([np.full((len(s.faces), 1), 3), s.faces]).ravel()
        malla = pv.PolyData(s.verts + np.array([0.0, 0.0, 0.9 * i]), caras)
        plotter.add_mesh(malla, color=color, show_edges=False, smooth_shading=False, label=s.nombre)
    plotter.add_legend(bcolor="white", face=None, size=(0.22, 0.26))
    plotter.camera_position = [(26.0, -30.0, 19.0), (0.0, 0.0, 3.2), (0.0, 0.0, 1.0)]
    plotter.screenshot(str(ruta))
    plotter.close()


def bim():
    solidos = extraer_solidos(IFC)
    vista = SALIDA / "bim_base_3d.png"
    _vista_3d(solidos, vista)

    fig, (a3, ap, ac) = plt.subplots(1, 3, figsize=(14, 4.2), gridspec_kw={"width_ratios": [1.25, 1, 1.5]})
    a3.imshow(plt.imread(vista))
    a3.set_axis_off()
    a3.set_title("Vertidas leídas del IFC (separadas en altura)")
    # En planta se dibuja de abajo hacia arriba: queda visible lo que se ve desde arriba
    for s, color in zip(solidos, COLORES):
        ap.tripcolor(s.verts[:, 0], s.verts[:, 1], s.faces, np.zeros(len(s.faces)),
                     cmap=matplotlib.colors.ListedColormap([color]))
        # Corte en y = 0: cada triangulo que cruza el plano aporta un segmento
        for tri in s.verts[s.faces]:
            pts = []
            for i in range(3):
                p, q = tri[i], tri[(i + 1) % 3]
                if (p[1] - 1e-6) * (q[1] - 1e-6) < 0:
                    pts.append(p + (1e-6 - p[1]) / (q[1] - p[1]) * (q - p))
            if len(pts) == 2:
                ac.plot([pts[0][0], pts[1][0]], [pts[0][2], pts[1][2]], color=color, lw=1.8)
    ap.set(xlabel="x [m]", ylabel="y [m]", title="Planta (18 m entre caras)", aspect="equal")
    ac.set(xlabel="x [m]", ylabel="z [m]", title="Corte en y = 0 (altura total 4,30 m)", aspect="equal")
    for a in (ap, ac):
        a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(SALIDA / "bim_base.png", dpi=150)
    plt.close(fig)

    lineas = ["| Vertida | z [m] | Ancho máx. en x [m] | V IFC [m³] | V Pset [m³] | Inicio [h] | T colocación [°C] |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for s in solidos:
        z0, z1 = s.verts[:, 2].min(), s.verts[:, 2].max()
        lineas.append(f"| {s.nombre} | {z0:.2f}–{z1:.2f} | {np.ptp(s.verts[:, 0]):.2f} | {s.volumen:.2f} | "
                      f"{s.volumen_pset_m3:.2f} | {s.inicio_h:.0f} | {s.temperatura_colocacion_C:.0f} |")
    total = sum(s.volumen for s in solidos)
    lineas.append(f"| **Total** | 0.00–4.30 | | **{total:.2f}** | "
                  f"**{sum(s.volumen_pset_m3 for s in solidos):.2f}** | | |")
    # Con fin de linea LF: Git puede cambiarlo al clonar en Windows y el hash no debe depender de eso
    sha = hashlib.sha256(IFC.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    (SALIDA / "bim_dimensiones.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    (SALIDA / "ifc_sha256.txt").write_text(sha + "\n", encoding="utf-8")
    return lineas, sha


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    filas = matriz()
    encabezado = ["Test", "Qué verifica", "Error/métrica", "Resultado"]
    with open(SALIDA / "matriz_verificacion.csv", "w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(encabezado)
        w.writerows(filas)
    md = ["| " + " | ".join(encabezado) + " |", "|---|---|---|---|"] + ["| " + " | ".join(f) + " |" for f in filas]
    (SALIDA / "matriz_verificacion.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    lineas, sha = bim()
    print("\n" + "\n".join(lineas))
    print(f"\nSHA-256 de foundation.ifc (fin de linea LF): {sha}")
    fallas = [f[0] for f in filas if f[-1] != "PASA"]
    print(f"\n{len(filas) - len(fallas)}/{len(filas)} casos pasan" + (f"; FALLAN: {fallas}" if fallas else ""))
    print(f"Resultados en {SALIDA}")
    return 1 if fallas else 0


if __name__ == "__main__":
    raise SystemExit(main())
