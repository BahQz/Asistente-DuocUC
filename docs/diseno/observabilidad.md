# Bocetos de Diseño y Arquitectura de Observabilidad (EP3)

Este documento contiene los diagramas técnicos de diseño de arquitectura, secuencia de ejecución, modelo de datos y wireframes del dashboard de observabilidad para el agente Duqui.

---

## 1. Arquitectura General del Sistema de Observabilidad

El sistema incorpora tres capas concéntricas: **Guardrails deterministas** (entrada y salida), **Instrumentación de callbacks** en el ciclo ReAct, y **Persistencia estructurada thread-safe en JSONL**, desacoplada de la interfaz de usuario.

```mermaid
flowchart TD
    User([Estudiante / Usuario]) -->|Consulta cruda| UI["Interfaz Web Streamlit / CLI<br/>web.py"]
    UI -->|Consulta| G_IN["🛡️ Guardrail de Entrada<br/>chatbot.seguridad"]
    
    subgraph SeguridadEntrada ["Seguridad de Entrada"]
        G_IN -->|Detección & Enmascaramiento| PII["Filtro PII: [RUT], [CORREO], [TELEFONO]"]
        PII -->|Análisis Determinista| INY{"¿Prompt Injection?"}
        INY -->|Severidad Alta| BLOQ_IN["🛑 Bloqueo Preventivo<br/>Mensaje Fijo Institucional"]
        INY -->|Baja / Media| SAFE_TEXT["Texto Seguro Normalizado"]
    end

    BLOQ_IN -->|Fin Turno 0 tokens LLM| REG_TURNO
    SAFE_TEXT -->|Contexto Seguro| MEM[("Memoria Conversacional<br/>Historial Limpio")]

    subgraph AgenteReAct ["Orquestación del Agente ReAct"]
        MEM --> AG["Agente Duqui<br/>LangGraph create_agent"]
        AG <-->|Eventos de Invocación| CB["ManejadorObservabilidad<br/>BaseCallbackHandler"]
        CB -->|Defensa en profundidad| AUDIT["Auditor PII hacia Proveedor"]
        AG -->|Tool Calls| TOOLS["7 Herramientas Oficiales"]
        TOOLS -->|Retries sin cachear error| API["API Feriados / Fechas / ChromaDB"]
        TOOLS -->|Eventos herramienta| CB
    end

    AG -->|Respuesta preliminar| G_OUT["🛡️ Guardrail de Salida<br/>chatbot.seguridad"]

    subgraph SeguridadSalida ["Seguridad de Salida"]
        G_OUT --> FUGA{"¿Fuga Prompt?<br/>8-shingles"}
        FUGA -->|Sí| BLOQ_FUGA["🛑 Bloqueo Fuga<br/>Mensaje Institucional"]
        FUGA -->|No| VERIF{"¿Respaldo Normativo?"}
        VERIF -->|Grave: sin evidencia| BLOQ_RESP["🛑 Bloqueo Alucinación<br/>Derivación Oficial"]
        VERIF -->|Dudoso / OK| RESP_FINAL["Respuesta Final Validada"]
    end

    RESP_FINAL --> UI
    BLOQ_FUGA --> UI
    BLOQ_RESP --> UI

    subgraph Telemetria ["Capa de Telemetría JSONL"]
        CB -.->|etapas: llm, tool| WRITER["Escritor JSONL Thread-Safe<br/>observabilidad.registro"]
        G_IN -.->|eventos seguridad| WRITER
        G_OUT -.->|eventos seguridad| WRITER
        TOOLS -.->|retrieval / api_externa| WRITER
        REG_TURNO["Registro de Turno"] -.-> WRITER
        PSUTIL["Métricas Hardware (psutil)"] -.-> WRITER
        WRITER --> LOGS[("logs/eventos.jsonl")]
    end

    LOGS --> DASH["📊 Dashboard Observabilidad<br/>pages/1_Observabilidad.py"]
```

---

