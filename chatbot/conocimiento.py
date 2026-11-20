import hashlib
import json
import re
import time
import unicodedata
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

from chatbot.ajustes import (
    BASE_CONOCIMIENTO,
    COLECCION_REGLAMENTOS,
    EMBEDDINGS_DISPOSITIVO,
    EMBEDDINGS_MODEL,
    FRAGMENTOS_MAXIMOS,
    FRAGMENTOS_POR_DEFECTO,
    MARGEN_RELEVANCIA,
    OBS_ZONA_GRIS,
    UMBRAL_RELEVANCIA,
    VECTOR_DIR,
)
from chatbot.seguridad import enmascarar
from observabilidad.recursos import instantanea, registrar_recursos
from observabilidad.registro import marcar_turno_frio, medir_etapa, registrar

PATRON_SECCION = re.compile(r"(?m)^##\s+(.+)$")
PATRON_SUBSECCION = re.compile(r"(?m)^(\d+\.\d+)\s+(.+)$")

VERSION_INDICE = "2"
_CANDADO = Lock()
_ULTIMO_EMBED_MS: ContextVar[float] = ContextVar("ultimo_embed_ms", default=0.0)


@dataclass(frozen=True)
class Fragmento:
    id: str
    seccion: str
    titulo: str
    contenido: str
    relevancia: float = 0.0

    @property
    def cita(self) -> str:
        return f"{self.seccion} — {self.titulo}" if self.titulo else self.seccion


@dataclass
class ResultadoBusqueda:
    candidatos: list[dict] = field(default_factory=list)
    aceptados: list[Fragmento] = field(default_factory=list)
    top1_score: float = 0.0
    distancia_a_umbral: float = 0.0
    decision: str = "abstencion"
    zona_gris: bool = False
    embedding_ms: float = 0.0
    chroma_ms: float = 0.0
    total_ms: float = 0.0


def normalizar(texto: str) -> str:
    texto = texto.lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def cargar_fragmentos(ruta: Path = BASE_CONOCIMIENTO) -> list[Document]:
    contenido = Path(ruta).read_text(encoding="utf-8")
    partes = PATRON_SECCION.split(contenido)

    documentos: list[Document] = []
    indice = 0

    preambulo = partes[0].strip()
    if preambulo:
        documentos.append(
            Document(
                page_content=(
                    "Presentación de la base de conocimiento\n" + preambulo
                ),
                metadata={
                    "id": "s00-preambulo",
                    "seccion": "Presentación de la base de conocimiento",
                    "titulo": "Alcance del documento",
                    "numero": "0",
                    "fuente": Path(ruta).name,
                    "orden": 0,
                },
            )
        )

    for posicion in range(1, len(partes), 2):
        seccion = partes[posicion].strip()
        cuerpo = partes[posicion + 1].strip() if posicion + 1 < len(partes) else ""
        if not cuerpo:
            continue

        subsecciones = list(PATRON_SUBSECCION.finditer(cuerpo))
        if not subsecciones:
            indice += 1
            documentos.append(
                Document(
                    page_content=f"{seccion}\n{cuerpo}",
                    metadata={
                        "id": f"s{indice:02d}-general",
                        "seccion": seccion,
                        "titulo": "Disposiciones generales",
                        "numero": str(indice),
                        "fuente": Path(ruta).name,
                        "orden": indice,
                    },
                )
            )
            continue

        for numero, coincidencia in enumerate(subsecciones):
            inicio = coincidencia.start()
            fin = (
                subsecciones[numero + 1].start()
                if numero + 1 < len(subsecciones)
                else len(cuerpo)
            )
            bloque = cuerpo[inicio:fin].strip()
            if not bloque:
                continue

            indice += 1
            documentos.append(
                Document(
                    page_content=f"{seccion}\n{bloque}",
                    metadata={
                        "id": f"s{indice:02d}-{coincidencia.group(1)}",
                        "seccion": seccion,
                        "titulo": coincidencia.group(2).strip(),
                        "numero": coincidencia.group(1),
                        "fuente": Path(ruta).name,
                        "orden": indice,
                    },
                )
            )

    return documentos


def _huella_base(ruta: Path = BASE_CONOCIMIENTO) -> str:
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()[:16]


def _ruta_meta() -> Path:
    return Path(VECTOR_DIR) / "indice_meta.json"


