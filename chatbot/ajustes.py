import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://api.groq.com/openai/v1",
)
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
LLM_MODEL_SMALL = os.getenv("LLM_MODEL_SMALL", "openai/gpt-oss-120b")
LLM_TEMPERATURA = float(os.getenv("LLM_TEMPERATURA", "0.2"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "3000"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "90"))
LLM_THINKING_LEVEL = os.getenv("LLM_THINKING_LEVEL", "low")
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "low")

PROYECTO_RAIZ = Path(__file__).resolve().parent.parent
BASE_CONOCIMIENTO = PROYECTO_RAIZ / "data" / "base_conocimiento_duoc.txt"
DOCUMENTOS_DIR = Path(
    os.getenv("DOCUMENTOS_DIR", str(PROYECTO_RAIZ / "documentos"))
)

MEMORIA_MAX_TURNOS = int(os.getenv("MEMORIA_MAX_TURNOS", "8"))
MEMORIA_RUTA = os.getenv("MEMORIA_RUTA", ".historial/sesion.json")

VECTOR_DIR = Path(os.getenv("VECTOR_DIR", str(PROYECTO_RAIZ / ".chroma")))
COLECCION_REGLAMENTOS = os.getenv("COLECCION_REGLAMENTOS", "reglamentos_duoc")
EMBEDDINGS_MODEL = os.getenv(
    "EMBEDDINGS_MODEL",
    "intfloat/multilingual-e5-small",
)
EMBEDDINGS_DISPOSITIVO = os.getenv("EMBEDDINGS_DISPOSITIVO", "cpu")

FRAGMENTOS_POR_DEFECTO = int(os.getenv("FRAGMENTOS_POR_DEFECTO", "3"))
FRAGMENTOS_MAXIMOS = int(os.getenv("FRAGMENTOS_MAXIMOS", "8"))
UMBRAL_RELEVANCIA = float(os.getenv("UMBRAL_RELEVANCIA", "0.82"))
MARGEN_RELEVANCIA = float(os.getenv("MARGEN_RELEVANCIA", "0.02"))

FERIADOS_URL = os.getenv(
    "FERIADOS_URL", "https://date.nager.at/api/v3/PublicHolidays"
)
FERIADOS_TIMEOUT = int(os.getenv("FERIADOS_TIMEOUT", "15"))

AGENTE_MAX_ITERACIONES = int(os.getenv("AGENTE_MAX_ITERACIONES", "18"))
AGENTE_REINTENTOS = int(os.getenv("AGENTE_REINTENTOS", "2"))
AGENTE_DEBUG = os.getenv("AGENTE_DEBUG", "0").lower() in ("1", "true", "si", "sí")

# --- Observabilidad (EP3) ---
OBS_ACTIVA = os.getenv("OBS_ACTIVA", "1").lower() in ("1", "true", "si", "sí")
OBS_DIR = Path(os.getenv("OBS_DIR", str(PROYECTO_RAIZ / "logs")))
OBS_TRUNCAR_CHARS = int(os.getenv("OBS_TRUNCAR_CHARS", "300"))
OBS_ZONA_GRIS = float(os.getenv("OBS_ZONA_GRIS", "0.03"))

# --- Guardrails de seguridad (EP3) ---
GUARDRAIL_PII = os.getenv("GUARDRAIL_PII", "1").lower() in ("1", "true", "si", "sí")
GUARDRAIL_INYECCION = os.getenv("GUARDRAIL_INYECCION", "bloquear")
GUARDRAIL_RESPALDO = os.getenv("GUARDRAIL_RESPALDO", "bloquear_grave")

# --- Benchmark (EP3) ---
BENCH_PRESUPUESTO_TOKENS = int(os.getenv("BENCH_PRESUPUESTO_TOKENS", "150000"))
BENCH_MAX_TURNOS_LLM = int(os.getenv("BENCH_MAX_TURNOS_LLM", "15"))
BENCH_PAUSA_SEG = float(os.getenv("BENCH_PAUSA_SEG", "2"))
BENCH_TOKENS_POR_TURNO_ESTIMADO = int(
    os.getenv("BENCH_TOKENS_POR_TURNO_ESTIMADO", "8000")
)
