# Curvas de hidratación del profesor

Aquí están las **8 curvas reales** entregadas por el profesor: `originales/source_terms.txt`, sin modificar,
y su descripción en `curvas.yaml`. Si faltara `curvas.yaml`, `scripts/defensa_plan.py` usaría la curva C1
**provisoria** y lo avisaría en cada corrida.

## Cómo agregarlas

1. Copiar los archivos originales en `originales/`, sin modificarlos, para la trazabilidad.
2. Por cada curva, un CSV con dos columnas `edad, valor` (con o sin encabezado), en las unidades
   del ensayo.
3. Escribir `curvas.yaml`:

```yaml
curvas:
  - nombre: M1
    archivo: M1.csv
    tipo: dT_ad            # dT_ad: incremento adiabático [°C]  |  Q_kg: calor acumulado por masa de cementante
    unidad_edad: h         # h | d | min | s
    unidad_valor: °C       # °C (dT_ad) | J/kg | J/g | kJ/kg (Q_kg)
    cementante_kg_m3: 380  # solo para Q_kg (b en q = b dH/da)
    mezcla: "..."          # lo que se sepa del ensayo
    temperatura_ensayo_C: 20
    fuente: "archivo original, fecha"
    # peso: 0.125          # opcional; sin pesos, las curvas son equiprobables (hipótesis declarada)
  - nombre: M2
    ...
```

4. Correr `python -m pytest tests/test_defensa.py -q` y `python scripts/defensa_plan.py`.

## Qué revisar antes de usarlas como escenarios

- **Qué midió cada ensayo:** incremento adiabático, calor por masa o temperatura de un ensayo
  no adiabático. Este último **no** sirve directo: necesita un balance del ensayo, y el cargador
  lo rechaza.
- **Si son réplicas de una misma mezcla.** Mezclas o contenidos de cemento distintos no son variabilidad
  de una población: la mezcla es una decisión. En ese caso, declarar el supuesto y tratarlas como
  escenarios de incertidumbre de modelo.
- **Unidades:** horas o días; J/g o J/kg.
- **Cola:** si la curva sigue subiendo al final del ensayo, el cargador avisa. Después del último
  punto se supone que no se libera más calor, y eso subestima el calor total.

El cargador interpola linealmente, sin suavizar, y recorta los tramos decrecientes, avisándolo. La
energía total liberada es exactamente ρ·cp·θ(última edad).
