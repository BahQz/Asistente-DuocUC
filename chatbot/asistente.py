"""Agente conversacional del asistente estudiantil de Duoc UC.

Combina recuperación de información (RAG), memoria conversacional y
herramientas externas sobre un modelo servido vía API compatible con OpenAI.

Autor: Benjamín Quiroz
"""

import re
import time

from openai import OpenAI

from chatbot.ajustes import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from chatbot.conocimiento import construir_buscador, normalizar
from chatbot.herramientas import consultar_fecha_actual, consultar_feriados
from chatbot.memoria import crear_memoria

PROMPT_SISTEMA = """\
/no_think
Eres el Asistente Estudiantil de Duoc UC.
Tu única función es responder dudas de los estudiantes usando la información
institucional que se te entrega como contexto.

REGLAS ESTRICTAS:
1. Responde SOLO con la información que aparezca en el contexto entregado.
2. Si la respuesta no está en el contexto, di exactamente: "Lo siento, no cuento
   con esa información. Te recomiendo escribir a soporte@duocuc.cl o llamar al
   600-300-4000 para que una persona te ayude." No inventes datos.
3. Responde siempre en español, de forma breve, clara y respetuosa.
4. Si la pregunta no tiene relación con temas académicos o institucionales,
   indica amablemente que solo puedes ayudar con consultas de Duoc UC.
5. No muestres tu razonamiento interno ni supongas información que no esté en
   el contexto.
6. Cuando uses un dato como una fecha, un monto o un plazo, respétalo tal cual
   aparece en el contexto.
"""

PATRON_RAZONAMIENTO = re.compile(r"<think>.*?</think>", re.DOTALL)

PALABRAS_FECHA = (
    "hoy", "fecha actual", "qué día es", "que dia es", "fecha de hoy",
)
PALABRAS_FERIADO = ("feriado", "feriados", "festivo", "festivos")

PALABRAS_SALUDO = (
    "hola", "holi", "buenas", "buenos dias", "buenas tardes",
    "buenas noches", "que tal", "hey", "saludos", "hola buenas",
)
PALABRAS_DESPEDIDA = (
    "gracias", "adios", "chao", "hasta luego", "nos vemos", "bye",
)

RESPUESTA_SALUDO = (
    "¡Hola! Soy el Asistente Estudiantil de Duoc UC. Puedo ayudarte con "
    "consultas sobre matrícula, calendario académico, becas y beneficios, "
    "evaluaciones y asistencia, biblioteca, bienestar estudiantil, práctica, "
    "titulación, aranceles y pagos, entre otros temas. ¿En qué te ayudo?"
)
RESPUESTA_DESPEDIDA = (
    "¡De nada! Si tienes otra duda sobre Duoc UC, aquí estoy. "
    "Que tengas un buen día."
)


def inicializar_cliente():
    """Crea el cliente del proveedor compatible con OpenAI."""
    return OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)


def limpiar_respuesta(contenido: str) -> str:
    """Quita los bloques de razonamiento del modelo."""
    if not contenido:
        return ""
    contenido = re.sub(r"<think>.*?</think>", "", contenido, flags=re.DOTALL)
    if "<think>" in contenido:
        contenido = contenido.split("<think>")[0]
    return contenido.strip()


def construir_mensajes(consulta, contexto, historial):
    """Arma la lista de mensajes con contexto e historial."""
    if contexto:
        instruccion = (
            f"Contexto institucional:\n{contexto}\n\n"
            f"Pregunta del estudiante: {consulta}\n\n"
            "Responde usando únicamente el contexto. Si la información no está "
            "en el contexto, indica que no cuentas con ella. Responde directo, "
            "sin razonamiento interno."
        )
    else:
        instruccion = (
            f"Pregunta del estudiante: {consulta}\n\n"
            "No se encontró contexto en la base de conocimiento. Indica que no "
            "cuentas con esa información y sugiere contactar a la mesa de ayuda. "
            "Responde directo, sin razonamiento interno."
        )

    return (
        [{"role": "system", "content": PROMPT_SISTEMA}]
        + historial
        + [{"role": "user", "content": instruccion}]
    )


