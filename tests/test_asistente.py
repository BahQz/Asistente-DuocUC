"""Pruebas del asistente estudiantil de Duoc UC.

Autor: Benjamín Quiroz
"""

import os
import re
import tempfile
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from chatbot.conocimiento import construir_buscador
from chatbot.herramientas import (
    buscar_en_base_conocimiento,
    consultar_fecha_actual,
    consultar_feriados,
)
from chatbot.memoria import MemoriaVentanaDeslizante


class TestRecuperacion(unittest.TestCase):

    def setUp(self):
        self.buscador = construir_buscador()

    def test_asistencia_minima(self):
        fragmentos = self.buscador("cual es la asistencia minima para aprobar")
        unido = "\n".join(fragmentos)
        self.assertIn("75%", unido)

    def test_tolerancia_a_acentos(self):
        fragmentos = self.buscador("hasta cuando puedo retirar una asignatura")
        unido = "\n".join(fragmentos)
        self.assertIn("semana 8", unido)

    def test_sinonimos_de_dinero(self):
        fragmentos = self.buscador("cuando vence la plata del arancel")
        unido = re.sub(r"\s+", " ", "\n".join(fragmentos))
        self.assertIn("15 de marzo", unido)

    def test_tema_desconocido_no_devuelve_nada(self):
        fragmentos = self.buscador("tutorias de surf en la playa")
        self.assertEqual(fragmentos, [])


class TestBuscarEnBaseConocimiento(unittest.TestCase):

    @patch("chatbot.herramientas._obtener_buscador")
    def test_devuelve_resultados(self, mock_buscador):
        mock_buscador.return_value = lambda q, top_k=3: [
            "La biblioteca atiende hasta las 21:00 horas."
        ]
        resultado = buscar_en_base_conocimiento("horario biblioteca")
        self.assertIn("21:00", resultado)

    @patch("chatbot.herramientas._obtener_buscador")
    def test_sin_resultados_avisa(self, mock_buscador):
        mock_buscador.return_value = lambda q, top_k=3: []
        resultado = buscar_en_base_conocimiento("tema inexistente")
        self.assertIn("No se encontró información", resultado)


class TestHerramientas(unittest.TestCase):

    def test_fecha_actual_incluye_anio(self):
        resultado = consultar_fecha_actual()
        self.assertIn(str(date.today().year), resultado)
        self.assertIn("Hoy es", resultado)

    @patch("chatbot.herramientas.requests.get")
    def test_feriados_formateados(self, mock_get):
        mock_respuesta = MagicMock()
        mock_respuesta.json.return_value = [
            {"date": "2026-01-01", "localName": "Año Nuevo"},
            {"date": "2026-05-01", "localName": "Día del Trabajo"},
        ]
        mock_respuesta.raise_for_status = MagicMock()
        mock_get.return_value = mock_respuesta

        resultado = consultar_feriados(2026)
        self.assertIn("Año Nuevo", resultado)
        self.assertIn("2026-05-01", resultado)

    @patch("chatbot.herramientas.requests.get")
    def test_feriados_maneja_timeout(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout()
        resultado = consultar_feriados()
        self.assertIn("timeout", resultado.lower())


class TestMemoriaVentanaDeslizante(unittest.TestCase):

    def test_recorta_a_la_ventana(self):
        memoria = MemoriaVentanaDeslizante(max_turnos=2)
        for i in range(5):
            memoria.agregar_usuario(f"pregunta {i}")
            memoria.agregar_asistente(f"respuesta {i}")

        historial = memoria.historial()
        self.assertEqual(len(historial), 4)
        self.assertEqual(historial[0]["content"], "pregunta 3")
        self.assertEqual(historial[-1]["content"], "respuesta 4")

    def test_limpiar(self):
        memoria = MemoriaVentanaDeslizante(max_turnos=3)
        memoria.agregar_usuario("hola")
        memoria.limpiar()
        self.assertEqual(memoria.historial(), [])

    def test_guardar_y_cargar(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = os.path.join(temporal, "sesion.json")
            memoria = MemoriaVentanaDeslizante(max_turnos=3, ruta=ruta)
            memoria.agregar_usuario("¿cuándo es la matrícula?")
            memoria.agregar_asistente("En la primera quincena de enero.")
            memoria.guardar()

            restaurada = MemoriaVentanaDeslizante(max_turnos=3, ruta=ruta)
            restaurada.cargar()
            self.assertEqual(restaurada.historial(), memoria.historial())


if __name__ == "__main__":
    unittest.main()
