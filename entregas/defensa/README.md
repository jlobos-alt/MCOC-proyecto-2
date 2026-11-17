# Defensa (jueves 19-nov): el plan más rápido con P_f ≤ 5 %

> «Nuestro plan termina de colocar todo el hormigón en **D horas**. Es el más rápido de la familia de planes
> evaluada que satisface una probabilidad de excedencia conjunta no mayor que 5 %, bajo el modelo de
> incertidumbre declarado.»

**Estado al 17-nov:** la cadena completa funciona y está probada, pero **las 8 curvas de hidratación del
profesor todavía no están en el repo**. Todo lo de abajo usa la curva C1 **provisoria**: muestra el método y
la física, no es la decisión final. Con las curvas reales en `datos/curvas_hidratacion/` se vuelve a correr el
mismo comando. Qué llevar y qué preguntar mañana: [CONSULTAS_Y_CHECKLIST.md](CONSULTAS_Y_CHECKLIST.md).

## Cómo correr (desde la raíz del repo)

```powershell
python -m pytest tests/test_defensa.py -q             # 10 pruebas (S25 contra la solución exacta, decisión, curvas)
python scripts/descargar_clima_defensa.py             # SOLO para un clima nuevo: nunca pisa el anterior
python scripts/defensa_plan.py                        # familia completa + comprobaciones (~5 min con 8 núcleos)
python scripts/defensa_plan.py --rapido               # familia reducida (~45 s)
python scripts/defensa_plan.py --rehacer-figuras      # figuras desde results/defensa/corridas.csv
```

## 1. El problema de decisión

- **t₀ = jueves 19-nov-2026, 08:00 (America/Santiago)**, el mismo para todos los planes.
- **Objetivo:** D(u) = max_j t_fin,j − t₀. Postergar la primera vertida cuenta en D.
- **Recursos** (supuesto declarado, consulta 2 del taller):
  - r = 40 m³/h, con una bomba y sin vertidas simultáneas.
  - d_j = V_j / r. Volumen total de 636,9 m³, es decir **15,9 h de colocación**.
- **Colocación por capas:** dentro de cada vertida, cada celda aparece cuando el hormigón llega a su altura,
  a ritmo constante. No es una activación instantánea.
- **Familia evaluada:** 48 planes.

  | Decisión | Valores |
  |---|---|
  | Partición | 5 vertidas del IFC, o vertida única |
  | Espera entre vertidas | 0, 6, 12, 24 y 48 h (paso declarado) |
  | Protección | ninguna, EPS 50, 100 o 150 mm en laterales y como manta sobre todo techo expuesto |
  | Temperatura de colocación | 18 °C, o 10 °C con agua fría o hielo |

  El moldaje de madera se retira a las 72 h de cada vertida. La aislación se mantiene durante toda la ventana
  evaluada; su retiro no está simulado.

## 2. Métricas y evento de falla (guía, sección 2)

```text
MT(u,s) = max_t max_{x ∈ Ω_c(t)} T            Ω_c(t): solo hormigón ya colocado
MΔ(u,s) = max_t [ max_{Ω_c(t)} T − min_{S25(t)} T ]
F = {MT > 70 °C} ∪ {MΔ > 20 °C}               P_f(u) = Σ w_mk 1{F(u, m, k)} ≤ 0,05
```

- **S25(t):** hormigón a 25 mm bajo las caras exteriores que existen en t, incluidos los **techos temporales**
  de cada vertida mientras esperan a la siguiente. La base contra el suelo no se cuenta (consulta 3).
- **Cómo se obtienen los 25 mm:** con el mismo balance de cara que usa el solver, q = (T_c − T∞)/R, y
  un perfil lineal entre el centro de la celda y la cara: T(25 mm) = T_c − q·(Δ/2 − 0,025)/k. Coincide con la
  solución exacta con un error < 10⁻⁶ °C (`tests/test_defensa.py`).
- **Al agregar una vertida:** el techo de la anterior deja de ser superficie, y aparece una superficie nueva de
  hormigón fresco a la temperatura de colocación junto a un núcleo ya caliente. Por eso **esperar entre
  vertidas sube MΔ**.
- **Horizontes:** se evalúan 14 días desde t₀ y una ventana extendida hasta D + 240 h. La decisión usa la
  extendida, para no esconder picos; ambos quedan en `corridas.csv`.

## 3. Escenarios (guía, sección 4)

**Clima:**
- **Fuente:** ensemble GFS de Open-Meteo descargado el 17-nov, con 31 miembros que cubren hasta el 2-dic 23:00.
- **3 historias completas**, con su ciclo diario, persistencia y relación entre variables:

  | Historia | Miembro | Peso |
  |---|---|---:|
  | Fría | member25 | 0,355 |
  | Media | control | 0,323 |
  | Cálida | member12 | 0,323 |

- **Cómo se eligieron:** se ordenaron los miembros por T media en [t₀, t₀ + 14 d], se formaron tres grupos de
  tamaño parecido, y de cada grupo se tomó el más cercano a su mediana. Su peso es la fracción de miembros
  que representa.
- **Horas sin ensemble** (las últimas 9 de los 14 días y la extensión): ERA5 del mismo calendario de 2025,
  etiquetado hora a hora.
- **Detalle y hashes:** `datos/forecast_defensa/`.

**Hidratación:**
- Hoy hay 1 curva provisoria (C1). Con las 8 curvas reales serán 8 × 3 = 24 escenarios por plan, con
  w_mk = p_m q_k.
- Cada curva se usa **entera**, como fuente prescrita por edad desde la activación de cada celda y **sin
  Arrhenius**, como pide la guía.
