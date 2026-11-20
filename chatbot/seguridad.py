"""Guardrails de seguridad, ética y privacidad (EP3).

Funciones puras y deterministas (regex, reglas y aritmética) para:
- Enmascaramiento de PII (RUT, correos, teléfonos, claves, tarjetas).
- Detección de prompt injection (ES/EN) con baja tasa de falsos positivos.
- Detección de fuga de prompt institucional (shingles).
- Verificación de respaldo documental y veracidad de datos normativos.

Sin dependencias externas pesadas (no importa sentence_transformers ni Chroma).
"""

import re
import unicodedata
from typing import Any

MENSAJE_BLOQUEO_INYECCION = (
    "Por políticas de seguridad institucional de Duoc UC, no puedo procesar "
    "instrucciones que intenten modificar mis directrices o acceder a datos internos. "
    "Con gusto te puedo orientar sobre reglamentos, justificaciones, plazos o trámites académicos."
)

MENSAJE_FUGA_PROMPT = (
    "Como asistente de Duoc UC, mi función es orientarte sobre reglamentos y "
    "trámites académicos. ¿En qué trámite o consulta te puedo ayudar hoy?"
)

MENSAJE_SIN_RESPALDO = (
    "No cuento con información oficial en el reglamento para respaldar esos datos "
    "específicos. Para evitar confusiones, te recomiendo consultar directamente "
    "con la mesa de ayuda (soporte@duocuc.cl / 600-300-4000) o en tu Dirección de Escuela."
)

# Allowlist institucional (no se enmascaran)
CORREOS_ALLOWLIST = {"soporte@duocuc.cl"}
TELEFONOS_ALLOWLIST = {"6003004000", "600-300-4000", "600 300 4000"}

# Patrones para PII
PATRON_RUT_ESTANDAR = re.compile(
    r"\b(\d{1,2}(?:\.?\d{3}){2}-[\dkK])\b"
)
PATRON_RUT_PREFIJO = re.compile(
    r"\b(?:rut|run)\s*[:#]?\s*(\d{7,8}-?[\dkK]|\d{7,9})\b",
    re.IGNORECASE,
)
PATRON_CORREO = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
)
PATRON_TELEFONO = re.compile(
    r"(?:\+?56\s?)?(?:9\s?\d{4}\s?\d{4}|[2-9]\s?\d{3,4}\s?\d{4})\b"
)
PATRON_CLAVE = re.compile(
    r"(?i)\b(?:clave|contraseña|password|pin)\s*(?:es|:|=)\s*([^\s,;]+)"
)
PATRON_TARJETA_CANDIDATO = re.compile(
    r"\b(?:\d[ -]?){13,19}\b"
)


def normalizar_texto_seguro(texto: str) -> str:
    """Normaliza texto: minúsculas, NFKD sin tildes, sin caracteres zero-width."""
    if not texto:
        return ""
    # Quitar caracteres invisibles/ancho cero
    texto = re.sub(r"[\u200b-\u200d\ufeff]", "", texto)
    texto = texto.lower()
    texto = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(sin_tildes.split())


def validar_luhn(numero_str: str) -> bool:
    """Verifica si una cadena numérica pasa el algoritmo de Luhn (tarjetas)."""
    digitos = [int(c) for c in numero_str if c.isdigit()]
    if len(digitos) < 13 or len(digitos) > 19:
        return False
    checksum = 0
    par = False
    for d in reversed(digitos):
        if par:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
        par = not par
    return checksum % 10 == 0


def validar_rut_dv(rut_str: str) -> bool:
    """Valida el dígito verificador módulo 11 de un RUT chileno."""
    limpio = re.sub(r"[^0-9kK]", "", rut_str)
    if len(limpio) < 2:
        return False
    cuerpo, dv = limpio[:-1], limpio[-1].upper()
    try:
        suma = 0
        multiplicador = 2
        for c in reversed(cuerpo):
            suma += int(c) * multiplicador
            multiplicador = 2 if multiplicador == 7 else multiplicador + 1
        esperado = 11 - (suma % 11)
        dv_esperado = "0" if esperado == 11 else ("K" if esperado == 10 else str(esperado))
        return dv == dv_esperado
    except Exception:
        return False


