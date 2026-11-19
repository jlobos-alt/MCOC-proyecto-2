# Guion de la defensa (jueves 19-nov, F02)

Formato: **7 min de exposición + 5 de preguntas**. La exposición se corta a los 7 min. Cualquiera puede recibir
preguntas sobre cualquier parte (C8 es individual, 9 de 40 puntos).

Tres argumentos, en este orden: **el modelo representa el problema → el solver lo resuelve bien → la
comparación permite decidir**.

## Datos que hay que declarar (F02 §7)

| Qué | Valor |
|---|---|
| Grupo y autores | Grupo 5: José Lobos, Clemente Sánchez, Matías Campos |
| Repositorio y SHA | `https://github.com/jlobos-alt/MCOC-proyecto-2`, SHA: `git rev-parse HEAD` antes de entrar |
| Comandos | `python scripts/defensa_plan.py` (48 planes × 24 escenarios, ~25 min); `python scripts/defensa_complementos.py`; caso único: `--rapido` |
| t₀ y zona horaria | **19-nov-2026 08:00, America/Santiago**, común a todos los planes |
| Sitio | Pahuil / Chanco, Maule: −35,644721, −72,568332 |
| Clima congelado | Snapshot `20261117T173409Z` (ensemble GFS, Open-Meteo, descargado el 17-nov 17:34 UTC) + ERA5 2025 para horas sin ensemble |
| Curvas | `datos/curvas_hidratacion/originales/source_terms.txt`: M1–M4 SS y M1–M4 22A, Q(t) en W/m³, β = 2,5 |
| Recursos | Una bomba de 40 m³/h, sin vertidas simultáneas; colocación por capas; T_col 18 o 10 °C; EPS 50/100/150 mm |
| Geometría | IFC de la guía de Bonsai: 636,9 m³, 18 m entre caras, 3,30 m + pedestal de 1 m |
| Escenarios y pesos | 8 curvas (1/8 c/u) × 3 climas (35,5 / 32,3 / 32,3 %) = 24 por plan, fijados **antes** de comparar |
| Métricas por corrida | `results/defensa/corridas.csv` (1152 filas); tabla agregada `results/defensa/planes.csv` |

**Sin internet:** el visor corre local (`python -m http.server 8765 --directory results/visor` y abrir
`http://localhost:8765/visor.html`). Llevar también las figuras de `results/defensa/` y `complementos/`.

## Exposición: 9 láminas en 7 minutos

Presentación: [`Presentacion_Defensa_G5.pptx`](Presentacion_Defensa_G5.pptx) (y su
[PDF](Presentacion_Defensa_G5.pdf)). El texto de cada lámina está en las **notas del orador**: usar la Vista
Moderador. Se genera con `python scripts/figuras_presentacion.py` y `python scripts/presentacion_defensa.py`.

| # | Lámina | Quién | Tiempo | Qué se ve |
|---|---|---|---|---|
| 1 | Portada | Matías | 0:10 | BIM 3D del IFC |
| 2 | La decisión | Matías | 0:35 | 15,9 h · P_f 0 % · MΔ 17,6 °C · MT 49,5 °C |
| 3 | El problema de decisión | Matías | 0:45 | D frente a P_f de los 48 planes; t₀ con America/Santiago |
| 4 | Datos reales | Matías | 0:45 | IFC, 8 curvas, clima |
| 5 | Modelo físico | José | 1:00 | Ecuación y corte con los bordes por etapa |
| 6 | Solver y verificación | José | 1:05 | Convergencia, malla, energía, Δt |
| 7 | Probabilidad | Clemente | 0:50 | Grilla de los 24 escenarios (propuesta frente a espera 6 h) y una fila de ejemplo |
| 8 | Comparación y mecanismo | Clemente | 1:00 | Tabla con P_T, P_Δ y P_f; MΔ(t) de los 4 casos; corte del techo frío |
| 9 | Recomendación y límites | Clemente | 0:50 | Margen, fragilidad (β), día 14 (retiro no simulado), sensores |
| A–D | Anexos | Para preguntas | — | Robustez, después del día 14, cortes, voxeles |

Tabla comparativa (lámina 8):

| Plan | D [h] | P_T [%] | P_Δ [%] | P_f [%] | ¿Cumple? |
|---|---:|---:|---:|---:|---|
| Una vertida sin protección, 18 °C | 15,9 | 0 | 100 | 100 | No |
| **Propuesta: una vertida, EPS 150, 10 °C** | **15,9** | **0** | **0** | **0** | **Sí** |
| Más rápida | — | — | — | — | No existe: D ≥ 636,9/40 = 15,9 h con la bomba declarada |
| 5 vertidas, espera 6 h, EPS 150, 10 °C | 39,9 | 0 | 25 | 25 | No |
| 5 vertidas, espera 48 h, EPS 150, 10 °C | 207,9 | 0 | 100 | 100 | No |

Fila de ejemplo (lámina 7):

