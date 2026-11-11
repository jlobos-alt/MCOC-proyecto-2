# E10 — Guía de la revisión oral

**Fecha:** miércoles 11 de noviembre de 2026, 10:30–13:20.
**Foco:** cómo el ambiente real entra a la física y cómo se obtienen pronósticos trazables.
**Duración sugerida de la demo:** 6–8 minutos + preguntas.

---

## 0. La idea en una frase

El solver no sabe de clima ni de moldaje: solo resuelve un Robin

$$-k\frac{\partial T}{\partial n}=h(t)\,\bigl(T-T_\infty(t)\bigr)$$

en cada cara expuesta. Todo E10 consiste en construir $h(t)$ y $T_\infty(t)$ de forma defendible, y en dejar registro de dónde salieron.

$$
R_{\text{cara}}=\underbrace{\frac{\Delta x/2}{k_h}}_{\text{medio celda}}
+\underbrace{R_{\text{moldaje}}}_{\text{por vertida}}
+\underbrace{R_{\text{aislación}}}_{\text{por vertida}}
+\underbrace{\frac{1}{h(t)}}_{\text{viento + radiación}}
$$

El suelo es el mismo Robin, pero con $R_{\text{suelo}}=e/k$ y $T_\infty$ igual a la temperatura no perturbada a 1 m.

---

## 1. Mapa de archivos (para mostrar en pantalla)

| Requisito | Archivo | Qué mirar |
|---|---|---|
| Condiciones de borde | `src/mcplan/boundary.py` | `BoundaryGroup.h_series`, `convective_resistance(t)`, `minimum_resistance` |
| Ambiente | `src/mcplan/environment.py` | `wind_convection_coefficient`, `sol_air_temperature`, `aplicar_ambiente` |
| Suelo | `src/mcplan/soil.py` | `SoilSpec`: `penetration_depth`, `damping`, `phase_lag_h`, `resistance` |
| Moldaje / aislación | `datos/fundacion_e10.yaml`, `plan.py`, `thermal.py` | catálogos `moldajes`/`aislaciones`, `r_moldaje_flat`, `formwork_end_flat` |
| Cliente meteorológico | `src/mcplan/meteo.py` | `OpenMeteoClient.forecast/archive`, `assemble_timeline` |
| Snapshots | `src/mcplan/snapshots.py`, `datos/forecast/index.json` | `save_snapshot`, `verify`, hashes |
| Demo | `scripts/e10_ambiente.py`, `results/e10/` | 4 casos, 4 figuras, `resumen_e10.json` |

---

## 2. Las nueve preguntas

### 2.1 ¿Qué término usa la temperatura ambiente?

Es el **`far_field`** del Robin, es decir $T_\infty$ en

$$-k\frac{\partial T}{\partial n}=h\,(T-T_\infty).$$

En el código: `BoundaryGroup.far_field_at(t)` y la serie `TemperatureSeries` (`model.ambient`). Para las caras laterales y la superficie, $T_\infty$ es la **temperatura sol-aire** $T_{sa}$, no la temperatura del aire cruda. Para la base, $T_\infty$ es la temperatura del suelo a 1 m.

**Respuesta de 20 segundos:** “La temperatura ambiente entra como temperatura de película del Robin (`far_field`). No es un término fuente: es la temperatura contra la que la cara intercambia calor. Si hay sol, uso temperatura sol-aire en vez de temperatura de aire.”

---

### 2.2 ¿Cómo entra el viento si el modelo lo considera?

Entra en el **coeficiente convectivo**, no como fuerza ni como presión:

$$h_{conv}=5{,}7+3{,}8\,v \quad [\mathrm{W/(m^2K)}],\qquad v\ \text{en m/s}.$$

En `environment.py: wind_convection_coefficient`. El script arma `h_series(t)` leyendo el viento de cada hora del timeline; el solver lo evalúa en cada paso (`boundary.py: convective_resistance(t)`). Como $h$ cambia, `build_model` calcula `h_max` en el horizonte y `estimate_timestep` usa ese máximo para no perder estabilidad.