def detectar_pii(texto: str) -> dict[str, int]:
    """Detecta la presencia de PII en el texto sin modificarlo."""
    _, conteos = enmascarar(texto)
    return conteos


def enmascarar(texto: str) -> tuple[str, dict[str, int]]:
    """Enmascara datos personales sensibles con marcadores legibles.

    Es idempotente: enmascarar(enmascarar(x)) == enmascarar(x).
    """
    if not texto:
        return "", {}

    conteos: dict[str, int] = {}
    resultado = texto

    # 1. Claves / contraseñas explícitas
    def _reemplazar_clave(m: re.Match) -> str:
        prefijo = m.group(0)[: m.start(1) - m.start(0)]
        conteos["clave"] = conteos.get("clave", 0) + 1
        return f"{prefijo}[CLAVE]"

    resultado = PATRON_CLAVE.sub(_reemplazar_clave, resultado)

    # 2. Tarjetas bancarias con algoritmo de Luhn
    def _reemplazar_tarjeta(m: re.Match) -> str:
        candidato = m.group(0)
        solo_digitos = re.sub(r"\D", "", candidato)
        # Evitar falsos positivos con fechas o números cortos
        if 13 <= len(solo_digitos) <= 19 and validar_luhn(solo_digitos):
            conteos["tarjeta"] = conteos.get("tarjeta", 0) + 1
            return "[TARJETA]"
        return candidato

    resultado = PATRON_TARJETA_CANDIDATO.sub(_reemplazar_tarjeta, resultado)

    # 3. Correos electrónicos (respetando allowlist)
    def _reemplazar_correo(m: re.Match) -> str:
        correo = m.group(0)
        if correo.lower() in CORREOS_ALLOWLIST:
            return correo
        conteos["correo"] = conteos.get("correo", 0) + 1
        return "[CORREO]"

    resultado = PATRON_CORREO.sub(_reemplazar_correo, resultado)

    # 4. RUT chileno (estándar y con prefijo 'rut'/'run')
    def _reemplazar_rut_estandar(m: re.Match) -> str:
        conteos["rut"] = conteos.get("rut", 0) + 1
        return "[RUT]"

    resultado = PATRON_RUT_ESTANDAR.sub(_reemplazar_rut_estandar, resultado)

    def _reemplazar_rut_prefijo(m: re.Match) -> str:
        valor = m.group(1)
        if valor == "[RUT]":
            return m.group(0)
        conteos["rut"] = conteos.get("rut", 0) + 1
        prefijo = m.group(0)[: m.start(1) - m.start(0)]
        return f"{prefijo}[RUT]"

    resultado = PATRON_RUT_PREFIJO.sub(_reemplazar_rut_prefijo, resultado)

    # 5. Teléfonos chilenos (respetando allowlist institucional)
    def _reemplazar_tel(m: re.Match) -> str:
        tel = m.group(0)
        limpio = re.sub(r"\s+", " ", tel).strip()
        solo_digitos = re.sub(r"\D", "", tel)
        if limpio in TELEFONOS_ALLOWLIST or solo_digitos in TELEFONOS_ALLOWLIST:
            return tel
        # Evitar enmascarar años o fechas como 2026-10-21
        if len(solo_digitos) < 8 or len(solo_digitos) > 12:
            return tel
        conteos["telefono"] = conteos.get("telefono", 0) + 1
        return "[TELEFONO]"

    resultado = PATRON_TELEFONO.sub(_reemplazar_tel, resultado)

    return resultado, conteos


