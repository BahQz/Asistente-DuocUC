"""Herramienta de escritura: generación y memoria de borradores.

Los borradores se construyen con plantillas institucionales en Markdown, se
guardan en ``documentos/`` y se registran en ``documentos/registro.json``.
Ese registro funciona como **memoria de artefactos**: permite que el agente
recupere un documento generado varios turnos antes, aunque ya haya salido de la
ventana de memoria conversacional.

Las plantillas incluyen referencias explícitas a la base de conocimiento
institucional (por ejemplo, Sección 4.3 para justificaciones). Los datos que el
estudiante no entrega quedan como marcadores entre corchetes para que los
complete antes de firmar.

Autor: Benjamín Quiroz
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

from chatbot.ajustes import DOCUMENTOS_DIR, PROYECTO_RAIZ

_CANDADO = Lock()
_REGISTRO = "registro.json"

_DIAS = [
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
]
_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

TIPOS_VALIDOS = {
    "justificacion_inasistencia": "Justificación de inasistencia",
    "solicitud_recorreccion": "Solicitud de recorrección",
    "solicitud_retiro": "Solicitud de retiro de asignatura",
    "solicitud_beneficio": "Solicitud de beneficio estudiantil",
    "carta_general": "Carta formal general",
}

FUNDAMENTOS = {
    "justificacion_inasistencia": (
        "De acuerdo con la base de conocimiento institucional (Sección 4.3), "
        "las evaluaciones atrasadas solo se reprograman con justificación "
        "presentada en la Secretaría de Estudios dentro de 3 días hábiles."
    ),
    "solicitud_recorreccion": (
        "De acuerdo con la base de conocimiento institucional (Sección 4.3), "
        "la recorrección de una evaluación se solicita dentro de 5 días hábiles "
        "desde la entrega de la nota, mediante formulario en la Dirección de "
        "Escuela."
    ),
    "solicitud_retiro": (
        "De acuerdo con la base de conocimiento institucional (Sección 2.3), "
        "el retiro sin registro en el historial se permite hasta la semana 8; "
        "entre las semanas 9 y 12 el retiro queda con nota \"W\" y después de "
        "la semana 12 no es posible retirar asignaturas del periodo."
    ),
    "solicitud_beneficio": (
        "De acuerdo con la base de conocimiento institucional (Sección 3), "
        "los beneficios se solicitan en el portal de beneficios y su "
        "mantención exige aprobar las asignaturas, conservar el promedio "
        "exigido y no registrar sanciones disciplinarias graves."
    ),
    "carta_general": "",
}


@dataclass
class Borrador:
    """Documento generado y persistido."""

    id: str
    archivo: str
    tipo: str
    titulo: str
    creado: str
    contenido: str


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _normalizar(texto)).strip("-") or "documento"


def _fecha_larga(fecha: date | None = None) -> str:
    fecha = fecha or date.today()
    return (
        f"{_DIAS[fecha.weekday()]} {fecha.day} de "
        f"{_MESES[fecha.month - 1]} de {fecha.year}"
    )


def _detectar_tipo(tipo: str) -> str:
    """Mapea texto libre del agente a uno de los tipos de plantilla."""
    clave = _normalizar(tipo).replace(" ", "_")
    if clave in TIPOS_VALIDOS:
        return clave

    equivalencias = {
        "inasistencia": "justificacion_inasistencia",
        "justificacion": "justificacion_inasistencia",
        "justificar": "justificacion_inasistencia",
        "recorreccion": "solicitud_recorreccion",
        "reclamacion_nota": "solicitud_recorreccion",
        "retiro": "solicitud_retiro",
        "retirar": "solicitud_retiro",
        "beca": "solicitud_beneficio",
        "beneficio": "solicitud_beneficio",
        "carta": "carta_general",
        "general": "carta_general",
    }
    for palabra, destino in equivalencias.items():
        if palabra in clave:
            return destino
    return "carta_general"


def _cuerpo(tipo: str, datos: dict) -> str:
    nombre = datos["nombre"] or "[Nombre completo]"
    asignatura = datos["asignatura"] or "[Asignatura]"
    fecha_referencia = datos["fecha_referencia"] or "[Fecha de la evaluación]"
    motivo = datos["motivo"] or "[Motivo o situación]"
    detalles = datos["detalles"].strip()
    fundamento = datos["fundamento"].strip()
    bloque_detalles = f"\n{detalles}\n" if detalles else ""
    bloque_fundamento = f"\n{fundamento}\n" if fundamento else ""

    if tipo == "justificacion_inasistencia":
        return f"""Por medio de la presente, yo, {nombre}, RUT [RUT], estudiante de la carrera de [Carrera] en la sede [Sede], comunico a ustedes que no pude asistir a {asignatura} el día {fecha_referencia}, debido a {motivo}.
{bloque_detalles}
{bloque_fundamento}
En virtud de lo anterior, solicito la reprogramación de la evaluación y quedo atento(a) a los pasos administrativos que correspondan. Adjunto los antecedentes de respaldo: [certificado médico / documento pertinente].

