"""Independent support counter — the reference the MeTTa miner is checked against.

Upstream defines support as the number of solutions returned by
``(collapse (match $db <conjunction> <conjunction>))``
(``counter`` / ``sup-num`` in common-utils.metta). Concretely:

* every clause must unify with some atom of the database,
* shared variables must take the same value in every clause,
* *different* variables **may** take the same value (no injectivity), and
* duplicate atoms in the database count as separate solutions.

This module re-implements exactly that in plain Python, with no MeTTa involved.
Agreement between the two implementations is our evidence that the symbolic
side of the pipeline is correct (see tests/test_oracle*.py).

Counting uses memoised backtracking: after choosing clause *i*, only the
variables that later clauses still need are kept in the memo key. Patterns
whose raw solution count is in the millions therefore stay fast.
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from typing import Iterable

from .patterns import clauses
from .sexpr import Atom, Var, parse, variables


def _unify(pattern: Atom, fact: Atom, binding: dict) -> dict | None:
    """Match a pattern (may contain Vars) against a ground fact."""
    if isinstance(pattern, Var):
        if pattern in binding:
            return binding if binding[pattern] == fact else None
        new = dict(binding)
        new[pattern] = fact
        return new
    if isinstance(pattern, tuple):
        if not isinstance(fact, tuple) or len(pattern) != len(fact):
            return None
        for p, f in zip(pattern, fact):
            binding = _unify(p, f, binding)
            if binding is None:
                return None
        return binding
    return binding if pattern == fact else None


class Oracle:
    """Support counting over a fixed list of ground atoms."""

    def __init__(self, atoms: Iterable[Atom]):
        self.atoms = [a for a in atoms if isinstance(a, tuple) and a]
        # index: (head, arity) -> list of facts
        self._by_shape: dict[tuple, list[Atom]] = defaultdict(list)
        for a in self.atoms:
            self._by_shape[(a[0], len(a))].append(a)

    def __len__(self) -> int:
        return len(self.atoms)

    def _candidates(self, clause: Atom) -> list[Atom]:
        if isinstance(clause, tuple) and clause and not isinstance(clause[0], Var):
            return self._by_shape.get((clause[0], len(clause)), [])
        return self.atoms  # head is a variable: anything may match

    def support(self, pattern: Atom | str) -> int:
        """Number of solutions of ``pattern`` (a clause or a ``,`` conjunction)."""
        p = parse(pattern) if isinstance(pattern, str) else pattern
        cls = list(clauses(p))
        # put selective clauses first: fewer candidate facts first
        cls.sort(key=lambda c: len(self._candidates(c)))
        later_vars = []
        for i in range(len(cls)):
            rest = set()
            for c in cls[i + 1:]:
                rest.update(variables(c))
            later_vars.append(rest)

        @lru_cache(maxsize=None)
        def count(i: int, key: tuple) -> int:
            if i == len(cls):
                return 1
            binding = dict(key)
            total = 0
            for fact in self._candidates(cls[i]):
                b = _unify(cls[i], fact, binding)
                if b is None:
                    continue
                nxt = tuple(sorted(((v, val) for v, val in b.items() if v in later_vars[i]),
                                   key=lambda kv: kv[0].name))
                total += count(i + 1, nxt)
            return total

        return count(0, ())

    def frequency(self, pattern: Atom | str) -> float:
        """support / |db| — the 'empirical probability' used by the surprisingness code."""
        return self.support(pattern) / max(1, len(self.atoms))
