# CLAUDE.md — MCOC Proyecto 2 (Hormigón masivo) · Grupo 5

Contexto para Claude Code. Léelo completo antes de trabajar en este repo.

## Quiénes y cómo trabajar

- Curso: *Design by Simulation in Civil Engineering* (MCOC), capstone de hormigón masivo.
- Grupo 5: José Lobos (dueño del repo, `jlobos-alt`), Clemente Sánchez (`cjsanchez12`), Matías Campos.
- Responder **en español**. Los integrantes son estudiantes: cada entrega tiene **revisión oral
  individual**, así que el código debe ser explicable y conviene acompañar los cambios con una
  explicación breve de la física y la numérica (qué decir y por qué funciona).
- Preferir soluciones simples y verificables antes que sofisticadas. Todo resultado debe ser
  reproducible con un comando.

## El problema

Fundación de aerogenerador (geometría docente inspirada en Ju & Lei 2019): planta octagonal de
18 m entre caras, espesor 3,30 m, pedestal cilíndrico Ø 7 m. Se hormigona en vertidas. El
producto final es un **plan de vertidas defendible** (número, secuencia, hora, intervalo,
temperatura de colocación, moldaje/aislación, retiro), no una simulación.

- Criterios: **T_max ≤ 70 °C** y **ΔT ≤ 20 °C**. ΔT = T_max del hormigón − T en puntos ~25 mm bajo
  las superficies exteriores; máximo en el tiempo durante **14 días** desde la primera vertida.
- Sitio (Grupo 5): Pahuil / Chanco, Maule. Coordenadas **-35.644721, -72.568332** (usar en todo
  script de clima). Estación DMC de contraste: Dunas de Chanco (id 350040).
- Referencia de validación: Ju & Lei, sin control térmico → ~73 °C en el núcleo hacia el día 4 y
  ΔT ≈ 35 °C.
- Propiedades de referencia (Ju & Lei): hormigón k = 2,22 W/(m·K), cp = 970 J/(kg·K),
  ρ = 2400 kg/m³ (α ≈ 9,5·10⁻⁷ m²/s); suelo k = 1,39, cp = 1273, ρ = 1800.

## Reglas del curso (no romper)

- El solver lo escribe el equipo: grilla cartesiana con **balance por celda** (FD/FV). No usar
  Kratos, ANSYS, OpenSees ni otro solver como núcleo.
- Arquitectura: **Bonsai/Blender → IFC → IfcOpenShell → geometría + propiedades → voxelización →
  solver**. El solver **no depende de Blender** (BIM ≠ solver ≠ visualizador). La fuente de verdad
  del BIM es el `.ifc`, no el `.blend`.
- Cada vertida en el IFC debe tener (Pset): VertidaID, TipoHormigon, InicioPlanificado,
  TemperaturaColocacion_C, Moldaje, Aislacion, RetiroMoldaje_h. Usamos `Pset_HormigonMasivo`.
- Clima: guardar **snapshots** de pronóstico (fuente, modelo, fecha/hora de descarga, coordenadas,
  unidades, horizonte, variables) y **nunca sobrescribir** uno anterior. Explicar cómo se completa
  el horizonte faltante de 14 días.
- Incertidumbre: no justificar todo con normales arbitrarias; separar material, ejecución, clima.
  Reportar incertidumbre estadística de las estimaciones. Monte Carlo debe poder correr en HPC
  (Slurm arrays/batching).
- Visualización 3D con PyVista/VTK/ParaView; Matplotlib para curvas, convergencia, histogramas.
- **Regla del commit**: cada entrega se evalúa sobre el SHA declarado en Canvas
  (`Repositorio` + `Commit evaluado`). Antes de declarar un SHA: `git pull`, tests en verde, push.

## Estructura del repo

```text
src/mcplan/            paquete principal (raíz = versión vigente)
  thermal1d.py         solver 1D FTCS nodal (media celda en bordes): Material, BC.dirichlet/
                       neumann/adiabatic/robin, stable_dt_1d, solve_1d (rechaza dt inestable)
  bim.py               lee vertidas del IFC (IfcOpenShell si está; si no, lector STEP propio)
  thermal.py, grid.py  solver 3D por balance de celdas (centrado en celdas), build_model/solve
  boundary.py          capas en serie: convección, moldaje, aislación, retiro en el tiempo
  hydration.py         θ_ad(t) → q_h = ρ cp dθ/dt (exponencial, provisorio)
  plan.py, criteria.py plan declarativo YAML (datos/caso_fundacion.yaml) y chequeo 70/20 °C
  reliability.py, weather.py   Monte Carlo y series de clima (esqueleto)
geometry/              foundation.ifc (guardado con Bonsai), foundation_base.ifc (semilla),
                       course_geometry.json, make_foundation_ifc.py, bonsai_open_and_save.py
scripts/               inspect_ifc.py, run_1d_demo.py, run_case.py
tests/                 tests de la raíz (unittest/pytest)
entregas/entregaN/     carpeta AUTOCONTENIDA por entrega (convención de José): copia de src,
                       scripts, tests, resultados y README con el mapeo a la rúbrica
docs/                  guías del curso G00–G08 (docs/guias), respuestas y guiones orales
calendario/            calendario E00–E15
datos/, validacion/    plan YAML y resultados del caso 3D
```

