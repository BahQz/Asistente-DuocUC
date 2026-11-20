"""Cálculo determinista de métricas, KPIs y anomalías (EP3).

Funciones puras para procesar eventos JSONL y calcular:
- Tasas de éxito, bloqueo y derivación.
- Percentiles de latencia (P50, P95) y estadísticas de tokens.
- Precisión de recuperación (Precision@1, Hit@k) y matriz de abstención.
- Consistencia por grupo temático y barrido de umbral de relevancia.
- Detección de anomalías basada en reglas nombradas sin juicios automáticos.
"""

import math
from collections import Counter
from typing import Any

from chatbot.ajustes import AGENTE_MAX_ITERACIONES
from chatbot.seguridad import normalizar_texto_seguro

FRASES_DERIVACION = (
    "mesa de ayuda",
    "soporte@duocuc.cl",
    "600-300-4000",
    "600 300 4000",
    "6003004000",
    "direccion de escuela",
)


def es_derivacion(texto: str) -> bool:
    """Verifica si una respuesta contiene derivación explícita a canales oficiales."""
    if not texto:
        return False
    norm = normalizar_texto_seguro(texto)
    return any(frase in norm for frase in FRASES_DERIVACION)


def calcular_percentil(valores: list[float], percentil: float) -> float:
    """Calcula un percentil con interpolación lineal (equivalente a numpy/pandas)."""
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    n = len(ordenados)
    if n == 1:
        return float(ordenados[0])

    k = (n - 1) * (percentil / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(ordenados[int(k)])
    d0 = ordenados[int(f)] * (c - k)
    d1 = ordenados[int(c)] * (k - f)
    return round(float(d0 + d1), 2)


def calcular_percentiles(valores: list[float]) -> dict[str, float]:
    """Calcula P50 (mediana) y P95 para una serie de valores numéricos."""
    if not valores:
        return {"media": 0.0, "p50": 0.0, "p95": 0.0}
    media = round(sum(valores) / len(valores), 2)
    return {
        "media": media,
        "p50": calcular_percentil(valores, 50.0),
        "p95": calcular_percentil(valores, 95.0),
    }


def tasa_exito(turnos: list[dict[str, Any]]) -> float:
    """Calcula tasa de éxito = ok / (ok + error). Excluye bloqueos de seguridad."""
    oks = sum(1 for t in turnos if t.get("resultado") == "ok")
    errores = sum(1 for t in turnos if t.get("resultado") == "error")
    total = oks + errores
    if total == 0:
        return 0.0
    return round(oks / total, 4)


def tasa_bloqueo(turnos: list[dict[str, Any]]) -> float:
    """Calcula la proporción de turnos bloqueados por guardrails de seguridad."""
    if not turnos:
        return 0.0
    bloqueados = sum(
        1 for t in turnos if str(t.get("resultado", "")).startswith("bloqueado_")
    )
    return round(bloqueados / len(turnos), 4)


def precision_at_1(casos_evaluados: list[dict[str, Any]]) -> float:
    """Precision@1: proporción de casos donde top1_numero está en seccion_esperada."""
    evaluables = [
        c for c in casos_evaluados
        if c.get("esperado", {}).get("seccion_esperada")
    ]
    if not evaluables:
        return 0.0
    aciertos = 0
    for caso in evaluables:
        secciones_esp = caso.get("esperado", {}).get("seccion_esperada", [])
        observado = caso.get("observado", {})
        top1 = str(observado.get("top1_numero", ""))
        if any(sec in top1 or top1 == sec for sec in secciones_esp):
            aciertos += 1
    return round(aciertos / len(evaluables), 4)


def hit_at_k(casos_evaluados: list[dict[str, Any]]) -> float:
    """Hit@k: proporción donde alguna sección esperada apareció en los candidatos recuperados."""
    evaluables = [
        c for c in casos_evaluados
        if c.get("esperado", {}).get("seccion_esperada")
    ]
    if not evaluables:
        return 0.0
    aciertos = sum(
        1 for c in evaluables if c.get("observado", {}).get("hit_topk", False)
    )
    return round(aciertos / len(evaluables), 4)


def matriz_abstencion(casos_evaluados: list[dict[str, Any]]) -> dict[str, Any]:
    """Calcula la matriz de confusión sobre abstención y riesgos de alucinación."""
    tp = fp = tn = fn = 0
    for c in casos_evaluados:
        esperado_abs = bool(c.get("esperado", {}).get("debe_abstenerse"))
        observado_abs = c.get("observado", {}).get("decision") == "abstencion"

        if esperado_abs and observado_abs:
            tp += 1
        elif not esperado_abs and observado_abs:
            fp += 1
        elif not esperado_abs and not observado_abs:
            tn += 1
        elif esperado_abs and not observado_abs:
            fn += 1

    tasa_abstencion_correcta = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    tasa_falsos_rechazos = round(fp / (fp + tn), 4) if (fp + tn) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "tasa_abstencion_correcta": tasa_abstencion_correcta,
        "tasa_falsos_rechazos": tasa_falsos_rechazos,
    }