def enmascarar_obj(obj: Any) -> Any:
    """Aplica enmascaramiento recursivo sobre diccionarios, listas y strings."""
    if isinstance(obj, str):
        enmascarado, _ = enmascarar(obj)
        return enmascarado
    if isinstance(obj, dict):
        return {k: enmascarar_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [enmascarar_obj(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(enmascarar_obj(item) for item in obj)
    return obj


# Reglas de Prompt Injection
REGLAS_INYECCION_ALTA = [
    (
        "anular_instrucciones",
        re.compile(
            r"\b(ignora|ignore|olvida|forget|descarta|omite|disregard|anula|override|desactiva)\b"
            r"(?:\s+\w+){0,6}?\s+"
            r"\b(instrucciones|reglas|indicaciones|restricciones|politicas|directrices|prompt|configuracion|instructions|rules|guidelines)\b"
        ),
    ),
    (
        "extraer_prompt",
        re.compile(
            r"(\b(muestra|revela|repite|imprime|dime|copia|reveal|show|print|repeat)\b(?:\s+\w+){0,8}?\s+\b(tu|your)\s+(prompt|instrucciones|instructions|configuracion|configuration|reglas internas|mensaje del sistema|system prompt|system instructions|system message)\b)"
            r"|(\b(system prompt|prompt del sistema|que instrucciones te dieron)\b)"
        ),
    ),
    (
        "delimitadores_falsos",
        re.compile(
            r"(</?system>|<\|im_start\|>|<\|im_end\|>|\[inst\]|###\s*system|^(?:system|assistant)\s*:)",
            re.MULTILINE,
        ),
    ),
    (
        "exfiltracion_secretos",
        re.compile(
            r"(\b(api[ _]key|llm_api_key|variables de entorno|\.env|clave de la api)\b(?:\s+\w+){0,5}?\s+\b(muestra|dime|revela|imprime|lista|show|print)\b)"
            r"|(\b(muestra|dime|revela|imprime|lista|show|print)\b(?:\s+\w+){0,5}?\s+\b(api[ _]key|llm_api_key|variables de entorno|\.env|clave de la api)\b)"
        ),
    ),
]

REGLAS_INYECCION_MEDIA = [
    (
        "cambio_de_rol",
        re.compile(
            r"\b(actua como|ahora eres|a partir de ahora eres|finge ser|pretend to be|you are now|modo desarrollador|developer mode|jailbreak|\bdan\b|sin restricciones|sin filtros)\b"
        ),
    ),
    (
        "evasion_codificada",
        re.compile(
            r"(\b(base64|rot13|hex)\b(?:\s+\w+){0,4}?\s+\b(decodifica|decode|ejecuta|execute)\b)"
            r"|(\b(decodifica|decode|ejecuta|execute)\b(?:\s+\w+){0,4}?\s+\b(base64|rot13|hex)\b)"
        ),
    ),
]

PATRONES_EXCEPCION_LEGITIMA = [
    # Preguntas legítimas sobre reglamentos de asistencia o convivencia
    re.compile(r"\b(reglas|normas|politica)s?\s+de\s+(asistencia|convivencia|evaluacion|evaluaciones)\b"),
    # Preguntas sobre instrucciones para trámites
    re.compile(r"\bque\s+instrucciones\s+(debo|tengo que)\s+seguir\b"),
    # Frases de corrección conversacional legítimas
    re.compile(r"\b(olvida|ignora)\s+(mi\s+pregunta\s+anterior|lo\s+anterior)\b"),
    # Mostrar reglamento
    re.compile(r"\b(mostrarme|ver|consultar)\s+(el\s+)?reglamento\b"),
    # Actuar rápido
    re.compile(r"\bactua\s+rapido\b"),
]


def analizar_inyeccion(texto: str) -> dict[str, Any]:
    """Analiza si el texto de entrada contiene intentos de Prompt Injection.

    Retorna un diccionario con severidad ('baja', 'media', 'alta'), reglas disparadas y puntaje.
    """
    if not texto:
        return {"severidad": "baja", "reglas": [], "puntaje": 0}

    norm = normalizar_texto_seguro(texto)

    # Filtrar excepciones legítimas
    for pat in PATRONES_EXCEPCION_LEGITIMA:
        if pat.search(norm):
            # Si contiene una frase legítima y no contiene delimitadores ni exfiltración de api keys
            if not any(r[1].search(norm) for r in REGLAS_INYECCION_ALTA if r[0] in ("delimitadores_falsos", "exfiltracion_secretos")):
                return {"severidad": "baja", "reglas": [], "puntaje": 0}

    disparadas: list[str] = []
    puntaje = 0

    for nombre, patron in REGLAS_INYECCION_ALTA:
        if patron.search(norm):
            disparadas.append(nombre)
            puntaje += 3

    for nombre, patron in REGLAS_INYECCION_MEDIA:
        if patron.search(norm):
            disparadas.append(nombre)
            puntaje += 1

    # Reglas de severidad
    altas = [r for r in disparadas if any(r == nom for nom, _ in REGLAS_INYECCION_ALTA)]
    medias = [r for r in disparadas if any(r == nom for nom, _ in REGLAS_INYECCION_MEDIA)]

    if altas or len(medias) >= 2:
        severidad = "alta"
    elif len(medias) == 1:
        severidad = "media"
    else:
        severidad = "baja"

    return {
        "severidad": severidad,
        "reglas": disparadas,
        "puntaje": puntaje,
    }


def detectar_fuga_prompt(respuesta: str, prompt_sistema: str) -> bool:
    """Verifica si la respuesta reproduce secuencias de 8 palabras del prompt del sistema."""
    if not respuesta or not prompt_sistema:
        return False

    def _palabras(txt: str) -> list[str]:
        norm = normalizar_texto_seguro(txt)
        return re.sub(r"[^\w\s]", " ", norm).split()

    palabras_resp = _palabras(respuesta)
    palabras_sys = _palabras(prompt_sistema)

    if len(palabras_resp) < 8 or len(palabras_sys) < 8:
        return False

    shingles_sys = {
        " ".join(palabras_sys[i : i + 8])
        for i in range(len(palabras_sys) - 7)
    }

    for i in range(len(palabras_resp) - 7):
        shingle_resp = " ".join(palabras_resp[i : i + 8])
        if shingle_resp in shingles_sys:
            return True

    return False


PATRON_AFIRMACIONES = re.compile(
    r"(\b\d+(?:[.,]\d+)?\s?%)|"  # Porcentajes (ej. 75%)
    r"(\b\d+\s+(?:dias|semanas|horas|meses|creditos)(?:\s+(?:habiles|corridos))?)|"  # Duraciones
    r"(\bsemana\s+\d+)|"  # Semana X
    r"(\$\s?\d+(?:[.]\d{3})*)|"  # Montos
    r"(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b)|"  # Correos
    r"(\b600[- ]?300[- ]?4000\b)|"  # Teléfono institucional
    r"(\bseccion\s+\d+(?:\.\d+)?\b)"  # Cita Sección X
)


def verificar_respaldo(
    respuesta: str,
    eventos: list[dict[str, Any]],
    fuentes: list[dict[str, Any]],
    texto_usuario: str,
) -> dict[str, Any]:
    """Evalúa si las afirmaciones normativas de la respuesta tienen respaldo en la evidencia."""
    if not respuesta:
        return {"nivel": "ok", "afirmaciones": [], "sin_respaldo": []}

    resp_norm = normalizar_texto_seguro(respuesta)
    afirmaciones = [
        m.group(0).strip() for m in PATRON_AFIRMACIONES.finditer(resp_norm)
    ]
    if not afirmaciones:
        return {"nivel": "ok", "afirmaciones": [], "sin_respaldo": []}

    # Evidencia disponible
    tiene_fuentes = bool(fuentes)
    herramientas_validas = {
        "calcular_plazo",
        "consultar_feriados",
        "consultar_fecha_actual",
        "redactar_borrador",
        "listar_borradores",
        "leer_borrador",
    }
    tiene_herramienta_valida = any(
        e.get("tipo") == "herramienta"
        and e.get("nombre") in herramientas_validas
        and e.get("ok") is not False
        for e in eventos
    )

    tiene_evidencia = tiene_fuentes or tiene_herramienta_valida

    if not tiene_evidencia:
        # Se hicieron afirmaciones normativas sin ninguna fuente válida ni herramienta
        return {
            "nivel": "grave",
            "afirmaciones": afirmaciones,
            "sin_respaldo": afirmaciones,
        }

    # Recopilar todo el texto de evidencia (fuentes + salidas de herramientas + consulta de usuario)
    textos_evidencia = [normalizar_texto_seguro(texto_usuario)]
    for e in eventos:
        if e.get("tipo") == "herramienta":
            res = str(e.get("resultado", ""))
            textos_evidencia.append(normalizar_texto_seguro(res))

    texto_total_evidencia = " ".join(textos_evidencia)

    sin_respaldo = []
    for afirmacion in afirmaciones:
        if afirmacion not in texto_total_evidencia:
            sin_respaldo.append(afirmacion)

    if sin_respaldo:
        return {
            "nivel": "dudoso",
            "afirmaciones": afirmaciones,
            "sin_respaldo": sin_respaldo,
        }

    return {"nivel": "ok", "afirmaciones": afirmaciones, "sin_respaldo": []}
