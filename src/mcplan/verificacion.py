"""Bateria de verificacion del solver termico 3D (E05).

Cada caso arma un plan pequeno, lo resuelve con `build_model` + `solve` (el
mismo solver del caso real) y lo compara con una solucion exacta:

    sinusoidal 1D/2D/3D   T = T0 + A prod sin(pi x_i/L_i) exp(-alpha lambda t),
                          lambda = sum (pi/L_i)^2, bordes Dirichlet T0
    energia adiabatica    sin fuente: sum C_i T_i constante
    fuente uniforme       dT/dt = q0/(rho cp)  ->  T = T0 + q0 t/(rho cp)
    neumann (balance)     dE/dt = -q_n A       (unica cara con flujo)
    neumann (permanente)  T(x) = T_D - q_n (L - x)/k
    robin (permanente)    q = (T_D - T_inf)/(L/k + 1/h),  T(x) = T_D - q x/k

Todos los parametros son argumentos: el ayudante puede cambiarlos y volver a
correr (ver scripts/bateria_e05.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .plan import plan_from_dict
from .thermal import Model, Result, build_model, solve

# Hormigon de referencia (Ju & Lei 2019)
CONCRETO = {"k": 2.22, "rho": 2400.0, "cp": 970.0}


@dataclass
class Caso:
    """Resultado de un caso de verificacion."""

    nombre: str
    error: float
    tolerancia: float
    detalle: str = ""
    datos: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.error <= self.tolerancia)

    def linea(self) -> str:
        estado = "PASA" if self.ok else "FALLA"
        return f"[{estado}] {self.nombre:<26} error = {self.error:.3e}  (tol {self.tolerancia:.1e})  {self.detalle}"


def difusividad(mat: dict) -> float:
    return mat["k"] / (mat["rho"] * mat["cp"])


def plan_caja(L, n, mat=CONCRETO, fronteras=None, T0=20.0, T_ambiente=20.0) -> dict:
    """Plan de una caja [0,Lx]x[0,Ly]x[0,Lz] con n = (nx, ny, nz) celdas.

    Sin hidratacion (elevacion adiabatica 0). Las caras sin frontera declarada
    quedan adiabaticas.
    """
    Lx, Ly, Lz = L
    nx, ny, nz = n
    return {
        "caso": "verificacion",
        "geometria": {
            "x": [0.0, Lx], "y": [0.0, Ly], "z": [0.0, Lz],
            "dx": Lx / nx, "dy": Ly / ny, "dz": Lz / nz,
        },
        "materiales": {"M1": dict(mat)},
        "vertidas": [
            {"id": 1, "inicio_h": 0.0, "z_min": 0.0, "z_max": Lz, "material": "M1",
             "temperatura_colocacion_C": T0}
        ],
        "hidratacion": {"elevacion_adibatica_C": 0.0, "tau_h": 1.0},
        "ambiente": {"media_C": T_ambiente},
        "fronteras": fronteras or [],
        "criterios": {"core_erosion": 0},
    }


def _centros(model: Model):
    x, y, z = model.grid.centers()
    return np.meshgrid(x, y, z, indexing="ij")


def _energia(model: Model, T: np.ndarray) -> float:
    """E = sum rho cp V T [J] (referida a 0 C)."""
    return float(np.sum(model.rho_cp_flat * model.grid.cell_volume * T.ravel()))


# ---------------------------------------------------------------------------
# Soluciones sinusoidales 1D / 2D / 3D (Dirichlet)
# ---------------------------------------------------------------------------

def caso_sinusoidal(dim: int, L=(1.0, 1.0, 1.0), n: int = 20, T0: float = 20.0, A: float = 10.0,
                    t_h: float = 24.0, mat=CONCRETO, tol_rel: float = 2e-2):
    """Decaimiento del modo sinusoidal en `dim` dimensiones.

    Los ejes activos (0..dim-1) tienen n celdas y bordes Dirichlet T0; los demas
    ejes tienen una sola celda con caras adiabaticas (el problema no varia ahi).
    Devuelve (Caso, model, result, exacto). El error es max|T - T_exacta| dividido
    por la amplitud que queda en t, A exp(-alpha lambda t): asi un t largo (seno ya
    casi apagado) no hace pasar el test por tener todo cerca de T0.
    """
    L = tuple(float(v) for v in L)
    celdas = tuple(n if eje < dim else 1 for eje in range(3))
    # en un eje inactivo el espesor da lo mismo: se usa el de una celda activa
    largos = tuple(L[eje] if eje < dim else L[0] / n for eje in range(3))
    fronteras = [{"name": "dirichlet", "direccion": "ejes", "ejes": list(range(dim)),
                  "signo": "ambos", "tipo": "dirichlet", "valor_dirichlet_C": T0}]
    model = build_model(plan_from_dict(plan_caja(largos, celdas, mat, fronteras, T0)))

    X = _centros(model)
    forma = np.ones(model.grid.shape)
    lam = 0.0
    for eje in range(dim):
        forma = forma * np.sin(np.pi * X[eje] / largos[eje])
        lam += (np.pi / largos[eje]) ** 2
    inicial = T0 + A * forma

    result = solve(model, duracion_h=t_h, intervalo_salida_h=t_h, temperatura_inicial=inicial.ravel())
    t_s = result.time_h[-1] * 3600.0
    decaimiento = np.exp(-difusividad(mat) * lam * t_s)
    exacto = T0 + A * forma * decaimiento
    error = float(np.max(np.abs(result.T_final - exacto))) / (A * decaimiento)
    caso = Caso(
        nombre=f"sinusoidal {dim}D (n={n})",
        error=error,
        tolerancia=tol_rel,
        detalle=f"L={largos[:dim]}, t={t_h} h, exp(-a*lam*t)={decaimiento:.3f}, dt={result.dt_s:.0f} s",
    )
    return caso, model, result, exacto


def convergencia(dim: int, ns=(10, 20, 40), orden_min: float = 1.8, **kwargs):
    """Orden de convergencia espacial p = log2(e_n / e_2n) (dt ~ dx^2, esperado 2)."""
    errores = [caso_sinusoidal(dim, n=n, **kwargs)[0].error for n in ns]
    ordenes = [float(np.log(errores[i] / errores[i + 1]) / np.log(ns[i + 1] / ns[i]))
               for i in range(len(ns) - 1)]
    # se reporta como "error" cuanto falta para el orden minimo (0 si se cumple)
    caso = Caso(
        nombre=f"convergencia {dim}D",
        error=max(0.0, orden_min - ordenes[-1]),
        tolerancia=0.0,
        detalle=f"n={list(ns)} errores={[f'{e:.2e}' for e in errores]} orden={[round(p, 2) for p in ordenes]}",
        datos={"ns": list(ns), "errores": errores, "ordenes": ordenes},
    )
    return caso


# ---------------------------------------------------------------------------
# Conservacion de energia y fuente volumetrica
# ---------------------------------------------------------------------------

def caso_energia_adiabatica(L=(1.0, 0.8, 0.6), n=(10, 8, 6), t_h: float = 48.0, mat=CONCRETO,
                            q0: float = 0.0, semilla: int = 0, tol_rel: float = 1e-10):
    """Campo inicial aleatorio en una caja adiabatica.

    Sin fuente la energia total no cambia; con fuente q0 debe crecer exactamente
    q0 * V_total * t. Error = |E_final - E_esperada| / E_inicial.
    """
    model = build_model(plan_from_dict(plan_caja(L, n, mat)))
    rng = np.random.default_rng(semilla)
    inicial = 20.0 + 30.0 * rng.random(model.grid.n_cells)
    result = solve(model, duracion_h=t_h, intervalo_salida_h=t_h / 12,
                   temperatura_inicial=inicial, fuente_W_m3=q0)
    t_s = result.time_h[-1] * 3600.0
    E0 = _energia(model, inicial)
    E1 = _energia(model, result.T_final)
    V_total = model.grid.cell_volume * model.grid.n_cells
    esperado = E0 + q0 * V_total * t_s
    caso = Caso(
        nombre="energia adiabatica" + (" + fuente" if q0 else ""),
        error=abs(E1 - esperado) / abs(E0),
        tolerancia=tol_rel,
        detalle=f"E0={E0:.4e} J, E1={E1:.4e} J, q0*V*t={q0 * V_total * t_s:.3e} J, "
                f"rango T: {inicial.max() - inicial.min():.1f} -> {np.ptp(result.T_final):.2f} C",
    )
    return caso, model, result


def caso_fuente_uniforme(L=(1.0, 1.0, 1.0), n=(5, 5, 5), q0: float = 1000.0, T0: float = 20.0,
                         t_h: float = 24.0, mat=CONCRETO, tol: float = 1e-8):
    """Caja adiabatica a T0 con fuente q0 [W/m3]: T(t) = T0 + q0 t / (rho cp) en todas las celdas."""
    model = build_model(plan_from_dict(plan_caja(L, n, mat, T0=T0)))
    result = solve(model, duracion_h=t_h, intervalo_salida_h=t_h / 24, fuente_W_m3=q0)
    rho_cp = mat["rho"] * mat["cp"]
    exacto_t = T0 + q0 * result.time_h * 3600.0 / rho_cp
    error = max(float(np.max(np.abs(result.T_mean - exacto_t))),
                float(np.max(np.abs(result.T_final - exacto_t[-1]))))
    caso = Caso(
        nombre="fuente uniforme",
        error=error,
        tolerancia=tol,
        detalle=f"q0={q0} W/m3, dT/dt={q0 / rho_cp * 3600:.3f} C/h, T({t_h} h)={result.T_final.mean():.3f} C "
                f"(exacta {exacto_t[-1]:.3f})",
        datos={"exacto_t": exacto_t},
    )
    return caso, model, result


# ---------------------------------------------------------------------------
# Condiciones de borde: Neumann y Robin
# ---------------------------------------------------------------------------

def _barra(L: float, n: int):
    """Barra 1D en x: n celdas, seccion de una celda (caras y, z adiabaticas)."""
    dx = L / n
    return (L, dx, dx), (n, 1, 1)


def caso_neumann_balance(L: float = 1.0, n: int = 20, q_n: float = -100.0, T0: float = 20.0,
                         t_h: float = 24.0, mat=CONCRETO, tol_rel: float = 1e-10):
    """Flujo q_n [W/m2] en la cara x=0 (n hacia afuera; q_n<0 entra calor), resto adiabatico.

    Balance global: E(t) - E0 = -q_n * A * t.
    """
    largos, celdas = _barra(L, n)
    fronteras = [{"name": "flujo", "direccion": "ejes", "ejes": [0], "signo": "-",
                  "tipo": "neumann", "flujo_W_m2": q_n}]
    model = build_model(plan_from_dict(plan_caja(largos, celdas, mat, fronteras, T0)))
    result = solve(model, duracion_h=t_h, intervalo_salida_h=t_h)
    t_s = result.time_h[-1] * 3600.0
    A = model.grid.face_area(0)
    E0 = _energia(model, np.full(model.grid.n_cells, T0))
    dE = _energia(model, result.T_final) - E0
    esperado = -q_n * A * t_s
    caso = Caso(
        nombre="neumann balance",
        error=abs(dE - esperado) / abs(esperado),
        tolerancia=tol_rel,
        detalle=f"q_n={q_n} W/m2: dE={dE:.4e} J vs -q_n*A*t={esperado:.4e} J",
    )
    return caso, model, result


def _t_permanente(L: float, mat) -> float:
    """Tiempo [h] para llegar a regimen: 8 L^2/alpha (el modo lento decae ~e^-20)."""
    return 8.0 * L ** 2 / difusividad(mat) / 3600.0


def caso_neumann_permanente(L: float = 1.0, n: int = 20, q_n: float = -50.0, T_D: float = 20.0,
                            mat=CONCRETO, tol: float = 1e-3):
    """Flujo q_n en x=0 y Dirichlet T_D en x=L. Permanente: T(x) = T_D - q_n (L - x)/k."""
    largos, celdas = _barra(L, n)
    fronteras = [
        {"name": "flujo", "direccion": "ejes", "ejes": [0], "signo": "-", "tipo": "neumann", "flujo_W_m2": q_n},
        {"name": "fijo", "direccion": "ejes", "ejes": [0], "signo": "+", "tipo": "dirichlet", "valor_dirichlet_C": T_D},
    ]
    model = build_model(plan_from_dict(plan_caja(largos, celdas, mat, fronteras, T_D)))
    t_h = _t_permanente(L, mat)
    result = solve(model, duracion_h=t_h, intervalo_salida_h=t_h)
    x = model.grid.centers()[0]
    exacto = T_D - q_n * (L - x) / mat["k"]
    numerico = result.T_final[:, 0, 0]
    caso = Caso(
        nombre="neumann permanente",
        error=float(np.max(np.abs(numerico - exacto))),
        tolerancia=tol,
        detalle=f"q_n={q_n} W/m2, T 1a celda={numerico[0]:.4f} C (exacta {exacto[0]:.4f}), "
                f"T(x=0)={T_D - q_n * L / mat['k']:.3f} C",
        datos={"x": x, "numerico": numerico, "exacto": exacto},
    )
    return caso, model, result


def caso_robin_permanente(L: float = 1.0, n: int = 20, h: float = 10.0, T_D: float = 60.0,
                          T_inf: float = 20.0, mat=CONCRETO, tol: float = 1e-3):
    """Dirichlet T_D en x=0 y conveccion (h, T_inf) en x=L.

    Permanente: resistencias en serie, q = (T_D - T_inf)/(L/k + 1/h), T(x) = T_D - q x/k.
    """
    largos, celdas = _barra(L, n)
    fronteras = [
        {"name": "fijo", "direccion": "ejes", "ejes": [0], "signo": "-", "tipo": "dirichlet", "valor_dirichlet_C": T_D},
        {"name": "aire", "direccion": "ejes", "ejes": [0], "signo": "+", "tipo": "convectiva", "h": h},
    ]
    model = build_model(plan_from_dict(plan_caja(largos, celdas, mat, fronteras, T_D, T_ambiente=T_inf)))
    t_h = _t_permanente(L, mat)
    result = solve(model, duracion_h=t_h, intervalo_salida_h=t_h)
    x = model.grid.centers()[0]
    q = (T_D - T_inf) / (L / mat["k"] + 1.0 / h)
    exacto = T_D - q * x / mat["k"]
    numerico = result.T_final[:, 0, 0]
    caso = Caso(
        nombre="robin permanente",
        error=float(np.max(np.abs(numerico - exacto))),
        tolerancia=tol,
        detalle=f"h={h} W/m2K, q={q:.2f} W/m2, T superficie={T_D - q * L / mat['k']:.3f} C, Bi=hL/k={h * L / mat['k']:.2f}",
        datos={"x": x, "numerico": numerico, "exacto": exacto},
    )
    return caso, model, result


def caso_robin_transitorio(L: float = 0.02, n: int = 4, h: float = 5.0, T0: float = 40.0,
                           T_inf: float = 20.0, mat=CONCRETO, tol: float = 2e-2):
    """Placa delgada (Bi << 1) con conveccion en ambas caras: capacidad agrupada.

    T(t) = T_inf + (T0 - T_inf) exp(-t/tau), tau = rho cp L / (2 h).
    El error es relativo a (T0 - T_inf); con Bi pequeno debe ser pequeno.
    """
    largos, celdas = _barra(L, n)
    fronteras = [{"name": "aire", "direccion": "ejes", "ejes": [0], "signo": "ambos", "tipo": "convectiva", "h": h}]
    model = build_model(plan_from_dict(plan_caja(largos, celdas, mat, fronteras, T0, T_ambiente=T_inf)))
    tau_s = mat["rho"] * mat["cp"] * L / (2.0 * h)
    t_h = tau_s / 3600.0
    result = solve(model, duracion_h=t_h, intervalo_salida_h=t_h / 20)
    exacto_t = T_inf + (T0 - T_inf) * np.exp(-result.time_h * 3600.0 / tau_s)
    caso = Caso(
        nombre="robin capacidad agrupada",
        error=float(np.max(np.abs(result.T_mean - exacto_t))) / abs(T0 - T_inf),
        tolerancia=tol,
        detalle=f"Bi=h(L/2)/k={h * L / 2 / mat['k']:.3f}, tau={t_h:.2f} h",
        datos={"exacto_t": exacto_t},
    )
    return caso, model, result


def bateria(mat=CONCRETO) -> list[Caso]:
    """Corre todos los casos con sus parametros por defecto."""
    return [
        caso_sinusoidal(1, mat=mat)[0],
        caso_sinusoidal(2, mat=mat)[0],
        caso_sinusoidal(3, mat=mat)[0],
        convergencia(1, mat=mat),
        convergencia(2, mat=mat),
        convergencia(3, ns=(8, 16, 32), mat=mat),
        caso_energia_adiabatica(mat=mat)[0],
        caso_energia_adiabatica(q0=1000.0, mat=mat)[0],
        caso_fuente_uniforme(mat=mat)[0],
        caso_neumann_balance(mat=mat)[0],
        caso_neumann_permanente(mat=mat)[0],
        caso_robin_permanente(mat=mat)[0],
        caso_robin_transitorio(mat=mat)[0],
    ]
