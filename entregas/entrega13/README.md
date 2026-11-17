# E13 — Revisión oral: incertidumbre y confiabilidad (5 puntos)

**Fecha:** miércoles 18 de noviembre, 10:30–13:20 · **Objetivo:** un modelo probabilístico defendible y
estados límite claros.

Carpeta autocontenida (copia de la raíz). Guion: [docs/E13_guion_oral.md](docs/E13_guion_oral.md).
Tabla de variables: [results/e13/tabla_variables.md](results/e13/tabla_variables.md).

## Cómo correr (desde esta carpeta)

```powershell
pip install -r requirements.txt
python -m pytest tests/test_e13_incertidumbre.py -q    # 11 pruebas (~5 s)
python scripts/e13_incertidumbre.py --solo-tabla       # solo la tabla de variables
python scripts/e13_incertidumbre.py --n 200            # piloto (~2 min con 8 núcleos)
python scripts/e13_incertidumbre.py                    # N = 2000 por conjunto (~20 min con 8 núcleos)
python scripts/e13_incertidumbre.py --rehacer-figuras  # figuras desde las muestras guardadas
```

Cada muestra es **el caso determinista de E12**: IFC, curva C1, suelo, moldaje y clima de los snapshots.
Con todas las variables en su nominal, el script reproduce E12 exactamente (T_max = 63,98 °C,
ΔT_max = 42,06 °C), y una prueba lo verifica.

## Modelo probabilístico

**15 variables**: 11 aleatorias y 4 epistémicas, con 4 dependencias. La tabla completa, con fuentes, está en
`results/e13/tabla_variables.md` y el código en `src/mcplan/incertidumbre.py`.

| Grupo | Variable | Naturaleza | Distribución |
|---|---|---|---|
| Clima | `dT_aire` (desfase de la T del aire) | aleatoria | N(0; 2) °C en [−6; 6] |
| | `f_viento` (factor sobre v) | aleatoria | LogN(mediana 1; σ_ln 0,25) |
| | `f_solar` (factor sobre G) | aleatoria | U[0,75; 1,10] |
| Ejecución | `dT_colocacion` (desfase común) | aleatoria | N(0; 1,5) °C en [−5; 5] |
| | `ruido_colocacion` ×5 (por camión) | aleatoria | N(0; 0,7) °C en [−2,5; 2,5] |
| | `retraso_vertida_h` ×4 | aleatoria | U[0; 3] h, solo atrasos |
| | `retiro_moldaje_h` | aleatoria | U[60; 84] h |
| Materiales | `f_k`, `f_cp`, `f_rho` | aleatoria | N(1; 0,08 / 0,05 / 0,02), truncadas |
| | `f_k_moldaje` | aleatoria | U[0,8; 1,25] |
| Hidratación y suelo | `theta_inf_C` | **epistémica** | N(45; 4) °C en [35; 55] |
| | `tau_h` | **epistémica** | U[20; 40] h |
| | `Ea_R_K` | **epistémica** | U[3500; 5400] K |
| | `T_suelo_C` | **epistémica** | N(14,5; 1) °C en [11; 18] |

**Dependencias (cópula gaussiana):** ρ(dT_aire, f_solar) = 0,5; ρ(dT_aire, dT_colocacion) = 0,6;
ρ(f_solar, dT_colocacion) = 0,3; ρ(f_k, f_rho) = 0,3. Un día más cálido suele ser más soleado y entrega
hormigón más tibio. Las demás variables son independientes.

**Estados límite** (g ≤ 0 es falla):

```text
g_T  = 70 − T_max
g_ΔT = 20 − ΔT_max
g_sistema = min(g_T, g_ΔT)      sistema en serie: falla si falla cualquiera
```

**Estimador Monte Carlo:**

```text
p̂ = N_fallas / N          error estándar = √(p̂ (1 − p̂) / N)          CoV = √((1 − p̂) / (N p̂))
IC 95 %: Wilson (sirve con 0 fallas)          con 0 fallas: p ≤ 1 − 0,05^(1/N) ≈ 3/N
N para un CoV dado: N = (1 − p) / (p · CoV²)
```

Dos conjuntos con la misma semilla, para separar las naturalezas:

- **A:** solo aleatorias; las epistémicas quedan en el nominal de E12.
- **B:** aleatorias + epistémicas.

## Resultados (N = 2000 por conjunto, semilla 20261118, malla 0,5 m)

| Conjunto | T_max media ± σ | T_max P95 | ΔT_max media ± σ | P(g_T ≤ 0) | IC 95 % | P(g_ΔT ≤ 0) |
|---|---|---|---|---|---|---|
| A: solo aleatorias | 63,71 ± 1,59 °C | 66,40 °C | 42,14 ± 1,72 °C | **0/2000** | [0; 0,0019] | 2000/2000 |
| B: + epistémicas | 63,92 ± 4,46 °C | 71,37 °C | 42,31 ± 4,13 °C | **187/2000 = 0,094** | [0,082; 0,107] | 2000/2000 |

