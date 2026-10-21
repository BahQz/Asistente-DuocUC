# Guion de demostración — EP2 ISY0101

**Proyecto:** Duqui · Agente Estudiantil Duoc UC
**Duración:** 10 minutos (más preguntas)
**Formato:** demo en vivo con la interfaz Streamlit + una diapositiva de arquitectura
**Integrantes:** 1 (presentación individual; una misma persona cubre contexto y demo)
**Evidencia central:** traza ReAct visible en la interfaz, fuentes con relevancia y
borrador descargable.

> **Mensaje que la audiencia debe recordar al salir:**
> “Pasamos de un buscador léxico que solo acertaba cuando calzaban las palabras
> a un agente que **decide qué herramienta usar**, **recuerda la conversación** y
> **produce un documento**, sin perder la trazabilidad ni inventar datos
> institucionales.”

---

## 1. Objetivo de la demo

Demostrar, en este orden, los cuatro cambios que exige la EP2:

1. **Recuperación semántica real** (embeddings + ChromaDB), no TF-IDF.
2. **Agente ReAct** que elige herramientas por decisión del modelo, no por `if/elif`.
3. **Memoria** de corto plazo (conversación) y de artefactos (borradores).
4. **Planificación multi-etapa**: buscar requisito → calcular plazo → redactar.

La demo no es un recorrido por archivos: es un caso de uso estudiantil completo,
con la traza abierta como prueba de autonomía.

---

## 2. Reparto de roles

| Rol | Responsabilidad | Participa en |
|---|---|---|
| **Tú — contexto** | Problema, decisión de diseño, cierre y moderación de preguntas | 0:00–1:30 y 8:00–10:00 |
| **Tú — demo** | Ejecuta la demo, abre trazas y fuentes, explica lo que ocurre en pantalla | 1:30–8:00 |

> **Si presentas solo:** cambias de “sombrero” en los minutos indicados. Si
> alguien te acompaña, esa persona puede tomar el rol de demo y tú quedarte en
> contexto; el guion funciona igual.

**Regla de continuidad:** antes de cambiar de caso, deja la pantalla en el punto
exacto que vas a comentar; no abras una pestaña nueva ni reinicies la app en vivo.

**Regla de honestidad:** si algo falla, se dice. La pauta evalúa toma de
decisiones, no una demo perfecta.

---

## 3. Preparación (checklist)

### T-30 minutos

- [ ] `.env` con `LLM_API_KEY` real de Groq y `LLM_MODEL=openai/gpt-oss-120b`.
- [ ] `python verificar_proveedor.py` responde `[OK] El modelo respondió: OK`.
- [ ] Cuota del proveedor verificada (Groq free ≈1.000/día; Gemini free ≈20/día).
- [ ] Índice construido: `python construir_indice.py` → “35 vectores”.
- [ ] Modelo de embeddings ya descargado (evita esperar ~470 MB en vivo).
- [ ] “Calentar” el agente con una consulta cualquiera y luego **Limpiar conversación**.
- [ ] `documentos/` vacío o solo con el borrador que se quiere mostrar.
- [ ] Navegador en `http://localhost:8501`, zoom 110–125 %, una sola pestaña.
- [ ] Notificaciones del sistema y de Teams/WhatsApp desactivadas.
- [ ] Video de respaldo grabado (ver §7) y disponible sin conexión.
- [ ] Diapositiva con el diagrama de `docs/arquitectura.md` abierta.
- [ ] Cronómetro visible para el rol A.

### T-10 minutos

- [ ] Ejecutar `python -m streamlit run web.py` (no usar el comando `streamlit`
      suelto: puede no estar en el PATH).
- [ ] Verificar en la barra lateral: modelo, embeddings, “Ventana deslizante ·
      8 turnos” y “Estado del índice” con 35 fragmentos.
- [ ] Probar en voz baja la primera consulta y volver a limpiar.
- [ ] Cerrar sesión de pantalla completa y dejar el chat visible sin scroll.

### T-0

- [ ] Tú, en la diapositiva de arquitectura.
- [ ] La app enfocada y el cursor fuera del cuadro de texto.
- [ ] Micrófono probado. No compartir audio del sistema.

