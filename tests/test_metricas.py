"""Pruebas unitarias para las funciones de cálculo de métricas (EP3).

Prueba funciones matemáticas puras (percentiles, tasas, matrices, consistencia,
barrido y reglas de anomalías) con fixtures sintéticos.
"""

import unittest

from observabilidad.metricas import (
    barrido_umbral,
    calcular_percentil,
    calcular_percentiles,
    consistencia_por_grupo,
    detectar_anomalias,
    es_derivacion,
    hit_at_k,
    matriz_abstencion,
    precision_at_1,
    tasa_bloqueo,
    tasa_exito,
)


class TestMetricas(unittest.TestCase):

    def test_es_derivacion(self):
        self.assertTrue(es_derivacion("Por favor contacta a soporte@duocuc.cl"))
        self.assertTrue(es_derivacion("Llama a la mesa de ayuda al 600-300-4000"))
        self.assertTrue(es_derivacion("Acude a tu direccion de escuela."))
        self.assertFalse(es_derivacion("El horario de la biblioteca es de 8:00 a 20:00."))

    def test_percentiles(self):
        datos = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        res = calcular_percentiles(datos)
        self.assertEqual(res["media"], 55.0)
        self.assertEqual(res["p50"], 55.0)
        self.assertAlmostEqual(res["p95"], 95.5, places=1)

    def test_tasas(self):
        turnos = [
            {"resultado": "ok"},
            {"resultado": "ok"},
            {"resultado": "error"},
            {"resultado": "bloqueado_entrada"},
        ]
        self.assertAlmostEqual(tasa_exito(turnos), 2 / 3, places=3)
        self.assertEqual(tasa_bloqueo(turnos), 0.25)

    def test_precision_y_hit(self):
        casos = [
            {
                "esperado": {"seccion_esperada": ["4.1", "4.2"]},
                "observado": {"top1_numero": "4.1", "hit_topk": True},
            },
            {
                "esperado": {"seccion_esperada": ["2.3"]},
                "observado": {"top1_numero": "2.1", "hit_topk": True},
            },
            {
                "esperado": {"seccion_esperada": ["5.1"]},
                "observado": {"top1_numero": "9.9", "hit_topk": False},
            },
        ]
        self.assertAlmostEqual(precision_at_1(casos), 1 / 3, places=3)
        self.assertAlmostEqual(hit_at_k(casos), 2 / 3, places=3)

    def test_matriz_abstencion(self):
        casos = [
            # TP: debía abstenerse y se abstuvo
            {"esperado": {"debe_abstenerse": True}, "observado": {"decision": "abstencion"}},
            # TN: era del dominio y respondió
            {"esperado": {"debe_abstenerse": False}, "observado": {"decision": "respuesta"}},
            # FP: era del dominio pero se abstuvo (falso rechazo)
            {"esperado": {"debe_abstenerse": False}, "observado": {"decision": "abstencion"}},
            # FN: debía abstenerse pero respondió (alucinación)
            {"esperado": {"debe_abstenerse": True}, "observado": {"decision": "respuesta"}},
        ]
        mat = matriz_abstencion(casos)
        self.assertEqual(mat["tp"], 1)
        self.assertEqual(mat["fp"], 1)
        self.assertEqual(mat["tn"], 1)
        self.assertEqual(mat["fn"], 1)
        self.assertEqual(mat["tasa_abstencion_correcta"], 0.5)
        self.assertEqual(mat["tasa_falsos_rechazos"], 0.5)

    def test_consistencia_por_grupo(self):
        casos = [
            {
                "grupo_consistencia": "asistencia",
                "observado": {
                    "top1_numero": "4.1",
                    "decision": "respuesta",
                    "top1_score": 0.88,
                    "datos_clave_ok": True,
                },
            },
            {
                "grupo_consistencia": "asistencia",
                "observado": {
                    "top1_numero": "4.1",
                    "decision": "respuesta",
                    "top1_score": 0.86,
                    "datos_clave_ok": True,
                },
            },
            {
                "grupo_consistencia": "asistencia",
                "observado": {
                    "top1_numero": "4.1",
                    "decision": "respuesta",
                    "top1_score": 0.87,
                    "datos_clave_ok": False,
                },
            },
        ]
        res = consistencia_por_grupo(casos)
        self.assertIn("asistencia", res)
        self.assertEqual(res["asistencia"]["consistencia_recuperacion"], 1.0)
        self.assertEqual(res["asistencia"]["consistencia_decision"], 1.0)
        self.assertAlmostEqual(res["asistencia"]["consistencia_respuesta"], 2 / 3, places=2)
        self.assertLess(res["asistencia"]["std_score"], 0.05)

    def test_barrido_umbral(self):
        candidatos = [
            {"debe_abstenerse": True, "top1_score": 0.78},
            {"debe_abstenerse": False, "top1_score": 0.85},
        ]
        barrido = barrido_umbral(candidatos, min_u=0.76, max_u=0.90, paso=0.05)
        self.assertTrue(len(barrido) >= 3)
        for fila in barrido:
            self.assertIn("umbral", fila)
            self.assertIn("tasa_abstencion_correcta", fila)

    def test_detectar_anomalias(self):
        turnos = [
            {"trace_id": "t1", "latencia_total_ms": 100, "tokens_total": 500, "resultado": "ok", "herramientas": ["t1"]},
            {"trace_id": "t2", "latencia_total_ms": 200, "tokens_total": 600, "resultado": "error", "herramientas": ["t1"]},
            {"trace_id": "t3", "latencia_total_ms": 250, "tokens_total": 700, "resultado": "error", "herramientas": ["t1"]},  # racha_errores >= 2
            {"trace_id": "t4", "latencia_total_ms": 2000, "tokens_total": 5000, "resultado": "ok", "herramientas": ["a", "b", "c", "d"]},  # muchas herramientas
        ]
        anomalias = detectar_anomalias(turnos)
        reglas_detectadas = {a["regla"] for a in anomalias}
        self.assertIn("racha_errores_ge_2", reglas_detectadas)
        self.assertIn("muchas_herramientas", reglas_detectadas)


if __name__ == "__main__":
    unittest.main()
