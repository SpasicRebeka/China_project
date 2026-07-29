PYTHON ?= python3
PNPM ?= pnpm

.PHONY: install dev-api dev-doctor dev-patient build start kiosk test test-e2e check contracts

install:
	$(PNPM) install --frozen-lockfile
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install -r services/api/requirements.lock
	.venv/bin/python -m pip install -e services/api --no-deps

dev-api:
	.venv/bin/python -m uvicorn app.main:app --app-dir services/api --host 127.0.0.1 --port 8000 --reload

dev-doctor:
	$(PNPM) dev:doctor

dev-patient:
	$(PNPM) dev:patient

build:
	$(PNPM) build

start:
	.venv/bin/python -m uvicorn app.main:app --app-dir services/api --host 127.0.0.1 --port 8000

kiosk:
	bash ops/kiosk/start-kiosk.sh

test:
	$(PNPM) test
	.venv/bin/python -m pytest services/api/tests

test-e2e:
	$(PNPM) test:e2e

check:
	$(PNPM) lint
	$(PNPM) typecheck
	.venv/bin/python -m ruff check services/api
	.venv/bin/python -m mypy services/api/app

contracts:
	.venv/bin/python services/api/scripts/export_contracts.py
	$(PNPM) contracts:generate
