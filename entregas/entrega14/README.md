# E14 â€” Lab: Monte Carlo + HPC (Semana 5 / jueves)

**Fecha:** jueves 19 de noviembre, 10:30â€“12:30  
**Puntaje:** 4 puntos  
**Objetivo:** demostrar un workflow paralelo reproducible de Monte Carlo en el cluster.

## Evidencia (Canvas)

```text
Repositorio: https://github.com/jlobos-alt/MCOC-proyecto-2
Commit evaluado: b0233ce53259d8f083f87bb90cc709e1f224c0a5
Job ID representativo (Slurm, si aplica): <SLURM_ARRAY_JOB_ID> (ver results/e14/meta_ejemplo.json y slurm/e14_montecarlo_array.slurm)
```

## Resumen del workflow

El workflow implementa Monte Carlo paralelo y reproducible sobre el caso tÃ©rmico de E12/E13, con muestreo de incertidumbres, ejecuciÃ³n parametrizada por tramos, extracciÃ³n automÃ¡tica de mÃ©tricas, agregaciÃ³n y anÃ¡lisis de convergencia del estimador `P_f(N)`.

| Etapa | Artefacto | Entrada | Salida |
|---|---|---|---|
| Sampler / simulaciÃ³n por tramo | `scripts/e13_incertidumbre.py` | parÃ¡metros (`--conjunto`, `--desde`, `--hasta`, `--semilla`, `--dx`, `--n`) | `muestras_<C>_<desde>_<hasta>.csv` |
| EjecuciÃ³n HPC (array) | `slurm/e14_montecarlo_array.slurm` | variables de entorno / SBATCH | CSV por tramo + `meta_*.json` + logs |
| ExtracciÃ³n de mÃ©tricas | incluida en cada tramo | muestra simulada | `T_max`, `dT_max`, `t_T_max_h`, `t_dT_max_h` por fila |
| AgregaciÃ³n y convergencia | `scripts/e14_agregar.py` | carpeta con tramos o `muestras_A/B.csv` | `resumen_e14.json`, `convergencia_pf.csv`, `e14_convergencia_pf.png` |
| Metadata / reproducibilidad | Slurm + JSON | commit, semilla, Ã­ndices, host, fecha | `meta_*.json`, `resumen_e14.json` |

## Estructura

```text
entregas/entrega14/
  README.md
  slurm/
    e14_montecarlo_array.slurm      # job array Slurm parametrizado
  scripts/
    e13_incertidumbre.py            # sampler + simulaciÃ³n + mÃ©tricas (base E13, chunked)
    e14_agregar.py                  # agregaciÃ³n + P_f(N) + IC + figura
  results/
    e13/                            # muestras base A/B (N=2000) usadas como evidencia reproducible
    e14/
      resumen_e14.json              # resumen agregado, IC, CoV, metadatos
      convergencia_pf.csv           # curva P_f(N) por conjunto
      e14_convergencia_pf.png       # figura convergencia/IC
      meta_ejemplo.json             # ejemplo de metadata de tramo/job
  src/mcplan/incertidumbre.py       # modelo probabilÃ­stico, semillas por Ã­ndice, estimadores
  docs/E14_guion_demo.md            # guion corto para demo/oral
```

## Reproducibilidad y seeds

- **Semilla global:** `SEMILLA=20261118` (parametrizable).
- **Muestreo independiente por Ã­ndice:** cada muestra `i` se genera con `numpy.random.default_rng([semilla, i])` (ver `src/mcplan/incertidumbre.py`, funciÃ³n `muestrear`). Por lo tanto, el valor de la muestra `i` no depende del orden de ejecuciÃ³n, del nÃºmero de workers, ni del tramo Slurm que la procese.
- **Particionamiento:** el arreglo Slurm divide el total en tramos disjuntos `[desde, hasta)`; cada tramo produce un CSV independiente. La agregaciÃ³n solo concatena y ordena por `indice`.
- **Trazabilidad:** el script Slurm registra `job_id`, `array_task_id`, `host`, `date`, `git_commit`, `python`, parÃ¡metros y rangos en `meta_<C>_<desde>_<hasta>.json`. La agregaciÃ³n escribe metadatos en `resumen_e14.json`.
- **Determinismo:** mismos inputs + mismo commit + misma semilla + mismos Ã­ndices => mismas muestras y mÃ©tricas.

## CÃ³mo correr

### 1) Preparar entorno

Desde `entregas/entrega14`:

```bash
pip install -r requirements.txt
```

### 2) Ejecutar en HPC con Slurm (recomendado para E14)

Ajustar `#SBATCH --partition`, mÃ³dulos/venv y recursos en `slurm/e14_montecarlo_array.slurm`.

```bash
mkdir -p logs
sbatch --export=ALL,SEMILLA=20261118,N_TOTAL=2000,CHUNK=250,CONJUNTO=B,DX=0.5,SALIDA_BASE=results/e14/array_${RANDOM} slurm/e14_montecarlo_array.slurm
```

Inspeccionar jobs:

```bash
squeue -u $USER
sacct -j <JOB_ID> --format=JobID,State,Elapsed,MaxRSS,AllocCPUS
ls results/e14/array_<JOB_ID>/
cat logs/e14_<JOB_ID>_0.out
cat results/e14/array_<JOB_ID>/meta_B_0_250.json
```