**Si preguntan por el techo:** el viento no cambia la temperatura del aire; cambia la resistencia superficial. Con viento fuerte, $h$ sube, la película pesa menos y la cara sigue más de cerca al aire.

---

### 2.3 ¿Cómo modelar una resistencia térmica de moldaje?

Como una **capa conductiva en serie**:

$$R_{\text{moldaje}}=\frac{e}{k}.$$

Madera de 19 mm con $k=0{,}12$: $R=0{,}158\ \mathrm{m^2K/W}$. Está declarada en el catálogo del YAML (`datos/fundacion_e10.yaml: moldajes`) y el IFC trae `Moldaje = Madera` por vertida. En `thermal.py`, cada celda de la vertida hereda `r_moldaje_flat` y `r_aislacion_flat`; en `_accumulate_boundary` esas resistencias se suman solo en caras laterales (x, y).

$$R_{\text{cara}}=\frac{\Delta x/2}{k_h}+R_{\text{moldaje}}+R_{\text{aislación}}+\frac{1}{h}.$$

**Si preguntan por contacto:** se puede agregar $R_{contacto}$; en esta entrega se desprecia y se declara. **Si preguntan por el orden:** en serie el orden no cambia $R$ total; cambia el perfil dentro de las capas, que aquí no se resuelve.

---

### 2.4 ¿Qué cambia al desmoldar?

Cambia la **condición de frontera en el tiempo**, no la malla. Mientras el moldaje está puesto, la cara lateral tiene $R_{\text{moldaje}}$; al retirarlo, esa resistencia desaparece y la cara pasa a

$$R_{\text{cara}}=\frac{\Delta x/2}{k_h}+R_{\text{aislación}}+\frac{1}{h(t)}.$$

En `thermal.py`, `formwork_end_flat = inicio_h + retiro_moldaje_h` (72 h después de **cada** colocación). En `_accumulate_boundary`:

```python
activo = t_h < model.formwork_end_flat[celdas]
extra = np.where(activo, capa, 0.0) + model.r_aislacion_flat[celdas]
```

Consecuencia física: al desmoldar baja $R$, sube la conductancia y el hormigón se enfría más rápido; el gradiente núcleo–superficie aumenta. En la figura `results/e10/e10_moldaje.png` se ven los cinco escalones: 0, 6, 12, 18 y 24 h, cada uno con su retiro a las 72 h.

**Ojo:** las caras que se usan para el criterio de superficie son las **permanentes** (`_definir_conjuntos_de_control`). El desmoldaje cambia el campo térmico, pero no redefine qué es “superficie” para el criterio.

---

### 2.5 ¿Qué es un flujo solar?

Es una **densidad de flujo** de onda corta, $G$ [W/m²], que llega a la superficie. El hormigón no absorbe todo: absorbe

$$q_{solar}=\alpha G,$$

con $\alpha\approx 0{,}6$ para hormigón visto. No es una temperatura: es energía por unidad de área y tiempo. En el código aparece en `environment.py: surface_heat_fluxes` como `q_solar`, y en `sol_air_temperature` dentro del numerador.

**Si preguntan por la diferencia con radiación de onda larga:** el sol es onda corta (≈0,3–3 µm) y atraviesa la atmósfera; la onda larga (≈5–50 µm) es el intercambio entre la superficie y el cielo. Ambos son radiación, pero se tratan por separado.

---

### 2.6 ¿Cómo evitar doble contar radiación y convección?

Eligiendo **una sola vía** y declarándola. Hay dos implementaciones válidas:

1. **Sol-aire (la que usa E10):** se juntan convección y radiación en un único Robin:
   $$h_{total}=h_{conv}+h_{rad},\qquad h_{rad}=4\varepsilon\sigma T^3,$$
   $$T_{sa}=T_{aire}+\frac{\alpha G+\varepsilon\sigma(T_{cielo}^4-T_{aire}^4)}{h_{total}}.$$
   El solver ve **un** $h$ y **un** $T_\infty$; la radiación ya está adentro.

