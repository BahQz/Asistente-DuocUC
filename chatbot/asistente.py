"""Consola interactiva del agente estudiantil de Duoc UC.

La interfaz web (``web.py``) es la vía recomendada, pero esta consola permite
probar el agente sin Streamlit y es útil para depurar la traza ReAct.

Ejecutar con:
    PYTHONPATH=. python chatbot/asistente.py

Comandos:
    /limpiar   vacía la memoria de la conversación
    /ayuda     muestra los comandos disponibles
    salir      termina y guarda la sesión

Autor: Benjamín Quiroz
"""

from chatbot.agente import AgenteDuocUC, ErrorAgente, ErrorConfiguracion
from chatbot.memoria import crear_memoria

ICONOS = {
    "buscar_reglamentos": "🔎",
    "consultar_fecha_actual": "📅",
    "consultar_feriados": "🎉",
    "calcular_plazo": "⏳",
    "redactar_borrador": "📝",
    "listar_borradores": "📂",
    "leer_borrador": "📄",
}


def _imprimir_traza(resultado) -> None:
    """Muestra las decisiones del agente en la consola."""
    if not resultado.eventos:
        return
    print("  ┌─ Traza del agente " + "─" * 40)
    for evento in resultado.eventos:
        if evento.get("tipo") == "plan":
            print(f"  │ 🧠 {evento.get('detalle', '').strip()}")
        elif evento.get("tipo") == "herramienta":
            icono = ICONOS.get(evento.get("nombre"), "🛠")
            argumentos = evento.get("argumentos") or {}
            resumen = ", ".join(f"{k}={v!r}" for k, v in argumentos.items())
            print(f"  │ {icono} {evento.get('nombre')}({resumen})")
            if evento.get("ok") is False:
                print("  │    ↳ sin resultados relevantes")
    print("  └" + "─" * 58)


def main() -> None:
    print("=" * 62)
    print("  Asistente Estudiantil Duoc UC — Agente ReAct")
    print("  LangChain + ChromaDB + memoria conversacional")
    print("=" * 62)
    print("Escribe 'salir' para terminar o '/ayuda' para ver los comandos.\n")

    try:
        agente = AgenteDuocUC(memoria=crear_memoria())
    except ErrorConfiguracion as exc:
        print(f"  ⚠️  {exc}")
        return

    while True:
        try:
            entrada = input("  Estudiante: ").strip()
        except (EOFError, KeyboardInterrupt):
            agente.memoria.guardar()
            print("\n  Sesión finalizada.")
            break

        if entrada.lower() in ("salir", "exit", "/salir"):
            agente.memoria.guardar()
            print("  Sesión finalizada.")
            break

        if not entrada:
            continue

        if entrada.lower() == "/limpiar":
            agente.limpiar_memoria()
            print("  Memoria de la conversación vaciada.\n")
            continue

        if entrada.lower() in ("/ayuda", "ayuda"):
            print(
                "  Comandos: /limpiar (vaciar memoria), /ayuda, salir.\n"
                "  Ejemplos: '¿cuál es la asistencia mínima?', "
                "'justifica mi inasistencia de ayer'.\n"
            )
            continue

        try:
            resultado = agente.responder(entrada)
            _imprimir_traza(resultado)
            print(f"\n  Duqui: {resultado.respuesta}")
            if resultado.fuentes:
                print("\n  📚 Fuentes:")
                for fuente in resultado.fuentes:
                    print(
                        f"     - {fuente['seccion']} — {fuente['titulo']} "
                        f"(relevancia {fuente['relevancia']:.2f})"
                    )
            if resultado.borradores:
                print("\n  📄 Borradores generados:")
                for borrador in resultado.borradores:
                    print(f"     - {borrador['archivo']}")
            print()
        except ErrorAgente as exc:
            print(f"\n  ⚠️  {exc}\n")
        except Exception as exc:  # noqa: BLE001 - la consola no debe caerse
            print(f"\n  ⚠️  Error inesperado: {exc}\n")


if __name__ == "__main__":
    main()
