"""E11: del snapshot de clima a la condicion de borde y a los resultados 3D.

Recorre en orden lo que pide el laboratorio:

  [1] archivo meteorologico      ruta, tamano y primeras filas del CSV
  [2] metadata                   fuente, emision, coordenadas, horizonte y hashes verificados
  [3] grafico                    temperatura ambiente (y viento y radiacion) -> clima.png
  [4] condicion de borde         que valores recibe el Robin en algunos instantes
  [5] simulacion corta           72 h por defecto, malla de 0,5 m
  [6] resultados 3D              serie .vti/.pvd para ParaView, imagenes y visor PyVista
  [7] corte y clipping           cortes ortogonales y mitad cortada
  [8] nucleo y superficie        donde estan y que temperatura tienen

La frontera usa la misma fisica de E10 (src/mcplan/environment.py). Hidratacion y
plantilla siguen siendo provisorias: la simulacion muestra la cadena, no decide el plan.

Uso:
    python scripts/e11_clima_3d.py                      # todo, con el forecast como clima
    python scripts/e11_clima_3d.py --solo-clima         # solo pasos 1 a 3, sin simular
    python scripts/e11_clima_3d.py --visor              # al final abre la ventana 3D
    python scripts/e11_clima_3d.py --frontera temperatura   # Robin solo con T aire (sin viento ni sol)
    python scripts/e11_clima_3d.py --clima-desde obra   # clima del 27-nov (climatologia del archivo)

Salidas en results/e11/: clima.png, frontera.png, cortes_3d.png, nucleo_superficie.png,
vista_3d.png, corrida.json y vti/ (serie.pvd para ParaView).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan import (  # noqa: E402
    build_model, dz_que_calza, evaluar_criterios, extraer_solidos, load_plan, plan_desde_solidos, solve,
    voxelizar,
)
from mcplan import visualization as vis  # noqa: E402
from mcplan.environment import aplicar_ambiente, condiciones_de_timeline  # noqa: E402
from mcplan.meteo import SITIO_PAHUIL, assemble_timeline  # noqa: E402
from mcplan.snapshots import latest_snapshot, load_snapshot, verify  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INICIO_OBRA = "2026-11-27T04:00:00"     # primera vertida del IFC
ABSORTIVIDAD, EMISIVIDAD = 0.6, 0.9     # hormigon visto, iguales a E10


def titulo(n: int, texto: str) -> None:
    print(f"\n[{n}] {texto}")


# ---------------------------------------------------------------- pasos 1 a 3: el clima
def leer_snapshots(carpeta: Path, snapshot_id: str | None):
    """Snapshot de forecast pedido (o el ultimo) y el ultimo historico, ya verificados."""
    verificados = verify(carpeta)
    meta_f = latest_snapshot(carpeta, "open-meteo-forecast") if snapshot_id is None else None
    forecast, meta_f = load_snapshot(carpeta, snapshot_id or meta_f.snapshot_id)
    meta_a = latest_snapshot(carpeta, "open-meteo-archive")
    archivo = load_snapshot(carpeta, meta_a.snapshot_id)[0] if meta_a is not None else None
    return forecast, meta_f, archivo, verificados


def mostrar_archivo(carpeta: Path, meta) -> None:
    titulo(1, "Archivo meteorológico")
    sub = carpeta / meta.snapshot_id
    for nombre in sorted(p.name for p in sub.iterdir()):
        print(f"    {sub.relative_to(ROOT) if sub.is_relative_to(ROOT) else sub}\\{nombre}"
              f"   ({(sub / nombre).stat().st_size / 1024:.1f} kB)")
    print("    Primeras filas de normalizado.csv:")
    with open(sub / "normalizado.csv", encoding="utf-8") as h:
        for _ in range(4):
            print("      " + h.readline().rstrip())


def mostrar_metadata(meta, verificados) -> None:
    titulo(2, "Metadata")
    filas = [
        ("snapshot", meta.snapshot_id), ("fuente", meta.source), ("modelo", meta.model),
        ("endpoint", meta.endpoint), ("emitido / descargado", f"{meta.issued_at} / {meta.fetched_at}"),
        ("coordenadas de la celda", f"{meta.latitude:.6f}, {meta.longitude:.6f}"),
        ("coordenadas del sitio", f"{SITIO_PAHUIL.latitude:.6f}, {SITIO_PAHUIL.longitude:.6f}"),
        ("zona horaria", meta.timezone), ("horizonte", f"{meta.first_time} -> {meta.last_time} ({meta.n_hours} h)"),
        ("SHA-256 crudo", meta.sha256_raw), ("SHA-256 csv", meta.sha256_csv),
    ]
    for clave, valor in filas:
        print(f"    {clave:<24}{valor}")
    print(f"    Hashes verificados: {len(verificados)} snapshot(s) sin alteraciones")
    print("    Unidades: T [°C], humedad [%], viento a 10 m [m/s], radiación de onda corta [W/m²], nubosidad [%]")


def armar_timeline(meta, forecast, archivo, clima_desde: str, duracion: float):
    inicio = meta.first_time + ":00" if clima_desde == "forecast" else INICIO_OBRA
    horas = np.arange(0.0, duracion + 1e-9, 1.0).tolist()
    return assemble_timeline(inicio, horas, forecast=forecast, climatology=archivo), inicio


def figura_clima(forecast, timeline, h_fn, t_fn, carpeta: Path) -> None:
    titulo(3, "Gráfico del clima")
    t = np.array([p.t_h for p in timeline.points])
    fig, ejes = plt.subplots(3, 1, figsize=(11, 8.2), sharex=False)
    horas = np.arange(len(forecast.times))
    ejes[0].plot(horas, forecast.temperature_C, color="#e76f51", lw=1.2)
    ejes[0].set(title=f"Snapshot completo: {forecast.source}, {forecast.times[0]} a {forecast.times[-1]}",
                xlabel="horas desde el inicio del snapshot", ylabel="T aire [°C]")
    T_aire = np.array([p.temperature_C for p in timeline.points])
    ejes[1].plot(t, T_aire, color="#e76f51", label="T aire (snapshot)")
    ejes[1].plot(t, [t_fn(x) for x in t], color="#264653", label="T∞ que recibe el Robin (sol-aire)")
    ejes[1].set(title=f"Lo que entra a la frontera desde {timeline.start_local}", xlabel="t de simulación [h]",
                ylabel="T [°C]")
    ejes[1].legend(fontsize=9)
    ax2 = ejes[2]
    ax2.plot(t, [h_fn(x) for x in t], color="#2a9d8f", label="h(t) [W/(m²·K)]")
    ax2.set(xlabel="t de simulación [h]", ylabel="h [W/(m²·K)]")
    ax3 = ax2.twinx()
    ax3.plot(t, [p.wind_ms for p in timeline.points], color="#8a8a8a", lw=0.9, label="viento [m/s]")
    ax3.plot(t, [p.solar_W_m2 / 100.0 for p in timeline.points], color="#e9c46a", lw=0.9,
             label="radiación [W/m² ÷ 100]")
    ax3.set_ylabel("viento [m/s] · radiación/100")
    lineas = ax2.get_legend_handles_labels()
    otras = ax3.get_legend_handles_labels()
    ax2.legend(lineas[0] + otras[0], lineas[1] + otras[1], fontsize=9, loc="upper right")
    for a in ejes:
        a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(carpeta / "clima.png", dpi=150)
    plt.close(fig)
    print(f"    T aire en el snapshot: {min(forecast.temperature_C):.1f} a {max(forecast.temperature_C):.1f} °C")
    print(f"    Fuente de cada hora simulada: {dict(timeline.sources)}")
    print(f"    Figura: {carpeta / 'clima.png'}")


def mostrar_frontera(timeline, h_fn, t_fn, modo: str) -> None:
    titulo(4, f"Condición de borde alimentada con la serie (modo: {modo})")
    print("    Robin en caras laterales y superior: -k ∂T/∂n = h(t) · (T - T∞(t)); la base sigue con el suelo")
    if modo == "completa":
        print("    h(t)  = 5,7 + 3,8·v  +  4·ε·σ·T³          (viento + radiación linealizada)")
        print("    T∞(t) = T aire + [α·G + ε·σ·(T_cielo⁴ - T_aire⁴)] / h   (sol-aire)")
    else:
        print("    h = 5,7 (aire en calma) y T∞(t) = T aire: solo la temperatura del snapshot")
    print(f"    {'t [h]':>6}{'hora local':>18}{'T aire':>9}{'viento':>9}{'G':>8}{'h':>8}{'T∞':>8}  fuente")
    for t in (0.0, 6.0, 12.0, 18.0, 24.0):
        if t > timeline.points[-1].t_h:
            break
        p = timeline.at(t)
        print(f"    {t:>6.0f}{p.time_local:>18}{p.temperature_C:>8.1f}°{p.wind_ms:>8.1f}{p.solar_W_m2:>8.0f}"
              f"{h_fn(t):>8.1f}{t_fn(t):>7.1f}°  {p.source}")


# ---------------------------------------------------------------- pasos 5 a 8: simulacion y 3D
def simular(args, timeline, modo: str):
    titulo(5, f"Simulación corta: {args.duracion_h:g} h, malla de {args.dx:g} m")
    plantilla = load_plan(str(args.plantilla))
    plantilla.simulacion.duracion_h = args.duracion_h
    solidos = extraer_solidos(args.ifc)
    dz = args.dz or dz_que_calza(solidos, args.dx)
    vox = voxelizar(solidos, dx=args.dx, dz=dz)
    plan = plan_desde_solidos(plantilla, solidos, args.dx)
    plan = copy.deepcopy(plan)
    aplicar_ambiente(plan, timeline, con_viento=(modo == "completa"), con_radiacion=(modo == "completa"),
                     absorptivity=ABSORTIVIDAD, emissivity=EMISIVIDAD)
    modelo = build_model(plan, voxeles=vox)
    instantes = np.arange(0.0, args.duracion_h + 1e-9, 3.0)
    r = solve(modelo, duracion_h=args.duracion_h, intervalo_salida_h=1.0,
              factor_estabilidad=plan.simulacion.factor_estabilidad, instantes_campo_h=instantes)
    veredicto = evaluar_criterios(r, plan.criterios)
    print(f"    Grilla {vox.grid.shape}, {int(vox.mask.sum())} celdas de hormigón, dz = {dz:g} m, "
          f"error de volumen {100 * vox.error_volumen():.2f} %")
    print(f"    dt = {r.dt_s:.0f} s, {r.metadata['pasos']} pasos")
    for linea in veredicto.resumen().splitlines():
        print("    " + linea)
    print("    (hidratación y plantilla provisorias: muestra la cadena, no decide el plan)")
    return vox, modelo, r, veredicto


def zonas_del_modelo(modelo):
    forma = modelo.grid.shape
    return {"nucleo": modelo.is_core.reshape(forma), "superficie": modelo.is_surface.reshape(forma)}


def exportar_y_ver(args, vox, modelo, r, carpeta: Path) -> float:
    titulo(6, "Resultados 3D")
    zonas = zonas_del_modelo(modelo)
    extras = {k: v.astype(np.uint8) for k, v in zonas.items()}
    tiempos = sorted(r.campos)
    paso = max(1, int(round(args.vti_cada_h / 3.0)))
    archivos = vis.guardar_serie(carpeta / "vti", vox.grid, vox.vertida_id,
                                 {t: r.campos[t] for t in tiempos[::paso]}, extras)
    print(f"    {len(archivos)} archivos .vti y {carpeta / 'vti' / 'serie.pvd'} (ábrelo en ParaView)")
    print("    Campos por celda: temperature, vertida_id, nucleo (0/1), superficie (0/1)")
    t_img = min(tiempos, key=lambda x: abs(x - (args.t if args.t is not None else min(48.0, tiempos[-1]))))

    import pyvista as pv
    titulo(7, f"Cortes y clipping a t = {t_img:.0f} h")
    malla = vis.a_image_data(vox.grid, vox.vertida_id, r.campos[t_img], extras)
    hormigon = malla.threshold(-0.5, scalars="vertida_id")      # solo celdas con vertida (id >= 0)
    hormigon = hormigon.threshold(value=(-1e9, 1e9), scalars="temperature")   # ya colocadas
    clim = (10.0, float(np.ceil(np.nanmax(r.campos[t_img]) / 5.0) * 5.0))
    p = pv.Plotter(off_screen=True, window_size=(1250, 850))
    p.set_background("white")
    p.add_mesh(hormigon.outline(), color="#555555")
    p.add_mesh(hormigon.slice_orthogonal(x=0.0, y=0.0, z=1.6), scalars="temperature", cmap="inferno", clim=clim,
               scalar_bar_args={"title": "T [°C]", "color": "black", "vertical": True, "position_x": 0.88,
                                "position_y": 0.25, "height": 0.5, "fmt": "%.0f"})
    p.add_text(f"Cortes x = 0, y = 0 y z = 1,6 m · t = {t_img:.0f} h", position="upper_edge", font_size=11,
               color="black")
    p.camera_position = [(27.0, -31.0, 19.0), (0.0, 0.0, 1.9), (0.0, 0.0, 1.0)]
    p.screenshot(str(carpeta / "cortes_3d.png"))
    p.close()
    print(f"    Cortes ortogonales: {carpeta / 'cortes_3d.png'}")

    visor = vis.VisorVertidas(vox.grid, vox.vertida_id, r.campos, off_screen=True, zonas=zonas)
    visor.fijar_tiempo(t_img)
    visor.fijar_corte(True)
    visor.captura(carpeta / "vista_3d.png")
    print(f"    Mitad cortada en y = 0 (clipping): {carpeta / 'vista_3d.png'}")
    visor.mostrar_zona("nucleo", True)
    visor.mostrar_zona("superficie", True)
    visor.captura(carpeta / "nucleo_superficie.png")
    visor.cerrar()
    return t_img


def identificar(modelo, r, t_img: float) -> dict:
    titulo(8, f"Núcleo y superficie a t = {t_img:.0f} h")
    T = r.campos[t_img]
    zonas = zonas_del_modelo(modelo)
    X, Y, Z = np.meshgrid(*modelo.grid.centers(), indexing="ij")
    salida = {}
    for nombre, mascara, func, texto in (("nucleo", zonas["nucleo"], np.nanargmax, "más caliente"),
                                         ("superficie", zonas["superficie"], np.nanargmin, "más fría")):
        activa = mascara & np.isfinite(T)
        if not activa.any():
            print(f"    {nombre}: aún sin celdas colocadas")
            continue
        valores = np.where(activa, T, np.nan)
        i = np.unravel_index(func(valores), T.shape)
        salida[nombre] = {"celdas": int(mascara.sum()), "T_C": round(float(T[i]), 2),
                          "x_m": round(float(X[i]), 2), "y_m": round(float(Y[i]), 2), "z_m": round(float(Z[i]), 2)}
        print(f"    {nombre.capitalize():<11}{int(mascara.sum()):>6} celdas · celda {texto}: "
              f"{T[i]:.1f} °C en ({X[i]:.2f}; {Y[i]:.2f}; {Z[i]:.2f}) m")
    print("    Núcleo = hormigón a 2 celdas o más de cualquier cara exterior (erosión de la geometría).")
    print("    Superficie = celdas con una cara expuesta permanente, sin contar la base sobre el suelo.")
    if "nucleo" in salida and "superficie" in salida:
        print(f"    ΔT = T máx núcleo - T mín superficie = {salida['nucleo']['T_C'] - salida['superficie']['T_C']:.1f} °C "
              "en este instante")
    return salida


def figura_frontera(r, carpeta: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(r.time_h, r.T_max_core, color="#2b6cb0", label="T máx núcleo")
    ax.plot(r.time_h, r.T_min_surface, color="#2f9e44", label="T mín superficie")
    ax.plot(r.time_h, r.T_mean, color="#8a8a8a", lw=0.9, label="T media")
    ax.set(xlabel="t [h]", ylabel="T [°C]", title="Núcleo y superficie con la frontera alimentada por el snapshot")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(carpeta / "frontera.png", dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--forecast-dir", type=Path, default=ROOT / "datos" / "forecast")
    ap.add_argument("--snapshot", default=None, help="id del snapshot de forecast (por defecto, el último)")
    ap.add_argument("--clima-desde", choices=["forecast", "obra"], default="forecast",
                    help="forecast: la simulación parte al inicio del snapshot; obra: el 27-nov con climatología")
    ap.add_argument("--frontera", choices=["completa", "temperatura"], default="completa",
                    help="completa: viento y radiación; temperatura: solo T aire")
    ap.add_argument("--ifc", type=Path, default=ROOT / "geometry" / "foundation.ifc")
    ap.add_argument("--plantilla", type=Path, default=ROOT / "datos" / "fundacion_e10.yaml")
    ap.add_argument("--dx", type=float, default=0.5)
    ap.add_argument("--dz", type=float, default=None)
    ap.add_argument("--duracion-h", type=float, default=72.0)
    ap.add_argument("--t", type=float, default=None, help="instante de las imágenes 3D [h] (por defecto 48)")
    ap.add_argument("--vti-cada-h", type=float, default=12.0)
    ap.add_argument("--solo-clima", action="store_true", help="solo pasos 1 a 3")
    ap.add_argument("--visor", action="store_true", help="abrir la ventana 3D al final")
    ap.add_argument("--salida", type=Path, default=ROOT / "results" / "e11")
    args = ap.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)

    forecast, meta, archivo, verificados = leer_snapshots(args.forecast_dir, args.snapshot)
    mostrar_archivo(args.forecast_dir, meta)
    mostrar_metadata(meta, verificados)
    timeline, inicio = armar_timeline(meta, forecast, archivo, args.clima_desde, args.duracion_h)
    completa = args.frontera == "completa"
    h_fn, t_fn = condiciones_de_timeline(timeline, con_viento=completa, con_radiacion=completa,
                                         absorptivity=ABSORTIVIDAD, emissivity=EMISIVIDAD)
    figura_clima(forecast, timeline, h_fn, t_fn, args.salida)
    if args.solo_clima:
        return
    mostrar_frontera(timeline, h_fn, t_fn, args.frontera)

    vox, modelo, r, veredicto = simular(args, timeline, args.frontera)
    figura_frontera(r, args.salida)
    t_img = exportar_y_ver(args, vox, modelo, r, args.salida)
    zonas = identificar(modelo, r, t_img)

    t_max, delta = veredicto.criterios
    (args.salida / "corrida.json").write_text(json.dumps({
        "snapshot": meta.snapshot_id, "sha256_csv": meta.sha256_csv, "inicio_local": inicio,
        "fuentes_por_hora": dict(timeline.sources), "frontera": args.frontera, "dx_m": args.dx,
        "duracion_h": args.duracion_h, "dt_s": r.dt_s,
        "T_max_C": round(t_max.valor, 2), "T_max_h": t_max.instante_h,
        "delta_T_C": round(delta.valor, 2), "delta_T_h": delta.instante_h,
        "instante_imagenes_h": t_img, "zonas": zonas,
        "aviso": "Hidratacion y plantilla provisorias.",
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultados en {args.salida}")

    if args.visor:
        print("Ventana 3D: teclas 1-5 vertidas, x corte, n núcleo, m superficie; la barra cambia t.")
        visor = vis.VisorVertidas(vox.grid, vox.vertida_id, r.campos, zonas=zonas_del_modelo(modelo))
        visor.fijar_tiempo(t_img)
        visor.abrir()


if __name__ == "__main__":
    main()