### 3) Ejecutar un batch local (equivalente, sin Slurm)

```bash
# Ejemplo: 4 tramos de 50 muestras (conjunto B), total 200
python scripts/e13_incertidumbre.py --conjunto B --desde 0   --hasta 50  --n 200 --semilla 20261118 --dx 0.5 --procesos 4 --salida results/e14/local_B
python scripts/e13_incertidumbre.py --conjunto B --desde 50  --hasta 100 --n 200 --semilla 20261118 --dx 0.5 --procesos 4 --salida results/e14/local_B
python scripts/e13_incertidumbre.py --conjunto B --desde 100 --hasta 150 --n 200 --semilla 20261118 --dx 0.5 --procesos 4 --salida results/e14/local_B
python scripts/e13_incertidumbre.py --conjunto B --desde 150 --hasta 200 --n 200 --semilla 20261118 --dx 0.5 --procesos 4 --salida results/e14/local_B
```

### 4) Agregar resultados y generar P_f(N)

```bash
python scripts/e14_agregar.py --entrada results/e14/local_B --salida results/e14/local_B_agregado --conjuntos B --patron "muestras_B_*.csv"
```

Para usar la evidencia base ya calculada (N=2000 por conjunto A/B, derivada de E13 con el mismo sampler/semilla):

```bash
python scripts/e14_agregar.py --entrada results/e13 --salida results/e14 --conjuntos A B
```

## Inputs / Outputs

### Inputs principales

- GeometrÃ­a/caso: `geometry/foundation.ifc`, `datos/fundacion_e12.yaml`, snapshots de clima en `datos/forecast/`.
- ParÃ¡metros de ejecuciÃ³n: `semilla`, `n`, `conjunto` (A/B), `desde/hasta`, `dx`, `procesos`.
- Modelo probabilÃ­stico: `src/mcplan/incertidumbre.py` (15 variables, 11 aleatorias y 4 epistÃ©micas, dependencias por cÃ³pula gaussiana).

### Outputs principales

- Por tramo: `muestras_<C>_<desde>_<hasta>.csv`, `meta_<C>_<desde>_<hasta>.json`.
- Agregado: `convergencia_pf.csv`, `resumen_e14.json`, `e14_convergencia_pf.png`.
- MÃ©tricas por muestra: `T_max`, `t_T_max_h`, `dT_max`, `t_dT_max_h` y variables muestreadas.

## Convergencia del estimador

Se estima la probabilidad de falla por Monte Carlo:

```text
pÌ‚(N) = N_f(N) / N
SE(N) = sqrt(pÌ‚(1-pÌ‚)/N)
CoV(N) = sqrt((1-pÌ‚)/(NÂ·pÌ‚))
IC95%: Wilson
Si N_f = 0: p <= 1 - 0.05^(1/N) â‰ˆ 3/N  (95% confianza)
```

Estados lÃ­mite:
- `g_T = 70 - T_max <= 0` (falla por temperatura mÃ¡xima).
- `g_dT = 20 - Î”T_max <= 0` (falla por gradiente tÃ©rmico).

La figura `results/e14/e14_convergencia_pf.png` muestra `P_f(N)` e intervalos de confianza de Wilson para los conjuntos A y B. La curva se estabiliza a medida que crece N; la incertidumbre del estimador decrece como `1/sqrt(N)`.

## Independencia de realizaciones

Las realizaciones son independientes porque cada muestra `i` se construye desde un generador pseudoaleatorio inicializado con una clave Ãºnica `[semilla, i]`. No hay estado compartido entre muestras: el muestreo y la simulaciÃ³n de `i` no usan resultados de `j`. En Slurm, esto permite dividir el trabajo en arreglos de tareas (`array`) sin cambiar el resultado; cada tarea procesa un rango disjunto de Ã­ndices y la agregaciÃ³n solo une los CSV.

## Demo / explicaciÃ³n oral (guÃ­a rÃ¡pida)

1. Mostrar seeds y particiÃ³n: `SEMILLA`, `N_TOTAL`, `CHUNK`, `--desde/--hasta`.
2. Ejecutar un batch/tramo local o mostrar `sbatch`.
3. Inspeccionar un job: `squeue`, `sacct`, `logs/e14_*`, `meta_*.json`.
4. Explicar inputs/outputs: YAML/IFC/clima + parÃ¡metros -> CSV de mÃ©tricas + metadata.
5. Agregar resultados: `python scripts/e14_agregar.py ...`
6. Mostrar `P_f(N)`: `results/e14/e14_convergencia_pf.png` y `convergencia_pf.csv`.
7. Explicar independencia: `default_rng([semilla, i])`, sin estado compartido, tramos disjuntos.

Ver `docs/E14_guion_demo.md`.

## Limitaciones

- Las distribuciones son preliminares (orden de magnitud), no calibradas al proyecto; correlaciones por juicio experto.
- Curva C1 y clima usados en la base E12/E13: las probabilidades comparan y discuten el mÃ©todo, no aprueban el plan constructivo.
- Î”T se calcula en centros de celda (no a 25 mm exactos), lo que subestima el gradiente (sesgo de modelo declarado).
- El costo computacional por muestra depende de malla/dt; en HPC se escala por arreglo Slurm.
