"""Generador de gráficos Plotly y utilidades de carga de datos para el Dashboard (EP3).

Este módulo es una librería pura (NO importa Streamlit) para que todas las figuras
puedan ser testeadas con pruebas unitarias sin levantar el servidor web.
"""

from collections import Counter
from typing import Any

import plotly.graph_objects as go

PALETA_DUOC = {
    "azul_oscuro": "#00205b",
    "azul_primario": "#0033a0",
    "azul_acento": "#0b57d0",
    "azul_claro": "#eaf1ff",
    "amarillo": "#ffb81c",
    "rojo": "#d9381e",
    "verde": "#137333",
    "gris": "#7a869c",
    "gris_claro": "#f2f6ff",
}


def figura_latencia_por_turno(
    turnos: list[dict[str, Any]],
    p50: float = 0.0,
    p95: float = 0.0,
) -> go.Figure:
    """Gráfico de dispersión/línea de latencia a lo largo de los turnos."""
    fig = go.Figure()
    if not turnos:
        fig.update_layout(title="Sin datos de turnos")
        return fig

    indices = list(range(1, len(turnos) + 1))
    latencias = [float(t.get("latencia_total_ms", 0)) for t in turnos]
    hover_texts = [
        f"Turno #{idx}<br>Latencia: {lat:.1f} ms<br>Tokens: {t.get('tokens_total', 0)}<br>Resultado: {t.get('resultado')}"
        for idx, (lat, t) in enumerate(zip(latencias, turnos), 1)
    ]

    colores = [
        PALETA_DUOC["rojo"] if t.get("resultado") == "error"
        else (PALETA_DUOC["amarillo"] if str(t.get("resultado", "")).startswith("bloqueado")
              else PALETA_DUOC["azul_acento"])
        for t in turnos
    ]

    fig.add_trace(
        go.Scatter(
            x=indices,
            y=latencias,
            mode="lines+markers",
            name="Latencia turno",
            line={"color": PALETA_DUOC["azul_primario"], "width": 2},
            marker={"size": 7, "color": colores},
            text=hover_texts,
            hoverinfo="text",
        )
    )

    if p50 > 0:
        fig.add_hline(
            y=p50,
            line_dash="dash",
            line_color=PALETA_DUOC["verde"],
            annotation_text=f"P50: {p50:.1f} ms",
            annotation_position="bottom right",
        )
    if p95 > 0:
        fig.add_hline(
            y=p95,
            line_dash="dot",
            line_color=PALETA_DUOC["rojo"],
            annotation_text=f"P95: {p95:.1f} ms",
            annotation_position="top right",
        )

    fig.update_layout(
        title="Latencia Total por Turno (ms)",
        xaxis_title="Número de Turno",
        yaxis_title="Latencia (ms)",
        template="plotly_white",
        height=380,
        margin={"l": 40, "r": 40, "t": 50, "b": 40},
    )
    return fig


def figura_desglose_latencia_etapas(etapas: list[dict[str, Any]]) -> go.Figure:
    """Diagrama de cajas de latencia por componente del sistema."""
    fig = go.Figure()
    if not etapas:
        fig.update_layout(title="Sin datos de etapas")
        return fig

    componentes = ["guardrail", "embeddings", "retrieval", "llm", "herramienta", "api_externa"]
    for comp in componentes:
        vals = [
            float(e.get("duracion_ms", 0))
            for e in etapas
            if e.get("componente") == comp
        ]
        if vals:
            fig.add_trace(
                go.Box(
                    y=vals,
                    name=comp,
                    boxpoints="outliers",
                    marker_color=PALETA_DUOC["azul_acento"],
                )
            )

    fig.update_layout(
        title="Distribución de Latencia por Componente (ms)",
        yaxis_title="Duración (ms)",
        template="plotly_white",
        height=400,
        margin={"l": 40, "r": 40, "t": 50, "b": 40},
    )
    return fig


