"""Motor de recuperación de información (RAG) del asistente de Duoc.

Implementa una búsqueda léxica ponderada tipo TF-IDF sobre la base de
conocimiento, usando únicamente la librería estándar. Incluye:

- normalización de texto y acentos,
- eliminación de palabras vacías,
- singularización básica (plurales),
- expansión con sinónimos del dominio,
- ponderación por frecuencia inversa (IDF) y por título.

Cuando ninguna palabra relevante coincide, la recuperación devuelve una lista
vacía para que el agente admita que no cuenta con la información.

Autor: Benjamín Quiroz
"""

import math
import re
import unicodedata

from chatbot.ajustes import BASE_CONOCIMIENTO, FRAGMENTOS_POR_DEFECTO

PALABRAS_VACIAS = {
    "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas",
    "y", "e", "o", "u", "para", "por", "con", "sin", "que", "cual",
    "cuales", "como", "cuanto", "cuanta", "cuantos", "cuantas", "donde",
    "cuando", "porque", "es", "son", "esta", "estan", "al", "en", "a",
    "se", "su", "sus", "mi", "mis", "tu", "tus", "me", "te", "lo", "le",
    "les", "nos", "hay", "si", "no", "mas", "pero", "sobre", "tiene",
    "tengo", "puedo", "debo", "hago", "hacer", "ser", "sera", "fue",
    "era", "mi", "es", "hay", "esta",
}

SINONIMOS = {
    "nota": {"calificacion", "promedio"},
    "calificacion": {"nota", "promedio"},
    "promedio": {"nota", "calificacion"},
    "plata": {"dinero", "arancel", "pago"},
    "dinero": {"arancel", "pago", "cuota"},
    "arancel": {"pago", "cuota", "dinero"},
    "beca": {"beneficio", "becas", "beneficios"},
    "beneficio": {"beca", "beneficios"},
    "horario": {"hora", "atencion"},
    "contacto": {"telefono", "correo", "soporte"},
    "correo": {"contacto", "soporte", "email"},
    "telefono": {"contacto", "numero"},
    "asistencia": {"inasistencia", "presente"},
    "practica": {"practicas"},
    "retiro": {"retirar", "anular"},
    "profesor": {"docente", "academico"},
    "campus": {"sede", "instituto"},
}

FRAGMENTO_PATTERN = re.compile(r"(?m)^(?=##\s)")


def normalizar(texto: str) -> str:
    """Pasa a minúsculas y quita los acentos (á -> a, ñ -> n)."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def _singularizar(palabra: str) -> str:
    """Reduce plurales simples: 'becas' -> 'beca', 'pagos' -> 'pago'."""
    if palabra.endswith("es") and len(palabra) > 4:
        return palabra[:-2]
    if palabra.endswith("s") and len(palabra) > 3:
        return palabra[:-1]
    return palabra


def _tokenizar(texto: str) -> list:
    """Normaliza, separa en palabras, quita vacías y singulariza."""
    brutos = re.findall(r"\w+", normalizar(texto))
    return [
        _singularizar(t)
        for t in brutos
        if t not in PALABRAS_VACIAS and len(t) > 2
    ]


def _expandir(tokens: list) -> list:
    """Agrega sinónimos del dominio a la lista de tokens."""
    ampliados = list(tokens)
    for token in tokens:
        ampliados.extend(SINONIMOS.get(token, set()))
    return ampliados


def cargar_fragmentos() -> list:
    """Lee la base de conocimiento y la divide por secciones ('## ')."""
    with open(BASE_CONOCIMIENTO, "r", encoding="utf-8") as archivo:
        contenido = archivo.read()

    partes = FRAGMENTO_PATTERN.split(contenido)
    return [parte.strip() for parte in partes if parte.strip()]


class IndiceTFIDF:
    """Índice invertido con puntaje TF-IDF sobre la base de conocimiento."""

    def __init__(self, fragmentos: list):
        self.fragmentos = fragmentos
        self._frecuencias = []      # lista de dict {token: conteo}
        self._titulos = []          # tokens del título de cada fragmento
        self._idf = {}

        documento_frecuencia = {}
        for fragmento in fragmentos:
            tokens = _tokenizar(fragmento)
            frecuencias = {}
            for token in tokens:
                frecuencias[token] = frecuencias.get(token, 0) + 1
            self._frecuencias.append(frecuencias)

            titulo = fragmento.splitlines()[0] if fragmento else ""
            self._titulos.append(set(_tokenizar(titulo)))

            for token in set(tokens):
                documento_frecuencia[token] = documento_frecuencia.get(token, 0) + 1

        total = len(fragmentos)
        for token, frecuencia in documento_frecuencia.items():
            self._idf[token] = math.log((total + 1) / (frecuencia + 1)) + 1

    def _puntaje(self, tokens_consulta: list, posicion: int) -> float:
        """Calcula el puntaje TF-IDF de un fragmento para una consulta."""
        frecuencias = self._frecuencias[posicion]
        largo = sum(frecuencias.values()) or 1
        titulo = self._titulos[posicion]

        puntaje = 0.0
        for token in tokens_consulta:
            if token in frecuencias:
                tf = frecuencias[token] / largo
                idf = self._idf.get(token, 0.0)
                puntaje += tf * idf
                if token in titulo:
                    puntaje += 0.75
        return puntaje

    def buscar(self, consulta: str, top_k: int = FRAGMENTOS_POR_DEFECTO) -> list:
        """Devuelve los fragmentos más relevantes o [] si no hay coincidencias."""
        tokens = _expandir(_tokenizar(consulta))
        if not tokens:
            return []

        puntuados = []
        for posicion in range(len(self.fragmentos)):
            puntaje = self._puntaje(tokens, posicion)
            if puntaje > 0:
                puntuados.append((puntaje, self.fragmentos[posicion]))

        if not puntuados:
            return []

        puntuados.sort(key=lambda par: par[0], reverse=True)
        return [fragmento for _, fragmento in puntuados[:top_k]]


def construir_buscador():
    """Carga la base de conocimiento y devuelve una función de búsqueda."""
    indice = IndiceTFIDF(cargar_fragmentos())

    def buscador(consulta: str, top_k: int = FRAGMENTOS_POR_DEFECTO) -> list:
        return indice.buscar(consulta, top_k)

    return buscador