Convención: el código evoluciona en `src/mcplan` (raíz). Para cada entrega se crea
`entregas/entregaN/` autocontenida con lo necesario para la demo; si se arregla algo ahí, llevarlo
también a la raíz (y viceversa) para que no diverjan.

Utilidades de E02 que solo existen en `entregas/entrega2/`: `src/mcplan/ifc_diff.py` (foto del IFC
y comparación antes/después sin IfcOpenShell) y `scripts/roundtrip_ifc.py --antes/--despues`.

## Física y numérica (convenciones)

- Unidades SI; temperaturas en °C; fuente volumétrica en W/m³; flujos de borde en W/m².
- Balance por celda: `C_i dT_i/dt = Σ G_ij (T_j − T_i) + q_i V_i + Q_b,i`, `C = ρ cp V`,
  `G = k A / d`. Interfaces entre materiales: k de cara con **media armónica**.
- Robin como resistencias en serie: `R = (Δx/2)/(kA) + R_moldaje + R_aislación + 1/(hA)`.
  Retirar moldaje = cambiar R en el tiempo.
- Neumann: `-k ∂T/∂n = q_n` con n hacia afuera (q_n > 0 sale calor; 0 = adiabático).
- Estabilidad explícita: `Δt ≤ C_i/(Σ G_ij + G_b)`; en grilla uniforme Fo ≤ 1/2, 1/4, 1/6 en
  1D/2D/3D. Un borde Robin con h alto reduce el Δt admisible.
- Verificación mínima esperada: solución exacta (seno) y orden de convergencia, conservación de
  energía adiabática, fuente uniforme → subida lineal, flujo Neumann, Robin analítico, Fo > límite
  diverge. Verificación ≠ validación.

## Estado de entregas

| Entrega | Fecha | Estado | SHA declarado / referencia |
|---|---|---|---|
| E00 Kickoff | 15 oct | hecho | `f222414` |
| E01 Revisión oral BIM + difusión + 1D | 21 oct | hecho | `0d70e29` |
| E02 Lab round-trip IFC + demo 1D | 22 oct | hecho | `adf0e1c` |
| E03 Verificación 1D | 23 oct | hecho (José) | `513eb4e` |
| E04 Revisión oral 2D/3D + CC | 28 oct | hecho (José) | `25b992f` |
| E05 Lab batería de verificación térmica | 29 oct | pendiente | — |
| E06 Dossier de verificación + BIM del caso | 30 oct | pendiente | — |
| E07–E09 Voxelización, vertidas, hidratación, baseline 3D | 4–6 nov | pendiente | — |
| E10–E12 Entorno, moldaje, clima, simulación 14 días | 11–13 nov | pendiente | — |
| E13–E15 Incertidumbre, Monte Carlo + HPC, recomendación | 18–20 nov | pendiente | — |

Detalle de cada entrega en `calendario/calendario.md` y en `entregas/entregaN/README.md`.

## Entorno (PC de Clemente)

- Windows 11, PowerShell, VS Code. Python del sistema 3.14 (`python`), con numpy, matplotlib,
  pytest y pyyaml. **IfcOpenShell no está en el Python del sistema** (los tests IFC tienen lector
  STEP de respaldo); sí viene con Bonsai dentro de Blender.
- Blender 5.2 + Bonsai 0.9 (extensión `bl_ext.blender_org.bonsai`). Para abrir un IFC:
  File → Open IFC Project. Propiedades: pestaña Object Information → Property Sets.
- La carpeta del proyecto aparece con dos rutas equivalentes (`...\semestre 26-2\MCOC\...` y
  `...\semestre_actual\MCOC\...`); son la misma carpeta.
- Git: los archivos pueden aparecer modificados solo por fin de línea (CRLF). No commitear ese
  ruido: revisar `git diff --ignore-cr-at-eol` antes de `git add`.

## Comandos habituales

```powershell
pip install -r requirements.txt
python -m pytest tests -q                       # tests de la raíz
python scripts\inspect_ifc.py                   # vertidas, GUID y Pset
python scripts\run_1d_demo.py                   # demo 1D con hidratación
python scripts\run_case.py --plan datos\caso_fundacion.yaml   # caso 3D

cd entregas\entrega2
python scripts\roundtrip_ifc.py --antes         # foto antes de editar en Bonsai
python scripts\roundtrip_ifc.py --despues       # Python detecta el cambio
python scripts\demo_1d_dx_dt.py --nx 21 | --nx 161 | --dt 3600 [--forzar] | --sweep
```

## Flujo de git

- Rama única `master`. Siempre `git pull` antes de empezar (José también hace push).
- Mensajes en español, estilo `feat(entregas): ...`, `fix(...)`, `docs: ...`.
- Al cerrar una entrega: tests en verde → commit → push → informar el SHA completo
  (`git rev-parse HEAD`) para Canvas, y avisar al grupo cuál se declaró.