def figura_barras_apiladas_etapas(
    turnos: list[dict[str, Any]],
    etapas_por_turno: dict[str, list[dict[str, Any]]],
) -> go.Figure:
    """Barras apiladas de tiempo por etapa en cada turno."""
    fig = go.Figure()
    if not turnos:
        fig.update_layout(title="Sin datos de turnos")
        return fig

    nombres_turnos = [f"#{idx}" for idx in range(1, len(turnos) + 1)]
    componentes = ["guardrail", "retrieval", "llm", "herramienta"]
    colores_comp = {
        "guardrail": PALETA_DUOC["amarillo"],
        "retrieval": PALETA_DUOC["azul_primario"],
        "llm": PALETA_DUOC["azul_acento"],
        "herramienta": PALETA_DUOC["verde"],
    }

    for comp in componentes:
        tiempos = []
        for t in turnos:
            tid = t.get("trace_id")
            etapas_t = etapas_por_turno.get(tid, [])
            total_comp = sum(
                float(e.get("duracion_ms", 0))
                for e in etapas_t
                if e.get("componente") == comp
            )
            tiempos.append(round(total_comp, 1))

        fig.add_trace(
            go.Bar(
                name=comp,
                x=nombres_turnos,
                y=tiempos,
                marker_color=colores_comp.get(comp, PALETA_DUOC["gris"]),
            )
        )

    fig.update_layout(
        barmode="stack",
        title="Desglose de Tiempo por Turno y Componente (ms)",
        xaxis_title="Turno",
        yaxis_title="Tiempo Acumulado (ms)",
        template="plotly_white",
        height=400,
        margin={"l": 40, "r": 40, "t": 50, "b": 40},
    )
    return fig


def figura_evolucion_scores(
    retrievals: list[dict[str, Any]],
    umbral: float = 0.82,
    zona_gris: float = 0.03,
) -> go.Figure:
    """Evolución temporal del top1_score con banda de zona gris y umbral institucional."""
    fig = go.Figure()
    if not retrievals:
        fig.update_layout(title="Sin datos de recuperación semántica")
        return fig

    indices = list(range(1, len(retrievals) + 1))
    scores = [float(r.get("top1_score", 0)) for r in retrievals]
    decisiones = [r.get("decision", "abstencion") for r in retrievals]

    colores = [
        PALETA_DUOC["azul_primario"] if d == "respuesta" else PALETA_DUOC["rojo"]
        for d in decisiones
    ]

    # Banda de zona gris
    fig.add_hrect(
        y0=umbral - zona_gris,
        y1=umbral + zona_gris,
        fillcolor=PALETA_DUOC["amarillo"],
        opacity=0.25,
        line_width=0,
        annotation_text="Zona gris (±0.03)",
        annotation_position="top left",
    )

    # Línea umbral
    fig.add_hline(
        y=umbral,
        line_dash="dash",
        line_color=PALETA_DUOC["azul_oscuro"],
        annotation_text=f"Umbral {umbral}",
        annotation_position="bottom right",
    )

    fig.add_trace(
        go.Scatter(
            x=indices,
            y=scores,
            mode="lines+markers",
            name="Top-1 Score",
            line={"color": PALETA_DUOC["gris"], "width": 1},
            marker={"size": 8, "color": colores},
            text=[f"Consulta #{i}<br>Score: {s:.3f}<br>Decisión: {d}" for i, s, d in zip(indices, scores, decisiones)],
            hoverinfo="text",
        )
    )

    fig.update_layout(
        title="Evolución de Top-1 Score de Recuperación Semántica",
        xaxis_title="Evento de Retrieval",
        yaxis_title="Score de Similitud Coseno",
        yaxis={"range": [0.5, 1.0]},
        template="plotly_white",
        height=380,
        margin={"l": 40, "r": 40, "t": 50, "b": 40},
    )
    return fig


