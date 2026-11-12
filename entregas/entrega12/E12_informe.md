# E12 — Simulación determinista de 14 días

**Grupo 5:** José Lobos, Clemente Sánchez y Matías Campos

**Repositorio:** https://github.com/jlobos-alt/MCOC-proyecto-2

**Commit evaluado:** f53f3d9

**Fecha:** viernes 13 de noviembre de 2026

**Caso:** fundación del IFC, 5 vertidas, 336 h desde el 27-nov-2026 04:00

## 1. Introducción

Este informe documenta la simulación determinista de 14 días (336 h) del caso de fundación del IFC. Su propósito es evaluar, con un único conjunto de supuestos y sin variabilidad aleatoria, si el plan de vertidas satisface los criterios de 70 °C de temperatura máxima y 20 °C de diferencial núcleo-superficie. El modelo integra la geometría y la secuencia del IFC, una única curva de hidratación (C1), el suelo semi-infinito, el moldaje por vertida, el clima de snapshots verificados y la visualización tridimensional, sobre una malla de 0,5 m. Los resultados indican que el criterio de 70 °C se satisface con 63,98 °C, mientras que el diferencial alcanza 42,06 °C y excede los 20 °C.

## 2. Curva de hidratación

Se emplea la curva C1, única declarada en el modelo desde E09: θ_ad(a) = 45·(1 − e^(−a/30)) °C, con madurez de Arrhenius Ea/R = 4000 K y T_ref = 20 °C, sin segunda rama exponencial (θ∞₂ = 0). La curva se evalúa con la edad equivalente: el hormigón caliente libera la misma energía en menos tiempo. La curva proporciona θ_ad(24 h) = 24,78 °C, θ_ad(168 h) = 44,83 °C y q̇(0) = 0,97 kW/m³.

$$θ_ad(a) = θ∞ (1 − e^(−a/τ)),    q̇_h = ρ c_p (dθ_ad/da) · m(T)$$

La curva se modifica editando θ∞, τ y Ea/R en `datos/fundacion_e12.yaml`; no se mezclan curvas entre vertidas.

## 3. Clima: datasets, timestamps y horizonte

Dos snapshots inmutables de Open-Meteo, verificados mediante SHA-256 antes de simular:

| Snapshot | Contenido | Horizonte | SHA-256 (csv) |
|---|---:|---:|---:|
| 20261111T193622Z_open-meteo-forecast | forecast best_match, Pahuil/Chanco; emitido 2026-11-11 19:36:22 UTC | 2026-11-11 00:00 → 2026-11-24 23:00 (336 h) | `ba1d71b5…` |
| 20261111T193623Z_open-meteo-archive | reanalysis ERA5 del mismo calendario | 2025-11-27 00:00 → 2025-12-11 23:00 (360 h) | `f4377629…` |

**Horizonte no cubierto.** La primera vertida ocurre el 27 de noviembre de 2026 a las 04:00, mientras que el pronóstico disponible finaliza el 24 de noviembre y no aporta horas. Las 336 h se completan con la climatología del archivo, desplazada al año del caso, hora a hora y sin interpolación entre años. Cada fila de `series_e12.csv` declara su fuente: 0 h de pronóstico y 337 puntos de climatología, sin horas faltantes. El archivo presenta aire entre 8,0 y 20,6 °C, viento medio de 2,57 m/s (máximo 7,06), radiación máxima de 1081 W/m², h entre 10,65 y 37,63 W/(m²·K) y sol-aire máxima de 47,96 °C.

## 4. Condiciones de borde

Las caras laterales y la superficie usan una condición de Robin; la base es un medio conductivo semi-infinito:

| Frontera | Tipo | Parámetros |
|---|---:|---:|
| Lateral y superior | Robin | −k∂T/∂n = h(t)·(T − T∞); h = 5,7 + 3,8v + 4εσT³; T∞ = T sol-aire; α = 0,6; ε = 0,9 |
| Moldaje | Capa en serie | madera 19 mm, k = 0,12 → R = 0,158 m²K/W; se retira 72 h después de cada vertida |
| Base | Robin conductivo | R = e/k = 1,0/1,389 = 0,72 m²K/W; T∞ = suelo a 1 m (onda anual, amortiguación 0,69, atraso 517 h) |
| Inicial | Dirichlet | T = 18 °C al colocar cada vertida |
| Fuente | Volumétrica | q̇ de la curva C1 con madurez de Arrhenius |

Muestras de la serie que recibe la condición de Robin:

| t [h] | Hora local | T aire [°C] | v [m/s] | G [W/m²] | h [W/m²K] | T∞ [°C] | T suelo [°C] |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 04:00 | 8,1 | 0,25 | 0 | 11,2 | 6,9 | 13,9 |
| 12 | 16:00 | 17,3 | 2,98 | 955 | 22,0 | 41,2 | 14,0 |
| 24 | 04:00 | 10,5 | 1,35 | 0 | 15,5 | 8,6 | 14,0 |
| 72 | 04:00 | 12,5 | 2,09 | 0 | 18,4 | 9,6 | 14,1 |
| 168 | 04:00 | 13,5 | 0,47 | 0 | 12,3 | 9,1 | 14,3 |
| 336 | 04:00 | 13,2 | 1,10 | 0 | 14,7 | 12,2 | 14,7 |

## 5. Plan de vertidas

El plan se obtiene del IFC (horas, temperatura de colocación, moldaje y retiro), sin datos de obra en el script:

