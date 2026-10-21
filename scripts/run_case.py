"""Ejecuta un caso declarativo y guarda los resultados en `validacion/`.

Uso:

    python scripts/run_case.py --plan datos/caso_fundacion.yaml
    python scripts/run_case.py --plan datos/caso_fundacion.yaml --montecarlo 200

Salidas (en la carpeta de salida):
    series.csv              series temporales de T_max, T_min, delta_T
    resumen.json            veredicto de criterios y parametros usados
    campo_final.csv         temperatura final por celda (x, y, z, T)
    series.png              grafico de series temporales
    campo_peak.png          campo de temperatura en el instante critico
    confiabilidad.json      probabilidades de excedencia (si se pide MC)
    confiabilidad.png       histogramas de T_max y delta_T (si se pide MC)
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

from mcplan import build_model, evaluar_criterios, load_plan, solve  # noqa: E402
from mcplan.reliability import ejecutar_montecarlo  # noqa: E402


def _commit() -> str:
    try:
        salida = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            check=False,
        )
        return salida.stdout.strip() or "desconocido"
    except OSError:
        return "desconocido"


def _escribir_series(ruta: Path, result) -> None:
    with open(ruta, "w", encoding="utf-8", newline="") as handle:
        escritor = csv.writer(handle)
        escritor.writerow(
            [
                "t_h",
                "T_max_global_C",
                "T_max_core_C",
                "T_min_surface_C",
                "delta_T_C",
                "T_media_C",
            ]
        )
        for indice in range(result.time_h.size):
            escritor.writerow(
                [
                    f"{result.time_h[indice]:.6f}",
                    f"{result.T_max_global[indice]:.4f}",
                    f"{result.T_max_core[indice]:.4f}",
                    f"{result.T_min_surface[indice]:.4f}",
                    f"{result.delta_T[indice]:.4f}",
                    f"{result.T_mean[indice]:.4f}",
                ]
            )


def _escribir_campo(ruta: Path, model, result) -> None:
    grid = model.grid
    x, y, z = grid.centers()
    T = result.T_final
    activo = result.active_final
    with open(ruta, "w", encoding="utf-8", newline="") as handle:
        escritor = csv.writer(handle)
        escritor.writerow(["x", "y", "z", "T_C", "activo"])
        indices = np.flatnonzero(activo.ravel())
        for indice in indices:
            i, j, k = grid.unravel(np.array([indice]))
            escritor.writerow(
                [
                    f"{x[i[0]]:.3f}",
                    f"{y[j[0]]:.3f}",
                    f"{z[k[0]]:.3f}",
                    f"{T.ravel()[indice]:.4f}",
                    1,
                ]
            )


def _graficar_series(ruta: Path, result, criterios) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figura, ejes = plt.subplots(figsize=(9, 5))
    ejes.plot(result.time_h, result.T_max_core, label="T max nucleo")
    ejes.plot(result.time_h, result.T_max_global, label="T max global", linestyle="--")
    ejes.plot(result.time_h, result.T_min_surface, label="T min superficie")
    ejes.plot(result.time_h, result.T_min_surface + criterios.delta_T_max_C, label="criterio dT", color="C3", linestyle=":")
    ejes.axhline(criterios.T_max_C, color="C1", linestyle="-.", label="limite T max")
    ejes.set_xlabel("tiempo [h]")
    ejes.set_ylabel("temperatura [C]")
    ejes.set_title("Losa de fundacion: series termicas")
    ejes.grid(alpha=0.3)
    ejes.legend(loc="best", fontsize=8)
    figura.tight_layout()
    figura.savefig(ruta, dpi=140)
    plt.close(figura)


def _graficar_campo(ruta: Path, model, result) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    indice = int(np.nanargmax(result.delta_T))
    campo = result.T_final
    plano = campo[:, :, campo.shape[2] // 2]
    mascara = result.active_final[:, :, campo.shape[2] // 2]
    figura, ejes = plt.subplots(figsize=(8, 5))
    imagen = ejes.imshow(
        np.ma.masked_where(~mascara, plano.T),
        origin="lower",
        cmap="inferno",
        aspect="auto",
    )
    figura.colorbar(imagen, ax=ejes, label="T [C]")
    ejes.set_title(f"Campo de temperatura en t = {result.time_h[indice]:.1f} h")
    ejes.set_xlabel("x [m]")
    ejes.set_ylabel("y [m]")
    figura.tight_layout()
    figura.savefig(ruta, dpi=140)
    plt.close(figura)


def _graficar_confiabilidad(ruta: Path, muestra) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figura, ejes = plt.subplots(1, 2, figsize=(11, 4))
    ejes[0].hist(muestra.T_max, bins=25, color="C0", edgecolor="white")
    ejes[0].axvline(muestra.lim_T_max_C, color="C1", linestyle="--", label="limite 70 C")
    ejes[0].set_title("T maxima")
    ejes[0].set_xlabel("T max [C]")
    ejes[0].legend(fontsize=8)
    ejes[1].hist(muestra.delta_T_max, bins=25, color="C2", edgecolor="white")
    ejes[1].axvline(muestra.lim_delta_T_C, color="C1", linestyle="--", label="limite 20 C")
    ejes[1].set_title("Diferencial termico")
    ejes[1].set_xlabel("delta T [C]")
    ejes[1].legend(fontsize=8)
    figura.tight_layout()
    figura.savefig(ruta, dpi=140)
    plt.close(figura)


def main() -> int:
    analizador = argparse.ArgumentParser(description="Ejecuta un caso y guarda resultados.")
    analizador.add_argument("--plan", default="datos/caso_fundacion.yaml")
    analizador.add_argument("--salida", default="validacion/caso_fundacion")
    analizador.add_argument("--montecarlo", type=int, default=0, help="numero de muestras")
    analizador.add_argument("--semilla", type=int, default=20240915)
    analizador.add_argument("--dx", type=float, default=None, help="override del paso de grilla")
    analizador.add_argument("--duracion-h", type=float, default=None)
    analizador.add_argument("--sin-graficos", action="store_true")
    argumentos = analizador.parse_args()

    plan = load_plan(str(RAIZ / argumentos.plan) if not Path(argumentos.plan).is_absolute() else argumentos.plan)
    if argumentos.dx:
        plan.geometria.dx = argumentos.dx
    if argumentos.duracion_h:
        plan.simulacion.duracion_h = argumentos.duracion_h

    salida = RAIZ / argumentos.salida
    salida.mkdir(parents=True, exist_ok=True)

    print(f"Caso: {plan.caso}")
    print(f"Grilla: dx = {plan.geometria.dx} m")
    model = build_model(plan)
    print(
        f"Celdas: {model.grid.n_cells}  "
        f"dx={model.grid.dx} m  "
        f"nucleo={int(model.is_core.sum())}  superficie={int(model.is_surface.sum())}"
    )

    result = solve(
        model,
        duracion_h=plan.simulacion.duracion_h,
        intervalo_salida_h=plan.simulacion.intervalo_salida_h,
        factor_estabilidad=plan.simulacion.factor_estabilidad,
    )
    veredicto = evaluar_criterios(result, plan.criterios)
    print(veredicto.resumen())
    print(f"dt = {result.dt_s:.1f} s, pasos = {result.metadata['pasos']}")

    _escribir_series(salida / "series.csv", result)
    _escribir_campo(salida / "campo_final.csv", model, result)
    if not argumentos.sin_graficos:
        _graficar_series(salida / "series.png", result, plan.criterios)
        _graficar_campo(salida / "campo_peak.png", model, result)

    resumen = {
        "caso": plan.caso,
        "descripcion": plan.descripcion.strip(),
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _commit(),
        "python": platform.python_version(),
        "plan": argumentos.plan,
        "geometria": {
            "dx_m": plan.geometria.dx,
            "n_celdas": int(model.grid.n_cells),
            "celdas_nucleo": int(model.is_core.sum()),
            "celdas_superficie": int(model.is_surface.sum()),
        },
        "simulacion": {
            "duracion_h": plan.simulacion.duracion_h,
            "intervalo_salida_h": plan.simulacion.intervalo_salida_h,
            "dt_s": result.dt_s,
            "pasos": result.metadata["pasos"],
        },
        "criterios": veredicto.to_dict(),
        "series": {
            "T_max_global_C": float(np.nanmax(result.T_max_global)),
            "T_max_core_C": float(np.nanmax(result.T_max_core)),
            "T_min_surface_C": float(np.nanmin(result.T_min_surface)),
            "delta_T_max_C": float(np.nanmax(result.delta_T)),
            "T_media_final_C": float(result.T_mean[-1]),
        },
    }

    if argumentos.montecarlo > 0:
        print(f"Monte Carlo: {argumentos.montecarlo} muestras (semilla {argumentos.semilla})")
        muestra = ejecutar_montecarlo(
            plan,
            n_muestras=argumentos.montecarlo,
            semilla=argumentos.semilla,
            verbose=True,
        )
        resumen["confiabilidad"] = muestra.to_dict()
        print(
            f"P(T_max > 70 C) = {muestra.prob_T_max:.3f}   "
            f"P(delta_T > 20 C) = {muestra.prob_delta_T:.3f}"
        )
        with open(salida / "confiabilidad.json", "w", encoding="utf-8") as handle:
            json.dump(muestra.to_dict(), handle, indent=2, ensure_ascii=False)
        if not argumentos.sin_graficos:
            _graficar_confiabilidad(salida / "confiabilidad.png", muestra)

    with open(salida / "resumen.json", "w", encoding="utf-8") as handle:
        json.dump(resumen, handle, indent=2, ensure_ascii=False)

    print(f"Resultados guardados en {salida}")
    return 0 if veredicto.cumple else 1


if __name__ == "__main__":
    raise SystemExit(main())