def figura_barrido_umbral(datos_barrido: list[dict[str, Any]]) -> go.Figure:
    """Curvas de abstención correcta y falsos rechazos ante barrido de umbral."""
    fig = go.Figure()
    if not datos_barrido:
        fig.update_layout(title="Sin datos de barrido de umbral")
        return fig

    umbrales = [d["umbral"] for d in datos_barrido]
    tasa_abs = [d["tasa_abstencion_correcta"] * 100 for d in datos_barrido]
    tasa_fp = [d["tasa_falsos_rechazos"] * 100 for d in datos_barrido]

    fig.add_trace(
        go.Scatter(
            x=umbrales,
            y=tasa_abs,
            mode="lines+markers",
            name="Abstención Correcta (%)",
            line={"color": PALETA_DUOC["verde"], "width": 2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=umbrales,
            y=tasa_fp,
            mode="lines+markers",
            name="Falsos Rechazos (%)",
            line={"color": PALETA_DUOC["rojo"], "width": 2},
        )
    )

    fig.add_vline(
        x=0.82,
        line_dash="dash",
        line_color=PALETA_DUOC["azul_primario"],
        annotation_text="Umbral actual 0.82",
    )

    fig.update_layout(
        title="Impacto del Umbral de Relevancia (Datos Crudos)",
        xaxis_title="Umbral de Relevancia Coseno",
        yaxis_title="Porcentaje (%)",
        template="plotly_white",
        height=380,
        margin={"l": 40, "r": 40, "t": 50, "b": 40},
    )
    return fig


def figura_uso_herramientas(turnos: list[dict[str, Any]]) -> go.Figure:
    """Gráfico de barras de las 7 herramientas oficiales (mostrando también las de 0 uso)."""
    fig = go.Figure()
    todas_herramientas = [
        "buscar_reglamentos",
        "consultar_fecha_actual",
        "consultar_feriados",
        "calcular_plazo",
        "redactar_borrador",
        "listar_borradores",
        "leer_borrador",
    ]

    conteo: Counter = Counter()
    for t in turnos:
        for h in t.get("herramientas") or []:
            conteo[h] += 1

    valores = [conteo[h] for h in todas_herramientas]

    fig.add_trace(
        go.Bar(
            y=todas_herramientas,
            x=valores,
            orientation="h",
            marker_color=PALETA_DUOC["azul_primario"],
            text=valores,
            textposition="auto",
        )
    )

    fig.update_layout(
        title="Frecuencia de Invocación por Herramienta",
        xaxis_title="Cantidad de Ejecuciones",
        yaxis_title="Herramienta",
        template="plotly_white",
        height=350,
        margin={"l": 40, "r": 40, "t": 50, "b": 40},
    )
    return fig


def figura_distribucion_errores(errores: list[dict[str, Any]]) -> go.Figure:
    """Distribución de errores por categoría."""
    fig = go.Figure()
    if not errores:
        fig.update_layout(title="Sin errores registrados")
        return fig

    conteo = Counter(e.get("categoria", "otro") for e in errores)
    labels = list(conteo.keys())
    values = list(conteo.values())

    fig.add_trace(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.45,
            marker_colors=[
                PALETA_DUOC["rojo"],
                PALETA_DUOC["amarillo"],
                PALETA_DUOC["azul_acento"],
                PALETA_DUOC["gris"],
            ],
        )
    )

    fig.update_layout(
        title="Distribución de Errores por Categoría",
        template="plotly_white",
        height=350,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
    )
    return fig


