import logging
from pathlib import Path
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from medlink.config import settings
from medlink.db import get_session
from medlink.embeddings import Embedder, get_embedder
from medlink.models import Chunk, Dataset
from medlink.retrieval import IndexNotReady, structured_search, vector_search
from medlink.schemas import SearchResponse, StructuredRequest, VectorRequest

app = FastAPI(
    title="MedLink AI",
    version="0.1.0",
    docs_url=None,
    description=(
        "Synthetic HIS retrieval demo. All times require a timezone. "
        "Read-only search; no clinical decisions or arbitrary SQL execution."
    ),
)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)
logger = logging.getLogger("uvicorn.error")


@app.get("/docs", include_in_schema=False)
def docs():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
        swagger_favicon_url="data:,",
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(_request: Request, _error: SQLAlchemyError):
    return JSONResponse(
        status_code=503, content={"detail": "Database unavailable; check readiness"}
    )


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(session: Session = Depends(get_session)):
    try:
        session.execute(text("SELECT 1"))
        dataset = session.scalar(select(Dataset))
        chunks = session.scalar(select(func.count()).select_from(Chunk))
        if not dataset or not chunks or dataset.embedding_key != settings().embedding_key:
            raise HTTPException(503, "Dataset/index not ready; run seed")
    except SQLAlchemyError as error:
        raise HTTPException(503, "Database unavailable or schema not initialized") from error
    return {
        "status": "ready",
        "dataset": dataset.id,
        "chunks": chunks,
        "embedding_model": dataset.embedding_key,
    }


def respond(mode, request, hits, start, model=None):
    elapsed = round((perf_counter() - start) * 1000, 2)
    # Do not log query text, patient identifiers, or note contents.
    logger.info("retrieval mode=%s count=%s elapsed_ms=%s", mode, len(hits), elapsed)
    return SearchResponse(
        mode=mode,
        as_of=request.as_of,
        hits=hits,
        count=len(hits),
        elapsed_ms=elapsed,
        embedding_model=model,
    )


@app.post("/search/structured", response_model=SearchResponse)
def structured(request: StructuredRequest, session: Session = Depends(get_session)):
    start = perf_counter()
    return respond("structured", request, structured_search(session, request), start)


def embedding_dependency() -> Embedder:
    try:
        return get_embedder()
    except (ImportError, OSError, ValueError) as error:
        raise HTTPException(503, "Embedding model unavailable; check installation/cache") from error


def semantic(mode, request, session, embedder):
    start = perf_counter()
    try:
        hits = vector_search(session, request, embedder, hybrid=mode == "hybrid")
    except IndexNotReady as error:
        raise HTTPException(503, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return respond(mode, request, hits, start, embedder.key)


@app.post("/search/vector", response_model=SearchResponse)
def vector(
    request: VectorRequest,
    session: Session = Depends(get_session),
    embedder: Embedder = Depends(embedding_dependency),
):
    return semantic("vector", request, session, embedder)


@app.post("/search/hybrid", response_model=SearchResponse)
def hybrid(
    request: VectorRequest,
    session: Session = Depends(get_session),
    embedder: Embedder = Depends(embedding_dependency),
):
    return semantic("hybrid", request, session, embedder)
