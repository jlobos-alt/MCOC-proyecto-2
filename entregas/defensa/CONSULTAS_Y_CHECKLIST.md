# Taller del miércoles 18: qué llevar y qué preguntar

## Qué llevar

| Pide la guía | Estado | Dónde |
|---|---|---|
| Computador, repo ejecutable, commit identificado | ✅ | `git rev-parse HEAD` tras el commit de la defensa |
| Geometría/IFC y voxelización | ✅ | `geometry/foundation.ifc`, `src/mcplan/voxel.py` |
| Corrida completa en una sola vertida | ✅ | plan `unica_*` en `results/defensa/planes.csv` |
| **Las 8 curvas de hidratación, archivos originales y unidades** | ❌ **FALTAN** | Ponerlas en `datos/curvas_hidratacion/` (ver `LEEME.md`) |
| Clima descargado: archivo, fuente, sitio, fechas, zona horaria, unidades, cobertura | ✅ | `datos/forecast_defensa/` (índice con SHA-256) y `escenarios/*.json` |
| Propuesta de vertidas, parámetros, bordes y resultados preliminares | ✅ (con curva provisoria) | `results/defensa/` y `README.md` |
| Evidencia de verificación | ✅ | E05/E06 (batería y dossier), `tests/test_defensa.py` (S25 contra la solución exacta) |
| Hasta 3 consultas prioritarias | ✅ | abajo |

## Las 3 consultas prioritarias

1. **Las 8 curvas.**
   - ¿Qué midió cada ensayo: incremento adiabático o calor por masa (J/g o J/kg)?
   - ¿En qué unidades de edad?
   - ¿Son réplicas de una misma mezcla, o mezclas o contenidos de cemento distintos?
   - ¿Hay contenido de cementante b?
   - Sin esto no se pueden asignar pesos ni cerrar P_f.
2. **Recursos y controles admisibles.**
   - Capacidad de colocación r: usamos 40 m³/h, con una bomba y sin simultaneidad.
   - Espera mínima entre vertidas.
   - Temperatura de colocación mínima construible: usamos 10 °C, con agua fría o hielo.
   - Aislación disponible: probamos EPS de 50, 100 y 150 mm, en laterales y como manta superior.
3. **Definición de S25 y criterio de malla.**
   - ¿La base contra el suelo cuenta como superficie exterior? La excluimos.
   - Con techos temporales incluidos, esperar entre vertidas sube MΔ: ¿es la interpretación esperada?
   - Nuestro plan foco cambia de clasificación al refinar la malla (ver README): ¿qué margen o qué malla
     se espera para declarar cumplimiento?

## Tareas concretas pendientes

- [ ] Conseguir las 8 curvas originales y escribir `datos/curvas_hidratacion/curvas.yaml`.
- [ ] Volver a correr `python scripts/defensa_plan.py` con las curvas reales: 8 × 3 = 24 escenarios por plan.
- [ ] Decidir con el profesor el criterio de malla o de margen para el plan que quede en la frontera.
- [ ] Commit y SHA para la defensa del jueves 19.
