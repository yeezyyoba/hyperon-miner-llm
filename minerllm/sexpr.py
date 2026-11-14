"""Minimal S-expression reader/printer for the MeTTa atoms the miner emits.

Representation
    Symbol / number / string -> ``str`` | ``int`` | ``float`` | ``Str``
    Variable ``$x``          -> ``Var("x")``
    Expression ``(a b c)``   -> ``tuple``

Tuples are hashable, so parsed patterns can live in sets and dict keys. That's
what the canonicaliser and the oracle need.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator, Union


@dataclass(frozen=True, order=True)
class Var:
    name: str

    def __str__(self) -> str:
        return f"${self.name}"


class Str(str):
    """A MeTTa string literal (kept distinct from symbols when printing)."""


Atom = Union[str, int, float, Var, Str, tuple]

_TOKEN = re.compile(r'\s*(?:(;[^\n]*)|(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()";]+))')


def tokenize(text: str) -> Iterator[str]:
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            if text[pos:].strip():
                raise ValueError(f"cannot tokenize at {pos}: {text[pos:pos + 30]!r}")
            return
        pos = m.end()
        comment, lp, rp, string, word = m.groups()
        if comment:
            continue
        yield lp or rp or string or word


def _atom(tok: str) -> Atom:
    if tok.startswith('"'):
        return Str(bytes(tok[1:-1], "utf-8").decode("unicode_escape"))
    if tok.startswith("$") and len(tok) > 1:
        return Var(tok[1:])
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        return tok


def parse_all(text: str) -> list[Atom]:
    """Parse every top-level expression in ``text`` (comments ignored)."""
    stack: list[list] = [[]]
    for tok in tokenize(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            if len(stack) == 1:
                raise ValueError("unbalanced ')'")
            done = tuple(stack.pop())
            stack[-1].append(done)
        else:
            stack[-1].append(_atom(tok))
    if len(stack) != 1:
        raise ValueError("unbalanced '('")
    return stack[0]


def parse(text: str) -> Atom:
    """Parse exactly one expression."""
    atoms = parse_all(text)
    if len(atoms) != 1:
        raise ValueError(f"expected one expression, got {len(atoms)}")
    return atoms[0]


def dumps(atom: Atom) -> str:
    """Print an atom back as MeTTa text (inverse of :func:`parse`)."""
    if isinstance(atom, tuple):
        return "(" + " ".join(dumps(a) for a in atom) + ")"
    if isinstance(atom, Var):
        return str(atom)
    if isinstance(atom, Str):
        return '"' + atom.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(atom, float):
        return repr(atom)
    return str(atom)


def variables(atom: Atom) -> list[Var]:
    """Variables in first-occurrence (depth-first, left-to-right) order, unique."""
    seen: dict[Var, None] = {}

    def walk(a: Atom) -> None:
        if isinstance(a, Var):
            seen.setdefault(a, None)
        elif isinstance(a, tuple):
            for x in a:
                walk(x)

    walk(atom)
    return list(seen)


def substitute(atom: Atom, mapping: dict) -> Atom:
    if isinstance(atom, Var):
        return mapping.get(atom, atom)
    if isinstance(atom, tuple):
        return tuple(substitute(a, mapping) for a in atom)
    return atom
