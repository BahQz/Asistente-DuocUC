# Diccionario de Métricas de Observabilidad — Duqui (EP3)

Este documento detalla las definiciones formales, fórmulas matemáticas, eventos de origen y paneles de visualización para todas las métricas implementadas en el sistema de observabilidad del agente Duqui, en conformidad con los criterios de evaluación de la asignatura **Ingeniería de Soluciones con IA (007D_OLS)**.

---

## 1. Resumen de Métricas Principales

| Métrica | Definición Conceptual | Fórmula / Algoritmo | Evento de Origen | Panel del Dashboard | Indicador de Logro |
|---|---|---|---|---|---|
| **Tasa de Éxito** | Proporción de turnos resueltos satisfactoriamente sobre turnos ejecutados sin error interno. | $$\text{Tasa de Éxito} = \frac{N_{\text{ok}}}{N_{\text{ok}} + N_{\text{error}}}$$ | `turno.resultado` | Tab 1: Resumen | IE1 |
| **Tasa de Bloqueo** | Proporción de turnos interceptados preventivamente por guardrails de seguridad (inyección o salida). | $$\text{Tasa de Bloqueo} = \frac{N_{\text{bloqueado\_entrada}} + N_{\text{bloqueado\_salida}}}{N_{\text{total\_turnos}}}$$ | `turno.resultado` | Tab 1 / Tab 5 | IE8 |
| **Latencia Total P50** | Mediana del tiempo total transcurrido desde el ingreso de la consulta hasta la entrega de la respuesta. | Percentil 50 de $\text{latencia\_total\_ms}$ con interpolación lineal. | `turno.latencia_total_ms` | Tab 1: Resumen | IE2 |
| **Latencia Total P95** | Percentil 95 del tiempo total de respuesta, indicando la cola de peor desempeño (SLA). | Percentil 95 de $\text{latencia\_total\_ms}$ con interpolación lineal. | `turno.latencia_total_ms` | Tab 1: Resumen | IE2 |
| **Tokens por Turno** | Cantidad de tokens consumidos (prompt + completion) por cada invocación del modelo de lenguaje. | $$\text{Tokens Total} = \text{Tokens}_{\text{prompt}} + \text{Tokens}_{\text{completion}}$$ | `turno.tokens_total` | Tab 1 / Tab 3 | IE2 |
| **Precision@1** | Proporción de consultas del benchmark donde el fragmento de mayor score coincide con la sección esperada. | $$\text{Precision@1} = \frac{\sum \mathbb{I}(\text{top1} \in \text{secciones\_esperadas})}{N_{\text{casos\_con\_seccion}}}$$ | `benchmark_caso.observado.acierto_top1` | Tab 2: Precisión | IE1 |
| **Hit@k** | Proporción de consultas donde al menos una sección esperada apareció entre los $k$ candidatos recuperados. | $$\text{Hit@k} = \frac{\sum \mathbb{I}(\exists s \in \text{candidatos} \cap \text{esperados})}{N_{\text{casos\_con\_seccion}}}$$ | `benchmark_caso.observado.hit_topk` | Tab 2: Precisión | IE1 |
| **Abstención Correcta** | Sensibilidad ante preguntas fuera de dominio (True Positive Rate de abstención). | $$\text{Tasa Abs.} = \frac{\text{TP}}{\text{TP} + \text{FN}}$$ | `benchmark_caso.observado.decision` | Tab 2: Precisión | IE1 |
| **Falsos Rechazos** | Tasa de consultas válidas dentro del reglamento que fueron rechazadas erróneamente por el umbral. | $$\text{Falsos Rechazos} = \frac{\text{FP}}{\text{FP} + \text{TN}}$$ | `benchmark_caso.observado.decision` | Tab 2: Precisión | IE1 |
| **Consistencia Semántica** | Estabilidad de recuperación entre variantes lingüísticas de un mismo grupo temático (moda top-1). | $$\text{Consistencia} = \frac{\text{Frecuencia}(\text{top1}_{\text{modal}})}{N_{\text{grupo}}}$$ | `benchmark_caso.grupo_consistencia` | Tab 2: Consistencia | IE1 |
| **Consistencia de Decisión** | Proporción de variantes de un grupo que producen la misma decisión (responder vs abstenerse). | $$\text{Consistencia Decisión} = \frac{\text{Frecuencia}(\text{decisión}_{\text{modal}})}{N_{\text{grupo}}}$$ | `benchmark_caso.grupo_consistencia` | Tab 2: Consistencia | IE1 |
| **Desviación Score (std)** | Desviación estándar del `top1_score` entre las variantes de un mismo grupo semántico. | $$\sigma = \sqrt{\frac{1}{N}\sum_{i=1}^N (s_i - \bar{s})^2}$$ | `retrieval.top1_score` | Tab 2: Consistencia | IE1 |
| **Consumo de Memoria RSS** | Memoria física residente (Resident Set Size) ocupada por el proceso en megabytes. | `psutil.Process().memory_info().rss / 1024 / 1024` | `recursos.rss_mb` | Tab 3: Recursos | IE2 |
| **Delta RSS Embeddings** | Incremento neto de memoria física tras la inicialización del modelo `multilingual-e5-small`. | $$\Delta \text{RSS} = \text{RSS}_{\text{post\_embeddings}} - \text{RSS}_{\text{pre\_embeddings}}$$ | `recursos.delta_rss_mb` | Tab 3: Recursos | IE2 |
| **Frecuencia de Errores** | Cantidad y porcentaje de fallas clasificadas por categoría (429, timeout, auth, iteraciones, etc.). | Conteo por `error.categoria` | `error.categoria` | Tab 4: Errores | IE1, IE3 |
| **Tasa de Derivación** | Porcentaje de respuestas donde el asistente deriva explícitamente a la mesa de ayuda o dirección. | $$\text{Tasa Derivación} = \frac{N_{\text{derivaciones}}}{N_{\text{turnos}}}$$ | `turno.derivacion` | Tab 1: Resumen | IE1 |

