"""Herramientas externas del asistente estudiantil.

Incluye la búsqueda en la base de conocimiento institucional y la consulta de
la fecha actual y de los feriados en Chile (API pública date.nager.at), útil
para calcular plazos académicos.

Autor: Benjamín Quiroz
"""

from datetime import date

import requests

from chatbot.ajustes import FRAGMENTOS_POR_DEFECTO
from chatbot.conocimiento import construir_buscador

_DIAS = [
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
]
_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

_buscador = None


def _obtener_buscador():
    global _buscador
    if _buscador is None:
        _buscador = construir_buscador()
    return _buscador


def buscar_en_base_conocimiento(consulta: str) -> str:
    """Busca información relevante en la base de conocimiento de Duoc."""
    fragmentos = _obtener_buscador()(consulta, top_k=FRAGMENTOS_POR_DEFECTO)
    if not fragmentos:
        return "No se encontró información relacionada en la base de conocimiento."
    bloques = []
    for numero, fragmento in enumerate(fragmentos, 1):
        bloques.append(f"[Resultado {numero}]\n{fragmento}")
    return "\n\n".join(bloques)


def consultar_fecha_actual() -> str:
    """Entrega la fecha actual en español para calcular plazos."""
    hoy = date.today()
    return (
        f"Hoy es {_DIAS[hoy.weekday()]} {hoy.day} de "
        f"{_MESES[hoy.month - 1]} de {hoy.year}."
    )


def consultar_feriados(anio: int = None, reintentos: int = 3) -> str:
    """Consulta los feriados de Chile de un año en la API date.nager.at."""
    anio = anio or date.today().year
    url = f"https://date.nager.at/api/v3/PublicHolidays/{anio}/CL"
    ultimo_error = "sin respuesta"

    for _ in range(reintentos):
        try:
            respuesta = requests.get(
                url,
                headers={"User-Agent": "AsistenteDuoc/1.0"},
                timeout=20,
            )
            respuesta.raise_for_status()
            datos = respuesta.json()
            if not datos:
                return f"No se encontraron feriados para el año {anio}."

            lineas = [
                f"- {feriado['date']}: {feriado['localName']}"
                for feriado in datos
            ]
            return f"Feriados en Chile ({anio}):\n" + "\n".join(lineas)
        except requests.exceptions.Timeout:
            ultimo_error = "timeout"
        except requests.exceptions.RequestException as exc:
            ultimo_error = f"error de conexión: {exc}"
        except (KeyError, ValueError) as exc:
            ultimo_error = f"formato inesperado: {exc}"

    return f"No se pudo consultar los feriados ({ultimo_error})."


HERRAMIENTAS = {
    "buscar_en_base_conocimiento": buscar_en_base_conocimiento,
    "consultar_fecha_actual": consultar_fecha_actual,
    "consultar_feriados": consultar_feriados,
}

DESCRIPCION_HERRAMIENTAS = """
Herramientas disponibles:
- buscar_en_base_conocimiento(consulta): busca información en la base de
  conocimiento de Duoc UC (matrícula, calendario, becas, evaluaciones,
  biblioteca, bienestar, práctica, titulación, pagos y convivencia).
- consultar_fecha_actual(): entrega la fecha de hoy en español.
- consultar_feriados(anio): entrega los feriados de Chile de un año.
"""
