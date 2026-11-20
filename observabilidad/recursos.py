"""Medición de recursos del sistema y proceso (psutil).

Permite capturar memoria RSS, uso de CPU y cantidad de hilos para
observar el costo del modelo de embeddings y el consumo por turno.
"""

from typing import Any

import psutil

# Inicializa y primea la lectura de CPU para evitar valores 0.0 en la primera llamada
_PROCESO = psutil.Process()
try:
    _PROCESO.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None)
except Exception:
    pass


def instantanea() -> dict[str, Any]:
    """Captura el estado actual de memoria y CPU del proceso y sistema."""
    try:
        mem_info = _PROCESO.memory_info()
        rss_mb = round(mem_info.rss / (1024 * 1024), 2)
    except Exception:
        rss_mb = 0.0

    try:
        cpu_proc = round(_PROCESO.cpu_percent(interval=None), 1)
    except Exception:
        cpu_proc = 0.0

    try:
        cpu_sys = round(psutil.cpu_percent(interval=None), 1)
    except Exception:
        cpu_sys = 0.0

    try:
        hilos = _PROCESO.num_threads()
    except Exception:
        hilos = 0

    return {
        "rss_mb": rss_mb,
        "cpu_proceso_pct": cpu_proc,
        "cpu_sistema_pct": cpu_sys,
        "hilos": hilos,
    }


def registrar_recursos(
    momento: str,
    delta_rss_mb: float | None = None,
    *,
    trace_id: str | None = None,
) -> None:
    """Registra un evento 'recursos' en el log de observabilidad."""
    from observabilidad.registro import registrar

    datos = instantanea()
    datos["momento"] = momento
    if delta_rss_mb is not None:
        datos["delta_rss_mb"] = round(delta_rss_mb, 2)

    registrar("recursos", datos, trace_id=trace_id)
