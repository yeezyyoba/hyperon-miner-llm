"""Integration: harness drives the real MeTTa miner; the oracle independently agrees."""
from __future__ import annotations

import pytest

from minerllm.config import MinerConfig
from minerllm.datagen import UniversitySpec, write_dataset
from minerllm.datasets import UPSTREAM_DATA
from minerllm.harness import run_upstream

UGLY = str(UPSTREAM_DATA / "ugly_man_sodaDrinker")


@pytest.mark.petta
@pytest.mark.parametrize("depth,distinct", [(0, 11), (1, 16)])
def test_upstream_supports_match_oracle(tmp_path, depth, distinct):
    run, ver = run_upstream(MinerConfig(dataset=UGLY, minsup=10, depth=depth, surp_mode="none"),
                            tmp_path)
    assert run.ok
    assert len(run.patterns) == distinct           # printed 12 / 20, minus clause-order duplicates
    assert ver.checked == distinct and ver.ok, ver.mismatches


@pytest.mark.petta
def test_surprisingness_run_gets_supports_from_oracle(tmp_path):
    run, ver = run_upstream(MinerConfig(dataset=UGLY, minsup=10, depth=0, surp_mode="isurp"),
                            tmp_path)
    assert run.ok and len(run.patterns) == 11
    assert all(p.surprisingness is not None and p.support >= 10 for p in run.patterns)


@pytest.mark.petta
def test_synthetic_graph_mines_and_verifies(tmp_path):
    data = write_dataset(UniversitySpec(students=30, seed=5), tmp_path)
    run, ver = run_upstream(MinerConfig(dataset=str(data), minsup=8, depth=0, surp_mode="none"),
                            tmp_path)
    assert run.ok and run.patterns
    assert ver.ok, ver.mismatches
