# Esquema del Informe Técnico — EP2 ISY0101

**Título sugerido:** *De un RAG léxico a un agente ReAct: evolución de un
asistente estudiantil con memoria, herramientas y recuperación semántica*

**Extensión máxima:** 5 páginas (sin contar portada ni anexos, si la sección lo
permite). **Formato:** Word o PDF, hoja carta, márgenes de 2,5 cm, fuente
Calibri o Arial 11, interlineado 1,15.

> **Cómo usar este documento:** es un **esquema de contenido**, no el informe
> final. Cada sección incluye el objetivo, los argumentos que deben aparecer,
> las figuras/tablas sugeridas y el espacio recomendado. La conclusión y la
> reflexión individual deben ser redactadas por el autor **sin apoyo de IA**,
> según las instrucciones de la evaluación.

---

## Mapa de cobertura de indicadores

| Indicador | Dónde se evidencia en el informe | Evidencia en el repositorio |
|---|---|---|
| **IE1** Herramientas autónomas | §4.2 y §5 | `chatbot/herramientas.py`, traza en la UI |
| **IE2** Framework adecuado | §3.2 | `chatbot/agente.py` (`create_agent`), `requirements.txt` |
| **IE3** Memoria de contenido | §3.3 | `chatbot/memoria.py`, `chatbot/documentos.py` |
| **IE4** Recuperación semántica | §3.4 | `chatbot/conocimiento.py`, `.chroma/` |
| **IE5** Planificación y prioridades | §4.3 | Prompt ReAct, `calcular_plazo`, casos multi-etapa |
| **IE6** Informe, diagramas y flujos | Todo el documento | `docs/arquitectura.md`, README, Mermaid |
| **IE7** Toma de decisiones demostrada | §5.2 y anexo de demo | `docs/guion_demostracion.md`, traza |
| **IE8** Diagrama + README | §3.1 | README + Mermaid |
| **IE9** Justificación de componentes | §3.2 a §3.4 y §6 | Tabla de decisiones y referencias |
| **IE10** Lenguaje técnico | Todo el documento | Uso consistente de términos y evidencia |

---

## Presupuesto de páginas

| Sección | Páginas | Prioridad |
|---|---:|---|
| Portada + resumen ejecutivo | 0,5 | Alta |
| 1. Contexto y problema | 0,5 | Alta |
| 2. Objetivos y alcance | 0,25 | Media |
| 3. Arquitectura y decisiones de diseño | 1,5 | **Muy alta** |
| 4. Implementación del agente | 0,75 | Alta |
| 5. Pruebas y resultados | 0,75 | **Muy alta** |
| 6. Limitaciones y trabajo futuro | 0,25 | Media |
| 7. Conclusiones y reflexiones individuales | 0,4 | Alta |
| 8. Referencias | 0,1 | Alta |
| **Total** | **5,0** | |

---

## Portada y resumen ejecutivo (0,5 página)

**Debe incluir:**

- Título, asignatura, sigla, sección, nombre del autor, docente, fecha.
- Resumen de 120–150 palabras con esta estructura:
  1. Problema: la mesa de ayuda recibe consultas repetitivas y la EP1 resolvía
     solo coincidencias léxicas.
  2. Solución: agente ReAct con LangChain/LangGraph, ChromaDB, embeddings y
     siete herramientas.
  3. Resultado: recuperación semántica con erratas, memoria multi-turno,
     cálculo de plazos y generación de borradores.
  4. Evidencia: 22 pruebas automatizadas y demo con traza de decisiones.
- 4–5 palabras clave: *agente LLM, ReAct, RAG semántico, ChromaDB, memoria
  conversacional*.

**No incluir** capturas ni tablas en el resumen.

---

## 1. Contexto y problema (0,5 página)

**Objetivo:** justificar por qué la solución de la EP1 ya no es suficiente.

**Contenido mínimo:**

1. **Contexto organizacional simulado:** Mesa de Ayuda de Duoc UC; consultas
   frecuentes sobre matrícula, becas, asistencia, pagos y trámites.
2. **Solución EP1:** Streamlit + TF-IDF + Qwen3 vía Groq + prompt rígido +
   funciones externas de fecha/feriados.
3. **Limitaciones observadas** (usar evidencia, no opiniones):
   - La búsqueda léxica falla con erratas y sinónimos no mapeados
     (`"asta"`, `"ramo"`, `"plata"`).
   - El prompt “solo responde con el contexto” impide pedir aclaraciones o
     encadenar pasos.
   - Las herramientas se invocaban por heurísticas (`if "feriado" in consulta`),
     no por decisión del modelo.
   - No había memoria de documentos ni continuidad de tareas.
4. **Pregunta de diseño:** ¿cómo evolucionar el RAG a un agente que decida,
   recuerde y actúe sin perder trazabilidad ni control anti-alucinación?