---

## 4. Run of show (10 minutos)

| Hora | Bloque | Quién | Qué se ve |
|---:|---|---|---|
| 0:00–0:30 | Hook y problema | Tú | Diapositiva: consulta con errata que la EP1 fallaba |
| 0:30–1:30 | Arquitectura y decisiones | Tú | Diagrama: UI → agente → tools → ChromaDB/API/archivos |
| 1:30–2:00 | **Caso 1: ambigüedad** | Tú | “¿Puedo retirarme?” → pregunta de aclaración |
| 2:00–3:00 | **Caso 2: errata semántica** | Tú | Consulta `asta cuando puedo retirar un ramo` + fuentes |
| 3:00–3:45 | **Caso 3: memoria conversacional** | Tú | “¿Y en la semana 10?” → conserva el tema |
| 3:45–6:30 | **Caso 4: multi-herramienta + borrador** | Tú | Buscar → calcular → redactar + descarga |
| 6:30–7:15 | **Caso 5: memoria de artefactos** | Tú | “¿Qué decía el borrador?” → recuperación |
| 7:15–8:00 | **Caso 6: anti-alucinación** | Tú | Tema fuera de dominio → deriva a mesa de ayuda |
| 8:00–9:15 | Lectura de la traza (IE7) | Tú | Plan, tools, argumentos, observaciones |
| 9:15–10:00 | Cierre y transición a preguntas | Tú | Mensaje final + limitaciones honestas |

**Presupuesto de latencia:** una consulta simple tarda 10–25 s; una consulta
multi-herramienta puede tardar 40–70 s. Mientras el spinner gira, **narrar** lo
que debería ocurrir; no quedarse en silencio. Si un turno supera 90 s, aplicar
el plan B (§7).

---

## 5. Guion detallado

### 0:00–0:30 · Hook y problema — Tú (contexto)

**Dice:**

> “En la EP1 teníamos un RAG que funcionaba con TF-IDF. Si el estudiante escribía
> exactamente las palabras del reglamento, respondía bien. Pero un estudiante
> real escribe ‘asta cuando puedo retirar un ramo’: ‘asta’ sin la hache y ‘ramo’
> en vez de ‘asignatura’. La EP1 no encontraba la sección correcta.”
>
> “Hoy vamos a mostrar la evolución: un agente que entiende la intención,
> decide qué herramienta usar, recuerda lo que ya conversamos y redacta el
> documento que el estudiante necesita.”

**No decir:** “es un chatbot con IA”. Decir **agente con herramientas y traza**.

---

### 0:30–1:30 · Arquitectura — Tú (contexto)

**Muestra:** diagrama de `docs/arquitectura.md`.

**Dice (guion de 60 s):**

> “La interfaz Streamlit mantiene la experiencia de la EP1. Debajo cambia el
> motor: LangChain 1.x y LangGraph construyen un grafo ReAct con
> `create_agent`. El modelo GPT-OSS 120B, vía Groq, recibe siete herramientas y decide
> cuál usar.”
>
> “Hay tres memorias: la conversación de los últimos 8 turnos; el reglamento
> indexado en ChromaDB con embeddings E5; y los borradores guardados en
> `documentos/` con un registro.”
>
> “La regla anti-alucinación es simple: todo dato institucional sale de
> `buscar_reglamentos`. Si no hay evidencia, el agente lo dice y deriva. Y cada
> decisión queda en la traza que van a ver en pantalla.”

**Transición:** “Paso a la demo.”

---

### 1:30–2:00 · Caso 1: ambigüedad — Tú (demo)

**Acción:** escribir en una conversación vacía:

> `¿Puedo retirarme?`

**Respuesta esperada:** una **pregunta de aclaración** con opciones concretas:
¿retiro de una **asignatura**, retiro de la **carrera** o retiro de una
**evaluación**? Máximo dos preguntas.

**Dice:**

> “Acá no adivina. El prompt le pide detectar datos faltantes y preguntar con
> opciones. Un RAG clásico habría respondido cualquier cosa con el fragmento más
> parecido.”