2. **Flujos separados:** $h$ solo convectivo, y la radiación entra como flujo Neumann $q_{rad}$ o como un segundo Robin con $T_{cielo}$. También es válido, pero no se mezcla con la vía 1.

**Regla mnemotécnica:** o la radiación está dentro de $T_{sa}$, o está como flujo; nunca las dos. En el código, la frontera `perimetro` y `superficie` son Robin y **no** tienen `flujo_W_m2`. El caso `sin_radiacion` apaga $G$ y la onda larga, y sirve para ver cuánto aporta la radiación: ≈0,8 °C en $T_{max}$ y ≈1,6 °C en $\Delta T$.

**Si preguntan por el test:** `tests/test_e10_ambiente.py::test_sol_aire_suma_radiacion_sin_tocar_la_aire` verifica que con $G=0$ el sol-aire vuelve a $T_{aire}$, y `test_balance_de_flujos_es_consistente` verifica que `q_neto = q_conv + q_solar + q_lw`.

---

### 2.7 ¿Qué diferencia hay entre forecast, reanalysis y observación?

| Fuente | Qué es | Cuándo se conoce | Uso correcto |
|---|---|---|---|
| **Forecast** | Predicción emitida en un instante por un modelo numérico | Antes del evento | Forzar la simulación con lo que se sabía ese día |
| **Reanalysis** | Serie histórica consistente (asimilación de observaciones) | Después del evento | Climatología, validación, relleno declarado |
| **Observación** | Medición de una estación | Después del evento (o en tiempo real) | Validar el modelo; no forzarlo si no se conocía |

En el repo: `meteo.py` descarga forecast y archive; cada snapshot declara `source`. El reanalysis **no** se usa como si fuera forecast: sería *data leakage* (usar información que no existía al momento de decidir). La observación no se usa porque no hay estación propia en Pahuil; se declara como límite y como paso de validación futuro.

---

### 2.8 ¿Qué ocurre si el forecast no cubre aún los 14 días posteriores al 27?

**Es exactamente lo que pasa hoy.** El forecast descargado el 11-nov-2026 llega hasta el 24-nov-2026 23:00; la primera vertida es el 27-nov-2026 04:00. Cobertura de forecast en la ventana: **0 de 337 h**.

La solución no es inventar ni estirar el forecast:

1. Se usa el forecast solo donde cubre.
2. El resto se rellena con **climatología**: reanalysis del mismo calendario (27-nov a 11-dic de 2025) desplazado al año del caso.
3. Cada hora queda etiquetada: `forecast`, `climatology` o `missing`.
4. Cuando exista un forecast que cubra el 27, se guarda un **snapshot nuevo** y se vuelve a correr; el anterior no se edita.

En `meteo.py: assemble_timeline` está el `if not dentro: fuente = "climatology"`. En `results/e10/resumen_e10.json` se lee `"cobertura": {"climatology": 337}` y `"cobertura_forecast_h": 0`.

**Respuesta de 20 segundos:** “Se rellena con climatología declarada y etiquetada. El tramo sin forecast no se disfraza de forecast: queda como `climatology` hasta que llegue el pronóstico que cubra la obra.”

---

### 2.9 ¿Por qué se deben conservar forecasts antiguos?

Porque un forecast es un **documento**, no un dato mutable:

- **Trazabilidad:** saber qué pronóstico se usó en cada corrida y con qué hash.
- **Reproducibilidad:** volver a correr la simulación del 11-nov y obtener lo mismo, aunque hoy el servicio devuelva otra cosa.
- **Auditoría técnica:** comparar la decisión con la información disponible en su momento; sin esto, se contamina con información posterior.
- **Evaluación del proveedor:** medir el error del forecast contra observación y ajustar el margen de seguridad.