| Plan | Curva | Clima | Peso w | M_T [°C] | M_Δ [°C] | I_T | I_Δ | I_F |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Propuesta | M4_SS | medio | 0,0403 | 49,45 | 15,96 | 0 | 0 | 0 |
| 5 vertidas, espera 6 h | M4_SS | medio | 0,0403 | 49,66 | 20,69 | 0 | 1 | 1 |

## Plan de sensores y contingencia (lámina 8 y respaldo)

| Sensor | Dónde | Para qué |
|---|---|---|
| Termocuplas de núcleo | Eje del pedestal, a media altura y a 1,1 m | Seguir MT, comparar con el modelo |
| Termocuplas de piel | 25 mm bajo el techo, bajo una cara lateral y en el borde de la losa | Seguir T_S25 y la diferencia MΔ medida |
| Termómetro en cada camión | Al llegar (ASTM C1064) | Verificar T_col ≤ 10–12 °C |
| Estación meteorológica | En obra | Viento y temperatura reales frente al ensemble |

| Si… | Entonces |
|---|---|
| Un camión llega sobre 12 °C | Rechazarlo o agregar hielo en planta |
| La diferencia medida pasa 18 °C | Mantener la aislación, agregar una segunda manta |
| La temperatura del núcleo sube más rápido que el modelo | Revisar contra β = 3,0 y alargar la permanencia de la aislación |
| Después del día 14 | Retirar la aislación **por etapas**, solo cuando la diferencia medida lo permita |

## Sección 6 de la guía: qué explicar

| Tema | Respuesta corta | Dónde mostrarlo |
|---|---|---|
| **Balance continuo** | ρ cp ∂T/∂t = ∇·(k∇T) + q_h. Unidades: W/m³. Propiedades constantes: k = 2,22 (Ju & Lei); ρ = 2476 y cp = 1023, las de las probetas de las curvas | `docs/guias/G05` |
| **Dominio activo y condición inicial** | Una celda existe desde que el hormigón llega a su altura (colocación por capas a r constante). Nace a T_col y con edad 0 | `thermal.build_model` (`duracion_h`) |
| **Edad de hidratación** | a = t − t_activación de cada celda. Fuente Q(a) [W/m³] de cada curva, entera y sin Arrhenius | `curvas.py`, `thermal._accumulate_sources` |
| **Bordes por etapa** | Laterales: Robin con moldaje de madera (hasta 72 h de cada vertida) + EPS. Superior: Robin + manta EPS, incluidos los techos temporales. Base: suelo 1D (R = e/k hacia T del suelo a 1 m). Juntas: conducen desde que llega la vertida de arriba | `boundary.py`, `decision.aplicar_plan` |
| **Clima en el borde** | h = 5,7 + 3,8 v + h_rad; T∞ = T sol-aire. Una sola vía para la radiación, sin contarla dos veces | `environment.py` |
| **Balance de celda** | C dT/dt = Σ G (T_j − T_i) + (A/R)(T∞ − T_i) + q V, con G = kA/d y k armónica en las interfaces | `thermal.py` |
| **Estabilidad** | Euler explícito, Δt ≤ C/ΣG (incluido el borde), factor 0,8. El caso usa Δt = 1 h | `thermal.estimate_timestep` |
| **Verificación** | Seno 1D/2D/3D con orden ≈ 2 en espacio y ≈ 1 en tiempo, energía, Robin, Neumann (E05, E06). S25 contra el perfil exacto con error < 10⁻⁶ °C | `tests/` |
| **Sensibilidad de las métricas** | Malla (plan elegido, M4_SS): MΔ = 15,96 → 16,99 → 17,60 °C (0,5 → 0,25 → 0,125 m). Profundidad de S25 25 / 50 / 275 mm: 15,96 / 15,90 / 15,39 °C. Δt de 1 h a 15 min: 0,02 °C. Energía: error 2,8·10⁻⁴, baja con Δt | `COMPLEMENTOS.md` |
| **Calibrado, verificado, validado** | Verificado: el solver. Calibrado: nada (las curvas ya vienen invertidas). Validado: nada contra mediciones de la fundación | README §6 |
| **Qué limita la recomendación** | El calor total de las curvas (β de la inversión), la malla converge lento, r y T_col mínimas son supuestos, el retiro de la aislación no está simulado y el suelo es 1D | README §6 |

## Preguntas probables

- **¿Por qué esperar entre vertidas es peor, si cada capa alcanza a enfriarse?**
  Con S25 sobre las superficies existentes, cada vertida nueva crea un techo de hormigón fresco a T_col junto a
  un núcleo ya caliente. Con 6 h de espera (EPS 150, 10 °C), MΔ llega a 20,7 °C en M4_SS y 21,4 °C en M2_22A:
  fallan esas 2 curvas en los 3 climas, 6 escenarios, P_f = 25 %.
- **¿Por qué no subieron la malla en toda la familia?**
  Con 0,125 m cada corrida tarda ~8 min. La malla gruesa subestima MΔ en ~1,5–2,5 °C y sirve para descartar.
  Los candidatos de la frontera se refinan en sus escenarios más desfavorables: el elegido da 15,96 → 16,99 →
  17,60 °C. Una vertida a 18 °C con EPS 150 da 20,0 °C con malla gruesa y 21,2 °C con 0,25 m: no se acepta.
