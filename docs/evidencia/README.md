# Carpeta de Evidencia y Registros de Validación (EP3)

Este directorio almacena la evidencia reproducible de ejecución, pruebas de software y telemetría de referencia para la **Evaluación Parcial N.º 3**.

---

## 1. Archivos Generados Automáticamente

- **`pruebas_unittest.txt`**: Registro completo de la ejecución de la suite de 68 pruebas automatizadas (`python -m unittest discover -s tests -v`), demostrando compatibilidad total con EP2 y validación de observabilidad, seguridad y benchmark.

---

## 2. Pendientes Manuales para el Estudiante (Benjamín Quiroz)

Conforme a las instrucciones de la asignatura y la rúbrica de evaluación de Duoc UC, los siguientes apartados deben ser completados o validados manualmente por el autor:

### A. Validación de Etiquetas del Benchmark
1. Revisa las etiquetas de `benchmark/casos.json` (sección esperada, debe abstenerse, datos clave).
2. Cambia el campo `"validado_por_humano": false` a `true` una vez confirmadas.

### B. Ejecución de la Corrida de Referencia
1. Ejecuta una simulación previa:
   ```bash
   python -m benchmark.ejecutar --perfil minimo --dry-run
   ```
2. Ejecuta el benchmark real en perfil mínimo (consume $\le 15$ turnos con tu API key de Groq):
   ```bash
   python -m benchmark.ejecutar --perfil minimo
   ```
3. Exporta la corrida generada hacia esta carpeta de evidencia:
   ```bash
   python -m observabilidad.resumen --run <RUN_ID> --exportar docs/evidencia
   ```
   Esto generará aquí:
   - `eventos_referencia.jsonl`
   - `resumen_referencia.json`
   - `tablas_referencia.md`
   - Archivos CSV por tabla (`kpis_principales.csv`, etc.)

### C. Capturas del Dashboard para el Informe (IE4, IE5)
Inicia la aplicación:
```bash
python -m streamlit run web.py
```
Abre en la barra lateral la página **📊 Observabilidad** y toma capturas de pantalla de alta resolución para incluir en el informe de 5 páginas:
- `captura_dashboard_resumen.png` (Pestaña 1: Resumen y latencia P50/P95)
- `captura_dashboard_precision.png` (Pestaña 2: Precision@1, Hit@k y barrido de umbral)
- `captura_dashboard_latencia.png` (Pestaña 3: Desglose por componente y hardware)
- `captura_dashboard_herramientas.png` (Pestaña 4: Frecuencia de herramientas y errores)
- `captura_dashboard_seguridad.png` (Pestaña 5: PII y bloqueos)
- `captura_dashboard_anomalias.png` (Pestaña 6: Tabla de anomalías detectadas)
- `captura_dashboard_trazas.png` (Pestaña 7: Diagrama de Gantt de una traza ReAct)

### D. Redacción Personal del Informe Escrito (Máximo 5 páginas)
> **RECORDATORIO ÉTICO DUOC UC:** La rúbrica prohíbe el uso de IA para redactar conclusiones, justificaciones técnicas o reflexiones individuales.
- [ ] **Análisis Crítico de Ejecución (IE6)**: Redacta tus hallazgos sobre los cuellos de botella observados (latencia del LLM vs retrieval, impacto del cold start).
- [ ] **Propuesta de Mejora y Escalabilidad (IE7)**: Propón recomendaciones fundamentadas basadas en los datos observados (ej. ajuste de umbral a 0.82, optimización de prompts, caché semántica).
- [ ] **Defensa de Criterios Éticos y Normativos (IE8)**: Justifica cómo el enmascaramiento de PII y la auditoría al proveedor cumplen con la normativa chilena de protección de datos personales.
- [ ] **Reflexión Individual Obligatoria**: Incluye tu reflexión personal sobre el aprendizaje y contribución al proyecto.
- [ ] **Declaración de Uso de IA**: Cita el uso de IA como herramienta de apoyo en desarrollo según https://bibliotecas.duoc.cl/ia.
