# CondoOS — common commands. Run `make help`.
.DEFAULT_GOAL := help
API := cd api &&
WEB := cd web &&

help: ## List commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

up: ## Build and start the whole stack (api, worker, web, postgres, s3, mailpit)
	docker compose up -d --build --wait

down: ## Stop the stack
	docker compose down

reset: ## Stop the stack and delete its data volumes
	docker compose down -v

logs: ## Follow logs
	docker compose logs -f api worker web

install: ## Install backend and frontend dependencies locally
	$(API) uv sync --extra docling
	$(WEB) npm ci

test: ## Backend tests (needs a local PostgreSQL 16 + pgvector; see README)
	$(API) uv run pytest

coverage: ## Tests with coverage; fails if rules, matching or extraction < 80%
	$(API) uv run pytest --cov=app --cov-report=json:coverage.json -q && uv run python scripts/coverage_gate.py

test-slow: ## Backend tests including the slow ones (chat evaluation, real LLM)
	$(API) uv run pytest -m slow

e2e: ## Playwright tests against the running stack
	docker compose exec -T postgres psql -U postgres condoos -qc \
	  "UPDATE magic_link_token SET created_at = created_at - interval '2 hours'"
	$(WEB) npx playwright test

lint: ## Linters, formatters and type checks (backend + frontend)
	$(API) uv run ruff check app tests corpus scripts && uv run black --check app tests corpus scripts && uv run mypy app tests corpus scripts
	$(WEB) npm run lint && npm run typecheck && npm run format:check

format: ## Auto-format
	$(API) uv run ruff check --fix app tests corpus && uv run black app tests corpus
	$(WEB) npm run format

corpus: ## Regenerate the fictitious 30-document corpus (deterministic)
	$(API) uv run python -m corpus.generate

accuracy: ## Per-field extraction accuracy over the corpus (writes docs/extraction_accuracy.md)
	$(API) uv run python -m corpus.accuracy --out ../docs/extraction_accuracy.md

chat-eval: ## Live chat evaluation (needs ANTHROPIC_API_KEY; writes docs/chat_eval.md)
	$(API) uv run pytest -m slow tests/chat_eval -q

migrate: ## Apply migrations to the database in DATABASE_ADMIN_URL
	$(API) uv run alembic upgrade head

seed: ## Load the fictitious seed into the database in DATABASE_ADMIN_URL
	$(API) uv run python -m app.seed

.PHONY: help up down reset logs install test coverage test-slow e2e lint format corpus accuracy chat-eval migrate seed
