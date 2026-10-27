# E03 — Entrega de verificación 1D (2 puntos)

**Fecha:** Viernes 23 de octubre  
**Objetivo:** Demostrar cuantitativamente que el solver 1D converge hacia una solución conocida.

## Ecuación y solución exacta
Para difusión pura con $T(x,0)=A\sin(\pi x/L)$, $T(0,t)=T(L,t)=0$:
$$
T_{exact}(x,t)=A\sin\frac{\pi x}{L}\exp\!\left(-\alpha\left(\frac{\pi}{L}\right)^2 t\right),\qquad \alpha=\frac{k}{\rho c_p}.
$$

## Esquema usado
FTCS (Forward Time, Central Space) con volúmenes de control por celda (ver `src/mcplan/thermal1d.py`).
- Condiciones Dirichlet homogéneas
- Estabilidad (explícito): $\mathrm{Fo}=\alpha\frac{\Delta t}{\Delta x^2}\le 0.5$
- $\Delta t_{max}$ calculado con `stable_dt_1d`

## Reproducibilidad
```powershell
cd entregas/entrega3
pip install -r requirements.txt
python scripts/verificar_convergencia.py
```
Genera en `results/`:
- `e03_exact_vs_num.png`
- `e03_conv_espacial.png`
- `e03_conv_temporal.png`

## Evidencia / entrega (Canvas)
```
Repositorio: https://github.com/jlobos-alt/MCOC-proyecto-2
Commit evaluado: (completar tras commit)
```

## Respuesta a la pregunta
**¿Qué evidencia tienen de que el programa resuelve la ecuación que creen estar resolviendo?**
Comparamos el resultado numérico con la solución analítica del problema de difusión con Dirichlet homogéneas: $T(x,0)=10\sin(\pi x/L)$. Al refinar $\Delta x$ manteniendo $\mathrm{Fo}\approx const$, el error máximo $\|e\|_\infty = \max_x |T_{num}-T_{exact}|$ disminuye con orden ~2 ($\mathcal{O}(\Delta x^2)$), consistente con FTCS. Al refinar $\Delta t$ con $\Delta x$ fijo se observa convergencia hacia la solución espacialmente discreta. Además, para $\mathrm{Fo}>0.5$ el esquema diverge (comprobado en tests). Esto verifica tanto el esquema como la implementación.
