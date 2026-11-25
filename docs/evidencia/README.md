# Evidencia y validación de la EP3

Esta carpeta reúne pruebas automatizadas, resultados reproducibles del
benchmark, capturas del dashboard y el informe técnico de la Evaluación
Parcial N.º 3.

## Benchmark de recuperación

El conjunto contiene 50 casos en `benchmark/casos.json`. El perfil `retrieval`
ejecuta los 50 sin llamar al LLM ni consumir tokens de proveedor; carga el
modelo de embeddings local. Su salida mide recuperación RAG y abstención,
no fidelidad de respuestas generadas.

```powershell
python -m benchmark.ejecutar --perfil retrieval --dry-run
python -m benchmark.ejecutar --perfil retrieval --pausa 0
```

Los artefactos de la corrida documentada son:

- `eventos_referencia.jsonl`: eventos de benchmark y retrieval correlacionados
  por `run_id` y `trace_id`, con consultas enmascaradas.
- `benchmark_retrieval_preliminar.json`: KPIs, percentiles y estado de
  validación del dataset.
- `benchmark_retrieval_preliminar.csv`: resultados por caso.

**Estado actual:** el dataset declara `validado_por_humano: true` tras la revisión humana de las 50 etiquetas de sección esperada, abstención, datos clave y bloqueos de seguridad. La corrida de referencia exportada (`ep3-referencia`) incluye `eventos_referencia.jsonl`, `resumen_referencia.json`, `tablas_referencia.md`, `kpis_principales.csv` y `metricas_por_caso.csv`.

El perfil `minimo` genera respuestas con el LLM y requiere una clave válida.
Solo debe ejecutarse tras validar las etiquetas y obtener autorización del
equipo para el consumo de tokens:

```powershell
python -m benchmark.ejecutar --perfil minimo --dry-run
python -m benchmark.ejecutar --perfil minimo
```

## Dashboard y trazabilidad

Inicia la aplicación con:

```powershell
python -m streamlit run web.py
```

En la página **Observabilidad**, selecciona **Corrida de referencia**. El panel
incluye resumen, precisión/consistencia, latencia/recursos, herramientas/errores,
seguridad/privacidad, anomalías y explorador de trazas. Si el benchmark no está
validado, el panel muestra una advertencia explícita.

Capturas guardadas en esta entrega:

- `captura_dashboard_precision.png`: métricas del benchmark y su advertencia.
- `captura_dashboard_traza.png`: eventos de retrieval vinculados a una traza.

## Pruebas y entregables verificados

- `pruebas_unittest.txt`: salida de la ejecución completa de la suite (**72 pruebas aprobadas**).
- `benchmark/casos.json`: 50 casos etiquetados y validados (`validado_por_humano: true`).
- `../Informe_EP3_Duqui.docx` y `../Informe_EP3_Duqui.md`: informe técnico completo de 5 páginas con métricas, trazas, capturas, análisis crítico (IE6), recomendaciones justificadas (IE7), defensa ética/normativa (IE8), reflexión individual y referencias APA 7.
- `../Presentacion_EP3_Duqui.pptx`, `../guion_presentacion_EP3.md` y `../guia_estudio_EP3.md`: presentación de 10 diapositivas, guion completo de exposición y guía de estudio con las preguntas del foro del profesor.

## Uso de IA

OpenCode se utilizó como apoyo para revisar código, corregir la selección y
clasificación de métricas del benchmark, generar la corrida local y preparar
materiales de estudio. El equipo debe revisar los artefactos, validar las
etiquetas y declarar/citar este uso conforme a
<https://bibliotecas.duoc.cl/ia>. No se generaron conclusiones, justificaciones
críticas ni reflexiones personales.