Agradezco de antemano su gestión."""

    if tipo == "solicitud_recorreccion":
        return f"""Por medio de la presente, yo, {nombre}, RUT [RUT], estudiante de la carrera de [Carrera] en la sede [Sede], solicito formalmente la recorrección de la evaluación de {asignatura}, correspondiente al día {fecha_referencia}.
{bloque_detalles}
{bloque_fundamento}
Solicito que se revise la pauta de corrección y se me informe por escrito el resultado de la recorrección. Adjunto copia de la evaluación y de la pauta entregada.

Agradezco de antemano su gestión."""

    if tipo == "solicitud_retiro":
        return f"""Por medio de la presente, yo, {nombre}, RUT [RUT], estudiante de la carrera de [Carrera] en la sede [Sede], solicito el retiro de la asignatura {asignatura}, en la fecha {fecha_referencia}.
{bloque_detalles}
{bloque_fundamento}
Declaro conocer las consecuencias académicas y administrativas de esta solicitud y solicito que se registre en mi historial académico según la normativa vigente.

Agradezco de antemano su gestión."""

    if tipo == "solicitud_beneficio":
        return f"""Por medio de la presente, yo, {nombre}, RUT [RUT], estudiante de la carrera de [Carrera] en la sede [Sede], presento mi solicitud para el beneficio estudiantil correspondiente a {motivo}.
{bloque_detalles}
{bloque_fundamento}
Declaro que la información entregada es verídica y autorizo su verificación. Adjunto los antecedentes solicitados: [documentos de respaldo].

Agradezco de antemano su gestión."""

    return f"""Por medio de la presente, yo, {nombre}, RUT [RUT], estudiante de la carrera de [Carrera] en la sede [Sede], me dirijo a ustedes para exponer lo siguiente:

{motivo}
{bloque_detalles}
{bloque_fundamento}
Solicito que se evalúe mi situación y se me informe sobre los pasos a seguir.

Agradezco de antemano su gestión."""


def _armar_documento(tipo: str, datos: dict) -> str:
    titulo = TIPOS_VALIDOS[tipo]
    return f"""# {titulo}

> **BORRADOR GENERADO AUTOMÁTICAMENTE.** Revísalo, completa los campos entre corchetes, adjunta los respaldos y fírmalo antes de presentarlo. No reemplaza la orientación de la Dirección de Escuela ni de la mesa de ayuda.

{datos["fecha_documento"]}

**Señores**
Dirección de Escuela / Secretaría de Estudios
Duoc UC
Presente

**Asunto:** {titulo}

De mi consideración:

{_cuerpo(tipo, datos)}

Atentamente,

**{datos["nombre"] or "[Nombre completo]"}**
RUT [RUT] — [Carrera] — [Sede]
[Correo institucional] — [Teléfono]

---

