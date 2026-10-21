"""Herramientas (Tools) que el agente decide cuándo invocar.

Se separan dos capas:

* **Funciones de dominio** (``buscar_en_base_conocimiento``,
  ``consultar_feriados``, ``calcular_plazo``, ``redactar_borrador``…): código
  reutilizable y testeable sin depender del LLM.
* **Herramientas LangChain** (``@tool``): contratos con nombre, descripción y
  esquema de argumentos que el agente ve y utiliza para razonar.

Herramientas disponibles:
1. ``buscar_reglamentos`` — consulta semántica en ChromaDB (consulta).
2. ``consultar_fecha_actual`` / ``consultar_feriados`` — API date.nager.at
   (consulta externa).
3. ``calcular_plazo`` — planificación de plazos en días hábiles.
4. ``redactar_borrador`` — escritura de documentos (con efecto real en disco).
5. ``listar_borradores`` / ``leer_borrador`` — memoria de artefactos.

Autor: Benjamín Quiroz
"""

from datetime import date, datetime, timedelta
from functools import lru_cache

import requests
from langchain_core.tools import tool

from chatbot.ajustes import (
    FERIADOS_TIMEOUT,
    FERIADOS_URL,
    FRAGMENTOS_POR_DEFECTO,
)
from chatbot.conocimiento import buscar_semantico
from chatbot.documentos import Borrador, generar_borrador
from chatbot.documentos import leer_borrador as _leer_borrador
from chatbot.documentos import listar_borradores as _listar_borradores

_DIAS = [
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
]
_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


# --------------------------------------------------------------------------
# 1. Consulta semántica en la base de conocimiento
# --------------------------------------------------------------------------
def buscar_en_base_conocimiento(
    consulta: str, top_k: int = FRAGMENTOS_POR_DEFECTO
) -> str:
    """Busca fragmentos relevantes y los formatea para el agente."""
    fragmentos = buscar_semantico(consulta, top_k=top_k)
    if not fragmentos:
        return (
            f'No se encontraron fragmentos con relevancia suficiente para "{consulta}" '
            "en la base de conocimiento institucional. No inventes una respuesta: "
            "pide una aclaración, sugiere reformular la pregunta o deriva a la mesa "
            "de ayuda (soporte@duocuc.cl / 600-300-4000)."
        )

    bloques = [
        f'Resultados de búsqueda semántica para: "{consulta}"',
        "Cita la sección cuando uses un dato en tu respuesta.\n",
    ]
    for numero, fragmento in enumerate(fragmentos, 1):
        bloques.append(
            f"[Fuente {numero} | {fragmento.seccion} | {fragmento.titulo} | "
            f"relevancia {fragmento.relevancia:.3f}]\n{fragmento.contenido}"
        )
    return "\n\n".join(bloques)


# --------------------------------------------------------------------------
# 2. Fecha, feriados y cálculo de plazos (API externa)
# --------------------------------------------------------------------------
def _fecha_larga(fecha: date) -> str:
    return (
        f"{_DIAS[fecha.weekday()]} {fecha.day} de "
        f"{_MESES[fecha.month - 1]} de {fecha.year}"
    )


@lru_cache(maxsize=8)
def _feriados_api(anio: int) -> tuple[list[dict], str]:
    """Consulta los feriados de Chile y cachea el resultado por año.

    Returns:
        (lista de feriados, mensaje de error). Si hay error, la lista va vacía.
    """
    url = f"{FERIADOS_URL}/{anio}/CL"
    ultimo_error = "sin respuesta"

    for _ in range(3):
        try:
            respuesta = requests.get(
                url,
                headers={"User-Agent": "AsistenteDuoc/2.0"},
                timeout=FERIADOS_TIMEOUT,
            )
            respuesta.raise_for_status()
            datos = respuesta.json()
            if not isinstance(datos, list):
                return [], "formato inesperado de la API"
            return datos, ""
        except requests.exceptions.Timeout:
            ultimo_error = "timeout"
        except requests.exceptions.RequestException as exc:
            ultimo_error = f"error de conexión: {exc}"
        except (KeyError, ValueError) as exc:
            ultimo_error = f"formato inesperado: {exc}"

    return [], ultimo_error


def consultar_fecha_actual() -> str:
    """Entrega la fecha actual en español para calcular plazos."""
    hoy = date.today()
    return f"Hoy es {_fecha_larga(hoy)}."


