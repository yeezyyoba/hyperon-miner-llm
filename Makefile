# hyperon-miner-llm — one-command entry points
#   make setup             install pinned PeTTa + Python deps
#   make run               run the (fixed) upstream miner on the sample data
#   make test              Python unit tests (no PeTTa needed)
#   make test-metta        MeTTa tests (needs PeTTa)
#   make reproduce-issues  re-run the evidence behind docs/01-problem.md
#   make profile           measure the conjunction-expansion blow-up

PYTHON ?= python3
PETTA  ?= bash .petta/run.sh
export LANG := C.UTF-8
export LC_ALL := C.UTF-8

.PHONY: help setup run test test-metta test-all reproduce-issues profile clean

help:
	@grep -E '^#   make' Makefile | sed 's/^#   //'

setup:
	./setup.sh

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

clean:
	rm -rf runs/ .cache/ _generated/ .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