**Si el agente responde directo asumiendo “asignatura”:** no lo justificar;
decir “en este caso eligió la interpretación más probable; por eso la traza y la
posibilidad de corregirlo importan”. Luego continuar. No gastar más de 30 s.

**Transición:** “Le doy el dato que falta y, de paso, pruebo la errata.”

---

### 2:00–3:00 · Caso 2: errata semántica — Tú (demo)

**Acción:** escribir (es la respuesta a la aclaración anterior; las sugerencias
del inicio ya no están visibles):

> `asta cuando puedo retirar un ramo`

**Mientras carga, dice:**

> “Fíjense que la consulta tiene dos señales de un estudiante real: ‘asta’ sin
> hache y ‘ramo’ en vez de ‘asignatura’. La búsqueda no corrige la palabra:
> compara significado en un espacio vectorial. Y el agente ya sabe, por el turno
> anterior, que el tema es retiro.”

**Al responder, debe verse:**

- Respuesta con el **período de retiro**: sin registro hasta la **semana 8**;
  entre **semana 9 y 12** aparece con nota **“W”**; después de la **semana 12**
  no se permite.
- Cita **Sección 2.3**.
- Expander **📚 Fuentes consultadas** con `Sección 2.3 — Período de retiro de
  asignaturas` y relevancia cercana a **0.827**.

**Acción:** abrir “Fuentes consultadas” y señalar el número.

**Dice:**

> “La relevancia coseno es 0,827. El umbral configurado es 0,82: por eso entra
> como evidencia. Si estuviera por debajo, el agente no tendría respaldo y
> debería decirlo.”

**Énfasis:** no hubo sinónimos manuales ni corrección ortográfica. Es semántica.

---

### 3:00–3:45 · Caso 3: memoria conversacional — Tú (demo)

**Acción:** escribir en el mismo hilo:

> `¿Y si estoy en la semana 10?`

**Mientras carga, dice:**

> “No repito ‘retiro de asignaturas’. La pregunta depende del turno anterior.
> El agente recibe el historial y resuelve ‘y si estoy…’ con la memoria de corto
> plazo.”

**Respuesta esperada:** en la semana 10 el retiro **sí se permite**, pero queda
con nota **“W”** (retiro justificado); se mantiene la referencia a la Sección
2.3. **No** debe volver a explicar desde cero ni preguntar “¿retiro de qué?”.

**En la traza:** la consulta a `buscar_reglamentos` debe mencionar el **retiro de
asignatura** y la **semana 10**, no solo el texto literal “¿y si estoy en la
semana 10?”. Eso demuestra que el agente usó el historial para reformular la
búsqueda, no solo para redactar la respuesta.

**Dice:**

> “La memoria es una ventana de mensajes LangChain de 8 turnos, no
> `ConversationBufferMemory`, que es legado en LangChain 1.x. Se puede limpiar
> desde la barra lateral y no se mezcla con los documentos.”

---

### 3:45–6:30 · Caso 4: multi-herramienta + borrador — Tú (demo)

**Acción:** escribir (la sugerencia del inicio ya no estará visible después de
los casos anteriores):

> `Falté a una evaluación ayer por una gripe. ¿Cuál es el plazo para justificar y puedes redactar el borrador?`

> **Alternativa fija si se quiere reproducir el caso del informe:**
> `Falté a una evaluación el 20 de octubre por una gripe. ¿Cuántos días tengo para justificar y puedes redactar el borrador?`
> En ese caso el vencimiento esperado es **23/10/2026** (3 días hábiles desde el
> 20/10, sin feriados). Verificar que la fecha siga siendo futura al momento de
> la demo; si no, usar “ayer”.

**Mientras carga (30–60 s), narrar el plan esperado:**

> “Esto tiene tres etapas. Primero tiene que confirmar el plazo en el reglamento;
> después calcular la fecha real en días hábiles, excluyendo fines de semana y
> feriados; y recién entonces redactar. No debería calcular mentalmente.”

**Al terminar, abrir `🧠 Traza ReAct` y mostrar la secuencia.** Debe incluir:

1. `buscar_reglamentos` con una consulta sobre el **plazo para justificar una
   evaluación atrasada** (no el texto literal de la pregunta).
