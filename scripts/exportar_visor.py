"""Exporta los datos del visor de la defensa (results/visor/), corriendo el mismo solver.

No inventa nada: re-ejecuta los 48 planes x 24 escenarios de scripts/defensa_plan.py con la malla
de 0,5 m, guarda las series hora a hora (T max del hormigon colocado y T min a 25 mm bajo las
superficies) y, para el clima "medio", el campo 3D de temperatura cada 6 h. Al final compara MT y
MDelta con results/defensa/corridas.csv para demostrar que son las mismas corridas.

    python scripts/exportar_visor.py            # ~25-30 min con 7 procesos
"""
from __future__ import annotations

import csv
import base64
import gzip
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import defensa_plan as d  # noqa: E402
from mcplan.decision import (LIM_DT, LIM_T, PROTECCIONES, aplicar_plan, cronograma,  # noqa: E402
                             duracion_D, metricas)
from mcplan.environment import aplicar_ambiente, condiciones_de_timeline  # noqa: E402
from mcplan.thermal import build_model, solve  # noqa: E402

DX = 0.5
TASA = 40.0
PASO_CAMPO_H = 6.0
CLIMA_CAMPO = "medio"
T_MIN_COD, PASO_COD = -5.0, 0.35          # uint8: T = -5 + 0,35 * codigo; 255 = aun no colocado
OUT = ROOT / "results" / "visor"


def familia():
    return d.familia(False, [0, 6, 12, 24, 48], list(PROTECCIONES), [18.0, 10.0])


def correr_completo(args):
    ip, m, k = args
    ctx = d._ctx(DX)
    plan = familia()[ip]
    curva, clima = ctx["curvas"][m], ctx["climas"][k]
    etiqueta = ctx["esc"]["escenarios"][k]["etiqueta"]
    D = duracion_D(plan, ctx["volumenes"], TASA)
    H = max(336.0, D + 240.0)
    p = aplicar_plan(ctx["base"], plan, ctx["volumenes"], TASA)
    p.simulacion.duracion_h = H
    meta = getattr(curva, "metadatos", {}) or {}
    if "rho" in meta and "cp" in meta:
        mat = p.materiales["M1"]
        p.materiales["M1"] = type(mat)(name=mat.name, k=mat.k, cp=float(meta["cp"]), rho=float(meta["rho"]))
    tl = d.timeline(ctx, clima, H)
    aplicar_ambiente(p, tl, con_viento=True, con_radiacion=True,
                     absorptivity=d.ABSORTIVIDAD, emissivity=d.EMISIVIDAD)
    modelo = build_model(p, voxeles=ctx["vox"][plan.particion])
    modelo.hydration = curva
    con_campo = etiqueta == CLIMA_CAMPO
    instantes = np.arange(0.0, H + 1e-9, PASO_CAMPO_H).tolist() if con_campo else None
    r = solve(modelo, duracion_h=H, intervalo_salida_h=1.0, factor_estabilidad=p.simulacion.factor_estabilidad,
              profundidad_s25_m=0.025, instantes_campo_h=instantes)
    salida = {"ip": ip, "m": m, "k": k, "H": H, "D": D, **metricas(r),
              "Tmax": np.asarray(r.T_max_global, dtype=np.float64),
              "Ts25": np.asarray(r.T_min_s25, dtype=np.float64)}
    if con_campo:
        sel = ctx["vox"]["5"].vertida_id.reshape(-1) >= 0
        cuadros = []
        for t in instantes:
            T = r.campos[round(float(t), 6)].reshape(-1)[sel]
            cod = np.where(np.isfinite(T), np.clip(np.round((T - T_MIN_COD) / PASO_COD), 0, 254), 255)
            cuadros.append(cod.astype(np.uint8))
        salida["campo"] = np.stack(cuadros)
    return salida


def codificar_serie(v):
    return np.where(np.isfinite(v), np.round(v * 100), -32768).astype("<i2")


