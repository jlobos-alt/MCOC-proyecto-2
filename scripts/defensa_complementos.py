"""Defensa: evidencia complementaria del plan elegido (no reemplaza a defensa_plan.py).

    [A] mecanismo   vertida unica, propuesta y variantes mas lentas en el MISMO escenario:
                    MT(t), T a 25 mm y MDelta(t), y cortes de temperatura en el instante de MDelta
    [B] dt          el plan elegido en su peor escenario con dt = 3600, 1800 y 900 s
    [C] energia     fundacion real aislada (todas las caras adiabaticas), curva real y colocacion
                    por capas: calor almacenado = integral de la fuente, celda por celda
    [E] posterior   el plan elegido hasta 30 dias: que pasa con MDelta despues de los 14 del criterio
    [D] robustez    las comprobaciones de defensa_plan.py rehechas sobre el plan ELEGIDO
                    (antes se habian corrido con la variante EPS 100): profundidad de S25, pesos
                    del clima, solo campana SS, beta de la inversion y los 31 miembros

Usa la misma cadena que scripts/defensa_plan.py (mismo IFC, curvas, clima, plan y solver).
Guarda en results/defensa/complementos/ sin tocar los resultados existentes.

Uso:
    python scripts/defensa_complementos.py                      # A, B, C y E (~2 min)
    python scripts/defensa_complementos.py --partes robustez    # D (~10 min con 8 procesos)
    python scripts/defensa_complementos.py --partes todo
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import defensa_plan as dp  # noqa: E402
from mcplan import build_model, solve  # noqa: E402
from mcplan.curvas import CurvaHidratacion  # noqa: E402
from mcplan.decision import LIM_DT, LIM_T, PlanVertidas, aplicar_plan, duracion_D, metricas  # noqa: E402
from mcplan.environment import aplicar_ambiente  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

TASA = 40.0
DX = 0.5
ELEGIDO = PlanVertidas("unica", 0.0, "EPS150", 10.0)
CASOS = [
    ("Vertida única sin protección, 18 °C", PlanVertidas("unica", 0.0, "ninguna", 18.0), "#8a8a8a"),
    ("Propuesta: única, EPS 150, 10 °C", ELEGIDO, "#e76f51"),
    ("5 vertidas, espera 6 h, EPS 150, 10 °C", PlanVertidas("5", 6.0, "EPS150", 10.0), "#2a9d8f"),
    ("5 vertidas, espera 48 h, EPS 150, 10 °C", PlanVertidas("5", 48.0, "EPS150", 10.0), "#264653"),
]


def correr_detalle(plan, curva, clima_frame, dx=DX, dt_s=None, adiabatico=False, campos=True, horizonte_h=None):
    """Igual que defensa_plan.correr, pero devuelve el resultado completo y el modelo."""
    ctx = dp._ctx(dx)
    D = duracion_D(plan, ctx["volumenes"], TASA)
    H = horizonte_h or max(336.0, D + 240.0)
    p = aplicar_plan(ctx["base"], plan, ctx["volumenes"], TASA)
    p.simulacion.duracion_h = H
    meta = getattr(curva, "metadatos", {}) or {}
    if "rho" in meta and "cp" in meta:
        mat = p.materiales["M1"]
        p.materiales["M1"] = type(mat)(name=mat.name, k=mat.k, cp=float(meta["cp"]), rho=float(meta["rho"]))
    if adiabatico:
        for f in p.fronteras:
            f.tipo = "adiabatica"
    else:
        tl = dp.timeline(ctx, clima_frame, H)
        aplicar_ambiente(p, tl, con_viento=True, con_radiacion=True,
                         absorptivity=dp.ABSORTIVIDAD, emissivity=dp.EMISIVIDAD)
    modelo = build_model(p, voxeles=ctx["vox"][plan.particion])
    modelo.hydration = curva
    instantes = np.arange(0.0, H + 1e-9, 1.0) if campos else None
    r = solve(modelo, duracion_h=H, intervalo_salida_h=1.0, dt_s=dt_s,
              factor_estabilidad=p.simulacion.factor_estabilidad, instantes_campo_h=instantes)
    return r, modelo, p, D, H


def peor_escenario(plan_nombre: str):
    """Curva y clima con el MDelta mas alto del plan en results/defensa/corridas.csv (malla 0,5 m)."""
    with open(ROOT / "results" / "defensa" / "corridas.csv", encoding="utf-8") as h:
        filas = [f for f in csv.DictReader(h) if f["plan"] == plan_nombre and float(f["dx"]) == DX]
    peor = max(filas, key=lambda f: float(f["MDelta"]))
    ctx = dp._ctx(DX)
    m = [c.nombre for c in ctx["curvas"]].index(peor["curva"])
    k = [e["etiqueta"] for e in ctx["esc"]["escenarios"]].index(peor["clima"])
    return m, k, float(peor["MDelta"])


# --------------------------------------------------------------------------- [A] mecanismo
def parte_mecanismo(out: Path, resumen: dict) -> None:
    print("\n[A] Mecanismo: mismos datos y recursos, escenario más desfavorable de la propuesta")
    ctx = dp._ctx(DX)
    m, k, md_csv = peor_escenario(ELEGIDO.nombre)
    curva, clima = ctx["curvas"][m], ctx["climas"][k]
    etiqueta_clima = ctx["esc"]["escenarios"][k]["etiqueta"]
    print(f"    Escenario: curva {curva.nombre}, clima {etiqueta_clima} (MΔ de la propuesta en corridas.csv: {md_csv:.2f} °C)")
    filas, series, cortes = [], [], []
    for nombre, plan, color in CASOS:
        r, modelo, p, D, H = correr_detalle(plan, curva, clima)
        met = metricas(r)
        t_md = met["t_MDelta"]
        filas.append({"caso": nombre, "plan": plan.nombre, "D_h": round(D, 2), "MT_C": round(met["MT"], 2),
                      "t_MT_h": met["t_MT"], "MDelta_C": round(met["MDelta"], 2), "t_MDelta_h": t_md,
                      "cumple": bool(met["MT"] <= LIM_T and met["MDelta"] <= LIM_DT)})
        series.append((nombre, color, D, np.asarray(r.time_h), np.asarray(r.T_max_global),
                       np.asarray(r.T_min_s25), np.asarray(r.delta_T_s25)))
        t_campo = min(r.campos, key=lambda t: abs(t - t_md))
        cortes.append((nombre, t_campo, r.campos[t_campo], modelo.grid, met["MDelta"]))
        print(f"    {nombre:<42} D = {D:6.1f} h   MT = {met['MT']:5.1f} °C ({met['t_MT']:.0f} h)   "
              f"MΔ = {met['MDelta']:5.1f} °C ({t_md:.0f} h)")
    resumen["mecanismo"] = {"curva": curva.nombre, "clima": etiqueta_clima, "casos": filas}

    fig, ejes = plt.subplots(1, 3, figsize=(15, 4.6))
    for nombre, color, D, t, MT, T25, MD in series:
        for ax, y in zip(ejes, (MT, T25, MD)):
            ax.plot(t, y, color=color, lw=1.6, label=nombre)
        ejes[2].axvline(D, color=color, lw=0.8, ls=":")
    ejes[0].axhline(LIM_T, color="k", lw=1, ls="--")
    ejes[2].axhline(LIM_DT, color="k", lw=1, ls="--")
    ejes[0].set(title="T máx del hormigón colocado", ylabel="T [°C]")
    ejes[1].set(title="T mín a 25 mm bajo las caras existentes (S25)", ylabel="T [°C]")
    ejes[2].set(title="MΔ(t) = T máx − T mín S25 (punteado: fin de colocación)", ylabel="ΔT [°C]")
    for ax in ejes:
        ax.set_xlabel("t desde t0 [h]")
        ax.set_xlim(0, 336)
        ax.grid(alpha=0.3)
    ejes[0].legend(fontsize=8, loc="lower right")
    fig.suptitle(f"Mismo escenario para los 4 casos: curva {curva.nombre}, clima {etiqueta_clima}, malla 0,5 m", y=1.0)
    fig.tight_layout()
    fig.savefig(out / "mecanismo_series.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, ejes = plt.subplots(2, 2, figsize=(12, 6.2), sharex=True, sharey=True)
    for ax, (nombre, t_campo, T, grid, md) in zip(ejes.ravel(), cortes):
        _, y, _ = grid.centers()
        j = int(np.argmin(np.abs(y)))
        extent = (grid.x0, grid.x0 + grid.nx * grid.dx, grid.z0, grid.z0 + grid.nz * grid.dz)
        im = ax.imshow(T[:, j, :].T, origin="lower", extent=extent, cmap="inferno", vmin=0, vmax=60, aspect="auto")
        ax.set_title(f"{nombre}\nt = {t_campo:.0f} h, instante de MΔ = {md:.1f} °C", fontsize=9)
        ax.set_facecolor("#e8e8e8")
    fig.supxlabel("x [m] (corte en y = 0)")
    fig.supylabel("z [m]")
    fig.colorbar(im, ax=ejes, fraction=0.025, pad=0.02, label="T [°C] (gris: sin hormigón)")
    fig.savefig(out / "mecanismo_cortes.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"    Figuras: {out / 'mecanismo_series.png'}, {out / 'mecanismo_cortes.png'}")


# --------------------------------------------------------------------------- [B] paso temporal
def parte_dt(out: Path, resumen: dict) -> None:
    print("\n[B] Sensibilidad temporal del plan elegido (peor escenario, malla 0,5 m)")
    ctx = dp._ctx(DX)
    m, k, _ = peor_escenario(ELEGIDO.nombre)
    filas = []
    for dt in (3600.0, 1800.0, 900.0):
        r, *_ = correr_detalle(ELEGIDO, ctx["curvas"][m], ctx["climas"][k], dt_s=dt, campos=False)
        met = metricas(r)
        filas.append({"dt_s": dt, "MT_C": round(met["MT"], 3), "MDelta_C": round(met["MDelta"], 3)})
        print(f"    dt = {dt:6.0f} s   MT = {met['MT']:.3f} °C   MΔ = {met['MDelta']:.3f} °C")
    base = filas[-1]
    for f in filas:
        f["dif_MDelta_vs_900s_C"] = round(f["MDelta_C"] - base["MDelta_C"], 3)
        f["dif_MT_vs_900s_C"] = round(f["MT_C"] - base["MT_C"], 3)
    resumen["sensibilidad_dt"] = {"curva": ctx["curvas"][m].nombre,
                                  "clima": ctx["esc"]["escenarios"][k]["etiqueta"], "corridas": filas}
    print(f"    Diferencia de MΔ entre 3600 s y 900 s: {filas[0]['dif_MDelta_vs_900s_C']:+.3f} °C")


# --------------------------------------------------------------------------- [C] energia
def parte_energia(out: Path, resumen: dict) -> None:
    print("\n[C] Balance de energía en la fundación real aislada (plan elegido, colocación por capas)")
    ctx = dp._ctx(DX)
    m, _, _ = peor_escenario(ELEGIDO.nombre)
    curva = ctx["curvas"][m]
    filas = []
    for dt in (3600.0, 900.0, 225.0):
        r, modelo, p, D, H = correr_detalle(ELEGIDO, curva, None, dt_s=dt, adiabatico=True, campos=False)
        V = modelo.grid.cell_volume
        activa = np.isfinite(modelo.place_time) & modelo.mask
        rho_cp = modelo.rho_cp_flat[activa]
        esperado = float(np.sum(rho_cp * V * curva.theta(H - modelo.place_time[activa])))   # integral de la fuente
        almacenado = float(np.sum(rho_cp * V * (r.T_final.ravel()[activa] - ELEGIDO.t_col_C)))  # rho cp V (T - T_col)
        error = abs(almacenado - esperado) / esperado
        filas.append({"dt_s": dt, "calor_generado_GJ": round(esperado / 1e9, 6),
                      "calor_almacenado_GJ": round(almacenado / 1e9, 6), "error_relativo": error})
        print(f"    dt = {dt:6.0f} s   generado {esperado / 1e9:.6f} GJ   almacenado {almacenado / 1e9:.6f} GJ   "
              f"error {error:.2e}")
    print("    La diferencia es la fraccion de paso entre que llega el hormigon y el paso en que la celda nace:")
    print("    baja con dt (orden 1). Sin colocacion por capas, en las pruebas el cierre es exacto (< 1e-9).")
    resumen["energia_adiabatica"] = {"curva": curva.nombre, "H_h": H, "celdas": int(activa.sum()), "corridas": filas}


# --------------------------------------------------------------------------- [E] despues del dia 14
def parte_posterior(out: Path, resumen: dict) -> None:
    print("\n[E] Plan elegido hasta 30 días (el criterio son 14; la aislación no se retira)")
    ctx = dp._ctx(DX)
    m, k, _ = peor_escenario(ELEGIDO.nombre)
    r, *_ = correr_detalle(ELEGIDO, ctx["curvas"][m], ctx["climas"][k], campos=False, horizonte_h=720.0)
    t, md, mt = np.asarray(r.time_h), np.asarray(r.delta_T_s25), np.asarray(r.T_max_global)
    filas = []
    for corte in (336, 480, 600, 720):
        sel = t <= corte
        i = int(np.nanargmax(md[sel]))
        filas.append({"hasta_h": corte, "MDelta_max_C": round(float(md[sel][i]), 2), "t_h": float(t[sel][i]),
                      "T_max_al_corte_C": round(float(mt[sel][-1]), 2)})
        print(f"    hasta {corte:4d} h: MΔ máx {md[sel][i]:5.2f} °C a las {t[sel][i]:.0f} h; "
              f"T máx a esa hora {mt[sel][-1]:.1f} °C")
    resumen["posterior_30d"] = {"curva": ctx["curvas"][m].nombre, "clima": ctx["esc"]["escenarios"][k]["etiqueta"],
                                "nota": "Clima despues del ensemble: ERA5 2025 (climatologia). Malla 0,5 m.",
                                "cortes": filas}
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(t, md, color="#e76f51", label="MΔ(t), propuesta con EPS 150 permanente")
    ax.axhline(LIM_DT, color="k", lw=1, ls="--", label="20 °C")
    ax.axvline(336, color="#8a8a8a", lw=1, ls=":", label="fin de los 14 días del criterio")
    ax.set(xlabel="t desde t0 [h]", ylabel="ΔT [°C]", title="Después del día 14 el diferencial sigue subiendo (malla 0,5 m)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "posterior_30d.png", dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------------- [D] robustez
def _tarea_31(args):
    m, nombre, dx = args
    import json as _json
    ctx = dp._ctx(dx)
    esc = ctx["esc"]
    ens_raw = _json.loads((dp.CLIMA / esc["ensemble"] / "raw.json").read_text(encoding="utf-8"))
    from mcplan.escenarios_clima import miembro
    frame = miembro(ens_raw, nombre, "gfs_seamless", "")
    r = dp.correr(ELEGIDO, ctx["curvas"][m], frame, dx, TASA)
    return {"curva": ctx["curvas"][m].nombre, "miembro": nombre, "MT": r["MT"], "MDelta": r["MDelta"],
            "falla": bool(r["MT"] > LIM_T or r["MDelta"] > LIM_DT)}


def _tarea_beta(args):
    m, k, i, dx = args
    ctx = dp._ctx(dx)
    c = ctx["curvas"][m]
    tot = c.metadatos["totales_MJ_m3"]
    escalada = CurvaHidratacion(c.nombre, c.edad_h, c.theta_C * tot[i] / tot[1], c.metadatos)
    r = dp.correr(ELEGIDO, escalada, ctx["climas"][k], dx, TASA)
    return {"i": i, "m": m, "k": k, "MT": r["MT"], "MDelta": r["MDelta"]}


def parte_robustez(out: Path, resumen: dict, procesos: int) -> None:
    print(f"\n[D] Robustez del plan ELEGIDO ({ELEGIDO.nombre}), malla 0,5 m, {procesos} procesos")
    ctx = dp._ctx(DX)
    esc = ctx["esc"]
    etiquetas = [e["etiqueta"] for e in esc["escenarios"]]
    rob = {}
    with open(ROOT / "results" / "defensa" / "corridas.csv", encoding="utf-8") as h:
        corr = [f for f in csv.DictReader(h) if f["plan"] == ELEGIDO.nombre and float(f["dx"]) == DX]
    for f in corr:
        f["falla"] = float(f["MT"]) > LIM_T or float(f["MDelta"]) > LIM_DT
    pesos = {}
    for nombre_p, qk in [("declarados", ctx["pesos_k"]), ("iguales", [1 / 3] * 3), ("todo_frio", [1, 0, 0]),
                         ("todo_medio", [0, 1, 0]), ("todo_calido", [0, 0, 1])]:
        pesos[nombre_p] = round(sum(ctx["pesos_m"][[c.nombre for c in ctx["curvas"]].index(f["curva"])]
                                    * qk[etiquetas.index(f["clima"])] for f in corr if f["falla"]), 4)
    rob["pesos_clima_P_f"] = pesos
    ss = [c.nombre for c in ctx["curvas"] if (c.metadatos or {}).get("campana") == "SS"]
    rob["solo_SS_P_f"] = round(sum(ctx["pesos_k"][etiquetas.index(f["clima"])] / len(ss)
                                   for f in corr if f["curva"] in ss and f["falla"]), 4)
    print(f"    Pesos del clima -> P_f: {pesos}; solo campaña SS -> P_f: {rob['solo_SS_P_f']}")

    prof = {}
    for d in (0.025, 0.05, ctx["vox"]["5"].grid.dz / 2):
        ev, _ = dp.evaluar([ELEGIDO], DX, TASA, procesos, profundidad=d)
        prof[f"{d * 1000:.0f} mm"] = {"P_f": round(ev[0].P_f, 4),
                                     "MDelta_max_C": round(max(c["MDelta"] for c in ev[0].corridas), 2)}
        print(f"    S25 a {d * 1000:4.0f} mm: P_f {ev[0].P_f:.3f}, MΔ máx {prof[f'{d * 1000:.0f} mm']['MDelta_max_C']:.2f} °C")
    rob["profundidad_S25"] = prof

    tareas = [(m, k, i, DX) for i in (0, 2) for m in range(len(ctx["curvas"])) for k in range(len(ctx["climas"]))]
    with Pool(procesos) as pool:
        res = pool.map(_tarea_beta, tareas, chunksize=1)
    beta = {}
    for i, nombre_b in ((0, "beta_2.1"), (2, "beta_3.0")):
        sel = [x for x in res if x["i"] == i]
        beta[nombre_b] = {"P_f": round(sum(ctx["pesos_m"][x["m"]] * ctx["pesos_k"][x["k"]] for x in sel
                                           if x["MT"] > LIM_T or x["MDelta"] > LIM_DT), 4),
                          "MDelta_max_C": round(max(x["MDelta"] for x in sel), 2),
                          "MT_max_C": round(max(x["MT"] for x in sel), 2)}
    rob["beta_inversion"] = beta
    print(f"    β de la inversión: {beta}")

    ens_raw = json.loads((dp.CLIMA / esc["ensemble"] / "raw.json").read_text(encoding="utf-8"))
    from mcplan.escenarios_clima import nombres_miembros
    nombres = nombres_miembros(ens_raw)
    with Pool(procesos) as pool:
        res31 = pool.map(_tarea_31, [(m, n, DX) for m in range(len(ctx["curvas"])) for n in nombres], chunksize=1)
    with open(out / "elegido_31_miembros.csv", "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(res31[0]))
        w.writeheader()
        w.writerows(res31)
    frac = sum(ctx["pesos_m"][[c.nombre for c in ctx["curvas"]].index(x["curva"])] / len(nombres)
               for x in res31 if x["falla"])
    rob["miembros_31"] = {"corridas": len(res31), "P_f_equiprobable": round(frac, 4),
                          "MDelta_min_C": round(min(x["MDelta"] for x in res31), 2),
                          "MDelta_max_C": round(max(x["MDelta"] for x in res31), 2),
                          "MT_max_C": round(max(x["MT"] for x in res31), 2)}
    print(f"    31 miembros × {len(ctx['curvas'])} curvas: P_f {frac:.3f}, MΔ "
          f"{rob['miembros_31']['MDelta_min_C']:.2f}..{rob['miembros_31']['MDelta_max_C']:.2f} °C")
    resumen["robustez_elegido"] = rob


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--partes", default="mecanismo,dt,energia,posterior",
                    help="mecanismo, dt, energia, posterior, robustez o todo (separadas por coma)")
    ap.add_argument("--procesos", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--salida", type=Path, default=ROOT / "results" / "defensa" / "complementos")
    args = ap.parse_args()
    partes = ({"mecanismo", "dt", "energia", "posterior", "robustez"} if args.partes == "todo"
              else set(args.partes.split(",")))
    out = args.salida
    out.mkdir(parents=True, exist_ok=True)
    ruta_json = out / "complementos.json"
    resumen = json.loads(ruta_json.read_text(encoding="utf-8")) if ruta_json.exists() else {}
    inicio = time.perf_counter()
    if dp._ctx(DX)["provisoria"]:
        raise SystemExit("Faltan las 8 curvas reales en datos/curvas_hidratacion: no se corre con la curva provisoria.")
    if "mecanismo" in partes:
        parte_mecanismo(out, resumen)
    if "dt" in partes:
        parte_dt(out, resumen)
    if "energia" in partes:
        parte_energia(out, resumen)
    if "posterior" in partes:
        parte_posterior(out, resumen)
    if "robustez" in partes:
        parte_robustez(out, resumen, args.procesos)
    resumen["plan_elegido"] = ELEGIDO.nombre
    ruta_json.write_text(json.dumps(resumen, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"\nResultados en {out} ({time.perf_counter() - inicio:.0f} s)")


if __name__ == "__main__":
    main()
