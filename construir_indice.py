import argparse

from chatbot.conocimiento import (
    buscar_semantico,
    cargar_fragmentos,
    construir_indice,
    informacion_indice,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Indexa la base de conocimiento de Duoc UC en ChromaDB."
    )
    parser.add_argument(
        "--reindexar",
        action="store_true",
        help="Fuerza la reconstrucción completa del índice.",
    )
    parser.add_argument(
        "--probar",
        metavar="CONSULTA",
        help="Ejecuta una búsqueda semántica de prueba al terminar.",
    )
    argumentos = parser.parse_args()

    documentos = cargar_fragmentos()
    print(f"Base de conocimiento: {len(documentos)} fragmentos detectados.")
    construir_indice(forzar=argumentos.reindexar, verboso=True)

    indice = informacion_indice()
    print("\nResumen del índice:")
    print(f"  - Vectores: {indice['fragmentos']}")
    print(f"  - Modelo: {indice['modelo']}")
    print(f"  - Directorio: {indice['directorio']}")
    print(f"  - Actualizado: {indice['actualizado']}")

    if argumentos.probar:
        print(f'\nBúsqueda de prueba: "{argumentos.probar}"')
        resultados = buscar_semantico(argumentos.probar, top_k=4)
        if not resultados:
            print("  Sin resultados sobre el umbral de relevancia.")
        for fragmento in resultados:
            print(
                f"  - {fragmento.relevancia:.3f} | {fragmento.seccion} — "
                f"{fragmento.titulo}"
            )
            print(f"    {fragmento.contenido[:160].replace(chr(10), ' ')}…")


if __name__ == "__main__":
    main()
