# Guion de la defensa (jueves 19-nov)

Tres argumentos, en este orden: **el modelo representa el problema → el solver lo resuelve bien → la
comparación permite decidir**.

## Frase de apertura

> «Terminamos de colocar en D = 15,9 h, que es el mínimo con una bomba de 40 m³/h: colocación continua por
> capas, hormigón a 10 °C y 150 mm de EPS. De 48 planes, es el más rápido que cumple P_f ≤ 5 %. Con las 8 curvas
> del profesor y 3 climas da P_f = 0, y en el escenario más desfavorable MΔ = 17,6 °C con la malla fina. Su
> debilidad es el calor total de las curvas: si la inversión subestima el calor (β = 3,0), queda en el límite.»

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
| **Calibrado, verificado, validado** | Verificado: el solver. Calibrado: nada aún. Validado: nada contra observaciones | README §5 |
| **Qué limita la recomendación** | El calor total de las curvas (β de la inversión), la malla converge lento, r y T_col mínimas son supuestos, la aislación no se retira y el suelo es 1D | README §5 |

## Preguntas probables

- **¿Por qué esperar entre vertidas es peor, si cada capa alcanza a enfriarse?**
  Con S25 sobre las superficies existentes, cada vertida nueva crea un techo de hormigón fresco a T_col junto a
  un núcleo ya caliente. MΔ sube de 16,0 a 21,4 °C con solo 6 h de espera (EPS 150, 10 °C), y deja de cumplir.
- **¿Por qué no subieron la malla en toda la familia?**
  Con 0,125 m cada corrida tarda ~8 min. La malla gruesa subestima MΔ en ~1,5–2,5 °C y sirve para descartar.
  Los candidatos de la frontera se refinan en sus escenarios más desfavorables: el elegido da 15,96 → 16,99 →
  17,60 °C.
- **¿Cómo usaron las 8 curvas?**
  Cada una entera, como Q(a) en W/m³ desde la activación de cada celda, con las propiedades de su probeta
  (ρ = 2476, cp = 1023) y sin Arrhenius. Son réplicas de una misma mezcla, equiprobables por hipótesis. Con
  solo la campaña SS, la de mayor confianza, P_f sigue en 0.
- **¿Qué pasa si las curvas están mal?**
  Vienen de una inversión con β = 2,5. Con β = 3,0 liberan 20 % más calor, y el plan queda en 19,7 °C con la
  malla gruesa, sin margen. Lo decimos: es la debilidad principal.
- **Con 24 escenarios, ¿qué resolución tiene P_f?**
  Cada escenario pesa entre 4,0 y 4,4 %: una falla podría todavía cumplir, dos no. Es la probabilidad
  exacta del modelo discreto, sin error de muestreo y sin intervalo binomial.
- **¿Por qué solo 3 historias de clima?**
  Son trayectorias completas y coherentes. Con los 31 miembros y las 8 curvas (248 corridas), P_f sigue en 0 y
  MΔ queda entre 8,6 y 16,0 °C con la malla gruesa. Cambiar los pesos (iguales, todo al frío, todo al medio, todo al
  cálido) tampoco cambia P_f.
- **¿Cumple con 95 % de confianza?**
  No es lo mismo. P_f ≤ 5 % es un riesgo bajo el conjunto y los pesos declarados. La enumeración no tiene error
  de muestreo, sí incertidumbre de representatividad, y no certifica ausencia de grietas.
- **¿Y el Monte Carlo de E13?**
  Queda como alternativa, con su distribución, N, semilla y cota binomial. Para la decisión usamos la
  enumeración ponderada que pide la guía.
- **¿Y después del día 14?**
  El criterio son 14 días y ahí cumple. Con la aislación puesta, el núcleo sigue caliente y MΔ sube a 18,1 °C a
  los 20 días y 19,8 °C a los 30. El plan incluye retirar la aislación de forma gradual, guiada por monitoreo.