**Evidencia sugerida:** una tabla de 3 filas con “consulta / respuesta EP1 /
problema”. Ejemplo:

| Consulta | EP1 | Problema |
|---|---|---|
| `asta cuando puedo retirar un ramo` | No recupera la Sección 2.3 | Dependencia de coincidencia exacta |
| “¿y eso aplica a mi carrera?” | No usa el turno anterior | Sin memoria efectiva |
| “hazme el borrador” | No tiene herramienta de escritura | Solo consulta |

---

## 2. Objetivos y alcance (0,25 página)

**Objetivo general:** refactorizar el asistente de la EP1 en un agente funcional
capaz de integrar consulta, escritura y razonamiento, con memoria de corto y
largo plazo.

**Objetivos específicos (medibles):**

1. Reemplazar TF-IDF por embeddings + ChromaDB y demostrar tolerancia a erratas.
2. Integrar LangChain/LangGraph con al menos tres herramientas y una de escritura.
3. Implementar memoria conversacional y memoria de artefactos.
4. Implementar un esquema ReAct con planificación y aclaraciones.
5. Documentar la orquestación y validar con pruebas automatizadas y demo.

**Alcance:** prototipo académico, corpus de 35 fragmentos, un usuario por sesión,
feriados de Chile. **Fuera de alcance:** autenticación institucional, base de
datos de estudiantes real, escalamiento multiusuario y despliegue en producción.

---

## 3. Arquitectura y decisiones de diseño (1,5 páginas)

### 3.1 Vista general (0,5 página)

Insertar el **diagrama de orquestación** de `docs/arquitectura.md` (versión
Mermaid o exportada a PNG). Describir en un párrafo el flujo:

> Interfaz → agente ReAct → memoria de corto plazo → enrutamiento a tools →
> ChromaDB / API / sistema de archivos → respuesta + traza.

Incluir una **tabla de componentes** (5–7 filas): interfaz, agente, memoria,
vector store, tools, fuentes externas, pruebas.

### 3.2 Framework: LangChain/LangGraph (0,4 página)

**Argumentos que deben aparecer:**

- **Tool calling nativo:** `@tool` genera el esquema de argumentos y el modelo
  decide; no hay `if/elif` por intención.
- **Grafo ReAct con estado:** LangGraph controla el ciclo razón → acto →
  observación, el límite de iteraciones y la trazabilidad.
- **Compatibilidad:** Groq/GPT-OSS 120B usa el cliente compatible con OpenAI;
  Gemini 3.5 se integra con `ChatGoogleGenerativeAI`, que conserva las firmas de
  pensamiento exigidas por el tool calling. Cambiar de proveedor no exige
  reescribir el agente.
- **Escalabilidad:** agregar una herramienta es agregar un `@tool` a la lista;
  la memoria y el vector store son reemplazables.
- **Alternativas evaluadas:** bucle propio (más control, más código y errores),
  Haystack (válido, pero el autor ya tenía experiencia con LangChain),
  AutoGen (orientado a multiagente, sobredimensionado para este caso).

**Evidencia:** fragmento de `construir_agente` con `create_agent`, tools y
`system_prompt`. No pegar más de 10 líneas.

### 3.3 Memoria (0,3 página)

Dos capas + artefactos:

| Tipo | Implementación | Qué resuelve | Evidencia |
|---|---|---|---|
| Corto plazo | Ventana de mensajes LangChain (`deque`, 8 turnos) | “¿y eso?”, “¿y en mi caso?” | `chatbot/memoria.py` |
| Largo plazo | ChromaDB persistente (35 fragmentos) | Consultar reglamentos tras reiniciar | `chatbot/conocimiento.py` |
| Artefactos | `documentos/registro.json` | Recuperar un borrador de turnos anteriores | `chatbot/documentos.py` |

**Justificación:** `ConversationBufferMemory` es legado en LangChain 1.x; la
ventana de mensajes es su reemplazo recomendado y permite controlar tokens,
persistir y limpiar por sesión. Se separa la memoria conversacional de la de
artefactos para que un documento no se pierda al recortar el historial.

### 3.4 Recuperación: TF-IDF → embeddings (0,3 página)

**Esta es la sección más importante para IE4/IE9.** Incluir:

1. **Cómo funcionaba TF-IDF:** bolsa de palabras, normalización, stopwords,
   singularización, sinónimos manuales, peso `tf × idf`.
2. **Por qué falla:** no captura semántica; una errata o un sinónimo no mapeado
   produce cero coincidencia; el mantenimiento de sinónimos no escala.
3. **Cómo funcionan los embeddings:** cada fragmento y consulta se proyectan en
   un espacio vectorial; la similitud coseno mide cercanía semántica. E5
   multilingüe usa prefijos `query:` / `passage:`.
