"""CLI de resumen de KPIs y exportación de datos de referencia (EP3).

Procesa eventos JSONL registrados y genera tablas de números crudos
sin prosa interpretativa, listas para incluir en informes técnicos.
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from chatbot.ajustes import OBS_DIR, PROYECTO_RAIZ
from observabilidad.metricas import (
    calcular_percentiles,
    es_derivacion,
    tasa_bloqueo,
    tasa_exito,
)


def cargar_eventos(
    ruta_log: Path,
    run_id: str | None = None,
    origen: str | None = None,
) -> list[dict[str, Any]]:
    """Carga y filtra eventos desde el archivo JSONL omitiendo líneas corruptas."""
    if not ruta_log.exists():
        return []

    eventos: list[dict[str, Any]] = []
    with open(ruta_log, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                ev = json.loads(linea)
                if run_id and ev.get("run_id") != run_id:
                    continue
                if origen and ev.get("origen") != origen:
                    continue
                eventos.append(ev)
            except Exception:
                continue
    return eventos


def generar_kpis(eventos: list[dict[str, Any]]) -> dict[str, Any]:
    turnos = [e["datos"] for e in eventos if e.get("tipo") == "turno"]
    etapas = [e["datos"] for e in eventos if e.get("tipo") == "etapa"]
    errores = [e["datos"] for e in eventos if e.get("tipo") == "error"]
    seguridad = [e["datos"] for e in eventos if e.get("tipo") == "seguridad"]

    n_turnos = len(turnos)
    latencias = [float(t.get("latencia_total_ms", 0)) for t in turnos]
    stats_lat = calcular_percentiles(latencias)

    tokens = [int(t.get("tokens_total", 0)) for t in turnos]
    tokens_totales = sum(tokens)
    tokens_stats = calcular_percentiles(tokens)

    # Herramientas
    uso_herramientas: Counter = Counter()
    for t in turnos:
        for h in t.get("herramientas") or []:
            uso_herramientas[h] += 1

    # Errores por categoría
    cats_error: Counter = Counter()
    for err in errores:
        cat = err.get("categoria", "otro")
        cats_error[cat] += 1

    # Seguridad por control y acción
    controles_seg: Counter = Counter()
    for s in seguridad:
        clave = f"{s.get('control')}:{s.get('accion')}"
        controles_seg[clave] += 1

    # Derivación y abstención
    abstenciones = [t for t in turnos if t.get("abstencion") is True]
    derivaciones = [t for t in turnos if t.get("derivacion") is True]
    turnos_con_retrieval = [t for t in turnos if t.get("abstencion") is not None]

    pct_abstencion = (
        round(len(abstenciones) / len(turnos_con_retrieval) * 100, 1)
        if turnos_con_retrieval
        else 0.0
    )
    pct_derivacion = round(len(derivaciones) / n_turnos * 100, 1) if n_turnos else 0.0

    return {
        "n_turnos": n_turnos,
        "tasa_exito": tasa_exito(turnos),
        "tasa_bloqueo": tasa_bloqueo(turnos),
        "latencia_total_ms": stats_lat,
        "tokens_totales": tokens_totales,
        "tokens_por_turno": tokens_stats,
        "pct_abstencion": pct_abstencion,
        "pct_derivacion": pct_derivacion,
        "uso_herramientas": dict(uso_herramientas),
        "errores_por_categoria": dict(cats_error),
        "seguridad_por_control": dict(controles_seg),
    }


def imprimir_consola(kpis: dict[str, Any]) -> None:
    print("=" * 66)
    print("  RESUMEN DE KPIs DE OBSERVABILIDAD (DATOS CRUDOS)")
    print("=" * 66)
    print(f"  Total turnos procesados:     {kpis['n_turnos']}")
    print(f"  Tasa de éxito:               {kpis['tasa_exito'] * 100:.1f} %")
    print(f"  Tasa de bloqueos seguridad:  {kpis['tasa_bloqueo'] * 100:.1f} %")
    print(f"  Latencia media:              {kpis['latencia_total_ms']['media']:.1f} ms")
    print(f"  Latencia P50 / P95:          {kpis['latencia_total_ms']['p50']:.1f} ms / {kpis['latencia_total_ms']['p95']:.1f} ms")
    print(f"  Tokens totales consumidos:   {kpis['tokens_totales']:,}")
    print(f"  Tokens por turno (media):    {kpis['tokens_por_turno']['media']:.1f}")
    print(f"  Tasa de abstención:          {kpis['pct_abstencion']} %")
    print(f"  Tasa de derivación oficial:  {kpis['pct_derivacion']} %")
    print("-" * 66)
    print("  Uso de herramientas:")
    for h, cnt in kpis["uso_herramientas"].items():
        print(f"    - {h:25s}: {cnt}")
    print("-" * 66)
    print("  Errores detectados:")
    for cat, cnt in kpis["errores_por_categoria"].items():
        print(f"    - {cat:25s}: {cnt}")
    print("-" * 66)
    print("  Eventos de seguridad:")
    for ctrl, cnt in kpis["seguridad_por_control"].items():
        print(f"    - {ctrl:25s}: {cnt}")
    print("=" * 66)


def exportar_tablas(
    eventos: list[dict[str, Any]],
    kpis: dict[str, Any],
    directorio: Path,
) -> None:
    directorio.mkdir(parents=True, exist_ok=True)

    # 1. eventos_referencia.jsonl
    ruta_jsonl = directorio / "eventos_referencia.jsonl"
    with open(ruta_jsonl, "w", encoding="utf-8") as f:
        for ev in eventos:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    # 2. resumen_referencia.json
    ruta_json = directorio / "resumen_referencia.json"
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(kpis, f, ensure_ascii=False, indent=2)

    # 3. tablas_referencia.md
    ruta_md = directorio / "tablas_referencia.md"
    contenido_md = [
        "# Datos crudos — sin interpretación",
        "",
        "> **Aviso:** Este documento contiene registros numéricos estructurados de la ejecución "
        "del sistema para su examen técnico y análisis individual conforme a la rúbrica de evaluación.",
        "",
        "## 1. Indicadores Clave de Desempeño (KPIs)",
        "",
        "| Métrica | Valor | Unidad / Formato |",
        "|---|---|---|",
        f"| Total de turnos evaluados | {kpis['n_turnos']} | turnos |",
        f"| Tasa de éxito | {kpis['tasa_exito'] * 100:.2f}% | % |",
        f"| Tasa de bloqueos de seguridad | {kpis['tasa_bloqueo'] * 100:.2f}% | % |",
        f"| Latencia media total | {kpis['latencia_total_ms']['media']:.1f} | ms |",
        f"| Latencia P50 (mediana) | {kpis['latencia_total_ms']['p50']:.1f} | ms |",
        f"| Latencia P95 | {kpis['latencia_total_ms']['p95']:.1f} | ms |",
        f"| Tokens totales consumidos | {kpis['tokens_totales']} | tokens |",
        f"| Tokens promedio por turno | {kpis['tokens_por_turno']['media']:.1f} | tokens |",
        f"| Tasa de abstención (retrieval) | {kpis['pct_abstencion']:.1f}% | % |",
        f"| Tasa de derivación oficial | {kpis['pct_derivacion']:.1f}% | % |",
        "",
        "## 2. Frecuencia de Uso de Herramientas",
        "",
        "| Herramienta | Cantidad de Invocaciones |",
        "|---|---|",
    ]

    for h, cnt in kpis["uso_herramientas"].items():
        contenido_md.append(f"| `{h}` | {cnt} |")

    contenido_md.extend([
        "",
        "## 3. Distribución de Errores por Categoría",
        "",
        "| Categoría de Error | Conteo |",
        "|---|---|",
    ])
    for c, cnt in kpis["errores_por_categoria"].items():
        contenido_md.append(f"| `{c}` | {cnt} |")

    contenido_md.extend([
        "",
        "## 4. Controles y Acciones de Seguridad",
        "",
        "| Control y Acción | Frecuencia |",
        "|---|---|",
    ])
    for c, cnt in kpis["seguridad_por_control"].items():
        contenido_md.append(f"| `{c}` | {cnt} |")

    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write("\n".join(contenido_md) + "\n")

    # 4. CSVs individuales
    with open(directorio / "kpis_principales.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metrica", "valor"])
        w.writerow(["n_turnos", kpis["n_turnos"]])
        w.writerow(["tasa_exito", kpis["tasa_exito"]])
        w.writerow(["latencia_media_ms", kpis["latencia_total_ms"]["media"]])
        w.writerow(["latencia_p50_ms", kpis["latencia_total_ms"]["p50"]])
        w.writerow(["latencia_p95_ms", kpis["latencia_total_ms"]["p95"]])
        w.writerow(["tokens_totales", kpis["tokens_totales"]])

    print(f"  Tablas y datos crudos exportados exitosamente en: {directorio}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI de resumen de KPIs de Duqui.")
    parser.add_argument("--run", default=None, help="Filtrar por run_id")
    parser.add_argument("--origen", choices=["app", "benchmark", "consola"], default=None)
    parser.add_argument("--log", default=str(Path(OBS_DIR) / "eventos.jsonl"), help="Ruta al archivo jsonl")
    parser.add_argument("--exportar", default=None, help="Directorio destino para exportar tablas")

    args = parser.parse_args()
    eventos = cargar_eventos(Path(args.log), run_id=args.run, origen=args.origen)

    if not eventos:
        print(f"  No se encontraron eventos en {args.log} con los filtros seleccionados.")
        return

    kpis = generar_kpis(eventos)
    imprimir_consola(kpis)

    if args.exportar:
        exportar_tablas(eventos, kpis, Path(args.exportar))


if __name__ == "__main__":
    main()
