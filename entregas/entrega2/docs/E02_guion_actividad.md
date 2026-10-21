# E02 — Guion de la actividad (round-trip IFC + demo 1D)

Guion para la sesión del jueves 22 de octubre (10:30–12:30). El ayudante pedirá
los 8 pasos de abajo; aquí está el comando exacto y qué responder.

---

## Antes de la actividad (checklist)

- [ ] IFC con al menos 3 objetos identificables → `geometry/foundation.ifc` (5 vertidas).
- [ ] Script que lea el IFC → `scripts/roundtrip_ifc.py --list`.
- [ ] Solver 1D ejecutable → `scripts/demo_1d_dx_dt.py`.
- [ ] Al menos un test automatizado → `tests/` (36 tests).

---

## Paso 1 — Abrir el IFC en Bonsai

- Bonsai: **File → Open IFC Project** → `geometry/foundation.ifc`.
- El modelo aparece en el árbol: 5 objetos `Vertida_01..Vertida_05`.

## Paso 2 — Identificar los objetos

```bash
python scripts/roundtrip_ifc.py --list
```

Salida esperada: 5 filas, cada una con nombre, GUID (22 caracteres), clase
`IfcFooting` y temperatura de colocación.

> **Qué decir:** son 5 vertidas de hormigón masivo, cada una `IfcFooting`, con
> GUID único y un `Pset_HormigonMasivo` con propiedades (VertidaID, fechas,
> T de colocación, volumen).

## Paso 3 — Modificar geometría o una propiedad

Propiedad (por script):

```bash
python scripts/roundtrip_ifc.py --set TemperaturaColocacion_C 21.5 --vertida Vertida_03
```

O en Bonsai: seleccionar `Vertida_03` → **Object Properties** → editar
`TemperaturaColocacion_C` (o mover/escalar la geometría con las herramientas
de edición).

> **Qué decir:** cambio la temperatura de colocación de la vertida 3 de 18 a
> 21.5 °C para representar una colocación más calurosa.

## Paso 4 — Guardar

- Script: escribe `geometry/foundation_editado.ifc` (no toca el original).
- Bonsai: **Ctrl+S** / File → Save.

> **Qué decir:** el `.ifc` es la fuente de verdad; el `.blend` no se versiona.

## Paso 5 — Demostrar que Python detecta la modificación

El propio script imprime la verificación:

```
[4] Antes  -> Despues : 18.0 -> 21.5
[6] Verificacion (Python detecta el cambio): 21.5
    OK: el round-trip cerro correctamente.
```

O con el test:

```bash
python -m pytest tests/test_roundtrip.py -v
```

> **Qué decir:** re-leo el IFC con IfcOpenShell (el mismo motor que usa Bonsai) y
> encuentro el valor nuevo. Los GUID no cambian: la identidad BIM se preserva.

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
python scripts/demo_1d_dx_dt.py --dt 2000
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
