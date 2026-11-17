"""E13: modelo probabilistico, estados limite y Monte Carlo sobre el caso de E12.

Cada muestra es el caso determinista de E12 (IFC, curva C1, suelo, moldaje y clima
de los snapshots) con las entradas inciertas de `src/mcplan/incertidumbre.py`.

  [1] tabla de variables inciertas           results/e13/tabla_variables.{csv,md}
  [2] la muestra nominal reproduce E12       control antes de muestrear
  [3] Monte Carlo A: solo aleatorias         epistemicas fijas en el nominal
      Monte Carlo B: aleatorias + epistemicas
  [4] estados limite y estimador              P(g <= 0), IC de Wilson, cota con 0 fallas
  [5] que variables importan                  Spearman (Monte Carlo B) y tornado (una a la vez)
  [6] figuras y resumen                       results/e13/

Uso:
    python scripts/e13_incertidumbre.py                     # N = 2000 por conjunto, hasta 8 procesos
    python scripts/e13_incertidumbre.py --n 200             # piloto rapido
    python scripts/e13_incertidumbre.py --solo-tabla        # solo la tabla de variables
    python scripts/e13_incertidumbre.py --conjunto B --desde 0 --hasta 250 --salida parte0
        # un tramo de muestras: el mismo indice da la misma muestra en cualquier maquina (Slurm array)

Parametros fisicos provisorios (curva C1 sin calibrar): las probabilidades sirven para
discutir el metodo y comparar, no para aprobar el plan.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import os
import sys
import time
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan import (  # noqa: E402
    build_model, dz_que_calza, evaluar_criterios, extraer_solidos, load_plan, plan_desde_solidos, solve, voxelizar,
)
from mcplan.environment import aplicar_ambiente  # noqa: E402
from mcplan.incertidumbre import (  # noqa: E402
    ALEATORIA, CORRELACIONES, EPISTEMICA, REPETICIONES, VARIABLES, estados_limite, estimar, muestra_nominal,
    muestrear, spearman,
)
from mcplan.meteo import WeatherTimeline, assemble_timeline  # noqa: E402
from mcplan.snapshots import latest_snapshot, load_snapshot, verify  # noqa: E402

INICIO_LOCAL = "2026-11-27T04:00:00"      # primera vertida (IFC), igual que E12
ABSORTIVIDAD = 0.6
EMISIVIDAD = 0.9
E12_T_MAX, E12_DT_MAX = 63.98, 42.06      # resultado declarado de E12 (malla 0,5 m)

_CTX: dict = {}


# --------------------------------------------------------------------------- caso base
def preparar(dx: float = 0.5, dz: float | None = None) -> dict:
    """Arma una vez lo que no es incierto: geometria, voxeles, plan y clima base."""
    carpeta = ROOT / "datos" / "forecast"
    verificados = verify(carpeta)
    meta_f = latest_snapshot(carpeta, "open-meteo-forecast")
    meta_a = latest_snapshot(carpeta, "open-meteo-archive")
    forecast = load_snapshot(carpeta, meta_f.snapshot_id)[0]
    archivo = load_snapshot(carpeta, meta_a.snapshot_id)[0]
    plantilla = load_plan(str(ROOT / "datos" / "fundacion_e12.yaml"))
    duracion = plantilla.simulacion.duracion_h
    timeline = assemble_timeline(INICIO_LOCAL, np.arange(0.0, duracion + 1e-9, 1.0).tolist(),
                                 forecast=forecast, climatology=archivo)
    solidos = extraer_solidos(ROOT / "geometry" / "foundation.ifc")
    vox = voxelizar(solidos, dx=dx, dz=dz or dz_que_calza(solidos, dx))
    plan = copy.deepcopy(plan_desde_solidos(plantilla, solidos, dx))
    return {"plan": plan, "timeline": timeline, "vox": vox, "duracion": duracion,
            "snapshots": verificados, "forecast": meta_f.snapshot_id, "archivo": meta_a.snapshot_id}


def _iniciar(dx: float, dz: float | None) -> None:
    _CTX.update(preparar(dx, dz))


def clima_perturbado(timeline: WeatherTimeline, m: dict) -> WeatherTimeline:
    """Misma serie horaria con el desfase de temperatura y los factores de viento y sol."""
    puntos = [
        replace(p, temperature_C=p.temperature_C + m["dT_aire"],
                wind_ms=p.wind_ms * m["f_viento"], solar_W_m2=p.solar_W_m2 * m["f_solar"])
        for p in timeline.points
    ]
    return WeatherTimeline(start_local=timeline.start_local, points=puntos)


def caso(m: dict, ctx: dict | None = None):
    """Plan del caso E12 con los valores de la muestra `m`."""
    ctx = ctx or _CTX
    plan = copy.deepcopy(ctx["plan"])
    plan.hidratacion.elevacion_adibatica_C = m["theta_inf_C"]
    plan.hidratacion.tau_h = m["tau_h"]
    plan.hidratacion.energia_activacion_K = m["Ea_R_K"]
    mat = plan.materiales["M1"]
    plan.materiales["M1"] = replace(mat, k=mat.k * m["f_k"], cp=mat.cp * m["f_cp"], rho=mat.rho * m["f_rho"])
    for nombre, capa in list(plan.moldajes.items()):
        if nombre == "Madera":
            plan.moldajes[nombre] = replace(capa, k=capa.k * m["f_k_moldaje"])
    plan.suelo.mean_C = m["T_suelo_C"]
    atraso = 0.0
    for i, v in enumerate(sorted(plan.vertidas, key=lambda x: x.inicio_h)):
        if i > 0:
            atraso += m["retraso_vertida_h"][i - 1]
        v.inicio_h += atraso
        v.temperatura_colocacion_C += m["dT_colocacion"] + m["ruido_colocacion"][i]
        v.retiro_moldaje_h = m["retiro_moldaje_h"]
    aplicar_ambiente(plan, clima_perturbado(ctx["timeline"], m), con_viento=True, con_radiacion=True,
                     absorptivity=ABSORTIVIDAD, emissivity=EMISIVIDAD)
    return plan


def evaluar(m: dict, ctx: dict | None = None) -> dict:
    """Corre una muestra y devuelve T_max y dT_max (con sus instantes)."""
    ctx = ctx or _CTX
    plan = caso(m, ctx)
    r = solve(build_model(plan, voxeles=ctx["vox"]), duracion_h=ctx["duracion"], intervalo_salida_h=1.0,
              factor_estabilidad=plan.simulacion.factor_estabilidad)
    t, d = evaluar_criterios(r, plan.criterios).criterios
    return {"T_max": t.valor, "t_T_max_h": t.instante_h, "dT_max": d.valor, "t_dT_max_h": d.instante_h}


def _plano(m: dict) -> dict:
    fila = {}
    for k, v in m.items():
        if isinstance(v, list):
            fila.update({f"{k}_{i + 1}": x for i, x in enumerate(v)})
        else:
            fila[k] = v
    return fila


def _trabajo(tarea: tuple[int, int, bool]) -> dict:
    indice, semilla, epistemicas = tarea
    m = muestrear(indice, semilla, epistemicas)
    return {"indice": indice, **_plano(m), **evaluar(m)}


def correr_conjunto(nombre: str, epistemicas: bool, desde: int, hasta: int, semilla: int,
                    procesos: int, dx: float, dz: float | None) -> list[dict]:
    tareas = [(i, semilla, epistemicas) for i in range(desde, hasta)]
    inicio = time.perf_counter()
    if procesos > 1:
        with Pool(procesos, initializer=_iniciar, initargs=(dx, dz)) as pool:
            filas = pool.map(_trabajo, tareas, chunksize=max(1, len(tareas) // (procesos * 8)))
    else:
        filas = [_trabajo(t) for t in tareas]
    print(f"    Conjunto {nombre}: {len(filas)} muestras en {time.perf_counter() - inicio:.0f} s")
    return filas


# --------------------------------------------------------------------------- salidas
def escribir_tabla(carpeta: Path) -> None:
    cab = ["variable", "naturaleza", "unidad", "nominal_E12", "distribucion", "repeticion", "descripcion", "fuente"]
    filas = [[v.nombre, v.naturaleza, v.unidad, f"{v.nominal:g}", v.texto_distribucion(),
              f"{REPETICIONES[v.nombre]} (una por vertida)" if v.nombre in REPETICIONES else "1",
              v.descripcion, v.fuente] for v in VARIABLES]
    with open(carpeta / "tabla_variables.csv", "w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(cab)
        w.writerows(filas)
    lineas = ["| Variable | Naturaleza | Nominal E12 | Distribución | Qué representa | Fuente |",
              "|---|---|---|---|---|---|"]
    for v in VARIABLES:
        rep = f" ×{REPETICIONES[v.nombre]}" if v.nombre in REPETICIONES else ""
        lineas.append(f"| `{v.nombre}`{rep} | {v.naturaleza} | {v.nominal:g} {v.unidad} | {v.texto_distribucion()} | "
                      f"{v.descripcion} | {v.fuente} |")
    lineas += ["", "Dependencias (cópula gaussiana):", ""]
    lineas += [f"- ρ({a}, {b}) = {r:g}" for (a, b), r in CORRELACIONES.items()]
    (carpeta / "tabla_variables.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def guardar_muestras(filas: list[dict], ruta: Path) -> None:
    with open(ruta, "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def leer_muestras(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8") as h:
        return [{k: float(v) if v not in ("", "None") else math.nan for k, v in fila.items()} for fila in csv.DictReader(h)]


def resumir(filas: list[dict]) -> dict:
    T = np.array([f["T_max"] for f in filas])
    dT = np.array([f["dT_max"] for f in filas])
    g = estados_limite(T, dT)
    return {
        "T_max": {"media": float(T.mean()), "desv": float(T.std(ddof=1)), "min": float(T.min()), "max": float(T.max()),
                  "P05": float(np.quantile(T, 0.05)), "P95": float(np.quantile(T, 0.95))},
        "dT_max": {"media": float(dT.mean()), "desv": float(dT.std(ddof=1)), "min": float(dT.min()),
                   "max": float(dT.max()), "P05": float(np.quantile(dT, 0.05)), "P95": float(np.quantile(dT, 0.95))},
        "g_T": estimar(g["g_T"]),
        "g_dT": estimar(g["g_dT"]),
        "g_sistema": estimar(g["g_sistema"]),
    }


def condicional_epistemica(filas: list[dict], variable: str = "theta_inf_C", cortes=(42.0, 48.0)) -> list[dict]:
    """P(g_T <= 0) en tramos de una variable epistemica: lo epistemico se reporta como rango."""
    x = np.array([f[variable] for f in filas])
    g = 70.0 - np.array([f["T_max"] for f in filas])
    bordes = [-math.inf, *cortes, math.inf]
    salida = []
    for lo, hi in zip(bordes[:-1], bordes[1:]):
        sel = (x >= lo) & (x < hi)
        if np.any(sel):
            salida.append({"variable": variable, "desde": lo, "hasta": hi, **estimar(g[sel])})
    return salida


def _entradas_escalares() -> list[str]:
    return [v.nombre for v in VARIABLES if v.nombre not in REPETICIONES]


def sensibilidad_spearman(filas: list[dict]) -> dict:
    salida = {}
    for salida_n in ("T_max", "dT_max"):
        y = np.array([f[salida_n] for f in filas])
        salida[salida_n] = {n: spearman(np.array([f[n] for f in filas]), y) for n in _entradas_escalares()
                            if np.std([f[n] for f in filas]) > 0}
    return salida


def tornado(ctx: dict) -> dict:
    """Una variable a la vez en su percentil 5 y 95; el resto en el nominal."""
    base = evaluar(muestra_nominal(), ctx)
    salida = {"nominal": base, "variables": {}}
    for v in VARIABLES:
        extremos = {}
        for etiqueta, z in (("P05", -1.6449), ("P95", 1.6449)):
            m = muestra_nominal()
            valor = v.desde_normal(z)
            m[v.nombre] = [valor] * REPETICIONES[v.nombre] if v.nombre in REPETICIONES else valor
            extremos[etiqueta] = {"valor": valor, **evaluar(m, ctx)}
        salida["variables"][v.nombre] = {"naturaleza": v.naturaleza, **extremos}
    return salida


# --------------------------------------------------------------------------- figuras
SUP, TINTA, TINTA2, GRILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
C_A, C_B = "#2a78d6", "#eb6834"


def _estilo(ax) -> None:
    ax.set_facecolor(SUP)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRILLA)
    ax.tick_params(colors=TINTA2, labelsize=8, length=0)
    ax.xaxis.label.set_color(TINTA2)
    ax.yaxis.label.set_color(TINTA2)
    ax.title.set_color(TINTA)
    ax.title.set_fontsize(10)
    ax.grid(True, color=GRILLA, linewidth=0.6)
    ax.set_axisbelow(True)


def figuras(A: list[dict], B: list[dict], sens: dict, torn: dict, carpeta: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # 1. Estados limite
    fig, ejes = plt.subplots(1, 2, figsize=(12, 4), facecolor=SUP, constrained_layout=True)
    for ax, (clave, titulo, lim) in zip(ejes, (("T_max", "g_T = 70 − T_max", 70.0), ("dT_max", "g_ΔT = 20 − ΔT_max", 20.0))):
        for filas, color, nombre in ((A, C_A, "A: solo aleatorias"), (B, C_B, "B: aleatorias + epistémicas")):
            g = lim - np.array([f[clave] for f in filas])
            ax.hist(g, bins=40, color=color, alpha=0.55, label=nombre, edgecolor=SUP, linewidth=0.5)
        ax.axvline(0.0, color=TINTA, linewidth=1.2)
        ax.annotate("falla (g ≤ 0)", (0.0, ax.get_ylim()[1] * 0.92), xytext=(-6, 0), textcoords="offset points",
                    ha="right", fontsize=8, color=TINTA)
        ax.set_title(f"Estado límite {titulo}")
        ax.set_xlabel("g [°C]")
        ax.set_ylabel("Muestras")
        ax.legend(frameon=False, fontsize=8)
        _estilo(ax)
    fig.savefig(carpeta / "e13_estados_limite.png", dpi=160, facecolor=SUP)
    plt.close(fig)

    # 2. Convergencia del estimador de P(g_T <= 0) y cota con cero fallas
    fig, ax = plt.subplots(figsize=(7.5, 4), facecolor=SUP, constrained_layout=True)
    from mcplan.incertidumbre import cota_cero_fallas, wilson
    for filas, color, nombre in ((A, C_A, "A"), (B, C_B, "B")):
        falla = (70.0 - np.array([f["T_max"] for f in filas])) <= 0
        n = np.arange(1, falla.size + 1)
        k = np.cumsum(falla)
        hi = np.array([wilson(int(kk), int(nn))[1] for kk, nn in zip(k, n)])
        etiqueta = f"{nombre}: p̂ (fallas / N)" if k[-1] else f"{nombre}: p̂ = 0, sin fallas (no se dibuja en escala log)"
        ax.loglog(n, np.maximum(k / n, 1e-6), color=color, linewidth=2, label=etiqueta)
        ax.loglog(n, hi, color=color, linewidth=1, linestyle="--", label=f"{nombre}: límite superior IC 95 %")
    n = np.arange(1, max(len(A), len(B)) + 1)
    ax.loglog(n, [cota_cero_fallas(int(x)) for x in n], color=TINTA2, linewidth=1, linestyle=":",
              label="cota con 0 fallas ≈ 3/N")
    ax.set_xlabel("Número de muestras N")
    ax.set_ylabel("P(T_max > 70 °C)")
    ax.set_title("No ver fallas no prueba que P sea chica: la cota baja como 3/N")
    ax.set_ylim(1e-4, 1.0)
    ax.legend(frameon=False, fontsize=8)
    _estilo(ax)
    fig.savefig(carpeta / "e13_convergencia.png", dpi=160, facecolor=SUP)
    plt.close(fig)

    # 3. Sensibilidad: Spearman (B) y tornado
    fig, ejes = plt.subplots(1, 2, figsize=(13, 5), facecolor=SUP, constrained_layout=True)
    for ax, clave, titulo in ((ejes[0], "T_max", "T_max"), (ejes[1], "dT_max", "ΔT_max")):
        pares = sorted(sens[clave].items(), key=lambda kv: abs(kv[1]))
        nombres = [p[0] for p in pares]
        valores = [p[1] for p in pares]
        colores = [C_B if v.naturaleza == EPISTEMICA else C_A for v in (next(x for x in VARIABLES if x.nombre == n)
                                                                        for n in nombres)]
        ax.barh(nombres, valores, color=colores, height=0.6)
        ax.axvline(0, color=TINTA2, linewidth=0.8)
        ax.set_xlim(-1, 1)
        ax.set_title(f"Correlación de rangos con {titulo} (Monte Carlo B)")
        ax.set_xlabel("ρ de Spearman  (azul: aleatoria · naranjo: epistémica)")
        _estilo(ax)
    fig.savefig(carpeta / "e13_sensibilidad.png", dpi=160, facecolor=SUP)
    plt.close(fig)

    fig, ejes = plt.subplots(1, 2, figsize=(13, 5), facecolor=SUP, constrained_layout=True)
    for ax, clave, titulo in ((ejes[0], "T_max", "T_max [°C]"), (ejes[1], "dT_max", "ΔT_max [°C]")):
        base = torn["nominal"][clave]
        filas = []
        for nombre, d in torn["variables"].items():
            lo, hi = d["P05"][clave] - base, d["P95"][clave] - base
            filas.append((nombre, lo, hi, d["naturaleza"]))
        filas.sort(key=lambda f: max(abs(f[1]), abs(f[2])))
        for i, (nombre, lo, hi, nat) in enumerate(filas):
            color = C_B if nat == EPISTEMICA else C_A
            ax.barh(i, hi, color=color, height=0.6)
            ax.barh(i, lo, color=color, height=0.6, alpha=0.45)
        ax.set_yticks(range(len(filas)), [f[0] for f in filas])
        ax.axvline(0, color=TINTA2, linewidth=0.8)
        ax.set_title(f"Tornado: cambio de {titulo} con cada variable en su P05 / P95")
        ax.set_xlabel(f"Δ respecto del nominal (E12: {base:.2f} °C) · claro: P05, oscuro: P95")
        _estilo(ax)
    fig.savefig(carpeta / "e13_tornado.png", dpi=160, facecolor=SUP)
    plt.close(fig)


# --------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=2000, help="muestras por conjunto")
    ap.add_argument("--semilla", type=int, default=20261118)
    ap.add_argument("--procesos", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--dx", type=float, default=0.5)
    ap.add_argument("--dz", type=float, default=None)
    ap.add_argument("--solo-tabla", action="store_true")
    ap.add_argument("--rehacer-figuras", action="store_true",
                    help="regenera las figuras desde muestras_*.csv y resumen_e13.json, sin simular")
    ap.add_argument("--conjunto", choices=["A", "B"], default=None, help="correr solo un tramo de un conjunto")
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=None)
    ap.add_argument("--salida", type=Path, default=ROOT / "results" / "e13")
    args = ap.parse_args()
    carpeta = args.salida
    carpeta.mkdir(parents=True, exist_ok=True)

    print("[1] Tabla de variables inciertas")
    escribir_tabla(carpeta)
    n_a = sum(v.naturaleza == ALEATORIA for v in VARIABLES)
    print(f"    {len(VARIABLES)} variables: {n_a} aleatorias, {len(VARIABLES) - n_a} epistémicas, "
          f"{len(CORRELACIONES)} correlaciones -> {carpeta / 'tabla_variables.md'}")
    if args.solo_tabla:
        return
    if args.rehacer_figuras:
        guardado = json.loads((carpeta / "resumen_e13.json").read_text(encoding="utf-8"))
        figuras(leer_muestras(carpeta / "muestras_A.csv"), leer_muestras(carpeta / "muestras_B.csv"),
                guardado["spearman_B"], guardado["tornado"], carpeta)
        print(f"    Figuras regeneradas en {carpeta}")
        return

    if args.conjunto:
        hasta = args.hasta if args.hasta is not None else args.n
        filas = correr_conjunto(args.conjunto, args.conjunto == "B", args.desde, hasta, args.semilla,
                                args.procesos, args.dx, args.dz)
        ruta = carpeta / f"muestras_{args.conjunto}_{args.desde}_{hasta}.csv"
        guardar_muestras(filas, ruta)
        print(f"    Tramo guardado en {ruta}")
        return

    print("\n[2] La muestra nominal reproduce E12")
    ctx = preparar(args.dx, args.dz)
    nominal = evaluar(muestra_nominal(), ctx)
    print(f"    T_max = {nominal['T_max']:.2f} °C (E12: {E12_T_MAX}) · ΔT_max = {nominal['dT_max']:.2f} °C (E12: {E12_DT_MAX})")
    print(f"    Snapshots verificados: {ctx['snapshots']}")

    print(f"\n[3] Monte Carlo, N = {args.n} por conjunto, semilla {args.semilla}, {args.procesos} procesos")
    A = correr_conjunto("A (solo aleatorias)", False, 0, args.n, args.semilla, args.procesos, args.dx, args.dz)
    B = correr_conjunto("B (aleatorias + epistémicas)", True, 0, args.n, args.semilla, args.procesos, args.dx, args.dz)
    guardar_muestras(A, carpeta / "muestras_A.csv")
    guardar_muestras(B, carpeta / "muestras_B.csv")

    print("\n[4] Estados límite y estimador Monte Carlo")
    res = {"A": resumir(A), "B": resumir(B)}
    for nombre, r in res.items():
        print(f"    Conjunto {nombre}: T_max {r['T_max']['media']:.2f} ± {r['T_max']['desv']:.2f} °C "
              f"(P95 {r['T_max']['P95']:.2f}) · ΔT_max {r['dT_max']['media']:.2f} ± {r['dT_max']['desv']:.2f} °C")
        for g in ("g_T", "g_dT", "g_sistema"):
            e = r[g]
            lo, hi = e["IC95_wilson"]
            extra = f" · cota con 0 fallas {e['cota_superior_cero_fallas']:.2e}" if e["fallas"] == 0 else ""
            print(f"      P({g} <= 0) = {e['fallas']}/{e['n']} = {e['p_hat']:.4f}  IC95 [{lo:.4f}; {hi:.4f}]{extra}")
    cond = condicional_epistemica(B)
    res["B"]["condicional_theta_inf"] = cond
    print("    Conjunto B, P(g_T <= 0) según θ∞ (lo epistémico se reporta como rango):")
    for c in cond:
        lo, hi = c["IC95_wilson"]
        print(f"      θ∞ en [{c['desde']:g}; {c['hasta']:g}) °C: {c['fallas']}/{c['n']} = {c['p_hat']:.4f}  "
              f"IC95 [{lo:.4f}; {hi:.4f}]")

    print("\n[5] Qué variables importan")
    sens = sensibilidad_spearman(B)
    for clave in ("T_max", "dT_max"):
        top = sorted(sens[clave].items(), key=lambda kv: -abs(kv[1]))[:5]
        print(f"    {clave}: " + ", ".join(f"{n} ({r:+.2f})" for n, r in top))
    torn = tornado(ctx)

    print("\n[6] Figuras y resumen")
    figuras(A, B, sens, torn, carpeta)
    resumen = {
        "semilla": args.semilla, "n_por_conjunto": args.n, "dx_m": args.dx,
        "snapshots": {"forecast": ctx["forecast"], "archivo": ctx["archivo"]},
        "nominal": nominal, "conjuntos": res, "spearman_B": sens, "tornado": torn,
        "aviso": "Curva C1 y clima provisorios: las probabilidades comparan y discuten el metodo; no aprueban el plan.",
    }
    (carpeta / "resumen_e13.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"    Resultados en {carpeta}")


if __name__ == "__main__":
    main()
