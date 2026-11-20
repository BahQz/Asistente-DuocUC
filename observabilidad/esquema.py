"""Esquema y validación de eventos de observabilidad (EP3).

Define las constantes de eventos, categorías de errores y controles de seguridad,
así como el validador estricto para garantizar la calidad del registro JSONL.
"""

from typing import Any

VERSION_ESQUEMA = 1

TIPOS_EVENTO = (
    "turno",
    "etapa",
    "retrieval",
    "api_externa",
    "error",
    "seguridad",
    "recursos",
    "benchmark_caso",
)

CATEGORIAS_ERROR = (
    "rate_limit_429",
    "auth_401",
    "modelo_no_encontrado",
    "timeout",
    "red_api_externa",
    "limite_iteraciones",
    "herramienta_fallo",
    "otro",
)

CONTROLES_SEGURIDAD = (
    "pii",
    "prompt_injection",
    "fuga_prompt",
    "respuesta_sin_respaldo",
    "pii_hacia_proveedor",
)

ACCIONES_SEGURIDAD = (
    "enmascarado",
    "bloqueado",
    "alertado",
)

SEVERIDADES = (
    "baja",
    "media",
    "alta",
)

ORIGENES = (
    "app",
    "consola",
    "benchmark",
)

RESULTADOS_TURNO = (
    "ok",
    "error",
    "bloqueado_entrada",
    "bloqueado_salida",
)

NOMBRES_ETAPA = (
    "guardrail_entrada",
    "carga_embeddings",
    "carga_indice",
    "retrieval",
    "llm",
    "herramienta",
    "guardrail_salida",
)

COMPONENTES = (
    "guardrail",
    "embeddings",
    "retrieval",
    "llm",
    "herramienta",
    "api_externa",
)


def validar_evento(evento: dict[str, Any]) -> list[str]:
    """Valida un evento frente al contrato del esquema v1.

    Retorna una lista de errores encontrados; vacía si el evento es válido.
    """
    errores: list[str] = []
    if not isinstance(evento, dict):
        return ["El evento debe ser un diccionario."]

    if evento.get("v") != VERSION_ESQUEMA:
        errores.append(f"Versión de esquema inválida: {evento.get('v')!r}.")

    if not evento.get("ts") or not isinstance(evento.get("ts"), str):
        errores.append("Campo 'ts' faltante o no es cadena ISO 8601.")

    tipo = evento.get("tipo")
    if tipo not in TIPOS_EVENTO:
        errores.append(f"Tipo de evento desconocido: {tipo!r}.")

    origen = evento.get("origen")
    if origen not in ORIGENES:
        errores.append(f"Origen de evento desconocido: {origen!r}.")

    datos = evento.get("datos")
    if not isinstance(datos, dict):
        errores.append("El campo 'datos' debe ser un diccionario.")
        return errores

    # Validaciones específicas por tipo de evento
    if tipo == "turno":
        if "consulta_masc" not in datos:
            errores.append("Evento 'turno' requiere 'consulta_masc'.")
        if datos.get("resultado") not in RESULTADOS_TURNO:
            errores.append(f"Resultado de turno inválido: {datos.get('resultado')!r}.")
        if not isinstance(datos.get("latencia_total_ms"), (int, float)):
            errores.append("'latencia_total_ms' debe ser numérico.")
        if not isinstance(datos.get("turno_frio"), bool):
            errores.append("'turno_frio' debe ser booleano.")
        if not isinstance(datos.get("n_llamadas_llm"), int):
            errores.append("'n_llamadas_llm' debe ser entero.")
        if not isinstance(datos.get("tokens_total"), int):
            errores.append("'tokens_total' debe ser entero.")
        if not isinstance(datos.get("herramientas"), list):
            errores.append("'herramientas' debe ser una lista.")

    elif tipo == "etapa":
        if not datos.get("nombre"):
            errores.append("Evento 'etapa' requiere 'nombre'.")
        if not datos.get("componente"):
            errores.append("Evento 'etapa' requiere 'componente'.")
        if not isinstance(datos.get("offset_ms"), (int, float)):
            errores.append("'offset_ms' debe ser numérico.")
        if not isinstance(datos.get("duracion_ms"), (int, float)):
            errores.append("'duracion_ms' debe ser numérico.")
        if not isinstance(datos.get("ok"), bool):
            errores.append("'ok' debe ser booleano en 'etapa'.")

    elif tipo == "retrieval":
        if not isinstance(datos.get("top_k"), int):
            errores.append("'top_k' debe ser entero.")
        if not isinstance(datos.get("umbral"), (int, float)):
            errores.append("'umbral' debe ser numérico.")
        if not isinstance(datos.get("candidatos"), list):
            errores.append("'candidatos' debe ser una lista.")
        if not isinstance(datos.get("aceptados"), list):
            errores.append("'aceptados' debe ser una lista.")
        if not isinstance(datos.get("top1_score"), (int, float)):
            errores.append("'top1_score' debe ser numérico.")
        if datos.get("decision") not in ("respuesta", "abstencion"):
            errores.append(f"Decisión inválida en retrieval: {datos.get('decision')!r}.")

    elif tipo == "api_externa":
        if not datos.get("servicio"):
            errores.append("Evento 'api_externa' requiere 'servicio'.")
        if not isinstance(datos.get("intentos"), int):
            errores.append("'intentos' debe ser entero.")
        if not isinstance(datos.get("cache_hit"), bool):
            errores.append("'cache_hit' debe ser booleano.")

    elif tipo == "error":
        if datos.get("categoria") not in CATEGORIAS_ERROR:
            errores.append(f"Categoría de error inválida: {datos.get('categoria')!r}.")
        if not datos.get("componente"):
            errores.append("Evento 'error' requiere 'componente'.")

    elif tipo == "seguridad":
        if datos.get("control") not in CONTROLES_SEGURIDAD:
            errores.append(f"Control de seguridad inválido: {datos.get('control')!r}.")
        if datos.get("accion") not in ACCIONES_SEGURIDAD:
            errores.append(f"Acción de seguridad inválida: {datos.get('accion')!r}.")
        if datos.get("severidad") not in SEVERIDADES:
            errores.append(f"Severidad de seguridad inválida: {datos.get('severidad')!r}.")

    elif tipo == "recursos":
        if not datos.get("momento"):
            errores.append("Evento 'recursos' requiere 'momento'.")
        if not isinstance(datos.get("rss_mb"), (int, float)):
            errores.append("'rss_mb' debe ser numérico.")

    elif tipo == "benchmark_caso":
        if not datos.get("caso_id"):
            errores.append("Evento 'benchmark_caso' requiere 'caso_id'.")
        if "esperado" not in datos or "observado" not in datos:
            errores.append("Evento 'benchmark_caso' requiere 'esperado' y 'observado'.")

    return errores