def consultar_feriados(anio: int | None = None, solo_proximos: bool = False) -> str:
    """Consulta los feriados de Chile en la API date.nager.at.

    Args:
        anio: año a consultar. Si es ``None`` o 0, usa el año actual.
        solo_proximos: si es True, devuelve solo los feriados desde hoy.
    """
    anio = int(anio) if anio else date.today().year
    if not 2015 <= anio <= 2100:
        return (
            "La API pública de feriados solo entrega años entre 2015 y 2100. "
            f"Se solicitó {anio}."
        )

    datos, error = _feriados_api(anio)
    if error:
        return (
            f"No se pudo consultar los feriados de {anio} ({error}). "
            "Puedes intentarlo nuevamente o indicar que no tienes el dato."
        )
    if not datos:
        return f"No se encontraron feriados para el año {anio}."

    feriados = datos
    if solo_proximos:
        hoy = date.today().isoformat()
        feriados = [f for f in datos if str(f.get("date", "")) >= hoy][:6]
        if not feriados:
            return f"No quedan feriados en {anio} desde hoy."

    lineas = [
        f"- {feriado.get('date', '?')}: {feriado.get('localName', 'Feriado')}"
        for feriado in feriados
    ]
    encabezado = (
        f"Próximos feriados en Chile ({anio}):"
        if solo_proximos
        else f"Feriados en Chile ({anio}):"
    )
    return encabezado + "\n" + "\n".join(lineas)


def _parsear_fecha(texto: str) -> date | None:
    """Acepta 'hoy', 'YYYY-MM-DD', 'DD/MM/YYYY' y 'DD-MM-YYYY'."""
    limpio = (texto or "").strip().lower()
    if limpio in ("hoy", "fecha actual", "ahora"):
        return date.today()

    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(limpio, formato).date()
        except ValueError:
            continue
    return None


def calcular_plazo(
    fecha_inicio: str, dias_habiles: int, proposito: str = ""
) -> str:
    """Calcula el vencimiento de un plazo en días hábiles.

    Se excluyen sábados, domingos y feriados nacionales de Chile. El conteo
    comienza el día hábil siguiente a ``fecha_inicio`` (convención habitual
    para plazos "desde" un hecho).
    """
    inicio = _parsear_fecha(fecha_inicio)
    if inicio is None:
        return (
            f'No pude interpretar la fecha "{fecha_inicio}". Usa el formato '
            "AAAA-MM-DD, DD/MM/AAAA, DD-MM-AAAA o la palabra 'hoy'."
        )

    try:
        dias = int(dias_habiles)
    except (TypeError, ValueError):
        return "La cantidad de días hábiles debe ser un número entero."
    if not 1 <= dias <= 365:
        return "La cantidad de días hábiles debe estar entre 1 y 365."

    anios = {inicio.year, (inicio + timedelta(days=dias * 3 + 10)).year}
    feriados: dict[str, str] = {}
    fallo_api = ""
    for anio in sorted(anios):
        datos, error = _feriados_api(anio)
        if error:
            fallo_api = error
            continue
        for feriado in datos:
            feriados[str(feriado.get("date", ""))] = str(
                feriado.get("localName", "Feriado")
            )

    actual = inicio
    contados = 0
    excluidos: list[str] = []
    limite = 0
    while contados < dias and limite < 1000:
        actual += timedelta(days=1)
        limite += 1
        if actual.weekday() >= 5:
            continue
        if actual.isoformat() in feriados:
            excluidos.append(
                f"{_fecha_larga(actual)} ({actual.isoformat()}) — "
                f"{feriados[actual.isoformat()]}"
            )
            continue
        contados += 1

    lineas = [
        "Cálculo de plazo en días hábiles",
        f"- Inicio del cómputo: {_fecha_larga(inicio)} ({inicio.isoformat()})",
        f"- Plazo: {dias} día(s) hábil(es)",
        f"- Vencimiento: {_fecha_larga(actual)} ({actual.isoformat()})",
        "- Convención: se cuenta desde el día hábil siguiente al inicio y se "
        "excluyen sábados, domingos y feriados nacionales.",
    ]
    if proposito:
        lineas.insert(1, f"- Trámite: {proposito}")
    if excluidos:
        lineas.append("- Feriados excluidos: " + "; ".join(excluidos))
    if fallo_api:
        lineas.append(
            f"- Advertencia: no se pudieron consultar los feriados ({fallo_api}); "
            "el cálculo solo excluyó fines de semana. Verifica el feriado en "
            "date.nager.at antes de confirmar el plazo."
        )
    return "\n".join(lineas)