def consistencia_por_grupo(casos_evaluados: list[dict[str, Any]]) -> dict[str, Any]:
    """Calcula métricas de consistencia entre variantes de un mismo grupo semántico."""
    grupos: dict[str, list[dict[str, Any]]] = {}
    for c in casos_evaluados:
        grupo = c.get("grupo_consistencia")
        if grupo:
            grupos.setdefault(grupo, []).append(c)

    resumen: dict[str, Any] = {}
    for nombre_grupo, casos in grupos.items():
        if len(casos) < 2:
            continue

        # Top-1 modal
        top1_list = [
            str(c.get("observado", {}).get("top1_numero", "")) for c in casos
        ]
        moda_top1, count_top1 = Counter(top1_list).most_common(1)[0]
        consistencia_recuperacion = round(count_top1 / len(casos), 4)

        # Decisión modal
        decisiones = [
            str(c.get("observado", {}).get("decision", "")) for c in casos
        ]
        _, count_dec = Counter(decisiones).most_common(1)[0]
        consistencia_decision = round(count_dec / len(casos), 4)

        # Desviación estándar de scores
        scores = [
            float(c.get("observado", {}).get("top1_score", 0.0)) for c in casos
        ]
        media_score = sum(scores) / len(scores)
        varianza = sum((s - media_score) ** 2 for s in scores) / len(scores)
        std_score = round(math.sqrt(varianza), 4)

        # Consistencia de respuesta (datos clave)
        datos_clave_ok_count = sum(
            1 for c in casos if c.get("observado", {}).get("datos_clave_ok", True)
        )
        consistencia_respuesta = round(datos_clave_ok_count / len(casos), 4)

        resumen[nombre_grupo] = {
            "n_casos": len(casos),
            "consistencia_recuperacion": consistencia_recuperacion,
            "consistencia_decision": consistencia_decision,
            "consistencia_respuesta": consistencia_respuesta,
            "std_score": std_score,
            "top1_modal": moda_top1,
        }

    return resumen


def barrido_umbral(
    candidatos_por_caso: list[dict[str, Any]],
    min_u: float = 0.76,
    max_u: float = 0.92,
    paso: float = 0.01,
) -> list[dict[str, Any]]:
    """Simula abstenciones y rechazos para distintos umbrales de relevancia (datos crudos)."""
    umbrales: list[float] = []
    u = min_u
    while u <= max_u + 1e-9:
        umbrales.append(round(u, 2))
        u += paso

    resultados: list[dict[str, Any]] = []

    for umbral in umbrales:
        tp = fp = tn = fn = 0
        for item in candidatos_por_caso:
            debe_abstenerse = bool(item.get("debe_abstenerse"))
            top1_score = float(item.get("top1_score", 0.0))
            se_abstiene = top1_score < umbral

            if debe_abstenerse and se_abstiene:
                tp += 1
            elif not debe_abstenerse and se_abstiene:
                fp += 1
            elif not debe_abstenerse and not se_abstiene:
                tn += 1
            elif debe_abstenerse and not se_abstiene:
                fn += 1

        tasa_abs = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        tasa_fp = round(fp / (fp + tn), 4) if (fp + tn) > 0 else 0.0

        resultados.append(
            {
                "umbral": umbral,
                "tp": tp,
                "fp": fp,
                "tn": tn,
                "fn": fn,
                "tasa_abstencion_correcta": tasa_abs,
                "tasa_falsos_rechazos": tasa_fp,
            }
        )

    return resultados


