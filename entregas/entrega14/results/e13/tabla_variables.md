| Variable | Naturaleza | Nominal E12 | Distribución | Qué representa | Fuente |
|---|---|---|---|---|---|
| `dT_aire` | aleatoria | 0 °C | N(0; 2) en [-6; 6] | Desfase de la temperatura del aire respecto de la serie de clima, todo el periodo | Variabilidad interanual de fines de noviembre (ERA5, Open-Meteo archive); el forecast a >10 dias no supera a la climatologia. A recalcular con 2015-2025. |
| `f_viento` | aleatoria | 1 - | LogN(mediana 1; σ_ln 0.25) |  |  |
| `f_solar` | aleatoria | 1 - | U[0.75; 1.1] | Factor sobre la radiacion de onda corta (nubosidad del periodo) | Dispersion de la radiacion diaria de fines de noviembre en ERA5; acotada por cielo despejado. |
| `dT_colocacion` | aleatoria | 0 °C | N(0; 1.5) en [-5; 5] | Desfase comun de la temperatura de colocacion de todas las vertidas | Control de temperatura en planta (especificacion ICH 2019) y temperatura del dia. |
| `ruido_colocacion` ×5 | aleatoria | 0 °C | N(0; 0.7) en [-2.5; 2.5] | Diferencia de temperatura de cada camion respecto del desfase comun (una por vertida) | Variacion entre lotes de una misma jornada. |
| `retraso_vertida_h` ×4 | aleatoria | 0 h | U[0; 3] | Atraso de cada vertida (2 a 5) respecto del intervalo planificado de 6 h | Logistica de despacho y bombeo; solo atrasos, nunca adelantos. |
| `retiro_moldaje_h` | aleatoria | 72 h | U[60; 84] | Hora de retiro del moldaje desde cada vertida (plan: 72 h) | Turno de la cuadrilla; ±12 h alrededor del plan. |
| `f_k` | aleatoria | 1 - | N(1; 0.08) en [0.8; 1.2] | Factor sobre la conductividad del hormigon (k = 2,22 W/(m·K)) | Ju & Lei (2019) y rangos de ACI 207.2R segun arido y humedad. |
| `f_cp` | aleatoria | 1 - | N(1; 0.05) en [0.85; 1.15] | Factor sobre el calor especifico (cp = 970 J/(kg·K)) | Ju & Lei (2019); cp depende de la humedad del hormigon joven. |
| `f_rho` | aleatoria | 1 - | N(1; 0.02) en [0.95; 1.05] | Factor sobre la densidad (2400 kg/m³) | Control de densidad en obra; la densidad varia poco. |
| `f_k_moldaje` | aleatoria | 1 - | U[0.8; 1.25] | Factor sobre la conductividad del moldaje de madera (k = 0,12 W/(m·K)) | Humedad de la madera y tipo de terciado. |
| `theta_inf_C` | epistemica | 45 °C | N(45; 4) en [35; 55] | Elevacion adiabatica final de la curva C1 | Proporcional al contenido de cemento (±10 %); sin ensayo adiabatico del hormigon del proyecto. |
| `tau_h` | epistemica | 30 h | U[20; 40] | Constante de tiempo de la curva C1 | Rango de cementos Portland; se fija al calibrar contra Ju & Lei o un ensayo. |
| `Ea_R_K` | epistemica | 4000 K | U[3500; 5400] | Energia de activacion / R (madurez de Arrhenius) | Ea = 29-45 kJ/mol: Freiesleben Hansen y Pedersen (1977), ASTM C1074. |
| `T_suelo_C` | epistemica | 14.5 °C | N(14.5; 1) en [11; 18] | Temperatura media anual del suelo a 1 m | No hay medicion en el sitio: se estima desde la media anual del aire. |

Dependencias (cópula gaussiana):

- ρ(dT_aire, f_solar) = 0.5
- ρ(dT_aire, dT_colocacion) = 0.6
- ρ(f_solar, dT_colocacion) = 0.3
- ρ(f_k, f_rho) = 0.3