## 2. Diagrama de Secuencia de un Turno

Muestra el flujo sincrónico desde que ingresa la consulta hasta la persistencia y respuesta:

```mermaid
sequenceDiagram
    autonumber
    actor Estudiante
    participant UI as Interfaz (web.py)
    participant Agente as AgenteDuocUC (agente.py)
    participant Seg as Seguridad (seguridad.py)
    participant CB as CallbackHandler (callbacks.py)
    participant LLM as Proveedor Groq (LLM)
    participant Tools as Herramientas (herramientas.py)
    participant Log as Registro JSONL (registro.py)

    Estudiante->>UI: Ingresa consulta ("Mi RUT es 12.345.678-5...")
    UI->>Agente: responder(consulta)
    Agente->>Log: iniciar_traza(session_id, origen) -> trace_id
    
    rect rgb(240, 248, 255)
    Note over Agente,Seg: 1. Guardrail de Entrada
    Agente->>Seg: enmascarar(consulta)
    Seg-->>Agente: texto_seguro ("[RUT]"), conteos_pii
    Agente->>Log: registrar("seguridad", pii_enmascarado)
    Agente->>Seg: analizar_inyeccion(texto_seguro)
    Seg-->>Agente: {severidad: "baja", reglas: []}
    end

    rect rgb(255, 250, 240)
    Note over Agente,LLM: 2. Invocación ReAct con Callbacks
    Agente->>Agente: _invocar(historial + [HumanMessage(texto_seguro)])
    Agente->>CB: on_chat_model_start (audita mensajes salientes)
    CB->>Log: registrar("seguridad", pii_hacia_proveedor: 0)
    Agente->>LLM: invoke(messages)
    LLM-->>Agente: AIMessage(tool_calls=[buscar_reglamentos])
    CB->>Log: registrar("etapa", llm, tokens_prompt, duracion)
    
    Agente->>Tools: buscar_reglamentos(consulta)
    Tools->>Log: registrar("retrieval", candidatos, top1_score, decision)
    Tools-->>Agente: ToolMessage(fragmentos)
    CB->>Log: registrar("etapa", herramienta, args_masc, duracion)

    Agente->>LLM: invoke(messages + ToolMessage)
    LLM-->>Agente: AIMessage("La asistencia mínima es 75%...")
    CB->>Log: registrar("etapa", llm, tokens_completion, duracion)
    end

    rect rgb(245, 255, 245)
    Note over Agente,Seg: 3. Guardrail de Salida
    Agente->>Seg: detectar_fuga_prompt(respuesta, PROMPT_SISTEMA)
    Seg-->>Agente: False
    Agente->>Seg: verificar_respaldo(respuesta, eventos, fuentes)
    Seg-->>Agente: {nivel: "ok", afirmaciones: ["75%"]}
    end

    Agente->>Agente: memoria.agregar(texto_seguro, respuesta)
    Agente->>Log: registrar_recursos("turno", rss_mb, cpu)
    Agente->>Log: registrar("turno", latencia_total, tokens, herramientas)
    Agente-->>UI: ResultadoAgente(respuesta, fuentes, trace_id, metricas)
    UI-->>Estudiante: Renderiza respuesta, fuentes y chip de telemetría
```

---

## 3. Modelo de Datos de Eventos (JSONL)

El contrato del registro se basa en un envoltorio común con 8 subtipos de eventos validados estrictamente por `observabilidad/esquema.py`:

