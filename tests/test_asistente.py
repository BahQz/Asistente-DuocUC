
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from chatbot.agente import AgenteDuocUC
from chatbot.conocimiento import (
    buscar_semantico,
    cargar_fragmentos,
    construir_buscador,
)
from chatbot.documentos import generar_borrador, leer_borrador, listar_borradores
from chatbot.herramientas import (
    HERRAMIENTAS,
    buscar_en_base_conocimiento,
    calcular_plazo,
    consultar_fecha_actual,
    consultar_feriados,
)
from chatbot.memoria import MemoriaConversacional


class TestFragmentacion(unittest.TestCase):

    def test_fragmentos_con_metadatos(self):
        fragmentos = cargar_fragmentos()
        self.assertGreaterEqual(len(fragmentos), 30)
        identificadores = [f.metadata["id"] for f in fragmentos]
        self.assertEqual(len(identificadores), len(set(identificadores)))
        for fragmento in fragmentos:
            self.assertTrue(fragmento.metadata["seccion"])
            self.assertTrue(fragmento.metadata["titulo"])
            self.assertIn(fragmento.metadata["seccion"], fragmento.page_content)


class TestRecuperacionSemantica(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            from chatbot.conocimiento import construir_indice

            construir_indice()
        except Exception as exc:  # pragma: no cover - depende del entorno
            raise unittest.SkipTest(f"No se pudo preparar el índice: {exc}")

    def test_errata_encuentra_retiro(self):
        fragmentos = buscar_semantico("asta cuando puedo retirar un ramo")
        unido = "\n".join(f.contenido for f in fragmentos)
        self.assertIn("semana 8", unido)
        self.assertIn("Sección 2", unido)

    def test_errata_encuentra_asistencia(self):
        fragmentos = buscar_semantico("cual es la asistencia minima para aprovar")
        unido = "\n".join(f.contenido for f in fragmentos)
        self.assertIn("75%", unido)

    def test_tema_desconocido_no_devuelve_nada(self):
        self.assertEqual(buscar_semantico("tutorias de surf en la playa"), [])

    def test_fuente_con_relevancia(self):
        fragmentos = buscar_semantico("horario de la biblioteca")
        self.assertTrue(fragmentos)
        self.assertGreaterEqual(fragmentos[0].relevancia, 0.82)
        self.assertIn("biblioteca", fragmentos[0].contenido.lower())

    def test_fachada_compatible(self):
        buscador = construir_buscador()
        resultados = buscador("horario de la biblioteca")
        self.assertTrue(resultados)
        self.assertIsInstance(resultados[0], str)

    def test_tool_de_busqueda(self):
        herramienta = next(t for t in HERRAMIENTAS if t.name == "buscar_reglamentos")
        salida = herramienta.invoke({"consulta": "asta cuando puedo retirar un ramo"})
        self.assertIn("Fuente 1", salida)
        self.assertIn("semana 8", salida)


class TestHerramientas(unittest.TestCase):

    def test_fecha_actual_incluye_anio(self):
        resultado = consultar_fecha_actual()
        self.assertIn(str(date.today().year), resultado)
        self.assertIn("Hoy es", resultado)

    @patch("chatbot.herramientas._feriados_api")
    def test_feriados_formateados(self, mock_feriados):
        mock_feriados.return_value = (
            [
                {"date": "2026-01-01", "localName": "Año Nuevo"},
                {"date": "2026-05-01", "localName": "Día del Trabajo"},
            ],
            "",
        )
        resultado = consultar_feriados(2026)
        self.assertIn("Año Nuevo", resultado)
        self.assertIn("2026-05-01", resultado)

    @patch("chatbot.herramientas._feriados_api")
    def test_feriados_maneja_error(self, mock_feriados):
        mock_feriados.return_value = ([], "timeout")
        resultado = consultar_feriados(2026)
        self.assertIn("timeout", resultado.lower())

    @patch("chatbot.herramientas._feriados_api", return_value=([], ""))
    def test_calculo_de_plazo_sin_feriados(self, _mock):
        resultado = calcular_plazo("2026-10-21", 3, "justificar inasistencia")
        self.assertIn("2026-10-26", resultado)
        self.assertIn("3 día(s) hábil(es)", resultado)

    @patch("chatbot.herramientas._feriados_api")
    def test_calculo_de_plazo_excluye_feriado(self, mock_feriados):
        mock_feriados.return_value = (
            [{"date": "2026-10-26", "localName": "Feriado de prueba"}],
            "",
        )
        resultado = calcular_plazo("2026-10-21", 3)
        self.assertIn("2026-10-27", resultado)
        self.assertIn("Feriado de prueba", resultado)

    @patch("chatbot.herramientas._feriados_api", return_value=([], ""))
    def test_calculo_de_plazo_fecha_invalida(self, _mock):
        self.assertIn("No pude interpretar", calcular_plazo("32/13/2026", 3))

    def test_hay_al_menos_tres_herramientas(self):
        nombres = {herramienta.name for herramienta in HERRAMIENTAS}
        self.assertGreaterEqual(len(nombres), 3)
        self.assertTrue(
            {"buscar_reglamentos", "consultar_feriados", "redactar_borrador"}
            <= nombres
        )

    def test_busqueda_sin_resultados_avisa(self):
        with patch("chatbot.herramientas.buscar_semantico", return_value=[]):
            resultado = buscar_en_base_conocimiento("tema inexistente")
        self.assertIn("No se encontraron fragmentos", resultado)


class TestBorradores(unittest.TestCase):

    def test_generar_listar_y_leer(self):
        with tempfile.TemporaryDirectory() as temporal:
            with patch("chatbot.documentos.DOCUMENTOS_DIR", Path(temporal)):
                borrador = generar_borrador(
                    tipo="justificacion_inasistencia",
                    motivo="una gripe con reposo médico",
                    nombre_estudiante="Benjamín Quiroz",
                    asignatura="ISY0101",
                    fecha_referencia="20 de octubre de 2026",
                )
                self.assertTrue(Path(borrador.archivo).exists())
                self.assertIn("3 días hábiles", borrador.contenido)
                self.assertIn("Sección 4.3", borrador.contenido)
                self.assertIn("Benjamín Quiroz", borrador.contenido)
                self.assertIn("[RUT]", borrador.contenido)
                self.assertIn("BORRADOR GENERADO", borrador.contenido)

                registros = listar_borradores()
                self.assertEqual(registros[0]["id"], borrador.id)

                recuperado = leer_borrador(borrador.id)
                self.assertIsNotNone(recuperado)
                self.assertEqual(recuperado.contenido, borrador.contenido)

    def test_tipo_desconocido_usa_carta_general(self):
        with tempfile.TemporaryDirectory() as temporal:
            with patch("chatbot.documentos.DOCUMENTOS_DIR", Path(temporal)):
                borrador = generar_borrador(
                    tipo="algo raro", motivo="una solicitud especial"
                )
                self.assertIn("Carta formal general", borrador.contenido)


class TestMemoriaConversacional(unittest.TestCase):

    def test_recorta_a_la_ventana(self):
        memoria = MemoriaConversacional(max_turnos=2)
        for i in range(5):
            memoria.agregar_usuario(f"pregunta {i}")
            memoria.agregar_asistente(f"respuesta {i}")

        historial = memoria.historial()
        self.assertEqual(len(historial), 4)
        self.assertEqual(historial[0].content, "pregunta 3")
        self.assertEqual(historial[-1].content, "respuesta 4")
        self.assertIsInstance(historial[0], HumanMessage)
        self.assertIsInstance(historial[-1], AIMessage)

    def test_limpiar(self):
        memoria = MemoriaConversacional(max_turnos=3)
        memoria.agregar_usuario("hola")
        memoria.limpiar()
        self.assertEqual(memoria.historial(), [])

    def test_guardar_y_cargar(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = os.path.join(temporal, "sesion.json")
            memoria = MemoriaConversacional(max_turnos=3, ruta=ruta)
            memoria.agregar_usuario("¿cuándo es la matrícula?")
            memoria.agregar_asistente("En la primera quincena de enero.")
            memoria.guardar()

            restaurada = MemoriaConversacional(max_turnos=3, ruta=ruta)
            restaurada.cargar()
            self.assertEqual(
                [m.content for m in restaurada.historial()],
                [m.content for m in memoria.historial()],
            )


class AgenteFalso:

    def __init__(self, borrador):
        self.borrador = borrador
        self.consultas = []

    def invoke(self, entrada, config=None):
        mensajes = list(entrada["messages"])
        self.consultas.append(mensajes[-1].content)
        consulta = mensajes[-1].content

        plan = AIMessage(
            id="ai-plan",
            content="Plan: buscaré el plazo y luego redactaré el borrador.",
            tool_calls=[
                {
                    "name": "buscar_reglamentos",
                    "args": {"consulta": consulta},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        )
        observacion = ToolMessage(
            id="tool-1",
            content=(
                "[Fuente 1 | Sección 4: Evaluaciones, Asistencia y Aprobación | "
                "Recorrección y evaluaciones atrasadas | relevancia 0.901]\n"
                "Las evaluaciones atrasadas se reprograman dentro de 3 días hábiles."
            ),
            tool_call_id="call-1",
            name="buscar_reglamentos",
        )
        escritura = AIMessage(
            id="ai-escritura",
            content="Plan: ya tengo el plazo; generaré el borrador.",
            tool_calls=[
                {
                    "name": "redactar_borrador",
                    "args": {"tipo": "justificacion_inasistencia", "motivo": "gripe"},
                    "id": "call-2",
                    "type": "tool_call",
                }
            ],
        )
        resultado_tool = ToolMessage(
            id="tool-2",
            content=(
                f"Borrador generado correctamente.\nID: {self.borrador.id}\n"
                f"Archivo: {self.borrador.archivo}\nTipo: {self.borrador.titulo}\n"
                f"Vista previa:\n\n{self.borrador.contenido}"
            ),
            tool_call_id="call-2",
            name="redactar_borrador",
        )
        final = AIMessage(
            id="ai-final",
            content=(
                "Puedes justificar la inasistencia dentro de 3 días hábiles "
                "(Fuente: Sección 4.3). El borrador quedó listo para descargar."
            ),
        )
        return {
            "messages": [
                SystemMessage(id="sys", content="prompt del sistema"),
                *mensajes,
                plan,
                observacion,
                escritura,
                resultado_tool,
                final,
            ]
        }


class TestOrquestacionAgente(unittest.TestCase):

    def test_traza_fuentes_borradores_y_memoria(self):
        with tempfile.TemporaryDirectory() as temporal:
            with patch("chatbot.documentos.DOCUMENTOS_DIR", Path(temporal)):
                borrador = generar_borrador(
                    tipo="justificacion_inasistencia",
                    motivo="gripe",
                    nombre_estudiante="Benjamín Quiroz",
                )
                falso = AgenteFalso(borrador)
                memoria = MemoriaConversacional(max_turnos=3)
                agente = AgenteDuocUC(agente=falso, memoria=memoria)

                resultado = agente.responder(
                    "asta cuando puedo justificar una inasistencia"
                )

                self.assertIn("3 días hábiles", resultado.respuesta)
                self.assertEqual(len(resultado.fuentes), 1)
                self.assertEqual(
                    resultado.fuentes[0]["titulo"],
                    "Recorrección y evaluaciones atrasadas",
                )
                self.assertEqual(
                    resultado.herramientas_usadas,
                    ["buscar_reglamentos", "redactar_borrador"],
                )
                self.assertEqual(len(resultado.borradores), 1)
                self.assertEqual(resultado.borradores[0]["id"], borrador.id)
                self.assertEqual(len(resultado.eventos), 4)
                self.assertEqual(resultado.turnos_memoria, 1)

                agente.responder("¿y cuántos días eran?")
                self.assertEqual(len(memoria.historial()), 4)
                self.assertEqual(falso.consultas[0], "asta cuando puedo justificar una inasistencia")
                self.assertIn("¿y cuántos días eran?", falso.consultas[1])

    def test_consulta_vacia(self):
        memoria = MemoriaConversacional(max_turnos=2)
        agente = AgenteDuocUC(agente=AgenteFalso(MagicMock()), memoria=memoria)
        resultado = agente.responder("   ")
        self.assertIn("Escríbeme", resultado.respuesta)
        self.assertEqual(memoria.historial(), [])


if __name__ == "__main__":
    unittest.main()