*Documento generado por el Asistente Estudiantil Duoc UC. Verifica los datos y plazos en la base de conocimiento institucional o con la mesa de ayuda (soporte@duocuc.cl / 600-300-4000).*
"""


def _ruta_registro() -> Path:
    return Path(DOCUMENTOS_DIR) / _REGISTRO


def _leer_registro() -> list[dict]:
    try:
        datos = json.loads(_ruta_registro().read_text(encoding="utf-8"))
        return datos if isinstance(datos, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _escribir_registro(registros: list[dict]) -> None:
    Path(DOCUMENTOS_DIR).mkdir(parents=True, exist_ok=True)
    temporal = _ruta_registro().with_suffix(".tmp")
    temporal.write_text(
        json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporal.replace(_ruta_registro())


def _ruta_visible(ruta: Path) -> str:
    try:
        return ruta.resolve().relative_to(PROYECTO_RAIZ.resolve()).as_posix()
    except ValueError:
        return ruta.as_posix()


def generar_borrador(
    tipo: str,
    motivo: str,
    nombre_estudiante: str = "",
    asignatura: str = "",
    fecha_referencia: str = "",
    detalles: str = "",
    fundamento: str = "",
) -> Borrador:
    """Genera un borrador formal, lo guarda y lo registra.

    Args:
        tipo: tipo de documento (justificación, recorrección, retiro, beneficio
            o carta general). Se aceptan variantes en lenguaje natural.
        motivo: razón principal del documento.
        nombre_estudiante: nombre completo, si se conoce.
        asignatura: asignatura involucrada, si corresponde.
        fecha_referencia: fecha del hecho (evaluación, entrega, etc.).
        detalles: antecedentes adicionales que el estudiante quiera incluir.
        fundamento: referencia normativa. Si se omite, se usa la de la base de
            conocimiento institucional para ese tipo de documento.

    Returns:
        El borrador generado, con su ruta y contenido.
    """
    tipo_normalizado = _detectar_tipo(tipo)
    titulo = TIPOS_VALIDOS[tipo_normalizado]

    datos = {
        "nombre": (nombre_estudiante or "").strip(),
        "asignatura": (asignatura or "").strip(),
        "fecha_referencia": (fecha_referencia or "").strip(),
        "motivo": (motivo or "").strip(),
        "detalles": (detalles or "").strip(),
        "fundamento": (fundamento or FUNDAMENTOS[tipo_normalizado]).strip(),
        "fecha_documento": f"Santiago, {_fecha_larga()}",
    }

    contenido = _armar_documento(tipo_normalizado, datos)

    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    identificador = f"{marca}-{uuid4().hex[:4]}"
    nombre_archivo = f"{marca}_{_slug(tipo_normalizado)}_{identificador[-4:]}.md"

    Path(DOCUMENTOS_DIR).mkdir(parents=True, exist_ok=True)
    ruta = Path(DOCUMENTOS_DIR) / nombre_archivo
    ruta.write_text(contenido, encoding="utf-8")

    borrador = Borrador(
        id=identificador,
        archivo=_ruta_visible(ruta),
        tipo=tipo_normalizado,
        titulo=titulo,
        creado=datetime.now().isoformat(timespec="seconds"),
        contenido=contenido,
    )

    with _CANDADO:
        registros = _leer_registro()
        registros.insert(
            0,
            {
                "id": borrador.id,
                "archivo": borrador.archivo,
                "tipo": borrador.tipo,
                "titulo": borrador.titulo,
                "creado": borrador.creado,
                "resumen": (motivo or titulo)[:180],
            },
        )
        _escribir_registro(registros[:100])

    return borrador


def listar_borradores(limite: int = 10) -> list[dict]:
    """Lista los borradores registrados, del más reciente al más antiguo."""
    registros = _leer_registro()
    return registros[: max(1, int(limite))]


def leer_borrador(identificador: str) -> Borrador | None:
    """Recupera un borrador por ID, nombre de archivo o prefijo de ambos."""
    buscado = (identificador or "").strip()
    if not buscado:
        return None

    for registro in _leer_registro():
        archivo = str(registro.get("archivo", ""))
        id_registro = str(registro.get("id", ""))
        nombre = Path(archivo).name
        if buscado in (id_registro, archivo, nombre):
            ruta = PROYECTO_RAIZ / archivo
            if not ruta.exists():
                ruta = Path(DOCUMENTOS_DIR) / nombre
            if not ruta.exists():
                continue
            return Borrador(
                id=id_registro,
                archivo=archivo,
                tipo=str(registro.get("tipo", "")),
                titulo=str(registro.get("titulo", "")),
                creado=str(registro.get("creado", "")),
                contenido=ruta.read_text(encoding="utf-8"),
            )

    return None
