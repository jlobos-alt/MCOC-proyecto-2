#!/bin/bash
#SBATCH --job-name=e14-mc
#SBATCH --output=logs/e14_%A_%a.out
#SBATCH --error=logs/e14_%A_%a.err
#SBATCH --array=0-7                 # 8 tramos => 8*250 = 2000 muestras (ajustar con N y CHUNK)
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=02:00:00
# #SBATCH --partition=general      # descomentar/ajustar según cluster
# #SBATCH --mail-type=END,FAIL

# E14 - Monte Carlo paralelo reproducible (Slurm array)
# Cada tarea del arreglo ejecuta un tramo independiente de muestras.
# Reproducibilidad: la muestra i usa RNG default_rng([SEMILLA, i]) en el código,
# por lo que el resultado de i no depende del orden de ejecución ni del worker.

set -euo pipefail

# --- Parámetros (sobrescribibles por entorno) ---
SEMILLA="${SEMILLA:-20261118}"
N_TOTAL="${N_TOTAL:-2000}"
CHUNK="${CHUNK:-250}"
CONJUNTO="${CONJUNTO:-B}"          # A: solo aleatorias | B: aleatorias+epistémicas
DX="${DX:-0.5}"
SALIDA_BASE="${SALIDA_BASE:-results/e14/array_${SLURM_ARRAY_JOB_ID:-local}}"
PYTHON="${PYTHON:-python}"

# --- Entorno ---
# module load python/3.11            # ajustar al cluster
# source ~/venvs/mcoc/bin/activate   # ajustar al cluster

mkdir -p "$SALIDA_BASE" logs

DESDE=$(( SLURM_ARRAY_TASK_ID * CHUNK ))
HASTA=$(( DESDE + CHUNK ))
if [ "$HASTA" -gt "$N_TOTAL" ]; then HASTA="$N_TOTAL"; fi
if [ "$DESDE" -ge "$N_TOTAL" ]; then echo "Tramo fuera de rango"; exit 0; fi

echo "=== E14 Monte Carlo chunk ==="
echo "job_id=${SLURM_ARRAY_JOB_ID:-NA} task_id=${SLURM_ARRAY_TASK_ID:-NA}"
echo "host=$(hostname) date=$(date -Is)"
echo "semilla=$SEMILLA conjunto=$CONJUNTO desde=$DESDE hasta=$HASTA n_total=$N_TOTAL dx=$DX"
echo "git_commit=$(git rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
echo "python=$($PYTHON --version 2>&1)"

# Ejecución parametrizada del tramo (sampler + simulación + extracción de métricas)
$PYTHON scripts/e13_incertidumbre.py \
  --conjunto "$CONJUNTO" \
  --desde "$DESDE" \
  --hasta "$HASTA" \
  --n "$N_TOTAL" \
  --semilla "$SEMILLA" \
  --dx "$DX" \
  --procesos "${SLURM_CPUS_PER_TASK:-1}" \
  --salida "$SALIDA_BASE"

# Metadata por tramo (trazabilidad/reproducibilidad)
cat > "$SALIDA_BASE/meta_${CONJUNTO}_${DESDE}_${HASTA}.json" <<META
{
  "job_id": "${SLURM_ARRAY_JOB_ID:-NA}",
  "array_task_id": "${SLURM_ARRAY_TASK_ID:-NA}",
  "host": "$(hostname)",
  "date": "$(date -Is)",
  "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo UNKNOWN)",
  "python": "$($PYTHON --version 2>&1)",
  "semilla": $SEMILLA,
  "n_total": $N_TOTAL,
  "conjunto": "$CONJUNTO",
  "desde": $DESDE,
  "hasta": $HASTA,
  "dx_m": $DX,
  "cpus_per_task": ${SLURM_CPUS_PER_TASK:-1},
  "salida": "$SALIDA_BASE"
}
META

echo "=== chunk listo: $SALIDA_BASE/muestras_${CONJUNTO}_${DESDE}_${HASTA}.csv ==="
