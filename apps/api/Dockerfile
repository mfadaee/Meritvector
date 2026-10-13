# MeritVector API + analytics worker image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY packages ./packages
COPY apps/api ./apps/api
RUN pip install . \
    && useradd --create-home --uid 10001 meritvector \
    && mkdir -p /app/artifacts /app/data/synthetic \
    && chown -R meritvector /app

USER meritvector
ENV MV_DATA_DIR=/app/data/synthetic \
    MV_ARTIFACT_DIR=/app/artifacts/models
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=180s --retries=30 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"
# Bootstrap is idempotent: it loads synthetic data and trains only when the database is empty.
CMD ["sh", "-c", "python -m meritvector_api.cli bootstrap && python -m meritvector_api.cli serve --port 8000"]