2. `calcular_plazo` con `dias_habiles: 3` y la fecha del hecho (o `consultar_fecha_actual`
   antes, si el estudiante dijo “ayer”).
3. `redactar_borrador` con `tipo: justificacion_inasistencia`, el motivo y el
   `fundamento` tomado de la búsqueda.

**Respuesta esperada:**

- Plazo: **3 días hábiles** desde la evaluación (Sección 4.3).
- Fecha de vencimiento calculada por la herramienta, con la convención “el conteo
  parte el día hábil siguiente”.
- Aviso de que el borrador quedó disponible y que debe completar los campos
  entre corchetes.

**Acción:** abrir **📄 Borrador generado**, leer en voz alta 2–3 líneas
(encabezado, fundamento y despedida) y mostrar el botón
**⬇️ Descargar borrador (.md)**. **No descargar** salvo que sobre tiempo.

**Dice:**

> “El borrador no lo inventa el modelo: lo genera una plantilla institucional
> con el fundamento que recuperó del reglamento. Los datos personales quedan como
> `[RUT]`, `[Carrera]` y `[Sede]` para que el estudiante los complete. Así
> evitamos que invente un RUT o una fecha.”

**Énfasis para IE1/IE5:** tres o cuatro herramientas encadenadas (incluida
`consultar_fecha_actual` si se usó “ayer”), sin `if "feriado" in consulta`. El
modelo eligió el orden.

---

### 6:30–7:15 · Caso 5: memoria de artefactos — Tú (demo)

**Acción:** escribir:

> `¿Qué decía el borrador que hiciste?`

**Respuesta esperada:** el agente usa `listar_borradores` y/o `leer_borrador`,
identifica el documento por su ID y resume su contenido. **No** vuelve a generar
otro borrador.

**Dice:**

> “Esta es la tercera memoria: los documentos sobreviven al recorte del historial
> porque están en disco y en un registro. Si mañana reinicio la app, el borrador
> sigue ahí.”

**Si el agente genera un borrador nuevo:** señalarlo como mejora pendiente
(prompt/IDs) y continuar. No improvisar una solución en vivo.

---

### 7:15–8:00 · Caso 6: anti-alucinación — Tú (demo)

**Acción:** escribir:

> `¿Cuál es la política de tutorías de surf?`

**Respuesta esperada:**

- Reconoce que **no cuenta con esa información**.
- **No** inventa una política, un horario ni un correo.
- Deriva a la **mesa de ayuda**: `soporte@duocuc.cl` / **600-300-4000**
  (Sección 9.1), o a la Dirección de Escuela.

**Dice:**

> “El corpus no tiene tutorías de surf. La búsqueda devuelve ‘sin resultados’ y
> el prompt prohíbe rellenar el vacío. Preferimos una abstención honesta a una
> respuesta plausible pero falsa.”

**Énfasis:** esto es una **decisión de diseño**, no una limitación accidental.

---

### 8:00–9:15 · Lectura de la traza — Tú

**Acción:** volver al caso 4 y dejar abierta la traza.

**Señala:**

- **Plan:** línea breve con la estrategia.
- **Herramienta + argumentos JSON:** qué decidió y con qué datos.
- **Observación:** qué devolvió la tool (sección, fecha, ID).
- **Fuentes:** sección y relevancia coseno.

**Dice:**

> “La traza es la diferencia entre ‘confiar en el chatbot’ y ‘auditar al agente’.
> Si mañana el modelo elige mal una herramienta, acá se ve. Por eso no ocultamos
> el razonamiento detrás de una respuesta bonita.”

**Frase de cierre técnico:**

> “Siete herramientas, tres memorias, 35 fragmentos, 22 pruebas automatizadas.
> El agente no siempre es perfecto, pero cada paso es observable.”

---

### 9:15–10:00 · Cierre — Tú (contexto)

**Dice:**

