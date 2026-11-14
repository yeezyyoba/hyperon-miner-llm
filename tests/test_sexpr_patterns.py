"""S-expression parsing and pattern canonicalisation."""
from __future__ import annotations

import pytest

from minerllm.patterns import (canonical, clauses, n_clauses, predicates, same_pattern,
                               shared_variables)
from minerllm.sexpr import Str, Var, dumps, parse, parse_all, variables


def test_parse_roundtrip_nested_with_vars_numbers_strings():
    text = '(supportOf (, (Inheritance $_0 (And A B)) (Inheritance $_0 $_1)) 35 0.5 "hi there")'
    atom = parse(text)
    assert atom[0] == "supportOf"
    assert atom[2] == 35 and atom[3] == 0.5 and atom[4] == Str("hi there")
    assert dumps(atom) == text


def test_parse_all_skips_comments_and_blank_lines():
    atoms = parse_all(";; header\n(A x)\n\n; c\n(B y) ; trailing\n")
    assert atoms == [("A", "x"), ("B", "y")]


@pytest.mark.parametrize("bad", ["(a b", "a b)", "((a)"])
def test_unbalanced_input_raises(bad):
    with pytest.raises(ValueError):
        parse_all(bad)


def test_variables_first_occurrence_order():
    assert variables(parse("(, (R $b $a) (S $a $c))")) == [Var("b"), Var("a"), Var("c")]


def test_canonical_ignores_variable_names():
    assert same_pattern("(, (R $x $y) (S $y $z))", "(, (R $_9 $_1) (S $_1 $q))")


def test_canonical_ignores_clause_order():
    # the exact duplicate pair the upstream miner prints (docs/01-problem.md, Issue 4)
    a = "(, (Inheritance $_0 $_1) (Inheritance $_0 man))"
    b = "(, (Inheritance $_0 man) (Inheritance $_0 $_1))"
    assert canonical(a) == canonical(b)


def test_canonical_keeps_different_joins_apart():
    chain = "(, (R $x $y) (R $y $z))"     # x->y->z
    fork = "(, (R $x $y) (R $x $z))"      # x->y, x->z
    star = "(, (R $x $y) (R $z $y))"      # x->y<-z
    assert len({canonical(chain), canonical(fork), canonical(star)}) == 3


def test_canonical_keeps_constants():
    assert not same_pattern("(, (R $x a) (S $x $y))", "(, (R $x b) (S $x $y))")


def test_clause_helpers():
    p = "(, (HAS_STEP $w $s) (STEP_USES_TOOL $s $t))"
    assert n_clauses(p) == 2
    assert predicates(p) == ["HAS_STEP", "STEP_USES_TOOL"]
    assert shared_variables(p) == [Var("s")]
    assert clauses(parse("(R $x)")) == (("R", Var("x")),)
