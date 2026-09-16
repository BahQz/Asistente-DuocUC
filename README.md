# Asistente Estudiantil Duoc UC

> Proyecto académico de un chatbot con IA que responde dudas de estudiantes de
> Duoc UC basándose **únicamente** en una base de conocimiento institucional
> delimitada. Si la respuesta no está en esa base, el asistente lo indica y
> deriva a la mesa de ayuda.

**Autor:** Benjamín Quiroz

## Descripción

Este asistente conversacional apoya a los estudiantes de Duoc UC con consultas
sobre admisión y matrícula, calendario académico, becas y beneficios,
evaluaciones y asistencia, biblioteca, bienestar estudiantil, práctica y
titulación, aranceles y pagos, canales de contacto y convivencia.

Además puede consultar la fecha actual y los feriados de Chile (API pública
`date.nager.at`) para ayudar a calcular plazos académicos.

La regla central es **anti-alucinación**: el asistente solo responde con la
información recuperada de la base de conocimiento. Cuando el tema no aparece,
responde que no cuenta con esa información.

### Tecnologías

- **Groq** — inferencia del modelo Qwen3 vía API compatible con OpenAI
- **OpenAI SDK** — cliente usado contra el endpoint de Groq
- **RAG léxico TF-IDF** — recuperación ponderada por frecuencia inversa, con
  normalización de acentos, stopwords, singularización y sinónimos
- **Herramientas externas** — fecha del sistema y feriados de Chile
- **Memoria conversacional** — ventana deslizante sobre `collections.deque`

## Arquitectura

```
Estudiante → Web (Streamlit) / Consola → Agente (Qwen3 vía Groq)
                          │                        │
                          │                        ├── Memoria (ventana deslizante)
                          │                        │
                          │                        ├── Buscador TF-IDF →
                          │                        │   base_conocimiento_duoc.txt
                          │                        │
                          │                        └── consultar_fecha_actual
                          │                            consultar_feriados → date.nager.at
                          │
                    Respuesta basada solo en el contexto
```

Ver [docs/arquitectura.md](docs/arquitectura.md) para el diagrama completo.

## Requisitos Previos

- Python 3.10+
- API key de Groq ([console.groq.com](https://console.groq.com/))

## Instalación

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd asistente-duoc-benjamin-quiroz

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env y agregar tu LLM_API_KEY de Groq
```

### Archivo `.env`

```env
LLM_API_KEY=tu-api-key-de-groq
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=qwen/qwen3-235b-a22b
LLM_MODEL_SMALL=qwen/qwen3-30b-a3b

MEMORIA_MAX_TURNOS=6
MEMORIA_RUTA=.historial/sesion.json
FRAGMENTOS_POR_DEFECTO=3
```

## Memoria Conversacional

El asistente usa una **memoria de ventana deslizante**
(`MemoriaVentanaDeslizante`, en `chatbot/memoria.py`) construida sobre
`collections.deque`. Conserva los últimos `MEMORIA_MAX_TURNOS` intercambios
(6 por defecto) y descarta automáticamente los más antiguos. En consola la
sesión se guarda en `.historial/sesion.json`.

| Variable | Descripción | Default |
|---|---|---|
| `MEMORIA_MAX_TURNOS` | Turnos conservados (usuario + asistente) | `6` |
| `MEMORIA_RUTA` | Archivo de persistencia de la sesión | `.historial/sesion.json` |

## Recuperación (RAG)

`chatbot/conocimiento.py` implementa un índice **TF-IDF** con la librería
estándar:

1. **Normalización**: minúsculas y sin acentos (`régimen` → `regimen`).
2. **Stopwords**: se descartan palabras vacías (`el`, `es`, `para`, `cuál`…).
3. **Singularización**: `becas` → `beca`, `pagos` → `pago`.
4. **Sinónimos**: `plata → arancel`, `nota → calificación`, `beca → beneficio`.
5. **Ponderación IDF + título**: las palabras poco frecuentes pesan más y una
   coincidencia en el título de la sección suma puntaje extra.

Si ninguna palabra relevante coincide, el buscador devuelve una lista vacía y
el asistente responde que no cuenta con la información.

## Ejecución

### Opción 1 — Interfaz web (Streamlit, recomendada)

```bash
streamlit run web.py
```

Abre `http://localhost:8501`. Incluye burbujas de chat, sugerencias rápidas,
panel de **Fuentes consultadas** y botón para limpiar la conversación.

### Opción 2 — Consola

```bash
PYTHONPATH=. python chatbot/asistente.py
```

Ejemplo de conversación:

```
  Estudiante: ¿Cuál es la asistencia mínima para aprobar?
  Asistente: La asistencia mínima para aprobar es de 75% (85% en carreras de salud y educación).

  Estudiante: ¿Quién ganó el mundial de fútbol?
  Asistente: Lo siento, no cuento con esa información. Te recomiendo escribir a
             soporte@duocuc.cl o llamar al 600-300-4000...
```

## Casos de Prueba

| # | Tipo | Pregunta de Ejemplo | Resultado Esperado |
|---|------|---------------------|-------------------|
| 1 | Consulta interna | "¿Cuál es la asistencia mínima para aprobar?" | 75% (85% en salud y educación) |
| 2 | Memoria multi-turno | "¿Cuántos turnos conserva la memoria?" → "¿y eso en la práctica?" | Usa el turno anterior |
| 3 | Herramienta externa | "¿Qué feriados hay este año?" | Lista de feriados desde date.nager.at |
| 4 | Anti-alucinación | "¿Cuál es la política de tutorías de surf?" | "no cuento con esa información" |
| 5 | Becas | "¿Cómo postulo a la beca de excelencia?" | Promedio ≥ 5.5, postula del 1 al 15 de julio |
| 6 | Tolerancia a acentos | "cuando puedo retirar un ramo" (sin tildes) | Semana 8 sin registro |

## Ejecutar Tests

```bash
PYTHONPATH=. python -m unittest discover -s tests -v
```

## Estructura del Proyecto

```
├── data/
│   └── base_conocimiento_duoc.txt   # Base de conocimiento institucional
├── docs/
│   └── arquitectura.md              # Documentación técnica
├── chatbot/
│   ├── __init__.py
│   ├── ajustes.py                   # Configuración y variables de entorno
│   ├── conocimiento.py              # Índice TF-IDF y recuperación (RAG)
│   ├── memoria.py                   # Memoria de ventana deslizante
│   ├── herramientas.py              # Búsqueda, fecha actual y feriados
│   └── asistente.py                 # Agente + consola (CLI)
├── web.py                           # Interfaz web (Streamlit)
├── .streamlit/
│   └── config.toml                  # Tema visual de la app web
├── tests/
│   └── test_asistente.py            # Pruebas unitarias
├── .gitignore
├── .env.example
├── requirements.txt
└── README.md
```

## Licencia

Proyecto académico — Benjamín Quiroz.
