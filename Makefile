.PHONY: up down demo seed migrate fmt lint test api-test workflow-test web-test web-build

up:
	docker compose -f infra/compose/docker-compose.yml up -d --build

down:
	docker compose -f infra/compose/docker-compose.yml down -v

migrate:
	cd apps/api && alembic upgrade head

seed:
	python scripts/seed_demo.py

demo: down up migrate seed
	@echo "open http://localhost:3000"

test: api-test workflow-test web-test

api-test:
	cd apps/api && python -m pytest

workflow-test:
	cd apps/workflow && python -m pytest

web-test:
	cd apps/web && npm run typecheck

web-build:
	cd apps/web && npm run build

fmt:
	cd apps/api && python -m ruff format .

lint:
	cd apps/api && python -m ruff check .