```mermaid
classDiagram
    class EnvoltorioEvento {
        +int v = 1
        +string ts
        +string trace_id
        +string session_id
        +string run_id
        +string origen
        +string tipo
        +dict datos
    }

    class EventoTurno {
        +string consulta_masc
        +string resultado
        +float latencia_total_ms
        +bool turno_frio
        +int n_llamadas_llm
        +int tokens_prompt
        +int tokens_completion
        +int tokens_total
        +bool tokens_estimados
        +list herramientas
        +int n_herramientas
        +bool abstencion
        +bool derivacion
        +list fuentes
        +float top1_score
        +int respuesta_chars
        +string error_categoria
        +string modelo
        +int turnos_memoria
    }

    class EventoEtapa {
        +string nombre
        +string componente
        +dict detalle
        +float offset_ms
        +float duracion_ms
        +bool ok
    }

    class EventoRetrieval {
        +string consulta_masc
        +int top_k
        +float umbral
        +float margen
        +list candidatos
        +list aceptados
        +int n_aceptados
        +float top1_score
        +float distancia_a_umbral
        +string decision
        +bool zona_gris
        +float embedding_ms
        +float chroma_ms
        +float total_ms
    }

    class EventoSeguridad {
        +string control
        +string accion
        +string severidad
        +dict detalle
    }

    class EventoError {
        +string categoria
        +string componente
        +string mensaje_masc
        +int reintento
        +bool recuperado
    }

    class EventoRecursos {
        +string momento
        +float rss_mb
        +float delta_rss_mb
        +float cpu_proceso_pct
        +float cpu_sistema_pct
        +int hilos
    }

    EnvoltorioEvento o-- EventoTurno
    EnvoltorioEvento o-- EventoEtapa
    EnvoltorioEvento o-- EventoRetrieval
    EnvoltorioEvento o-- EventoSeguridad
    EnvoltorioEvento o-- EventoError
    EnvoltorioEvento o-- EventoRecursos
```

---

## 4. Wireframes Textuales del Dashboard (`pages/1_Observabilidad.py`)

A continuación se presentan los esquemas visuales en texto de las 7 pestañas del dashboard interactivo:

### Tab 1: Resumen de Rendimiento
```
+---------------------------------------------------------------------------------------------------+
| [📊 Turnos: 45]  [✅ Éxito: 97.8%]  [⚡ P50: 1.2s]  [⚡ P95: 3.4s]  [🪙 Tokens: 54,200]             |
| [🪙 Media: 1,204] [🛑 Bloqueo: 4.4%] [📚 Abstención: 8] [📞 Derivación: 5] [⚠️ Zona Gris: 2]     |
+---------------------------------------------------------------------------------------------------+
| [GRÁFICO PLOTLY: Latencia Total por Turno (ms) con líneas P50 y P95]                              |
|   ms                                                                                              |
| 3500|                  *                                      * (P95: 3400 ms)                    |
| 1200|  *   *   *   *       *   *   *   *   *   *   *   *  -- (P50: 1200 ms)                    |
|  200|_______________________________________________________                                      |
|      #1  #5  #10  #15  #20  #25  #30  #35  #40  #45 (Turnos)                                      |
+---------------------------------------------------------------------------------------------------+
```

### Tab 2: Precisión y Consistencia
```
+---------------------------------------------------------------------------------------------------+
| [🎯 Precision@1: 91.2%]  [🎯 Hit@k: 97.1%]  [🛡️ Abstención Correcta: 100%] [⚠️ Falsos Rechazos: 3.2%] |
+-------------------------------------------------+-------------------------------------------------+
| Evolución Temporal de Top-1 Score Coseno        | Barrido de Umbral (Simulación 0.76 - 0.92)      |
|  1.0|     *       *        *   (Respuesta)      |   % |                                           |
| 0.85|========= [Zona Gris ±0.03] ============== | 100%|  ---- Abstención Correcta                |
| 0.82|--------- [Umbral 0.82] ------------------ |     |  .... Falsos Rechazos                     |
| 0.60|         x        x       (Abstención)     |   0%|________________                           |
|     +------------------------------------------ |     0.76      0.82      0.90 (Umbral)           |
+-------------------------------------------------+-------------------------------------------------+
| Tabla: Consistencia Semántica por Grupo (asistencia, retiro, justificacion, biblioteca)           |
+---------------------------------------------------------------------------------------------------+
```

