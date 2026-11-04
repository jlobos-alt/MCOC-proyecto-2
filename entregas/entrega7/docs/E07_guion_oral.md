# E07 — Guion oral: voxelización, vertidas e hidratación

Cadena completa: `geometry/foundation.ifc` → `bim.extraer_solidos` → `voxel.voxelizar` →
`plan.plan_desde_solidos` → `thermal.build_model` → `thermal.solve`.

## Demo de 2 minutos

```powershell
python scripts/voxelizar_ifc.py            # volumen y área al refinar + cortes por vertida
python scripts/curva_hidratacion.py        # curva adiabática, Q̇h y madurez
python scripts/simular_fundacion_ifc.py    # fundación completa, vertida por vertida (~10 s)
python -m pytest tests -q                  # 99 pruebas (~1 min)
```

Figuras en `results/e07/`: `voxeles_cortes.png`, `volumen_vs_dx.png`, `hidratacion.png`,
`activacion_cortes.png`, `series_fundacion.png`.

## Las 9 preguntas

### 1. ¿Cómo decide el código si un voxel pertenece al sólido?

**Regla:** la celda es del sólido si **su centro** está dentro. Para saberlo se lanza un rayo vertical
desde el centro hacia abajo y se cuentan los triángulos que cruza: **impar es dentro, par es fuera**.

Código: `voxel.py`, `centros_dentro`. No se prueba celda por celda: cada triángulo se proyecta en
planta, se calcula a qué altura lo cruza cada columna y una suma acumulada en z da los cruces bajo
cada centro.

Dos detalles que conviene saber:
- Los rayos se corren 10⁻⁷ m para no pasar justo por una arista entre dos triángulos, donde el cruce
  se contaría dos veces.
- Si una columna cruza un número impar de veces, la malla está abierta y el código lanza un error.

Comprobación: en una pirámide, el resultado coincide celda por celda con la fórmula analítica.

### 2. ¿Qué error produce la frontera staircase?

Dos errores distintos, y conviene separarlos:

- **Volumen: es pequeño y baja al refinar.** El exceso de unas celdas compensa la falta de otras.
- **Área expuesta: no baja al refinar.** Una cara inclinada se vuelve escalera, y una escalera mide lo
  mismo sin importar el tamaño de los peldaños: una pendiente de 45° mide √2 veces más, con cualquier Δx.

| Δx [m] | A escalera [m²] | A real [m²] | Razón |
|---|---|---|---|
| 0,5 | 760,0 | 642,0 | 1,18 |
| 0,25 | 748,5 | 642,0 | 1,17 |
| 0,125 | 750,9 | 642,0 | 1,17 |
| 0,0625 | 754,0 | 642,0 | 1,17 |

**Consecuencia:** las caras inclinadas tienen cerca de 17 % más área por la que perder calor, y refinar
no lo arregla. Es una limitación conocida del baseline; las fracciones de volumen o cut cells de la
guía G04 son el camino para corregirla y son opcionales.

### 3. ¿Cómo cambia el error de volumen con Δx?

Definición: `V_h = N_activo · Δx · Δy · Δz` y `e_V = |V_h − V_geom| / V_geom`. V_geom = 636,88 m³.

| Δx [m] | Celdas | V_h [m³] | e_V total | Peor vertida |
|---|---|---|---|---|
| 1,0 | 608 | 608,00 | 4,53 % | 100 % (vertida 2) |
| 0,5 | 5 140 | 642,50 | 0,88 % | 37,8 % |
| 0,25 | 40 536 | 633,38 | 0,55 % | 16,0 % |
| 0,125 | 324 508 | 633,80 | 0,48 % | 13,3 % |
| 0,0625 | 2 610 064 | 637,22 | 0,05 % | 3,9 % |

Baja al refinar, pero **sin una pendiente limpia** (ajuste p ≈ 1,4): por las compensaciones, puede
estancarse entre dos Δx.

**El hallazgo importante: el total engaña.** Con Δx = 0,125 m el total es 0,48 %, pero la vertida 2
tiene 13 % de error. Las interfaces (0,55, 1,10, 2,20 y 3,30 m) caen dentro de las celdas, y cada celda
se va entera a una vertida. Con Δx = 1 m, la vertida 2 ni siquiera tiene celdas y `build_model` lo avisa.

**Lo que hicimos:** `dz_que_calza` elige un Δz cuyas caras coinciden con esas interfaces.

| Malla | e_V vertidas 1 a 4 | e_V vertida 5 | T máx | Instante |
|---|---|---|---|---|
| Δx = Δz = 0,25 | hasta 16,0 % | 0,1 % | 62,20 °C | 81 h |
| Δx = Δz = 0,125 | hasta 13,3 % | 0,4 % | 61,39 °C | 79 h |
| Δx = 0,25, Δz = 0,275 | hasta 0,8 % | 10,1 % | 61,47 °C | 105 h |
| Δx = 0,125, Δz = 0,1375 | hasta 0,3 % | 3,4 % | 61,47 °C | 104 h |

Con Δz calzado, T máx ya no cambia entre las dos mallas y el peak se mantiene en 104–105 h. Sin calzar,
el peak parecía ocurrir casi un día antes solo por error de malla. La vertida 5 queda con más error
porque su cara superior (4,30 m) no calza con ese Δz.

### 4. ¿Cómo identifica una superficie exterior?

Una cara de una celda activa es exterior si **al otro lado no hay hormigón**: borde de la grilla o celda
vacía. Hay dos conjuntos en `thermal.py`:

