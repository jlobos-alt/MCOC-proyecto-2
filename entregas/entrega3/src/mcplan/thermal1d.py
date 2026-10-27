"""
Solver térmico 1D explícito (FTCS) escrito como balance de energía por celda.

Ecuación:   rho*cp * dT/dt = d/dx( k dT/dx ) + Q(t)        [W/m^3]

Discretización (volúmenes de control centrados en nodos, grilla uniforme):

    C_i dT_i/dt = sum_j G_ij (T_j - T_i) + Q_i V_i + Q_borde,i

    C_i  = rho*cp*V_i              capacidad térmica de la celda   [J/K]
    G_ij = k*A/dx                  conductancia entre nodos        [W/K]
    V_i  = A*dx  (interior),  A*dx/2 (nodos de borde: media celda)

Por unidad de área (A = 1 m^2).  Euler explícito en el tiempo:

    T_i^{n+1} = T_i^n + dt/C_i * [ sum_j G_ij (T_j^n - T_i^n) + Q_i V_i + Q_borde,i ]

Condiciones de borde (n = normal exterior):
    Dirichlet : T = T_b
    Neumann   : -k dT/dn = q_n       (q_n > 0 sale calor; q_n = 0 adiabático)
    Robin     : -k dT/dn = h (T - T_inf)   (convección)

Estabilidad: para cada celda  dt <= C_i / (sum_j G_ij + G_borde,i).
En el interior esto equivale a  Fo = alpha*dt/dx^2 <= 1/2.

El solver NO depende de Blender/Bonsai: recibe números (geometría, propiedades,
condiciones) y devuelve números.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Union

import numpy as np

Scalar = Union[float, Callable[[float], float]]


def _val(v: Scalar, t: float) -> float:
    """Permite que un parámetro sea constante o función del tiempo t [s]."""
    return float(v(t)) if callable(v) else float(v)


@dataclass(frozen=True)
class Material:
    k: float      # conductividad térmica            [W/(m K)]
    rho: float    # densidad                         [kg/m^3]
    cp: float     # calor específico                 [J/(kg K)]

    @property
    def alpha(self) -> float:
        """Difusividad térmica alpha = k/(rho cp) [m^2/s]."""
        return self.k / (self.rho * self.cp)


@dataclass(frozen=True)
class BC:
    """Condición de borde. Usar los constructores BC.dirichlet / neumann / robin."""
    kind: str
    T: Scalar = 0.0       # Dirichlet: temperatura impuesta [°C]
    q: Scalar = 0.0       # Neumann: flujo saliente q_n [W/m^2]
    h: float = 0.0        # Robin: coef. de convección [W/(m^2 K)]
    T_inf: Scalar = 0.0   # Robin: temperatura del ambiente [°C]

    @staticmethod
    def dirichlet(T: Scalar) -> "BC":
        return BC("dirichlet", T=T)

    @staticmethod
    def neumann(q: Scalar = 0.0) -> "BC":
        return BC("neumann", q=q)

    @staticmethod
    def adiabatic() -> "BC":
        return BC("neumann", q=0.0)

    @staticmethod
    def robin(h: float, T_inf: Scalar) -> "BC":
        if h < 0:
            raise ValueError("h debe ser >= 0")
        return BC("robin", h=h, T_inf=T_inf)

    def __post_init__(self):
        if self.kind not in ("dirichlet", "neumann", "robin"):
            raise ValueError(f"Tipo de borde desconocido: {self.kind}")


@dataclass
class Result1D:
    x: np.ndarray          # posiciones nodales [m]
    t: np.ndarray          # instantes guardados [s]
    T: np.ndarray          # T[n_guardado, i]   [°C]
    dt: float
    fo: float              # número de Fourier interior alpha dt/dx^2
    dt_max: float
    info: dict = field(default_factory=dict)

    @property
    def T_final(self) -> np.ndarray:
        return self.T[-1]


def cell_volumes(nx: int, dx: float) -> np.ndarray:
    """Longitud (volumen por m^2) de cada volumen de control nodal."""
    V = np.full(nx, dx)
    V[0] = V[-1] = dx / 2.0
    return V


def stable_dt_1d(mat: Material, dx: float, left: BC, right: BC) -> float:
    """Paso de tiempo máximo estable: min_i C_i / (sum G_ij + G_borde,i)."""
    G = mat.k / dx
    C_int = mat.rho * mat.cp * dx
    dt = C_int / (2.0 * G)                      # = dx^2/(2 alpha)
    for bc in (left, right):
        if bc.kind == "dirichlet":
            continue                            # nodo impuesto: no evoluciona
        C_b = mat.rho * mat.cp * dx / 2.0
        G_b = G + (bc.h if bc.kind == "robin" else 0.0)
        dt = min(dt, C_b / G_b)
    return dt


def solve_1d(
    L: float,
    nx: int,
    mat: Material,
    T0: Union[float, np.ndarray, Callable[[np.ndarray], np.ndarray]],
    t_end: float,
    left: BC,
    right: BC,
    Q: Scalar = 0.0,
    dt: Optional[float] = None,
    safety: float = 0.9,
    n_save: int = 50,
    allow_unstable: bool = False,
) -> Result1D:
    """Integra la ecuación del calor 1D con FTCS hasta t_end.

    T0 : condición inicial (escalar, arreglo de largo nx o función T0(x)).
    Q  : fuente volumétrica [W/m^3], constante o Q(t) (p.ej. calor de hidratación).
    dt : paso de tiempo; si es None se usa safety*dt_max.
    """
    if nx < 3:
        raise ValueError("nx debe ser >= 3")
    x = np.linspace(0.0, L, nx)
    dx = x[1] - x[0]

    dt_max = stable_dt_1d(mat, dx, left, right)
    if dt is None:
        dt = safety * dt_max
    if dt > dt_max * (1 + 1e-12) and not allow_unstable:
        raise ValueError(
            f"dt={dt:.4g} s excede el límite de estabilidad dt_max={dt_max:.4g} s "
            f"(Fo={mat.alpha*dt/dx**2:.3f} > 0.5 en el interior o borde Robin)."
        )
    nsteps = max(1, int(np.ceil(t_end / dt - 1e-12)))
    dt = t_end / nsteps                        # llegar exactamente a t_end

    # --- condición inicial -------------------------------------------------
    if callable(T0):
        T = np.asarray(T0(x), dtype=float).copy()
    else:
        T = np.broadcast_to(np.asarray(T0, dtype=float), (nx,)).copy()

    V = cell_volumes(nx, dx)
    C = mat.rho * mat.cp * V                   # [J/(K m^2)]
    G = mat.k / dx                             # [W/(K m^2)]

    def apply_dirichlet(Tarr, t):
        if left.kind == "dirichlet":
            Tarr[0] = _val(left.T, t)
        if right.kind == "dirichlet":
            Tarr[-1] = _val(right.T, t)

    apply_dirichlet(T, 0.0)

    save_steps = set(np.rint(np.linspace(0, nsteps, min(n_save, nsteps + 1))).astype(int))
    t_saved, T_saved = [0.0], [T.copy()]

    flux = np.empty(nx)
    for n in range(nsteps):
        t = n * dt
        # Conducción: suma de G_ij (T_j - T_i)
        flux[:] = 0.0
        dT = G * (T[1:] - T[:-1])              # calor que fluye de i+1 hacia i
        flux[:-1] += dT
        flux[1:] -= dT
        # Fuente volumétrica
        flux += _val(Q, t) * V
        # Bordes (calor que ENTRA a la celda de borde)
        for idx, bc in ((0, left), (-1, right)):
            if bc.kind == "neumann":
                flux[idx] -= _val(bc.q, t)
            elif bc.kind == "robin":
                flux[idx] -= bc.h * (T[idx] - _val(bc.T_inf, t))
        T = T + dt * flux / C
        apply_dirichlet(T, t + dt)

        if (n + 1) in save_steps:
            t_saved.append((n + 1) * dt)
            T_saved.append(T.copy())

    return Result1D(
        x=x, t=np.array(t_saved), T=np.array(T_saved), dt=dt,
        fo=mat.alpha * dt / dx**2, dt_max=dt_max,
        info={"nsteps": nsteps, "dx": dx},
    )


def energy(res_T: np.ndarray, mat: Material, dx: float) -> float:
    """Energía interna relativa por m^2:  sum_i C_i T_i   [J/m^2]."""
    V = cell_volumes(res_T.size, dx)
    return float(np.sum(mat.rho * mat.cp * V * res_T))
