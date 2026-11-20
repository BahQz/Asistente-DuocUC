"""Pruebas unitarias para el dataset y CLI de benchmark (EP3).

Valida el contrato de casos.json, integridad frente a la base de conocimiento,
la ejecución en modo dry-run y el control de presupuesto.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from benchmark.ejecutar import cargar_casos, ejecutar_benchmark, estimar_presupuesto
from chatbot.ajustes import BASE_CONOCIMIENTO
from chatbot.conocimiento import cargar_fragmentos


class TestBenchmarkCasos(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ruta_casos = Path(__file__).resolve().parent.parent / "benchmark" / "casos.json"
        with open(cls.ruta_casos, encoding="utf-8") as f:
            cls.datos = json.load(f)
        cls.casos = cls.datos.get("casos", [])
        cls.fragmentos = cargar_fragmentos()
        cls.secciones_existentes = {
            str(f.metadata.get("numero")) for f in cls.fragmentos if f.metadata.get("numero")
        }
        cls.texto_base = Path(BASE_CONOCIMIENTO).read_text(encoding="utf-8").lower()

    def test_estructura_y_campos_obligatorios(self):
        self.assertEqual(self.datos.get("version"), 1)
        self.assertIn("validado_por_humano", self.datos)
        self.assertGreaterEqual(len(self.casos), 40)

        ids_vistos = set()
        for c in self.casos:
            cid = c.get("id")
            self.assertTrue(cid)
            self.assertNotIn(cid, ids_vistos, f"ID duplicado: {cid}")
            ids_vistos.add(cid)

            self.assertIn(c.get("categoria"), (
                "normal", "errata_sinonimo", "jerga", "multi_etapa",
                "seguimiento", "fuera_de_dominio", "ambigua",
                "api_externa", "seguridad_pii", "seguridad_inyeccion",
            ))
            self.assertIn(c.get("perfil"), ("minimo", "completo"))
            self.assertIsInstance(c.get("turnos_previos"), list)
            self.assertIsInstance(c.get("seccion_esperada"), list)
            self.assertIsInstance(c.get("debe_abstenerse"), bool)
            self.assertIsInstance(c.get("herramientas_esperadas"), list)

    def test_perfil_minimo_limite_15_turnos_llm(self):
        estimacion = estimar_presupuesto(self.casos, "minimo")
        turnos_llm = estimacion["turnos_llm"]
        self.assertLessEqual(
            turnos_llm,
            15,
            f"El perfil mínimo supera los 15 turnos con LLM: {turnos_llm}",
        )

    def test_al_menos_cuatro_grupos_de_consistencia(self):
        grupos = {
            c.get("grupo_consistencia")
            for c in self.casos
            if c.get("grupo_consistencia")
        }
        self.assertGreaterEqual(len(grupos), 4)
        self.assertTrue({"asistencia", "retiro", "justificacion", "biblioteca"} <= grupos)

        for g in ("asistencia", "retiro", "justificacion", "biblioteca"):
            variantes = [c for c in self.casos if c.get("grupo_consistencia") == g]
            self.assertGreaterEqual(
                len(variantes),
                3,
                f"Grupo {g} debe tener al menos 3 variantes, tiene {len(variantes)}",
            )

    def test_secciones_esperadas_existen_en_la_base(self):
        for c in self.casos:
            for sec in c.get("seccion_esperada", []):
                self.assertIn(
                    sec,
                    self.secciones_existentes,
                    f"Caso {c['id']}: la sección esperada '{sec}' no existe en el índice.",
                )

    def test_dry_run_termina_exitoso(self):
        ret = ejecutar_benchmark(
            perfil="minimo",
            run_id="test-dry-run",
            ruta_casos=self.ruta_casos,
            dry_run=True,
        )
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