- **Caras expuestas (`_build_faces`):** intercambian calor con el aire. Incluyen las **transitorias**,
  la cara superior de una vertida mientras espera a la siguiente.
- **Superficie de control para ΔT (`_definir_conjuntos_de_control`):** solo las **permanentes**,
  sin contar la base. Una cara que después quedará tapada no es la superficie final de la obra.

El grupo de frontera sale de la orientación: lateral (x, y) es `perimetro`, hacia arriba es `superficie`
y hacia abajo es `base`.

**Corrección importante:** antes, una cara hacia una celda vacía quedaba aislada. La misma caja de 2 m
daba 24,7 °C llenando la grilla y 39,0 °C con celdas vacías al lado. En cajas nunca se notaba; en un
octágono, las paredes no habrían perdido calor. Ahora hay dos pruebas para esto.

### 5. ¿Qué ocurre en una interfaz entre dos vertidas?

Depende del tiempo:

- **Antes de que llegue la de arriba:** la cara de la vertida inferior está expuesta al aire.
- **Desde que llega:** deja de estar expuesta y empieza a conducir, con `G = k·A/d`. Si los materiales
  difieren, k es la media armónica.

No hay salto de calor artificial: lo que sale de una celda entra a la otra. La prueba adiabática lo
confirma: dos vertidas a 10 y 30 °C terminan en 20 °C exactos.

**Supuesto:** contacto perfecto, sin resistencia térmica en la junta.

Si el centro de una celda cae justo en la interfaz, pertenece a la vertida de arriba, porque el intervalo
es semiabierto [z_abajo, z_arriba). Así ninguna celda queda en dos vertidas ni en ninguna.

### 6. ¿Cómo se inicializa una vertida nueva?

Antes de su hora, sus celdas **no existen** para el solver: T = NaN, sin capacidad activa, sin conducción
y sin fuente. Al llegar `inicio_h`:

- T = T de colocación (del IFC);
- edad = 0, así que hidrata desde su propia hora;
- sus caras se incorporan a la conducción o a la exposición.

Los datos salen del Pset del IFC. `InicioPlanificado` es una fecha y se convierte en horas desde la
primera vertida: 0, 24, 48, 72 y 96 h.

**Corrección:** `read_ifc_vertidas` buscaba `Inicio_h`, que no existe en el IFC, y dejaba las 5 vertidas
partiendo a la vez, sin avisar.

La figura `activacion_cortes.png` lo muestra: gris es que aún no hay hormigón.

### 7. ¿Qué unidades tiene Q̇h?

**W/m³**, porque es una fuente volumétrica. En el balance de la celda se multiplica por el volumen para
dar W. No confundir con la convección, que es W/m² y va en el borde.

### 8. ¿Cómo se relaciona una curva adiabática con generación volumétrica de calor?

En una celda sin pérdidas, toda la energía generada calienta el material: `ρ·cp·dT/dt = Q̇h`. Como
T = T₀ + θ(t), resulta **Q̇h = ρ·cp·dθ/dt**.

Con θ∞ = 45 °C y τ = 30 h: Q̇h(0) = 2,328·10⁶ · (45/30) / 3600 = **970 W/m³**. Energía total:
ρ·cp·θ∞ = **104,8 MJ/m³**. Las dos relaciones están probadas.

### 9. ¿Cómo influye la temperatura en la hidratación?

Con madurez de Arrhenius, `m(T) = exp(−(Ea/R)(1/T − 1/T_ref))`: el hormigón caliente envejece más rápido.
A 50 °C corre 3,55 veces más rápido que a 20 °C. **El calor total no cambia; cambia cuándo se libera.**

| T colocación | Subida a las 24 h | Subida a las 300 h | Q̇h máx |
|---|---|---|---|
| 5 °C | 21,8 °C | 45,0 °C | 682 W/m³ |
| 18 °C | 38,2 °C | 45,0 °C | 1187 W/m³ |
| 30 °C | 44,4 °C | 45,0 °C | 1914 W/m³ |

También hay un ciclo: más calor sube T, lo que acelera la reacción. En la fundación, con madurez T máx da
61,47 °C a las 105 h, y sin ella 59,09 °C a las 200 h.

**Dos correcciones que conviene poder explicar:** el código dividía por R un valor que ya era Ea/R (daba
1,16 en vez de 3,55), y no multiplicaba por m(T) en el solver, así que se perdía calor.

## Si preguntan por los resultados

La fundación da T máx 61,5 °C (cumple) y ΔT 45,2 °C (no cumple). **No se pueden usar como conclusión
todavía:** hidratación sin calibrar, clima genérico y las limitaciones de abajo.

## Limitaciones que hay que decir antes de que las pregunten

1. **Parámetros provisorios:** θ∞, τ, Ea/R y clima.
2. **Área en escalera:** cerca de 17 % de más en las caras inclinadas, no converge al refinar.
3. **ΔT no se mide a 25 mm:** la superficie de control usa centros de celda, a Δx/2 de la cara (12,5 cm con
   Δx = 0,25 m). Por eso ΔT sigue creciendo al refinar (43,2, 44,7 y 46,1 °C con Δx = 0,5, 0,25 y 0,125 m).
4. **Moldaje común:** una sola capa en todas las caras laterales entre 0 y 72 h, no por vertida. La vertida 5
   entra a las 96 h sin moldaje. `Moldaje` y `Aislacion` del IFC se leen, pero aún no se aplican (E10).
5. **Suelo:** condición efectiva en la base, no modelado explícitamente.
6. **Verificado, no validado:** falta comparar con el caso medido de Ju & Lei (E09).
