"""Visualizador termico interactivo sobre el solver 3D del proyecto (mcplan).

Abre una ventana con:
  - a la izquierda: el caso, los parametros (sliders) y el boton "Simular";
  - mapa termico: barra (1D), placa (2D) o bloque de voxels con un corte (3D);
  - perfil de temperatura numerico vs solucion exacta;
  - curva de calor T(t) en puntos de control (centro, borde/superficie);
  - un slider de tiempo para recorrer la simulacion sin recalcular.

Cada "Simular" arma un plan, llama a build_model + solve (el mismo solver del
caso real) en N_FOTOS tramos y guarda el campo de cada tramo.

Uso:
    python scripts/visualizador_termico.py
    python scripts/visualizador_termico.py --prueba carpeta   # sin ventana: PNG de cada caso
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from mcplan.plan import plan_from_dict  # noqa: E402
from mcplan.thermal import build_model, estimate_timestep, solve  # noqa: E402
from mcplan.verificacion import CONCRETO, difusividad, plan_caja  # noqa: E402

N_FOTOS = 40          # campos guardados para el slider de tiempo
N_LATERAL = 6         # celdas en x e y para los casos de borde (el problema varia en z)
N_MAX_3D = 16         # tope de celdas por eje en el seno 3D (dibujar voxels es lento)
N_SERIE = 200         # terminos de las series de Fourier exactas
MAX_PASOS = 100_000   # sobre esto la ventana se congelaria (~0.3 ms por paso)


class SimulacionMuyLarga(Exception):
    """El dt estable es tan chico que la simulacion tardaria demasiado."""

CASOS = [
    "Seno 1D", "Seno 2D", "Seno 3D",
    "Dirichlet base/techo", "Adiabatico dT/dn=0", "Robin beta",
    "Fuente q0", "Neumann q_n",
]

# Sliders comunes: clave -> (etiqueta, min, max, inicial, paso)
COMUNES = {
    "n": ("celdas n", 4, 40, 12, 1),
    "t_h": ("t final [h]", 1, 2000, 300, 1),
    "Lx": ("Lx [m]", 0.2, 5.0, 3.0, 0.1),
    "Ly": ("Ly [m]", 0.2, 5.0, 3.0, 0.1),
    "Lz": ("Lz / H [m]", 0.1, 3.0, 0.6, 0.05),
}

# Sliders propios de cada caso
PROPIOS = {
    "Seno 1D": {"T0": ("T0 [C]", 0, 40, 20, 1), "A": ("amplitud A [C]", 1, 30, 10, 1)},
    "Seno 2D": {"T0": ("T0 [C]", 0, 40, 20, 1), "A": ("amplitud A [C]", 1, 30, 10, 1)},
    "Seno 3D": {"T0": ("T0 [C]", 0, 40, 20, 1), "A": ("amplitud A [C]", 1, 30, 10, 1)},
    "Dirichlet base/techo": {"Tbase": ("T base [C]", 0, 60, 20, 1), "Ttecho": ("T techo [C]", 0, 60, 30, 1)},
    "Adiabatico dT/dn=0": {"Tbase": ("T0 abajo [C]", 0, 60, 20, 1), "Ttecho": ("T0 arriba [C]", 0, 60, 30, 1)},
    "Robin beta": {"Tbase": ("T base [C]", 0, 60, 30, 1), "beta": ("beta = h/k [1/m]", 0.1, 100, 5, 0.1),
                   "Taire": ("T aire [C]", -5, 40, 20, 1)},
    "Fuente q0": {"T0": ("T0 [C]", 0, 40, 20, 1), "q0": ("q0 [W/m3]", 0, 3000, 1000, 50)},
    "Neumann q_n": {"qn": ("q_n base [W/m2]", -300, 300, -100, 10), "Ttecho": ("T techo [C]", 0, 60, 20, 1)},
}

AYUDA = {
    "Seno 1D": "Dirichlet T0 en x=0 y x=Lx. Exacta: T0 + A sin(pi x/Lx) e^(-a lam t)",
    "Seno 2D": "Dirichlet T0 en los 4 bordes. lam = (pi/Lx)^2 + (pi/Ly)^2",
    "Seno 3D": "Dirichlet T0 en las 6 caras. lam = suma de los 3 (pi/L)^2",
    "Dirichlet base/techo": "Base y techo a T fija, costados adiabaticos. Regimen: recta en z",
    "Adiabatico dT/dn=0": "Ninguna cara deja pasar calor. Energia constante, termina en el promedio",
    "Robin beta": "Base a T fija, techo -k dT/dn = h (T - T_aire), h = k beta",
    "Fuente q0": "Todo adiabatico + fuente q0. Exacta: T0 + q0 t/(rho cp)",
    "Neumann q_n": "Flujo q_n en la base (<0 entra), techo a T fija. Regimen: recta",
}


# ---------------------------------------------------------------------------
# Simulacion
# ---------------------------------------------------------------------------

def _dirichlet_caras(ejes, T):
    return [{"name": "dirichlet", "direccion": "ejes", "ejes": list(ejes), "signo": "ambos",
             "tipo": "dirichlet", "valor_dirichlet_C": T}]


def _cara_z(nombre, signo, **kw):
    return {"name": nombre, "direccion": "ejes", "ejes": [2], "signo": signo, **kw}


def _raices_robin(Bi: float, n: int) -> np.ndarray:
    """Raices x_m de Bi sin x + x cos x = 0 (equivale a tan x = -x/Bi), una en ((m-1/2)pi, m pi).

    Vienen de X(z) = sin(mu z) con X(0) = 0 (Dirichlet) y -k X'(H) = h X(H) (Robin), x = mu H.
    """
    m = np.arange(1, n + 1)
    lo, hi = (m - 0.5) * np.pi, m * np.pi
    f = lambda x: Bi * np.sin(x) + x * np.cos(x)
    for _ in range(60):  # biseccion
        mid = 0.5 * (lo + hi)
        mismo = np.sign(f(mid)) == np.sign(f(lo))
        lo, hi = np.where(mismo, mid, lo), np.where(mismo, hi, mid)
    return 0.5 * (lo + hi)


def _serie_transitoria(z_c, H, alpha, T_regimen, u0, autofuncion, mu):
    """T(z,t) = T_regimen(z) + sum_m b_m X_m(z) exp(-alpha mu_m^2 t).

    b_m = int u0 X_m / int X_m^2 (proyeccion; las X_m son ortogonales), u0 = T_inicial - T_regimen.
    """
    zf = np.linspace(0.0, H, 4001)
    Xf = autofuncion(np.outer(zf, mu))
    b = np.trapezoid(u0(zf)[:, None] * Xf, zf, axis=0) / np.trapezoid(Xf ** 2, zf, axis=0)
    Xc = autofuncion(np.outer(z_c, mu))
    return lambda t_s: T_regimen(z_c) + Xc @ (b * np.exp(-alpha * mu ** 2 * t_s))


def simular(caso: str, p: dict) -> dict:
    """Corre el caso y devuelve campos en N_FOTOS+1 instantes y la solucion exacta."""
    mat = CONCRETO
    alpha = difusividad(mat)
    k = mat["k"]
    t_h = float(p["t_h"])
    sim = {"caso": caso, "nota": ""}

    if caso.startswith("Seno"):
        dim = int(caso[5])
        n = int(p["n"])
        if dim == 3 and n > N_MAX_3D:
            sim["nota"] = f"(n limitado a {N_MAX_3D} en 3D para dibujar rapido)"
            n = N_MAX_3D
        L_act = [p["Lx"], p["Ly"], p["Lz"]][:dim]
        largos = tuple(L_act[e] if e < dim else L_act[0] / n for e in range(3))
        celdas = tuple(n if e < dim else 1 for e in range(3))
        T0, A = p["T0"], p["A"]
        model = build_model(plan_from_dict(plan_caja(largos, celdas, mat, _dirichlet_caras(range(dim), T0), T0)))
        X = np.meshgrid(*model.grid.centers(), indexing="ij")
        forma = np.ones(model.grid.shape)
        lam = 0.0
        for e in range(dim):
            forma = forma * np.sin(np.pi * X[e] / largos[e])
            lam += (np.pi / largos[e]) ** 2
        inicial = T0 + A * forma
        sim["exacta"] = lambda t_s: T0 + A * forma * np.exp(-alpha * lam * t_s)
        sim["exacta_es_transitoria"] = True
        sim["lim"] = (T0, T0 + A)
        c = tuple(s // 2 for s in celdas)
        sim["sondas"] = {"centro": c, "junto al borde": (0,) + c[1:]}
        sim["tau_h"] = 1.0 / (alpha * lam) / 3600.0
        sim["eje_perfil"] = 0
        sim["dim"] = dim
        fuente = 0.0
    else:
        n = int(p["n"])
        H = p["Lz"]
        largos = (p["Lx"], p["Ly"], H)
        celdas = (N_LATERAL, N_LATERAL, n)
        z_c = (np.arange(n) + 0.5) * H / n
        fuente = 0.0
        T_amb = 20.0

        if caso == "Dirichlet base/techo":
            Ta, Tb = p["Tbase"], p["Ttecho"]
            fronteras = [_cara_z("base", "-", tipo="dirichlet", valor_dirichlet_C=Ta),
                         _cara_z("techo", "+", tipo="dirichlet", valor_dirichlet_C=Tb)]
            T_ini = Ta
            m_ = np.arange(1, N_SERIE + 1)
            b = 2.0 * (Tb - Ta) * (-1.0) ** m_ / (m_ * np.pi)
            seno = np.sin(np.outer(z_c, m_) * np.pi / H)

            def perfil(t_s):
                return Ta + (Tb - Ta) * z_c / H + seno @ (b * np.exp(-alpha * (m_ * np.pi / H) ** 2 * t_s))
            sim["exacta_es_transitoria"] = True
            sim["lim"] = (min(Ta, Tb), max(Ta, Tb))
        elif caso == "Adiabatico dT/dn=0":
            Ta, Tb = p["Tbase"], p["Ttecho"]
            fronteras = []
            T_ini = None
            m_ = np.arange(1, N_SERIE + 1)
            a = 2.0 * (Tb - Ta) * ((-1.0) ** m_ - 1.0) / (m_ * np.pi) ** 2
            coseno = np.cos(np.outer(z_c, m_) * np.pi / H)

            def perfil(t_s):
                return (Ta + Tb) / 2 + coseno @ (a * np.exp(-alpha * (m_ * np.pi / H) ** 2 * t_s))
            sim["exacta_es_transitoria"] = True
            sim["lim"] = (min(Ta, Tb), max(Ta, Tb))
        elif caso == "Robin beta":
            Ta, Tair = p["Tbase"], p["Taire"]
            h = k * p["beta"]
            T_amb = Tair
            fronteras = [_cara_z("base", "-", tipo="dirichlet", valor_dirichlet_C=Ta),
                         _cara_z("aire", "+", tipo="convectiva", h=h)]
            T_ini = Ta
            q = (Ta - Tair) / (H / k + 1.0 / h)
            mu = _raices_robin(h * H / k, N_SERIE) / H
            perfil = _serie_transitoria(z_c, H, alpha, lambda z: Ta - q * z / k,
                                        lambda z: Ta - (Ta - q * z / k), np.sin, mu)
            sim["exacta_es_transitoria"] = True
            sim["lim"] = (min(Ta, Tair), max(Ta, Tair))
            sim["mu1"] = mu[0]
            sim["nota"] = f"h = {h:.1f} W/m2K, q = {q:.1f} W/m2, T sup. regimen = {Ta - q * H / k:.2f} C"
        elif caso == "Fuente q0":
            T0 = p["T0"]
            fuente = p["q0"]
            fronteras = []
            T_ini = T0
            rho_cp = mat["rho"] * mat["cp"]

            def perfil(t_s):
                return np.full_like(z_c, T0 + fuente * t_s / rho_cp)
            sim["exacta_es_transitoria"] = True
            sim["nota"] = f"dT/dt = q0/(rho cp) = {fuente / rho_cp * 3600:.3f} C/h"
            sim["lim"] = (min(T0, T0 + fuente * t_h * 3600 / rho_cp), max(T0, T0 + fuente * t_h * 3600 / rho_cp))
        elif caso == "Neumann q_n":
            qn, Tb = p["qn"], p["Ttecho"]
            fronteras = [_cara_z("flujo", "-", tipo="neumann", flujo_W_m2=qn),
                         _cara_z("techo", "+", tipo="dirichlet", valor_dirichlet_C=Tb)]
            T_ini = Tb
            mu = (np.arange(1, N_SERIE + 1) - 0.5) * np.pi / H
            perfil = _serie_transitoria(z_c, H, alpha, lambda z: Tb - qn * (H - z) / k,
                                        lambda z: qn * (H - z) / k, np.cos, mu)
            sim["exacta_es_transitoria"] = True
            sim["lim"] = (min(Tb, Tb - qn * H / k), max(Tb, Tb - qn * H / k))
            sim["mu1"] = mu[0]
            sim["nota"] = f"q_n = {qn:g} W/m2 ({'entra' if qn < 0 else 'sale'} calor por la base)"
        else:
            raise ValueError(caso)

        model = build_model(plan_from_dict(plan_caja(largos, celdas, mat, fronteras, T_ini or 20.0, T_amb)))
        if T_ini is None:
            inicial = np.broadcast_to(p["Tbase"] + (p["Ttecho"] - p["Tbase"]) * z_c / H, model.grid.shape).copy()
        else:
            inicial = np.full(model.grid.shape, float(T_ini))
        sim["exacta"] = lambda t_s: np.broadcast_to(perfil(t_s), model.grid.shape)
        i = N_LATERAL // 2
        sim["sondas"] = {"base": (i, i, 0), "centro": (i, i, n // 2), "techo": (i, i, n - 1)}
        sim["eje_perfil"] = 2
        sim["dim"] = 3
        # modo mas lento: (pi/H)^2 con dos caras fijas o aisladas, (pi/2H)^2 si una es Robin/Neumann
        lam_lento = {"Dirichlet base/techo": (np.pi / H) ** 2, "Adiabatico dT/dn=0": (np.pi / H) ** 2,
                     "Robin beta": sim.get("mu1", 0.0) ** 2, "Neumann q_n": sim.get("mu1", 0.0) ** 2}.get(caso)
        sim["tau_h"] = 1.0 / (alpha * lam_lento) / 3600.0 if lam_lento else None

    # dt estable ~ dx^2/alpha: con celdas muy chicas y t largo hay demasiados pasos
    pasos = t_h * 3600.0 / estimate_timestep(model)
    if pasos > MAX_PASOS:
        d_min = min(model.grid.dx, model.grid.dy, model.grid.dz)
        raise SimulacionMuyLarga(
            f"Demasiados pasos: {pasos:,.0f} (dt estable ~ {t_h * 3600 / pasos:.1f} s con celdas de "
            f"{d_min * 1000:.1f} mm).\nBaja 'celdas n' o 't final', o sube el tamano del bloque.")

    # integrar en tramos para guardar el campo en cada instante
    tiempos = np.linspace(0.0, t_h, N_FOTOS + 1)
    campos = [inicial.copy()]
    T = inicial.ravel()
    inicio = time.perf_counter()
    dt_s = None
    for t0, t1 in zip(tiempos[:-1], tiempos[1:]):
        res = solve(model, duracion_h=t1 - t0, intervalo_salida_h=t1 - t0,
                    temperatura_inicial=T, fuente_W_m3=fuente)
        T = res.T_final.ravel()
        campos.append(res.T_final.copy())
        dt_s = res.dt_s
    sim.update(model=model, q0=fuente, tiempos=tiempos, campos=campos, dt_s=dt_s,
               segundos=time.perf_counter() - inicio, largos=largos)
    return sim


# ---------------------------------------------------------------------------
# Dibujo
# ---------------------------------------------------------------------------

def _linea(campo, eje, sonda):
    i, j, k = sonda
    if eje == 0:
        return campo[:, j, k]
    return campo[i, j, :]


class Visualizador:
    def __init__(self, fig):
        from matplotlib.widgets import Button, RadioButtons, Slider

        self.fig = fig
        self.Slider = Slider
        self.valores = {clave: d[3] for clave, d in COMUNES.items()}
        # cada caso guarda sus propios valores (T base del Robin no es la del Dirichlet)
        self.propios = {caso: {clave: d[3] for clave, d in props.items()} for caso, props in PROPIOS.items()}
        self.caso = CASOS[0]
        self.sim = None
        self.ax_mapa = None

        fig.text(0.01, 0.975, "Caso", fontsize=11, weight="bold")
        ax_radio = fig.add_axes([0.01, 0.62, 0.19, 0.35])
        self.radio = RadioButtons(ax_radio, CASOS, active=0)
        self.radio.on_clicked(self._cambiar_caso)

        self.sliders_comunes = {}
        y = 0.57
        for clave, (etq, lo, hi, ini, paso) in COMUNES.items():
            ax = fig.add_axes([0.085, y, 0.11, 0.022])
            s = Slider(ax, etq, lo, hi, valinit=ini, valstep=paso)
            s.label.set_fontsize(8)
            s.on_changed(lambda v, c=clave: self.valores.__setitem__(c, v))
            self.sliders_comunes[clave] = s
            y -= 0.034
        self.y_propios = y - 0.01
        self.sliders_propios = []

        ax_btn = fig.add_axes([0.03, 0.155, 0.15, 0.05])
        self.boton = Button(ax_btn, "Simular", color="#ffd27f", hovercolor="#ffb347")
        self.boton.on_clicked(lambda _: self.simular())

        self.texto = fig.text(0.01, 0.01, "", fontsize=8, family="monospace", va="bottom")
        self.ayuda = fig.text(0.25, 0.975, "", fontsize=10, va="top")

        self.cax = fig.add_axes([0.635, 0.45, 0.01, 0.46])
        self.ax_perfil = fig.add_axes([0.735, 0.45, 0.245, 0.46])
        self.ax_curva = fig.add_axes([0.27, 0.07, 0.71, 0.26])
        ax_t = fig.add_axes([0.335, 0.385, 0.255, 0.022])
        self.slider_t = Slider(ax_t, "t", 0, N_FOTOS, valinit=0, valstep=1)
        self.slider_t.on_changed(lambda v: self.dibujar(int(v)))
        ax_play = fig.add_axes([0.255, 0.377, 0.06, 0.038])
        self.boton_play = Button(ax_play, "Animar")
        self.boton_play.on_clicked(lambda _: self._animar())
        self.timer = fig.canvas.new_timer(interval=120)
        self.timer.add_callback(self._paso_animacion)

        self._crear_sliders_propios()

    # --- controles ---------------------------------------------------------
    def _crear_sliders_propios(self):
        for s in self.sliders_propios:
            s.ax.remove()
        self.sliders_propios = []
        y = self.y_propios
        for clave, (etq, lo, hi, ini, paso) in PROPIOS[self.caso].items():
            ax = self.fig.add_axes([0.085, y, 0.11, 0.022])
            valores = self.propios[self.caso]
            s = self.Slider(ax, etq, lo, hi, valinit=valores[clave], valstep=paso, color="#d9534f")
            s.label.set_fontsize(8)
            s.on_changed(lambda v, c=clave, d=valores: d.__setitem__(c, v))
            self.sliders_propios.append(s)
            y -= 0.034

    def _animar(self):
        self.timer.stop()
        self.slider_t.set_val(0)
        self.timer.start()

    def _paso_animacion(self):
        foto = int(self.slider_t.val)
        if foto >= N_FOTOS:
            self.timer.stop()
            return
        self.slider_t.set_val(foto + 1)

    def _cambiar_caso(self, etiqueta):
        self.caso = etiqueta
        self._crear_sliders_propios()
        self.simular()

    # --- simular y dibujar ---------------------------------------------------
    def simular(self):
        self.texto.set_text("Simulando...")
        self.fig.canvas.draw_idle()
        try:
            self.fig.canvas.flush_events()
        except NotImplementedError:
            pass
        try:
            self.sim = simular(self.caso, {**self.valores, **self.propios[self.caso]})
        except SimulacionMuyLarga as error:
            self.texto.set_text(f"NO SE SIMULO:\n{error}")
            self.fig.canvas.draw_idle()
            return
        if "lim" in self.sim:
            # rango fisico del caso: asi un cambio de beta, q_n, etc. si cambia los colores
            lo, hi = map(float, self.sim["lim"])
        else:
            todos = np.concatenate([c.ravel() for c in self.sim["campos"]])
            lo, hi = float(todos.min()), float(todos.max())
        if hi - lo < 1e-6:
            lo, hi = lo - 0.5, hi + 0.5
        self.lim = (lo, hi)
        self._preparar_mapa()
        self._dibujar_curva()
        self.ayuda.set_text(f"{self.caso}:  {AYUDA[self.caso]}")
        self.slider_t.set_val(0)   # parte en t = 0 (llama a dibujar)

    def _preparar_mapa(self):
        import matplotlib.pyplot as plt
        from matplotlib.cm import ScalarMappable
        from matplotlib.colors import Normalize

        if self.ax_mapa is not None:
            self.ax_mapa.remove()
        rect = [0.25, 0.45, 0.37, 0.46]
        if self.sim["dim"] == 3:
            self.ax_mapa = self.fig.add_axes(rect, projection="3d")
        else:
            self.ax_mapa = self.fig.add_axes(rect)
        self.norm = Normalize(*self.lim)
        self.cmap = plt.get_cmap("inferno")
        self.cax.cla()
        self.fig.colorbar(ScalarMappable(self.norm, self.cmap), cax=self.cax)
        self.cax.set_title("T [C]", fontsize=9)

    def dibujar(self, foto: int):
        if self.sim is None:
            return
        sim = self.sim
        campo = sim["campos"][foto]
        t_h = sim["tiempos"][foto]
        t_s = t_h * 3600.0
        self.slider_t.valtext.set_text(f"{t_h:.1f} h")
        grid = sim["model"].grid
        x, y, z = grid.centers()
        Lx, Ly, Lz = sim["largos"]

        ax = self.ax_mapa
        ax.cla()
        if sim["dim"] == 1:
            ax.imshow(campo[:, 0, 0][None, :], extent=[0, Lx, 0, Lx / 8], cmap=self.cmap, norm=self.norm,
                      aspect="auto", interpolation="nearest")
            ax.set(xlabel="x [m]", yticks=[], title=f"Barra 1D  ({grid.nx} celdas)   t = {t_h:.1f} h")
        elif sim["dim"] == 2:
            ax.imshow(campo[:, :, 0].T, extent=[0, Lx, 0, Ly], origin="lower", cmap=self.cmap, norm=self.norm,
                      interpolation="nearest")
            ax.set(xlabel="x [m]", ylabel="y [m]", title=f"Placa 2D  ({grid.nx} x {grid.ny})   t = {t_h:.1f} h")
        else:
            xe = np.linspace(0, Lx, grid.nx + 1)
            ye = np.linspace(0, Ly, grid.ny + 1)
            ze = np.linspace(0, Lz, grid.nz + 1)
            XE, YE, ZE = np.meshgrid(xe, ye, ze, indexing="ij")
            lleno = np.ones(grid.shape, dtype=bool)
            # corte: se saca un cuarto de columna para ver el interior
            lleno[grid.nx // 2:, : grid.ny // 2, :] = False
            colores = self.cmap(self.norm(campo))
            ax.voxels(XE, YE, ZE, lleno, facecolors=colores, edgecolor=(0, 0, 0, 0.25), linewidth=0.3)
            ax.set_box_aspect((Lx, Ly, max(Lz, 0.3 * max(Lx, Ly))))
            ax.set(xlabel="x [m]", ylabel="y [m]", zlabel="z [m]",
                   title=f"Bloque 3D  ({grid.nx} x {grid.ny} x {grid.nz})   t = {t_h:.1f} h"
                         + ("" if Lz >= 0.3 * max(Lx, Ly) else "   (z exagerado)"))
            ax.view_init(elev=22, azim=-58)

        # perfil numerico vs exacto
        ap = self.ax_perfil
        ap.cla()
        eje = sim["eje_perfil"]
        sonda = sim["sondas"]["centro"]
        coord = x if eje == 0 else z
        num = _linea(campo, eje, sonda)
        exacta = sim["exacta"](t_s) if sim["exacta_es_transitoria"] else sim["exacta"](np.inf)
        ex = _linea(np.asarray(exacta), eje, sonda)
        etq_ex = "exacta" if sim["exacta_es_transitoria"] else "exacta (regimen permanente)"
        estilo_ex = "-" if sim["exacta_es_transitoria"] else "--"
        if eje == 2:
            ap.plot(ex, coord, "k" + estilo_ex, label=etq_ex)
            ap.plot(num, coord, "o", color="#d9534f", ms=5, label="solver 3D")
            ap.set(xlabel="T [C]", ylabel="z [m]  (0 = base)", xlim=self.lim)
        else:
            ap.plot(coord, ex, "k" + estilo_ex, label=etq_ex)
            ap.plot(coord, num, "o", color="#d9534f", ms=5, label="solver 3D")
            ap.set(xlabel="x [m]", ylabel="T [C]", ylim=self.lim)
        ap.set_title(f"Perfil por el centro, t = {t_h:.1f} h", fontsize=10)
        ap.grid(alpha=0.3)
        ap.legend(fontsize=8)

        # marcador de tiempo en la curva
        self.linea_t.set_xdata([t_h, t_h])

        # informacion
        model = sim["model"]
        C = model.rho_cp_flat * model.grid.cell_volume
        E0 = float(np.sum(C * sim["campos"][0].ravel()))
        E = float(np.sum(C * campo.ravel()))
        d_min = min(grid.dx, grid.dy, grid.dz)
        Fo = difusividad(CONCRETO) * sim["dt_s"] / d_min ** 2
        lineas = [
            f"celdas: {grid.nx} x {grid.ny} x {grid.nz} = {grid.n_cells}",
            f"dt = {sim['dt_s']:.0f} s   Fo(min dx) = {Fo:.3f}",
            f"calculo: {sim['segundos']:.1f} s ({N_FOTOS} tramos)",
            f"t = {t_h:.1f} h   T max = {campo.max():.2f}  T min = {campo.min():.2f} C",
        ]
        if sim["caso"] in ("Adiabatico dT/dn=0", "Fuente q0"):
            V = grid.cell_volume * grid.n_cells
            esperado = E0 + sim["q0"] * V * t_s
            lineas.append(f"energia: E - E0 = {E - E0:.4e} J (exacto {esperado - E0:.4e} J)")
        if sim["exacta_es_transitoria"]:
            lineas.append(f"error max vs exacta = {np.max(np.abs(campo - exacta)):.2e} C")
        if sim["nota"]:
            lineas.append(sim["nota"])
        if sim["tau_h"]:
            lineas.append(f"tiempo caracteristico tau = {sim['tau_h']:.1f} h  (t final sugerido ~ {3 * sim['tau_h']:.0f} h)")
        self.texto.set_text("\n".join(lineas))
        self.fig.canvas.draw_idle()

    def _dibujar_curva(self):
        sim = self.sim
        ac = self.ax_curva
        ac.cla()
        tiempos = sim["tiempos"]
        colores = ["#1f77b4", "#d9534f", "#2ca02c"]
        for (nombre, sonda), color in zip(sim["sondas"].items(), colores):
            serie = [c[sonda] for c in sim["campos"]]
            ac.plot(tiempos, serie, "-", color=color, lw=2, label=f"{nombre} (solver)")
            if sim["exacta_es_transitoria"]:
                ex = [np.asarray(sim["exacta"](t * 3600.0))[sonda] for t in tiempos]
                ac.plot(tiempos, ex, ":", color="k", lw=1)
        if sim["exacta_es_transitoria"]:
            ac.plot([], [], ":", color="k", label="exacta")
        self.linea_t = ac.axvline(tiempos[-1], color="gray", lw=1)
        ac.set(xlabel="t [h]", ylabel="T [C]", title="Curva de calor en puntos de control")
        ac.grid(alpha=0.3)
        ac.legend(fontsize=8, ncol=4, loc="best")


def main() -> int:
    ap = argparse.ArgumentParser(description="Visualizador termico interactivo")
    ap.add_argument("--prueba", metavar="CARPETA", help="sin ventana: guarda un PNG por caso en CARPETA")
    a = ap.parse_args()

    import matplotlib
    if a.prueba:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(15, 8.5))
    fig.canvas.manager.set_window_title("Visualizador termico - MCOC Grupo 5")
    vis = Visualizador(fig)

    if a.prueba:
        carpeta = Path(a.prueba)
        carpeta.mkdir(parents=True, exist_ok=True)
        for i, caso in enumerate(CASOS):
            vis.radio.set_active(i)          # cambia el caso y simula
            vis.slider_t.set_val(N_FOTOS // 4)
            nombre = carpeta / f"{i}_{caso.split()[0].lower()}_{caso.split()[-1][:2].lower()}.png"
            fig.savefig(nombre, dpi=80)
            print(f"{caso:<22} {vis.sim['segundos']:.1f} s  -> {nombre.name}")
        return 0

    vis.simular()
    plt.show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
