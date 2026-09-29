FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml requirements.lock requirements-embeddings.lock ./
COPY src ./src
COPY data ./data
RUN pip install -r requirements.lock && pip install --no-deps .

FROM base AS test
COPY tests ./tests
CMD ["pytest", "-v", "-m", "not semantic"]

FROM base AS app
RUN pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements-embeddings.lock
RUN useradd --create-home appuser && mkdir -p /models /app/reports \
    && chown -R appuser:appuser /models /app/reports
ENV HF_HOME=/models
USER appuser
EXPOSE 8000
CMD ["uvicorn", "medlink.api:app", "--host", "0.0.0.0", "--port", "8000"]
