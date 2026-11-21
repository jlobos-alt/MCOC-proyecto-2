"""E14: agregación de resultados Monte Carlo y convergencia P_f(N).

Lee muestras por tramos (salida de Slurm array) o archivos completos de E13,
extrae métricas, calcula P_f(N) con IC de Wilson y genera resumen + figura.

Uso:
  python scripts/e14_agregar.py --entrada results/e13 --salida results/e14
  python scripts/e14_agregar.py --entrada results/e14/array_12345 --salida results/e14/agregado --patron "muestras_B_*.csv"
  python scripts/e14_agregar.py --entrada results/e13 --salida results/e14 --conjuntos A B
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcplan.incertidumbre import cota_cero_fallas, estimar, wilson  # noqa: E402

SUP, TINTA, TINTA2, GRILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
COLORES = {"A": "#2a78d6", "B": "#eb6834"}


def leer_csv(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def cargar_muestras(entrada: Path, conjunto: str, patron: str | None) -> list[dict]:
    if patron:
        archivos = sorted(entrada.glob(patron))
    else:
        # Preferir tramos; si no, archivo completo
        archivos = sorted(entrada.glob(f"muestras_{conjunto}_*_*.csv"))
        if not archivos:
            completo = entrada / f"muestras_{conjunto}.csv"
            if completo.exists():
                archivos = [completo]
    if not archivos:
        raise FileNotFoundError(f"No se encontraron muestras para conjunto {conjunto} en {entrada}")
    filas = []
    for a in archivos:
        filas.extend(leer_csv(a))
    # ordenar por indice si existe para reproducibilidad de la curva P_f(N)
    if filas and "indice" in filas[0]:
        filas.sort(key=lambda r: int(float(r["indice"])))
    return filas


def serie_pf(filas: list[dict], limite: float, clave: str) -> dict:
    valores = np.array([float(r[clave]) for r in filas], dtype=float)
    falla = (limite - valores) <= 0  # g <= 0
    n = np.arange(1, len(falla) + 1)
    k = np.cumsum(falla)
    p_hat = k / n
    lo, hi = [], []
    se, cov = [], []
    for kk, nn in zip(k, n):
        a, b = wilson(int(kk), int(nn))
        lo.append(a)
        hi.append(b)
        p = kk / nn
        s = math.sqrt(p * (1 - p) / nn)
        se.append(s)
        cov.append((s / p) if p > 0 else math.inf)
    return {
        "n": n.tolist(),
        "k": k.tolist(),
        "p_hat": p_hat.tolist(),
        "wilson_lo": lo,
        "wilson_hi": hi,
        "se": se,
        "cov": cov,
        "p_final": float(p_hat[-1]),
        "k_final": int(k[-1]),
        "n_final": int(n[-1]),
        "ic95_final": [float(lo[-1]), float(hi[-1])],
    }


def resumen_conjunto(filas: list[dict]) -> dict:
    T = np.array([float(r["T_max"]) for r in filas], dtype=float)
    dT = np.array([float(r["dT_max"]) for r in filas], dtype=float)
    gT = 70.0 - T
    gdT = 20.0 - dT
    gsis = np.minimum(gT, gdT)
    res = {
        "n": len(filas),
        "T_max": {"media": float(T.mean()), "desv": float(T.std(ddof=1)), "P05": float(np.quantile(T, 0.05)), "P95": float(np.quantile(T, 0.95)), "min": float(T.min()), "max": float(T.max())},
        "dT_max": {"media": float(dT.mean()), "desv": float(dT.std(ddof=1)), "P05": float(np.quantile(dT, 0.05)), "P95": float(np.quantile(dT, 0.95)), "min": float(dT.min()), "max": float(dT.max())},
        "P_Tmax_gt_70": estimar(gT),
        "P_dTmax_gt_20": estimar(gdT),
        "P_sistema": estimar(gsis),
    }
    res["PfN_Tmax"] = serie_pf(filas, 70.0, "T_max")
    res["PfN_dTmax"] = serie_pf(filas, 20.0, "dT_max")
    return res


def guardar_convergencia_csv(resumen: dict, ruta: Path) -> None:
    campos = ["conjunto", "n", "k_Tmax", "Pf_Tmax", "wilson_lo_Tmax", "wilson_hi_Tmax", "k_dT", "Pf_dT", "wilson_lo_dT", "wilson_hi_dT"]
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for nombre, r in resumen["conjuntos"].items():
            a = r["PfN_Tmax"]
            b = r["PfN_dTmax"]
            for i in range(r["n"]):
                w.writerow({
                    "conjunto": nombre,
                    "n": a["n"][i],
                    "k_Tmax": a["k"][i],
                    "Pf_Tmax": a["p_hat"][i],
                    "wilson_lo_Tmax": a["wilson_lo"][i],
                    "wilson_hi_Tmax": a["wilson_hi"][i],
                    "k_dT": b["k"][i],
                    "Pf_dT": b["p_hat"][i],
                    "wilson_lo_dT": b["wilson_lo"][i],
                    "wilson_hi_dT": b["wilson_hi"][i],
                })


def _estilo(ax):
    ax.set_facecolor(SUP)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRILLA)
    ax.tick_params(colors=TINTA2, labelsize=8, length=0)
    ax.grid(True, color=GRILLA, linewidth=0.6)
    ax.set_axisbelow(True)


def figura_convergencia(resumen: dict, ruta: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), facecolor=SUP, constrained_layout=True)
    specs = [
        ("PfN_Tmax", "P_f(N) = P(Tmax > 70 °C)", axes[0]),
        ("PfN_dTmax", "P_f(N) = P(ΔT > 20 °C)", axes[1]),
    ]
    for key, titulo, ax in specs:
        for nombre, r in resumen["conjuntos"].items():
            s = r[key]
            n = np.array(s["n"])
            p = np.array(s["p_hat"])
            lo = np.array(s["wilson_lo"])
            hi = np.array(s["wilson_hi"])
            color = COLORES.get(nombre, "#333333")
            # evitar log(0): mostrar cota visual
            p_plot = np.where(p > 0, p, np.nan)
            ax.plot(n, p_plot, color=color, linewidth=2, label=f"Conjunto {nombre}: p̂(N)")
            ax.fill_between(n, lo, hi, color=color, alpha=0.15, label=f"Conjunto {nombre}: IC95% Wilson")
            if p[-1] == 0:
                cota = np.array([cota_cero_fallas(int(x)) for x in n])
                ax.plot(n, cota, color=color, linestyle=":", linewidth=1.5, label=f"Conjunto {nombre}: cota 0 fallas ≈ 3/N")
        ax.set_xlabel("Número de muestras N")
        ax.set_ylabel("Probabilidad de falla")
        ax.set_title(titulo)
        ax.set_ylim(bottom=0)
        ax.legend(frameon=False, fontsize=7, loc="best")
        _estilo(ax)
    fig.savefig(ruta, dpi=170, facecolor=SUP)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entrada", type=Path, default=ROOT / "results" / "e13")
    ap.add_argument("--salida", type=Path, default=ROOT / "results" / "e14")
    ap.add_argument("--conjuntos", nargs="+", default=["A", "B"])
    ap.add_argument("--patron", default=None, help="Patrón glob para tramos, ej. 'muestras_B_*.csv'")
    args = ap.parse_args()

    args.salida.mkdir(parents=True, exist_ok=True)
    resumen = {"entrada": str(args.entrada), "conjuntos": {}, "metadatos": {}}

    for c in args.conjuntos:
        filas = cargar_muestras(args.entrada, c, args.patron)
        r = resumen_conjunto(filas)
        resumen["conjuntos"][c] = r
        print(f"[{c}] N={r['n']} P(Tmax>70)={r['P_Tmax_gt_70']['p_hat']:.4f} IC95={r['P_Tmax_gt_70']['IC95_wilson']}  P(dT>20)={r['P_dTmax_gt_20']['p_hat']:.4f}")

    guardar_convergencia_csv(resumen, args.salida / "convergencia_pf.csv")
    figura_convergencia(resumen, args.salida / "e14_convergencia_pf.png")

    # metadata de reproducibilidad
    resumen["metadatos"] = {
        "script": "scripts/e14_agregar.py",
        "descripcion": "Agregación de tramos Monte Carlo y convergencia P_f(N)",
        "independencia": "Cada muestra i se genera con default_rng([semilla, i]); el valor de la muestra no depende del orden, del worker ni del tramo. Los tramos son particiones disjuntas de índices.",
        "estimador": "p_hat = N_f/N; IC95 Wilson; CoV=sqrt((1-p)/(N*p)); cota 0 fallas: p <= 1-0.05^(1/N).",
    }
    (args.salida / "resumen_e14.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Escrito: {args.salida / 'resumen_e14.json'}")
    print(f"Escrito: {args.salida / 'convergencia_pf.csv'}")
    print(f"Escrito: {args.salida / 'e14_convergencia_pf.png'}")


if __name__ == "__main__":
    main()
