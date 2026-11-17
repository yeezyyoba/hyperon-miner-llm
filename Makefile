# hyperon-miner-llm — one-command entry points
#   make setup             install pinned PeTTa + Python deps
#   make doctor            check the toolchain (swipl, janus, Python, PeTTa, keys)
#   make run               run the (fixed) upstream miner on the sample data
#   make test              Python unit tests (no PeTTa needed)
#   make test-metta        MeTTa tests (needs PeTTa)
#   make reproduce-issues  re-run the evidence behind docs/01-problem.md
#   make profile           measure the conjunction-expansion blow-up
#   make datasets          regenerate experiments/data (synthetic + Galaxy subset)
#   make mine CONFIG=...   run the upstream miner from a YAML config, verify with the oracle
#   make eval-baselines    Step 5: upstream, exhaustive, random x5, heuristic on all datasets
#   make eval-llm          Step 6: LLM arms per provider (needs .env keys; resumable)
#   make report            regenerate results/, figures and the tables in docs/05, docs/06
#   make demo              5-minute live demo (DEMO_PAUSE=0 to run without pauses)
#   make ui                build the dashboard and serve it at http://127.0.0.1:8000
#   make api               API only, auto-reload (pair with make ui-dev for UI work)
#   make ui-dev            Vite dev server on :5173, proxies /api to make api

PYTHON ?= python3
PETTA  ?= bash .petta/run.sh
export LANG := C.UTF-8
export LC_ALL := C.UTF-8

.PHONY: help setup doctor run test test-metta test-all reproduce-issues profile datasets mine eval-baselines eval-llm report demo ui ui-build ui-dev api clean

help:
	@grep -E '^#   make' Makefile | sed 's/^#   //'

setup:
	./setup.sh

doctor:
	bash scripts/doctor.sh

run:
	$(PETTA) run_miner.metta

test:
	$(PYTHON) -m pytest -q -m "not petta"

test-metta:
	$(PYTHON) scripts/run_metta_tests.py

test-all: test test-metta
	$(PYTHON) -m pytest -q -m petta

reproduce-issues:
	bash scripts/reproduce_issues.sh

profile:
	$(PYTHON) scripts/profile_baseline.py --sizes 200 400 600 800 --depths 0 1
	$(PYTHON) scripts/profile_baseline.py --sizes 200 --depths 2 --timeout 1800 --append

CONFIG ?= configs/sample.yaml

datasets:
	$(PYTHON) -m minerllm datagen --seed 0 --strength 0.8
	$(PYTHON) -m minerllm datagen --seed 0 --strength 0.8 --anonymize
	$(PYTHON) -m minerllm datagen --seed 0 --strength 0.0
	$(PYTHON) -m minerllm galaxy 400

mine:
	$(PYTHON) -m minerllm mine --config $(CONFIG)

eval-baselines:
	$(PYTHON) -m minerllm eval baselines

eval-llm:
	$(PYTHON) -m minerllm eval llm

report:
	$(PYTHON) -m minerllm eval report

demo:
	bash scripts/demo.sh

UI_HOST ?= 127.0.0.1
UI_PORT ?= 8000

ui/node_modules: ui/package.json
	cd ui && npm install --no-audit --no-fund
	@touch ui/node_modules

ui-build: ui/node_modules
	cd ui && npm run build

ui: ui-build
	@echo "Dashboard: http://$(UI_HOST):$(UI_PORT)"
	$(PYTHON) -m uvicorn minerllm.api.app:app --host $(UI_HOST) --port $(UI_PORT)

api:
	$(PYTHON) -m uvicorn minerllm.api.app:app --host $(UI_HOST) --port $(UI_PORT) --reload --reload-dir minerllm

ui-dev: ui/node_modules
	cd ui && npm run dev

clean:
	rm -rf runs/ .cache/ _generated/ .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