> “La EP1 respondía si la pregunta se parecía a las palabras del reglamento. La
> EP2 entiende la intención, planifica, usa herramientas y deja evidencia. Eso es
> un agente: no solo recupera información, **actúa sobre ella**.”
>
> “Las limitaciones las tenemos claras: corpus acotado, memoria por sesión,
> borradores que requieren revisión humana y dependencia del proveedor del
> modelo. Todo está en el informe y en el README.”
>
> “Quedamos atentos a sus preguntas.”

---

## 6. Frases de transición (para no improvisar)

| Situación | Frase |
|---|---|
| Antes de una consulta | “Voy a pedirle algo que un buscador léxico fallaría.” |
| Mientras carga | “Mientras responde, el agente está decidiendo si necesita una herramienta o si puede contestar directo.” |
| Al abrir la traza | “Acá está la decisión, no solo el resultado.” |
| Si la respuesta es buena | “Y fíjense que cita la sección: no pido que me crean, les muestro la fuente.” |
| Si la respuesta es incompleta | “Ese es un caso límite: el agente prefirió no inventar; la traza muestra por qué.” |
| Al cambiar de caso | “Ahora voy a probar la memoria / la escritura / el límite del corpus.” |

---

## 7. Planes de contingencia

### Plan A — La app responde, pero más lento de lo esperado

- Narrar el plan esperado mientras se espera.
- No hacer clic repetido en “Enviar”.
- Si un turno supera **90 s**, decir: “El proveedor está demorando; sigamos con la traza
  del caso anterior” y continuar. No reiniciar la app en vivo.

### Plan B — Error de API, cuota o timeout

1. **No** mostrar el traceback ni la clave.
2. Decir: “El proveedor del modelo no está respondiendo; la arquitectura es
   independiente del proveedor, así que mostramos la evidencia grabada.”
3. Abrir el **video de respaldo** (§7.1) o las capturas.
4. Continuar con la explicación de la traza y las pruebas.

### Plan C — El índice o el modelo de embeddings no cargan

- Ejecutar en la terminal visible: `python construir_indice.py --probar "asta cuando puedo retirar un ramo"`.
- Si falla por red, mostrar la salida de pruebas (`22 tests OK`) y el video.
- No borrar `.chroma/` en vivo.

### 7.1 Video de respaldo (grabar antes)

Duración objetivo: **2–3 minutos**, sin audio o con voz en off. Debe mostrar:

1. Consulta con errata y fuentes.
2. Seguimiento de memoria.
3. Traza del caso multi-herramienta.
4. Borrador generado y botón de descarga.
5. Respuesta de anti-alucinación.

Guardarlo como `docs/demo_respaldo.mp4` (o en la nube) y probarlo **sin
conexión** antes de la presentación. Si el archivo pesa demasiado para el
repositorio, dejarlo fuera y llevar una copia local.

### 7.2 Frase honesta si algo no se puede demostrar

> “Ese caso no lo pudimos ejecutar en vivo por una falla del proveedor. La
> evidencia está en las pruebas automatizadas y en la grabación; con gusto
> mostramos el código y la traza guardada.”

---

## 8. Preguntas probables del jurado

Responder en **20–30 segundos**, con una decisión y una evidencia. No leer.