4. **Pipeline:** fragmentación por subsección → vectorización → ChromaDB →
   top-k → umbral 0,82 → margen 0,02 → contexto.
5. **Evidencia empírica:** tabla comparativa con la consulta con errata
   (`0.827`), asistencia (`0.911`), fuera de dominio (sin resultados).
6. **Costo:** modelo local de ~470 MB, primera descarga; inferencia en CPU;
   alternativa de API de embeddings si se requiere.

**Tabla sugerida:**

| Criterio | TF-IDF | Embeddings E5 |
|---|---|---|
| Unidad | Token | Vector semántico |
| Erratas | No tolera sin sinónimo | Tolera por cercanía |
| Sinónimos | Lista manual | Aprendidos |
| Corpus nuevo | Recalcular IDF | Reindexar |
| Explicabilidad | Alta (términos) | Media (sección + score) |
| Costo | Muy bajo | Descarga + CPU |

### 3.5 Herramientas y planificación (0,2 página)

Tabla de las 7 tools (nombre, tipo, cuándo se usa). Explicar la secuencia
`buscar_reglamentos → calcular_plazo → redactar_borrador` como ejemplo de
planificación multi-etapa. Mencionar el límite de 18 iteraciones y los
reintentos ante 429.

---

## 4. Implementación del agente (0,75 página)

**Objetivo:** mostrar que el diseño se llevó a código, sin convertir el informe
en un listado de archivos.

### 4.1 Organización del código (0,2 página)

Tabla breve:

| Módulo | Responsabilidad |
|---|---|
| `ajustes.py` | Configuración y entorno |
| `conocimiento.py` | Embeddings, ChromaDB, búsqueda |
| `memoria.py` | Ventana conversacional |
| `documentos.py` | Plantillas y registro de borradores |
| `herramientas.py` | Funciones de dominio + `@tool` |
| `agente.py` | Grafo ReAct, prompt, extracción de traza |
| `web.py` | Interfaz Streamlit |

### 4.2 Prompt y toma de decisiones (0,25 página)

Resumir las reglas del system prompt:

- dato institucional → buscar antes de afirmar;
- plazo → buscar + calcular, nunca mental;
- documento → confirmar datos + fundamento + `redactar_borrador`;
- ambigüedad → máximo 2 preguntas;
- sin evidencia → derivar;
- datos sensibles → no pedir, usar marcadores.

Incluir **una** captura de la traza ReAct de la interfaz (plan → tool →
observación). Es la evidencia visual de IE7.

### 4.3 Herramienta de escritura (0,15 página)

Describir el contrato de `redactar_borrador`: entradas, plantillas, referencias
normativas, marcadores `[RUT]`, guardado y registro. Explicar por qué se usan
plantillas en lugar de generación libre: control, trazabilidad y ausencia de
datos inventados.

### 4.4 Interfaz (0,15 página)

Captura de pantalla con: respuesta, panel de fuentes con relevancia, traza y
botón de descarga. Señalar que la traza es la evidencia de autonomía.

---

## 5. Pruebas y resultados (0,75 página)

**Objetivo:** demostrar con evidencia, no con adjetivos.

### 5.1 Estrategia de pruebas (0,2 página)

- **Unitarias:** fragmentación, búsqueda semántica, tools, memoria, borradores.
- **Integración:** orquestación con un agente falso que simula la traza
  (sin consumir API).
- **End-to-end:** servidor OpenAI simulado que ejecuta el ciclo completo
  (buscar → calcular → redactar) y valida 4 llamadas al modelo.
- **UI:** `streamlit.testing.AppTest` para renderizado y manejo de errores.
- **Manuales:** demo guiada con casos del §5.2.

### 5.2 Tabla de resultados (0,35 página)

| # | Caso | Entrada | Resultado | Evidencia |
|---|---|---|---|---|
| 1 | Errata semántica | `asta cuando puedo retirar un ramo` | Sección 2.3, semana 8, score 0.827 | Test + captura |
| 2 | Asistencia | `asistencia minima para aprovar` | 75% / 85%, score 0.911 | Test |
| 3 | Fuera de dominio | `tutorias de surf` | Sin resultados | Test |
| 4 | Memoria | “¿y cuántos días eran?” | Recupera el turno anterior | Test de memoria |
| 5 | Multi-tool | justificar + borrador | 3 tools, 4 llamadas, archivo generado | Test e2e |
| 6 | Feriados | consulta de feriados | Lista desde date.nager.at | Test con mock/real |
| 7 | Plazo | 20/10 + 3 días hábiles | 23/10/2026 | Test |
| 8 | UI sin API key | abrir app | Aviso claro, sin excepción | AppTest |