def _leer_meta() -> dict:
    try:
        return json.loads(_ruta_meta().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _guardar_meta(fragmentos: int) -> None:
    Path(VECTOR_DIR).mkdir(parents=True, exist_ok=True)
    _ruta_meta().write_text(
        json.dumps(
            {
                "huella_base": _huella_base(),
                "modelo_embeddings": EMBEDDINGS_MODEL,
                "version_indice": VERSION_INDICE,
                "fragmentos": fragmentos,
                "actualizado": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


@lru_cache(maxsize=1)
def obtener_embeddings() -> "EmbeddingsInstitucionales":
    marcar_turno_frio()
    rss_antes = instantanea()["rss_mb"]
    registrar_recursos("pre_carga_embeddings")
    with medir_etapa("carga_embeddings", "embeddings", {"modelo": EMBEDDINGS_MODEL}):
        instancia = EmbeddingsInstitucionales()
    rss_despues = instantanea()["rss_mb"]
    registrar_recursos("post_carga_embeddings", delta_rss_mb=round(rss_despues - rss_antes, 2))
    return instancia


class EmbeddingsInstitucionales(Embeddings):
    def __init__(
        self,
        modelo: str = EMBEDDINGS_MODEL,
        dispositivo: str = EMBEDDINGS_DISPOSITIVO,
    ):
        self.modelo = modelo
        self.dispositivo = dispositivo
        self._prefijos = "e5" in modelo.lower()
        self._cliente = SentenceTransformer(modelo, device=dispositivo)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        entradas = (
            [f"passage: {texto}" for texto in texts] if self._prefijos else list(texts)
        )
        vectores = self._cliente.encode(
            entradas,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )
        return vectores.tolist()

    def embed_query(self, text: str) -> list[float]:
        t0 = time.perf_counter()
        entrada = f"query: {text}" if self._prefijos else text
        vector = self._cliente.encode(
            [entrada],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        duracion_ms = round((time.perf_counter() - t0) * 1000, 2)
        _ULTIMO_EMBED_MS.set(duracion_ms)
        return vector.tolist()


def _abrir_coleccion() -> Chroma:
    return Chroma(
        collection_name=COLECCION_REGLAMENTOS,
        embedding_function=obtener_embeddings(),
        persist_directory=str(VECTOR_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )


def _indice_vigente(cantidad_esperada: int) -> bool:
    meta = _leer_meta()
    if not meta:
        return False
    if meta.get("huella_base") != _huella_base():
        return False
    if meta.get("modelo_embeddings") != EMBEDDINGS_MODEL:
        return False
    if meta.get("version_indice") != VERSION_INDICE:
        return False
    if meta.get("fragmentos") != cantidad_esperada:
        return False
    try:
        return _abrir_coleccion()._collection.count() == cantidad_esperada
    except Exception:
        return False


def construir_indice(forzar: bool = False, verboso: bool = False) -> Chroma:
    documentos = cargar_fragmentos()

    with _CANDADO:
        if not forzar and _indice_vigente(len(documentos)):
            if verboso:
                print(f"Índice vigente: {len(documentos)} fragmentos en {VECTOR_DIR}")
            return _abrir_coleccion()

        marcar_turno_frio()
        with medir_etapa("carga_indice", "embeddings", {"forzar": forzar, "fragmentos": len(documentos)}):
            Path(VECTOR_DIR).mkdir(parents=True, exist_ok=True)
            if verboso:
                print(f"Indexando {len(documentos)} fragmentos con {EMBEDDINGS_MODEL}…")

            coleccion = _abrir_coleccion()
            try:
                coleccion.delete_collection()
            except Exception:
                pass

            coleccion = _abrir_coleccion()
            coleccion.add_documents(
                documents=documentos,
                ids=[documento.metadata["id"] for documento in documentos],
            )
            _guardar_meta(len(documentos))

            if verboso:
                print(f"Índice creado: {coleccion._collection.count()} vectores.")
            return coleccion


@lru_cache(maxsize=1)
def obtener_vectorstore() -> Chroma:
    return construir_indice()


def _puntaje(documento: Document, distancia: float) -> float:
    if distancia is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(distancia)))


def buscar_semantico_detallado(
    consulta: str,
    top_k: int = FRAGMENTOS_POR_DEFECTO,
    umbral: float = UMBRAL_RELEVANCIA,
) -> ResultadoBusqueda:
    consulta_limpia = (consulta or "").strip()
    if not consulta_limpia:
        return ResultadoBusqueda()

    top_k = max(1, min(int(top_k), FRAGMENTOS_MAXIMOS))
    t0 = time.perf_counter()
    vectorstore = obtener_vectorstore()
    pares = vectorstore.similarity_search_with_score(consulta_limpia, k=top_k)
    total_ms = round((time.perf_counter() - t0) * 1000, 2)
    embedding_ms = _ULTIMO_EMBED_MS.get()
    chroma_ms = max(0.0, round(total_ms - embedding_ms, 2))

    candidatos: list[dict] = []
    aceptados: list[Fragmento] = []
    vistos_aceptados: set[str] = set()

    for documento, distancia in pares:
        relevancia = _puntaje(documento, distancia)
        score_redondeado = round(relevancia, 3)
        identificador = str(documento.metadata.get("id", ""))
        seccion = str(documento.metadata.get("seccion", ""))
        titulo = str(documento.metadata.get("titulo", ""))
        numero = str(documento.metadata.get("numero", ""))

        candidatos.append(
            {
                "id": identificador,
                "seccion": seccion,
                "titulo": titulo,
                "numero": numero,
                "score": score_redondeado,
                "sobre_umbral": bool(score_redondeado >= umbral),
            }
        )

        if score_redondeado >= umbral:
            if identificador not in vistos_aceptados:
                vistos_aceptados.add(identificador)
                aceptados.append(
                    Fragmento(
                        id=identificador,
                        seccion=seccion,
                        titulo=titulo,
                        contenido=documento.page_content,
                        relevancia=score_redondeado,
                    )
                )

    aceptados.sort(key=lambda fragmento: fragmento.relevancia, reverse=True)
    if aceptados:
        minimo = max(umbral, aceptados[0].relevancia - MARGEN_RELEVANCIA)
        aceptados = [
            fragmento for fragmento in aceptados if fragmento.relevancia >= minimo
        ]

    top1_score = candidatos[0]["score"] if candidatos else 0.0
    for cand in candidatos:
        if cand["score"] > top1_score:
            top1_score = cand["score"]

    distancia_a_umbral = round(top1_score - umbral, 4)
    decision = "respuesta" if aceptados else "abstencion"
    zona_gris = abs(distancia_a_umbral) <= OBS_ZONA_GRIS

    consulta_masc, _ = enmascarar(consulta_limpia)
    registrar(
        "retrieval",
        {
            "consulta_masc": consulta_masc,
            "top_k": top_k,
            "umbral": umbral,
            "margen": MARGEN_RELEVANCIA,
            "candidatos": candidatos,
            "aceptados": [f.id for f in aceptados],
            "n_aceptados": len(aceptados),
            "top1_score": top1_score,
            "distancia_a_umbral": distancia_a_umbral,
            "decision": decision,
            "zona_gris": zona_gris,
            "embedding_ms": embedding_ms,
            "chroma_ms": chroma_ms,
            "total_ms": total_ms,
        },
    )

    return ResultadoBusqueda(
        candidatos=candidatos,
        aceptados=aceptados,
        top1_score=top1_score,
        distancia_a_umbral=distancia_a_umbral,
        decision=decision,
        zona_gris=zona_gris,
        embedding_ms=embedding_ms,
        chroma_ms=chroma_ms,
        total_ms=total_ms,
    )


def buscar_semantico(
    consulta: str,
    top_k: int = FRAGMENTOS_POR_DEFECTO,
    umbral: float = UMBRAL_RELEVANCIA,
) -> list[Fragmento]:
    return buscar_semantico_detallado(
        consulta, top_k=top_k, umbral=umbral
    ).aceptados


def construir_buscador(top_k: int = FRAGMENTOS_POR_DEFECTO):
    def buscador(consulta: str, limite: int | None = None) -> list[str]:
        fragmentos = buscar_semantico(consulta, limite or top_k)
        return [fragmento.contenido for fragmento in fragmentos]

    return buscador


def informacion_indice() -> dict:
    meta = _leer_meta()
    try:
        cantidad = obtener_vectorstore()._collection.count()
    except Exception:
        cantidad = 0
    return {
        "fragmentos": cantidad,
        "modelo": meta.get("modelo_embeddings", EMBEDDINGS_MODEL),
        "actualizado": meta.get("actualizado", "sin datos"),
        "directorio": str(VECTOR_DIR),
    }
