# Guion oral E13 — Incertidumbre y confiabilidad

Comandos desde `entregas/entrega13`. Figuras en `results/e13/`.

## Demo corta

```powershell
python scripts/e13_incertidumbre.py --solo-tabla        # la tabla
python scripts/e13_incertidumbre.py --n 100 --salida results/e13_demo   # Monte Carlo en vivo (~1 min)
```

Muestra las figuras ya calculadas, con N = 2000: `e13_estados_limite.png`, `e13_convergencia.png`,
`e13_tornado.png` y `e13_sensibilidad.png`.

**Frase de apertura:** "Cada muestra es el caso de E12 con entradas inciertas. Con todo en el nominal,
reproduce E12 exacto. Corrimos 2000 muestras solo con variabilidad aleatoria y 2000 sumando lo
epistémico".

## 1. ¿Qué es aleatorio y qué es epistémico?

- **Aleatorio:** variabilidad real que no baja con más estudio. Por ejemplo, el clima del día, la
  temperatura de cada camión, la hora de llegada del hormigón o las propiedades de un lote.
- **Epistémico:** falta de conocimiento que **sí** baja si medimos o calibramos. Por ejemplo, la curva de
  hidratación (θ∞, τ, Ea/R) y la temperatura del suelo del sitio.
- **Por qué importa:**
  - Lo aleatorio se integra en una probabilidad.
  - Lo epistémico se reporta como rango: "si θ∞ es tal, la probabilidad es tal".
  - Por eso corremos dos conjuntos: A, solo aleatorias, y B, con epistémicas.

## 2. ¿Qué variables realmente importan?

**θ∞ domina:** Spearman 0,92 con T_max, y en el tornado mueve T_max ±6,7 °C.

Le siguen:
- La temperatura de colocación: ±2,4 °C en T_max.
- Para ΔT, el aire (±2,7 °C) y el viento (±1,1 °C).

Casi no importan (< 0,4 °C): el suelo, el retiro del moldaje, k, ρ y la madera.

**Conclusión práctica:** antes de correr más Monte Carlo, conviene un ensayo adiabático o calibrar
contra Ju & Lei, porque eso reduce la incertidumbre que más pesa.

## 3. ¿Qué fuentes sostienen los rangos?

| Variable | Fuente |
|---|---|
| Propiedades térmicas | Ju & Lei (2019) y rangos de ACI 207.2R |
| Ea | 29–45 kJ/mol según Freiesleben Hansen y Pedersen (1977) y ASTM C1074 |
| θ∞ | ±10 % por contenido de cemento |
| Clima | Variabilidad interanual de ERA5 (Open-Meteo archive) |
| Ejecución | Logística de despacho y turnos |

Son **preliminares**: justifican el orden de magnitud, no están ajustadas a datos del proyecto. Las
correlaciones son juicio experto. Hay que decirlo así.

## 4. ¿Cómo se representa la incertidumbre meteorológica?

Sobre la serie del snapshot, que es climatología porque el forecast no cubre el 27-nov:

```text
T_aire + dT_aire           desfase en °C
v · f_viento               entra en h = 5,7 + 3,8 v
G · f_solar                entra en T sol-aire
```

- Las tres variables entran a la misma física de E10 a E12.
- Están correlacionadas: un día más cálido es más soleado.
- **Limitación:** el desfase es constante durante 14 días y hay un solo año de reanálisis.
- **Mejora para E14:** varios años de ERA5 (2015–2025) como escenarios, o el ensemble de Open-Meteo. Cuando
  haya forecast que cubra el 27-nov, su error depende del plazo.

## 5. ¿Existen dependencias?

Sí, y se modelan con una **cópula gaussiana**:
1. Se generan normales correlacionadas con Cholesky.
2. Cada una se lleva a su distribución con la inversa de su CDF.

| Par | ρ |
|---|---:|
| dT_aire y f_solar | 0,5 |
| dT_aire y dT_colocación | 0,6 |
| f_solar y dT_colocación | 0,3 |
| k y ρ | 0,3 |

Hay una prueba que verifica que la correlación se reproduce: Spearman ≈ 0,58, como predice la teoría para
ρ = 0,6. Ignorar la dependencia entre aire y colocación subestimaría las colas, porque los días calientes
calientan todo junto.

## 6. Definición del estado límite

```text
g_T  = 70 − T_max          g_ΔT = 20 − ΔT_max          g ≤ 0 es falla
g_sistema = min(g_T, g_ΔT)  (sistema en serie)
```

T_max es el máximo en todo el hormigón durante 14 días. ΔT es el máximo en el tiempo de
(T máx del núcleo − T mín de la superficie). La superficie se toma en centros de celda, lo que subestima
ΔT: es un sesgo de modelo declarado.

## 7. Estimación Monte Carlo

```text
p̂ = N_fallas / N
```

**Resultados con N = 2000:**

| Conjunto | P(g_T ≤ 0) | IC 95 % | P(g_ΔT ≤ 0) |
|---|---|---|---|
| A | 0/2000 | [0; 0,0019] | 2000/2000 |
| B | 187/2000 = 0,094 | [0,082; 0,107] | 2000/2000 |

**ΔT:** falla siempre, con mínimo de 29,7 °C. Es un problema de diseño, no de probabilidad: hay que cambiar
el plan (aislación, colocación más fría, enfriamiento).

## 8. Incertidumbre del estimador

```text
error estándar = √(p̂ (1 − p̂) / N)          CoV = √((1 − p̂) / (N p̂))
```

- **Conjunto B:** error estándar = 0,0065 y CoV ≈ 7 %.
- **IC de Wilson:** funciona aunque haya 0 fallas.
- **Muestras para un CoV de 10 %:** `N = (1 − p)/(p · CoV²)`. Con p = 0,094 basta con unas 970; con
  p = 10⁻³ harían falta unas 100 000. Por eso se usa HPC en E14.

## 9. No observar fallas no es demostrar p pequeña

En A no hubo ninguna falla en 2000 muestras. Eso **no** significa p = 0: solo significa que

```text
p ≤ 1 − 0,05^(1/N) ≈ 3/N = 1,5·10⁻³    con 95 % de confianza
```

- **Para demostrar p ≤ 10⁻⁴ sin fallas:** hacen falta unas 30 000 muestras.
- **Si se supone g normal:** β = 3,95 y p ≈ 4·10⁻⁵. Eso es una **extrapolación** que depende del supuesto
  sobre la cola; no está demostrado por la simulación.
- **Figura:** `e13_convergencia.png` muestra cómo la cota baja como 3/N.

## Si preguntan "¿entonces el plan cumple?"

**No.**
- ΔT falla en todas las muestras.
- T_max podría superar 70 °C si θ∞ resulta alto (41 % de las muestras con θ∞ ≥ 48 °C).

Lo prioritario es calibrar la curva de hidratación y rediseñar el plan para ΔT (E15).
