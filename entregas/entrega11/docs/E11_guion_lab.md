# E11 — Guion del laboratorio

Abre una terminal en esta carpeta, con el entorno activo, y corre las pruebas antes de que llegue el ayudante:

```powershell
python -m pytest tests -q
python scripts/e11_clima_3d.py
```

## Frase de apertura

"Descargamos el clima de Open-Meteo y lo guardamos como snapshot que no se sobrescribe, con su hash. Esa serie se convierte en h(t) y T∞(t) de una condición de Robin, el solver corre y el resultado se exporta a VTK para verlo en ParaView o PyVista."

## Los 8 pedidos

El comando `python scripts/e11_clima_3d.py` muestra los pasos [1] a [8] en orden. Si piden ver uno en particular:

### 1. Mostrar el archivo meteorológico

Abre `datos/forecast/20261111T193622Z_open-meteo-forecast/normalizado.csv`.

**Qué decir:** "Es la serie horaria normalizada: temperatura a 2 m, humedad, viento a 10 m, radiación de onda corta, nubosidad y lluvia. Al lado está `raw.json`, la respuesta original de la API sin tocar."

### 2. Mostrar la metadata

Abre `metadata.json` de la misma carpeta, o mira el paso [2].

**Qué decir:** "Guarda fuente, modelo, endpoint, cuándo se emitió y descargó, coordenadas, zona horaria, horizonte y el SHA-256 del crudo y del CSV. Al cargarlo se recalcula el hash: si alguien cambió el archivo, falla. Un snapshot nuevo nunca pisa a uno anterior."

**Si preguntan por las coordenadas:** "Open-Meteo devuelve su celda de grilla más cercana al sitio, a unos 5 km. Guardamos las de esa celda y el sitio queda fijo en el código."

### 3. Graficar la temperatura ambiente

```powershell
python scripts/e11_clima_3d.py --solo-clima
```

Abre `results/e11/clima.png`. Arriba está la temperatura del snapshot completo; al medio, lo que entra a la frontera; abajo, h(t), viento y radiación.

### 4. Alimentar una BC con esa serie

La tabla del paso [4] muestra los valores que recibe el Robin en las caras laterales y superior:

```
−k·∂T/∂n = h(t) · (T − T∞(t))
```

La base no cambia: sigue con el suelo.

**Para mostrar solo la temperatura**, sin viento ni sol:

```powershell
python scripts/e11_clima_3d.py --frontera temperatura
```

Ahí T∞ es igual a la temperatura del CSV en cada hora y h = 5,7 W/(m²·K). Hay una prueba que compara T∞ con el archivo, fila por fila.

### 5. Ejecutar una simulación corta

El paso [5] simula 72 h con malla de 0,5 m en unos segundos. Con `--duracion-h 24` es aún más corta.

### 6. Abrir resultados 3D

**PyVista:**

```powershell
python scripts/e11_clima_3d.py --visor
```

Teclas: `1` a `5` para las vertidas, `x` para cortar, `n` para el núcleo, `m` para la superficie y la barra para el tiempo.

**ParaView:** abre `results/e11/vti/serie.pvd` y aprieta *Apply*. Colorea por `temperature`. Con el botón de reproducción avanza en el tiempo.

### 7. Slice o clipping

- **PyVista:** tecla `x` para la mitad cortada en y = 0. La imagen `cortes_3d.png` tiene 3 cortes ortogonales.
- **ParaView:** filtro *Slice* (plano normal a y, origen 0,0,0) o *Clip* (lo mismo, pero deja la mitad 3D).

**Qué decir:** "El corte muestra el núcleo más caliente y cómo se enfría hacia las caras."

### 8. Identificar núcleo y superficie

- **PyVista:** teclas `n` y `m`. El núcleo se pinta azul y la superficie verde; lo demás queda transparente.
- **ParaView:** filtro *Threshold* sobre `nucleo` entre 1 y 1, y otro sobre `superficie`.
- **Paso [8]:** dice cuántas celdas tiene cada zona y dónde está la más caliente del núcleo y la más fría de la superficie.

**Qué decir:** "El núcleo es el hormigón a 2 celdas o más de cualquier cara exterior. La superficie son las celdas con una cara expuesta que queda así al final, sin contar la base sobre el suelo. ΔT es la T máxima del núcleo menos la T mínima de la superficie en el mismo instante."

## Dónde entran el viento y la radiación

La pauta pide señalar la ecuación exacta. Están en `src/mcplan/environment.py`:

| Qué | Ecuación | Línea |
|---|---|---|
| Viento → convección | h_conv = 5,7 + 3,8·v | 34 (`wind_convection_coefficient`) |
| Radiación de onda larga linealizada | h_r = 4·ε·σ·T³ | 43 (`radiative_coefficient`) |
| Temperatura de cielo | T_cielo = T_aire − 12·(1 − 0,75·N^3,4) | 53 (`sky_temperature`) |
| Flujo solar absorbido | q_solar = α·G, con α = 0,6 | 72 |
| Temperatura sol-aire | T_sa = T_aire + [α·G + ε·σ·(T_cielo⁴ − T_aire⁴)] / h | 78 (`sol_air_temperature`) |
| h total que ve el Robin | h = h_conv + h_r | 167–170 (`condiciones_de_timeline`) |
| Se asignan a las caras | `h_series` y `far_field_series` | 212–213 (`aplicar_ambiente`) |

En el solver: `boundary.py`, línea 98, evalúa h(t) en cada paso, y `thermal.py`, línea 708, calcula el flujo `G·(T∞ − T)` de cada cara.

**Para no contar dos veces la radiación:** entra solo dentro de T sol-aire y de h. No se suma además como flujo aparte.

## Preguntas probables

**¿Por qué T∞ llega a 40 °C si el aire está a 20 °C?** "Es la temperatura sol-aire: la temperatura ficticia que daría el mismo flujo que el sol más el aire. De noche baja de la del aire, porque la superficie pierde calor hacia el cielo."

**¿Qué pasa con los días que el forecast no cubre?** "El forecast llega al 24 de noviembre y la obra parte el 27. Esas horas se completan con el archivo histórico del mismo calendario del año pasado, y cada hora queda marcada como forecast o climatología. Con `--clima-desde obra` se ve: 73 horas de climatología."

**¿Por qué ΔT es menor que en la E09?** "Porque son solo 72 h; el máximo de la obra ocurre más tarde. Además, la malla de 0,5 m mide la superficie más adentro."

## Si algo falla

| Problema | Qué hacer |
|---|---|
| `Snapshots alterados` | Git cambió el fin de línea: `git rm -r --cached -q datos/forecast` y `git checkout -- datos/forecast` |
| La ventana 3D no abre | Mostrar `vista_3d.png`, `cortes_3d.png` y `nucleo_superficie.png` |
| ParaView no carga la serie | Abrir un `.vti` suelto de `results/e11/vti/` |
