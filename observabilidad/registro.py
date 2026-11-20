"""Escritor estructurado JSONL thread-safe y gestor de contexto de traza.

Maneja la persistencia resiliente de eventos de observabilidad en formato JSONL,
con degradación silenciosa y propagación de traza vía ContextVar.
"""

import contextvars
import json
import threading
import time
import uuid
import warnings
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from chatbot.ajustes import OBS_ACTIVA, OBS_DIR, OBS_TRUNCAR_CHARS
from observabilidad.esquema import VERSION_ESQUEMA

_TRAZA_CTX: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "traza_actual", default=None
)
_FALLBACK_TRAZAS: dict[int, dict[str, Any]] = {}
_FALLBACK_LOCK = threading.Lock()
_ESCRIBIR_LOCK = threading.Lock()
_WARNED_ERROR = False


def iniciar_traza(
    session_id: str | None = None,
    origen: str = "app",
    run_id: str | None = None,
) -> str:
    """Inicia una nueva traza de ejecución y la asigna al contexto actual."""
    trace_id = uuid.uuid4().hex
    info_traza = {
        "trace_id": trace_id,
        "session_id": session_id or uuid.uuid4().hex,
        "origen": origen,
        "run_id": run_id,
        "inicio_perf": time.perf_counter(),
        "turno_frio": False,
    }
    _TRAZA_CTX.set(info_traza)
    ident = threading.get_ident()
    with _FALLBACK_LOCK:
        _FALLBACK_TRAZAS[ident] = info_traza
    return trace_id


def marcar_turno_frio() -> None:
    """Marca el turno activo como frío (disparó carga de modelo o índice)."""
    traza = traza_actual()
    if traza:
        traza["turno_frio"] = True


def traza_actual() -> dict[str, Any] | None:
    """Retorna los metadatos de la traza activa en el contexto actual."""
    ctx = _TRAZA_CTX.get()
    if ctx is not None:
        return ctx
    ident = threading.get_ident()
    with _FALLBACK_LOCK:
        return _FALLBACK_TRAZAS.get(ident)


def limpiar_traza() -> None:
    """Limpia la traza activa."""
    _TRAZA_CTX.set(None)
    ident = threading.get_ident()
    with _FALLBACK_LOCK:
        _FALLBACK_TRAZAS.pop(ident, None)


def _truncar_valores(obj: Any, max_len: int = OBS_TRUNCAR_CHARS) -> Any:
    """Trunca recursivamente cadenas largas en estructuras de datos."""
    if isinstance(obj, str):
        if len(obj) > max_len:
            return obj[:max_len] + " […]"
        return obj
    if isinstance(obj, dict):
        return {k: _truncar_valores(v, max_len) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_truncar_valores(item, max_len) for item in obj]
    return obj


def registrar(
    tipo: str,
    datos: dict[str, Any],
    *,
    trace_id: str | None = None,
    session_id: str | None = None,
    origen: str | None = None,
    run_id: str | None = None,
) -> None:
    """Escribe un evento en formato JSONL de forma thread-safe y resiliente."""
    if not OBS_ACTIVA:
        return

    global _WARNED_ERROR
    try:
        traza = traza_actual() or {}
        tid = trace_id or traza.get("trace_id")
        sid = session_id or traza.get("session_id")
        orig = origen or traza.get("origen", "app")
        rid = run_id or traza.get("run_id")

        evento = {
            "v": VERSION_ESQUEMA,
            "ts": datetime.now(timezone.utc).isoformat(),
            "trace_id": tid,
            "session_id": sid,
            "run_id": rid,
            "origen": orig,
            "tipo": tipo,
            "datos": _truncar_valores(datos),
        }

        linea = json.dumps(evento, ensure_ascii=False)
        ruta_dir = Path(OBS_DIR)
        ruta_dir.mkdir(parents=True, exist_ok=True)
        ruta_archivo = ruta_dir / "eventos.jsonl"

        with _ESCRIBIR_LOCK:
            with open(ruta_archivo, "a", encoding="utf-8") as f:
                f.write(linea + "\n")

    except Exception as exc:
        if not _WARNED_ERROR:
            warnings.warn(
                f"[observabilidad] No se pudo escribir evento en {OBS_DIR}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            _WARNED_ERROR = True


@contextmanager
def medir_etapa(
    nombre: str,
    componente: str,
    detalle: dict[str, Any] | None = None,
    *,
    trace_id: str | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Mide la duración de una etapa y registra el evento automáticamente."""
    traza = traza_actual() or {}
    inicio_turno = traza.get("inicio_perf")
    t0 = time.perf_counter()
    offset_ms = (
        round((t0 - inicio_turno) * 1000, 2)
        if inicio_turno is not None
        else 0.0
    )

    info_detalle = dict(detalle or {})
    ok = True
    try:
        yield info_detalle
    except Exception:
        ok = False
        raise
    finally:
        duracion_ms = round((time.perf_counter() - t0) * 1000, 2)
        registrar(
            "etapa",
            {
                "nombre": nombre,
                "componente": componente,
                "detalle": info_detalle,
                "offset_ms": offset_ms,
                "duracion_ms": duracion_ms,
                "ok": ok,
            },
            trace_id=trace_id,
        )