**Métricas sugeridas:** 22 pruebas OK; latencia de recuperación (~0,05 s por
consulta después de cargar el modelo); latencia total dependiente del proveedor;
tamaño del índice (35 vectores, 384 dimensiones).

### 5.3 Análisis (0,2 página)

- La recuperación semántica resolvió el caso que motivó el cambio (errata).
- El agente usó herramientas en el orden esperado sin reglas `if/elif`.
- La memoria permitió resolver referencias y recuperar documentos.
- El umbral evitó respuestas inventadas en temas fuera de dominio.
- Limitación: el LLM puede elegir una tool subóptima; la traza permite
  auditarlo y el prompt lo guía.

---

## 6. Limitaciones y trabajo futuro (0,25 página)

**Limitaciones honestas:**

1. Corpus pequeño (35 fragmentos) y estático; no cubre todas las carreras.
2. El modelo de embeddings se ejecuta en CPU; la primera carga es lenta.
3. La memoria es por sesión; no hay autenticación ni perfiles persistentes.
4. Los borradores son plantillas: requieren revisión humana y datos del
   estudiante.
5. La calidad depende del proveedor del LLM y de sus límites de tasa.
6. El umbral de relevancia está calibrado para E5; cambiarlo exige recalibrar.

**Trabajo futuro:**

- Checkpointer persistente de LangGraph (`SqliteSaver`) con `thread_id`.
- Reranking con cross-encoder para mayor precisión.
- Filtros por carrera/sede en ChromaDB.
- Panel de administración para actualizar reglamentos.
- Evaluación con RAGAS o métricas de fidelidad/contexto.
- Despliegue con autenticación y trazabilidad LangSmith.

---

## 7. Conclusiones y reflexiones individuales (0,4 página)

**Estructura sugerida:**

1. **Conclusión técnica (autor, 3–4 oraciones):** qué se logró, con qué
   evidencia y qué se aprendió sobre agentes.
2. **Reflexión individual (obligatoria, sin IA):**
   - ¿Qué aprendí sobre la diferencia entre RAG y agente?
   - ¿Qué decisión de diseño defendería y por qué?
   - ¿Qué error o limitación me obligó a cambiar el enfoque?
   - ¿Cómo contribuí al proyecto?

> **No usar IA para esta sección.** La pauta lo prohíbe explícitamente. Escribe
> en primera persona, con ejemplos concretos de tu trabajo.

---

## 8. Referencias (0,1 página)

Usar APA 7. Mínimo 6 fuentes:

1. LangChain. (2025). *LangChain documentation*.
2. LangGraph. (2025). *LangGraph documentation*.
3. Chroma. (2025). *Chroma documentation*.
4. Wang, L. et al. (2024). *Multilingual E5 text embeddings* (arXiv).
5. Yao, S. et al. (2023). *ReAct: Synergizing reasoning and acting in language
   models* (ICLR).
6. Salton, G., & Buckley, C. (1988). Term-weighting approaches in automatic
   text retrieval.
7. Nager.Date. (2025). *Public holidays API*.
8. Streamlit. (2025). *Streamlit documentation*.
9. Google. (2025). *Gemini API documentation*. https://ai.google.dev/gemini-api/docs
10. Groq. (2025). *Groq API documentation*. https://console.groq.com/docs

Citar en el texto con (Autor, año). No incluir URLs sueltas sin formato.

---

## Anexo sugerido (no cuenta para las 5 páginas, si el docente lo permite)

- **A. Evidencia de pruebas:** salida de `python -m unittest discover -s tests -v`.
- **B. Diagrama de secuencia** de la tarea multi-etapa.
- **C. Ejemplo de borrador generado** (con datos ficticios).
- **D. Declaración de uso de IA:** herramienta usada, para qué y cómo se
  validó. Incluir el enlace a https://bibliotecas.duoc.cl/ia.

---

## Checklist final antes de entregar

- [ ] El informe tiene **máximo 5 páginas** (revisar el PDF, no el Word).
- [ ] El diagrama de orquestación se ve nítido y tiene título (“Figura 1”).
- [ ] La tabla TF-IDF vs. embeddings tiene evidencia numérica.
- [ ] Se explica **por qué** LangChain/LangGraph, no solo que se usó.
- [ ] Se distingue memoria de corto plazo, largo plazo y artefactos.
- [ ] Se muestra una traza ReAct real (captura o tabla).
- [ ] Las pruebas incluyen el caso con errata y el caso fuera de dominio.
- [ ] Las referencias están en APA 7 y se citan en el texto.
- [ ] Las reflexiones individuales están escritas sin IA.
- [ ] El repositorio tiene README, `.env.example`, requirements y el código
      ejecutable.
- [ ] El enlace del repositorio está probado en una ventana de incógnito.
