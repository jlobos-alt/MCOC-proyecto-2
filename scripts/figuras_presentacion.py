"""Figuras simples para la presentación de la defensa, desde los resultados ya calculados.

Lee results/defensa/corridas.csv y results/visor/ (series de las mismas 1152 corridas).
Escribe en results/defensa/presentacion/.
"""
import base64
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "defensa" / "presentacion"
OUT.mkdir(parents=True, exist_ok=True)
INK, MUTED, ORANGE, TEAL, DARK, RED, GREY = "#1D2D35", "#5B6B73", "#E76F51", "#2A9D8F", "#264653", "#C0392B", "#9AA5AB"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False})

filas = list(csv.DictReader(open(ROOT / "results/defensa/corridas.csv", encoding="utf-8")))
CURVAS = ["M1_SS", "M2_SS", "M3_SS", "M4_SS", "M1_22A", "M2_22A", "M3_22A", "M4_22A"]
CLIMAS = [("frio", "Frío\n35,5 %"), ("medio", "Medio\n32,3 %"), ("calido", "Cálido\n32,3 %")]


def matriz(plan):
    M = np.zeros((8, 3))
    for f in filas:
        if f["plan"] == plan:
            M[CURVAS.index(f["curva"]), [c for c, _ in CLIMAS].index(f["clima"])] = float(f["MDelta"])
    return M


# 1. Grilla de los 24 escenarios: propuesta frente a esperar 6 h
cmap = LinearSegmentedColormap.from_list("dt", ["#D8F0EC", "#9FD8CF", "#F4D58D", "#E76F51", "#B23A2B"])
fig, axes = plt.subplots(1, 2, figsize=(11, 6.2))
for ax, plan, titulo in zip(axes, ["unica_EPS150_Tcol10", "5v_espera6h_EPS150_Tcol10"],
                            ["Propuesta: P_f = 0 %", "Esperar 6 h: P_f = 25 %"]):
    M = matriz(plan)
    ax.imshow(M, cmap=cmap, vmin=8, vmax=24, aspect="auto")
    for i in range(8):
        for j in range(3):
            falla = M[i, j] > 20
            ax.text(j, i, f"{M[i, j]:.1f}".replace(".", ","), ha="center", va="center", fontsize=14,
                    color="white" if falla else INK, fontweight="bold" if falla else "normal")
            if falla:
                ax.add_patch(plt.Rectangle((j - .48, i - .48), .96, .96, fill=False, ec=RED, lw=3))
    ax.set_xticks(range(3), [l for _, l in CLIMAS])
    ax.set_yticks(range(8), CURVAS)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(titulo, fontsize=17, color=TEAL if "0 %" in titulo else RED, fontweight="bold", pad=12)
fig.text(0.5, 0.015, "Cada celda = una corrida completa (curva × clima). Valor = MΔ [°C]. Borde rojo = falla (MΔ > 20 °C).",
         ha="center", color=MUTED, fontsize=12)
fig.tight_layout(rect=(0, 0.05, 1, 1))
fig.savefig(OUT / "escenarios_24.png", dpi=200)
plt.close(fig)

# 2. MΔ(t) de los 4 casos en el mismo escenario (M4_SS, clima medio)
meta = json.loads((ROOT / "results/visor/meta.json").read_text(encoding="utf-8"))
serie = np.frombuffer(base64.b64decode((ROOT / "results/visor/series.txt").read_text()), dtype="<i2")
m, k = CURVAS.index("M4_SS"), 1


def mdelta(plan):
    ip = meta["orden_planes"].index(plan)
    pos, n = meta["series"]["offsets"][f"{ip}_{m}_{k}"]
    a, b = serie[pos:pos + n].astype(float), serie[pos + n:pos + 2 * n].astype(float)
    ok = (a != -32768) & (b != -32768)
    d = np.where(ok, (a - b) / 100, np.nan)
    return np.arange(n), d


casos = [("unica_ninguna_Tcol18", "Una vertida sin protección, 18 °C", GREY, 1.6),
         ("5v_espera48h_EPS150_Tcol10", "5 vertidas, espera 48 h", DARK, 2.0),
         ("5v_espera6h_EPS150_Tcol10", "5 vertidas, espera 6 h", TEAL, 2.4),
         ("unica_EPS150_Tcol10", "Propuesta: una vertida, EPS 150, 10 °C", ORANGE, 3.4)]
fig, ax = plt.subplots(figsize=(11, 5.8))
ax.axhspan(20, 46, color="#F6DFDB", zorder=0)
ax.axhline(20, color=RED, lw=1.8, ls="--")
ax.text(338, 20.6, "límite 20 °C", color=RED, ha="right", fontsize=13)
for plan, nombre, color, lw in casos:
    t, d = mdelta(plan)
    sel = t <= 336
    ax.plot(t[sel], d[sel], color=color, lw=lw, label=nombre)
ax.set_xlim(0, 340)
ax.set_ylim(-2, 45)
ax.set_xlabel("horas desde t₀ (19-nov 08:00)")
ax.set_ylabel("ΔT = T máx − T mín a 25 mm [°C]")
caja = dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.9)
ax.annotate("espera 6 h: salta a 20,7 °C\nal terminar de colocar (42 h)", xy=(42, 20.7), xytext=(62, 27),
            color=TEAL, fontsize=12, bbox=caja, arrowprops=dict(arrowstyle="->", color=TEAL))
ax.annotate("propuesta: máx. 16,0 °C", xy=(330, 15.9), xytext=(215, 4), color=ORANGE, fontsize=13,
            fontweight="bold", bbox=caja, arrowprops=dict(arrowstyle="->", color=ORANGE))
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), frameon=False, fontsize=11.5, ncol=2)
ax.set_title("Mismo escenario para los 4 casos: curva M4_SS, clima medio", color=MUTED, fontsize=12, loc="left")
fig.tight_layout()
fig.savefig(OUT / "mdelta_4casos.png", dpi=200)
plt.close(fig)

# 3. Recortes de figuras existentes
cortes = Image.open(ROOT / "results/defensa/complementos/mecanismo_cortes.png")
cortes.crop((925, 10, 1545, 400)).save(OUT / "corte_propuesta.png")
cortes.crop((200, 400, 820, 790)).save(OUT / "corte_espera6h.png")
print("Figuras en", OUT)