### Tab 3: Latencia y Recursos
```
+-------------------------------------------------+-------------------------------------------------+
| Desglose por Componente (Boxplot)               | Desglose Acumulado por Turno (Barras Apiladas)  |
| ms |                                            | ms |                                            |
|    |   [guardrail]  [retrieval]  [llm]  [tool]  |    |  [LLM] [Tool] [Retrieval] [Guardrail]       |
+-------------------------------------------------+-------------------------------------------------+
| Consumo de Hardware en el Tiempo: RAM RSS (MB) en eje izquierdo y CPU (%) en eje derecho         |
+---------------------------------------------------------------------------------------------------+
```

### Tab 4: Herramientas y Errores
```
+-------------------------------------------------+-------------------------------------------------+
| Frecuencia de las 7 Herramientas (Barras Horiz) | Distribución de Errores por Categoría (Donut)   |
| buscar_reglamentos   ================== (38)    |  [Rate Limit 429] 60%                           |
| consultar_feriados   ====== (8)                 |  [Timeout]        25%                           |
| redactar_borrador    ==== (5)                   |  [Otro]           15%                           |
| leer_borrador        = (1)                      |                                                 |
+-------------------------------------------------+-------------------------------------------------+
| Tabla Histórica Filtrable de Errores y Reintentos Recuperados                                     |
+---------------------------------------------------------------------------------------------------+
```

### Tab 5: Seguridad y Privacidad
```
+-------------------------------------------------+-------------------------------------------------+
| Eventos de Seguridad por Control y Acción       | Verificación de Privacidad (Zero Data Leakage)  |
| [pii: enmascarado]       ======== (14)          | PII cruda enviada al LLM: 0 (CERO GARANTIZADO)  |
| [inyeccion: bloqueado]   === (4)                | PII cruda en logs:        0 (CERO GARANTIZADO)  |
| [respaldo: alertado]     == (2)                 | PII cruda en memoria:     0 (CERO GARANTIZADO)  |
+-------------------------------------------------+-------------------------------------------------+
| Desglose de Datos Enmascarados: RUT (8) | Correo (4) | Teléfono (3) | Tarjeta (1) | Clave (1)     |
+---------------------------------------------------------------------------------------------------+
```

### Tab 6: Detección de Anomalías
```
+---------------------------------------------------------------------------------------------------+
| Reglas Nombradas Detectadas (Sin texto interpretativo de IA - Datos estadísticos crudos)          |
| | Trace ID   | Regla Activada            | Valor Observado                                      | |
| |------------|---------------------------|------------------------------------------------------| |
| | 9f3c1a...  | latencia_sobre_p95        | 3520.4 ms (p95=3410.2 ms)                            | |
| | 8a1b2c...  | racha_errores_ge_2        | 2 errores consecutivos (429 Rate Limit)              | |
| | c4d5e6...  | zona_gris                 | top1_score=0.818 (distancia=-0.002)                  | |
| | f7a8b9...  | muchas_herramientas       | 4 herramientas ejecutadas en un turno                | |
| [⬇️ Descargar anomalías .csv]                                                                     |
+---------------------------------------------------------------------------------------------------+
```

### Tab 7: Explorador de Trazas
```
+---------------------------------------------------------------------------------------------------+
| Selector de Traza: [ 9f3c1a82d0e4... (Consulta: "¿Cuál es la asistencia...?")                   ] |
|                                                                                                   |
| Diagrama de Gantt de la Traza:                                                                    |
| guardrail_entrada [===] (12 ms)                                                                   |
| llm (planificación)     [========] (840 ms)                                                       |
| retrieval                         [===] (45 ms)                                                   |
| llm (respuesta final)                 [===========] (1120 ms)                                     |
| guardrail_salida                                            [=] (8 ms)                            |
| 0 ms                     500 ms                    1000 ms                   2000 ms              |
|                                                                                                   |
| [Expandir JSON crudo de la traza]   [⬇️ Descargar traza .json]                                    |
+---------------------------------------------------------------------------------------------------+
```
