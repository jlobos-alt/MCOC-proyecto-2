# Defensa (jueves 19-nov): el plan más rápido con P_f ≤ 5 %

> **Nuestro plan termina de colocar todo el hormigón en D = 15,9 h.** Colocamos los 636,9 m³ en forma continua,
> por capas, con una bomba de 40 m³/h, hormigón a 10 °C y 150 mm de EPS en laterales y como manta superior.
> Es el más rápido de los 48 planes evaluados, empatado con sus variantes de 15,9 h, y entre ellos el de mayor
> margen. Cumple **P_f = 0 ≤ 5 %** bajo las 8 curvas del profesor, las 3 historias de clima y los pesos
> declarados.

Con la capacidad declarada, **15,9 h es la duración mínima posible**: el plan no puede ser más rápido sin más
recursos. La pregunta que queda es si ese plan cumple, y con qué margen.

Qué llevar y qué preguntar al taller: [CONSULTAS_Y_CHECKLIST.md](CONSULTAS_Y_CHECKLIST.md). Guion:
[GUION_DEFENSA.md](GUION_DEFENSA.md). Mecanismo, sensibilidad temporal, balance de energía, robustez del plan
elegido y qué pasa después del día 14: [COMPLEMENTOS.md](COMPLEMENTOS.md).

## Cómo correr (desde la raíz del repo)

```powershell
python -m pytest tests/test_defensa.py -q             # 12 pruebas (S25 exacto, decisión, curvas reales)
python scripts/defensa_plan.py                        # 48 planes x 24 escenarios + comprobaciones (~25 min, 8 núcleos)
python scripts/defensa_plan.py --rapido               # familia reducida
python scripts/defensa_plan.py --rehacer-figuras      # figuras desde results/defensa/corridas.csv
python scripts/descargar_clima_defensa.py             # SOLO para un clima nuevo: nunca pisa el anterior
```

## 1. Problema de decisión

- **t₀ = jueves 19-nov-2026, 08:00 (America/Santiago)**, común a todos los planes.
- **D(u) = max_j t_fin,j − t₀.** Postergar la primera vertida cuenta en D.
- **Recursos declarados:**
  - r = 40 m³/h, con una bomba y sin vertidas simultáneas.
  - d_j = V_j/r: 636,9 m³ → **15,9 h**.
  - Colocación **por capas**: cada celda aparece cuando el hormigón llega a su altura. No hay activación
    instantánea.
- **Familia, 48 planes:**

  | Decisión | Valores |
  |---|---|
  | Partición | 5 vertidas del IFC, o vertida única |
  | Espera entre vertidas | 0, 6, 12, 24 y 48 h (paso declarado) |
  | Protección | ninguna, EPS 50, 100 o 150 mm (laterales + manta sobre todo techo expuesto) |
  | Temperatura de colocación | 18 °C, o 10 °C con agua fría o hielo |

  El moldaje de madera se retira a las 72 h de cada vertida. La aislación se mantiene toda la ventana.

## 2. Métricas y falla

```text
MT = max_t max_{Ω_c(t)} T              Ω_c(t): solo hormigón ya colocado
MΔ = max_t [ max_{Ω_c(t)} T − min_{S25(t)} T ]
F = {MT > 70} ∪ {MΔ > 20}      P_f = Σ w_mk 1{F}      w_mk = p_m q_k (material y clima independientes)
```

- **S25(t):** hormigón 25 mm bajo las caras exteriores **existentes en t**, incluidos los techos temporales.
  La base contra el suelo no se cuenta.
- **Cómo se obtienen los 25 mm:** con el balance de cara del solver, q = (T_c − T∞)/R, y un perfil lineal
  dentro de la celda. Coincide con la solución exacta con un error < 10⁻⁶ °C.
- **Horizontes:** 14 días desde t₀ y una ventana extendida hasta D + 240 h. Decide la extendida; ambas quedan
  en `corridas.csv`.

