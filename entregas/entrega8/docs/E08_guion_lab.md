# E08 — Guion del laboratorio

Abre una terminal en esta carpeta, con el entorno activo:

```powershell
C:\Users\matia\.venvs\mcoc-p2\Scripts\Activate.ps1
```

**Antes de que llegue el ayudante:** corre `python -m pytest tests -q` y abre una vez `python scripts/simular_fundacion_ifc.py --visor` para comprobar que la ventana funciona.

## Frase de apertura

"Del IFC salen la geometría y la secuencia de cada vertida. Se voxeliza y cada celda queda con su `vertida_id`. El solver no sabe nada de la obra: recibe celdas, horas de activación y temperaturas. Por eso cambiar la secuencia no requiere tocar el código."

## Lo que va a pedir el ayudante

### 1. Cambiar Δx y reportar el error de volumen

```powershell
python scripts/simular_fundacion_ifc.py --dx 0.5 --sin-comparar
python scripts/voxelizar_ifc.py --dx 1 0.5 0.25 0.125
```

**Qué decir:** "V_h = N·Δx·Δy·Δz y e_V = |V_h − V|/V. Con Δx = 0,5 m el total es 0,52 %. El total engaña, por eso también miro cada vertida. Elijo un Δz que calce con las interfaces; si no, una vertida puede quedar con 16 % de error e incluso desaparecer con Δx = 1 m."

**Si preguntan por qué no converge limpio:** "Los errores de unas celdas compensan los de otras, así que baja sin una pendiente limpia. El área expuesta, en cambio, queda cerca de 17 % sobre la real y no baja: una escalera mide lo mismo con cualquier tamaño de peldaño."

### 2. Ocultar y mostrar una vertida

```powershell
python scripts/simular_fundacion_ifc.py --visor
```

En la ventana: **casillas o teclas 1 a 5** para cada vertida, **x** para cortar en y = 0 y la barra de abajo para cambiar el tiempo.

**Qué decir:** "Oculto la vertida 5 y se ve lo que queda debajo. Con el corte se ve el núcleo caliente. Si retrocedo el tiempo, las vertidas que aún no se colocan desaparecen: es la activación."

**Si no abre la ventana:**

```powershell
python scripts/simular_fundacion_ifc.py --ocultar 5 --t 30 --corte
```

Eso deja la imagen en `vista_3d.png`, dentro de la carpeta que indica el comando.

**Si lo piden en Bonsai:** abre `geometry/foundation.ifc` con `File > Open IFC Project`, selecciona la vertida y aprieta `H`; `Alt+H` la muestra. Cierra sin guardar.

### 3. Cambiar la hora de inicio

```powershell
python scripts/simular_fundacion_ifc.py --inicio 5=48
python scripts/simular_fundacion_ifc.py --intervalo 12
```

**Qué decir:** "No toqué el solver ni el IFC. El comando cambia los datos de entrada y el solver activa esas celdas a esa hora. Si la secuencia no se puede construir, porque una vertida va antes que la de abajo, el programa lo avisa."

### 4. Cambiar la temperatura de colocación

```powershell
python scripts/simular_fundacion_ifc.py --tcol 3=12
```

**Qué decir:** "La vertida 3 parte a 12 °C. Con madurez, además, reacciona más lento al inicio, así que el calor sale más tarde."

### 5. Ejecutar y visualizar el efecto

Cada comando con cambios también corre el caso base e imprime la diferencia. Se puede combinar todo:

```powershell
python scripts/simular_fundacion_ifc.py --intervalo 12 --tcol 3=12 --visor
```

Figuras en `results/e08/<caso>/`: `comparacion.png`, `activacion_cortes.png`, `series_fundacion.png`.

**Qué decir (con ese ejemplo):** "T máx baja de 63,06 °C a 62,03 °C y se retrasa de 52 h a 84 h, porque cada vertida alcanza a botar más calor antes de que llegue la siguiente. ΔT baja de 47,18 °C a 45,13 °C. Son valores con parámetros provisorios: muestran que el modelo responde, no son el plan."

## Preguntas probables

**¿Cómo sé que la secuencia no está en el código?** "`thermal.py` no tiene nombres ni fechas. Si edito `InicioPlanificado` en el IFC, o uso `--inicio`, cambia el resultado sin modificar el solver. Hay pruebas automáticas de eso."

**¿Qué pasa cuando entra una vertida?** "Sus celdas estaban en NaN y no participaban. A su hora toman la temperatura de colocación con edad cero. La cara superior de la vertida de abajo deja de perder calor al aire y empieza a conducir hacia la nueva."

**¿Cómo entra la hidratación?** "Q̇h = ρ·cp·dθ/dt, en W/m³. Cada celda tiene su propia edad. En cada paso integro la curva, Δθ = θ(edad final) − θ(edad inicial), para que el calor total no dependa de Δt. Con madurez, la edad corre según la temperatura."

**¿Por qué ΔT sube al refinar?** "Porque hoy se mide en el centro de la celda exterior, y al refinar queda más cerca de la cara. Falta medir a 25 mm: es de la próxima entrega."

**¿Los resultados cumplen?** "T máx sí y ΔT no, pero la hidratación no está calibrada y el clima es genérico. Todavía no se puede concluir."

## Si algo falla en vivo

| Problema | Qué hacer |
|---|---|
| La ventana 3D no abre | Usar `--ocultar`, `--t` y `--corte`, y mostrar `vista_3d.png` |
| Se demora con Δx muy fino | Volver a `--dx 0.5`: tarda unos segundos |
| `ModuleNotFoundError` | Falta activar el entorno |
| Una vertida "no tiene celdas" | Δz demasiado grande con `--dz`: quitar esa opción |