def detectar_anomalias(
    turnos: list[dict[str, Any]],
    p95_latencia: float | None = None,
    p95_tokens: float | None = None,
) -> list[dict[str, Any]]:
    """Detecta filas anómalas basándose en reglas nombradas deterministas."""
    if not turnos:
        return []

    latencias = [float(t.get("latencia_total_ms", 0)) for t in turnos]
    tokens = [float(t.get("tokens_total", 0)) for t in turnos]

    p95_lat = p95_latencia if p95_latencia is not None else calcular_percentil(latencias, 95)
    p95_tok = p95_tokens if p95_tokens is not None else calcular_percentil(tokens, 95)

    media_lat = sum(latencias) / len(latencias) if latencias else 0
    var_lat = sum((l - media_lat) ** 2 for l in latencias) / len(latencias) if len(latencias) > 1 else 0
    std_lat = math.sqrt(var_lat) if var_lat > 0 else 1.0

    anomalias: list[dict[str, Any]] = []
    racha_errores = 0

    for idx, t in enumerate(turnos):
        tid = t.get("trace_id", f"turno_{idx}")
        lat = float(t.get("latencia_total_ms", 0))
        tok = float(t.get("tokens_total", 0))
        resultado = t.get("resultado")
        n_herramientas = len(t.get("herramientas") or [])

        # Racha de errores
        if resultado == "error":
            racha_errores += 1
            if racha_errores >= 2:
                anomalias.append(
                    {
                        "trace_id": tid,
                        "regla": "racha_errores_ge_2",
                        "valor_observado": f"{racha_errores} errores consecutivos",
                    }
                )
        else:
            racha_errores = 0

        # Latencia sobre P95
        if p95_lat > 0 and lat > p95_lat:
            anomalias.append(
                {
                    "trace_id": tid,
                    "regla": "latencia_sobre_p95",
                    "valor_observado": f"{lat:.1f} ms (p95={p95_lat:.1f} ms)",
                }
            )

        # Z-score latencia > 2
        zscore_lat = (lat - media_lat) / std_lat if std_lat > 0 else 0
        if zscore_lat > 2.0:
            anomalias.append(
                {
                    "trace_id": tid,
                    "regla": "latencia_zscore_gt_2",
                    "valor_observado": f"z={zscore_lat:.2f} ({lat:.1f} ms)",
                }
            )

        # Tokens sobre P95
        if p95_tok > 0 and tok > p95_tok:
            anomalias.append(
                {
                    "trace_id": tid,
                    "regla": "tokens_sobre_p95",
                    "valor_observado": f"{int(tok)} tokens (p95={int(p95_tok)})",
                }
            )

        # Zona gris de retrieval
        if t.get("zona_gris"):
            anomalias.append(
                {
                    "trace_id": tid,
                    "regla": "zona_gris",
                    "valor_observado": f"top1_score={t.get('top1_score')}",
                }
            )

        # Muchas herramientas (> 3)
        if n_herramientas > 3:
            anomalias.append(
                {
                    "trace_id": tid,
                    "regla": "muchas_herramientas",
                    "valor_observado": f"{n_herramientas} herramientas usadas",
                }
            )

        # Cerca del límite de iteraciones (>= 80% de AGENTE_MAX_ITERACIONES)
        if n_herramientas >= int(0.8 * AGENTE_MAX_ITERACIONES):
            anomalias.append(
                {
                    "trace_id": tid,
                    "regla": "cerca_limite_iteraciones",
                    "valor_observado": f"{n_herramientas} pasos (límite={AGENTE_MAX_ITERACIONES})",
                }
            )

    return anomalias