def generar_respuesta(cliente, consulta, contexto, historial=None, reintentos=3):
    """Llama al modelo con reintentos ante límites de tasa."""
    historial = historial or []
    mensajes = construir_mensajes(consulta, contexto, historial)

    for intento in range(reintentos):
        try:
            respuesta = cliente.chat.completions.create(
                model=LLM_MODEL,
                messages=mensajes,
                temperature=0.1,
                max_tokens=600,
                reasoning_effort="none",
            )
            return limpiar_respuesta(respuesta.choices[0].message.content or "")
        except TypeError:
            respuesta = cliente.chat.completions.create(
                model=LLM_MODEL,
                messages=mensajes,
                temperature=0.1,
                max_tokens=600,
            )
            return limpiar_respuesta(respuesta.choices[0].message.content or "")
        except Exception as exc:  # noqa: BLE001
            if "429" in str(exc) and intento < reintentos - 1:
                espera = (intento + 1) * 15
                print(f"  Límite alcanzado. Reintentando en {espera}s...")
                time.sleep(espera)
            else:
                raise


def detectar_consulta_fecha(consulta: str) -> bool:
    """Determina si la consulta pide la fecha actual."""
    texto = consulta.lower()
    return any(palabra in texto for palabra in PALABRAS_FECHA)


def detectar_consulta_feriados(consulta: str) -> bool:
    """Determina si la consulta pide los feriados."""
    texto = consulta.lower()
    return any(palabra in texto for palabra in PALABRAS_FERIADO)


def detectar_charla(consulta: str) -> str:
    """Devuelve un saludo/despedida para mensajes breves, o cadena vacía."""
    texto = normalizar(consulta).strip()
    if len(texto.split()) > 3:
        return ""
    if any(palabra in texto for palabra in PALABRAS_SALUDO):
        return RESPUESTA_SALUDO
    if any(palabra in texto for palabra in PALABRAS_DESPEDIDA):
        return RESPUESTA_DESPEDIDA
    return ""


def responder_consulta(cliente, buscador, memoria, consulta: str) -> dict:
    """Ejecuta el pipeline completo para una consulta del estudiante.

    Devuelve un diccionario con: respuesta, fuentes, uso_fecha y uso_feriados.
    """
    charla = detectar_charla(consulta)
    if charla:
        memoria.agregar_usuario(consulta)
        memoria.agregar_asistente(charla)
        return {
            "respuesta": charla,
            "fuentes": [],
            "uso_fecha": False,
            "uso_feriados": False,
        }

    fragmentos = buscador(consulta)
    contexto = "\n".join(fragmentos) if fragmentos else ""

    uso_fecha = False
    uso_feriados = False
    datos_extra = []

    if detectar_consulta_fecha(consulta):
        datos_extra.append(consultar_fecha_actual())
        uso_fecha = True

    if detectar_consulta_feriados(consulta):
        datos_extra.append(consultar_feriados())
        uso_feriados = True

    if datos_extra:
        extra = "\n".join(datos_extra)
        contexto = f"{contexto}\n\nInformación de apoyo: {extra}" if contexto else extra

    respuesta = generar_respuesta(cliente, consulta, contexto, memoria.historial())
    memoria.agregar_usuario(consulta)
    memoria.agregar_asistente(respuesta)

    return {
        "respuesta": respuesta,
        "fuentes": fragmentos,
        "uso_fecha": uso_fecha,
        "uso_feriados": uso_feriados,
    }


def main():
    """Bucle interactivo de consola con memoria conversacional."""
    print("=" * 62)
    print("  Asistente Estudiantil Duoc UC - Benjamín Quiroz")
    print("=" * 62)
    print("Escribe 'salir' para terminar.\n")

    cliente = inicializar_cliente()
    buscador = construir_buscador()
    memoria = crear_memoria()

    while True:
        try:
            entrada = input("  Estudiante: ").strip()
        except (EOFError, KeyboardInterrupt):
            memoria.guardar()
            print("\n  Sesión finalizada.")
            break

        if entrada.lower() in ("salir", "exit"):
            memoria.guardar()
            print("  Sesión finalizada.")
            break

        if not entrada:
            continue

        try:
            resultado = responder_consulta(cliente, buscador, memoria, entrada)
            print(f"\n  Asistente: {resultado['respuesta']}\n")
        except Exception as exc:  # noqa: BLE001
            print(f"\n  Error: {exc}\n")


if __name__ == "__main__":
    main()
