"""Verificación rápida del proveedor de LLM configurado.

Uso:
    python verificar_proveedor.py
    python verificar_proveedor.py --consulta "asta cuando puedo retirar un ramo"

La primera forma solo comprueba que la clave, la URL base y el modelo
respondan. La segunda ejecuta un turno completo del agente (incluye tool
calling y recuperación semántica), por lo que consume más tokens.

No imprime la API key.
"""

from __future__ import annotations

import argparse
import sys

# La consola de Windows puede usar cp1252; evitamos que un carácter Unicode
# (por ejemplo, un espacio fino de una respuesta del modelo) rompa el script.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from chatbot.agente import AgenteDuocUC, ErrorAgente, ErrorConfiguracion, crear_llm
from chatbot.ajustes import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


def _mascara(clave: str) -> str:
    """Describe la clave sin exponer ningún fragmento de su contenido."""
    if not clave:
        return "(vacía)"
    return f"(definida, {len(clave)} caracteres)"


def _explicar_error(exc: Exception) -> str:
    texto = str(exc)
    bajo = texto.lower()

    if (
        "401" in texto
        or "403" in texto
        or "invalid api key" in bajo
        or "valid api key" in bajo
        or ("api key" in bajo and "invalid" in bajo)
        or "unauthorized" in bajo
    ):
        return (
            "La clave fue rechazada. Verifica que LLM_API_KEY corresponda al "
            "proveedor de LLM_BASE_URL y que la clave esté activa."
        )
    if "404" in texto or "not found" in bajo:
        return (
            f"El modelo o la URL no existen en el proveedor. Revisa LLM_MODEL "
            f"('{LLM_MODEL}') y LLM_BASE_URL ('{LLM_BASE_URL}')."
        )
    if "429" in texto or "rate limit" in bajo or "quota" in bajo or "resource_exhausted" in bajo:
        return (
            "El proveedor respondió con límite de cuota o tasa (429). El free "
            "tier de Gemini puede permitir solo 20 solicitudes por día; espera "
            "el reinicio o cambia a Groq/OpenRouter en .env."
        )
    if "timeout" in bajo or "connection" in bajo or "connect" in bajo:
        return (
            "No se pudo conectar con el proveedor. Revisa tu conexión, la URL "
            "base o un proxy/firewall."
        )
    return f"Error no clasificado: {texto}"


def _texto_respuesta(contenido) -> str:
    """Normaliza la respuesta de ChatOpenAI o de ChatGoogleGenerativeAI."""
    if isinstance(contenido, list):
        partes = [
            str(bloque.get("text", ""))
            for bloque in contenido
            if isinstance(bloque, dict) and bloque.get("text")
        ]
        return " ".join(partes).strip()
    return str(contenido or "").strip()


def _probar_modelo() -> bool:
    proveedor = (
        "Google Gemini (nativo)"
        if "generativelanguage.googleapis.com" in LLM_BASE_URL
        else "OpenAI-compatible"
    )
    print("1) Comprobando configuración…")
    print(f"   Proveedor : {proveedor}")
    print(f"   Modelo    : {LLM_MODEL}")
    print(f"   API key   : {_mascara(LLM_API_KEY)}")

    if not LLM_API_KEY:
        print("\n[ERROR] Falta LLM_API_KEY. Copia .env.example a .env y agrégala.")
        return False

    try:
        llm = crear_llm()
        respuesta = llm.invoke("Responde únicamente con la palabra OK.")
        texto = _texto_respuesta(getattr(respuesta, "content", respuesta))
        print(f"\n[OK] El modelo respondió: {texto[:120]}")
        return True
    except Exception as exc:  # noqa: BLE001 - diagnóstico para el usuario
        print(f"\n[ERROR] Falló la llamada al modelo.\n   {_explicar_error(exc)}")
        return False


def _probar_agente(consulta: str) -> bool:
    print("\n2) Ejecutando un turno completo del agente…")
    print(f"   Consulta: {consulta}")
    try:
        agente = AgenteDuocUC()
        resultado = agente.responder(consulta)
    except (ErrorConfiguracion, ErrorAgente) as exc:
        print(f"\n[ERROR] Falló el agente.\n   {exc}")
        return False
    except Exception as exc:  # noqa: BLE001 - diagnóstico para el usuario
        print(f"\n[ERROR] Falló el agente.\n   {_explicar_error(exc)}")
        return False

    print("\n[OK] Respuesta:")
    print(resultado.respuesta)
    print("\n   Herramientas usadas:", ", ".join(resultado.herramientas_usadas) or "(ninguna)")
    print(f"   Fuentes recuperadas: {len(resultado.fuentes)}")
    for fuente in resultado.fuentes:
        print(
            f"   - {fuente.get('seccion', '')} | {fuente.get('titulo', '')} "
            f"| {float(fuente.get('relevancia', 0)):.3f}"
        )
    if resultado.borradores:
        print(f"   Borradores generados: {len(resultado.borradores)}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica el proveedor del agente.")
    parser.add_argument(
        "--consulta",
        default="",
        help="Si se indica, ejecuta un turno completo del agente con esta consulta.",
    )
    args = parser.parse_args()

    if not _probar_modelo():
        return 1
    if args.consulta and not _probar_agente(args.consulta):
        return 1

    print("\nTodo listo. Puedes ejecutar: python -m streamlit run web.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
