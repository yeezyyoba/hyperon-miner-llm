"""Candidate rankers: the only place an LLM touches the mining process.

A ranker receives the *unchecked* candidate conjunctions of one expansion level
and returns an **order**. The guided miner then counts support for the first
``budget`` fraction of that order, in MeTTa. So the LLM boundary is:

    LLM may:     reorder candidates it was given (via 0–10 scores)
    LLM cannot:  add a pattern, change a support, skip verification, see data atoms

Strategies (same interface, so the evaluation compares like with like):

    exhaustive  identity order (with budget 1.0, reproduces the upstream miner)
    random      seeded shuffle (the "no information" baseline)
    heuristic   schema-only structural score (the "cheap, no LLM" baseline)
    cardinality schema-statistics baseline: estimated support under independence, most
                likely frequent first (the strong "cheap, no LLM" baseline)
    llm         the LLM scores JOINS between relation arguments (schema-level, a few
                calls per dataset, cached); candidates are scored from their joins
    llm-direct  the LLM scores every candidate pattern (many calls; kept to compare
                cost vs. quality against `llm`)

LLM answers are validated. Ties and invalid batches fall back to the cardinality order.
"""
from __future__ import annotations

import json
import math
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .datasets import DatasetStats
from .patterns import predicates, shared_variables
from .sexpr import parse, variables

# --------------------------------------------------------------------------- types


@dataclass
class Candidate:
    idx: int             # position in the unique-candidate list
    pattern: str         # canonical text


@dataclass
class RankResult:
    order: list[int]                       # unique-candidate indices, best first
    strategy: str
    batches: list[dict] = field(default_factory=list)
    llm_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def fallback_batches(self) -> int:
        return sum(1 for b in self.batches if b.get("fallback"))


# ----------------------------------------------------------------------- heuristic


def heuristic_score(pattern: str) -> float:
    """Schema-free structural prior. Prefer joins across *different* relations;
    penalise variables that appear in only one clause (they make a pattern generic).
    """
    p = parse(pattern)
    n_rel = len(set(predicates(p)))
    shared = set(shared_variables(p))
    all_vars = variables(p)
    free = sum(1 for v in all_vars if v not in shared)
    return 2.0 * n_rel - 1.0 * free - 0.25 * len(all_vars)


def heuristic_order(cands: list[Candidate]) -> list[int]:
    return [c.idx for c in sorted(cands, key=lambda c: (-heuristic_score(c.pattern), c.pattern))]


def estimated_support(pattern: str, stats: DatasetStats) -> float:
    """Expected support if every relation were independent (textbook join-size estimate).

    Uses only the schema statistics an LLM is also shown: atoms per relation and distinct
    values per argument. Each clause contributes its relation's size; each extra
    occurrence of a join variable divides by the largest distinct count among its slots;
    each constant divides by its slot's distinct count.
    """
    from .patterns import clauses
    est = 1.0
    slots_of: dict = {}
    for c in clauses(parse(pattern)):
        if not isinstance(c, tuple) or not c:
            continue
        head = str(c[0])
        est *= max(1, stats.relations.get(head, 1))
        distinct = stats.distinct_args.get(head, [])
        for pos, arg in enumerate(c[1:]):
            d = distinct[pos] if pos < len(distinct) else 1
            vs = variables(arg)
            if not vs:
                est /= max(1, d)                    # constant: one of d values
            for v in vs:
                slots_of.setdefault(v, []).append(d)
    for ds in slots_of.values():
        for _ in range(len(ds) - 1):
            est /= max(1, max(ds))
    return est


def cardinality_order(cands: list[Candidate], stats: DatasetStats | None) -> list[int]:
    """Most-likely-frequent first; falls back to the structural heuristic without stats."""
    if stats is None:
        return heuristic_order(cands)
    return [c.idx for c in sorted(cands, key=lambda c: (-estimated_support(c.pattern, stats),
                                                         -heuristic_score(c.pattern), c.pattern))]


