"""Modelo probabilistico del caso (E13): variables inciertas, estados limite y estimadores.

Cada variable declara su naturaleza:

- aleatoria (aleatoric): variabilidad real que no se reduce con mas estudio
  (lote de hormigon, clima del dia, hora en que llega el camion);
- epistemica (epistemic): falta de conocimiento que si se reduce midiendo o
  calibrando (curva de hidratacion, temperatura del suelo del sitio).

Estados limite (g <= 0 es falla):

    g_T  = 70 - T_max
    g_dT = 20 - dT_max
    g_sistema = min(g_T, g_dT)      (sistema en serie: falla si falla cualquiera)

Muestreo reproducible y particionable: la muestra i usa el generador
default_rng([semilla, i]). Su valor no depende de cuantas muestras se corran ni
en que orden, asi que el mismo conjunto se puede repartir en un arreglo de Slurm.

Dependencias: copula gaussiana. Se generan normales estandar correlacionadas
(Cholesky de la matriz de correlacion) y cada una se lleva a su distribucion
marginal por la inversa de su CDF.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np

_N01 = NormalDist()

ALEATORIA = "aleatoria"
EPISTEMICA = "epistemica"


@dataclass(frozen=True)
class VariableIncierta:
    """Una entrada incierta del modelo y como se muestrea."""

    nombre: str
    naturaleza: str            # ALEATORIA o EPISTEMICA
    unidad: str
    nominal: float             # valor del caso determinista (E12)
    distribucion: str          # "normal_trunc", "uniforme", "lognormal"
    a: float                   # normal: media; uniforme: minimo; lognormal: mediana
    b: float                   # normal: desviacion; uniforme: maximo; lognormal: sigma_ln
    minimo: float = -math.inf
    maximo: float = math.inf
    descripcion: str = ""
    fuente: str = ""

    def desde_normal(self, z: float) -> float:
        """Lleva una normal estandar z a la distribucion de la variable (inversa de la CDF)."""
        u = _N01.cdf(z)
        u = min(max(u, 1e-12), 1.0 - 1e-12)
        if self.distribucion == "uniforme":
            return self.a + u * (self.b - self.a)
        if self.distribucion == "lognormal":
            return self.a * math.exp(self.b * _N01.inv_cdf(u))
        if self.distribucion == "normal_trunc":
            dist = NormalDist(self.a, self.b)
            lo = dist.cdf(self.minimo) if math.isfinite(self.minimo) else 0.0
            hi = dist.cdf(self.maximo) if math.isfinite(self.maximo) else 1.0
            return dist.inv_cdf(lo + u * (hi - lo))
        raise ValueError(f"Distribucion desconocida: {self.distribucion}")

    def texto_distribucion(self) -> str:
        if self.distribucion == "uniforme":
            return f"U[{self.a:g}; {self.b:g}]"
        if self.distribucion == "lognormal":
            return f"LogN(mediana {self.a:g}; σ_ln {self.b:g})"
        rango = f" en [{self.minimo:g}; {self.maximo:g}]" if math.isfinite(self.minimo) else ""
        return f"N({self.a:g}; {self.b:g}){rango}"


# ---------------------------------------------------------------------------
# Tabla preliminar de variables (E13). Los valores son una primera propuesta
# defendible; las fuentes indican de donde salen y que falta para afinarlos.
# ---------------------------------------------------------------------------

VARIABLES: list[VariableIncierta] = [
    # --- Clima (incertidumbre meteorologica) ---
    VariableIncierta(
        "dT_aire", ALEATORIA, "°C", 0.0, "normal_trunc", 0.0, 2.0, -6.0, 6.0,
        "Desfase de la temperatura del aire respecto de la serie de clima, todo el periodo",
        "Variabilidad interanual de fines de noviembre (ERA5, Open-Meteo archive); "
        "el forecast a >10 dias no supera a la climatologia. A recalcular con 2015-2025.",
    ),
    VariableIncierta(
        "f_viento", ALEATORIA, "-", 1.0, "lognormal", 1.0, 0.25,
        "Factor sobre la velocidad del viento (entra en h = 5,7 + 3,8 v)",
        "Error tipico del viento modelado a 10 m y su variabilidad; lognormal porque v >= 0.",
    ),
    VariableIncierta(
        "f_solar", ALEATORIA, "-", 1.0, "uniforme", 0.75, 1.10,
        descripcion="Factor sobre la radiacion de onda corta (nubosidad del periodo)",
        fuente="Dispersion de la radiacion diaria de fines de noviembre en ERA5; acotada por cielo despejado.",
    ),
    # --- Ejecucion ---
    VariableIncierta(
        "dT_colocacion", ALEATORIA, "°C", 0.0, "normal_trunc", 0.0, 1.5, -5.0, 5.0,
        "Desfase comun de la temperatura de colocacion de todas las vertidas",
        "Control de temperatura en planta (especificacion ICH 2019) y temperatura del dia.",
    ),
    VariableIncierta(
        "ruido_colocacion", ALEATORIA, "°C", 0.0, "normal_trunc", 0.0, 0.7, -2.5, 2.5,
        "Diferencia de temperatura de cada camion respecto del desfase comun (una por vertida)",
        "Variacion entre lotes de una misma jornada.",
    ),
    VariableIncierta(
        "retraso_vertida_h", ALEATORIA, "h", 0.0, "uniforme", 0.0, 3.0,
        descripcion="Atraso de cada vertida (2 a 5) respecto del intervalo planificado de 6 h",
        fuente="Logistica de despacho y bombeo; solo atrasos, nunca adelantos.",
    ),
    VariableIncierta(
        "retiro_moldaje_h", ALEATORIA, "h", 72.0, "uniforme", 60.0, 84.0,
        descripcion="Hora de retiro del moldaje desde cada vertida (plan: 72 h)",
        fuente="Turno de la cuadrilla; ±12 h alrededor del plan.",
    ),
    # --- Materiales ---
    VariableIncierta(
        "f_k", ALEATORIA, "-", 1.0, "normal_trunc", 1.0, 0.08, 0.8, 1.2,
        "Factor sobre la conductividad del hormigon (k = 2,22 W/(m·K))",
        "Ju & Lei (2019) y rangos de ACI 207.2R segun arido y humedad.",
    ),
    VariableIncierta(
        "f_cp", ALEATORIA, "-", 1.0, "normal_trunc", 1.0, 0.05, 0.85, 1.15,
        "Factor sobre el calor especifico (cp = 970 J/(kg·K))",
        "Ju & Lei (2019); cp depende de la humedad del hormigon joven.",
    ),
    VariableIncierta(
        "f_rho", ALEATORIA, "-", 1.0, "normal_trunc", 1.0, 0.02, 0.95, 1.05,
        "Factor sobre la densidad (2400 kg/m³)",
        "Control de densidad en obra; la densidad varia poco.",
    ),
    VariableIncierta(
        "f_k_moldaje", ALEATORIA, "-", 1.0, "uniforme", 0.8, 1.25,
        descripcion="Factor sobre la conductividad del moldaje de madera (k = 0,12 W/(m·K))",
        fuente="Humedad de la madera y tipo de terciado.",
    ),
    # --- Modelo de hidratacion y suelo (epistemicas) ---
    VariableIncierta(
        "theta_inf_C", EPISTEMICA, "°C", 45.0, "normal_trunc", 45.0, 4.0, 35.0, 55.0,
        "Elevacion adiabatica final de la curva C1",
        "Proporcional al contenido de cemento (±10 %); sin ensayo adiabatico del hormigon del proyecto.",
    ),
    VariableIncierta(
        "tau_h", EPISTEMICA, "h", 30.0, "uniforme", 20.0, 40.0,
        descripcion="Constante de tiempo de la curva C1",
        fuente="Rango de cementos Portland; se fija al calibrar contra Ju & Lei o un ensayo.",
    ),
    VariableIncierta(
        "Ea_R_K", EPISTEMICA, "K", 4000.0, "uniforme", 3500.0, 5400.0,
        descripcion="Energia de activacion / R (madurez de Arrhenius)",
        fuente="Ea = 29-45 kJ/mol: Freiesleben Hansen y Pedersen (1977), ASTM C1074.",
    ),
    VariableIncierta(
        "T_suelo_C", EPISTEMICA, "°C", 14.5, "normal_trunc", 14.5, 1.0, 11.0, 18.0,
        "Temperatura media anual del suelo a 1 m",
        "No hay medicion en el sitio: se estima desde la media anual del aire.",
    ),
]

POR_NOMBRE = {v.nombre: v for v in VARIABLES}

# Variables que se repiten por vertida: (nombre, cuantas)
REPETICIONES = {"ruido_colocacion": 5, "retraso_vertida_h": 4}

# Dependencias (copula gaussiana): dia mas calido -> mas sol y hormigon mas tibio.
CORRELACIONES: dict[tuple[str, str], float] = {
    ("dT_aire", "f_solar"): 0.5,
    ("dT_aire", "dT_colocacion"): 0.6,
    ("f_solar", "dT_colocacion"): 0.3,
    ("f_k", "f_rho"): 0.3,       # aridos mas densos conducen mas
}


def _matriz_correlacion(nombres: list[str]) -> np.ndarray:
    idx = {n: i for i, n in enumerate(nombres)}
    R = np.eye(len(nombres))
    for (a, b), rho in CORRELACIONES.items():
        if a in idx and b in idx:
            R[idx[a], idx[b]] = R[idx[b], idx[a]] = rho
    return R


_NOMBRES = [v.nombre for v in VARIABLES]
_CHOL = np.linalg.cholesky(_matriz_correlacion(_NOMBRES))


def muestra_nominal() -> dict:
    """La muestra del caso determinista E12 (todas las variables en su nominal)."""
    m = {v.nombre: v.nominal for v in VARIABLES if v.nombre not in REPETICIONES}
    for nombre, n in REPETICIONES.items():
        m[nombre] = [POR_NOMBRE[nombre].nominal] * n
    return m


def muestrear(indice: int, semilla: int, epistemicas: bool = True) -> dict:
    """Muestra `indice` del conjunto definido por `semilla`.

    Con `epistemicas=False` las variables epistemicas quedan en su nominal: el
    resultado es la variabilidad aleatoria condicionada al modelo de E12.
    """
    rng = np.random.default_rng([int(semilla), int(indice)])
    z = _CHOL @ rng.standard_normal(len(VARIABLES))
    m = {}
    for v, zi in zip(VARIABLES, z):
        if v.nombre in REPETICIONES:
            continue
        if v.naturaleza == EPISTEMICA and not epistemicas:
            m[v.nombre] = v.nominal
        else:
            m[v.nombre] = v.desde_normal(float(zi))
    for nombre, n in REPETICIONES.items():
        v = POR_NOMBRE[nombre]
        m[nombre] = [v.desde_normal(float(x)) for x in rng.standard_normal(n)]
    return m


# ---------------------------------------------------------------------------
# Estados limite
# ---------------------------------------------------------------------------


def estados_limite(T_max: np.ndarray, dT_max: np.ndarray, lim_T: float = 70.0, lim_dT: float = 20.0) -> dict:
    """g <= 0 es falla. El sistema falla si falla cualquiera de los dos criterios."""
    g_T = lim_T - np.asarray(T_max, dtype=float)
    g_dT = lim_dT - np.asarray(dT_max, dtype=float)
    return {"g_T": g_T, "g_dT": g_dT, "g_sistema": np.minimum(g_T, g_dT)}


# ---------------------------------------------------------------------------
# Estimador Monte Carlo y su incertidumbre
# ---------------------------------------------------------------------------


def wilson(fallas: int, n: int, confianza: float = 0.95) -> tuple[float, float]:
    """Intervalo de Wilson para una probabilidad binomial (sirve aun con 0 o n fallas)."""
    if n <= 0:
        return (math.nan, math.nan)
    z = _N01.inv_cdf(0.5 + confianza / 2.0)
    p = fallas / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    medio = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centro - medio), min(1.0, centro + medio))


def cota_cero_fallas(n: int, confianza: float = 0.95) -> float:
    """Cota superior exacta de p si no se observo ninguna falla en n muestras.

    P(0 fallas | p) = (1 - p)^n = 1 - confianza  ->  p = 1 - (1 - confianza)^(1/n) ≈ 3/n al 95 %.
    """
    return 1.0 - (1.0 - confianza) ** (1.0 / n)


def n_requerido(p: float, cov: float = 0.1) -> float:
    """Muestras necesarias para estimar p con coeficiente de variacion `cov`."""
    if p <= 0.0:
        return math.inf
    return (1.0 - p) / (p * cov * cov)


def estimar(g: np.ndarray, confianza: float = 0.95) -> dict:
    """Probabilidad de falla P(g <= 0), su error y lo que se puede afirmar."""
    g = np.asarray(g, dtype=float)
    n = int(g.size)
    fallas = int(np.count_nonzero(g <= 0.0))
    p = fallas / n
    error = math.sqrt(p * (1.0 - p) / n)
    lo, hi = wilson(fallas, n, confianza)
    mu, sigma = float(np.mean(g)), float(np.std(g, ddof=1))
    salida = {
        "n": n,
        "fallas": fallas,
        "p_hat": p,
        "error_estandar": error,
        "cov": (error / p) if p > 0 else math.inf,
        f"IC{int(confianza * 100)}_wilson": [lo, hi],
        "media_g": mu,
        "desv_g": sigma,
        # Referencia con supuesto normal de g; no es una demostracion de p pequena.
        "beta_normal": mu / sigma if sigma > 0 else math.inf,
        "p_normal": _N01.cdf(-mu / sigma) if sigma > 0 else float(mu <= 0),
    }
    if fallas == 0:
        salida["cota_superior_cero_fallas"] = cota_cero_fallas(n, confianza)
    if 0 < p < 1:
        salida["n_para_cov_10pct"] = n_requerido(p, 0.10)
    return salida


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Correlacion de rangos: mide si y crece o decrece con x, aunque no sea lineal."""
    rx = np.argsort(np.argsort(np.asarray(x, dtype=float)))
    ry = np.argsort(np.argsort(np.asarray(y, dtype=float)))
    if np.std(rx) == 0 or np.std(ry) == 0:
        return 0.0
    return float(np.corrcoef(rx, ry)[0, 1])