- **ΔT falla en todas las muestras**, con mínimo de 29,7 °C en B: con este plan, sin aislación, el problema
  no es de probabilidad sino de diseño.
- **T_max:**
  - En A no hubo fallas. Eso **solo** permite afirmar p ≤ 1,5·10⁻³ con 95 % de confianza.
  - Suponer g normal daría β = 3,95 y p ≈ 4·10⁻⁵, pero es una extrapolación y no está demostrado.
  - En B, p̂ = 0,094 con CoV ≈ 7 %. Para un CoV de 10 % bastaban unas 970 muestras.
- **Lo epistémico se reporta como rango.** En B, P(g_T ≤ 0) según θ∞:

  | θ∞ | P(g_T ≤ 0) | IC 95 % |
  |---|---|---|
  | < 42 °C | 0/455 | [0; 0,0084] |
  | 42–48 °C | 4/1099 = 0,0036 | [0,0014; 0,0093] |
  | ≥ 48 °C | 183/446 = 0,41 | [0,37; 0,46] |

**Qué importa:** θ∞ domina ambas salidas, con Spearman 0,92 para T_max y 0,90 para ΔT_max.

| Variable | Efecto en T_max (P05 a P95) | Efecto en ΔT_max (P05 a P95) |
|---|---:|---:|
| θ∞ | ±6,7 °C | ±5,9 °C |
| Temperatura de colocación común | ±2,4 °C | ±2,2 °C |
| Temperatura del aire | ±0,2 °C | ∓2,7 °C |
| Viento | ±0,1 °C | ±1,1 °C |

El suelo, el retiro del moldaje, f_k, f_rho y la madera mueven menos de 0,4 °C.

## Rúbrica de la revisión → dónde está

| Debe poder justificar | Dónde |
|---|---|
| Aleatorio contra epistémico | Columna `naturaleza` de la tabla; conjuntos A y B |
| Qué variables importan | `e13_sensibilidad.png` (Spearman) y `e13_tornado.png` (una variable a la vez) |
| Fuentes de rangos y distribuciones | Columna `fuente` de `tabla_variables.md` |
| Incertidumbre meteorológica | `dT_aire`, `f_viento` y `f_solar` sobre la serie del snapshot, correlacionadas |
| Dependencias | `CORRELACIONES` en `incertidumbre.py` (cópula gaussiana); prueba de que se reproducen |
| Estado límite | `estados_limite()`: g_T, g_ΔT y sistema en serie |
| Estimación Monte Carlo | `scripts/e13_incertidumbre.py`, `muestras_A.csv` y `muestras_B.csv` |
| Incertidumbre del estimador | `estimar()`: error estándar, CoV, Wilson, N requerido; `e13_convergencia.png` |
| Cero fallas no demuestra p pequeña | `cota_cero_fallas()`, prueba `test_cero_fallas_no_demuestra_una_probabilidad_chica` y la figura de convergencia |

## Reproducibilidad y HPC

- **Muestras particionables:** la muestra i usa `default_rng([semilla, i])`, así que da lo mismo en cualquier
  orden y en cualquier máquina.
- **Tramos para Slurm:**
  ```powershell
  python scripts/e13_incertidumbre.py --conjunto B --desde 0 --hasta 500
  ```
  Esto calcula solo ese tramo, listo para un arreglo de Slurm en E14.
- **Trazabilidad:** antes de muestrear se verifican los snapshots (SHA-256), y `resumen_e13.json` guarda la
  semilla, N, la malla y los snapshots usados.

## Limitaciones declaradas

- **Distribuciones preliminares:**
  - Las fuentes justifican el orden de magnitud, pero los rangos no están ajustados a datos del proyecto.
  - Las correlaciones son juicio experto.
- **Clima:**
  - El desfase de temperatura es constante durante los 14 días, sin estructura temporal.
  - Hay un solo año de reanálisis.
  - Mejora para E14: varios años de ERA5 (2015–2025) o el ensemble de Open-Meteo.
- **Error de modelo, no muestreado:**
  - ΔT se mide en centros de celda, a 25 cm de la cara, no a 25 mm: subestima ΔT.
  - El área en escalera es ~17 % mayor que la real.
  - El suelo es 1D.

  Son sesgos epistémicos y se declaran aparte de la probabilidad.
- **Curva C1 provisoria:** las probabilidades comparan y discuten el método; no aprueban el plan.

## Evidencia (Canvas)

```
Repositorio: https://github.com/jlobos-alt/MCOC-proyecto-2
Commit evaluado: <SHA completo de git rev-parse HEAD>
```
