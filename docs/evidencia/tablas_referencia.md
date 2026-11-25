# Datos crudos — sin interpretación

> **Aviso:** Este documento contiene registros numéricos estructurados de la ejecución del sistema para su examen técnico y análisis individual conforme a la rúbrica de evaluación.

## 1. Indicadores Clave de Desempeño (KPIs)

| Métrica | Valor | Unidad / Formato |
|---|---|---|
| Total de turnos evaluados | 17 | turnos |
| Casos de benchmark evaluados | 16 | casos |
| Tasa de éxito | 100.00% | % |
| Tasa de bloqueos de seguridad | 29.41% | % |
| Latencia media total | 23712.6 | ms |
| Latencia P50 (mediana) | 20125.0 | ms |
| Latencia P95 | 50401.8 | ms |
| Tokens totales consumidos | 74857 | tokens |
| Tokens promedio por turno | 4403.4 | tokens |
| Tasa de abstención (retrieval) | 0.0% | % |
| Tasa de derivación oficial | 11.8% | % |
| Precision@1 (benchmark RAG) | 88.89% | % |
| Hit@k (benchmark RAG) | 88.89% | % |
| Abstención correcta (fuera de dominio) | 100.00% | % |
| Falsos rechazos (en dominio) | 0.00% | % |

## 2. Frecuencia de Uso de Herramientas

| Herramienta | Cantidad de Invocaciones |
|---|---|
| `buscar_reglamentos` | 9 |
| `calcular_plazo` | 2 |
| `consultar_feriados` | 1 |

## 3. Distribución de Errores por Categoría

| Categoría de Error | Conteo |
|---|---|

## 4. Controles y Acciones de Seguridad

| Control y Acción | Frecuencia |
|---|---|
| `respuesta_sin_respaldo:alertado` | 6 |
| `fuga_prompt:bloqueado` | 1 |
| `respuesta_sin_respaldo:bloqueado` | 2 |
| `pii:enmascarado` | 1 |
| `prompt_injection:bloqueado` | 2 |
