# Caso base, criterios y referencias

## 1. Paper geométrico y experimental principal

Yuwen Ju y Honggang Lei (2019): *Actual Temperature Evolution of Thick Raft
Concrete Foundations and Cracking Risk Analysis*, Advances in Materials Science
and Engineering, Article ID 7029671.
DOI: https://doi.org/10.1155/2019/7029671

Datos relevantes del caso:

- fundación para turbina eólica;
- aproximadamente 18 m x 18 m;
- espesor 3,30 m;
- parte superior cilíndrica de aproximadamente 7 m de diámetro;
- sensores a distintas alturas;
- temperatura de núcleo máxima cercana a 73 °C;
- peak cercano a 4 días;
- diferencia núcleo-superficie cercana a 35 °C;
- medidas de control estudiadas: vertidas por capas, aislación y monitoreo.

El paper es un caso físico real de referencia, pero no debe copiarse su modelo FE
ni asumirse que cada parámetro aplica automáticamente al caso del curso.

## 2. Especificación chilena principal

Instituto del Cemento y del Hormigón de Chile (ICH): *Especificación para Hormigón
Masivo Estructural*, Santiago, julio 2019.

https://ich.cl/documentos-ich/especificacion-para-hormigon-masivo-estructural/

Aspectos utilizados en el curso:

- definición de hormigón masivo;
- clasificación de riesgo;
- temperaturas máximas;
- diferencial núcleo-superficie;
- Plan de Control de Temperatura;
- monitoreo;
- curado y protección;
- estimación de aumento adiabático;
- método de Schmidt como enfoque simplificado de diferencias finitas.

## 3. Criterios numéricos del proyecto

### Temperatura máxima

ACI indica actualmente para hormigón masivo un máximo de 70 °C después de la
colocación: https://www.concrete.org/frequentlyaskedquestions/faqid/889.aspx

La especificación ICH tiene una tabla más matizada según categoría y exposición.
El curso adopta 70 °C como requisito único del caso docente.

### Diferencial térmico

ICH Tabla 4:

- 20 °C para resistencia real < 10 MPa;
- 25 °C para 10-25 MPa;
- 30 °C para > 25 MPa.

La página técnica del ICH explica que especificaciones antiguas usaban típicamente
un límite único de 20 °C, mientras la especificación 2019 lo hace dependiente de la
resistencia: https://hormigonaldia.ich.cl/recomendaciones-tecnicas/especificacion-para-hormigon-masivo-estructural/

Para mantener el foco en térmica + confiabilidad, se adopta 20 °C fijo durante los
14 días. Es más conservador que relajar el límite con la resistencia creciente.

ACI 301 usa actualmente 35 °F ≈ 19 °C entre centro y superficie, consistente con
ese orden de magnitud.

## 4. Método de Schmidt y enfoque del curso

El Anexo 4 del ICH describe el método de Schmidt como un método simplificado de
diferencias finitas adaptable a 1D, 2D y 3D. Puede considerar:

- geometría;
- propiedades térmicas;
- secuencia constructiva;
- interacción con fundación/relleno;
- gradientes;
- aislación;
- condiciones de borde.

Advierte que las condiciones de borde pueden ser determinantes. Nuestro solver no
reproduce literalmente el método de Schmidt, pero comparte su filosofía de
discretización cartesiana y balance térmico.

## 5. Pronósticos meteorológicos

Fuente abierta recomendada: https://open-meteo.com/

- Forecast API: https://open-meteo.com/en/docs
- Ensemble API: https://open-meteo.com/en/docs/ensemble-api
- Historical Forecast API: https://open-meteo.com/en/docs/historical-forecast-api
- Previous Runs API: https://open-meteo.com/en/docs/previous-runs-api

Variables potencialmente útiles: temperatura a 2 m; viento a 10 m; radiación solar
de onda corta; humedad si el modelo la requiere; temperatura de suelo si la fuente
la provee. Se puede usar otra fuente, pero debe documentarse.

## 6. BIM / IFC

- buildingSMART — IFC: https://technical.buildingsmart.org/standards/IFC/
- IfcOpenShell: https://docs.ifcopenshell.org/
- Procesamiento geométrico: https://docs.ifcopenshell.org/ifcopenshell-python/geometry_processing.html
- Bonsai: https://docs.bonsaibim.org/

## 7. Visualización

- PyVista: https://docs.pyvista.org/getting-started/
- PyVista tutorial: https://tutorial.pyvista.org/
- ParaView: https://docs.paraview.org/en/latest/
- ParaView tutorial: https://docs.paraview.org/en/latest/Tutorials/SelfDirectedTutorial/introduction.html
