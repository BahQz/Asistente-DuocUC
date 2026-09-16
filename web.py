"""Interfaz web (Streamlit) del asistente estudiantil de Duoc UC.

Reutiliza el mismo pipeline RAG + herramientas + memoria que la consola.

Ejecutar con:  streamlit run web.py

Autor: Benjamín Quiroz
"""

import streamlit as st

from chatbot.asistente import inicializar_cliente, responder_consulta
from chatbot.conocimiento import construir_buscador
from chatbot.memoria import MemoriaVentanaDeslizante

st.set_page_config(
    page_title="Asistente Estudiantil Duoc UC",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

ESTILOS = """
<style>
    #MainMenu, footer, [data-testid="stHeader"] {visibility: hidden;}

    .block-container {padding-top: 1.4rem; max-width: 880px;}

    .dq-encabezado {
        display: flex; align-items: center; gap: 18px;
        padding: 22px 26px; border-radius: 18px;
        background: linear-gradient(135deg, #00205b 0%, #0033a0 100%);
        color: #ffffff; margin-bottom: 6px;
        box-shadow: 0 8px 24px rgba(0, 51, 160, 0.20);
    }
    .dq-encabezado .dq-icono {font-size: 2.4rem; line-height: 1;}
    .dq-encabezado h1 {font-size: 1.45rem; margin: 0; color: #ffffff; font-weight: 700;}
    .dq-encabezado p {margin: 2px 0 0 0; font-size: 0.9rem; color: #cfe0ff;}

    .dq-etiqueta {
        display: inline-block; margin-top: 10px; padding: 4px 12px;
        border-radius: 999px; background: #fff3d6; color: #8a5a00;
        font-size: 0.75rem; font-weight: 600; letter-spacing: .3px;
    }

    [data-testid="stChatMessage"] {border-radius: 14px; padding: 4px 6px;}

    section[data-testid="stSidebar"] {
        background: #f2f6ff; border-right: 1px solid #dbe5fb;
    }

    .dq-pie {
        text-align: center; color: #7a869c; font-size: 0.75rem;
        margin-top: 24px;
    }
</style>
"""
st.markdown(ESTILOS, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def obtener_cliente():
    """Crea el cliente del modelo una vez por proceso."""
    return inicializar_cliente()


@st.cache_resource(show_spinner=False)
def obtener_buscador():
    """Carga e indexa la base de conocimiento una vez por proceso."""
    return construir_buscador()


def obtener_memoria() -> MemoriaVentanaDeslizante:
    """Devuelve la memoria de esta sesión del navegador."""
    if "memoria" not in st.session_state:
        st.session_state.memoria = MemoriaVentanaDeslizante(
            max_turnos=6, ruta=None
        )
    return st.session_state.memoria


if "mensajes" not in st.session_state:
    st.session_state.mensajes = []
if "pregunta_pendiente" not in st.session_state:
    st.session_state.pregunta_pendiente = None


SUGERENCIAS = [
    "¿Cuál es la asistencia mínima para aprobar?",
    "¿Cuándo puedo retirar una asignatura?",
    "¿Cómo postulo a la beca de excelencia?",
    "¿Hasta qué hora atiende la biblioteca?",
]


def mostrar_fuentes(resultado: dict) -> None:
    """Muestra los fragmentos recuperados y el uso de herramientas."""
    fuentes = resultado.get("fuentes") or []
    uso_fecha = resultado.get("uso_fecha")
    uso_feriados = resultado.get("uso_feriados")
    if not fuentes and not uso_fecha and not uso_feriados:
        return
    with st.expander("🔎 Fuentes consultadas"):
        for fragmento in fuentes:
            titulo = fragmento.splitlines()[0].strip() if fragmento else ""
            st.markdown(f"- **{titulo}**")
        if uso_fecha:
            st.markdown("- **Fecha actual (reloj del sistema)**")
        if uso_feriados:
            st.markdown("- **Feriados de Chile (date.nager.at)**")


def procesar_pregunta(pregunta: str) -> None:
    """Ejecuta el pipeline y dibuja el intercambio."""
    st.session_state.mensajes.append({"role": "user", "content": pregunta})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(pregunta)

    with st.chat_message("assistant", avatar="🎓"):
        with st.spinner("Revisando la información institucional…"):
            try:
                resultado = responder_consulta(
                    obtener_cliente(), obtener_buscador(), obtener_memoria(),
                    pregunta,
                )
            except Exception as exc:  # noqa: BLE001
                resultado = {
                    "respuesta": f"⚠️ Ocurrió un error al procesar tu consulta: {exc}",
                    "fuentes": [],
                    "uso_fecha": False,
                    "uso_feriados": False,
                }
        st.markdown(resultado["respuesta"])
        mostrar_fuentes(resultado)

    st.session_state.mensajes.append(
        {
            "role": "assistant",
            "content": resultado["respuesta"],
            "fuentes": resultado.get("fuentes", []),
            "uso_fecha": resultado.get("uso_fecha", False),
            "uso_feriados": resultado.get("uso_feriados", False),
        }
    )


# --------------------------------------------------------------- Encabezado
st.markdown(
    """
    <div class="dq-encabezado">
        <div class="dq-icono">🎓</div>
        <div>
            <h1>Asistente Estudiantil Duoc UC</h1>
            <p>Respuestas basadas en la información institucional</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<span class="dq-etiqueta">RAG + memoria conversacional · '
    "Solo responde con la base de conocimiento</span>",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ Barra lateral
with st.sidebar:
    st.markdown("### 🎓 Duoc UC")
    st.caption("Asistente Estudiantil")
    st.divider()
    st.markdown("**Modelo**\n\n`qwen/qwen3` · vía Groq")
    st.markdown("**Memoria**\n\nVentana deslizante · 6 turnos")
    st.markdown("**Fuentes**\n\nBase de conocimiento · Feriados de Chile")
    st.divider()
    if st.button("🧹 Limpiar conversación", use_container_width=True):
        st.session_state.mensajes = []
        st.session_state.memoria = MemoriaVentanaDeslizante(
            max_turnos=6, ruta=None
        )
        st.rerun()
    st.caption("Autor: Benjamín Quiroz")

# --------------------------------------------------------------- Chat
if not st.session_state.mensajes:
    st.markdown("#### ¿En qué te puedo ayudar hoy?")
    columnas = st.columns(2)
    for indice, sugerencia in enumerate(SUGERENCIAS):
        if columnas[indice % 2].button(
            sugerencia, use_container_width=True, key=f"sugerencia_{indice}"
        ):
            st.session_state.pregunta_pendiente = sugerencia
            st.rerun()

for mensaje in st.session_state.mensajes:
    avatar = "🧑" if mensaje["role"] == "user" else "🎓"
    with st.chat_message(mensaje["role"], avatar=avatar):
        st.markdown(mensaje["content"])
        if mensaje["role"] == "assistant":
            mostrar_fuentes(mensaje)

# --------------------------------------------------------------- Entrada
pregunta = st.chat_input("Escribe tu duda sobre matrícula, becas, ramos o pagos…")
if st.session_state.pregunta_pendiente:
    pregunta = st.session_state.pregunta_pendiente
    st.session_state.pregunta_pendiente = None

if pregunta:
    procesar_pregunta(pregunta)

st.markdown(
    '<div class="dq-pie">Proyecto académico · Benjamín Quiroz · '
    "Las respuestas se basan únicamente en la base de conocimiento.</div>",
    unsafe_allow_html=True,
)
