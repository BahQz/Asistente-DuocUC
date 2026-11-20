"""Ejecutor del benchmark económico en tokens (EP3).

Permite evaluar precisión de recuperación semántica (0 tokens de LLM),
o ejecutar perfiles mínimos/completos con estricto control presupuestario.
"""

import argparse
import csv
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chatbot.ajustes import (
    BENCH_MAX_TURNOS_LLM,
    BENCH_PAUSA_SEG,
    BENCH_PRESUPUESTO_TOKENS,
    BENCH_TOKENS_POR_TURNO_ESTIMADO,
    PROYECTO_RAIZ,
)
from chatbot.seguridad import enmascarar, normalizar_texto_seguro
from observabilidad.metricas import (
    barrido_umbral,
    calcular_percentiles,
    consistencia_por_grupo,
    hit_at_k,
    matriz_abstencion,
    precision_at_1,
)
from observabilidad.registro import iniciar_traza, registrar, traza_actual


def generar_run_id() -> str:
    ahora = datetime.now().strftime("%Y%m%d-%H%M%S")
    sufijo = uuid.uuid4().hex[:4]
    return f"{ahora}-{sufijo}"


def cargar_casos(ruta: Path) -> dict[str, Any]:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def estimar_presupuesto(casos: list[dict[str, Any]], perfil: str) -> dict[str, Any]:
    casos_filtrados = [
        c for c in casos
        if perfil == "completo" or c.get("perfil") == "minimo"
    ]

    turnos_llm = 0
    if perfil != "retrieval":
        for c in casos_filtrados:
            # Los casos de inyección se bloquean antes del LLM
            if c.get("esperado_bloqueo") == "bloqueado_entrada":
                continue
            turnos_llm += 1
            if c.get("turnos_previos"):
                turnos_llm += len(c["turnos_previos"])

    tokens_estimados = turnos_llm * BENCH_TOKENS_POR_TURNO_ESTIMADO
    return {
        "n_casos": len(casos_filtrados),
        "turnos_llm": turnos_llm,
        "tokens_estimados": tokens_estimados,
        "casos_filtrados": casos_filtrados,
    }


