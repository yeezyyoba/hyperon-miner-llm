"""Canonical form for conjunctive patterns.

The miner prints a pattern like ``(, (Inheritance $_0 human) (Inheritance $_0 $_1))``.
The *same* pattern can come out with different variable names (``$_627562``) or a
different clause order, for example from two runs, or from the upstream miner versus
our guided miner. To compare result sets we need one canonical spelling:

1. try every clause order (patterns have ≤ 5 clauses, so ≤ 120 orders),
2. rename variables to ``$v0, $v1, …`` in first-occurrence order,
3. keep the lexicographically smallest printed form.

Two patterns are alpha-equivalent up to clause reordering iff their canonical
forms are equal.
"""
from __future__ import annotations

from functools import lru_cache
from itertools import permutations

from .sexpr import Atom, Var, dumps, parse, substitute, variables

CONJ = ","


def clauses(pattern: Atom) -> tuple:
    """Clauses of a conjunction; a bare clause is a one-clause conjunction."""
    if isinstance(pattern, tuple) and pattern and pattern[0] == CONJ:
        return tuple(pattern[1:])
    return (pattern,)


def make_conjunction(cls) -> tuple:
    return (CONJ, *cls)


def rename_vars(pattern: Atom) -> Atom:
    mapping = {v: Var(f"v{i}") for i, v in enumerate(variables(pattern))}
    return substitute(pattern, mapping)


@lru_cache(maxsize=65536)
def _canonical_text(text: str) -> str:
    pattern = parse(text)
    cls = clauses(pattern)
    if len(cls) > 6:
        raise ValueError(f"pattern with {len(cls)} clauses is too large to canonicalise")
    best = None
    for order in permutations(cls):
        candidate = dumps(rename_vars(make_conjunction(order)))
        if best is None or candidate < best:
            best = candidate
    return best


def canonical(pattern: Atom | str) -> str:
    """Canonical printed form of ``pattern`` (an atom or MeTTa text)."""
    text = pattern if isinstance(pattern, str) else dumps(pattern)
    return _canonical_text(text)


def same_pattern(a: Atom | str, b: Atom | str) -> bool:
    return canonical(a) == canonical(b)


def n_clauses(pattern: Atom | str) -> int:
    p = parse(pattern) if isinstance(pattern, str) else pattern
    return len(clauses(p))


def predicates(pattern: Atom | str) -> list[str]:
    """Head symbol of each clause, e.g. ``['HAS_STEP', 'STEP_USES_TOOL']``."""
    p = parse(pattern) if isinstance(pattern, str) else pattern
    return [c[0] if isinstance(c, tuple) and c else str(c) for c in clauses(p)]


def shared_variables(pattern: Atom | str) -> list[Var]:
    """Variables that appear in more than one clause (the join variables)."""
    p = parse(pattern) if isinstance(pattern, str) else pattern
    count: dict[Var, int] = {}
    for c in clauses(p):
        for v in variables(c):
            count[v] = count.get(v, 0) + 1
    return [v for v, k in count.items() if k > 1]
