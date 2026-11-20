"""Página interactiva de Observabilidad, Métricas y Trazabilidad de Duqui (EP3).

Visualiza en tiempo real las métricas de precisión, latencia, consistencia,
recursos, anomalías, seguridad y trazas ReAct sin importar modelos pesados ni API key.
"""

import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from chatbot.ajustes import OBS_DIR, PROYECTO_RAIZ
from observabilidad.metricas import (
    barrido_umbral,
    calcular_percentiles,
    consistencia_por_grupo,
    detectar_anomalias,
    hit_at_k,
    matriz_abstencion,
    precision_at_1,
    tasa_bloqueo,
    tasa_exito,
)
from observabilidad.panel import (
    figura_barras_apiladas_etapas,
    figura_barrido_umbral,
    figura_desglose_latencia_etapas,
    figura_distribucion_errores,
    figura_eventos_seguridad,
    figura_evolucion_scores,
    figura_gantt_traza,
    figura_latencia_por_turno,
    figura_recursos_ram_cpu,
    figura_uso_herramientas,
)

st.set_page_config(
    page_title="Observabilidad · Duqui",
    page_icon="📊",
    layout="wide",
)

# Estilos institucionales
ESTILOS = """
<style>
    .dq-header-obs {
        background: linear-gradient(135deg, #00205b 0%, #0033a0 60%, #0b57d0 100%);
        color: #ffffff; padding: 20px 24px; border-radius: 14px; margin-bottom: 20px;
    }
    .dq-header-obs h1 {margin: 0; font-size: 1.6rem; color: #ffffff;}
    .dq-header-obs p {margin: 4px 0 0 0; font-size: 0.9rem; color: #d7e5ff;}
    .stMetric {background: #f8faff; border: 1px solid #e2eafc; border-radius: 10px; padding: 12px 14px;}
</style>
"""
st.markdown(ESTILOS, unsafe_allow_html=True)


def parsear_lineas_jsonl(lineas: list[str]) -> tuple[list[dict[str, Any]], int]:
    eventos: list[dict[str, Any]] = []
    corruptas = 0
    for l in lineas:
        l = l.strip()
        if not l:
            continue
        try:
            eventos.append(json.loads(l))
        except Exception:
            corruptas += 1
    return eventos, corruptas


@st.cache_data
def cargar_eventos_desde_disco(ruta_str: str, tamano: int, mtime: float) -> tuple[list[dict[str, Any]], int]:
    ruta = Path(ruta_str)
    if not ruta.exists():
        return [], 0
    try:
        contenido = ruta.read_text(encoding="utf-8")
        return parsear_lineas_jsonl(contenido.splitlines())
    except Exception:
        return [], 0


# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown("### 📊 Observabilidad")
    st.caption("Panel de Control · EP3 · 007D_OLS")
    try:
        st.page_link("web.py", label="🎓 Chat Duqui", icon="💬")
        st.page_link("pages/1_Observabilidad.py", label="📊 Observabilidad", icon="📊")
    except Exception:
        pass
    st.divider()

    st.markdown("**Fuente de Datos**")
    fuente = st.radio(
        "Seleccionar origen:",
        ["Logs en vivo", "Corrida de referencia", "Subir archivo .jsonl"],
        label_visibility="collapsed",
    )

    archivo_subido = None
    ruta_archivo: Path | None = None
    if fuente == "Logs en vivo":
        ruta_archivo = Path(OBS_DIR) / "eventos.jsonl"
    elif fuente == "Corrida de referencia":
        ruta_archivo = PROYECTO_RAIZ / "docs" / "evidencia" / "eventos_referencia.jsonl"
    else:
        archivo_subido = st.file_uploader("Subir log JSONL", type=["jsonl", "json"])

    if st.button("🔄 Recargar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown("**Filtros Globales**")
    excluir_frios = st.toggle("Excluir turnos fríos", value=False)


# Cargar datos según fuente
eventos_crudos: list[dict[str, Any]] = []
lineas_corruptas = 0

if archivo_subido is not None:
    contenido = archivo_subido.getvalue().decode("utf-8", errors="ignore")
    eventos_crudos, lineas_corruptas = parsear_lineas_jsonl(contenido.splitlines())
elif ruta_archivo is not None and ruta_archivo.exists():
    stats = ruta_archivo.stat()
    eventos_crudos, lineas_corruptas = cargar_eventos_desde_disco(
        str(ruta_archivo), stats.st_size, stats.st_mtime
    )

# Encabezado
st.markdown(
    """
    <div class="dq-header-obs">
        <h1>📊 Observabilidad y Trazabilidad · Duqui</h1>
        <p>Evaluación Parcial N.º 3 · Código Asignatura: 007D_OLS · Autor: Benjamín Quiroz</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if lineas_corruptas > 0:
    st.warning(f"Se omitieron {lineas_corruptas} líneas con formato JSON inválido.")

# ESTADO VACÍO
if not eventos_crudos:
    st.info(
        "ℹ️ **No se encontraron registros de eventos para mostrar.**\n\n"
        "Puedes generar datos rápidamente de las siguientes formas:\n"
        "1. Realiza consultas en el [Chat Duqui](web.py) para registrar turnos interactivos.\n"
        "2. Ejecuta el benchmark de precisión en consola: `python -m benchmark.ejecutar --perfil retrieval`\n"
        "3. Ejecuta una simulación: `python -m benchmark.ejecutar --perfil minimo --dry-run`\n"
        "4. Si ya exportaste una corrida, selecciona **Corrida de referencia** en la barra lateral."
    )
    st.stop()

# Extracción estructurada por tipo
turnos_todos = [e["datos"] for e in eventos_crudos if e.get("tipo") == "turno"]
for t, e in zip(turnos_todos, [e for e in eventos_crudos if e.get("tipo") == "turno"]):
    t["trace_id"] = e.get("trace_id")
    t["origen"] = e.get("origen")
    t["run_id"] = e.get("run_id")
    t["ts"] = e.get("ts")

etapas_todas = [e["datos"] for e in eventos_crudos if e.get("tipo") == "etapa"]
for et, e in zip(etapas_todas, [e for e in eventos_crudos if e.get("tipo") == "etapa"]):
    et["trace_id"] = e.get("trace_id")

retrievals_todos = [e["datos"] for e in eventos_crudos if e.get("tipo") == "retrieval"]
errores_todos = [e["datos"] for e in eventos_crudos if e.get("tipo") == "error"]
seguridad_todos = [e["datos"] for e in eventos_crudos if e.get("tipo") == "seguridad"]
recursos_todos = [e["datos"] for e in eventos_crudos if e.get("tipo") == "recursos"]
bench_casos = [e["datos"] for e in eventos_crudos if e.get("tipo") == "benchmark_caso"]

# Filtros adicionales en sidebar
origenes_disponibles = sorted(list({t.get("origen") for t in turnos_todos if t.get("origen")}))
with st.sidebar:
    filtro_origen = st.selectbox("Origen de ejecución:", ["Todos"] + origenes_disponibles)
    filtro_resultado = st.selectbox("Resultado del turno:", ["Todos", "ok", "error", "bloqueado_entrada", "bloqueado_salida"])

# Aplicar filtros a turnos
turnos = turnos_todos
if filtro_origen != "Todos":
    turnos = [t for t in turnos if t.get("origen") == filtro_origen]
if filtro_resultado != "Todos":
    turnos = [t for t in turnos if t.get("resultado") == filtro_resultado]
if excluir_frios:
    turnos = [t for t in turnos if not t.get("turno_frio")]

# Mapear etapas por trace_id
etapas_por_turno: dict[str, list[dict[str, Any]]] = {}
for et in etapas_todas:
    tid = et.get("trace_id")
    if tid:
        etapas_por_turno.setdefault(tid, []).append(et)

# 7 PESTAÑAS DEL DASHBOARD
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📈 Resumen",
    "🎯 Precisión y Consistencia",
    "⚡ Latencia y Recursos",
    "🛠️ Herramientas y Errores",
    "🛡️ Seguridad y Privacidad",
    "⚠️ Detección de Anomalías",
    "🔍 Explorador de Trazas",
])

# 1. PESTAÑA: RESUMEN
with tab1:
    st.subheader("Indicadores Clave de Desempeño (KPIs)")
    latencias = [float(t.get("latencia_total_ms", 0)) for t in turnos]
    stats_lat = calcular_percentiles(latencias)

    tokens = [int(t.get("tokens_total", 0)) for t in turnos]
    tokens_totales = sum(tokens)
    stats_tok = calcular_percentiles(tokens)

    n_turnos = len(turnos)
    t_exito = tasa_exito(turnos) * 100
    t_bloq = tasa_bloqueo(turnos) * 100

    abstenciones = [t for t in turnos if t.get("abstencion") is True]
    derivaciones = [t for t in turnos if t.get("derivacion") is True]
    zonas_grises = [t for t in turnos if t.get("zona_gris") is True]

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Turnos Evaluados", n_turnos)
    col2.metric("Tasa de Éxito", f"{t_exito:.1f}%")
    col3.metric("Latencia P50", f"{stats_lat['p50']:.0f} ms")
    col4.metric("Latencia P95", f"{stats_lat['p95']:.0f} ms")
    col5.metric("Tokens Totales", f"{tokens_totales:,}")

    col6, col7, col8, col9, col10 = st.columns(5)
    col6.metric("Tokens / Turno (Media)", f"{stats_tok['media']:.0f}")
    col7.metric("Tasa Bloqueo Seg.", f"{t_bloq:.1f}%")
    col8.metric("Abstención Retrieval", f"{len(abstenciones)}")
    col9.metric("Derivación Oficial", f"{len(derivaciones)}")
    col10.metric("En Zona Gris (±0.03)", f"{len(zonas_grises)}")

    st.plotly_chart(
        figura_latencia_por_turno(turnos, p50=stats_lat["p50"], p95=stats_lat["p95"]),
        use_container_width=True,
    )


# 2. PESTAÑA: PRECISIÓN Y CONSISTENCIA
with tab2:
    st.subheader("Métricas de Recuperación Semántica y Consistencia")

    if bench_casos:
        prec1 = precision_at_1(bench_casos) * 100
        hitk = hit_at_k(bench_casos) * 100
        mat_abs = matriz_abstencion(bench_casos)

        bcol1, bcol2, bcol3, bcol4 = st.columns(4)
        bcol1.metric("Precision@1", f"{prec1:.1f}%")
        bcol2.metric("Hit@k", f"{hitk:.1f}%")
        bcol3.metric("Abstención Correcta", f"{mat_abs['tasa_abstencion_correcta'] * 100:.1f}%")
        bcol4.metric("Falsos Rechazos", f"{mat_abs['tasa_falsos_rechazos'] * 100:.1f}%")

        # Consistencia por grupo
        cons_resumen = consistencia_por_grupo(bench_casos)
        if cons_resumen:
            st.markdown("##### Consistencia por Grupo Semántico")
            df_cons = pd.DataFrame.from_dict(cons_resumen, orient="index")
            st.dataframe(df_cons, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(figura_evolucion_scores(retrievals_todos), use_container_width=True)
    with c2:
        # Simular barrido con candidatos disponibles
        candidatos_para_barrido = [
            {"debe_abstenerse": c.get("esperado", {}).get("debe_abstenerse", False), "top1_score": c.get("observado", {}).get("top1_score", 0.0)}
            for c in bench_casos
        ]
        if candidatos_para_barrido:
            barrido_res = barrido_umbral(candidatos_para_barrido)
            st.plotly_chart(figura_barrido_umbral(barrido_res), use_container_width=True)
        else:
            st.info("Ejecuta el benchmark para visualizar la curva de barrido de umbral.")


# 3. PESTAÑA: LATENCIA Y RECURSOS
with tab3:
    st.subheader("Desglose de Latencia y Consumo de Hardware")
    lcol1, lcol2 = st.columns(2)
    with lcol1:
        st.plotly_chart(figura_desglose_latencia_etapas(etapas_todas), use_container_width=True)
    with lcol2:
        st.plotly_chart(figura_barras_apiladas_etapas(turnos, etapas_por_turno), use_container_width=True)

    if recursos_todos:
        st.plotly_chart(figura_recursos_ram_cpu(recursos_todos), use_container_width=True)


# 4. PESTAÑA: HERRAMIENTAS Y ERRORES
with tab4:
    st.subheader("Uso de Herramientas y Gestión de Errores")
    hcol1, hcol2 = st.columns(2)
    with hcol1:
        st.plotly_chart(figura_uso_herramientas(turnos), use_container_width=True)
    with hcol2:
        st.plotly_chart(figura_distribucion_errores(errores_todos), use_container_width=True)

    if errores_todos:
        st.markdown("##### Registro Histórico de Errores")
        df_err = pd.DataFrame(errores_todos)
        st.dataframe(df_err, use_container_width=True)


# 5. PESTAÑA: SEGURIDAD Y PRIVACIDAD
with tab5:
    st.subheader("Protocolos de Seguridad, Ética y Privacidad (IE8)")
    scol1, scol2 = st.columns(2)
    with scol1:
        st.plotly_chart(figura_eventos_seguridad(seguridad_todos), use_container_width=True)
    with scol2:
        st.markdown("##### Verificación de Defensa en Profundidad")
        fuga_llm = sum(1 for s in seguridad_todos if s.get("control") == "pii_hacia_proveedor")
        st.metric("PII Cruda Enviada al Proveedor LLM", fuga_llm, help="Debe ser estrictamente 0 en producción")

        st.markdown("##### Enmascaramiento de Datos Personales")
        pii_eventos = [s for s in seguridad_todos if s.get("control") == "pii"]
        conteo_pii: Counter = Counter()
        for p in pii_eventos:
            for k, v in (p.get("detalle") or {}).items():
                conteo_pii[k] += int(v)
        if conteo_pii:
            df_pii = pd.DataFrame.from_dict(dict(conteo_pii), orient="index", columns=["Ocurrencias"])
            st.dataframe(df_pii, use_container_width=True)
        else:
            st.caption("No se han registrado datos personales sensibles en las consultas cargadas.")


# 6. PESTAÑA: ANOMALÍAS
with tab6:
    st.subheader("Patrones y Anomalías en Registros (IE6)")
    st.caption("Filas detectadas mediante reglas deterministas nombradas (sin texto interpretativo generado por IA):")
    anomalias = detectar_anomalias(turnos)

    if anomalias:
        df_anom = pd.DataFrame(anomalias)
        st.dataframe(df_anom, use_container_width=True)

        buffer = io.StringIO()
        df_anom.to_csv(buffer, index=False)
        st.download_button(
            "⬇️ Descargar anomalías (.csv)",
            data=buffer.getvalue(),
            file_name="anomalias_detectadas.csv",
            mime="text/csv",
        )
    else:
        st.success("✅ No se detectaron anomalías con los umbrales estadísticos actuales.")


# 7. PESTAÑA: EXPLORADOR DE TRAZAS
with tab7:
    st.subheader("Trazabilidad Detallada de Ejecución ReAct (IE3)")
    tids_disponibles = [t.get("trace_id") for t in turnos if t.get("trace_id")]

    if tids_disponibles:
        trace_sel = st.selectbox("Seleccionar ID de Traza:", tids_disponibles)
        etapas_traza = etapas_por_turno.get(trace_sel, [])

        if etapas_traza:
            st.plotly_chart(figura_gantt_traza(etapas_traza), use_container_width=True)

            st.markdown("##### Eventos Cronológicos de la Traza")
            df_traza = pd.DataFrame(etapas_traza)
            st.dataframe(df_traza, use_container_width=True)

            with st.expander("📄 Ver JSON crudo de la traza"):
                eventos_de_traza = [e for e in eventos_crudos if e.get("trace_id") == trace_sel]
                st.code(json.dumps(eventos_de_traza, ensure_ascii=False, indent=2), language="json")
    else:
        st.info("No hay trazas registradas en los turnos filtrados.")
