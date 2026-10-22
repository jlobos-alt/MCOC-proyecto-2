# E02 — Guion de la actividad (round-trip IFC + demo 1D)

Guion para la sesión del jueves 22 de octubre (10:30–12:30). El ayudante pedirá
los 8 pasos de abajo; aquí está el comando exacto y qué responder.

---

## Antes de la actividad (checklist)

- [ ] IFC con al menos 3 objetos identificables → `geometry/foundation.ifc` (5 vertidas).
- [ ] Script que lea el IFC → `scripts/roundtrip_ifc.py --list`.
- [ ] Solver 1D ejecutable → `scripts/demo_1d_dx_dt.py`.
- [ ] Al menos un test automatizado → `tests/` (41 tests).

---

## Paso 1 — Abrir el IFC en Bonsai

- Bonsai: **File → Open IFC Project** → `geometry/foundation.ifc`.
- El modelo aparece en el árbol: 5 objetos `Vertida_01..Vertida_05`.

## Paso 2 — Identificar los objetos (y sacar la "foto" de antes)

```bash
python scripts/roundtrip_ifc.py --antes
```

Muestra los 5 objetos con nombre, GUID, clase, rango en z, volumen y ubicación,
y guarda esa foto en `resultados/foto_ifc_antes.json`.

En Bonsai, mostrar el árbol: IfcProject > IfcSite > IfcBuilding > IfcBuildingStorey
> 5 `IfcFooting`. Al seleccionar una vertida, el panel **Object Information**
muestra la clase, el GUID y el `Pset_HormigonMasivo`.

> **Qué decir:** son 5 vertidas de hormigón masivo, cada una `IfcFooting`, con
> GUID único y un `Pset_HormigonMasivo` con propiedades (VertidaID, fechas,
> T de colocación, moldaje, aislación, volumen).

## Paso 3 — Modificar en Bonsai (geometría o propiedad)

Opción A, **propiedad** (la más segura):
1. Seleccionar `Vertida_03` en el árbol.
2. Panel derecho → pestaña **Object** (Object Properties) → sección
   **Property Sets** → `Pset_HormigonMasivo` → ícono de lápiz (editar).
3. Cambiar `TemperaturaColocacion_C` de 18 a, por ejemplo, 12.5 y confirmar (✓).

Opción B, **geometría** (mover una vertida):
1. Seleccionar `Vertida_05` en el árbol (o en la vista 3D).
2. Teclas `G`, luego `Z`, escribir `0.5` y `Enter`: sube 0,5 m.

> **Qué decir:** bajo la temperatura de colocación de la vertida 3 (por ejemplo,
> enfriando el agua de la mezcla), o muevo el pedestal para ver que el cambio de
> geometría también viaja por el IFC.

## Paso 4 — Guardar

Bonsai: **File → Save IFC Project** (o `Ctrl+S`). Se guarda sobre `geometry/foundation.ifc`.

> **Qué decir:** el `.ifc` es la fuente de verdad; el `.blend` no se versiona.

## Paso 5 — Demostrar que Python detecta la modificación

```bash
python scripts/roundtrip_ifc.py --despues
```

Salida esperada (opción A):

```
Python detectó 1 cambio(s):
  * Vertida_03: propiedad Pset_HormigonMasivo.TemperaturaColocacion_C: 18 -> 12.5
Identidad BIM: 5 objetos conservan su GUID.
```

Con la opción B aparece `Vertida_05: ubicación (0,0,0) -> (0,0,0.5) m`,
`z mínimo 3.300 -> 3.800 m` y `z máximo 4.300 -> 4.800 m`. El volumen no
cambia, porque mover no cambia el tamaño.

Este comparador (`src/mcplan/ifc_diff.py`) lee el IFC como texto, sin
IfcOpenShell ni Blender: resuelve las referencias `#n`, suma los placements
y calcula volúmenes de extrusiones, B-reps y mallas. Está verificado por
`tests/test_roundtrip_bonsai.py`, que simula las tres ediciones típicas.

Alternativa sin Bonsai (si algo falla en vivo):

```bash
python scripts/roundtrip_ifc.py --set TemperaturaColocacion_C 21.5 --vertida Vertida_03
```

> **Qué decir:** re-leo el archivo guardado desde Python, sin Blender abierto,
> y aparece el valor nuevo. Los GUID no cambian: la identidad BIM se preserva.

**Después de la demo**, para dejar el IFC como estaba:
`git checkout geometry/foundation.ifc`.

## Paso 6 — Ejecutar el solver 1D

```bash
python scripts/demo_1d_dx_dt.py
```

Salida: `T_max`, `ΔT`, `dx`, `dt`, `Fo`, `dt_max`. Caso de la losa de 3.3 m de
hormigón con calor de hidratación; cara superior convectiva (día/noche), base
adiabática.

## Paso 7 — Modificar Δx o Δt

```bash
# Δx: cambiar el número de nodos
python scripts/demo_1d_dx_dt.py --nx 21      # Δx grueso
python scripts/demo_1d_dx_dt.py --nx 161     # Δx fino

# Δt: forzar el paso de tiempo
python scripts/demo_1d_dx_dt.py --dt 500          # estable (dt_max ≈ 950 s con nx=67)
python scripts/demo_1d_dx_dt.py --dt 3600         # el solver lo rechaza y explica por qué
python scripts/demo_1d_dx_dt.py --dt 3600 --forzar   # se ve cómo diverge
python scripts/demo_1d_dx_dt.py --sweep      # tabla comparativa
```

## Paso 8 — Explicar el efecto observado

- **Δx (número de nodos).** `Δx = L/(nx−1)`. Al duplicar nx el error cae ~4×
  (orden 2). El perfil de temperatura converge a la solución de referencia.
  Costo: más nodos → más cómputo.
- **Δt.** El método es Euler explícito (FTCS). El criterio de estabilidad es
  `Fo = α·Δt/Δx² ≤ 0.5` → `Δt ≤ Δx²/(2α)`. Por sobre ese valor la solución
  oscila y **diverge** (el script lo muestra con `--sweep`).
- **Acoplamiento.** Refinar Δx reduce Δx y por tanto `Δt_max` cae con Δx²: para
  malla fina hay que usar pasos de tiempo mucho menores (más pasos).

---

## Preguntas individuales breves (preparación)

1. ¿Por qué el `.ifc` es la fuente de verdad y no el `.blend`?
   → Es un formato abierto y estándar; cualquiera lo reabre y su identidad
   (GUID) y propiedades se preservan sin depender de Blender.
2. ¿Qué garantiza que la modificación "se vea" en Python?
   → Re-leer el archivo guardado con IfcOpenShell y volcar el Pset; el valor
   nuevo aparece y los GUID siguen iguales.
3. ¿Qué es el número de Fourier y por qué ≤ 0.5?
   → `Fo = α·Δt/Δx²`; para FTCS la amplificación de errores es ≤ 1 solo si
   `Fo ≤ 0.5`; sobre eso crece y el resultado diverge.
4. ¿Qué pasa si afinás Δx manteniendo Δt?
   → Se viola el límite de estabilidad (Fo crece) y el resultado se vuelve
   inestable; hay que reducir Δt proporcionalmente.
5. ¿Cómo se relaciona la geometría con el solver?
   → El solver recibe números (longitud/espesor, material, condiciones) que
   provienen de la geometría y las propiedades del IFC; no depende de Blender.
