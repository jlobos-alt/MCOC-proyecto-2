# Taller del miércoles 18: qué llevar y qué preguntar

## Qué llevar

| Pide la guía | Estado | Dónde |
|---|---|---|
| Computador, repo ejecutable, commit identificado | ✅ | `git rev-parse HEAD` tras el commit de la defensa |
| Geometría/IFC y voxelización | ✅ | `geometry/foundation.ifc`, `src/mcplan/voxel.py` |
| Corrida completa en una sola vertida | ✅ | plan `unica_*` en `results/defensa/planes.csv` |
| Las 8 curvas de hidratación, archivos originales y unidades | ✅ | `datos/curvas_hidratacion/originales/source_terms.txt` (Canvas) y `curvas.yaml` |
| Clima descargado: archivo, fuente, sitio, fechas, zona horaria, unidades, cobertura | ✅ | `datos/forecast_defensa/` (índice con SHA-256) y `escenarios/*.json` |
| Propuesta de vertidas, parámetros, bordes y resultados | ✅ | `results/defensa/` y `README.md` |
| Evidencia de verificación | ✅ | E05/E06 (batería y dossier), `tests/test_defensa.py` (S25 contra la solución exacta) |
| Hasta 3 consultas prioritarias | ✅ | abajo |

## Las 3 consultas prioritarias

1. **Las 8 curvas** (ya cargadas desde `source_terms.txt`).
   - ¿Es correcto tratarlas como 8 réplicas equiprobables, o la campaña 22A (menor confianza) debe pesar menos?
   - ¿Qué valor de β de la inversión considera más creíble? Con β = 3,0 nuestro plan queda en el límite.
   - ¿Hay que agregar el calor de las 2 primeras horas que no están en el archivo?
2. **Recursos y controles admisibles.**
   - Capacidad de colocación r: usamos 40 m³/h, con una bomba y sin simultaneidad.
   - Espera mínima entre vertidas.
   - Temperatura de colocación mínima construible: usamos 10 °C, con agua fría o hielo.
   - Aislación disponible: probamos EPS de 50, 100 y 150 mm, en laterales y como manta superior.
3. **Definición de S25 y criterio de malla.**
   - ¿La base contra el suelo cuenta como superficie exterior? La excluimos.
   - Con techos temporales incluidos, esperar entre vertidas sube MΔ: ¿es la interpretación esperada?
   - Con la malla fina, el plan elegido queda ~2,4 °C bajo el límite (17,6 °C) y su valor convergido se estima en
     ~18,5 °C: ¿qué margen se espera para declarar cumplimiento?

## Tareas concretas pendientes

- [x] Conseguir las 8 curvas y escribir `curvas.yaml`.
- [x] Correr la familia con 8 × 3 = 24 escenarios por plan.
- [ ] Confirmar con el profesor los pesos de las curvas y el criterio de margen frente a β y a la malla.
- [ ] Commit y SHA para la defensa del jueves 19.
