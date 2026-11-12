# E11 — Lab: weather pipeline y visualización 3D (3 puntos)

**Objetivo:** conectar datos meteorológicos reales con las condiciones de borde y producir resultados 3D inspeccionables.

**Canvas:** solo `Repositorio` y `Commit evaluado`, sin informe.

Carpeta autocontenida. Guion del laboratorio: [docs/E11_guion_lab.md](docs/E11_guion_lab.md).

## Preparar

```powershell
pip install -r requirements.txt
python -m pytest tests -q                  # 146 pruebas (~1-4 min)
python scripts/e11_clima_3d.py             # los 8 pasos del laboratorio (~10 s)
```

## Un solo comando para los 8 pedidos

`python scripts/e11_clima_3d.py` imprime cada paso numerado y deja las figuras en `results/e11/`.

| Pedido | Paso | Evidencia |
|---|---|---|
| Mostrar el archivo meteorológico | [1] | `datos/forecast/<snapshot>/normalizado.csv`, `raw.json` |
| Mostrar la metadata | [2] | `metadata.json`: fuente, emisión, coordenadas, horizonte y SHA-256 verificados |
| Graficar la temperatura ambiente | [3] | `results/e11/clima.png` (también viento, radiación, h y T sol-aire) |
| Alimentar una BC con esa serie | [4] | Tabla de h(t) y T∞(t) que recibe el Robin |
| Ejecutar una simulación corta | [5] | 72 h, malla de 0,5 m |
| Abrir resultados 3D | [6] | `results/e11/vti/serie.pvd` (ParaView) y `--visor` (PyVista) |
| Slice o clipping | [7] | `cortes_3d.png` (3 cortes ortogonales) y `vista_3d.png` (mitad cortada) |
| Identificar núcleo y superficie | [8] | `nucleo_superficie.png`, campos `nucleo` y `superficie` en los `.vti` |

| Rúbrica | Pts | Dónde |
|---|---|---|
| Weather pipeline trazable | 0,8 | Snapshots inmutables con SHA-256 (`src/mcplan/snapshots.py`); pasos [1]–[3]; `corrida.json` registra el snapshot usado |
| Integración con condiciones de borde | 0,8 | `src/mcplan/environment.py` → `aplicar_ambiente`; paso [4]; prueba `test_la_frontera_recibe_la_temperatura_del_archivo` |
| Visualización PyVista/ParaView | 0,7 | `src/mcplan/visualization.py`; pasos [6]–[8] |
| Demo y explicación | 0,7 | [Guion](docs/E11_guion_lab.md) |

## Opciones para la demo

| Qué | Comando |
|---|---|
| Solo el clima, sin simular | `python scripts/e11_clima_3d.py --solo-clima` |
| Robin solo con la temperatura del aire | `python scripts/e11_clima_3d.py --frontera temperatura` |
| Clima de la fecha de obra (27-nov, climatología) | `python scripts/e11_clima_3d.py --clima-desde obra` |
| Abrir la ventana 3D al final | `python scripts/e11_clima_3d.py --visor` |
| Imágenes en otro instante | `python scripts/e11_clima_3d.py --t 24` |

## Resultados (malla de 0,5 m, 72 h, parámetros provisorios)

| Caso | Clima | T máx | ΔT máx |
|---|---|---|---|
| Frontera completa | Forecast del 11-nov, con viento y sol | 63,94 °C a las 54 h | 27,40 °C a las 33 h |
| Solo temperatura | Mismo forecast, h = 5,7 | 63,38 °C a las 55 h | 26,33 °C a las 72 h |
| Fecha de obra | Climatología del archivo | 63,98 °C a las 54 h | 31,78 °C a las 72 h |

Son 72 h, no 14 días: el ΔT máximo de la obra ocurre después. La hidratación sigue siendo provisoria.

## Limitaciones

- El forecast del 11-nov termina el 24-nov y la obra parte el 27-nov: con `--clima-desde obra` el clima es climatología, y se declara hora a hora.
- Open-Meteo entrega la celda de su grilla más cercana al sitio, unos 5 km al noreste: la metadata guarda las coordenadas de esa celda.
- Núcleo y superficie se definen sobre la geometría final y se dibujan aunque una vertida aún no esté colocada.
- La superficie usa centros de celda; con la malla de 0,5 m quedan a 25 cm de la cara, no a 25 mm.

## Evidencia / entrega (Canvas)

```
Repositorio: https://github.com/jlobos-alt/MCOC-proyecto-2
Commit evaluado: (el SHA declarado en Canvas)
```
