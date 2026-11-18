"""Curvas de hidratacion medidas, usadas como fuente prescrita por edad (guia del 18-nov, 4.1).

Cada curva es una tabla (edad, valor) de un ensayo y se usa ENTERA en cada escenario: no se
sortean puntos ni se mezclan tramos de curvas distintas.

Lo que midio el ensayo decide la conversion a calor:

- "dT_ad" : incremento adiabatico de temperatura [°C]. Con propiedades constantes,
            q = rho cp dDeltaT_ad/da  [W/m3].
- "Q_kg"  : calor acumulado por masa de cementante [J/kg] (o [J/g], se convierte).
            q = b dH/da, con b = contenido de cementante [kg/m3].
- "Q_W_m3": fuente volumetrica Q(a) [W/m3] (calor por m3 de hormigon y por segundo). Se integra
            en el tiempo (trapecios) para obtener el calor acumulado por m3.

Las dos se llevan a una elevacion adiabatica equivalente theta(a) [°C] = calor por m3 / (rho cp),
que es lo que el solver integra en cada paso: Q = rho cp [theta(a + da) - theta(a)] / dt.
Asi el calor total liberado es exactamente rho cp theta(a_final), sin error de derivacion.

- Interpolacion: lineal en theta entre puntos medidos (no se suaviza: la derivada es la
  pendiente de cada tramo).
- Monotonia: una curva acumulada no puede bajar; un descenso (ruido) se recorta y se avisa.
- Cola: despues del ultimo punto theta queda constante (no hay calor sin dato). Si el ensayo
  termino antes de estabilizarse, eso subestima el calor: se informa la pendiente final.
- Edad: a = t - t_activacion de cada celda. Sin madurez/Arrhenius: la cinetica no depende de T.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml


@dataclass
class CurvaHidratacion:
    """Curva tabulada con la misma interfaz que `HydrationModel` (theta, dtheta_dage, ...)."""

    nombre: str
    edad_h: np.ndarray
    theta_C: np.ndarray            # elevacion adiabatica equivalente [°C]
    metadatos: dict = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)

    uses_maturity = False          # fuente prescrita por edad

    def theta(self, age_h):
        a = np.asarray(age_h, dtype=float)
        return np.interp(a, self.edad_h, self.theta_C, left=0.0, right=float(self.theta_C[-1]))

    def dtheta_dage(self, age_h):
        a = np.asarray(age_h, dtype=float)
        pend = np.diff(self.theta_C) / np.diff(self.edad_h)
        idx = np.clip(np.searchsorted(self.edad_h, a, side="right") - 1, 0, pend.size - 1)
        fuera = (a < self.edad_h[0]) | (a >= self.edad_h[-1])
        return np.where(fuera, 0.0, pend[idx])

    def maturity_factor(self, temperature_C):
        return np.ones_like(np.asarray(temperature_C, dtype=float))

    def heat_rate(self, age_h, temperature_C=None, volumetric_heat_capacity: float = 2.328e6,
                  aplicar_madurez: bool = True):
        return volumetric_heat_capacity * self.dtheta_dage(age_h) / 3600.0

    @property
    def theta_final_C(self) -> float:
        return float(self.theta_C[-1])

    def pendiente_final_C_h(self) -> float:
        """Pendiente en el ultimo tramo: si no es ~0, la curva no se estabilizo dentro del ensayo."""
        return float((self.theta_C[-1] - self.theta_C[-2]) / (self.edad_h[-1] - self.edad_h[-2]))


def desde_tabla(nombre: str, edad: np.ndarray, valor: np.ndarray, tipo: str, rho_cp: float,
                unidad_edad: str = "h", unidad_valor: str | None = None,
                cementante_kg_m3: float | None = None, metadatos: dict | None = None) -> CurvaHidratacion:
    """Convierte una tabla medida en una curva theta(a) [°C] lista para el solver."""
    edad = np.asarray(edad, dtype=float)
    valor = np.asarray(valor, dtype=float)
    factor_edad = {"h": 1.0, "d": 24.0, "min": 1.0 / 60.0, "s": 1.0 / 3600.0}[unidad_edad]
    edad = edad * factor_edad
    orden = np.argsort(edad)
    edad, valor = edad[orden], valor[orden]
    avisos = []
    if tipo == "dT_ad":
        theta = valor
    elif tipo == "Q_W_m3":
        calor = np.concatenate(([0.0], np.cumsum(0.5 * (valor[1:] + valor[:-1]) * np.diff(edad) * 3600.0)))
        theta = calor / rho_cp
    elif tipo == "Q_kg":
        if cementante_kg_m3 is None:
            raise ValueError(f"{nombre}: una curva de calor por masa necesita el contenido de cementante b [kg/m3].")
        a_J_kg = {"J/kg": 1.0, "J/g": 1000.0, "kJ/kg": 1000.0}[unidad_valor or "J/kg"]
        theta = valor * a_J_kg * cementante_kg_m3 / rho_cp
    else:
        raise ValueError(f"{nombre}: tipo '{tipo}' desconocido (dT_ad o Q_kg). Una temperatura de un ensayo "
                         "no adiabatico necesita un balance del ensayo: no es calor generado.")
    if edad[0] > 0.0:
        edad, theta = np.concatenate(([0.0], edad)), np.concatenate(([0.0], theta))
    theta = theta - theta[0]
    caidas = np.diff(theta) < 0
    if np.any(caidas):
        avisos.append(f"{int(caidas.sum())} tramos decrecientes recortados (curva acumulada no puede bajar)")
        theta = np.maximum.accumulate(theta)
    curva = CurvaHidratacion(nombre, edad, theta, metadatos or {}, avisos)
    if curva.pendiente_final_C_h() > 0.01:
        curva.avisos.append(f"la curva sigue subiendo al final ({curva.pendiente_final_C_h():.3f} °C/h): "
                            "la cola constante subestima el calor")
    return curva


def cargar_curvas(carpeta: Path, rho_cp: float) -> list[CurvaHidratacion]:
    """Lee `curvas.yaml` + un CSV por curva. Carpeta vacia o sin yaml -> lista vacia.

    curvas.yaml:
        curvas:
          - nombre: M1
            archivo: M1.csv          # columnas: edad, valor
            tipo: dT_ad | Q_kg | Q_W_m3
            columna: 1                # opcional: columna de un archivo con varias curvas
            unidad_edad: h | d | min
            unidad_valor: °C | J/kg | J/g | kJ/kg
            cementante_kg_m3: 380     # solo Q_kg
            mezcla: ...               # metadatos del ensayo (se conservan)
            temperatura_ensayo_C: 20
            peso: 0.125               # opcional; si falta, pesos iguales
    """
    carpeta = Path(carpeta)
    indice = carpeta / "curvas.yaml"
    if not indice.exists():
        return []
    datos = yaml.safe_load(indice.read_text(encoding="utf-8")) or {}
    curvas = []
    for spec in datos.get("curvas", []) or []:
        ruta = carpeta / spec["archivo"]
        if "columna" in spec:
            # Archivo con varias curvas en columnas separadas por espacios (p. ej. source_terms.txt)
            tabla = np.genfromtxt(ruta, comments="#")
            edad, valor = tabla[:, 0], tabla[:, int(spec["columna"])]
            ok = np.isfinite(edad) & np.isfinite(valor)
            edad, valor = edad[ok], valor[ok]
        else:
            with open(ruta, encoding="utf-8") as h:
                filas = [f for f in csv.reader(h) if f and not f[0].strip().startswith("#")]
            try:
                float(filas[0][0])
            except ValueError:
                filas = filas[1:]              # encabezado
            edad = [float(f[0]) for f in filas]
            valor = [float(f[1]) for f in filas]
        # Propiedades asociadas a la curva (las del ensayo): se conservan juntas con ella
        rho_cp_curva = float(spec["rho"]) * float(spec["cp"]) if "rho" in spec and "cp" in spec else rho_cp
        curvas.append(desde_tabla(
            spec["nombre"], edad, valor, spec["tipo"], rho_cp_curva,
            unidad_edad=spec.get("unidad_edad", "h"), unidad_valor=spec.get("unidad_valor"),
            cementante_kg_m3=spec.get("cementante_kg_m3"), metadatos=spec,
        ))
    return curvas


def curva_provisoria_c1(rho_cp: float, horas: float = 2000.0) -> CurvaHidratacion:
    """La curva C1 de E09-E13 (45 °C, tau 30 h) tabulada, SOLO mientras no esten las curvas reales."""
    edad = np.concatenate((np.linspace(0.0, 200.0, 401), np.linspace(205.0, horas, 360)))
    return CurvaHidratacion("C1_provisoria", edad, 45.0 * (1.0 - np.exp(-edad / 30.0)),
                            {"nombre": "C1_provisoria", "tipo": "dT_ad", "peso": 1.0,
                             "fuente": "Curva provisoria del repo (no es un ensayo). Reemplazar por las 8 curvas."},
                            ["PROVISORIA: no es una curva medida"])
