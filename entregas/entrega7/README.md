# E07 — Revisión oral: voxelización, vertidas e hidratación (4 puntos)

**Fecha:** miércoles 4 de noviembre, 10:30–13:20 · **Modalidad:** revisión oral

**Objetivo:** conectar el BIM real con la grilla térmica y formular la construcción por vertidas.

Carpeta autocontenida, copia de la raíz del repo en el commit declarado. Guion:
[docs/E07_guion_oral.md](docs/E07_guion_oral.md). Hidratación:
[docs/E07_diseno_hidratacion.md](docs/E07_diseno_hidratacion.md).

## Cómo correr (desde esta carpeta)

```powershell
pip install -r requirements.txt
python -m pytest tests -q                  # 99 tests (~1 min)
python scripts/voxelizar_ifc.py            # geometría, voxeles, error de volumen y de área
python scripts/curva_hidratacion.py        # curva adiabática, Q̇h y madurez
python scripts/simular_fundacion_ifc.py    # fundación completa por vertidas (~10 s)
```

IfcOpenShell es necesario para extraer la geometría. Sin él, esos tests se omiten.

### Cambiar parámetros en vivo

| Qué | Comando |
|---|---|
| Otra resolución | `python scripts/voxelizar_ifc.py --dx 1 0.5 0.25` |
| Figura de cortes con otro Δx | `python scripts/voxelizar_ifc.py --corte-dx 0.5` |
| Malla sin calzar | `python scripts/simular_fundacion_ifc.py --dz 0.25` |
| Sin efecto de la temperatura | `python scripts/simular_fundacion_ifc.py --sin-madurez` |
| Otra curva adiabática | `python scripts/curva_hidratacion.py --theta 50 --tau 24 --ea-r 5000` |

Para cambiar la secuencia, edita `InicioPlanificado` o `TemperaturaColocacion_C` en el IFC y vuelve a
correr `simular_fundacion_ifc.py`: el plan los lee de ahí.

## Lo que pide la entrega

| Requisito | Dónde | Evidencia |
|---|---|---|
| Extracción de geometría IFC | `src/mcplan/bim.py`, `extraer_solidos` | 5 sólidos, 636,88 m³, coincide con el Pset de cada vertida |
| Primer voxelizador | `src/mcplan/voxel.py`, `voxelizar` | Coincide con la fórmula de una pirámide, celda por celda |
| `vertida_id` | `Voxelizacion.vertida_id` | Cada celda en una sola vertida, `results/e07/voxeles_cortes.png` |
| Estimación de volumen | `error_volumen`, `scripts/voxelizar_ifc.py` | 5 resoluciones, total y por vertida, `results/e07/volumen_vs_dx.png` |
| Diseño del modelo de hidratación | `docs/E07_diseno_hidratacion.md`, `src/mcplan/hydration.py` | `results/e07/hidratacion.png` |
| Estructura para activación temporal | `build_model(plan, voxeles=...)`, `solve`, `plan_desde_solidos` | Inicios leídos del IFC, `results/e07/activacion_cortes.png` |

## Resultados

Volumen (V_geom = 636,88 m³; A real = 642,0 m²):

| Δx [m] | Δz [m] | Celdas | e_V total | Peor vertida | A escalera / A real |
|---|---|---|---|---|---:|
| 0,5 | 0,5 | 5 140 | 0,88 % | 37,8 % | 1,18 |
| 0,25 | 0,25 | 40 536 | 0,55 % | 16,0 % | 1,17 |
| 0,125 | 0,125 | 324 508 | 0,48 % | 13,3 % | 1,17 |
| 0,25 | 0,275 | 37 164 | 0,29 % | 10,1 % (vertida 5); 0,8 % las demás | 1,17 |
| 0,125 | 0,1375 | 295 340 | 0,37 % | 3,4 % (vertida 5); 0,3 % las demás | 1,17 |

Fundación, 14 días. **Parámetros provisorios: prueba la cadena, no concluye sobre el plan.**

| Δx [m] | Δz [m] | T máx | Instante | ΔT máx | Instante |
|---|---|---|---|---|---|
| 0,5 | 0,55 | 62,76 °C | 106 h | 42,94 °C | 96 h |
| 0,25 | 0,275 | 61,47 °C | 105 h | 45,19 °C | 142 h |
| 0,125 | 0,1375 | 61,47 °C | 104 h | 46,02 °C | 116 h |

La malla por defecto es Δx = 0,25 m, Δz = 0,275 m.

## Correcciones al solver existente

Afectan a `src/mcplan` y solo se aplican desde esta entrega. Las carpetas de entregas anteriores no cambian.

| Error | Efecto | Prueba |
|---|---|---|
| Cara hacia una celda vacía quedaba aislada | La misma caja daba 39,0 °C en vez de 24,7 °C; un octágono no habría perdido calor por sus lados | `test_celda_vacia_al_lado_es_frontera_no_aislacion`, `test_forma_en_l_...` |
| `maturity_factor` dividía Ea/R otra vez por R | m(50 °C) = 1,16 en vez de 3,55 | `test_factor_de_arrhenius` |
| Faltaba m(T) en el calor del solver | Con madurez se perdía calor: subía 40,8 °C en vez de 45 °C | `test_calor_total_no_depende_de_la_madurez` |
| Calor evaluado al inicio de cada paso | T máx de la fundación daba 82,3 °C con Δt = 6 h y 62,8 °C con Δt = 2 min | `test_calor_total_no_depende_de_dt` |
| `read_ifc_vertidas` buscaba `Inicio_h` | Las 5 vertidas partían a la vez | `test_read_ifc_vertidas_lee_los_inicios_reales` |

La cuarta corrección cambia un poco el caso antiguo de `datos/caso_fundacion.yaml`: T máx pasa de 58,16 a
57,49 °C y ΔT de 38,03 a 37,45 °C. `validacion/caso_fundacion/` conserva los valores anteriores.

## Limitaciones

- θ∞, τ, Ea/R y el clima son provisorios (E09–E12).
- El área en escalera queda cerca de 17 % sobre la real y no converge al refinar.
- ΔT se mide en centros de celda, a Δx/2 de la cara, no a 25 mm.
- El moldaje es una capa común entre 0 y 72 h; `Moldaje` y `Aislacion` del IFC aún no se aplican (E10).
- La vertida 5 queda con error de volumen mayor, porque su cara superior no calza con Δz.
- Verificado, no validado: falta comparar con Ju & Lei (E09).

## Evidencia / entrega (Canvas)

```
Repositorio: https://github.com/jlobos-alt/MCOC-proyecto-2
Commit evaluado: (completar tras el commit)
```
