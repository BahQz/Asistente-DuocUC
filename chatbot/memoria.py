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
    def __init__(self, max_turnos: int = MEMORIA_MAX_TURNOS, ruta: str | None = None):
        if max_turnos < 1:
            raise ValueError("max_turnos debe ser mayor o igual a 1")
        self.max_turnos = max_turnos
        self.ruta = ruta
        self._mensajes: deque[BaseMessage] = deque(maxlen=max_turnos * 2)

    def agregar_usuario(self, contenido: str) -> None:
        self._mensajes.append(HumanMessage(content=contenido))

    def agregar_asistente(self, contenido: str) -> None:
        self._mensajes.append(AIMessage(content=contenido))

    def historial(self) -> list[BaseMessage]:
        return list(self._mensajes)

    def como_dicts(self) -> list[dict]:
        return [message_to_dict(mensaje) for mensaje in self._mensajes]

    def turnos(self) -> int:
        return len(self._mensajes) // 2

    def vacia(self) -> bool:
        return not self._mensajes

    def limpiar(self) -> None:
        self._mensajes.clear()

    def guardar(self) -> None:
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
        if not self.ruta or not os.path.exists(self.ruta):
            return
        try:
            datos = json.loads(Path(self.ruta).read_text(encoding="utf-8"))
            mensajes = messages_from_dict(datos)
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            return

        self._mensajes = deque(mensajes, maxlen=self.max_turnos * 2)


MemoriaVentanaDeslizante = MemoriaConversacional


def crear_memoria() -> MemoriaConversacional:
    memoria = MemoriaConversacional(
        max_turnos=MEMORIA_MAX_TURNOS,
        ruta=MEMORIA_RUTA,
    )
    memoria.cargar()
    return memoria