- El cargador (`src/mcplan/curvas.py`) acepta ΔT_ad [°C] o calor por masa [J/kg, J/g] con b [kg/m³], y
  conserva el calor total.

## 4. Resultados con la curva C1 PROVISORIA (malla 0,5 m)

| Plan | D [h] | P_f | MΔ más alto [°C] | MT más alto [°C] |
|---|---:|---:|---:|---:|
| Vertida única, sin protección, 18 °C | 15,9 | 1 | 46,5 | 61,8 |
| Vertida única, EPS 100, 10 °C | 15,9 | 1 | 20,4 | 54,2 |
| **Vertida única, EPS 150, 10 °C (foco)** | **15,9** | **0** | **19,1** | **54,2** |
| 5 vertidas, espera 6 h, EPS 150, 18 °C | 39,9 | 1 | 28,0 | 62,2 |
| 5 vertidas, espera 24 h, EPS 150, 18 °C | 111,9 | 1 | 41,4 | 62,9 |
| 5 vertidas, espera 48 h, sin protección, 10 °C | 207,9 | 1 | 38,1 | 51,0 |

La tabla completa de los 48 planes está en `results/defensa/planes.csv`.

- **T_max nunca es el problema:** MT ≤ 63,4 °C en todos los planes. **Manda ΔT.**
- **Las dos palancas:** aislar baja MΔ porque la superficie se enfría menos, y colocar a 10 °C baja el pico del
  núcleo.
- **Esperar empeora:** con la definición de S25, cada techo nuevo de hormigón fresco aumenta MΔ. La
  vertida única, o 5 vertidas sin espera, es a la vez la opción más rápida y la de menor MΔ.
- **Comprobaciones del plan foco:**

  | Comprobación | Resultado |
  |---|---|
  | Profundidad de S25 (25 mm / 50 mm / centro de celda a 138 mm) | MΔ = 19,1 / 19,0 / 18,8 °C: el resultado no depende de esta elección |
  | Pesos del clima (declarados, iguales, todo al frío, todo al cálido) | P_f = 0 en los cuatro |
  | Los 31 miembros del ensemble | P_f = 0, MΔ entre 18,8 y 19,1 °C: la reducción a 3 historias no cambia nada |
  | **Malla** | **El plan deja de cumplir al refinar** (tabla siguiente) |

**Convergencia de malla** (`results/defensa/malla_plan_foco.json`; clima con peso, MΔ más alto de los 3):

| Malla Δx / Δz [m] | Vertida única, EPS 150, 10 °C | Vertida única, EPS 100, 10 °C |
|---|---:|---:|
| 0,5 / 0,55 | 19,05 °C | 20,39 °C |
| 0,25 / 0,275 | 20,22 °C | 21,45 °C |
| 0,125 / 0,1375 | 21,06 °C | 22,27 °C |

- **MΔ sube al refinar y converge lento:** las diferencias son 1,16 y 0,85 °C, con orden observado ≈ 0,45.
- **Valor convergido estimado (Richardson):** cerca de 23 °C.
- **La malla de 0,5 m subestima MΔ en 2–4 °C.** En la exploración, un plan solo puede considerarse candidato
  si deja ese margen. MT casi no cambia (54,2 a 54,6 °C).

**Conclusión provisoria:** con C1, **no se encontró un plan factible**.
- El "cumple" del candidato en la malla gruesa es un artefacto de la discretización: con la malla fina,
  MΔ = 21,1 °C.
- **Para encontrar uno hace falta más margen**, unos 3 a 4 °C, y hay tres caminos:
  - Más aislación, o mantas en la cara superior.
  - Colocar todavía más frío.
  - Que la curva real libere menos calor que C1.
- Se informa así, sin relajar umbrales ni ocultar fallas.
- Con las curvas reales, el plan foco y sus competidores deben evaluarse en la malla de 0,125 m
  (unos 8 min por corrida; 24 escenarios ≈ 3 h en un núcleo, o unos 25 min con 8 procesos).

## 5. Qué se calibró, verificó y validó

| | Qué | Dónde |
|---|---|---|
| **Verificado** | Solver contra soluciones exactas, orden de convergencia, energía, Robin, Neumann; S25 contra el perfil exacto; voxelización contra la geometría analítica | E05, E06, `tests/` |
| **Calibrado** | Nada todavía: la curva C1 no se ajustó a datos | — |
| **Validado** | Nada contra observaciones independientes; Ju & Lei solo como orden de magnitud (E09) | — |

**Limitaciones:**
- La curva es provisoria.
- La aislación no se retira dentro de la ventana.
- El suelo es 1D.
- El área en escalera es ~17 % mayor que la real.
- La radiación es horizontal en todas las caras.
- La capacidad r = 40 m³/h y la mínima de 10 °C son supuestos.
- Ajustar la hidratación no valida la fundación 3D.

## Archivos

| Archivo | Qué es |
|---|---|
| `src/mcplan/decision.py` | Plan, cronograma, D, métricas, P_f por enumeración y elección |
| `src/mcplan/curvas.py` | Curvas medidas a fuente por edad (ΔT_ad o J/kg) |
| `src/mcplan/escenarios_clima.py` | Ensemble y selección de 3 historias con pesos |
| `src/mcplan/thermal.py` | S25 a 25 mm (`_min_s25`, `Result.delta_T_s25`) y colocación por capas |
| `scripts/descargar_clima_defensa.py` | Congela el clima en `datos/forecast_defensa/` |
| `scripts/defensa_plan.py` | Familia, escenarios, P_f, comprobaciones y figuras |
| `results/defensa/` | `planes.csv`, `corridas.csv`, comprobaciones, `resumen_defensa.json` y figuras |
