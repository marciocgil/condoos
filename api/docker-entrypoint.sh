#!/bin/sh
set -e

case "$1" in
  api)
    # Migrations and (in development) the fictitious seed run before the API starts.
    alembic upgrade head
    if [ "${SEED_ON_START:-false}" = "true" ]; then
      python -m app.seed
    fi
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
    ;;
  worker)
    exec python -m app.worker
    ;;
  *)
    exec "$@"
    ;;
esac