| Pregunta | Respuesta breve |
|---|---|
| **¿Por qué LangChain/LangGraph y no un bucle propio?** | Porque `create_agent` ya implementa el ciclo ReAct con estado, tool calling nativo, límite de iteraciones y trazabilidad. Un bucle propio habría requerido reimplementar parsing, reintentos y estado; más código y más errores. |
| **¿Por qué no Haystack?** | Es una alternativa válida; el autor ya tenía experiencia con LangChain y el cliente OpenAI-compatible permitía usar Groq sin reescribir el agente. Gemini queda como alternativa con integración nativa. La decisión está justificada en el informe. |
| **¿Qué cambió respecto de la EP1?** | TF-IDF → embeddings E5 + ChromaDB; heurísticas `if/elif` → tool calling; prompt rígido → ReAct con planificación y aclaraciones; sin memoria → ventana de 8 turnos + artefactos. |
| **¿Cómo evitan las alucinaciones?** | Tres capas: recuperación con umbral 0,82, prompt que prohíbe afirmar sin `buscar_reglamentos` y herramientas deterministas para fechas y documentos. Si no hay evidencia, el agente se abstiene. |
| **¿Qué pasa si la búsqueda no supera el umbral?** | Devuelve “sin resultados” y el agente deriva a la mesa de ayuda. Preferimos no responder a inventar. |
| **¿Por qué 0,82?** | Se calibró con consultas del dominio y casos fuera de dominio: recupera la errata con 0,827 y deja fuera temas ajenos. Es un parámetro configurable, no una verdad absoluta. |
| **¿La memoria es persistente?** | La conversación vive en la sesión (ventana de 8 turnos); la clase permite guardarla en `.historial/sesion.json`, aunque la UI de la demo no lo activa. Los documentos y el índice sí persisten en disco. Un checkpointer SQLite es trabajo futuro. |
| **¿Por qué plantillas y no generación libre?** | Control y trazabilidad: el documento cita el reglamento, usa marcadores `[RUT]` y no inventa datos personales. La generación libre es más flexible, pero menos auditable. |
| **¿Cómo prueban que el agente usa las tools?** | 22 pruebas: unitarias de retrieval/tools/memoria, integración con agente falso y end-to-end con un servidor OpenAI simulado que verifica la secuencia buscar → calcular → redactar. Además, la traza en vivo. |
| **¿Qué pasa si el modelo elige la tool equivocada?** | La traza lo hace visible; el prompt guía el orden y las tools tienen descripciones estrictas. Es una limitación real de los agentes LLM: por eso hay supervisión humana. |
| **¿Escala a producción?** | El prototipo es de un usuario por sesión. Para producción faltan autenticación, perfiles, checkpointer persistente, filtros por carrera/sede y evaluación con RAGAS. |
| **¿Cuánto cuesta?** | Embeddings locales en CPU (sin costo por consulta); el LLM usa el free tier de Groq, sujeto a la cuota vigente. El índice son 35 vectores de 384 dimensiones. |
| **¿Usaron IA para el informe?** | Sí, para apoyo de redacción y revisión, declarado en el apartado de uso de IA. Las reflexiones individuales se redactan sin IA, como exige la pauta. |

**Si no saben una respuesta:**

> “No lo medimos en esta entrega; está en trabajo futuro. Lo que sí podemos
> afirmar es [dato con evidencia].”

No inventar métricas ni benchmarks.

---

## 9. Mapa de indicadores (para autoevaluación)

| Indicador | Momento de la demo | Evidencia |
|---|---|---|
| **IE1** Herramientas autónomas | Caso 4 | Traza con 3–4 tools encadenadas |
| **IE2** Framework adecuado | 0:30–1:30 | `create_agent` + LangGraph en el diagrama |
| **IE3** Memoria de contenido | Casos 3 y 5 | Seguimiento y recuperación de borrador |
| **IE4** Recuperación semántica | Caso 2 | Errata → Sección 2.3, score 0,827 |
| **IE5** Planificación y prioridades | Caso 4 | Buscar → calcular → redactar |
| **IE6** Informe, diagramas y flujos | 0:30–1:30 | Diagrama + README |
| **IE7** Toma de decisiones demostrada | 8:00–9:15 | Lectura de la traza |
| **IE8** Diagrama + README | 0:30–1:30 | `docs/arquitectura.md` |
| **IE9** Justificación de componentes | Preguntas | Decisiones y alternativas |
| **IE10** Lenguaje técnico | Toda la demo | “tool calling”, “embeddings”, “traza”, “umbral” |

---

## 10. Checklist final de 60 segundos (antes de entrar)

- [ ] App abierta y “Limpiar conversación” ya aplicado.
- [ ] La barra lateral muestra **35 fragmentos**.
- [ ] El diagrama está en la diapositiva correcta.
- [ ] El video de respaldo está accesible en 2 clics.
- [ ] Sé qué caso sigue si el anterior falla.
- [ ] Cronómetro en 10:00.
- [ ] Tienes claras tus respuestas a las preguntas del jurado.

**Regla de oro:** la demo dura **10 minutos**, no 15. Si el caso 5 o 6 se
complica, se corta uno y se protege la traza y el cierre. Es mejor terminar con
tiempo que apurar el final.