- **¿Cómo usaron las 8 curvas?**
  Cada una entera, como Q(a) en W/m³ desde la activación de cada celda, con las propiedades de su probeta
  (ρ = 2476, cp = 1023) y sin Arrhenius. Una misma curva para toda la fundación en cada escenario: variación
  común del material. Son réplicas de una misma mezcla, equiprobables por hipótesis. Con solo la campaña SS, la
  de mayor confianza, P_f sigue en 0.
- **¿Qué pasa si las curvas están mal?**
  Vienen de una inversión con β = 2,5. Con β = 3,0 liberan 20 % más calor, y el plan queda en 19,7 °C con la
  malla gruesa, sin margen. Lo decimos: es la debilidad principal.
- **Con 24 escenarios, ¿qué resolución tiene P_f?**
  Cada escenario pesa entre 4,0 y 4,4 %: una falla podría todavía cumplir, dos no. Es la probabilidad
  exacta del modelo discreto, sin error de muestreo y sin intervalo binomial.
- **¿Por qué solo 3 historias de clima? ¿Por qué el clima casi no cambia el resultado?**
  Son trayectorias completas y coherentes, elegidas por terciles de la T media del ensemble. Difieren en menos
  de 1 °C de media, y con 150 mm de EPS el núcleo es casi adiabático (difusión L²/α ≈ 36 días). Con los 31
  miembros y las 8 curvas (248 corridas), P_f sigue en 0 y MΔ queda entre 8,6 y 16,0 °C. Cambiar los pesos
  (iguales, todo al frío, todo al medio, todo al cálido) tampoco cambia P_f. Sin aislación el clima sí mueve MΔ
  cerca de 1 °C.
- **¿Cumple con 95 % de confianza?**
  No es lo mismo. P_f ≤ 5 % es un riesgo bajo el conjunto y los pesos declarados. La enumeración no tiene error
  de muestreo, sí incertidumbre de representatividad, y no certifica ausencia de grietas.
- **¿Y el Monte Carlo de E13?**
  Queda como alternativa, con su distribución, N, semilla y cota binomial (0 fallas en N = 60 da 4,87 %). Para la
  decisión usamos la enumeración ponderada que pide la guía.
- **¿Por qué enfriar a 10 °C si con EPS 150 a 18 °C también da P_f = 0?**
  Con malla gruesa da P_f = 0 pero con MΔ = 19,95 °C. Con la malla de 0,25 m, 7 de 24 escenarios pasan 20 °C
  (hasta 21,2 °C) y P_f = 29 %: el error de malla cambia la clasificación, así que ese plan no cumple.
- **¿Por qué no usan Arrhenius?**
  Cada curva se usa tal cual, por edad: simplificación declarada. A 10 °C el inicio sería más lento, pero en el
  núcleo a 45–50 °C la hidratación sería más rápida que en la probeta. No es necesariamente conservador; el
  efecto neto sobre el peak no está cuantificado.
- **¿Truncaron la respuesta a los 14 días?** (F02 §3.2 pide no ganar ventaja truncando)
  En el plan elegido MΔ ocurre a las 335 h, al final de la ventana, y sigue subiendo: 18,1 °C a los 20 días y
  19,8 °C a los 30 con la malla gruesa. Con el sesgo de malla (+1,6 °C) pasaría 20 °C hacia el día 20–25 **si la
  aislación se deja puesta**. Por eso declaramos que el cumplimiento vale para 14 días y que el plan requiere
  retirar la aislación por etapas guiado por los sensores. **Ese retiro no está simulado**: es la siguiente
  corrida a hacer.
- **¿Dónde ocurren los máximos?**
  MT: en el núcleo, cerca del eje (a ~1,5 m de él) y a ~2,5 m de altura, a las 222 h (peor escenario, campo
  guardado cada 6 h). MΔ: entre ese núcleo y la piel a 25 mm, al final de la ventana (335 h). Se ve en el corte
  del visor y en `mecanismo_cortes.png`. Guardamos el instante por corrida; la ubicación se lee en los campos.
- **¿Es viable colocar a 10 °C?**
  Sí, con agua enfriada y unos 20 kg de hielo por m³ (≈ 13 t en total), áridos a la sombra y hormigonado de
  noche; se controla midiendo cada camión. Es un supuesto declarado: a 18 °C el plan no cumple con malla fina.
- **¿Por qué 636,9 m³ y 4,3 m de alto, si el artículo dice 3,3 m?**
  Usamos la geometría docente de la guía de Bonsai del curso: 3,3 m centrales más un pedestal de 1 m "adoptado
  sólo para el ejercicio docente"; su chequeo de volumen da 636,89 m³. Es más hormigón y un núcleo más grueso
  que el artículo (~489 m³), así que es el lado conservador.
- **¿Qué información nueva no incorporaron?**
  El clima quedó congelado en el snapshot del 17-nov para que todos los planes usen los mismos insumos. Un
  pronóstico más reciente no está incluido; dada la baja sensibilidad al clima, no esperamos que cambie la
  decisión.
