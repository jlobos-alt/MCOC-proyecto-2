# E14 — Guion corto para demo / explicación oral

## 1. Objetivo (10 s)
"Demostramos un workflow Monte Carlo paralelo y reproducible en HPC: muestreamos incertidumbres, ejecutamos tramos independientes en Slurm, extraemos métricas, agregamos resultados y verificamos convergencia de P_f(N)."

## 2. Mostrar seeds y partición
- Semilla global: `SEMILLA=20261118`.
- Cada muestra `i` usa `default_rng([semilla, i])` (determinista por índice).
- Total `N_TOTAL=2000`, `CHUNK=250`, arreglo `0-7` (8 tareas). Cada tarea procesa `[desde,hasta)`.

Comando/archivo: `slurm/e14_montecarlo_array.slurm` (variables `SEMILLA,N_TOTAL,CHUNK,CONJUNTO,DX`).

## 3. Ejecutar un batch
- HPC: `sbatch --export=ALL,... slurm/e14_montecarlo_array.slurm`
- Local equivalente: ejecutar varios `python scripts/e13_incertidumbre.py --conjunto B --desde ... --hasta ... --salida ...`

Salida por tramo: `muestras_B_0_250.csv` y `meta_B_0_250.json`.

## 4. Inspeccionar un job
- `squeue -u $USER`
- `sacct -j <JOB_ID> --format=JobID,State,Elapsed,MaxRSS,AllocCPUS`
- Revisar `logs/e14_<JOB_ID>_<TASK>.out` y `meta_*.json` (job_id, task, host, git_commit, semilla, rango).

## 5. Inputs / outputs
- **Inputs:** geometría IFC, YAML del caso, snapshots de clima, modelo de incertidumbre (`src/mcplan/incertidumbre.py`), parámetros de ejecución.
- **Outputs por muestra:** `T_max`, `t_T_max_h`, `dT_max`, `t_dT_max_h` + variables muestreadas.
- **Outputs agregados:** `convergencia_pf.csv`, `resumen_e14.json`, `e14_convergencia_pf.png`.

## 6. Agregar resultados
```bash
python scripts/e14_agregar.py --entrada results/e14/array_<JOB_ID> --salida results/e14/agregado --conjuntos B --patron "muestras_B_*.csv"
```

## 7. Mostrar P_f(N) y convergencia
- Figura: `results/e14/e14_convergencia_pf.png`.
- CSV: `results/e14/convergencia_pf.csv`.
- Estimador: `p̂(N)=N_f/N`, IC95 Wilson, CoV `sqrt((1-p)/(N*p))`, convergencia ~`1/sqrt(N)`.
- Caso 0 fallas: no demuestra `p=0`; cota `p <= 1-0.05^(1/N) ≈ 3/N`.

## 8. Por qué las realizaciones son independientes
Cada muestra `i` se genera con `default_rng([semilla, i])` y se simula sin depender de otras muestras. Por eso los tramos del arreglo Slurm son embarazosamente paralelos: no hay comunicación MPI ni estado compartido; la agregación es una reducción posterior (concatenar métricas y recalcular el estimador).