# ---------------------------------------------------------------------- validator

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.M)


@dataclass
class Validation:
    scores: dict[int, float]
    issues: list[str]
    coverage: float

    @property
    def accepted(self) -> bool:
        return self.coverage >= 0.5 and not any(i.startswith("fatal:") for i in self.issues)


def validate_scores(text: str, valid_ids: set[int]) -> Validation:
    """Parse and check an LLM answer. Never trusts the model:

    * must be JSON with a ``scores`` list of {id, score} objects (code fences tolerated),
    * ids must be integers from ``valid_ids``; others are dropped (the LLM cannot invent),
    * duplicate ids keep their first score, scores are clamped to [0, 10],
    * the batch is *accepted* only if ≥ 50 % of the ids got a valid score.
    """
    issues: list[str] = []
    try:
        data = json.loads(_FENCE.sub("", text.strip()))
    except (json.JSONDecodeError, TypeError):
        return Validation({}, ["fatal: not valid JSON"], 0.0)
    items = data.get("scores") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return Validation({}, ["fatal: missing 'scores' list"], 0.0)
    scores: dict[int, float] = {}
    for it in items:
        if not isinstance(it, dict):
            issues.append("non-object entry dropped")
            continue
        try:
            i, s = int(it.get("id")), float(it.get("score"))
        except (TypeError, ValueError):
            issues.append("entry without numeric id/score dropped")
            continue
        if i not in valid_ids:
            issues.append(f"unknown id {i} dropped")
            continue
        if i in scores:
            issues.append(f"duplicate id {i} ignored")
            continue
        if not 0 <= s <= 10:
            issues.append(f"score {s} for id {i} clamped")
            s = min(10.0, max(0.0, s))
        if math.isnan(s):
            issues.append(f"NaN score for id {i} dropped")
            continue
        scores[i] = s
    coverage = len(scores) / max(1, len(valid_ids))
    if coverage < 1:
        issues.append(f"{len(valid_ids) - len(scores)} id(s) unscored")
    return Validation(scores, issues, coverage)


# ------------------------------------------------------------------------- prompt

SYSTEM_PROMPT = (
    "You help a symbolic pattern miner decide which candidate patterns to evaluate first. "
    "You see only the dataset's schema, never its facts. You do not decide whether a "
    "pattern holds: the miner counts the real support of every pattern it evaluates. "
    "Answer with JSON only."
)

USER_TEMPLATE = """\
## Dataset schema
{schema}

## Pattern syntax
`(, C1 C2 C3)` is a conjunction of clauses. `$v0, $v1, ...` are variables. A variable that
appears in two clauses is a JOIN: both clauses must refer to the same entity. A constant
in a clause restricts it to that value.

## Task
The miner will rank patterns by SURPRISINGNESS: how much more often the clauses occur
together than they would if each clause were independent. Surprising patterns usually
reflect a real dependency between the joined relations.

Score EVERY candidate from 0 (almost certainly unsurprising) to 10 (very likely
surprising). Low scores for: joins between unrelated relations, variables used in only
one clause, and joins that are trivially implied by how the data is structured.

Return exactly: {{"scores": [{{"id": <int>, "score": <0-10>}}, ...]}} with every id once.

## Candidates
{candidates}
"""


def build_prompt(cands: list[Candidate], local_ids: list[int], schema: str) -> str:
    lines = "\n".join(f"[{lid}] {c.pattern}" for lid, c in zip(local_ids, cands))
    return USER_TEMPLATE.format(schema=schema, candidates=lines)


# ------------------------------------------------------------------- join level

Slot = tuple  # (relation, argument position starting at 1)


def _slot_vars(clause) -> list[tuple[int, object]]:
    """(position, variable) pairs of a clause; a variable nested inside an argument
    counts for that top-level argument position."""
    out = []
    if not isinstance(clause, tuple):
        return out
    for pos, arg in enumerate(clause[1:], start=1):
        for v in variables(arg):
            out.append((pos, v))
    return out