def figura_eventos_seguridad(eventos_seguridad: list[dict[str, Any]]) -> go.Figure:
    """Distribución de eventos de seguridad por control y acción."""
    fig = go.Figure()
    if not eventos_seguridad:
        fig.update_layout(title="Sin eventos de seguridad registrados")
        return fig

    controles = Counter(e.get("control") for e in eventos_seguridad)
    acciones = Counter(e.get("accion") for e in eventos_seguridad)

    fig.add_trace(
        go.Bar(
            name="Por Control",
            x=list(controles.keys()),
            y=list(controles.values()),
            marker_color=PALETA_DUOC["azul_acento"],
        )
    )
    fig.add_trace(
        go.Bar(
            name="Por Acción",
            x=list(acciones.keys()),
            y=list(acciones.values()),
            marker_color=PALETA_DUOC["amarillo"],
        )
    )

    fig.update_layout(
        barmode="group",
        title="Eventos de Seguridad (Controles y Acciones)",
        xaxis_title="Tipo / Acción",
        yaxis_title="Cantidad de Eventos",
        template="plotly_white",
        height=350,
        margin={"l": 40, "r": 40, "t": 50, "b": 40},
    )
    return fig


def figura_gantt_traza(etapas: list[dict[str, Any]]) -> go.Figure:
    """Diagrama de Gantt de etapas cronológicas para una traza específica."""
    fig = go.Figure()
    if not etapas:
        fig.update_layout(title="Sin etapas para esta traza")
        return fig

    etapas_ordenadas = sorted(etapas, key=lambda e: float(e.get("offset_ms", 0)))
    nombres = [f"{e.get('nombre')} ({e.get('componente')})" for e in etapas_ordenadas]
    inicios = [float(e.get("offset_ms", 0)) for e in etapas_ordenadas]
    duraciones = [max(1.0, float(e.get("duracion_ms", 0))) for e in etapas_ordenadas]

    colores = [
        PALETA_DUOC["verde"] if e.get("ok") else PALETA_DUOC["rojo"]
        for e in etapas_ordenadas
    ]

    fig.add_trace(
        go.Bar(
            x=duraciones,
            y=nombres,
            base=inicios,
            orientation="h",
            marker_color=colores,
            text=[f"{d:.1f} ms" for d in duraciones],
            textposition="auto",
        )
    )

    fig.update_layout(
        title="Cronograma de Ejecución de la Traza (Diagrama de Gantt)",
        xaxis_title="Tiempo desde inicio del turno (ms)",
        yaxis_title="Etapa / Componente",
        template="plotly_white",
        height=max(300, len(etapas) * 45),
        margin={"l": 160, "r": 40, "t": 50, "b": 40},
    )
    return fig


def figura_recursos_ram_cpu(recursos: list[dict[str, Any]]) -> go.Figure:
    """Evolución de memoria RAM (RSS MB) y porcentaje de CPU."""
    fig = go.Figure()
    if not recursos:
        fig.update_layout(title="Sin registros de recursos")
        return fig

    indices = list(range(1, len(recursos) + 1))
    rss_mb = [float(r.get("rss_mb", 0)) for r in recursos]
    cpu_proc = [float(r.get("cpu_proceso_pct", 0)) for r in recursos]
    momentos = [str(r.get("momento", "")) for r in recursos]

    fig.add_trace(
        go.Scatter(
            x=indices,
            y=rss_mb,
            name="RAM RSS (MB)",
            mode="lines+markers",
            line={"color": PALETA_DUOC["azul_primario"], "width": 2},
            text=momentos,
            hoverinfo="x+y+text",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=indices,
            y=cpu_proc,
            name="CPU Proceso (%)",
            mode="lines+markers",
            yaxis="y2",
            line={"color": PALETA_DUOC["amarillo"], "width": 2},
            text=momentos,
            hoverinfo="x+y+text",
        )
    )

    fig.update_layout(
        title="Uso de Memoria y CPU en el Tiempo",
        xaxis_title="Registro de Recursos",
        yaxis_title="Memoria RSS (MB)",
        yaxis2={
            "title": "CPU (%)",
            "overlaying": "y",
            "side": "right",
            "range": [0, 100],
        },
        template="plotly_white",
        height=380,
        margin={"l": 40, "r": 40, "t": 50, "b": 40},
    )
    return fig
