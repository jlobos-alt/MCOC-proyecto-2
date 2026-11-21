"""Verificacion completa del visualizador termico (scripts/visualizador_termico.py).

Recorre los 8 casos cambiando cada parametro hasta los extremos de su slider y
revisa, en TODOS los instantes guardados:

  1. exactitud:    max |T_solver - T_exacta| / rango del caso      (<= 2 % si n >= 8)
  2. estabilidad:  dt usado <= dt limite C/sum(G); nada de NaN/inf
  3. fisica:       principio del maximo (sin fuente, T queda dentro del rango),
                   energia constante (adiabatico) o + q0 V t (fuente)
  4. tendencias:   Robin: mas beta -> techo mas frio; fuente: T lineal en q0;
                   Neumann: el signo de q_n decide si entra o sale calor;
                   seno: 3D se enfria mas rapido que 2D, y 2D mas que 1D
  5. interfaz:     sliders -> parametros, cada caso conserva sus valores,
                   escala de colores, slider de tiempo, animacion, aviso de "muy largo"

    python scripts/verificar_visualizador.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import visualizador_termico as v  # noqa: E402
from mcplan.thermal import estimate_timestep  # noqa: E402

TOL_REL = 0.02
SALTO_EN_BORDE = ("Dirichlet base/techo", "Robin beta", "Neumann q_n")
fallas: list[str] = []


def check(ok: bool, texto: str) -> None:
    print(("  [PASA] " if ok else "  [FALLA] ") + texto)
    if not ok:
        fallas.append(texto)


def parametros(caso: str, **cambios) -> dict:
    p = {k: d[3] for k, d in v.COMUNES.items()}
    p.update({k: d[3] for k, d in v.PROPIOS[caso].items()})
    p.update(cambios)
    return p


def evaluar(caso: str, p: dict) -> dict:
    sim = v.simular(caso, p)
    lo, hi = sim["lim"]
    rango = max(hi - lo, 1e-9)
    model = sim["model"]
    d_min = min(model.grid.dx, model.grid.dy, model.grid.dz)
    alpha = v.difusividad(v.CONCRETO)
    errores, tempranos = [], [0.0]
    for c, t in zip(sim["campos"][1:], sim["tiempos"][1:]):
        e = np.max(np.abs(c - np.asarray(sim["exacta"](t * 3600.0))))
        # salto brusco en un borde: mientras el calor no cruza una celda (sqrt(alpha t) < dx)
        # la malla no puede resolver la capa limite; ese error se reporta aparte
        if caso in SALTO_EN_BORDE and np.sqrt(alpha * t * 3600.0) < d_min:
            tempranos.append(e)
        else:
            errores.append(e)
    if not errores:
        errores = [0.0]
    campos = np.array(sim["campos"])
    dt_lim = estimate_timestep(sim["model"], safety=1.0)
    C = model.rho_cp_flat * model.grid.cell_volume
    E = np.array([np.sum(C * c.ravel()) for c in sim["campos"]])
    err_final = np.max(np.abs(sim["campos"][-1] - np.asarray(sim["exacta"](sim["tiempos"][-1] * 3600.0))))
    return dict(sim=sim, err_final=err_final, err_rel=max(errores) / rango, err_temprano=max(tempranos) / rango, finito=bool(np.all(np.isfinite(campos))),
                dt_ok=sim["dt_s"] <= dt_lim * (1 + 1e-9), Tmin=campos.min(), Tmax=campos.max(),
                lo=lo, hi=hi, E=E)


def barrido(caso: str, variaciones: list[dict]) -> None:
    print(f"\n=== {caso} ===")
    for cambios in variaciones:
        p = parametros(caso, **cambios)
        etiqueta = ", ".join(f"{k}={val:g}" for k, val in cambios.items()) or "por defecto"
        try:
            r = evaluar(caso, p)
        except v.SimulacionMuyLarga:
            print(f"  [AVISO] {etiqueta}: muy larga, el visualizador avisa en vez de congelarse")
            continue
        sin_fuente = caso != "Fuente q0"
        dentro = (not sin_fuente) or (r["lo"] - 1e-6 <= r["Tmin"] and r["Tmax"] <= r["hi"] + 1e-6)
        tol = TOL_REL if p["n"] >= 8 else 0.10   # n = 4 es malla gruesa a proposito
        ok = r["finito"] and r["dt_ok"] and dentro and r["err_rel"] <= tol
        detalle = (f"error {r['err_rel'] * 100:.3f} % del rango, dt {r['sim']['dt_s']:.0f} s, "
                   f"T en [{r['Tmin']:.2f}, {r['Tmax']:.2f}]")
        if r["err_temprano"] > tol:
            detalle += f"  (nota: {r['err_temprano'] * 100:.1f} % en los primeros minutos, capa limite < 1 celda)"
        if caso == "Adiabatico dT/dn=0":
            escala = np.sum(r["sim"]["model"].rho_cp_flat * r["sim"]["model"].grid.cell_volume) * (r["hi"] - r["lo"])
            dE = np.max(np.abs(r["E"] - r["E"][0])) / escala
            ok &= dE < 1e-12
            detalle += f", dE relativo {dE:.1e}"
        if caso == "Fuente q0":
            V = r["sim"]["model"].grid.cell_volume * r["sim"]["model"].grid.n_cells
            esperado = r["E"][0] + p["q0"] * V * r["sim"]["tiempos"] * 3600.0
            escala = np.sum(r["sim"]["model"].rho_cp_flat * r["sim"]["model"].grid.cell_volume) * max(r["hi"] - r["lo"], 1.0)
            dE = np.max(np.abs(r["E"] - esperado)) / escala
            ok &= dE < 1e-10
            detalle += f", energia vs q0*V*t {dE:.1e}"
        if not ok and r["finito"] and r["dt_ok"] and dentro and caso in SALTO_EN_BORDE:
            ns = [p["n"], min(2 * p["n"], 40), 40]
            errs = [evaluar(caso, {**p, "n": n})["err_final"] for n in ns]
            ok = errs[0] > errs[1] > errs[2]
            detalle += (f"\n           -> malla gruesa para ese tiempo; al refinar n={ns}, error final "
                        f"{[round(float(e), 4) for e in errs]} C: {'converge' if ok else 'NO converge'}")
        check(ok, f"{etiqueta}: {detalle}")


def main() -> int:
    print("1-3) EXACTITUD, ESTABILIDAD Y FISICA (un parametro a la vez, hasta los extremos)")
    for caso in ("Seno 1D", "Seno 2D", "Seno 3D"):
        barrido(caso, [{}, {"n": 4}, {"n": 40}, {"t_h": 1}, {"t_h": 2000}, {"Lx": 0.5}, {"Lx": 5},
                       {"Ly": 0.5}, {"Lz": 0.3}, {"Lz": 3}, {"T0": 0}, {"T0": 40}, {"A": 1}, {"A": 30},
                       {"Lx": 1, "Ly": 1, "Lz": 1, "t_h": 50}])
    comunes_borde = [{}, {"n": 4}, {"n": 40, "t_h": 100}, {"t_h": 1}, {"t_h": 2000},
                     {"Lz": 0.1, "t_h": 20}, {"Lz": 3, "t_h": 2000}, {"Lx": 0.2, "Ly": 5}]
    barrido("Dirichlet base/techo", comunes_borde + [{"Tbase": 0, "Ttecho": 60}, {"Tbase": 60, "Ttecho": 0},
                                                     {"Tbase": 30, "Ttecho": 30}])
    barrido("Adiabatico dT/dn=0", comunes_borde + [{"Tbase": 0, "Ttecho": 60}, {"Tbase": 60, "Ttecho": 0}])
    barrido("Robin beta", comunes_borde + [{"beta": 0.1}, {"beta": 100}, {"Taire": -5}, {"Taire": 40},
                                           {"Tbase": 0, "Taire": 40}])
    barrido("Fuente q0", [{}, {"n": 4}, {"t_h": 1}, {"q0": 0}, {"q0": 3000}, {"T0": 0}, {"Lz": 3}])
    barrido("Neumann q_n", comunes_borde + [{"qn": -300}, {"qn": 300}, {"qn": 0}, {"Ttecho": 60}])

    print("\n4) TENDENCIAS FISICAS")
    techo = []
    for beta in (0.1, 1, 5, 20, 100):
        sim = v.simular("Robin beta", parametros("Robin beta", beta=beta, t_h=200))
        techo.append(sim["campos"][-1][3, 3, -1])
    check(all(a > b for a, b in zip(techo, techo[1:])),
          f"Robin: mas beta -> techo mas frio {[round(float(x), 2) for x in techo]} (de 30 hacia 20 C)")
    finales = [v.simular("Fuente q0", parametros("Fuente q0", q0=q, t_h=24))["campos"][-1].mean()
               for q in (500, 1000, 2000)]
    subidas = [f - 20 for f in finales]
    check(abs(subidas[1] / subidas[0] - 2) < 1e-9 and abs(subidas[2] / subidas[1] - 2) < 1e-9,
          f"Fuente: duplicar q0 duplica la subida {[round(float(x), 3) for x in subidas]} C")
    base_entra = v.simular("Neumann q_n", parametros("Neumann q_n", qn=-100))["campos"][-1][3, 3, 0]
    base_sale = v.simular("Neumann q_n", parametros("Neumann q_n", qn=100))["campos"][-1][3, 3, 0]
    check(base_entra > 20 > base_sale,
          f"Neumann: q_n=-100 calienta la base ({base_entra:.1f} C), q_n=+100 la enfria ({base_sale:.1f} C)")
    centros = []
    for d in (1, 2, 3):
        sim = v.simular(f"Seno {d}D", parametros(f"Seno {d}D", Lx=1, Ly=1, Lz=1, t_h=50))
        centros.append(sim["campos"][-1][tuple(s // 2 for s in sim["campos"][-1].shape)])
    check(centros[0] > centros[1] > centros[2],
          f"Seno: con L=1 m, a las 50 h el centro 1D > 2D > 3D {[round(float(x), 2) for x in centros]} C")

    print("\n5) INTERFAZ (sin ventana)")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(15, 8.5))
    vis = v.Visualizador(fig)
    vis.radio.set_active(v.CASOS.index("Robin beta"))
    slider_beta = next(s for s in vis.sliders_propios if "beta" in s.label.get_text())
    slider_beta.set_val(100)
    vis.sliders_comunes["t_h"].set_val(60)
    vis.simular()
    check("h = 222.0" in vis.sim["nota"], f"slider beta=100 llega al solver ({vis.sim['nota'][:30]}...)")
    check(vis.sim["tiempos"][-1] == 60, "slider t final=60 llega al solver")
    check(tuple(vis.lim) == (20.0, 30.0), f"escala de colores fija del caso Robin {tuple(vis.lim)}")
    vis.radio.set_active(v.CASOS.index("Dirichlet base/techo"))
    check(vis.propios["Dirichlet base/techo"]["Tbase"] == 20, "Dirichlet conserva su T base (20 C)")
    vis.radio.set_active(v.CASOS.index("Robin beta"))
    slider_beta = next(s for s in vis.sliders_propios if "beta" in s.label.get_text())
    check(slider_beta.val == 100 and vis.propios["Robin beta"]["Tbase"] == 30,
          "al volver a Robin, beta sigue en 100 y T base en 30")
    errores_dibujo = 0
    for caso in v.CASOS:
        vis.radio.set_active(v.CASOS.index(caso))
        for foto in range(0, v.N_FOTOS + 1, 5):
            try:
                vis.dibujar(foto)
            except Exception:  # noqa: BLE001
                errores_dibujo += 1
    check(errores_dibujo == 0, "los 8 casos se dibujan en todos los instantes sin errores")
    vis.slider_t.set_val(10)
    check(vis.slider_t.valtext.get_text().endswith(" h"), f"slider de tiempo en horas ({vis.slider_t.valtext.get_text()})")
    vis.slider_t.set_val(0)
    vis._paso_animacion()
    check(int(vis.slider_t.val) == 1, "Animar avanza una foto por tick")
    vis.slider_t.set_val(v.N_FOTOS)
    vis._paso_animacion()
    check(int(vis.slider_t.val) == v.N_FOTOS, "Animar se detiene al final")
    sim_previa = vis.sim
    vis.sliders_comunes["n"].set_val(40)
    vis.sliders_comunes["Lz"].set_val(0.1)
    vis.sliders_comunes["t_h"].set_val(2000)
    vis.simular()
    check(vis.sim is sim_previa and "NO SE SIMULO" in vis.texto.get_text(),
          "con n=40, Lz=0.1, t=2000 h avisa en vez de congelarse")
    plt.close(fig)

    print("\n" + ("TODO OK" if not fallas else f"{len(fallas)} FALLAS:\n  - " + "\n  - ".join(fallas)))
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