def join_key(a: Slot, b: Slot) -> tuple:
    return tuple(sorted([a, b]))


def pattern_joins(pattern: str) -> list[tuple]:
    """Join edges of a conjunction: every pair of argument slots, in different
    clauses, that share a variable. E.g. (, (ADVISED_BY $s $p) (MEMBER_OF $p $d))
    -> [(('ADVISED_BY', 2), ('MEMBER_OF', 1))]."""
    from .patterns import clauses
    occ: dict = {}
    for ci, c in enumerate(clauses(parse(pattern))):
        head = c[0] if isinstance(c, tuple) and c else str(c)
        for pos, v in _slot_vars(c):
            occ.setdefault(v, []).append((ci, (str(head), pos)))
    edges = []
    for uses in occ.values():
        for i in range(len(uses)):
            for j in range(i + 1, len(uses)):
                if uses[i][0] != uses[j][0]:
                    edges.append(join_key(uses[i][1], uses[j][1]))
    return edges


def schema_joins(stats: DatasetStats) -> list[tuple]:
    """Every possible join between two argument slots of the schema (incl. same relation)."""
    slots = sorted((r, i) for r, ar in stats.arity.items() for i in range(1, ar + 1))
    return [join_key(slots[i], slots[j]) for i in range(len(slots)) for j in range(i, len(slots))]


def _fmt_join(j: tuple) -> str:
    (r1, p1), (r2, p2) = j
    return f"{r1}.arg{p1} = {r2}.arg{p2}"


JOIN_TEMPLATE = """\
## Dataset schema
{schema}

## What a join means
`R.argI = S.argJ` means: the entity in argument I of an R-fact is the SAME entity as the one
in argument J of an S-fact. Patterns are built by chaining such joins, for example
`ADVISED_BY.arg2 = MEMBER_OF.arg1` reads "the advisor is the member".

## Task
A symbolic miner will look for SURPRISING patterns: combinations of facts that co-occur much
more often than if the relations were independent. Score EVERY join from 0 to 10 for how
likely patterns built on it are to be surprising:
  0-2  the two slots hold different kinds of entities (type mismatch), or the link is meaningless
  3-5  type-compatible but no expected dependency
  6-10 type-compatible AND a real-world dependency is plausible
The same relation may be joined with itself.

Return exactly: {{"scores": [{{"id": <int>, "score": <0-10>}}, ...]}} with every id once.

## Joins
{joins}
"""


# ------------------------------------------------------------------ batch runner


def _ask(client, prompt: str, ids: set, timeout_s: float):
    """One validated LLM call. Returns (response or None, error or None, seconds)."""
    from .llm import LLMError
    start = time.time()
    try:
        try:
            resp = client.complete(prompt, SYSTEM_PROMPT, timeout_s,
                                   validate=lambda t: validate_scores(t, ids).accepted)
        except TypeError:                       # plain client without a validate hook
            resp = client.complete(prompt, SYSTEM_PROMPT, timeout_s)
        return resp, None, time.time() - start
    except LLMError as e:
        return None, e, time.time() - start


def run_batches(client, prompts: list[tuple[str, set]], timeout_s: float, workers: int,
                on_batch=None) -> list[tuple]:
    """Send all batch prompts, ``workers`` at a time. Order of results = order of prompts."""
    def job(i_p):
        i, (prompt, ids) = i_p
        out = _ask(client, prompt, ids, timeout_s)
        if on_batch:
            resp, err, secs = out
            on_batch(i, len(prompts), resp, err, secs)
        return out
    if workers <= 1 or len(prompts) <= 1:
        return [job(x) for x in enumerate(prompts)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(job, enumerate(prompts)))


