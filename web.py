import json
import uuid
from pathlib import Path

import streamlit as st

from chatbot.agente import (
    AgenteDuocUC,
    ErrorAgente,
    ErrorConfiguracion,
    construir_agente,
)
from chatbot.ajustes import (
    EMBEDDINGS_MODEL,
    FRAGMENTOS_POR_DEFECTO,
    LLM_API_KEY,
    LLM_MODEL,
    MEMORIA_MAX_TURNOS,
)
from chatbot.conocimiento import informacion_indice
from chatbot.memoria import MemoriaConversacional

st.set_page_config(
    page_title="Duqui · Agente Estudiantil Duoc UC",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

ESTILOS = """
<style>
    #MainMenu, footer, [data-testid="stHeader"] {visibility: hidden;}

    .block-container {padding-top: 1.3rem; max-width: 900px;}

    .dq-encabezado {
        display: flex; align-items: center; gap: 18px;
        padding: 22px 26px; border-radius: 18px;
        background: linear-gradient(135deg, #00205b 0%, #0033a0 55%, #0b57d0 100%);
        color: #ffffff; margin-bottom: 8px;
        box-shadow: 0 8px 24px rgba(0, 51, 160, 0.22);
    }
    .dq-encabezado .dq-icono {font-size: 2.5rem; line-height: 1;}
    .dq-encabezado h1 {font-size: 1.5rem; margin: 0; color: #ffffff; font-weight: 700;}
    .dq-encabezado p {margin: 3px 0 0 0; font-size: 0.9rem; color: #d7e5ff;}

    .dq-chips {display: flex; flex-wrap: wrap; gap: 7px; margin: 2px 0 14px 0;}
    .dq-chip {
        display: inline-block; padding: 4px 11px; border-radius: 999px;
        background: #eaf1ff; color: #0033a0; border: 1px solid #cfe0ff;
        font-size: 0.72rem; font-weight: 600; letter-spacing: .2px;
    }
    .dq-chip.dq-demo {background: #fff3d6; color: #8a5a00; border-color: #f5d68a;}

    [data-testid="stChatMessage"] {border-radius: 14px; padding: 4px 6px;}

    section[data-testid="stSidebar"] {
        background: #f2f6ff; border-right: 1px solid #dbe5fb;
    }

    .dq-paso {
        border-left: 3px solid #0b57d0; padding: 2px 0 2px 12px;
        margin: 10px 0; font-size: 0.88rem;
    }
    .dq-paso .dq-titulo {font-weight: 700; color: #00205b;}
    .dq-paso .dq-detalle {color: #3c4a5f;}

    .dq-fuente {
        display: flex; justify-content: space-between; gap: 12px;
        padding: 7px 10px; margin: 4px 0; border-radius: 8px;
        background: #f7f9ff; border: 1px solid #e3ebfb; font-size: 0.82rem;
    }
    .dq-fuente .dq-seccion {font-weight: 600; color: #00205b;}
    .dq-fuente .dq-score {color: #0b57d0; font-variant-numeric: tabular-nums;}

    .dq-pie {
        text-align: center; color: #7a869c; font-size: 0.75rem;
        margin-top: 24px;
    }
</style>
"""
st.markdown(ESTILOS, unsafe_allow_html=True)

ICONOS_HERRAMIENTA = {
    "buscar_reglamentos": "🔎",
    "consultar_fecha_actual": "📅",
    "consultar_feriados": "🎉",
    "calcular_plazo": "⏳",
    "redactar_borrador": "📝",
    "listar_borradores": "📂",
    "leer_borrador": "📄",
}

SUGERENCIAS = [
    "¿Cuál es la asistencia mínima para aprobar?",
    "asta cuando puedo retirar un ramo",
    "Falté a una evaluación ayer por una gripe. ¿Cuál es el plazo para justificar y puedes redactar el borrador?",
    "¿Qué feriados quedan este año?",
]


@st.cache_resource(show_spinner=False)
def cargar_agente_lc():
    return construir_agente()


@st.cache_resource(show_spinner=False)
def cargar_indice():
    return informacion_indice()


def obtener_memoria() -> MemoriaConversacional:
    if "memoria" not in st.session_state:
        st.session_state.memoria = MemoriaConversacional(
            max_turnos=MEMORIA_MAX_TURNOS, ruta=None
        )
    return st.session_state.memoria


def obtener_agente() -> AgenteDuocUC:
    with st.spinner("Cargando el agente…"):
        agente_lc = cargar_agente_lc()
    return AgenteDuocUC(
        agente=agente_lc,
        memoria=obtener_memoria(),
        session_id=st.session_state.get("session_id"),
        origen="app",
    )


def _cargar_indice_silencioso() -> dict:
    try:
        with st.spinner("Preparando el índice vectorial…"):
            return cargar_indice()
    except Exception as exc:  # noqa: BLE001
        return {"fragmentos": 0, "modelo": EMBEDDINGS_MODEL, "error": str(exc)}


def _resumen_resultado(evento: dict) -> str:
    resultado = (evento.get("resultado") or "").strip()
    if evento.get("nombre") == "redactar_borrador":
        primera = next(
            (linea for linea in resultado.splitlines() if linea.startswith("Archivo:")),
            "Borrador generado.",
        )
        return primera
    if not resultado:
        return "Sin salida registrada."
    if len(resultado) > 600:
        return resultado[:600].rsplit(" ", 1)[0] + " […]"
    return resultado


def mostrar_traza(mensaje: dict) -> None:
    eventos = mensaje.get("eventos") or []
    if not eventos:
        return
    herramientas = sum(1 for evento in eventos if evento.get("tipo") == "herramienta")
    with st.expander(
        f"🧠 Traza ReAct · {herramientas} herramienta(s) · plan y observaciones",
        expanded=False,
    ):
        metricas = mensaje.get("metricas") or {}
        tid = mensaje.get("trace_id") or ""
        if metricas or tid:
            lat = metricas.get("latencia_total_ms", 0)
            tok = metricas.get("tokens_total", 0)
            tid_abrev = tid[:8] if tid else "n/a"
            st.caption(f"⏱️ {lat:.0f} ms · 🪙 {tok} tokens · 🆔 traza `{tid_abrev}`")
            try:
                st.page_link("pages/1_Observabilidad.py", label="Ver telemetría en Dashboard", icon="📊")
            except Exception:
                pass

        for evento in eventos:
            if evento.get("tipo") == "plan":
                st.markdown(
                    '<div class="dq-paso"><span class="dq-titulo">Plan</span><br>'
                    f'<span class="dq-detalle">{evento.get("detalle", "")}</span></div>',
                    unsafe_allow_html=True,
                )
                continue

            icono = ICONOS_HERRAMIENTA.get(evento.get("nombre"), "🛠")
            estado = "✅" if evento.get("ok") else "⚠️"
            st.markdown(
                f'<div class="dq-paso"><span class="dq-titulo">{icono} '
                f'{evento.get("nombre", "herramienta")}</span> {estado}</div>',
                unsafe_allow_html=True,
            )
            argumentos = evento.get("argumentos") or {}
            if argumentos:
                st.code(
                    json.dumps(argumentos, ensure_ascii=False, indent=2),
                    language="json",
                )
            st.caption(_resumen_resultado(evento))


def mostrar_fuentes(mensaje: dict) -> None:
    fuentes = mensaje.get("fuentes") or []
    if not fuentes:
        return
    with st.expander(f"📚 Fuentes consultadas · {len(fuentes)} fragmento(s)"):
        for fuente in fuentes:
            st.markdown(
                '<div class="dq-fuente">'
                f'<span class="dq-seccion">{fuente.get("seccion", "")} — '
                f'{fuente.get("titulo", "")}</span>'
                f'<span class="dq-score">{float(fuente.get("relevancia", 0)):.3f}</span>'
                "</div>",
                unsafe_allow_html=True,
            )
        st.caption(
            "Relevancia coseno (0 a 1) calculada por el modelo de embeddings "
            f"`{EMBEDDINGS_MODEL}`. Las fuentes se recuperan de ChromaDB."
        )


def mostrar_borradores(mensaje: dict, posicion: int) -> None:
    borradores = mensaje.get("borradores") or []
    for numero, borrador in enumerate(borradores):
        with st.expander(
            f"📄 Borrador generado · {borrador.get('titulo', 'Documento')}",
            expanded=True,
        ):
            st.caption(
                "Revísalo, completa los campos entre corchetes y fírmalo antes "
                "de presentarlo. No reemplaza la orientación de la Dirección de "
                "Escuela."
            )
            st.markdown(borrador.get("contenido", ""))
            nombre_archivo = Path(borrador.get("archivo", "borrador.md")).name
            st.download_button(
                "⬇️ Descargar borrador (.md)",
                data=borrador.get("contenido", ""),
                file_name=nombre_archivo,
                mime="text/markdown",
                key=f"descarga_{posicion}_{numero}_{borrador.get('id', 'doc')}",
                use_container_width=True,
            )


def procesar_pregunta(pregunta: str) -> None:
    st.session_state.mensajes.append({"role": "user", "content": pregunta})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(pregunta)

    with st.chat_message("assistant", avatar="🎓"):
        try:
            with st.spinner("Duqui está razonando y consultando las fuentes…"):
                resultado = obtener_agente().responder(pregunta).como_dict()
        except ErrorConfiguracion as exc:
            resultado = {"respuesta": f"⚙️ {exc}", "fuentes": [], "eventos": []}
        except ErrorAgente as exc:
            resultado = {"respuesta": f"⚠️ {exc}", "fuentes": [], "eventos": []}
        except Exception as exc:  # noqa: BLE001
            resultado = {
                "respuesta": (
                    "⚠️ Ocurrió un error inesperado al procesar tu consulta. "
                    f"Detalle: `{exc}`"
                ),
                "fuentes": [],
                "eventos": [],
            }

        st.markdown(resultado["respuesta"])
        avisos = resultado.get("avisos_seguridad") or []
        for av in avisos:
            if av.get("control") == "pii":
                st.caption("🔒 Oculté datos personales antes de procesar tu consulta.")
        mostrar_fuentes(resultado)
        mostrar_traza(resultado)
        mostrar_borradores(resultado, len(st.session_state.mensajes))

    st.session_state.mensajes.append(
        {
            "role": "assistant",
            "content": resultado["respuesta"],
            "fuentes": resultado.get("fuentes", []),
            "eventos": resultado.get("eventos", []),
            "borradores": resultado.get("borradores", []),
            "herramientas_usadas": resultado.get("herramientas_usadas", []),
            "trace_id": resultado.get("trace_id"),
            "metricas": resultado.get("metricas", {}),
            "avisos_seguridad": resultado.get("avisos_seguridad", []),
        }
    )


st.markdown(
    """
    <div class="dq-encabezado">
        <div class="dq-icono">🎓</div>
        <div>
            <h1>Duqui · Agente Estudiantil Duoc UC</h1>
            <p>RAG semántico + herramientas + memoria + razonamiento ReAct</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="dq-chips">'
    '<span class="dq-chip">LangChain / LangGraph</span>'
    '<span class="dq-chip">ChromaDB · embeddings</span>'
    '<span class="dq-chip">Memoria conversacional</span>'
    '<span class="dq-chip">7 herramientas</span>'
    '<span class="dq-chip dq-demo">EP3 · 007D_OLS</span>'
    "</div>",
    unsafe_allow_html=True,
)

if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex
if "mensajes" not in st.session_state:
    st.session_state.mensajes = []
if "pregunta_pendiente" not in st.session_state:
    st.session_state.pregunta_pendiente = None

with st.sidebar:
    st.markdown("### 🎓 Duqui")
    st.caption("Agente estudiantil · Duoc UC")
    try:
        st.page_link("web.py", label="🎓 Chat Duqui", icon="💬")
        st.page_link("pages/1_Observabilidad.py", label="📊 Observabilidad", icon="📊")
    except Exception:
        pass
    st.divider()

    st.markdown("**Modelo**")
    st.markdown(f"`{LLM_MODEL}`")
    st.markdown("**Embeddings**")
    st.markdown(f"`{EMBEDDINGS_MODEL}`")
    st.markdown("**Memoria de corto plazo**")
    st.caption(f"Ventana deslizante · {MEMORIA_MAX_TURNOS} turnos")
    st.markdown("**Recuperación**")
    st.caption(
        f"ChromaDB · top {FRAGMENTOS_POR_DEFECTO} · umbral coseno configurable"
    )

    st.divider()
    st.markdown("**Herramientas del agente**")
    st.caption("🔎 buscar_reglamentos · consulta semántica")
    st.caption("📅 consultar_fecha_actual · fecha de hoy")
    st.caption("🎉 consultar_feriados · date.nager.at")
    st.caption("⏳ calcular_plazo · días hábiles")
    st.caption("📝 redactar_borrador · escritura")
    st.caption("📂 listar_borradores · memoria de artefactos")
    st.caption("📄 leer_borrador · recuperar documento")

    st.divider()
    if st.button("🧹 Limpiar conversación", use_container_width=True):
        st.session_state.mensajes = []
        st.session_state.memoria = MemoriaConversacional(
            max_turnos=MEMORIA_MAX_TURNOS, ruta=None
        )
        st.rerun()

    with st.expander("⚙️ Estado del índice"):
        indice = _cargar_indice_silencioso()
        if indice.get("error"):
            st.error(indice["error"])
        else:
            st.metric("Fragmentos indexados", indice.get("fragmentos", 0))
            st.caption(f"Modelo: `{indice.get('modelo', EMBEDDINGS_MODEL)}`")
            st.caption("Directorio: `.chroma/` (persistente)")
            st.caption("Índice semántico listo para consultar.")

    st.caption("Autor: Benjamín Quiroz · 007D_OLS")


if not LLM_API_KEY:
    st.error(
        "Falta configurar la API key del modelo. Crea un archivo `.env` a partir "
        "de `.env.example` y agrega tu clave de Groq."
    )
    st.code(
        "LLM_API_KEY=tu-api-key-de-groq\n"
        "LLM_BASE_URL=https://api.groq.com/openai/v1\n"
        "LLM_MODEL=openai/gpt-oss-120b",
        language="bash",
    )
    st.stop()

if not st.session_state.mensajes:
    st.markdown("#### ¿En qué te puedo ayudar hoy?")
    st.caption(
        "Puedo buscar en los reglamentos, calcular plazos, consultar feriados y "
        "redactar borradores. También entiendo preguntas con errores de escritura."
    )
    columnas = st.columns(2)
    for posicion, sugerencia in enumerate(SUGERENCIAS):
        if columnas[posicion % 2].button(
            sugerencia,
            use_container_width=True,
            key=f"sugerencia_{posicion}",
        ):
            st.session_state.pregunta_pendiente = sugerencia
            st.rerun()

for posicion, mensaje in enumerate(st.session_state.mensajes):
    avatar = "🧑" if mensaje["role"] == "user" else "🎓"
    with st.chat_message(mensaje["role"], avatar=avatar):
        st.markdown(mensaje["content"])
        if mensaje["role"] == "assistant":
            mostrar_fuentes(mensaje)
            mostrar_traza(mensaje)
            mostrar_borradores(mensaje, posicion)

pregunta = st.chat_input(
    "Escribe tu duda sobre matrícula, becas, ramos, pagos o trámites…"
)
if st.session_state.pregunta_pendiente:
    pregunta = st.session_state.pregunta_pendiente
    st.session_state.pregunta_pendiente = None

if pregunta:
    procesar_pregunta(pregunta)

st.markdown(
    '<div class="dq-pie">Proyecto académico · Benjamín Quiroz · '
    "Las respuestas institucionales se basan en la base de conocimiento y se "
    "citan con su fuente.</div>",
    unsafe_allow_html=True,
)