## 3. Escenarios: 8 curvas × 3 climas = 24 por plan

**Curvas** (`datos/curvas_hidratacion/`; el original de Canvas está intacto en `originales/source_terms.txt`):

| Qué | Detalle |
|---|---|
| Magnitud | Fuente volumétrica Q(t) [W/m³], paso de 10 min, obtenida por inversión FV + Tikhonov de probetas cilíndricas |
| Probetas | M1–M4 de una misma mezcla (350,8 kg/m³ de cemento), en dos campañas: SS (240 h) y 22A (163 h, de **menor confianza** según el archivo) |
| Calor total | 61–100 MJ/m³ (24–40 K adiabáticos); peak de Q a las 12–17 h |
| Propiedades | Se usan **juntas con cada curva**, como pide la guía: ρ = 2476 kg/m³ y cp = 1023 J/(kg K) |
| Uso en el solver | Cada curva **entera**, como fuente prescrita por edad desde la activación de cada celda, sin Arrhenius. El cargador reproduce exactamente el calor total de la cabecera |
| Pesos | **Hipótesis declarada:** las 8 son réplicas equiprobables (1/8) |

**Clima:**
- **Fuente:** ensemble GFS de Open-Meteo del 17-nov, con 31 miembros.
- **3 historias completas:**

  | Historia | Miembro | Peso |
  |---|---|---:|
  | Fría | member25 | 0,355 |
  | Media | control | 0,323 |
  | Cálida | member12 | 0,323 |

- **Cómo se eligieron:** se formaron tres grupos de tamaño parecido según la T media del aire, y de cada uno se
  tomó el miembro más cercano a su mediana. Su peso es la fracción de miembros del grupo.
- **Horas sin ensemble:** ERA5 de 2025, etiquetado hora a hora.

**Resolución del modelo discreto:** cada escenario pesa entre 4,0 y 4,4 %. Una sola falla podría todavía
cumplir; dos no.

## 4. Resultados (malla 0,5 m)

**Planes con P_f ≤ 5 %:** todos tienen D = 15,9 h, porque colocar todo seguido es lo único que cumple.

| Plan | D [h] | P_f | MΔ más alto [°C] | MT más alto [°C] |
|---|---:|---:|---:|---:|
| **Única, EPS 150, 10 °C (elegido)** | **15,9** | **0** | **16,0** | **49,5** |
| Única, EPS 100, 10 °C | 15,9 | 0 | 17,1 | 49,4 |
| Única, EPS 150, 18 °C | 15,9 | 0 | 20,0 (21,2 con malla de 0,25 m: no cumple) | 57,3 |
| Única, EPS 50, 10 °C | 15,9 | 0,04 | 20,0 | 49,4 |

**Desviaciones**, comparadas como pide la guía:

| Plan | D [h] | P_f | MΔ más alto [°C] | Por qué no se prefiere |
|---|---:|---:|---:|---|
| Única, sin protección, 18 °C | 15,9 | 1 | 41,8 | Igual de rápido, pero falla siempre por ΔT |
| Única, EPS 100, 18 °C | 15,9 | 0,38 | 21,4 | Sin enfriar el hormigón no alcanza |
| 5 vertidas, espera 6 h, EPS 150, 10 °C | 39,9 | 0,25 | 21,4 | **24 h más lento y peor**: cada techo de hormigón fresco sube MΔ |
| 5 vertidas, espera 48 h, EPS 150, 10 °C | 207,9 | 1 | 40,1 | **192 h más lento** y no gana nada a cambio |

La tabla completa de los 48 planes está en `results/defensa/planes.csv`.

## 5. Robustez del plan elegido