def ejecutar_benchmark(
    perfil: str,
    run_id: str,
    ruta_casos: Path,
    dry_run: bool = False,
    auto_confirmar: bool = False,
    pausa_seg: float = BENCH_PAUSA_SEG,
    presupuesto_tokens: int = BENCH_PRESUPUESTO_TOKENS,
    max_turnos_llm: int = BENCH_MAX_TURNOS_LLM,
    repeticiones_retrieval: int = 3,
) -> int:
    datos_casos = cargar_casos(ruta_casos)
    casos = datos_casos.get("casos", [])

    estimacion = estimar_presupuesto(casos, perfil)
    casos_a_ejecutar = estimacion["casos_filtrados"]
    turnos_llm_estimados = estimacion["turnos_llm"]
    tokens_estimados = estimacion["tokens_estimados"]

    print("=" * 66)
    print(f"  Benchmark Duqui EP3 · Perfil: {perfil.upper()} · Run ID: {run_id}")
    print("=" * 66)
    print(f"  Casos seleccionados:    {len(casos_a_ejecutar)}")
    print(f"  Turnos LLM estimados:   {turnos_llm_estimados} (máximo permitido: {max_turnos_llm})")
    print(f"  Tokens LLM estimados:   ~{tokens_estimados:,} tokens (presupuesto: {presupuesto_tokens:,})")
    print(f"  Pausa entre llamadas:   {pausa_seg:.1f} s")
    print(f"  Dataset validado:       {datos_casos.get('validado_por_humano', False)}")
    print("-" * 66)

    if dry_run:
        print("\n  [DRY-RUN] Simulación exitosa. No se consumieron tokens ni llamadas de red.")
        return 0

    if perfil != "retrieval" and not auto_confirmar:
        confirmacion = input("  ¿Deseas continuar con la ejecución real? [s/N]: ").strip().lower()
        if confirmacion not in ("s", "si", "sí", "y", "yes"):
            print("  Ejecución cancelada por el usuario.")
            return 0

    # Importaciones dinámicas para evitar cargar E5 o LangChain en dry-run
    from chatbot.conocimiento import buscar_semantico_detallado
    from chatbot.seguridad import analizar_inyeccion

    resultados_casos: list[dict[str, Any]] = []
    tokens_consumidos_total = 0
    turnos_llm_ejecutados = 0
    errores_429_consecutivos = 0
    abortado_por: str | None = None

    agente_real = None
    if perfil in ("minimo", "completo"):
        from chatbot.agente import AgenteDuocUC
        agente_real = AgenteDuocUC(origen="benchmark", run_id=run_id)

    print("\n  Iniciando ejecución de casos...")

    try:
        for idx, caso in enumerate(casos_a_ejecutar, 1):
            caso_id = caso["id"]
            consulta = caso.get("consulta", "")
            seccion_esp = caso.get("seccion_esperada", [])
            debe_abstenerse = caso.get("debe_abstenerse", False)
            herramientas_esp = caso.get("herramientas_esperadas", [])
            datos_clave_esp = caso.get("datos_clave", [])
            bloqueo_esp = caso.get("esperado_bloqueo")

            print(f"  [{idx:02d}/{len(casos_a_ejecutar):02d}] Caso {caso_id} ({caso.get('categoria')})... ", end="", flush=True)

            # Capa 1: Retrieval semántico (0 tokens)
            retrieval_res = buscar_semantico_detallado(consulta)
            candidatos = retrieval_res.candidatos
            top1_cand = candidatos[0] if candidatos else {}
            top1_numero = str(top1_cand.get("numero", ""))
            top1_score = retrieval_res.top1_score

            acierto_top1 = any(top1_numero == s or s in top1_numero for s in seccion_esp) if seccion_esp else False
            hit_topk = any(
                any(str(c.get("numero", "")) == s or s in str(c.get("numero", "")) for s in seccion_esp)
                for c in candidatos
            ) if seccion_esp else False

            abstencion_correcta = (retrieval_res.decision == "abstencion") if debe_abstenerse else (retrieval_res.decision == "respuesta")

            # Capa 2: Seguridad de entrada
            iny = analizar_inyeccion(consulta)
            bloqueo_real = "bloqueado_entrada" if iny["severidad"] == "alta" else None

            # Capa 3: Ejecución LLM si el perfil lo requiere y no está bloqueado
            herramientas_usadas: list[str] = []
            orden_correcto = True
            datos_clave_ok = True
            resultado_turno = "ok"
            tokens_caso = 0
            latencia_caso_ms = retrieval_res.total_ms

            if perfil in ("minimo", "completo") and agente_real is not None:
                # Comprobar presupuesto
                if tokens_consumidos_total >= presupuesto_tokens:
                    abortado_por = "presupuesto_tokens_excedido"
                    print("ABORTADO (presupuesto alcanzado)")
                    break
                if turnos_llm_ejecutados >= max_turnos_llm:
                    abortado_por = "max_turnos_llm_alcanzado"
                    print("ABORTADO (máximo turnos alcanzado)")
                    break

                # Nueva sesión y memoria por caso
                agente_real.limpiar_memoria()
                agente_real.session_id = f"bench_{run_id}_{caso_id}"

                # Ejecutar turnos previos de contexto si existen
                for prev in caso.get("turnos_previos", []):
                    agente_real.responder(prev)
                    turnos_llm_ejecutados += 1
                    time.sleep(pausa_seg)

                # Turno del caso
                try:
                    res_agente = agente_real.responder(consulta)
                    turnos_llm_ejecutados += 1
                    errores_429_consecutivos = 0

                    herramientas_usadas = res_agente.herramientas_usadas
                    bloqueo_real = "bloqueado_entrada" if "bloqueado" in [a.get("accion") for a in res_agente.avisos_seguridad] else None

                    # Verificar orden de herramientas esperadas
                    if herramientas_esp:
                        indices = []
                        for h in herramientas_esp:
                            if h in herramientas_usadas:
                                indices.append(herramientas_usadas.index(h))
                            else:
                                indices.append(999)
                        orden_correcto = indices == sorted(indices) and all(idx < 999 for idx in indices)

                    # Verificar datos clave en respuesta
                    resp_norm = normalizar_texto_seguro(res_agente.respuesta)
                    for dk in datos_clave_esp:
                        alternativas = [normalizar_texto_seguro(a.strip()) for a in dk.split("|")]
                        if not any(alt in resp_norm for alt in alternativas):
                            datos_clave_ok = False
                            break

                    metricas = res_agente.metricas or {}
                    tokens_caso = metricas.get("tokens_total", 0)
                    tokens_consumidos_total += tokens_caso
                    latencia_caso_ms = metricas.get("latencia_total_ms", 0.0)

                except Exception as exc:
                    resultado_turno = "error"
                    if "429" in str(exc):
                        errores_429_consecutivos += 1
                        if errores_429_consecutivos >= 3:
                            abortado_por = "tres_errores_429_consecutivos"
                            print("ABORTADO (3 errores 429 seguidos)")
                            break

                time.sleep(pausa_seg)

            caso_observado = {
                "top1_numero": top1_numero,
                "top1_score": top1_score,
                "decision": retrieval_res.decision,
                "acierto_top1": acierto_top1,
                "hit_topk": hit_topk,
                "abstencion_correcta": abstencion_correcta,
                "herramientas_usadas": herramientas_usadas,
                "orden_correcto": orden_correcto,
                "datos_clave_ok": datos_clave_ok,
                "bloqueo_real": bloqueo_real,
                "resultado_turno": resultado_turno,
                "tokens_total": tokens_caso,
                "latencia_total_ms": latencia_caso_ms,
            }

            caso_resultado = {
                "caso_id": caso_id,
                "categoria": caso.get("categoria"),
                "grupo_consistencia": caso.get("grupo_consistencia"),
                "perfil": perfil,
                "capa": "retrieval" if perfil == "retrieval" else "llm",
                "esperado": {
                    "seccion_esperada": seccion_esp,
                    "debe_abstenerse": debe_abstenerse,
                    "herramientas_esperadas": herramientas_esp,
                    "datos_clave": datos_clave_esp,
                    "esperado_bloqueo": bloqueo_esp,
                },
                "observado": caso_observado,
            }

            resultados_casos.append(caso_resultado)

            # Registrar evento benchmark_caso
            registrar("benchmark_caso", caso_resultado, run_id=run_id)

            estado_str = "OK" if (acierto_top1 or debe_abstenerse or bloqueo_real) else "REVISAR"
            print(f"{estado_str} (top1={top1_numero or 'n/a'} score={top1_score:.3f} tokens={tokens_caso})")

    except KeyboardInterrupt:
        abortado_por = "interrupcion_usuario_ctrl_c"
        print("\n  [INTERRUPCIÓN] Deteniendo benchmark y guardando resultados parciales...")

    # Guardar resumen y CSV
    dir_salida = PROYECTO_RAIZ / "logs" / "benchmark" / run_id
    dir_salida.mkdir(parents=True, exist_ok=True)

    ruta_resumen = dir_salida / "resumen.json"
    ruta_csv = dir_salida / "resultados_por_caso.csv"

    # KPIs de la corrida
    prec1 = precision_at_1(resultados_casos)
    hitk = hit_at_k(resultados_casos)
    mat_abs = matriz_abstencion(resultados_casos)
    cons_grupo = consistencia_por_grupo(resultados_casos)
    latencias = [c["observado"]["latencia_total_ms"] for c in resultados_casos]
    stats_lat = calcular_percentiles(latencias)

    resumen_data = {
        "run_id": run_id,
        "perfil": perfil,
        "fecha": datetime.now(timezone.utc).isoformat(),
        "abortado_por": abortado_por,
        "total_casos_evaluados": len(resultados_casos),
        "turnos_llm_ejecutados": turnos_llm_ejecutados,
        "tokens_totales_consumidos": tokens_consumidos_total,
        "kpis": {
            "precision_at_1": prec1,
            "hit_at_k": hitk,
            "matriz_abstencion": mat_abs,
            "consistencia_grupos": cons_grupo,
            "latencia_ms": stats_lat,
        },
    }

    with open(ruta_resumen, "w", encoding="utf-8") as f:
        json.dump(resumen_data, f, ensure_ascii=False, indent=2)

    # Exportar CSV por caso
    if resultados_casos:
        with open(ruta_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "caso_id", "categoria", "grupo_consistencia",
                "seccion_esperada", "debe_abstenerse",
                "top1_numero", "top1_score", "decision",
                "acierto_top1", "hit_topk", "abstencion_correcta",
                "datos_clave_ok", "tokens_total", "latencia_ms"
            ])
            for r in resultados_casos:
                obs = r["observado"]
                esp = r["esperado"]
                writer.writerow([
                    r["caso_id"], r["categoria"], r.get("grupo_consistencia", ""),
                    "|".join(esp.get("seccion_esperada", [])), esp.get("debe_abstenerse", False),
                    obs.get("top1_numero", ""), obs.get("top1_score", 0.0), obs.get("decision", ""),
                    obs.get("acierto_top1", False), obs.get("hit_topk", False), obs.get("abstencion_correcta", False),
                    obs.get("datos_clave_ok", False), obs.get("tokens_total", 0), obs.get("latencia_total_ms", 0.0)
                ])

    print("\n" + "=" * 66)
    print("  RESULTADOS DEL BENCHMARK")
    print("=" * 66)
    print(f"  Precision@1:             {prec1 * 100:.1f} %")
    print(f"  Hit@k:                   {hitk * 100:.1f} %")
    print(f"  Abstención correcta:     {mat_abs['tasa_abstencion_correcta'] * 100:.1f} %")
    print(f"  Falsos rechazos:         {mat_abs['tasa_falsos_rechazos'] * 100:.1f} %")
    print(f"  Latencia P50 / P95:      {stats_lat['p50']:.1f} ms / {stats_lat['p95']:.1f} ms")
    print(f"  Tokens LLM consumidos:   {tokens_consumidos_total:,}")
    print(f"  Resumen exportado en:    {ruta_resumen}")
    print(f"  CSV exportado en:        {ruta_csv}")
    print("=" * 66)

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLI de benchmark económico en tokens de Duqui (EP3)."
    )
    parser.add_argument(
        "--perfil",
        choices=["retrieval", "minimo", "completo"],
        required=True,
        help="Perfil de ejecución: retrieval (0 tokens), minimo (<=15 turnos) o completo",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Identificador del run (por defecto generado automáticamente)",
    )
    parser.add_argument(
        "--casos",
        default=str(PROYECTO_RAIZ / "benchmark" / "casos.json"),
        help="Ruta al archivo casos.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calcula el plan y tokens sin realizar llamadas ni cargar modelos",
    )
    parser.add_argument(
        "--si",
        action="store_true",
        help="Confirma automáticamente sin solicitar [s/N]",
    )
    parser.add_argument(
        "--pausa",
        type=float,
        default=BENCH_PAUSA_SEG,
        help="Segundos de pausa entre turnos LLM",
    )
    parser.add_argument(
        "--presupuesto-tokens",
        type=int,
        default=BENCH_PRESUPUESTO_TOKENS,
        help="Límite máximo de tokens acumulados antes de abortar",
    )
    parser.add_argument(
        "--max-turnos-llm",
        type=int,
        default=BENCH_MAX_TURNOS_LLM,
        help="Límite máximo de turnos con LLM",
    )
    parser.add_argument(
        "--repeticiones-retrieval",
        type=int,
        default=3,
        help="Repeticiones de retrieval",
    )

    args = parser.parse_args()
    run_id = args.run_id or generar_run_id()

    codigo = ejecutar_benchmark(
        perfil=args.perfil,
        run_id=run_id,
        ruta_casos=Path(args.casos),
        dry_run=args.dry_run,
        auto_confirmar=args.si,
        pausa_seg=args.pausa,
        presupuesto_tokens=args.presupuesto_tokens,
        max_turnos_llm=args.max_turnos_llm,
        repeticiones_retrieval=args.repeticiones_retrieval,
    )
    sys.exit(codigo)


if __name__ == "__main__":
    main()
