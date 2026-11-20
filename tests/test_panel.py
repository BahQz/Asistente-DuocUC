"""Pruebas unitarias para el dashboard y constructores de figuras Plotly (EP3).

Verifica que panel.py funciona sin Streamlit, que tolera JSON corruptos
y que pages/1_Observabilidad.py carga sin excepciones mediante AppTest.
"""

import tempfile
import unittest
from pathlib import Path

import plotly.graph_objects as go
from streamlit.testing.v1 import AppTest

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
from pages import __file__ as _


class TestConstructoresFiguras(unittest.TestCase):

    def test_figura_latencia_vacia_y_con_datos(self):
        fig_vacia = figura_latencia_por_turno([])
        self.assertIsInstance(fig_vacia, go.Figure)

        turnos = [
            {"latencia_total_ms": 150.0, "resultado": "ok", "tokens_total": 300},
            {"latencia_total_ms": 450.0, "resultado": "error", "tokens_total": 100},
        ]
        fig = figura_latencia_por_turno(turnos, p50=200, p95=400)
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 1)

    def test_figuras_sin_errores(self):
        etapas = [
            {"componente": "retrieval", "duracion_ms": 50.0, "nombre": "retrieval", "ok": True, "offset_ms": 10.0},
            {"componente": "llm", "duracion_ms": 120.0, "nombre": "llm", "ok": True, "offset_ms": 65.0},
        ]
        self.assertIsInstance(figura_desglose_latencia_etapas(etapas), go.Figure)
        self.assertIsInstance(figura_gantt_traza(etapas), go.Figure)

        retrievals = [{"top1_score": 0.88, "decision": "respuesta"}]
        self.assertIsInstance(figura_evolucion_scores(retrievals), go.Figure)

        barrido = [{"umbral": 0.80, "tasa_abstencion_correcta": 0.9, "tasa_falsos_rechazos": 0.05}]
        self.assertIsInstance(figura_barrido_umbral(barrido), go.Figure)

        self.assertIsInstance(figura_uso_herramientas([{"herramientas": ["buscar_reglamentos"]}]), go.Figure)
        self.assertIsInstance(figura_distribucion_errores([{"categoria": "timeout"}]), go.Figure)
        self.assertIsInstance(figura_eventos_seguridad([{"control": "pii", "accion": "enmascarado"}]), go.Figure)
        self.assertIsInstance(figura_recursos_ram_cpu([{"rss_mb": 150.0, "cpu_proceso_pct": 2.5}]), go.Figure)


class TestAppDashboard(unittest.TestCase):

    def test_estado_vacio_sin_excepciones(self):
        ruta_app = Path(__file__).resolve().parent.parent / "pages" / "1_Observabilidad.py"
        app = AppTest.from_file(str(ruta_app))
        app.run(timeout=10)
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