# --------------------------------------------------------------------------
# 3. Escritura y memoria de artefactos
# --------------------------------------------------------------------------
def redactar_borrador(
    tipo: str,
    motivo: str,
    nombre_estudiante: str = "",
    asignatura: str = "",
    fecha_referencia: str = "",
    detalles: str = "",
    fundamento: str = "",
) -> Borrador:
    """Genera un borrador formal y lo guarda en ``documentos/``."""
    return generar_borrador(
        tipo=tipo,
        motivo=motivo,
        nombre_estudiante=nombre_estudiante,
        asignatura=asignatura,
        fecha_referencia=fecha_referencia,
        detalles=detalles,
        fundamento=fundamento,
    )


def listar_borradores(limite: int = 5) -> list[dict]:
    """Lista los borradores generados (memoria de artefactos)."""
    return _listar_borradores(limite)


def leer_borrador(identificador: str) -> Borrador | None:
    """Recupera un borrador por ID o nombre de archivo."""
    return _leer_borrador(identificador)


# --------------------------------------------------------------------------
# 4. Contratos de herramientas para el agente (LangChain)
# --------------------------------------------------------------------------
@tool("buscar_reglamentos")
def herramienta_buscar_reglamentos(
    consulta: str, top_k: int = FRAGMENTOS_POR_DEFECTO
) -> str:
    """Busca información oficial en los reglamentos y la base de conocimiento de Duoc UC.

    Úsala SIEMPRE antes de afirmar cualquier dato institucional: requisitos,
    fechas, plazos, montos, porcentajes, horarios, correos o sanciones. La
    búsqueda es semántica, así que tolera errores ortográficos y sinónimos
    (por ejemplo, "retirar un ramo" encuentra "retiro de asignaturas").

    Args:
        consulta: pregunta o palabras clave en español, con el contexto necesario
            (por ejemplo, "plazo para justificar una inasistencia a evaluación").
            Si es un seguimiento, incluye el tema del turno anterior.
        top_k: cantidad de fragmentos a recuperar (1 a 8; por defecto 3).
    """
    return buscar_en_base_conocimiento(consulta, top_k=top_k)


@tool("consultar_fecha_actual")
def herramienta_fecha_actual() -> str:
    """Devuelve la fecha de hoy en español.

    Úsala cuando el estudiante diga "hoy", "esta semana" o pida calcular un
    plazo relativo al día actual.
    """
    return consultar_fecha_actual()


@tool("consultar_feriados")
def herramienta_feriados(anio: int = 0, solo_proximos: bool = False) -> str:
    """Consulta los feriados nacionales de Chile en la API pública date.nager.at.

    Úsala para responder por feriados, para saber si un día es hábil o para
    calcular plazos que cruzan un feriado.

    Args:
        anio: año a consultar (por ejemplo, 2026). Usa 0 para el año actual.
        solo_proximos: True para listar solo los feriados que quedan desde hoy.
    """
    return consultar_feriados(anio or None, solo_proximos=solo_proximos)


@tool("calcular_plazo")
def herramienta_calcular_plazo(
    fecha_inicio: str, dias_habiles: int, proposito: str = ""
) -> str:
    """Calcula la fecha de vencimiento de un plazo en días hábiles.

    Excluye fines de semana y feriados chilenos (consultados en date.nager.at).
    Úsala para trámites como justificar una inasistencia (3 días hábiles),
    pedir recorrección (5 días hábiles) o entregar un informe de práctica
    (10 días hábiles). Primero confirma el plazo en los reglamentos.

    Args:
        fecha_inicio: fecha del hecho, en formato AAAA-MM-DD, DD/MM/AAAA o "hoy".
        dias_habiles: cantidad de días hábiles del plazo (1 a 365).
        proposito: descripción breve del trámite (opcional).
    """
    return calcular_plazo(fecha_inicio, dias_habiles, proposito)