| V | Inicio [h] | Hora local | T col. [°C] | z [m] | Moldaje | Retiro [h] |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 04:00 | 18,0 | 0,00–0,55 | Madera | 72 |
| 2 | 6 | 10:00 | 18,0 | 0,55–1,10 | Madera | 72 |
| 3 | 12 | 16:00 | 18,0 | 1,10–2,20 | Madera | 72 |
| 4 | 18 | 22:00 | 18,0 | 2,20–3,30 | Madera | 72 |
| 5 | 24 | 04:00 | 18,0 | 3,30–4,30 | Madera | 72 |

Las cinco vertidas suman 636,89 m³ y usan madera sin aislación.

## 6. Resultados de los criterios de 70 °C y 20 °C

| Criterio | Límite [°C] | Valor [°C] | Instante | Veredicto |
|---|---:|---:|---:|---:|
| T_max | 70 | 63,98 | 54 h · 2026-11-29 10:00 | **cumple** |
| ΔT_max | 20 | 42,06 | 148 h · 2026-12-03 08:00 | **no cumple** |

La temperatura máxima asciende a 63,98 °C a las 54 h en la celda (-0,25; -0,25; 1,38) m, sobre el eje del pedestal (V3). Queda 6,02 °C bajo el límite, aunque el hormigón permanece 208 h sobre 60 °C.

El diferencial máximo alcanza 42,06 °C a las 148 h. El núcleo más caliente está en (-0,25; -0,25; 1,93) m con 62,43 °C (V3), y la superficie más fría en (-8,75; -3,75; 0,82) m con 20,38 °C (V2), sobre la cara lateral. El ΔT supera los 20 °C en 313 de las 337 horas: comienza a las 24 h y permanece sobre el límite al finalizar la ventana (34,26 °C a las 336 h).

La temperatura máxima por vertida es V1 57,03 °C, V2 61,96 °C, V3 63,98 °C, V4 63,27 °C y V5 61,56 °C, con instantes entre 43 y 64 h. El máximo global se explica por la acumulación de V1–V3 en el centro del bloque.

## 7. Curvas núcleo-superficie y visualización tridimensional

![](results/e12/e12_clima.png)

*Figura 1. Clima del caso: aire, sol-aire, suelo y h(t) en las 336 h (todo climatología).*

![](results/e12/e12_curva_c1.png)

*Figura 2. Curva C1: elevación adiabática y calor volumétrico con madurez.*

![](results/e12/e12_criterios.png)

*Figura 3. T_max(t) contra 70 °C y ΔT(t) contra 20 °C.*

El núcleo asciende con rapidez y desciende lentamente: 63,98 °C a las 54 h y 56,58 °C al final. La superficie sigue el ciclo diario y el retiro del moldaje: 35,53 °C a las 54 h y 20,38 °C a las 148 h. El ΔT crece de 28,45 a 42,06 °C al retirarse el moldaje (72–96 h), cuando la cara lateral pasa de R ≈ 0,37 a ≈ 0,21 m²K/W.

![](results/e12/e12_nucleo_superficie.png)

*Figura 4. Curvas núcleo (máximo) y superficie (mínimo) con el ΔT y el límite de 20 °C.*

![](results/e12/e12_3d_tmax.png)

*Figura 5. Cortes ortogonales x = 0, y = 0 y z = 1,6 m en el instante de T_max.*

![](results/e12/e12_3d_dtmax.png)

*Figura 6. Los mismos cortes en el instante de ΔT_max: núcleo caliente y perímetro frío.*

![](results/e12/e12_3d_zonas.png)

*Figura 7. Zonas de control del criterio (núcleo y superficie) a t = 148 h.*

La serie `.vti` (17 archivos, cada 24 h y los dos máximos) se abre en ParaView con temperatura, vertida y las zonas de control.

## 8. Conclusiones

En las condiciones declaradas, el plan no satisface el criterio de 20 °C: la temperatura máxima se mantiene bajo 70 °C, con 63,98 °C a las 54 h y 6,02 °C de margen, pero el diferencial alcanza 42,06 °C a las 148 h. El veredicto es determinista, pues la corrida reproduce exactamente la misma serie y la no conformidad proviene de los supuestos del caso, no de una fluctuación aleatoria.

El resultado está controlado por dos mecanismos. La temperatura máxima depende del calor de hidratación acumulado por las cinco vertidas y de las pérdidas de borde, y se aproxima a la suma adiabática de 63 °C porque la pérdida temprana es pequeña. El diferencial depende del desacople núcleo-superficie: con k = 2,22 W/(m·K) y V3 de 1,10 m, la conducción del núcleo tarda semanas, mientras que la superficie sigue el aire y la radiación en horas. El mínimo de superficie (20,38 °C), y no el máximo del núcleo, fija el ΔT, que crece al retirarse el moldaje.

Para cumplir los 20 °C sería necesario desacoplar la superficie, por ejemplo con aislación lateral de EPS o un retiro más tardío del moldaje; esa comparación se abordará en E15.

## 9. Reproducibilidad

```powershell
cd entregas/entrega12
pip install -r requirements.txt
python scripts/e12_determinista.py
python -m pytest tests -q
```

El script imprime los siete pasos, verifica los snapshots y genera las figuras, `series_e12.csv` (337 filas con su fuente), las tablas de borde y plan, `resumen_e12.json` y la serie `.vti`. La corrida usa dt = 3600 s y 336 pasos. Los nueve tests comprueban la curva, el clima, el plan, ambos criterios, la ubicación de los máximos y la repetibilidad.
