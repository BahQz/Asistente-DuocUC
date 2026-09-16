"""Ajustes y variables de entorno del asistente estudiantil.

Autor: Benjamín Quiroz
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Proveedor del modelo de lenguaje (compatible con OpenAI) ---
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")
LLM_MODEL_SMALL = os.getenv("LLM_MODEL_SMALL", "qwen/qwen3.8-27b")

# --- Rutas del proyecto ---
PROYECTO_RAIZ = Path(__file__).resolve().parent.parent
BASE_CONOCIMIENTO = PROYECTO_RAIZ / "data" / "base_conocimiento_duoc.txt"

# --- Memoria conversacional (ventana deslizante) ---
MEMORIA_MAX_TURNOS = int(os.getenv("MEMORIA_MAX_TURNOS", "6"))
MEMORIA_RUTA = os.getenv("MEMORIA_RUTA", ".historial/sesion.json")

# --- Recuperación ---
FRAGMENTOS_POR_DEFECTO = int(os.getenv("FRAGMENTOS_POR_DEFECTO", "3"))