def _record(level, kind, size, resp, err, secs, ids) -> tuple[dict, "Validation | None"]:
    record: dict = {"level": level, "kind": kind, "size": size}
    if err is not None:
        record.update(fallback=True, reason=f"llm unavailable: {err}"[:200],
                      attempts=getattr(err, "attempts", []), latency_s=round(secs, 3))
        return record, None
    v = validate_scores(resp.text, ids)
    record.update(provider=resp.provider, model=resp.model, cached=resp.cached,
                  input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
                  latency_s=round(resp.latency_s, 3), coverage=round(v.coverage, 3),
                  issues=v.issues[:10], attempts=resp.attempts)
    if not v.accepted:
        record.update(fallback=True, reason="validation failed")
    return record, v


# ------------------------------------------------------------------------ rankers


class Ranker:
    strategy = "base"

    def rank(self, cands: list[Candidate], stats: DatasetStats | None = None,
             level: int = 0) -> RankResult:
        raise NotImplementedError


class ExhaustiveRanker(Ranker):
    strategy = "exhaustive"

    def rank(self, cands, stats=None, level=0):
        return RankResult([c.idx for c in cands], self.strategy)


class RandomRanker(Ranker):
    strategy = "random"

    def __init__(self, seed: int = 0):
        self.seed = seed

    def rank(self, cands, stats=None, level=0):
        order = [c.idx for c in sorted(cands, key=lambda c: c.pattern)]
        random.Random(f"{self.seed}:{level}").shuffle(order)
        return RankResult(order, self.strategy)


class HeuristicRanker(Ranker):
    strategy = "heuristic"

    def rank(self, cands, stats=None, level=0):
        return RankResult(heuristic_order(cands), self.strategy)


class CardinalityRanker(Ranker):
    """Schema-statistics baseline: verify the candidates most likely to be frequent first."""

    strategy = "cardinality"

    def rank(self, cands, stats=None, level=0):
        return RankResult(cardinality_order(cands, stats), self.strategy)


class LLMRanker(Ranker):
    """llm-direct: scores every candidate in batches with an LLM client (usually a FallbackChain)."""

    strategy = "llm-direct"

    def __init__(self, client, batch_size: int = 60, timeout_s: float = 180.0, workers: int = 4,
                 on_batch=None):
        self.client = client
        self.batch_size = batch_size
        self.timeout_s = timeout_s
        self.workers = workers
        self.on_batch = on_batch

    def rank(self, cands, stats=None, level=0):
        schema = stats.describe() if stats else "(schema unavailable)"
        ordered = sorted(cands, key=lambda c: c.pattern)    # stable prompts -> cache hits
        batches = [ordered[b:b + self.batch_size] for b in range(0, len(ordered), self.batch_size)]
        prompts = [(build_prompt(bt, list(range(len(bt))), schema), set(range(len(bt))))
                   for bt in batches]
        t0 = time.time()
        outs = run_batches(self.client, prompts, self.timeout_s, self.workers, self.on_batch)
        result = RankResult([], self.strategy, llm_seconds=time.time() - t0)
        llm_score: dict[int, float] = {}
        for bt, (prompt, ids), (resp, err, secs) in zip(batches, prompts, outs):
            record, v = _record(level, "candidates", len(bt), resp, err, secs, ids)
            if resp is not None:
                result.input_tokens += resp.input_tokens
                result.output_tokens += resp.output_tokens
            if v is not None and v.accepted:
                for lid, sc in v.scores.items():
                    llm_score[bt[lid].idx] = sc
            result.batches.append(record)

        # scored candidates first (by LLM score), then unscored ones; ties and unscored
        # candidates follow the cardinality baseline (so failures degrade to it)
        base = {idx: r for r, idx in enumerate(cardinality_order(cands, stats))}

        def key(c: Candidate):
            sc = llm_score.get(c.idx)
            return (0 if sc is not None else 1, -(sc or 0), base[c.idx])

        result.order = [c.idx for c in sorted(cands, key=key)]
        return result