| Comprobación | Resultado |
|---|---|
| **Malla**, escenario más desfavorable (M4_SS) | MΔ = 15,96 → 16,99 → **17,60 °C** (0,5 → 0,25 → 0,125 m). Estimado convergido ≈ 18,5 °C: **cumple, con ~1,5 °C de margen** |
| Profundidad de S25 (25 / 50 / 275 mm) | P_f = 0; MΔ máximo 15,96 / 15,90 / 15,39 °C: la elección no cambia la conclusión |
| Pesos del clima (declarados, iguales, todo frío, todo medio, todo cálido) | P_f = 0 en todos |
| Solo la campaña SS (1/4 cada una) | P_f = 0 |
| Los 31 miembros del ensemble × 8 curvas (248 corridas) | P_f = 0, MΔ entre 8,6 y 16,0 °C |
| **β de la inversión** de las curvas | β = 2,1: P_f = 0, MΔ máximo 13,0 °C. **β = 3,0** (+20 % de calor): P_f = 0, MΔ máximo **19,7 °C** con la malla gruesa, sin margen para el error de malla. **Ahí la decisión es frágil** |
| Paso temporal (Δt = 3600 / 1800 / 900 s) | MΔ = 15,964 / 15,982 / 15,986 °C: el paso temporal no decide |
| Balance de energía, caso real aislado | Error relativo 2,8·10⁻⁴ con Δt = 1 h, que baja con Δt (1,1·10⁻⁵ con 225 s) |
| **Después del día 14**, aislación puesta | MΔ sigue subiendo: 18,1 °C a los 20 días y 19,8 °C a los 30. Hace falta retirar la aislación de forma gradual, guiada por monitoreo |

Todas las filas son del plan elegido (EPS 150, 10 °C), malla de 0,5 m salvo la de malla. Antes, varias se
habían corrido sobre la variante EPS 100; se rehicieron con `scripts/defensa_complementos.py`. Detalle y
figuras en [COMPLEMENTOS.md](COMPLEMENTOS.md).

**Conclusión admisible** (guía 4.3): *cumple bajo el conjunto de 8 curvas, 3 climas y los pesos declarados.* Las 8
curvas no certifican por sí solas un 95 % de confiabilidad real, y el criterio térmico no demuestra ausencia de
grietas.

La debilidad principal es **cuánto calor libera realmente el hormigón**. Si las curvas lo subestiman (β alto en la
inversión), el plan queda en el límite. Una mejora sin costo de tiempo sería aislación más gruesa, o colocar más
frío si la planta lo permite.

## 6. Calibrado, verificado, validado y limitaciones

| | Qué | Dónde |
|---|---|---|
| **Verificado** | Solver contra soluciones exactas, órdenes de convergencia, energía, Robin y Neumann (E05, E06); S25 contra el perfil exacto; carga de curvas contra los totales de la cabecera; voxelización contra la geometría analítica | `tests/` |
| **Calibrado** | Nada en este repo. Las curvas Q(t) ya vienen invertidas por el profesor | — |
| **Validado** | Nada contra observaciones independientes. Ajustar la hidratación no valida la fundación 3D | — |

**Limitaciones:**
- La aislación no se retira dentro de la ventana; el enfriamiento posterior se informa aparte.
- El suelo es 1D.
- El área en escalera es ~17 % mayor que la real.
- La radiación es horizontal en todas las caras.
- La capacidad r = 40 m³/h y la temperatura mínima de 10 °C son supuestos.
- A las curvas les faltan sus 2 primeras horas, y las 22A terminan a las 163 h.

## Archivos

| Archivo | Qué es |
|---|---|
| `src/mcplan/decision.py` | Plan, cronograma, D, MT/MΔ, P_f por enumeración y elección (desempate por margen) |
| `src/mcplan/curvas.py` | Curvas medidas → fuente por edad (ΔT_ad, J/kg o W/m³), con sus propiedades |
| `src/mcplan/escenarios_clima.py` | Ensemble → 3 historias con pesos |
| `src/mcplan/thermal.py` | S25 a 25 mm y colocación por capas |
| `results/defensa/` | `planes.csv`, `corridas.csv`, `resumen_defensa.json`, `robustez_curvas_reales.json`, `malla_plan_foco.json` (corrida previa con C1) y figuras |
