"""E10 - Ambiente real, moldaje por vertida y snapshots de pronostico.

Este script es la evidencia ejecutable de la revision oral:

1. Descarga (o relee) un forecast de Open-Meteo y un bloque de reanalysis.
   Cada descarga queda como snapshot inmutable con su hash SHA-256.
2. Ensambla el clima de la simulacion hora a hora y marca cada tramo como
   `forecast` o `climatology`. El forecast del 11 de noviembre no llega al
   27 de noviembre, asi que la ventana se rellena con climatologia: el tramo
   queda identificado, no inventado.
3. Corre cuatro casos con el mismo IFC y la misma grilla:
   - base: clima sinusoidal generico, h = 12, moldaje global 0-72 h (E09);
   - ambiente: clima real, h(viento) + radiacion via T sol-aire, moldaje por
     vertida desde el IFC;
   - sin_radiacion: igual que ambiente pero sin flujo solar ni onda larga
     (sirve para mostrar que la radiacion no se cuenta dos veces);
   - aislado: ambiente + EPS 50 mm en todas las vertidas.
4. Escribe figuras, series y un resumen JSON en results/e10.

Uso (desde entregas/entrega10):
    python scripts/e10_ambiente.py                 # usa snapshots guardados
    python scripts/e10_ambiente.py --actualizar    # descarga de nuevo
    python scripts/e10_ambiente.py --dx 0.5 --solo base,ambiente,aislado
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan import (  # noqa: E402
    SITIO_PAHUIL,
    OpenMeteoClient,
    aplicar_ambiente,
    assemble_timeline,
    build_model,
    condiciones_de_timeline,
    dz_que_calza,
    evaluar_criterios,
    extraer_solidos,
    latest_snapshot,
    load_plan,
    load_snapshot,
    plan_desde_solidos,
    save_snapshot,
    solve,
    verify,
    voxelizar,
)
from mcplan.plan import LayerSpec  # noqa: E402
from mcplan.soil import SoilSpec  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Eje temporal del caso: primera vertida del IFC.
INICIO_LOCAL = "2026-11-27T04:00:00"
ARCHIVO_DESDE = "2025-11-27"
ARCHIVO_HASTA = "2025-12-11"

ABSORTIVIDAD = 0.6      # hormigon visto: alfa ~0.6
EMISIVIDAD = 0.9        # hormigon: eps ~0.9

COLORES = {
    "base": "#8d99ae",
    "ambiente": "#e76f51",
    "sin_radiacion": "#2a9d8f",
    "aislado": "#264653",
}
ETIQUETAS = {
    "base": "Base E09 (clima genérico)",
    "ambiente": "Ambiente real",
    "sin_radiacion": "Ambiente sin radiación",
    "aislado": "Ambiente + EPS 50 mm",
}


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


def snapshots_disponibles(carpeta: Path) -> tuple[object, object]:
    meta_f = latest_snapshot(carpeta, "open-meteo-forecast")
    meta_a = latest_snapshot(carpeta, "open-meteo-archive")
    if meta_f is None or meta_a is None:
        return None, None
    forecast, _ = load_snapshot(carpeta, meta_f.snapshot_id)
    archivo, _ = load_snapshot(carpeta, meta_a.snapshot_id)
    return forecast, archivo


def obtener_snapshots(carpeta: Path, actualizar: bool):
    """Devuelve (forecast, reanalysis, metas, verificacion)."""
    if not actualizar:
        forecast, archivo = snapshots_disponibles(carpeta)
        if forecast is not None and archivo is not None:
            ok = verify(carpeta)
            return forecast, archivo, ok

    cliente = OpenMeteoClient()
    print("Descargando forecast Open-Meteo (14 dias desde hoy)...")
    forecast = cliente.forecast(SITIO_PAHUIL, days=14)
    meta_f = save_snapshot(
        forecast,
        carpeta,
        notes="Forecast 14 dias para Pahuil/Chanco. No cubre el 27-nov: se usa como referencia de lo que se sabia hoy.",
    )
    print(f"  {meta_f.snapshot_id}: {meta_f.first_time} -> {meta_f.last_time} ({meta_f.n_hours} h)")

    print(f"Descargando reanalysis {ARCHIVO_DESDE}..{ARCHIVO_HASTA}...")
    archivo = cliente.archive(SITIO_PAHUIL, ARCHIVO_DESDE, ARCHIVO_HASTA)
    meta_a = save_snapshot(
        archivo,
        carpeta,
        notes="Reanalysis del mismo calendario del anio anterior. Se desplaza al anio del caso como climatologia.",
    )
    print(f"  {meta_a.snapshot_id}: {meta_a.first_time} -> {meta_a.last_time} ({meta_a.n_hours} h)")

    ok = verify(carpeta)
    return forecast, archivo, ok


# ---------------------------------------------------------------------------
# Casos
# ---------------------------------------------------------------------------


def caso_base(plantilla):
    """Reproduce las hipotesis de E09: clima sinusoidal y moldaje global."""
    plan = copy.deepcopy(plantilla)
    for vertida in plan.vertidas:
        vertida.moldaje = ""
        vertida.aislacion = ""
    perimetro = next(f for f in plan.fronteras if f.direccion == "perimetro")
    perimetro.capas.append(
        LayerSpec(
            tipo="conductiva",
            nombre="encofrado_global_e09",
            espesor_m=0.02,
            k=0.5,
            desde_h=0.0,
            hasta_h=72.0,
        )
    )
    plan.suelo = SoilSpec(k=1.389, rho=1600.0, cp=1200.0, mean_C=12.0, amplitude_C=0.0, depth_m=1.0)
    return plan


def caso_ambiente(plantilla, timeline, con_radiacion=True):
    plan = copy.deepcopy(plantilla)
    aplicar_ambiente(
        plan,
        timeline,
        con_viento=True,
        con_radiacion=con_radiacion,
        absorptivity=ABSORTIVIDAD,
        emissivity=EMISIVIDAD,
    )
    return plan


def caso_aislado(plantilla, timeline):
    plan = caso_ambiente(plantilla, timeline, con_radiacion=True)
    for vertida in plan.vertidas:
        vertida.aislacion = "EPS_50mm"
    return plan


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------


def figura_clima(timeline, suelo, carpeta: Path) -> None:
    t = np.array([p.t_h for p in timeline.points])
    T_aire = np.array([p.temperature_C for p in timeline.points])
    h_fn, t_fn = condiciones_de_timeline(timeline, absorptivity=ABSORTIVIDAD, emissivity=EMISIVIDAD)
    T_sa = np.array([t_fn(x) for x in t])
    viento = np.array([p.wind_ms for p in timeline.points])
    solar = np.array([p.solar_W_m2 for p in timeline.points])
    nube = np.array([p.cloud_pct for p in timeline.points])
    h_total = np.array([h_fn(x) for x in t])
    T_suelo = np.array([suelo.temperature(x) for x in t])
    fuentes = [p.source for p in timeline.points]

    fig, ejes = plt.subplots(3, 1, figsize=(12.5, 8.4), sharex=True,
                             gridspec_kw={"height_ratios": [2.0, 1.2, 1.0]})
    ax = ejes[0]
    ax.plot(t, T_aire, color="#457b9d", lw=1.7, label="T aire (2 m)")
    ax.plot(t, T_sa, color="#e76f51", lw=1.9, label="T sol-aire (lo que ve el Robin)")
    ax.plot(t, T_suelo, color="#6a994e", lw=1.5, ls="--", label="T suelo a 1 m")
    _sombrear_fuentes(ax, t, fuentes)
    ax.set(ylabel="T [°C]", title="Clima del sitio: aire, sol-aire y suelo a 1 m")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper right", ncol=3)

    ax = ejes[1]
    ax.plot(t, viento, color="#264653", lw=1.7, label="viento (m/s)")
    ax.set(ylabel="v [m/s]")
    ax2 = ax.twinx()
    ax2.plot(t, h_total, color="#e9c46a", lw=1.7, label="h total (W/m²K)")
    ax2.set_ylabel("h [W/m²K]")
    lineas = ax.get_lines() + ax2.get_lines()
    ax.legend(lineas, [ln.get_label() for ln in lineas], fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)

    ax = ejes[2]
    ax.plot(t, solar, color="#f4a261", lw=1.5, label="G solar (W/m²)")
    ax.set(xlabel="t desde la primera vertida [h]", ylabel="G [W/m²]")
    ax3 = ax.twinx()
    ax3.plot(t, nube, color="#6c757d", lw=1.1, ls=":", label="nubosidad (%)")
    ax3.set_ylabel("nubosidad [%]")
    lineas = ax.get_lines() + ax3.get_lines()
    ax.legend(lineas, [ln.get_label() for ln in lineas], fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(carpeta / "e10_clima.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def _sombrear_fuentes(ax, t, fuentes) -> None:
    colores = {"forecast": "#d7e8f7", "climatology": "#f7e6c4", "missing": "#f2b5b5"}
    nombres = {"forecast": "forecast", "climatology": "climatología", "missing": "sin dato"}
    inicio = 0
    for i in range(1, len(fuentes) + 1):
        if i == len(fuentes) or fuentes[i] != fuentes[inicio]:
            ax.axvspan(t[inicio], t[i - 1], color=colores.get(fuentes[inicio], "#eeeeee"),
                       alpha=0.55, zorder=0)
            inicio = i
    if fuentes:
        primera = fuentes[0]
        ax.text(0.01, 0.95, f"tramo inicial: {nombres.get(primera, primera)}",
                transform=ax.transAxes, fontsize=7, color="#555", va="top")


def figura_casos(series: dict[str, dict], carpeta: Path) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.0, 4.7))
    for nombre, datos in series.items():
        a1.plot(datos["t"], datos["T_max"], color=COLORES.get(nombre, "k"), lw=1.8,
                label=ETIQUETAS.get(nombre, nombre))
        a2.plot(datos["t"], datos["delta_T"], color=COLORES.get(nombre, "k"), lw=1.8,
                label=ETIQUETAS.get(nombre, nombre))
    a1.axhline(70, color="#8a8a8a", ls=":", lw=1.1)
    a1.text(series[next(iter(series))]["t"][-1], 70.8, "limite 70 °C", ha="right", fontsize=7, color="#666")
    a2.axhline(20, color="#8a8a8a", ls=":", lw=1.1)
    a2.text(series[next(iter(series))]["t"][-1], 20.8, "limite 20 °C", ha="right", fontsize=7, color="#666")
    a1.set(xlabel="t [h]", ylabel="T [°C]", title="T maxima del hormigon")
    a2.set(xlabel="t [h]", ylabel="ΔT [°C]", title="ΔT nucleo - superficie")
    for ax in (a1, a2):
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    fig.savefig(carpeta / "e10_casos.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def figura_efectos(resumen: dict, plantilla, carpeta: Path) -> None:
    nombres = list(resumen["casos"])
    T = [resumen["casos"][n]["T_max_C"] for n in nombres]
    dT = [resumen["casos"][n]["delta_T_max_C"] for n in nombres]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.0, 4.6))
    x = np.arange(len(nombres))
    a1.bar(x, T, color=[COLORES.get(n, "k") for n in nombres], alpha=0.9)
    a1.axhline(70, color="#8a8a8a", ls=":", lw=1.1)
    a1.set_xticks(x, [ETIQUETAS.get(n, n) for n in nombres], rotation=12, fontsize=8)
    a1.set(ylabel="T max [°C]", title="T maxima absoluta por caso")
    for xi, valor in zip(x, T):
        a1.text(xi, valor + 0.4, f"{valor:.1f}", ha="center", fontsize=8)
    a1.grid(axis="y", alpha=0.3)

    a2.bar(x, dT, color=[COLORES.get(n, "k") for n in nombres], alpha=0.9)
    a2.axhline(20, color="#8a8a8a", ls=":", lw=1.1)
    a2.set_xticks(x, [ETIQUETAS.get(n, n) for n in nombres], rotation=12, fontsize=8)
    a2.set(ylabel="ΔT max [°C]", title="ΔT maximo por caso")
    for xi, valor in zip(x, dT):
        a2.text(xi, valor + 0.4, f"{valor:.1f}", ha="center", fontsize=8)
    a2.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(carpeta / "e10_efectos.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # Moldaje por vertida: R efectiva de la cara lateral antes y despues de desmoldar.
    fig, ax = plt.subplots(figsize=(10.0, 4.4))
    horas = np.linspace(0.0, plantilla.simulacion.duracion_h, 800)
    r_eps = plantilla.aislaciones["EPS_50mm"].resistencia
    for vertida in plantilla.vertidas:
        capa = plantilla.moldajes.get(vertida.moldaje)
        r_moldaje = capa.resistencia if capa is not None else 0.0
        inicio = vertida.inicio_h
        fin = inicio + (vertida.retiro_moldaje_h if vertida.retiro_moldaje_h else np.inf)
        activo = (horas >= inicio) & (horas < fin)
        ax.plot(horas, np.where(activo, r_moldaje, 0.0), lw=1.4,
                label=f"vertida {vertida.id}: {vertida.moldaje or 'sin moldaje'}")
        if "aislado" in resumen["casos"]:
            ax.plot(horas, np.where(activo, r_moldaje + r_eps, 0.0), lw=1.0, ls="--",
                    color="#264653", alpha=0.7,
                    label=f"vertida {vertida.id}: + EPS 50 mm" if vertida.id == 1 else None)
        ax.axvline(fin, color="#999", lw=0.7, ls=":")
    ax.set(xlabel="t [h]", ylabel="R lateral de moldaje [m²K/W]",
           title="Moldaje por vertida y retiro a las 72 h de cada colocacion")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(carpeta / "e10_moldaje.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ifc", type=Path, default=ROOT / "geometry" / "foundation.ifc")
    ap.add_argument("--plantilla", type=Path, default=ROOT / "datos" / "fundacion_e10.yaml")
    ap.add_argument("--forecast-dir", type=Path, default=ROOT / "datos" / "forecast")
    ap.add_argument("--dx", type=float, default=0.5)
    ap.add_argument("--dz", type=float, default=None)
    ap.add_argument("--duracion-h", type=float, default=None)
    ap.add_argument("--salida", type=Path, default=ROOT / "results" / "e10")
    ap.add_argument("--actualizar", action="store_true", help="vuelve a descargar y guarda un snapshot nuevo")
    ap.add_argument("--solo", type=str, default="base,ambiente,sin_radiacion,aislado")
    ap.add_argument("--sin-figuras", action="store_true")
    args = ap.parse_args()

    carpeta = args.salida
    carpeta.mkdir(parents=True, exist_ok=True)

    plantilla = load_plan(str(args.plantilla))
    duracion = args.duracion_h or plantilla.simulacion.duracion_h

    forecast, archivo, snapshots_ok = obtener_snapshots(args.forecast_dir, args.actualizar)
    print(f"Snapshots verificados: {len(snapshots_ok)}")

    timeline = assemble_timeline(
        INICIO_LOCAL,
        hours=np.arange(0.0, duracion + 1e-9, 1.0).tolist(),
        forecast=forecast,
        climatology=archivo,
    )
    print(f"Clima ensamblado: {dict(timeline.sources)}")

    solidos = extraer_solidos(args.ifc)
    dx = args.dx
    dz = args.dz or dz_que_calza(solidos, dx)
    vox = voxelizar(solidos, dx=dx, dz=dz)
    print(f"Grilla: dx={dx:g} m, dz={dz:g} m, {int(vox.mask.sum())} celdas activas, "
          f"error de volumen {100 * vox.error_volumen():.2f} %")

    queridos = [c.strip() for c in args.solo.split(",") if c.strip()]
    preparado = plan_desde_solidos(plantilla, solidos, dx)
    preparado.simulacion.duracion_h = duracion
    disponibles = {
        "base": lambda: caso_base(preparado),
        "ambiente": lambda: caso_ambiente(preparado, timeline, con_radiacion=True),
        "sin_radiacion": lambda: caso_ambiente(preparado, timeline, con_radiacion=False),
        "aislado": lambda: caso_aislado(preparado, timeline),
    }

    series: dict[str, dict] = {}
    resumen_casos: dict[str, dict] = {}
    for nombre in queridos:
        if nombre not in disponibles:
            raise SystemExit(f"Caso desconocido: {nombre}")
        print(f"\nSimulando caso {nombre}...")
        plan = disponibles[nombre]()
        modelo = build_model(plan, voxeles=vox)
        resultado = solve(
            modelo,
            duracion_h=duracion,
            intervalo_salida_h=plantilla.simulacion.intervalo_salida_h,
            factor_estabilidad=plantilla.simulacion.factor_estabilidad,
            guardar_campo=False,
        )
        veredicto = evaluar_criterios(resultado, plan.criterios)
        t = np.asarray(resultado.time_h)
        Tmax = np.asarray(resultado.T_max_global)
        dT = np.asarray(resultado.delta_T)
        serie = {
            "t": t,
            "T_max": Tmax,
            "delta_T": dT,
            "T_max_abs": float(resultado.T_max_abs),
            "T_max_h": float(resultado.time_of_max(resultado.T_max_global)),
            "delta_T_max": float(resultado.delta_T_max),
            "delta_T_h": float(resultado.time_of_max(resultado.delta_T)),
            "dt_s": float(resultado.dt_s),
            "pasos": int(resultado.metadata.get("pasos", 0)),
        }
        series[nombre] = serie
        resumen_casos[nombre] = {
            "T_max_C": round(serie["T_max_abs"], 2),
            "T_max_h": serie["T_max_h"],
            "delta_T_max_C": round(serie["delta_T_max"], 2),
            "delta_T_h": serie["delta_T_h"],
            "dt_s": serie["dt_s"],
            "pasos": serie["pasos"],
            "veredicto": veredicto.resumen(),
        }
        print(f"  T max = {serie['T_max_abs']:.2f} °C a {serie['T_max_h']:.0f} h; "
              f"ΔT max = {serie['delta_T_max']:.2f} °C a {serie['delta_T_h']:.0f} h; "
              f"dt = {serie['dt_s']:.0f} s")

    # ---- Series CSV ----
    suelo = plantilla.suelo
    h_fn, t_fn = condiciones_de_timeline(timeline, absorptivity=ABSORTIVIDAD, emissivity=EMISIVIDAD)
    with open(carpeta / "series_e10.csv", "w", newline="", encoding="utf-8") as fh:
        campos = ["t_h", "time_local", "source", "T_aire_C", "T_sol_aire_C", "viento_ms",
                  "solar_W_m2", "h_total_W_m2K", "T_suelo_C"]
        for nombre in series:
            campos += [f"T_max_{nombre}_C", f"delta_T_{nombre}_C"]
        writer = csv.DictWriter(fh, fieldnames=campos)
        writer.writeheader()
        for i, punto in enumerate(timeline.points):
            fila = {
                "t_h": punto.t_h,
                "time_local": punto.time_local,
                "source": punto.source,
                "T_aire_C": punto.temperature_C,
                "T_sol_aire_C": t_fn(punto.t_h),
                "viento_ms": punto.wind_ms,
                "solar_W_m2": punto.solar_W_m2,
                "h_total_W_m2K": h_fn(punto.t_h),
                "T_suelo_C": suelo.temperature(punto.t_h),
            }
            for nombre, serie in series.items():
                fila[f"T_max_{nombre}_C"] = float(np.interp(punto.t_h, serie["t"], serie["T_max"]))
                fila[f"delta_T_{nombre}_C"] = float(np.interp(punto.t_h, serie["t"], serie["delta_T"]))
            writer.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in fila.items()})

    # ---- Moldaje por vertida ----
    with open(carpeta / "moldaje_por_vertida.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["caso", "vertida", "inicio_h", "retiro_h", "moldaje", "R_moldaje_m2K_W",
                    "aislacion", "R_aislacion_m2K_W", "R_total_lateral_m2K_W"])
        variantes = [("ambiente", "Ninguna"), ("aislado", "EPS_50mm")]
        for caso, aislacion in variantes:
            for v in preparado.vertidas:
                capa = plantilla.moldajes.get(v.moldaje)
                aisl = plantilla.aislaciones.get(aislacion if caso == "aislado" else v.aislacion)
                r_m = capa.resistencia if capa else 0.0
                r_a = aisl.resistencia if aisl else 0.0
                w.writerow([caso, v.id, v.inicio_h,
                            v.inicio_h + (v.retiro_moldaje_h or 0.0),
                            v.moldaje or "ninguno", f"{r_m:.4f}",
                            aislacion, f"{r_a:.4f}", f"{r_m + r_a:.4f}"])

    # ---- Resumen JSON ----
    fuentes = timeline.sources
    meta_f = latest_snapshot(args.forecast_dir, "open-meteo-forecast")
    meta_a = latest_snapshot(args.forecast_dir, "open-meteo-archive")
    resumen = {
        "entrega": "E10 - ambiente real, moldaje por vertida y snapshots de forecast",
        "ifc": args.ifc.name,
        "inicio_local": INICIO_LOCAL,
        "duracion_h": duracion,
        "malla": {
            "dx_m": dx, "dz_m": dz, "nx": vox.grid.nx, "ny": vox.grid.ny, "nz": vox.grid.nz,
            "celdas_activas": int(vox.mask.sum()), "error_volumen_total": vox.error_volumen(),
        },
        "snapshots": {
            "forecast": asdict(meta_f) if meta_f else None,
            "archive": asdict(meta_a) if meta_a else None,
            "verificados": len(snapshots_ok),
        },
        "clima": {
            "cobertura": fuentes,
            "horas_totales": len(timeline),
            "cobertura_forecast_h": fuentes.get("forecast", 0),
            "T_aire_min_C": round(min(p.temperature_C for p in timeline.points), 2),
            "T_aire_max_C": round(max(p.temperature_C for p in timeline.points), 2),
            "viento_medio_ms": round(float(np.mean([p.wind_ms for p in timeline.points])), 2),
            "viento_max_ms": round(float(np.max([p.wind_ms for p in timeline.points])), 2),
            "G_max_W_m2": round(float(np.max([p.solar_W_m2 for p in timeline.points])), 1),
            "h_total_min_W_m2K": round(float(min(h_fn(p.t_h) for p in timeline.points)), 2),
            "h_total_max_W_m2K": round(float(max(h_fn(p.t_h) for p in timeline.points)), 2),
            "T_sol_aire_max_C": round(float(max(t_fn(p.t_h) for p in timeline.points)), 2),
        },
        "suelo": {
            "media_C": suelo.mean_C,
            "amplitud_superficie_C": suelo.amplitude_C,
            "profundidad_m": suelo.depth_m,
            "difusividad_m2_s": suelo.alpha,
            "profundidad_penetracion_m": suelo.penetration_depth,
            "amortiguacion": suelo.damping,
            "atraso_fase_h": suelo.phase_lag_h,
            "R_suelo_m2K_W": suelo.resistance,
        },
        "moldajes": {n: round(c.resistencia, 4) for n, c in plantilla.moldajes.items()},
        "aislaciones": {n: round(c.resistencia, 4) for n, c in plantilla.aislaciones.items()},
        "casos": resumen_casos,
        "supuestos": {
            "absortividad": ABSORTIVIDAD,
            "emisividad": EMISIVIDAD,
            "h_convectiva": "ASHRAE pared plana: h = 5.7 + 3.8 v",
            "radiacion": "incluida en T sol-aire; nunca como flujo separado",
            "suelo": "Robin con R = e/k y T no perturbada a 1 m (onda anual)",
        },
        "aviso": "Hidratacion aun provisoria: el foco de E10 es la cadena clima -> frontera.",
    }
    (carpeta / "resumen_e10.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    if not args.sin_figuras:
        figura_clima(timeline, suelo, carpeta)
        figura_casos(series, carpeta)
        figura_efectos(resumen, preparado, carpeta)

    print(f"\nResultados en {carpeta}")
    if "ambiente" in series and "base" in series:
        d_t = series["ambiente"]["T_max_abs"] - series["base"]["T_max_abs"]
        d_d = series["ambiente"]["delta_T_max"] - series["base"]["delta_T_max"]
        print(f"Ambiente vs base: T max {d_t:+.2f} °C, ΔT max {d_d:+.2f} °C")


if __name__ == "__main__":
    main()
