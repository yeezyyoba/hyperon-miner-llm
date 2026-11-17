"""API usage from an execution trace: requests, tokens, cache hits, retries, cost.

Pure functions over trace events (the dicts in ``*.trace.jsonl``), so the dashboard's
usage box can be recomputed after every event and tested without a network.
"""
from __future__ import annotations

from typing import Iterable

# USD per 1M tokens (input, output); the same table the evaluation uses.
from ..evaluate import PRICES


def _empty_provider() -> dict:
    return {"requests": 0, "ok": 0, "failed": 0, "retries": 0, "rate_limit_wait_s": 0.0,
            "batches": 0, "cached": 0, "input_tokens": 0, "output_tokens": 0,
            "latency_s": 0.0, "cost_usd": 0.0, "models": []}


def summarize_usage(events: Iterable[dict]) -> dict:
    """Aggregate LLM usage over the trace events seen so far.

    ``llm_batch`` events arrive as each batch returns (live progress); the ``select``
    event that follows carries the full per-batch records (tokens, attempts), which
    are the authoritative numbers.
    """
    providers: dict[str, dict] = {}
    answered = 0
    total_batches = 0
    fallback = 0
    llm_seconds = 0.0
    for e in events:
        ev = e.get("event")
        if ev == "llm_batch":
            answered += 1
            total_batches = max(total_batches, int(e.get("of") or 0))
        elif ev == "select":
            llm_seconds += float(e.get("llm_seconds") or 0.0)
            for rec in e.get("batches") or []:
                for a in rec.get("attempts") or []:
                    p = providers.setdefault(a.get("provider") or "unknown", _empty_provider())
                    p["requests"] += 1
                    if a.get("ok"):
                        p["ok"] += 1
                    else:
                        p["failed"] += 1
                    if (a.get("attempt") or 1) > 1:
                        p["retries"] += 1
                    p["rate_limit_wait_s"] += float(a.get("waited_s") or 0.0)
                if rec.get("fallback"):
                    fallback += 1
                name = rec.get("provider")
                if not name:
                    continue
                p = providers.setdefault(name, _empty_provider())
                p["batches"] += 1
                if rec.get("model") and rec["model"] not in p["models"]:
                    p["models"].append(rec["model"])
                tin, tout = int(rec.get("input_tokens") or 0), int(rec.get("output_tokens") or 0)
                p["input_tokens"] += tin
                p["output_tokens"] += tout
                p["latency_s"] += float(rec.get("latency_s") or 0.0)
                if rec.get("cached"):
                    p["cached"] += 1            # answered from the disk cache: no request, no cost
                elif name in PRICES:
                    pin, pout = PRICES[name]
                    p["cost_usd"] += tin / 1e6 * pin + tout / 1e6 * pout
        elif ev == "finish":
            total_batches = max(total_batches, int(e.get("batches") or 0))
            fallback = max(fallback, int(e.get("fallback_batches") or 0))
            llm_seconds = max(llm_seconds, float(e.get("llm_seconds") or 0.0))

    for p in providers.values():
        p["rate_limit_wait_s"] = round(p["rate_limit_wait_s"], 2)
        p["latency_s"] = round(p["latency_s"], 2)
        p["cost_usd"] = round(p["cost_usd"], 6)
    totals = {k: sum(p[k] for p in providers.values())
              for k in ("requests", "failed", "retries", "cached", "input_tokens", "output_tokens")}
    totals["cost_usd"] = round(sum(p["cost_usd"] for p in providers.values()), 6)
    totals["rate_limit_wait_s"] = round(sum(p["rate_limit_wait_s"] for p in providers.values()), 2)
    return {
        "providers": providers,
        "totals": totals,
        "batches_answered": answered,
        "batches_total": total_batches,
        "fallback_batches": fallback,
        "llm_seconds": round(llm_seconds, 2),
    }


def add_usage(a: dict, b: dict) -> dict:
    """Sum two usage summaries (for the session total across runs)."""
    out = {"providers": {}, "totals": {}, "batches_answered": 0, "batches_total": 0,
           "fallback_batches": 0, "llm_seconds": 0.0}
    for src in (a, b):
        for name, p in (src.get("providers") or {}).items():
            q = out["providers"].setdefault(name, _empty_provider())
            for k, v in p.items():
                if k == "models":
                    q["models"] += [m for m in v if m not in q["models"]]
                else:
                    q[k] = round(q[k] + v, 6)
        for k, v in (src.get("totals") or {}).items():
            out["totals"][k] = round(out["totals"].get(k, 0) + v, 6)
        for k in ("batches_answered", "batches_total", "fallback_batches", "llm_seconds"):
            out[k] = round(out[k] + (src.get(k) or 0), 2)
    return out