class LLMJoinRanker(Ranker):
    """llm: the LLM scores schema joins once (cached for every level); candidates are
    scored deterministically as the mean score of their joins."""

    strategy = "llm"

    def __init__(self, client, batch_size: int = 60, timeout_s: float = 180.0, workers: int = 4,
                 on_batch=None):
        self.client = client
        self.batch_size = batch_size
        self.timeout_s = timeout_s
        self.workers = workers
        self.on_batch = on_batch
        self.join_scores: dict[tuple, float] | None = None

    def _score_joins(self, stats: DatasetStats, result: RankResult) -> None:
        joins = schema_joins(stats)
        schema = stats.describe()
        batches = [joins[b:b + self.batch_size] for b in range(0, len(joins), self.batch_size)]
        prompts = [(JOIN_TEMPLATE.format(schema=schema, joins="\n".join(
                        f"[{i}] {_fmt_join(j)}" for i, j in enumerate(bt))), set(range(len(bt))))
                   for bt in batches]
        t0 = time.time()
        outs = run_batches(self.client, prompts, self.timeout_s, self.workers, self.on_batch)
        result.llm_seconds += time.time() - t0          # wall time, batches run in parallel
        scores: dict[tuple, float] = {}
        for bt, (prompt, ids), (resp, err, secs) in zip(batches, prompts, outs):
            record, v = _record(0, "joins", len(bt), resp, err, secs, ids)
            if resp is not None:
                result.input_tokens += resp.input_tokens
                result.output_tokens += resp.output_tokens
            if v is not None and v.accepted:
                scores.update({bt[i]: sc for i, sc in v.scores.items()})
            result.batches.append(record)
        self.join_scores = scores
        self.top_joins = sorted(scores.items(), key=lambda kv: -kv[1])[:15]

    def candidate_score(self, pattern: str) -> float | None:
        edges = pattern_joins(pattern)
        known = [self.join_scores[e] for e in edges if e in (self.join_scores or {})]
        if not edges or not known:
            return None
        return sum(known) / len(known)

    def rank(self, cands, stats=None, level=0):
        result = RankResult([], self.strategy)
        if self.join_scores is None:
            if stats is None:
                raise ValueError("join-level ranking needs dataset statistics")
            self._score_joins(stats, result)          # first level only; reused afterwards
        scored = {c.idx: self.candidate_score(c.pattern) for c in cands}
        base = {idx: r for r, idx in enumerate(cardinality_order(cands, stats))}

        # LLM join score first; ties (common: many candidates share a mean) and unscored
        # candidates follow the cardinality baseline, so the LLM's effect is measured on top of it
        def key(c: Candidate):
            s = scored[c.idx]
            return (0 if s is not None else 1, -(s or 0), base[c.idx])

        result.order = [c.idx for c in sorted(cands, key=key)]
        return result


def interleave(first: list[int], second: list[int]) -> list[int]:
    """Alternate two rankings (first, second, first, ...), skipping items already taken.

    With a budget of k, each ranking contributes about k/2 of its best picks.
    """
    out, seen = [], set()
    i = j = 0
    take_first = True
    while i < len(first) or j < len(second):
        if (take_first and i < len(first)) or j >= len(second):
            x, i = first[i], i + 1
        else:
            x, j = second[j], j + 1
        if x in seen:                      # already taken from the other list: same turn
            continue
        seen.add(x)
        out.append(x)
        take_first = not take_first
    return out


SAMPLE_NOTE = "\n(Independent rating {k} of {n}: judge every join afresh.)\n"