Implementación: `save_snapshot()` crea una carpeta por emisión y **falla** si se intenta guardar otro contenido con el mismo id; `index.json` guarda `sha256_raw` y `sha256_csv`; `verify()` recalcula y detecta alteraciones. El test `test_verify_detecta_un_snapshot_alterado` lo demuestra.

---

## 3. Guion de demo (6–8 min)

### Paso 1 — Enseñar el snapshot (1 min)

```powershell
cd entregas/entrega10
Get-Content datos/forecast/index.json
```

Decir: “Dos snapshots: forecast del 11-nov (336 h, hasta el 24-nov) y reanalysis del mismo calendario de 2025 (360 h). Cada uno tiene hash del JSON crudo y del CSV normalizado. No se pisan.”

### Paso 2 — Correr o mostrar la demo (2 min)

```powershell
python scripts/e10_ambiente.py --dx 0.5
```

Salida esperada:

```
Snapshots verificados: 2
Clima ensamblado: {'climatology': 337}
Grilla: dx=0.5 m, dz=0.55 m, 4656 celdas activas, error de volumen 0.52 %

Simulando caso base...
  T max = 63.23 °C a 55 h; ΔT max = 44.47 °C a 192 h; dt = 3600 s
Simulando caso ambiente...
  T max = 63.98 °C a 54 h; ΔT max = 42.06 °C a 148 h; dt = 3600 s
Simulando caso sin_radiacion...
  T max = 63.21 °C a 55 h; ΔT max = 43.62 °C a 148 h; dt = 3600 s
Simulando caso aislado...
  T max = 63.98 °C a 54 h; ΔT max = 34.72 °C a 197 h; dt = 3600 s

Ambiente vs base: T max +0.75 °C, ΔT max -2.41 °C
```

### Paso 3 — Figuras (2 min)

| Figura | Qué decir |
|---|---|
| `results/e10/e10_clima.png` | Aire, sol-aire y suelo a 1 m. El sol-aire llega a 47,96 °C (con $G$ hasta 1081 W/m²): la radiación no es despreciable. Abajo, viento y $h_{total}$ (10,65–37,63 W/m²K). Fondo beige = climatología. |
| `results/e10/e10_casos.png` | $T_{max}$ y $\Delta T$ de los 4 casos. `base` y `ambiente` casi se superponen en $T_{max}$; `aislado` baja el $\Delta T$ de 42,06 a 34,72 °C. |
| `results/e10/e10_moldaje.png` | Cinco escalones de $R$ lateral; cada vertida se desmolda a sus 72 h. Línea punteada: variante con EPS. |
| `results/e10/e10_efectos.png` | Barras comparativas: la aislación no cambia $T_{max}$ pero sí el gradiente. |

### Paso 4 — Cierre (1 min)

“El ambiente no entra como un número mágico: entra como $h(t)$ y $T_\infty(t)$. El suelo entra como $R=e/k$ y onda anual. El moldaje entra como capa en serie por vertida y se retira a las 72 h. La radiación entra una sola vez, por sol-aire. Y cada dato meteorológico tiene snapshot, fuente y hash. La hidratación sigue provisoria: esto es una cadena de ambiente defendible, no una calibración.”

---

## 4. Números de la corrida (para tener a mano)

