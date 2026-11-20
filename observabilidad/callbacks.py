"""Manejador de callbacks de LangChain/LangGraph para observabilidad (EP3).

Captura métricas de latencia por etapa, llamadas a herramientas, uso de tokens
y realiza verificación de defensa en profundidad contra fuga de PII hacia el LLM.
"""

import time
from typing import Any

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from chatbot.seguridad import detectar_pii, enmascarar_obj
from observabilidad.registro import registrar, traza_actual


class ManejadorObservabilidad(BaseCallbackHandler):
    """Callback thread-safe para instrumentar ejecuciones de agentes y herramientas."""

    raise_error: bool = False

    def __init__(self, trace_id: str | None = None) -> None:
        super().__init__()
        self.trace_id = trace_id
        self.tokens_prompt: int = 0
        self.tokens_completion: int = 0
        self.tokens_total: int = 0
        self.tokens_estimados: bool = False
        self.n_llamadas_llm: int = 0
        self.herramientas: list[str] = []

        self._inicios_llm: dict[str, float] = {}
        self._inicios_tool: dict[str, float] = {}
        self._args_tool: dict[str, Any] = {}

    def _offset_ms(self, t0: float) -> float:
        traza = traza_actual() or {}
        inicio_turno = traza.get("inicio_perf")
        if inicio_turno is not None:
            return round((t0 - inicio_turno) * 1000, 2)
        return 0.0

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        t0 = time.perf_counter()
        self._inicios_llm[str(run_id)] = t0

        # Defensa en profundidad: auditar que ningún mensaje enviado al modelo contenga PII cruda
        conteos_totales: dict[str, int] = {}
        for lista_msgs in messages:
            for msg in lista_msgs:
                contenido = getattr(msg, "content", "")
                if isinstance(contenido, str) and contenido:
                    conteos = detectar_pii(contenido)
                    for k, v in conteos.items():
                        conteos_totales[k] = conteos_totales.get(k, 0) + v

        if conteos_totales:
            registrar(
                "seguridad",
                {
                    "control": "pii_hacia_proveedor",
                    "accion": "alertado",
                    "severidad": "alta",
                    "detalle": conteos_totales,
                },
                trace_id=self.trace_id,
            )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        t0 = self._inicios_llm.pop(str(run_id), time.perf_counter())
        duracion_ms = round((time.perf_counter() - t0) * 1000, 2)
        offset_ms = self._offset_ms(t0)
        self.n_llamadas_llm += 1

        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        estimado = False

        # Intentar extraer de usage_metadata en generaciones
        for generacion_lista in response.generations:
            for gen in generacion_lista:
                msg = getattr(gen, "message", None)
                if msg is not None:
                    usage = getattr(msg, "usage_metadata", None)
                    if isinstance(usage, dict) and usage:
                        prompt_tokens += usage.get("input_tokens", 0)
                        completion_tokens += usage.get("output_tokens", 0)
                        total_tokens += usage.get("total_tokens", 0)

        # Fallback a response.llm_output
        if total_tokens == 0 and response.llm_output:
            token_usage = response.llm_output.get("token_usage") or {}
            prompt_tokens = token_usage.get("prompt_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens", 0)
            total_tokens = token_usage.get("total_tokens", 0)

        # Fallback a estimación por longitud de caracteres si el proveedor no reportó tokens
        if total_tokens == 0:
            texto_acumulado = ""
            for generacion_lista in response.generations:
                for gen in generacion_lista:
                    texto_acumulado += str(getattr(gen, "text", ""))
            total_tokens = max(1, len(texto_acumulado) // 4)
            completion_tokens = total_tokens
            estimado = True
            self.tokens_estimados = True

        self.tokens_prompt += prompt_tokens
        self.tokens_completion += completion_tokens
        self.tokens_total += total_tokens

        modelo = ""
        if response.llm_output:
            modelo = str(response.llm_output.get("model_name", ""))

        registrar(
            "etapa",
            {
                "nombre": "llm",
                "componente": "llm",
                "detalle": {
                    "idx": self.n_llamadas_llm,
                    "modelo": modelo,
                    "tokens_prompt": prompt_tokens,
                    "tokens_completion": completion_tokens,
                    "tokens_total": total_tokens,
                    "tokens_estimados": estimado,
                },
                "offset_ms": offset_ms,
                "duracion_ms": duracion_ms,
                "ok": True,
            },
            trace_id=self.trace_id,
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        t0 = self._inicios_llm.pop(str(run_id), time.perf_counter())
        duracion_ms = round((time.perf_counter() - t0) * 1000, 2)
        offset_ms = self._offset_ms(t0)

        registrar(
            "etapa",
            {
                "nombre": "llm",
                "componente": "llm",
                "detalle": {"error": str(error)},
                "offset_ms": offset_ms,
                "duracion_ms": duracion_ms,
                "ok": False,
            },
            trace_id=self.trace_id,
        )

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        t0 = time.perf_counter()
        rid = str(run_id)
        self._inicios_tool[rid] = t0
        nombre = serialized.get("name") or "herramienta"
        self.herramientas.append(nombre)
        self._args_tool[rid] = inputs or {"input": input_str}

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        t0 = self._inicios_tool.pop(rid, time.perf_counter())
        duracion_ms = round((time.perf_counter() - t0) * 1000, 2)
        offset_ms = self._offset_ms(t0)

        args_originales = self._args_tool.pop(rid, {})
        args_masc = enmascarar_obj(args_originales)
        # Regla de privacidad: el argumento nombre_estudiante siempre se registra como [NOMBRE]
        if isinstance(args_masc, dict) and "nombre_estudiante" in args_masc:
            args_masc["nombre_estudiante"] = "[NOMBRE]"

        salida_texto = getattr(output, "content", str(output or ""))
        salida_masc = enmascarar_obj(salida_texto)

        ok = True
        error_tipo = None
        if not salida_texto:
            ok = False
            error_tipo = "salida_vacia"
        elif salida_texto.startswith("No se encontraron fragmentos"):
            ok = False
            error_tipo = "sin_resultados"

        nombre = self.herramientas[-1] if self.herramientas else "herramienta"

        registrar(
            "etapa",
            {
                "nombre": "herramienta",
                "componente": "herramienta",
                "detalle": {
                    "nombre": nombre,
                    "args_masc": args_masc,
                    "salida_resumen_masc": salida_masc,
                    "ok": ok,
                    "error_tipo": error_tipo,
                },
                "offset_ms": offset_ms,
                "duracion_ms": duracion_ms,
                "ok": ok,
            },
            trace_id=self.trace_id,
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        t0 = self._inicios_tool.pop(rid, time.perf_counter())
        duracion_ms = round((time.perf_counter() - t0) * 1000, 2)
        offset_ms = self._offset_ms(t0)
        nombre = self.herramientas[-1] if self.herramientas else "herramienta"

        registrar(
            "etapa",
            {
                "nombre": "herramienta",
                "componente": "herramienta",
                "detalle": {
                    "nombre": nombre,
                    "error": str(error),
                    "ok": False,
                    "error_tipo": "excepcion",
                },
                "offset_ms": offset_ms,
                "duracion_ms": duracion_ms,
                "ok": False,
            },
            trace_id=self.trace_id,
        )
