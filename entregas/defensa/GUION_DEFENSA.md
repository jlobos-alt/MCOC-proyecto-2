# Guion de la defensa (jueves 19-nov)

Tres argumentos, en este orden: **el modelo representa el problema → el solver lo resuelve bien → la
comparación permite decidir**.

## Frase de apertura

> «Con t₀ el 19-nov a las 08:00 y una bomba de 40 m³/h, el hormigón se coloca en 15,9 h como mínimo. Con la
> curva provisoria, ninguno de los 48 planes evaluados cumple P_f ≤ 5 % de forma robusta: manda ΔT. El mejor
> candidato, vertida única con 150 mm de aislación y hormigón a 10 °C, cumple con la malla gruesa pero no con
> la fina. Con las 8 curvas reales corremos lo mismo.»

## Sección 6 de la guía: qué explicar

| Tema | Respuesta corta | Dónde mostrarlo |
|---|---|---|
| **Balance continuo** | ρ cp ∂T/∂t = ∇·(k∇T) + q_h. Unidades: W/m³. Propiedades constantes (Ju & Lei): k = 2,22, cp = 970, ρ = 2400 | `docs/guias/G05` |
| **Dominio activo y condición inicial** | Una celda existe desde que el hormigón llega a su altura (colocación por capas a r constante). Nace a T_col y con edad 0 | `thermal.build_model` (`duracion_h`) |
| **Edad de hidratación** | a = t − t_activación de cada celda. Fuente q = ρ cp dθ/da con la curva entera, sin Arrhenius | `curvas.py`, `thermal._accumulate_sources` |
| **Bordes por etapa** | Laterales: Robin con moldaje de madera (hasta 72 h de cada vertida) + EPS. Superior: Robin + manta EPS, incluidos los techos temporales. Base: suelo 1D (R = e/k hacia T del suelo a 1 m). Juntas: conducen desde que llega la vertida de arriba | `boundary.py`, `decision.aplicar_plan` |
| **Clima en el borde** | h = 5,7 + 3,8 v + h_rad; T∞ = T sol-aire. Una sola vía para la radiación, sin contarla dos veces | `environment.py` |
| **Balance de celda** | C dT/dt = Σ G (T_j − T_i) + (A/R)(T∞ − T_i) + q V, con G = kA/d y k armónica en las interfaces | `thermal.py` |
| **Estabilidad** | Euler explícito, Δt ≤ C/ΣG (incluido el borde), factor 0,8. El caso usa Δt = 1 h | `thermal.estimate_timestep` |
| **Verificación** | Seno 1D/2D/3D con orden ≈ 2 en espacio y ≈ 1 en tiempo, energía, Robin, Neumann (E05, E06). S25 contra el perfil exacto con error < 10⁻⁶ °C | `tests/` |
| **Sensibilidad de las métricas** | Malla: MΔ = 19,1 → 20,2 → 21,1 °C (0,5 → 0,25 → 0,125 m). Profundidad de S25: 25 / 50 / 138 mm → 19,1 / 19,0 / 18,8 °C | `results/defensa/` |
| **Calibrado, verificado, validado** | Verificado: el solver. Calibrado: nada aún. Validado: nada contra observaciones | README §5 |
| **Qué limita la recomendación** | Faltan las 8 curvas, la malla converge lento, r y T_col mínimas son supuestos, la aislación no se retira y el suelo es 1D | README §5 |

## Preguntas probables

- **¿Por qué esperar entre vertidas es peor, si cada capa alcanza a enfriarse?**
  Con S25 sobre las superficies existentes, cada vertida nueva crea un techo de hormigón fresco a T_col junto a
  un núcleo ya caliente. MΔ sube de 19 a 28 °C con solo 6 h de espera (EPS 150, 10 °C).
- **¿Por qué no subieron la malla en toda la familia?**
  Con 0,125 m cada corrida tarda ~8 min. La gruesa sirve para descartar: los planes con espera tienen MΔ ≥ 28 °C,
  lejos del límite incluso con el error de malla de 2–4 °C. Solo los candidatos de la frontera se refinan.
- **¿Por qué solo 3 historias de clima?**
  Son trayectorias completas y coherentes. Con los 31 miembros, el plan foco da el mismo resultado: MΔ entre 18,8
  y 19,1 °C con la malla gruesa. Cambiar los pesos (iguales, todo al frío, todo al cálido) tampoco cambia P_f.
- **¿Cumple con 95 % de confianza?**
  No es lo mismo. P_f ≤ 5 % es un riesgo bajo el conjunto y los pesos declarados. La enumeración no tiene error
  de muestreo, sí incertidumbre de representatividad, y no certifica ausencia de grietas.
- **¿Y el Monte Carlo de E13?**
  Queda como alternativa, con su distribución, N, semilla y cota binomial. Para la decisión usamos la
  enumeración ponderada que pide la guía.
