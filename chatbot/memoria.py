"""Memoria conversacional del asistente estudiantil.

Implementa una memoria de ventana deslizante apoyada en ``collections.deque``:
conserva los últimos ``max_turnos`` intercambios y descarta los más antiguos
automáticamente. La sesión puede persistirse en disco.

Autor: Benjamín Quiroz
"""

import json
import os
from collections import deque

from chatbot.ajustes import MEMORIA_MAX_TURNOS, MEMORIA_RUTA


class MemoriaVentanaDeslizante:
    """Ventana deslizante de turnos en formato de chat de OpenAI."""

    def __init__(self, max_turnos: int = 6, ruta: str = None):
        self.max_turnos = max_turnos
        self.ruta = ruta
        self._buffer = deque(maxlen=max_turnos * 2)

    def agregar_usuario(self, contenido: str) -> None:
        """Registra el mensaje del estudiante."""
        self._buffer.append({"role": "user", "content": contenido})

    def agregar_asistente(self, contenido: str) -> None:
        """Registra la respuesta del asistente."""
        self._buffer.append({"role": "assistant", "content": contenido})

    def historial(self) -> list:
        """Devuelve una copia de la ventana actual."""
        return list(self._buffer)

    def limpiar(self) -> None:
        """Vacía por completo la conversación."""
        self._buffer.clear()

    def guardar(self) -> None:
        """Guarda la conversación en disco si hay una ruta configurada."""
        if not self.ruta:
            return
        carpeta = os.path.dirname(self.ruta)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
        with open(self.ruta, "w", encoding="utf-8") as archivo:
            json.dump(list(self._buffer), archivo, ensure_ascii=False, indent=2)

    def cargar(self) -> None:
        """Recupera la conversación desde disco si el archivo existe."""
        if not self.ruta or not os.path.exists(self.ruta):
            return
        try:
            with open(self.ruta, "r", encoding="utf-8") as archivo:
                mensajes = json.load(archivo)
        except (json.JSONDecodeError, OSError):
            return

        self._buffer = deque(mensajes, maxlen=self.max_turnos * 2)


def crear_memoria() -> MemoriaVentanaDeslizante:
    """Crea la memoria de sesión con la ventana configurada."""
    memoria = MemoriaVentanaDeslizante(
        max_turnos=MEMORIA_MAX_TURNOS,
        ruta=MEMORIA_RUTA,
    )
    memoria.cargar()
    return memoria