class LLMHybridRanker(LLMJoinRanker):
    """llm-hybrid (exploratory, not pre-registered; docs/07-exploratory.md).

    Motivated by the Step 6 traces: the join ranker keeps as many frequent patterns as
    cardinality but *different* ones. Cardinality finds the high-support structural
    patterns and misses the planted ones; the LLM dismisses same-relation joins and
    sometimes finds planted ones. So the two orders are merged, half of the budget each:

    * cardinality order (most-likely-frequent first), interleaved with
    * the LLM join order, where each join's score is the mean of ``samples`` independent
      ratings (the first uses the exact ``llm`` prompt, so cached answers are reused).

    If every LLM call fails, the LLM order is the cardinality order, so the merge is the
    cardinality baseline: the failure path is unchanged.
    """

    strategy = "llm-hybrid"

    def __init__(self, client, samples: int = 3, **kw):
        super().__init__(client, **kw)
        self.samples = max(1, int(samples))

    def _score_joins(self, stats: DatasetStats, result: RankResult) -> None:
        joins = schema_joins(stats)
        schema = stats.describe()
        batches = [joins[b:b + self.batch_size] for b in range(0, len(joins), self.batch_size)]
        prompts, owners = [], []
        for k in range(self.samples):
            for bt in batches:
                text = JOIN_TEMPLATE.format(schema=schema, joins="\n".join(
                    f"[{i}] {_fmt_join(j)}" for i, j in enumerate(bt)))
                if k:
                    text += SAMPLE_NOTE.format(k=k + 1, n=self.samples)
                prompts.append((text, set(range(len(bt)))))
                owners.append(bt)
        t0 = time.time()
        outs = run_batches(self.client, prompts, self.timeout_s, self.workers, self.on_batch)
        result.llm_seconds += time.time() - t0
        sums: dict[tuple, float] = {}
        counts: dict[tuple, int] = {}
        for bt, (prompt, ids), (resp, err, secs) in zip(owners, prompts, outs):
            record, v = _record(0, "joins", len(bt), resp, err, secs, ids)
            if resp is not None:
                result.input_tokens += resp.input_tokens
                result.output_tokens += resp.output_tokens
            if v is not None and v.accepted:
                for i, sc in v.scores.items():
                    sums[bt[i]] = sums.get(bt[i], 0.0) + sc
                    counts[bt[i]] = counts.get(bt[i], 0) + 1
            result.batches.append(record)
        self.join_scores = {j: sums[j] / counts[j] for j in sums}
        self.top_joins = sorted(self.join_scores.items(), key=lambda kv: -kv[1])[:15]

    def rank(self, cands, stats=None, level=0):
        llm = super().rank(cands, stats, level)        # LLM join order, cardinality ties
        result = RankResult(interleave(cardinality_order(cands, stats), llm.order), self.strategy,
                            batches=llm.batches, llm_seconds=llm.llm_seconds,
                            input_tokens=llm.input_tokens, output_tokens=llm.output_tokens)
        return result


def make_ranker(strategy: str, seed: int = 0, client=None, batch_size: int = 60,
                timeout_s: float = 180.0, workers: int = 4, on_batch=None,
                samples: int = 3) -> Ranker:
    if strategy == "exhaustive":
        return ExhaustiveRanker()
    if strategy == "random":
        return RandomRanker(seed)
    if strategy == "heuristic":
        return HeuristicRanker()
    if strategy == "cardinality":
        return CardinalityRanker()
    if strategy == "llm-hybrid":
        if client is None:
            raise ValueError(f"{strategy} strategy needs an LLM client")
        return LLMHybridRanker(client, samples=samples, batch_size=batch_size,
                               timeout_s=timeout_s, workers=workers, on_batch=on_batch)
    if strategy in ("llm", "llm-direct"):
        if client is None:
            raise ValueError(f"{strategy} strategy needs an LLM client")
        cls = LLMJoinRanker if strategy == "llm" else LLMRanker
        return cls(client, batch_size=batch_size, timeout_s=timeout_s, workers=workers,
                   on_batch=on_batch)
    raise ValueError(f"unknown strategy {strategy!r}")
