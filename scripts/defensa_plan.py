"""Defensa (19-nov): el plan mas rapido con P_f <= 5 % bajo el modelo de incertidumbre declarado.

    [1] escenarios: curvas de hidratacion (datos/curvas_hidratacion) x 3 historias de clima
        (miembros del ensemble GFS guardados en datos/forecast_defensa), con sus pesos
    [2] familia de planes: particion (5 vertidas del IFC o vertida unica) x espera x proteccion x T_col
        con capacidad de colocacion declarada (d_j = V_j / r) -> D(u)
    [3] corrida de cada plan en cada escenario: MT y MDelta (Omega_c, S25 a 25 mm), 14 d y ventana extendida
    [4] P_f conjunta y marginales por enumeracion ponderada; plan mas rapido con P_f <= 5 %
    [5] comprobaciones del plan elegido y sus competidores: malla fina, profundidad de S25, pesos,
        los 31 miembros del ensemble
    [6] tablas, figuras y resumen en results/defensa/

Uso:
    python scripts/defensa_plan.py                 # todo (~10 min con 8 procesos y una curva)
    python scripts/defensa_plan.py --rapido        # familia reducida, sin comprobaciones
Sin las 8 curvas reales en datos/curvas_hidratacion/ usa la curva C1 PROVISORIA y lo dice.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import sys
import time
from dataclasses import asdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan import build_model, dz_que_calza, extraer_solidos, load_plan, plan_desde_solidos, solve, voxelizar  # noqa: E402
from mcplan.curvas import cargar_curvas, curva_provisoria_c1  # noqa: E402
from mcplan.decision import (  # noqa: E402
    LIM_DT, LIM_T, PROTECCIONES, Evaluacion, PlanVertidas, aplicar_plan, duracion_D, mas_rapido_factible, metricas,
)
from mcplan.environment import aplicar_ambiente  # noqa: E402
from mcplan.escenarios_clima import miembro  # noqa: E402
from mcplan.meteo import assemble_timeline  # noqa: E402
from mcplan.snapshots import load_snapshot, verify  # noqa: E402
from mcplan.voxel import Voxelizacion  # noqa: E402

CLIMA = ROOT / "datos" / "forecast_defensa"
CURVAS = ROOT / "datos" / "curvas_hidratacion"
PLANTILLA = ROOT / "datos" / "fundacion_e12.yaml"
ABSORTIVIDAD, EMISIVIDAD = 0.6, 0.9
HORAS_27NOV_MENOS_T0 = 188.0      # 19-nov 08:00 -> 27-nov 04:00: la fase del suelo de E12 se corre

_CTX: dict = {}


# --------------------------------------------------------------------------- contexto
def leer_escenarios_clima() -> dict:
    ruta = sorted((CLIMA / "escenarios").glob("*.json"))[-1]
    return {"ruta": ruta, **json.loads(ruta.read_text(encoding="utf-8"))}


def leer_curvas(rho_cp: float):
    curvas = cargar_curvas(CURVAS, rho_cp)
    if curvas:
        pesos = [c.metadatos.get("peso") for c in curvas]
        if any(p is None for p in pesos):
            pesos = [1.0 / len(curvas)] * len(curvas)
        return curvas, [float(p) for p in pesos], False
    return [curva_provisoria_c1(rho_cp)], [1.0], True


def preparar(dx: float) -> dict:
    plantilla = load_plan(str(PLANTILLA))
    plantilla.suelo.phase_h += HORAS_27NOV_MENOS_T0
    esc = leer_escenarios_clima()
    relleno = load_snapshot(CLIMA, esc["relleno"])[0]
    solidos = sorted(extraer_solidos(ROOT / "geometry" / "foundation.ifc"), key=lambda s: float(s.verts[:, 2].min()))
    vox5 = voxelizar(solidos, dx=dx, dz=dz_que_calza(solidos, dx))
    vox1 = Voxelizacion(grid=vox5.grid, vertida_id=np.where(vox5.vertida_id >= 0, 1, -1), solidos=solidos)
    mat = plantilla.materiales["M1"]
    curvas, pesos_m, provisoria = leer_curvas(mat.rho * mat.cp)
    climas = [load_snapshot(CLIMA, e["snapshot_id"])[0] for e in esc["escenarios"]]
    return {"plantilla": plantilla, "esc": esc, "relleno": relleno, "solidos": solidos,
            "base": plan_desde_solidos(plantilla, solidos, dx), "vox": {"5": vox5, "unica": vox1},
            "volumenes": [s.volumen for s in solidos], "curvas": curvas, "pesos_m": pesos_m,
            "provisoria": provisoria, "climas": climas, "pesos_k": [e["peso"] for e in esc["escenarios"]], "dx": dx}


def _ctx(dx: float) -> dict:
    if _CTX.get("dx") != dx:
        _CTX.clear()
        _CTX.update(preparar(dx))
    return _CTX


def timeline(ctx: dict, frame, horas: float):
    return assemble_timeline(ctx["esc"]["t0_local"], np.arange(0.0, horas + 1e-9, 1.0).tolist(),
                             forecast=frame, climatology=ctx["relleno"])


def correr(plan: PlanVertidas, curva, clima_frame, dx: float, tasa: float, profundidad: float = 0.025) -> dict:
    ctx = _ctx(dx)
    D = duracion_D(plan, ctx["volumenes"], tasa)
    H = max(336.0, D + 240.0)
    p = aplicar_plan(ctx["base"], plan, ctx["volumenes"], tasa)
    p.simulacion.duracion_h = H
    tl = timeline(ctx, clima_frame, H)
    aplicar_ambiente(p, tl, con_viento=True, con_radiacion=True, absorptivity=ABSORTIVIDAD, emissivity=EMISIVIDAD)
    modelo = build_model(p, voxeles=ctx["vox"][plan.particion])
    modelo.hydration = curva
    r = solve(modelo, duracion_h=H, intervalo_salida_h=1.0, factor_estabilidad=p.simulacion.factor_estabilidad,
              profundidad_s25_m=profundidad)
    fuentes = tl.sources
    return {"D_h": D, "H_h": H, "dt_s": r.dt_s, "horas_clima": fuentes, **metricas(r)}


def _tarea(args) -> dict:
    plan_d, m, k, dx, tasa, profundidad = args
    ctx = _ctx(dx)
    plan = PlanVertidas(**plan_d)
    res = correr(plan, ctx["curvas"][m], ctx["climas"][k], dx, tasa, profundidad)
    return {"plan": plan.nombre, **plan_d, "curva": ctx["curvas"][m].nombre,
            "clima": ctx["esc"]["escenarios"][k]["etiqueta"], "peso": ctx["pesos_m"][m] * ctx["pesos_k"][k],
            "dx": dx, "profundidad_m": profundidad, **res}


def evaluar(planes: list[PlanVertidas], dx: float, tasa: float, procesos: int, profundidad: float = 0.025):
    ctx = _ctx(dx)
    tareas = [(asdict(p), m, k, dx, tasa, profundidad)
              for p in planes for m in range(len(ctx["curvas"])) for k in range(len(ctx["climas"]))]
    if procesos > 1:
        with Pool(procesos) as pool:
            filas = pool.map(_tarea, tareas, chunksize=1)
    else:
        filas = [_tarea(t) for t in tareas]
    evals = []
    for p in planes:
        corr = [f for f in filas if f["plan"] == p.nombre]
        evals.append(Evaluacion(p, corr[0]["D_h"], corr))
    return evals, filas


# --------------------------------------------------------------------------- salidas
def fila_plan(e: Evaluacion) -> dict:
    MT = [c["MT"] for c in e.corridas]
    MD = [c["MDelta"] for c in e.corridas]
    return {"plan": e.plan.nombre, "particion": e.plan.particion, "espera_h": e.plan.espera_h,
            "proteccion": e.plan.proteccion, "t_col_C": e.plan.t_col_C, "D_h": round(e.D_h, 2),
            "P_f": round(e.P_f, 4), "P_MT": round(e.P_MT, 4), "P_MDelta": round(e.P_MDelta, 4),
            "MT_max_C": round(max(MT), 2), "MDelta_min_C": round(min(MD), 2), "MDelta_max_C": round(max(MD), 2),
            "cumple": e.cumple}


def guardar_csv(filas: list[dict], ruta: Path) -> None:
    with open(ruta, "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows([{k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in f.items()} for f in filas])


def familia(rapido: bool, esperas, protecciones, tcols) -> list[PlanVertidas]:
    planes = []
    for prot in protecciones:
        for tc in tcols:
            planes.append(PlanVertidas("unica", 0.0, prot, tc))
            for w in esperas:
                planes.append(PlanVertidas("5", float(w), prot, tc))
    return planes


# --------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasa", type=float, default=40.0, help="capacidad de colocacion r [m3/h] (una bomba)")
    ap.add_argument("--dx", type=float, default=0.5)
    ap.add_argument("--dx-fino", type=float, default=0.25)
    ap.add_argument("--esperas", type=float, nargs="+", default=[0, 6, 12, 24, 48])
    ap.add_argument("--protecciones", nargs="+", default=list(PROTECCIONES))
    ap.add_argument("--tcol", type=float, nargs="+", default=[18.0, 10.0])
    ap.add_argument("--procesos", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--rehacer-figuras", action="store_true", help="figuras desde corridas.csv, sin simular")
    ap.add_argument("--salida", type=Path, default=ROOT / "results" / "defensa")
    args = ap.parse_args()
    out = args.salida
    out.mkdir(parents=True, exist_ok=True)
    inicio = time.perf_counter()

    if args.rehacer_figuras:
        ctx = _ctx(args.dx)
        with open(out / "corridas.csv", encoding="utf-8") as h:
            filas = list(csv.DictReader(h))
        evals = {}
        for f in filas:
            plan = PlanVertidas(f["particion"], float(f["espera_h"]), f["proteccion"], float(f["t_col_C"]))
            e = evals.setdefault(plan.nombre, Evaluacion(plan, float(f["D_h"])))
            e.corridas.append({"peso": float(f["peso"]), "MT": float(f["MT"]), "MDelta": float(f["MDelta"])})
        resumen = json.loads((out / "resumen_defensa.json").read_text(encoding="utf-8"))
        figuras(ctx, list(evals.values()), evals[resumen["foco"]], args, out)
        print(f"Figuras regeneradas en {out}")
        return

    print("[1] Escenarios")
    print(f"    Snapshots verificados: {len(verify(CLIMA))}")
    ctx = _ctx(args.dx)
    esc = ctx["esc"]
    print(f"    t0 = {esc['t0_local']} ({esc['zona_horaria']}); clima: {esc['ruta'].name}")
    for e in esc["escenarios"]:
        print(f"      clima {e['etiqueta']:<7} {e['miembro']:<9} peso {e['peso']:.3f}  T media {e['T_media_ventana_C']:.2f} °C")
    for c, p in zip(ctx["curvas"], ctx["pesos_m"]):
        print(f"      curva {c.nombre:<14} peso {p:.3f}  θ final {c.theta_final_C:.1f} °C  {'; '.join(c.avisos)}")
    if ctx["provisoria"]:
        print("    AVISO: faltan las 8 curvas reales; se usa C1 PROVISORIA. El resultado no es la decision final.")
    print(f"    Escenarios por plan: {len(ctx['curvas']) * len(ctx['climas'])}; capacidad r = {args.tasa:g} m³/h; "
          f"V total = {sum(ctx['volumenes']):.1f} m³ -> {sum(ctx['volumenes']) / args.tasa:.1f} h de colocacion")

    esperas = [0, 24] if args.rapido else args.esperas
    planes = familia(args.rapido, esperas, args.protecciones, [18.0] if args.rapido else args.tcol)
    print(f"\n[2-3] Familia: {len(planes)} planes x {len(ctx['curvas']) * len(ctx['climas'])} escenarios, malla {args.dx:g} m")
    t1 = time.perf_counter()
    evals, filas = evaluar(planes, args.dx, args.tasa, args.procesos)
    print(f"    {len(filas)} corridas en {time.perf_counter() - t1:.0f} s")
    guardar_csv(filas, out / "corridas.csv")
    tabla = sorted((fila_plan(e) for e in evals), key=lambda f: (f["D_h"], f["P_f"]))
    guardar_csv(tabla, out / "planes.csv")

    print("\n[4] Planes ordenados por D")
    print(f"    {'plan':<34}{'D [h]':>7}{'P_f':>7}{'P_MT':>7}{'P_MΔ':>7}{'MT max':>8}{'MΔ min..max':>14}")
    for f in tabla:
        print(f"    {f['plan']:<34}{f['D_h']:>7.1f}{f['P_f']:>7.2f}{f['P_MT']:>7.2f}{f['P_MDelta']:>7.2f}"
              f"{f['MT_max_C']:>8.1f}{f['MDelta_min_C']:>7.1f}..{f['MDelta_max_C']:<6.1f}{'  CUMPLE' if f['cumple'] else ''}")
    elegido = mas_rapido_factible(evals)
    resumen = {"t0_local": esc["t0_local"], "tasa_m3_h": args.tasa, "dx_m": args.dx, "curvas_provisorias": ctx["provisoria"],
               "curvas": [c.nombre for c in ctx["curvas"]], "pesos_curvas": ctx["pesos_m"],
               "clima": esc["escenarios"], "planes": tabla}
    if elegido is None:
        mejor = min(evals, key=lambda e: (e.P_f, max(c["MDelta"] for c in e.corridas), e.D_h))
        print(f"\n    NINGUN plan de la familia cumple P_f <= 5 %. El de menor riesgo: {mejor.plan.nombre} "
              f"(P_f = {mejor.P_f:.2f}, MΔ min {min(c['MDelta'] for c in mejor.corridas):.1f} °C).")
        resumen["elegido"] = None
        resumen["menor_riesgo"] = fila_plan(mejor)
        foco = mejor
    else:
        print(f"\n    Plan mas rapido que cumple: {elegido.plan.nombre}  D = {elegido.D_h:.1f} h  P_f = {elegido.P_f:.3f}")
        resumen["elegido"] = fila_plan(elegido)
        foco = elegido

    if not args.rapido:
        print("\n[5] Comprobaciones del plan foco y sus competidores")
        competidores = sorted(evals, key=lambda e: e.D_h)
        idx = [e.plan.nombre for e in competidores].index(foco.plan.nombre)
        vecinos = {foco.plan.nombre: foco}
        for e in competidores[max(0, idx - 2): idx + 3]:
            vecinos[e.plan.nombre] = e
        finos, filas_finas = evaluar([e.plan for e in vecinos.values()], args.dx_fino, args.tasa, args.procesos)
        guardar_csv(filas_finas, out / "corridas_malla_fina.csv")
        malla = []
        for e in finos:
            g = vecinos[e.plan.nombre]
            malla.append({"plan": e.plan.nombre, "D_h": round(e.D_h, 2),
                          f"P_f_dx{args.dx:g}": round(g.P_f, 4), f"P_f_dx{args.dx_fino:g}": round(e.P_f, 4),
                          f"MDelta_max_dx{args.dx:g}": round(max(c["MDelta"] for c in g.corridas), 2),
                          f"MDelta_max_dx{args.dx_fino:g}": round(max(c["MDelta"] for c in e.corridas), 2),
                          f"MT_max_dx{args.dx:g}": round(max(c["MT"] for c in g.corridas), 2),
                          f"MT_max_dx{args.dx_fino:g}": round(max(c["MT"] for c in e.corridas), 2)})
            print(f"    malla {e.plan.nombre:<34} P_f {g.P_f:.2f} -> {e.P_f:.2f}   MΔ max "
                  f"{max(c['MDelta'] for c in g.corridas):.1f} -> {max(c['MDelta'] for c in e.corridas):.1f} °C")
        resumen["malla"] = malla
        # Profundidad de S25: 25 mm contra 50 mm y centro de celda (dz/2)
        prof = {}
        for d in (0.025, 0.05, ctx["vox"]["5"].grid.dz / 2):
            ev, _ = evaluar([foco.plan], args.dx, args.tasa, args.procesos, profundidad=d)
            prof[f"{d * 1000:.0f} mm"] = {"P_f": round(ev[0].P_f, 4),
                                         "MDelta_max_C": round(max(c["MDelta"] for c in ev[0].corridas), 2)}
            print(f"    S25 a {d * 1000:5.0f} mm: P_f {ev[0].P_f:.2f}, MΔ max {max(c['MDelta'] for c in ev[0].corridas):.1f} °C")
        resumen["profundidad_S25"] = prof
        # Pesos: iguales y todo el peso en cada historia
        pesos = {}
        for nombre_peso, qk in [("declarados", ctx["pesos_k"]), ("iguales", [1 / 3] * 3),
                                ("todo_frio", [1, 0, 0]), ("todo_calido", [0, 0, 1])]:
            pf = sum(c["peso"] / ctx["pesos_k"][[e["etiqueta"] for e in esc["escenarios"]].index(c["clima"])] * qk[
                [e["etiqueta"] for e in esc["escenarios"]].index(c["clima"])]
                for c in foco.corridas if c["MT"] > LIM_T or c["MDelta"] > LIM_DT)
            pesos[nombre_peso] = round(pf, 4)
        resumen["sensibilidad_pesos_clima"] = pesos
        print(f"    pesos del clima -> P_f: {pesos}")
        # Los 31 miembros del ensemble (la reduccion a 3 historias pierde extremos)
        ens_raw = json.loads((CLIMA / esc["ensemble"] / "raw.json").read_text(encoding="utf-8"))
        from mcplan.escenarios_clima import nombres_miembros
        nombres = nombres_miembros(ens_raw)
        frames = [miembro(ens_raw, n, "gfs_seamless", "") for n in nombres]
        ctx_m = _ctx(args.dx)
        res31 = []
        for m, curva in enumerate(ctx_m["curvas"]):
            for n, fr in zip(nombres, frames):
                r = correr(foco.plan, curva, fr, args.dx, args.tasa)
                res31.append({"curva": curva.nombre, "miembro": n, "MT": r["MT"], "MDelta": r["MDelta"],
                              "falla": bool(r["MT"] > LIM_T or r["MDelta"] > LIM_DT)})
        guardar_csv(res31, out / "plan_foco_31_miembros.csv")
        frac = sum(ctx_m["pesos_m"][[c.nombre for c in ctx_m["curvas"]].index(r["curva"])] / len(nombres)
                   for r in res31 if r["falla"])
        resumen["plan_foco_31_miembros"] = {"P_f_equiprobable": round(frac, 4),
                                           "MDelta_min_C": round(min(r["MDelta"] for r in res31), 2),
                                           "MDelta_max_C": round(max(r["MDelta"] for r in res31), 2)}
        print(f"    31 miembros, plan foco: P_f {frac:.2f}, MΔ {min(r['MDelta'] for r in res31):.1f}.."
              f"{max(r['MDelta'] for r in res31):.1f} °C")

    print("\n[6] Figuras")
    figuras(ctx, evals, foco, args, out)
    resumen["foco"] = foco.plan.nombre
    resumen["duracion_s"] = round(time.perf_counter() - inicio, 1)
    (out / "resumen_defensa.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False, default=str),
                                              encoding="utf-8")
    print(f"    Resultados en {out} ({resumen['duracion_s']:.0f} s)")


def figuras(ctx, evals, foco, args, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    SUP, TINTA, T2, GR = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
    COL = {"ninguna": "#8a8986", "EPS50": "#2a78d6", "EPS100": "#1baf7a", "EPS150": "#eb6834"}

    def estilo(ax):
        ax.set_facecolor(SUP)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(GR)
        ax.tick_params(colors=T2, labelsize=8, length=0)
        ax.grid(True, color=GR, linewidth=0.6)
        ax.set_axisbelow(True)

    # 1. D contra P_f y contra el MDelta mas alto de los escenarios, por proteccion y T_col
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13, 4.8), facecolor=SUP, constrained_layout=True)
    for prot, color in COL.items():
        for tc, marca, estilo_l in ((18.0, "o", "-"), (10.0, "s", "--")):
            sel = sorted([e for e in evals if e.plan.proteccion == prot and e.plan.t_col_C == tc and e.plan.particion == "5"],
                         key=lambda e: e.D_h)
            if not sel:
                continue
            md = [max(c["MDelta"] for c in e.corridas) for e in sel]
            ax.plot([e.D_h for e in sel], [e.P_f for e in sel], marker=marca, linestyle=estilo_l, color=color,
                    linewidth=1.4, label=f"{prot}, T_col {tc:g} °C")
            ax2.plot([e.D_h for e in sel], md, marker=marca, linestyle=estilo_l, color=color, linewidth=1.4)
            unica = [e for e in evals if e.plan.proteccion == prot and e.plan.t_col_C == tc and e.plan.particion == "unica"]
            for e in unica:
                ax.scatter([e.D_h], [e.P_f], marker="*", s=110, color=color, zorder=4)
                ax2.scatter([e.D_h], [max(c["MDelta"] for c in e.corridas)], marker="*", s=110, color=color, zorder=4)
    ax.axhline(0.05, color=TINTA, linewidth=1)
    ax.annotate("P_f = 5 %", (ax.get_xlim()[1], 0.05), xytext=(-50, 4), textcoords="offset points", fontsize=8)
    ax.scatter([foco.D_h], [foco.P_f], s=200, facecolors="none", edgecolors=TINTA, linewidths=1.5, zorder=5)
    ax.set_xlabel("D [h] desde t0 · estrella: vertida única")
    ax.set_ylabel("P_f conjunta")
    ax.set_title("Probabilidad de falla conjunta")
    ax.legend(frameon=False, fontsize=7, ncol=2, loc="center right")
    ax2.axhline(20.0, color=TINTA, linewidth=1)
    ax2.annotate("20 °C", (ax2.get_xlim()[1], 20.0), xytext=(-36, 4), textcoords="offset points", fontsize=8)
    ax2.scatter([foco.D_h], [max(c["MDelta"] for c in foco.corridas)], s=200, facecolors="none", edgecolors=TINTA,
                linewidths=1.5, zorder=5)
    ax2.set_xlabel("D [h] desde t0 · estrella: vertida única")
    ax2.set_ylabel("MΔ más alto de los escenarios [°C]")
    ax2.set_title("Margen: esperar entre vertidas sube MΔ (techos de hormigón fresco)")
    for a_ in (ax, ax2):
        estilo(a_)
    fig.suptitle(f"Plan foco (círculo): {foco.plan.nombre}" + (" — curva C1 PROVISORIA" if ctx["provisoria"] else ""),
                 fontsize=11)
    fig.savefig(out / "defensa_D_vs_Pf.png", dpi=160, facecolor=SUP)
    plt.close(fig)

    # 2. Curvas de hidratacion
    fig, ax = plt.subplots(figsize=(8, 3.8), facecolor=SUP, constrained_layout=True)
    a = np.linspace(0, 336, 600)
    for c in ctx["curvas"]:
        ax.plot(a, c.theta(a), linewidth=1.8, label=c.nombre)
    ax.set_xlabel("Edad [h]")
    ax.set_ylabel("Elevación adiabática equivalente [°C]")
    ax.set_title("Curvas de hidratación usadas como escenarios")
    ax.legend(frameon=False, fontsize=8)
    estilo(ax)
    fig.savefig(out / "defensa_curvas.png", dpi=160, facecolor=SUP)
    plt.close(fig)

    # 3. Historias de clima sobre el ensemble completo
    ens_raw = json.loads((CLIMA / ctx["esc"]["ensemble"] / "raw.json").read_text(encoding="utf-8"))
    from mcplan.escenarios_clima import nombres_miembros
    fig, ax = plt.subplots(figsize=(10, 3.8), facecolor=SUP, constrained_layout=True)
    H = 336.0
    for n in nombres_miembros(ens_raw):
        tl = timeline(ctx, miembro(ens_raw, n, "gfs", ""), H)
        ax.plot([p.t_h for p in tl.points], [p.temperature_C for p in tl.points], color=GR, linewidth=0.6)
    for e, color in zip(ctx["esc"]["escenarios"], ("#2a78d6", "#52514e", "#eb6834")):
        tl = timeline(ctx, load_snapshot(CLIMA, e["snapshot_id"])[0], H)
        ax.plot([p.t_h for p in tl.points], [p.temperature_C for p in tl.points], color=color, linewidth=1.6,
                label=f"{e['etiqueta']} ({e['miembro']}, peso {e['peso']:.2f})")
    ax.set_xlabel("t desde t0 = 19-nov 08:00 [h]")
    ax.set_ylabel("T aire [°C]")
    ax.set_title("3 historias completas del ensemble GFS (gris: los 31 miembros)")
    ax.legend(frameon=False, fontsize=8)
    estilo(ax)
    fig.savefig(out / "defensa_clima.png", dpi=160, facecolor=SUP)
    plt.close(fig)


if __name__ == "__main__":
    main()
