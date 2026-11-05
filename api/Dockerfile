FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    UV_NO_CACHE=1
RUN pip install --no-cache-dir uv==0.11.32 \
    && useradd --system --uid 10001 --create-home condoos \
    && mkdir /app && chown condoos /app
WORKDIR /app
USER condoos

# The worker image installs Docling (OCR, tables) and bakes its models in; the API image
# does not need it. Files are copied already owned by the app user (no chown layer).
ARG INSTALL_DOCLING=false
COPY --chown=condoos pyproject.toml uv.lock ./
RUN if [ "$INSTALL_DOCLING" = "true" ]; then \
      uv sync --frozen --no-dev --no-install-project --extra docling; \
    else \
      uv sync --frozen --no-dev --no-install-project; \
    fi

COPY --chown=condoos alembic.ini docker-entrypoint.sh ./
COPY --chown=condoos app ./app
RUN if [ "$INSTALL_DOCLING" = "true" ]; then \
      uv sync --frozen --no-dev --extra docling; \
    else \
      uv sync --frozen --no-dev; \
    fi
ENV PATH="/app/.venv/bin:$PATH" HF_HOME=/app/.cache/huggingface \
    EMBEDDING_CACHE_DIR=/app/.cache/fastembed
# Local embedding model for the chat's document search (no text leaves the infrastructure).
RUN python -m app.chat.warmup
RUN if [ "$INSTALL_DOCLING" = "true" ]; then python -m app.extraction.warmup; fi
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["api"]