| Dato | Valor |
|---|---|
| Grilla | `dx = 0,5 m`, `dz = 0,55 m`, 36 × 36 × 8, 4 656 celdas activas |
| Error de volumen | 0,52 % (V IFC 636,88 m³) |
| Inicio de obra | 2026-11-27 04:00 (America/Santiago) |
| Ventana | 336 h (14 días) |
| Paso | 3 600 s, 336 pasos |
| Forecast | 2026-11-11 00:00 → 2026-11-24 23:00 (336 h) |
| Reanalysis | 2025-11-27 00:00 → 2025-12-11 23:00 (360 h) |
| Cobertura | 0 h forecast + 337 h climatología |
| Aire | 8,0–20,6 °C |
| Viento | medio 2,57 m/s; máximo 7,06 m/s |
| $G_{max}$ | 1 081 W/m² |
| $h_{total}$ | 10,65–37,63 W/m²K |
| $T_{sa,max}$ | 47,96 °C |
| Suelo | $d=2,69$ m, amortiguación 0,69, atraso 517 h, $R=0,72$ m²K/W |
| Madera 19 mm | $R=0,1583$ m²K/W |
| EPS 50 mm | $R=1,4286$ m²K/W |
| `base` | 63,23 °C @ 55 h; ΔT 44,47 °C @ 192 h |
| `ambiente` | 63,98 °C @ 54 h; ΔT 42,06 °C @ 148 h |
| `sin_radiacion` | 63,21 °C @ 55 h; ΔT 43,62 °C @ 148 h |
| `aislado` | 63,98 °C @ 54 h; ΔT 34,72 °C @ 197 h |

---

## 5. Preguntas de seguimiento y trampas

**“¿Por qué no usaron la observación?”**
No hay estación propia en Pahuil y la observación no está disponible al momento de pronosticar. Sirve para validar después, no para forzar la corrida.

**“¿Por qué no usaron el reanalysis como forecast?”**
Porque el reanalysis usa observaciones posteriores: sería *data leakage*. Se usa solo como climatología declarada.

**“¿Por qué el viento no cambia la temperatura del aire?”**
Porque el viento no enfría el aire: aumenta el intercambio en la superficie. El aire lejos de la pared conserva su temperatura; lo que cambia es $h$.

**“¿Por qué el sol no aparece como fuente volumétrica?”**
Porque la radiación se absorbe en la superficie, no en el volumen. Entra por la frontera (sol-aire o flujo superficial), no como `fuente_W_m3`.

**“¿Por qué la aislación no baja la T máxima?”**
Porque el máximo ocurre a las 54 h, dominado por la hidratación y por la cara superior, que no está aislada. La aislación lateral reduce el gradiente y el enfriamiento posterior, no el pico.

**“¿Qué pasa si cambio el retiro de moldaje?”**
Puedo cambiarlo por vertida en el IFC (`RetiroMoldaje_h`) o en el YAML. No hay que remallar ni tocar el solver: cambia `formwork_end_flat`.

**“¿Qué pasa si el viento es muy alto?”**
Sube $h_{max}$ y baja el paso estable (`estimate_timestep`). La corrida sigue siendo estable; el costo computacional sube.

**“¿Cómo verifican que no hay doble conteo?”**
Dos pruebas: (1) con $G=0$ y sin onda larga, $T_{sa}=T_{aire}$; (2) el caso `sin_radiacion` apaga la radiación y la diferencia con `ambiente` es finita y del orden esperado (≈1 °C), no el doble.

**“¿Qué falta para E11/E12?”**
Calibrar hidratación, incorporar orientación/sombra por cara, validar contra observación y actualizar el forecast cuando cubra la obra.

---

## 6. Comandos de verificación rápida

```powershell
cd entregas/entrega10

# 1. Integridad de los snapshots (hashes)
python -c "import sys; sys.path.insert(0,'src'); from pathlib import Path; from mcplan import verify; print(verify(Path('datos/forecast')))"

# 2. Pruebas de E10
python -m pytest tests/test_e10_ambiente.py -q

# 3. Suite completa
python -m pytest tests -q
```

---

## 7. Límites que conviene declarar antes de que los pregunten

1. Todas las caras laterales ven el mismo $T_{sa}$: no hay orientación, sombra ni cara norte/sur.
2. El suelo es 1D y homogéneo; no hay estratigrafía ni flujo horizontal.
3. No hay evaporación, lluvia ni viento direccional.
4. La hidratación es provisoria; el objetivo de E10 es la cadena ambiente → frontera.
5. El forecast guardado no cubre la obra; la climatología es un relleno declarado, no una predicción.
