# E07 — Diseño del modelo de hidratación

Código: `src/mcplan/hydration.py` (la curva) y `_accumulate_sources` en `src/mcplan/thermal.py`
(cómo entra al solver). Parámetros: `datos/fundacion_ifc.yaml`.

**Estado: parámetros provisorios.** La estructura del modelo está implementada y probada; los
valores de θ∞, τ y Ea/R todavía no están calibrados. Calibrarlos es trabajo de E09.

## 1. Idea

No modelamos la química del cemento. Partimos de lo que se puede medir: cuánto subiría la
temperatura de un hormigón sin ninguna pérdida de calor. Esa es la **curva adiabática θ(t)**, y de
ella se deduce cuánto calor genera cada celda en cada instante.

## 2. Ecuaciones

Curva adiabática (una exponencial; el código admite dos):

    θ(edad) = θ∞ · (1 − exp(−edad / τ))

Calor volumétrico, de un balance de energía en una celda sin pérdidas (ρ·cp·dT/dt = Q̇h, con T = T₀ + θ):

    Q̇h = ρ · cp · dθ/dt     [W/m³]

Unidades: J/(m³·K) · K/s = W/m³. Es una fuente por **volumen**. La convección, en cambio, es un
flujo por **área** (W/m²) y va en el borde.

Efecto de la temperatura (madurez, Arrhenius). El hormigón caliente reacciona más rápido, lo que se
representa como una edad que corre a otra velocidad:

    m(T) = exp(−(Ea/R) · (1/T − 1/T_ref))     T en kelvin, T_ref = 293,15 K
    edad_eq(t) = ∫ m(T(τ)) dτ
    Q̇h = ρ · cp · dθ/d(edad_eq) · m(T)

El factor m(T) final viene de la regla de la cadena. Gracias a él, el calor total sigue siendo
ρ·cp·θ∞: **la temperatura cambia cuándo se libera el calor, no cuánto**.

## 3. Valores provisorios

| Parámetro | Valor | Origen |
|---|---|---|
| θ∞ | 45 °C | Provisorio, por calibrar |
| τ | 30 h | Provisorio, por calibrar |
| Ea/R | 4000 K (Ea ≈ 33 kJ/mol) | Provisorio, por confirmar con una fuente |
| ρ, cp | 2400 kg/m³, 970 J/(kg·K) | Ju & Lei (2019) |

Con estos valores: Q̇h(0) = 970 W/m³ sin madurez, y la energía total es 104,8 MJ/m³.

| T [°C] | 5 | 10 | 20 | 30 | 40 | 50 | 60 |
|---|---|---|---|---|---|---|---|
| m(T) | 0,48 | 0,62 | 1,00 | 1,57 | 2,39 | 3,55 | 5,15 |

Reproducir: `python scripts/curva_hidratacion.py` (figura en `results/e07/hidratacion.png`).

## 4. Cómo entra al solver

Cada celda guarda su propia edad, que parte en 0 cuando se activa su vertida. En cada paso:

    Δθ = θ(edad_fin) − θ(edad_ini)
    edad_fin = edad_ini + m(T_inicio_del_paso) · Δt
    Q̇h · V = ρ · cp · V · Δθ / Δt

Se integra la curva dentro del paso en lugar de evaluar dθ/dt al inicio. **Motivo medido:** la
estabilidad de la difusión permite pasos de hasta unas 8 h con celdas de 0,5 m, mucho para una curva
con τ = 30 h. Evaluando al inicio del paso, la fundación daba 82,3 °C con Δt = 6 h y 62,8 °C con
Δt = 2 min. Integrando, da 64,3 °C y 62,8 °C, y el calor total ya no depende de Δt.

## 5. Verificación (`tests/test_vertidas_hidratacion.py`)

| Prueba | Resultado esperado |
|---|---|
| Q̇h(0) y unidades | 970 W/m³ |
| Integrar Q̇h/(ρ·cp) | Recupera θ(t) |
| m(T) | 1 a 20 °C, 3,55 a 50 °C, menor que 1 a 5 °C |
| Caja adiabática a tiempo largo, con y sin madurez | Sube 45 °C exactos |
| Calor total con Δt = 20 min, 1 h y 6 h | Sube 45 °C exactos |
| Sin madurez | Sigue la curva exacta θ(t) |
| Colocación a 40 °C contra 10 °C | La caliente sube más en las primeras 12 h |
| Cada vertida | Hidrata desde su propia hora |

## 6. Efecto en la fundación

Malla Δx = 0,25 m, Δz = 0,275 m, 14 días, parámetros provisorios:

| Modelo | T máx | Instante | ΔT máx |
|---|---|---|---|
| Con madurez | 61,47 °C | 105 h | 45,19 °C |
| Sin madurez | 59,09 °C | 200 h | 44,70 °C |

Ignorar la temperatura adelanta poco el valor, pero cambia mucho el momento del peak.

## 7. Limitaciones y pendientes para E09

- **Calibrar θ∞ y τ.** Punto de partida: que el modelo reproduzca el caso de Ju & Lei sin control
  térmico (cerca de 73 °C hacia el día 4 y ΔT ≈ 35 °C), con la estimación de aumento adiabático de
  la especificación ICH como contraste. Eso es validación; lo de la sección 5 es verificación.
- **Confirmar Ea/R** con una fuente citable.
- **Evaluar dos exponenciales** si una sola no reproduce la forma de la curva. El código ya lo admite.
- **Sin efecto de edad en k y cp:** se suponen constantes.