---

## 2. Definiciones Operativas y Reglas Derivadas

### 2.1 Abstención
Un turno se clasifica como **abstención (`true`)** cuando se invocó la herramienta `buscar_reglamentos` y ningún fragmento superó el umbral de relevancia coseno (0.82) o margen relativo (0.02), impidiendo que el modelo elabore una respuesta normativa sin evidencia.
Si la consulta no requirió búsqueda reglamentaria (por ejemplo saludos, agradecimientos o preguntas sobre feriados), el valor de abstención es **`null`** y se excluye estrictamente de los denominadores de precisión.

### 2.2 Derivación Oficial
Se marca `derivacion = true` mediante una función pura (`es_derivacion(texto)`) cuando el texto final de la respuesta, tras ser normalizado (minúsculas y sin acentos), contiene menciones explícitas a los canales humanos institucionales de Duoc UC:
- `"mesa de ayuda"`
- `"soporte@duocuc.cl"`
- `"600-300-4000"` o `"600 300 4000"` o `"6003004000"`
- `"direccion de escuela"`

### 2.3 Zona Gris de Recuperación
Se define un evento de recuperación en **zona gris** cuando la distancia entre el puntaje de similitud del mejor candidato (`top1_score`) y el umbral configurado (`UMBRAL_RELEVANCIA = 0.82`) es menor o igual a $\pm 0.03$:
$$| \text{top1\_score} - \text{umbral} | \le 0.03$$
Indica casos limítrofes donde una pequeña fluctuación en la formulación de la pregunta puede cambiar la decisión de responder o abstenerse.

### 2.4 Turno Frío vs. Turno Caliente
- **Turno Frío (`turno_frio = true`)**: Aquel turno en el cual se disparó por primera vez la carga en memoria del modelo de embeddings (`multilingual-e5-small`) o la construcción/reindexación de ChromaDB. Se aísla en los análisis para evitar sesgar los percentiles operativos de latencia.
- **Turno Caliente (`turno_frio = false`)**: Turno ejecutado cuando los modelos e índices ya residen en la memoria RAM del proceso.

### 2.5 Reglas Deterministas de Detección de Anomalías
El panel de anomalías opera sin interpretaciones de IA, marcando las ejecuciones que cumplen reglas estadísticas objetivas:
1. `latencia_sobre_p95`: `latencia_total_ms > P95`.
2. `latencia_zscore_gt_2`: Puntaje estandarizado Z de latencia superior a 2.0 ($Z = \frac{x - \mu}{\sigma} > 2.0$).
3. `tokens_sobre_p95`: `tokens_total > P95_tokens`.
4. `racha_errores_ge_2`: Dos o más turnos consecutivos con `resultado = "error"`.
5. `zona_gris`: Recuperación semántica con $| \text{top1\_score} - 0.82 | \le 0.03$.
6. `muchas_herramientas`: Más de 3 llamadas a herramientas en un único turno.
7. `cerca_limite_iteraciones`: Cantidad de pasos ReAct superior o igual al 80% de `AGENTE_MAX_ITERACIONES` ($\ge 14$ pasos).
8. `con_reintentos`: Turnos que experimentaron al menos un reintento recuperado por rate limit o timeout.
