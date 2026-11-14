"""The independent support counter must agree with upstream's definition of support."""
from __future__ import annotations

import pytest

from minerllm.datasets import UPSTREAM_DATA, load_atoms
from minerllm.oracle import Oracle
from minerllm.sexpr import parse_all


@pytest.fixture(scope="module")
def ugly():
    return Oracle(load_atoms(UPSTREAM_DATA / "ugly_man_sodaDrinker"))


# Expected values copied from upstream's experiments/pattern-miner/tests/test-pattern-miner.metta
@pytest.mark.parametrize("pattern,expected", [
    ("(, (Inheritance $v sodaDrinker) (Inheritance $v human))", 10),
    ("(, (Inheritance $v sodaDrinker) (Inheritance $v $a))", 35),
    ("(, (Inheritance $v $a) (Inheritance $v $b))", 190),
    ("(, (Inheritance $v $a) (Inheritance $w $a))", 800),
    ("(, (Inheritance $v sodaDrinker) (Inheritance $v human) (Inheritance $v $a))", 35),
    ("(, (Inheritance $v $a) (Inheritance $w $a) (Inheritance $u $a))", 12000),
    ("(, (Inheritance $v $a) (Inheritance $v $b) (Inheritance $v $c))", 630),
])
def test_matches_upstream_expected_supports(ugly, pattern, expected):
    assert ugly.support(pattern) == expected


def test_variables_may_share_values_and_duplicates_count():
    o = Oracle(parse_all("(R a b) (R a b) (R b c)"))
    assert o.support("(R $x $y)") == 3                      # duplicate atom counts twice
    assert o.support("(, (R $x $y) (R $x $z))") == 5        # 2*2 for x=a, 1 for x=b
    assert o.support("(, (R $x $y) (R $y $z))") == 2        # a->b->c, twice


def test_nested_terms_unify_structurally():
    o = Oracle(parse_all("(Inheritance (And A B) C) (Inheritance (And A D) C)"))
    assert o.support("(Inheritance (And A $x) C)") == 2
    assert o.support("(Inheritance (And $x $x) C)") == 0


def test_large_counts_stay_fast():
    atoms = [("R", f"n{i}", "hub") for i in range(300)]
    # 300^4 = 8.1e9 raw solutions, counted via memoisation instead of enumeration
    assert Oracle(atoms).support("(, (R $a $h) (R $b $h) (R $c $h) (R $d $h))") == 300 ** 4
