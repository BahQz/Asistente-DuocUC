"""Memoria conversacional de corto plazo del agente.

Se implementa una **ventana deslizante de mensajes** sobre
``collections.deque`` y los tipos de mensaje de LangChain
(``HumanMessage`` / ``AIMessage``). Es el equivalente moderno de
``ConversationBufferWindowMemory``: conserva los últimos ``max_turnos``
intercambios, acota el prompt y permite persistir la sesión en disco.

La memoria de largo plazo no vive aquí: los reglamentos se recuperan desde
ChromaDB (``chatbot/conocimiento.py``) y los borradores generados se guardan en
``chatbot/documentos.py``.

Autor: Benjamín Quiroz
"""

import json
import os
from collections import deque
from pathlib import Path

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    message_to_dict,
    messages_from_dict,
)

from chatbot.ajustes import MEMORIA_MAX_TURNOS, MEMORIA_RUTA


class MemoriaConversacional:
    """Ventana de los últimos intercambios usuario/asistente."""

    def __init__(self, max_turnos: int = MEMORIA_MAX_TURNOS, ruta: str | None = None):
        if max_turnos < 1:
            raise ValueError("max_turnos debe ser mayor o igual a 1")
        self.max_turnos = max_turnos
        self.ruta = ruta
        self._mensajes: deque[BaseMessage] = deque(maxlen=max_turnos * 2)

    # ------------------------------------------------------------- escritura
    def agregar_usuario(self, contenido: str) -> None:
        """Registra el mensaje del estudiante."""
        self._mensajes.append(HumanMessage(content=contenido))

    def agregar_asistente(self, contenido: str) -> None:
        """Registra la respuesta final del agente."""
        self._mensajes.append(AIMessage(content=contenido))

    # -------------------------------------------------------------- lectura
    def historial(self) -> list[BaseMessage]:
        """Devuelve una copia de la ventana actual como mensajes LangChain."""
        return list(self._mensajes)

    def como_dicts(self) -> list[dict]:
        """Devuelve la ventana serializada (útil para la interfaz)."""
        return [message_to_dict(mensaje) for mensaje in self._mensajes]

    def turnos(self) -> int:
        """Cantidad de intercambios completos almacenados."""
        return len(self._mensajes) // 2

    def vacia(self) -> bool:
        return not self._mensajes

    # ------------------------------------------------------------- limpieza
    def limpiar(self) -> None:
        """Vacía por completo la conversación."""
        self._mensajes.clear()

    # --------------------------------------------------------- persistencia
    def guardar(self) -> None:
        """Guarda la conversación en disco si hay una ruta configurada."""
        if not self.ruta:
            return
        carpeta = os.path.dirname(self.ruta)
        if carpeta:
            Path(carpeta).mkdir(parents=True, exist_ok=True)
        Path(self.ruta).write_text(
            json.dumps(self.como_dicts(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def cargar(self) -> None:
        """Recupera la conversación desde disco si el archivo existe."""
        if not self.ruta or not os.path.exists(self.ruta):
            return
        try:
            datos = json.loads(Path(self.ruta).read_text(encoding="utf-8"))
            mensajes = messages_from_dict(datos)
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            return

        self._mensajes = deque(mensajes, maxlen=self.max_turnos * 2)


# Alias de compatibilidad con la EP1 (la clase cambió de nombre, no de rol).
MemoriaVentanaDeslizante = MemoriaConversacional


def crear_memoria() -> MemoriaConversacional:
    """Crea la memoria de sesión de la consola con la ventana configurada."""
    memoria = MemoriaConversacional(
        max_turnos=MEMORIA_MAX_TURNOS,
        ruta=MEMORIA_RUTA,
    )
    memoria.cargar()
    return memoria
