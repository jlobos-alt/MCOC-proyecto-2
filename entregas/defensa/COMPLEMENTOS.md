# Evidencia complementaria del plan elegido

Revisión contra la rúbrica del 18-nov: cubre lo que faltaba en C5 (sensibilidad temporal y balance de energía del caso real) y en C6 (mecanismo con curvas y campos), y rehace la robustez sobre el plan **elegido**, porque antes se había corrido con la variante EPS 100.

```powershell
python scripts/defensa_complementos.py                    # mecanismo, dt, energía y 30 días (~1 min)
python scripts/defensa_complementos.py --partes robustez  # robustez del plan elegido (~5 min con 7 procesos)
python -m pytest tests/test_defensa_complementos.py -q
```

Usa la misma cadena que `scripts/defensa_plan.py`: IFC, 8 curvas, clima, plan y solver. Los resultados quedan en `results/defensa/complementos/` (`complementos.json` y figuras), sin tocar los existentes. Malla de 0,5 m salvo que se indique otra.

## C6 — Mecanismo: mismos datos y recursos

Escenario más desfavorable de la propuesta: curva **M4_SS**, clima **medio**. Reproduce el MΔ de `corridas.csv` (15,96 °C).

| Caso | D [h] | MT [°C] | MΔ [°C] | Instante de MΔ |
|---|---:|---:|---:|---|
| Vertida única sin protección, 18 °C | 15,9 | 56,8 | 41,5 | 259 h |
| **Propuesta: única, EPS 150, 10 °C** | **15,9** | **49,5** | **16,0** | 335 h |
| 5 vertidas, espera 6 h, EPS 150, 10 °C | 39,9 | 49,7 | 20,7 | 42 h |
| 5 vertidas, espera 48 h, EPS 150, 10 °C | 207,9 | 51,7 | 40,0 | 208 h |

**Mecanismo** (`mecanismo_series.png`, `mecanismo_cortes.png`): con espera, cada vertida nueva entra a 10 °C sobre un núcleo que ya se calentó. Su cara superior es parte de S25, así que MΔ salta justo al terminar la colocación: 20,7 °C a las 42 h con espera de 6 h, y saltos de hasta 40 °C con 48 h. Sin protección, la superficie sigue el ciclo diario y MΔ oscila hasta 41,5 °C.

**No hay variante más rápida.** Con una bomba de 40 m³/h, colocar 636,9 m³ toma como mínimo 15,9 h, y la propuesta ya coloca sin pausas. Una variante más rápida exige más recursos, fuera de la familia declarada.

## C5 — Sensibilidad temporal

Plan elegido, peor escenario:

| Δt [s] | MT [°C] | MΔ [°C] |
|---:|---:|---:|
| 3600 | 49,453 | 15,964 |
| 1800 | 49,464 | 15,982 |
| 900 | 49,467 | 15,986 |

Pasar de 1 h a 15 min cambia MΔ en 0,02 °C, frente a los 1,6 °C que cambia por malla. El error de la decisión lo controla la malla, no el paso temporal.

## C5 — Balance de energía del caso real

Fundación del plan elegido con todas las caras adiabáticas, curva M4_SS y colocación por capas. Lo que almacena el hormigón, ρ·cp·V·(T − T_col), se compara con la integral de la fuente de cada celda desde su llegada:

| Δt [s] | Generado [GJ] | Almacenado [GJ] | Error relativo |
|---:|---:|---:|---:|
| 3600 | 64,1263 | 64,1081 | 2,8·10⁻⁴ |
| 900 | 64,1263 | 64,1231 | 5,0·10⁻⁵ |
| 225 | 64,1263 | 64,1257 | 1,1·10⁻⁵ |

La diferencia es la fracción de paso entre que llega el hormigón a una celda y el paso en que esa celda nace, y baja con Δt. Sin colocación por capas, el cierre es exacto (E06: 1,2·10⁻¹⁰ °C). Prueba: `tests/test_defensa_complementos.py`.

## Robustez del plan elegido (EPS 150, 10 °C)

| Comprobación | P_f | MΔ máx [°C] |
|---|---:|---:|
| Pesos del clima: declarados, iguales, todo frío, todo medio, todo cálido | 0 en todos | — |
| Solo la campaña SS | 0 | — |
| S25 a 25 / 50 / 275 mm | 0 / 0 / 0 | 15,96 / 15,90 / 15,39 |
| β de la inversión 2,1 / 3,0 | 0 / 0 | 12,98 / **19,70** |
| 31 miembros × 8 curvas (248 corridas) | 0 | 8,58 a 16,04 |

## Después del día 14

El criterio del curso son 14 días, y ahí el plan cumple. Pero con la aislación puesta, el núcleo se mantiene caliente mientras la superficie se enfría, y **MΔ sigue subiendo** (`posterior_30d.png`):

| Hasta | MΔ máx [°C] | T máx a esa hora [°C] |
|---|---:|---:|
| 14 días | 15,96 | 48,9 |
| 20 días | 18,10 | 47,8 |
| 25 días | 19,41 | 46,8 |
| 30 días | 19,77 | 45,6 |

Con el sesgo de malla (+1,6 °C entre 0,5 y 0,125 m), pasaría los 20 °C hacia el día 20–25. **El plan necesita un protocolo de retiro gradual de la aislación, guiado por monitoreo**: retirar cuando el núcleo haya bajado y la diferencia medida entre núcleo y superficie lo permita. El clima después del ensemble es ERA5 de 2025, como climatología.

## Qué decir en la defensa

- **Margen:** en el escenario más desfavorable, 17,6 °C con malla fina y ~18,5 °C estimado convergido. Con β = 3,0, la malla gruesa ya da 19,7 °C: si ambos efectos se suman, el plan queda en el límite.
- **El paso temporal no decide** (0,02 °C) y **la energía cierra** (≤ 3·10⁻⁴, y baja con Δt).
- **Después de los 14 días** hace falta retirar la aislación de forma controlada.
