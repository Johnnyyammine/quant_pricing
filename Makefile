.PHONY: help install dev serve test test-py test-web e2e bench lint fmt typecheck openapi check

help:  ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install:  ## Install Python and web dependencies
	uv sync
	cd web && npm ci

dev:  ## Hot-reload API + Vite dev server, opens browser
	uv run python scripts/launch.py dev

serve:  ## Build if stale, single-process app, opens browser
	uv run python scripts/launch.py serve

test: test-py test-web  ## Python and web unit tests

test-py:
	uv run pytest

test-web:
	cd web && npm test

e2e:  ## Playwright smoke tests against the built app
	cd web && npm run build && npx playwright test

bench:  ## Performance benchmarks
	uv run pytest -m perf

lint:  ## Linters and format checks
	uv run ruff check .
	uv run ruff format --check .
	cd web && npm run lint && npm run format:check

fmt:  ## Auto-format everything
	uv run ruff check --fix .
	uv run ruff format .
	cd web && npm run format

typecheck:  ## mypy (strict on engine) and tsc
	uv run mypy engine api
	cd web && npm run typecheck

openapi:  ## Regenerate api/openapi.json and web/src/api/schema.d.ts
	uv run python scripts/dump_openapi.py
	cd web && npm run gen:api

check: lint typecheck test  ## Everything CI runs except e2e