def clima_horario(ctx, k, horas):
    tl = d.timeline(ctx, ctx["climas"][k], horas)
    h_fn, t_fn = condiciones_de_timeline(tl, con_viento=True, con_radiacion=True,
                                         absorptivity=d.ABSORTIVIDAD, emissivity=d.EMISIVIDAD)
    pts = tl.points
    return {"t_h": [p.t_h for p in pts], "local": [p.time_local for p in pts],
            "T_aire": [round(p.temperature_C, 2) for p in pts], "viento": [round(p.wind_ms, 2) for p in pts],
            "solar": [round(p.solar_W_m2, 1) for p in pts], "nubes": [round(p.cloud_pct, 1) for p in pts],
            "T_inf": [round(float(t_fn(p.t_h)), 2) for p in pts], "h": [round(float(h_fn(p.t_h)), 2) for p in pts],
            "fuente": [p.source for p in pts]}


def leer_csv(ruta):
    with open(ruta, encoding="utf-8") as h:
        return list(csv.DictReader(h))


def main():
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "campos").mkdir(exist_ok=True)
    ctx = d._ctx(DX)
    planes = familia()
    nm, nk = len(ctx["curvas"]), len(ctx["climas"])
    tareas = [(ip, m, k) for ip in range(len(planes)) for m in range(nm) for k in range(nk)]
    print(f"{len(tareas)} corridas ({len(planes)} planes x {nm} curvas x {nk} climas)", flush=True)
    res = {}
    with Pool(7) as pool:
        for i, r in enumerate(pool.imap_unordered(correr_completo, tareas, chunksize=1), 1):
            res[(r["ip"], r["m"], r["k"])] = r
            if i % 48 == 0:
                print(f"  {i}/{len(tareas)}  {time.perf_counter() - t0:.0f} s", flush=True)

    # Comprobacion contra corridas.csv
    filas = {(f["plan"], f["curva"], f["clima"]): f for f in leer_csv(ROOT / "results/defensa/corridas.csv")}
    etiquetas = [e["etiqueta"] for e in ctx["esc"]["escenarios"]]
    dif = []
    for (ip, m, k), r in res.items():
        f = filas[(planes[ip].nombre, ctx["curvas"][m].nombre, etiquetas[k])]
        dif.append(max(abs(r["MT"] - float(f["MT"])), abs(r["MDelta"] - float(f["MDelta"]))))
    print(f"Diferencia maxima con corridas.csv: {max(dif):.2e} C", flush=True)

    # Series: un solo binario, en el orden plan -> curva -> clima
    offsets, partes, pos = {}, [], 0
    for ip in range(len(planes)):
        for m in range(nm):
            for k in range(nk):
                r = res[(ip, m, k)]
                n = r["Tmax"].size
                partes += [codificar_serie(r["Tmax"]), codificar_serie(r["Ts25"])]
                offsets[f"{ip}_{m}_{k}"] = [pos, n]
                pos += 2 * n
    # base64 en .txt: las paginas publicadas solo sirven tipos de texto, imagen, etc.
    (OUT / "series.txt").write_text(base64.b64encode(np.concatenate(partes).tobytes()).decode("ascii"), encoding="ascii")

    # Campos: un archivo gzip por plan con las 8 curvas del clima medio
    kc = etiquetas.index(CLIMA_CAMPO)
    cuadros = {}
    for ip, plan in enumerate(planes):
        bloques = [res[(ip, m, kc)]["campo"] for m in range(nm)]
        cuadros[plan.nombre] = int(bloques[0].shape[0])
        (OUT / "campos" / f"{plan.nombre}.txt").write_text(
            base64.b64encode(gzip.compress(np.stack(bloques).tobytes(), 9)).decode("ascii"), encoding="ascii")

    # Metadatos
    vox = ctx["vox"]["5"]
    g = vox.grid
    vid = vox.vertida_id
    ii, jj, kk = np.nonzero(vid >= 0)   # mismo orden que reshape(-1)[sel] (C order)
    corridas_meta = [{"plan": planes[ip].nombre, "curva": ctx["curvas"][m].nombre, "clima": etiquetas[k],
                      "MT": round(r["MT"], 3), "t_MT": r["t_MT"], "MDelta": round(r["MDelta"], 3),
                      "t_MDelta": r["t_MDelta"], "MT_14d": round(r["MT_14d"], 3),
                      "MDelta_14d": round(r["MDelta_14d"], 3),
                      "falla": bool(r["MT"] > LIM_T or r["MDelta"] > LIM_DT)}
                     for (ip, m, k), r in sorted(res.items())]
    raw = np.genfromtxt(ROOT / "datos/curvas_hidratacion/originales/source_terms.txt", comments="#")
    curvas = []
    for m, c in enumerate(ctx["curvas"]):
        col = raw[:, m + 1]
        ok = np.isfinite(col)
        sel = ok & (np.isclose(raw[:, 0] % 1.0, 0.0, atol=1e-3) | np.isclose(raw[:, 0] % 1.0, 1.0, atol=1e-3))
        curvas.append({"nombre": c.nombre, "peso": ctx["pesos_m"][m],
                       "campana": c.metadatos.get("campana"), "confianza": c.metadatos.get("confianza"),
                       "totales_MJ_m3": c.metadatos.get("totales_MJ_m3"),
                       "t_h": np.round(raw[sel, 0], 3).tolist(), "Q_W_m3": np.round(col[sel], 2).tolist(),
                       "edad_h": np.round(c.edad_h[::6], 3).tolist(), "theta_C": np.round(c.theta_C[::6], 3).tolist()})
    H_max = max(r["H"] for r in res.values())
    meta = {
        "generado": time.strftime("%Y-%m-%d %H:%M"),
        "fuente": "scripts/exportar_visor.py (mismo solver y supuestos que scripts/defensa_plan.py)",
        "dx_m": DX, "tasa_m3_h": TASA, "lim_T": LIM_T, "lim_dT": LIM_DT,
        "t0_local": ctx["esc"]["t0_local"], "validacion_max_dif_C": max(dif),
        "planes": leer_csv(ROOT / "results/defensa/planes.csv"),
        "orden_planes": [p.nombre for p in planes],
        "cronogramas": {p.nombre: cronograma(p, ctx["volumenes"], TASA) for p in planes},
        "volumenes_m3": ctx["volumenes"],
        "curvas": curvas,
        "climas": [{"etiqueta": e["etiqueta"], "peso": e["peso"], **{x: e.get(x) for x in ("miembro", "representa", "T_media_ventana_C", "grupo_T_media_C")}}
                   for e in ctx["esc"]["escenarios"]],
        "clima_horario": [clima_horario(ctx, k, H_max) for k in range(nk)],
        "series": {"archivo": "series.txt", "tipo": "base64 de int16 LE, centesimas de C, -32768 = sin dato",
                   "orden": "Tmax[n] y luego Ts25[n] por corrida", "offsets": offsets},
        "campos": {"carpeta": "campos", "clima": CLIMA_CAMPO, "paso_h": PASO_CAMPO_H, "cuadros": cuadros,
                   "cod": {"T_min": T_MIN_COD, "paso": PASO_COD, "sin_colocar": 255},
                   "forma": "base64(gzip(uint8[curva][cuadro][celda]))"},
        "geometria": {"nx": g.nx, "ny": g.ny, "nz": g.nz, "dx": g.dx, "dy": g.dy, "dz": g.dz,
                      "x0": g.x0, "y0": g.y0, "z0": g.z0, "i": ii.tolist(), "j": jj.tolist(), "k": kk.tolist(),
                      "vertida": vid[ii, jj, kk].tolist()},
        "corridas": corridas_meta,
        "malla_fina": leer_csv(ROOT / "results/defensa/corridas_malla_fina.csv"),
        "miembros_31": leer_csv(ROOT / "results/defensa/plan_foco_31_miembros.csv"),
        "robustez": json.loads((ROOT / "results/defensa/robustez_curvas_reales.json").read_text(encoding="utf-8")),
        "resumen": json.loads((ROOT / "results/defensa/resumen_defensa.json").read_text(encoding="utf-8")),
    }
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"Listo en {time.perf_counter() - t0:.0f} s -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