@tool("redactar_borrador")
def herramienta_redactar_borrador(
    tipo: str,
    motivo: str,
    nombre_estudiante: str = "",
    asignatura: str = "",
    fecha_referencia: str = "",
    detalles: str = "",
    fundamento: str = "",
) -> str:
    """Genera un borrador formal de documento y lo guarda como archivo Markdown.

    Úsala cuando el estudiante pida "redacta", "haz una carta", "prepara una
    justificación" o "necesito un documento". Antes de redactar, busca en los
    reglamentos el plazo y los requisitos aplicables y pásalos en
    ``fundamento``. No inventes datos personales: deja marcadores como [RUT]
    para que el estudiante los complete.

    Args:
        tipo: "justificacion_inasistencia", "solicitud_recorreccion",
            "solicitud_retiro", "solicitud_beneficio" o "carta_general".
        motivo: razón principal del documento, en una o dos frases.
        nombre_estudiante: nombre completo, solo si el estudiante lo entregó.
        asignatura: asignatura involucrada, si corresponde.
        fecha_referencia: fecha del hecho (evaluación, entrega, etc.).
        detalles: antecedentes adicionales que se quieran incluir.
        fundamento: referencia normativa obtenida de buscar_reglamentos.
    """
    borrador = redactar_borrador(
        tipo=tipo,
        motivo=motivo,
        nombre_estudiante=nombre_estudiante,
        asignatura=asignatura,
        fecha_referencia=fecha_referencia,
        detalles=detalles,
        fundamento=fundamento,
    )
    return (
        f"Borrador generado correctamente.\n"
        f"ID: {borrador.id}\n"
        f"Archivo: {borrador.archivo}\n"
        f"Tipo: {borrador.titulo}\n"
        f"Vista previa:\n\n{borrador.contenido}\n\n"
        "En tu respuesta final no repitas el documento completo: indica que ya "
        "está disponible para descargar, resume sus puntos principales y recuerda "
        "completar los campos entre corchetes."
    )


@tool("listar_borradores")
def herramienta_listar_borradores(limite: int = 5) -> str:
    """Lista los últimos borradores generados en esta u otras sesiones.

    Úsala si el estudiante pregunta "¿qué documentos tengo?", "¿dónde quedó el
    borrador?" o necesita retomar una tarea anterior.

    Args:
        limite: cantidad máxima de borradores a listar (1 a 20).
    """
    registros = listar_borradores(limite)
    if not registros:
        return "Todavía no se han generado borradores en este proyecto."
    lineas = ["Borradores generados (del más reciente al más antiguo):"]
    for registro in registros:
        lineas.append(
            f"- ID {registro.get('id')} | {registro.get('titulo')} | "
            f"{registro.get('creado')} | {registro.get('archivo')} | "
            f"{registro.get('resumen', '')}"
        )
    return "\n".join(lineas)


@tool("leer_borrador")
def herramienta_leer_borrador(identificador: str) -> str:
    """Recupera el contenido de un borrador ya generado.

    Úsala para responder preguntas sobre un documento anterior ("agrega el
    teléfono al borrador", "¿qué decía la justificación?") o para continuar
    una tarea retomada.

    Args:
        identificador: ID o nombre de archivo del borrador (se obtiene con
            listar_borradores o con la respuesta de redactar_borrador).
    """
    borrador = leer_borrador(identificador)
    if borrador is None:
        return (
            f'No encontré el borrador "{identificador}". Usa listar_borradores '
            "para ver los documentos disponibles."
        )
    return (
        f"Borrador {borrador.id} ({borrador.titulo}), creado {borrador.creado}:\n\n"
        f"{borrador.contenido}"
    )


HERRAMIENTAS = [
    herramienta_buscar_reglamentos,
    herramienta_fecha_actual,
    herramienta_feriados,
    herramienta_calcular_plazo,
    herramienta_redactar_borrador,
    herramienta_listar_borradores,
    herramienta_leer_borrador,
]

DESCRIPCION_HERRAMIENTAS = """
- buscar_reglamentos: búsqueda semántica en los reglamentos de Duoc UC.
- consultar_fecha_actual: fecha de hoy en español.
- consultar_feriados: feriados de Chile desde date.nager.at.
- calcular_plazo: vencimiento en días hábiles (excluye feriados).
- redactar_borrador: genera y guarda un documento formal en Markdown.
- listar_borradores / leer_borrador: memoria de documentos generados.
"""
