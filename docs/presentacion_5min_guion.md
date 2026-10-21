# Guion de Presentación (5 Minutos) — EP2 ISY0101

**Objetivo:** Mostrar autonomía, razonamiento y orquestación técnica en tiempo récord.

## Tiempos y Estructura
| Tiempo | Bloque | Slide | Puntos Clave |
|---|---|---|---|
| 0:00-0:45 | Introducción | 1-2 | Problema EP1 (fragilidad léxica) y evolución a Agente. |
| 0:45-1:45 | Arquitectura | 3 | LangGraph, 7 tools, 3 memorias. |
| 1:45-2:45 | RAG y Memoria | 4 | Score 0.892 (erratas), persistencia de documentos. |
| 2:45-4:15 | Demo en Vivo | (App) | "Justificar gripe de ayer + borrador". Narrar traza. |
| 4:15-5:00 | Conclusiones | 5 | Limitaciones, 22 tests OK y cierre. |

---

## Guion Detallado

### 1. Introducción (0:00-0:45)
"Buenos días. En la EP1 teníamos un buscador que fallaba si el alumno escribía 'asta' sin hache. Hoy presentamos a **Duqui**, un agente que no solo recupera información semántica, sino que **razona** y **actúa** para resolver trámites complejos."

### 2. Arquitectura y Orquestación (0:45-1:45)
"La orquestación se basa en LangGraph. No usamos reglas 'if/else'; el modelo (GPT-OSS 120B) decide qué herramienta usar según el contexto. Tenemos 7 herramientas, desde búsqueda institucional hasta cálculo de plazos y redacción de documentos."

### 3. Recuperación Semántica y Memoria (1:45-2:45)
"Pasamos de tokens a vectores con el modelo E5. Ahora toleramos erratas con una relevancia de 0.827. Implementamos tres capas de memoria: conversación (corto plazo), reglamentos (largo plazo) y artefactos (los borradores que el alumno ya generó)."

### 4. Demo en Vivo (2:45-4:15)
*(Escribir: "Falté ayer a una prueba por gripe, ¿cuánto plazo tengo y me haces el borrador?")*
"Mientras carga, observen la **traza ReAct**. El agente decide: 1. Buscar el plazo (3 días), 2. Calcular la fecha real usando la API de feriados, 3. Redactar usando una plantilla oficial. Todo es auditable."

### 5. Cierre (4:15-5:00)
"Validamos esto con 22 pruebas automatizadas. Sabemos que dependemos de la latencia del proveedor, pero la arquitectura es sólida y modular. Gracias por su atención."

---
**Plan B (Falla de API):** Mostrar capturas en `docs/assets/` y video de respaldo.
