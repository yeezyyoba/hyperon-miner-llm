"""What the dashboard can show: datasets, providers, recorded runs, results, run outputs.

Everything is read from files the CLI and ``make report`` already write.
API keys are only ever checked for presence; their values never leave this module.
"""
from __future__ import annotations

import csv
import json
import os
from functools import lru_cache
from pathlib import Path

from ..config import ROOT, MinerConfig
from ..evaluate import DATASETS, PRICES, tie_aware_top
from ..patterns import canonical

RESULTS = ROOT / "results"
RAW = RESULTS / "raw"

DATASET_INFO = {
    "university": ("University graph",
                   "Synthetic students, professors, courses and departments with 3 planted patterns."),
    "university-anon": ("University graph, names hidden",
                        "The same graph with relation and entity names replaced by R1, e1, ..."),
    "galaxy400": ("Galaxy sample",
                  "400 atoms sampled from the upstream Galaxy dataset. No planted patterns."),
}

STRATEGIES = {
    "llm": "LLM ranks schema joins",
    "llm-direct": "LLM scores every candidate",
    "cardinality": "Cardinality baseline",
    "heuristic": "Heuristic baseline",
    "random": "Random order",
    "exhaustive": "Exhaustive (100 %)",
}

PROVIDER_KEYS = {"groq": "GROQ_API_KEY", "nvidia": "NVIDIA_API_KEY", "gemini": "GEMINI_API_KEY"}


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


def config_for(dataset_id: str) -> MinerConfig:
    if dataset_id not in DATASETS:
        raise KeyError(dataset_id)
    return MinerConfig.from_yaml(ROOT / DATASETS[dataset_id])


def planted_for(cfg: MinerConfig) -> dict[str, str]:
    """name -> canonical pattern, for synthetic datasets with a truth file."""
    truth = cfg.dataset_path().with_suffix(".truth.json")
    if not truth.exists():
        return {}
    return {name: canonical(p) for name, p in json.loads(truth.read_text())["planted"].items()}


def list_datasets() -> list[dict]:
    out = []
    for ds in DATASETS:
        cfg = config_for(ds)
        title, blurb = DATASET_INFO.get(ds, (ds, ""))
        path = cfg.dataset_path()
        atoms = sum(1 for l in path.read_text().splitlines() if l.strip().startswith("(")) \
            if path.exists() else None
        out.append({"id": ds, "title": title, "description": blurb, "atoms": atoms,
                    "minsup": cfg.minsup, "conjuncts": cfg.conjuncts,
                    "planted": [{"name": n, "pattern": p} for n, p in planted_for(cfg).items()]})
    return out


def provider_status() -> dict:
    """Which providers have a key configured (true/false only), their model and price."""
    _load_env()
    from ..llm.providers import DEFAULT_MODELS
    order = [p.strip() for p in os.environ.get("MINERLLM_PROVIDERS", "groq,nvidia,gemini").split(",")
             if p.strip() in PROVIDER_KEYS]
    providers = []
    for name in order + [p for p in PROVIDER_KEYS if p not in order]:
        pin, pout = PRICES.get(name, (None, None))
        providers.append({"name": name, "configured": bool(os.environ.get(PROVIDER_KEYS[name])),
                          "model": os.environ.get(f"{name.upper()}_MODEL", DEFAULT_MODELS[name]),
                          "price_in": pin, "price_out": pout})
    return {"order": order, "providers": providers}


# --------------------------------------------------------------------------- recorded runs


@lru_cache(maxsize=1024)
def _record_meta(path: str, mtime: float) -> dict:
    rec = json.loads(Path(path).read_text())
    ranker = rec.get("ranker") or {}
    arm = rec.get("arm") or {}
    return {"n_patterns": rec.get("n_patterns"), "seconds": rec.get("seconds"),
            "strategy": ranker.get("strategy") or arm.get("strategy"),
            "budget": ranker.get("budget", arm.get("budget")),
            "providers": ranker.get("providers") or [], "family": arm.get("family")}


def list_replays() -> list[dict]:
    """Recorded runs that have both a trace and a result, LLM runs first."""
    out = []
    if not RAW.exists():
        return out
    for ds_dir in sorted(p for p in RAW.iterdir() if p.is_dir()):
        for trace in sorted(ds_dir.glob("*.trace.jsonl")):
            label = trace.name[: -len(".trace.jsonl")]
            rec = ds_dir / f"{label}.json"
            if not rec.exists():
                continue
            meta = _record_meta(str(rec), rec.stat().st_mtime)
            if not meta["strategy"]:
                continue
            out.append({"id": f"{ds_dir.name}/{label}", "dataset": ds_dir.name, "label": label, **meta})
    rank = {"llm": 0, "llm-direct": 1, "cardinality": 2, "heuristic": 3, "random": 4, "exhaustive": 5}
    out.sort(key=lambda r: (r["dataset"] != "university", r["dataset"],
                            rank.get(r["strategy"], 9), r["budget"] or 0, r["label"]))
    return out


def replay_paths(replay_id: str) -> tuple[str, Path, Path]:
    """(dataset, trace, record) for a replay id like ``university/llm-groq-b30``."""
    ds, _, label = replay_id.partition("/")
    if ds not in DATASETS or not label or "/" in label or label.startswith("."):
        raise KeyError(replay_id)
    trace, rec = RAW / ds / f"{label}.trace.jsonl", RAW / ds / f"{label}.json"
    if not (trace.exists() and rec.exists()):
        raise KeyError(replay_id)
    return ds, trace, rec


# --------------------------------------------------------------------------- run output


def _reference_tops(dataset_id: str, k: int = 10) -> set[str]:
    ref = RAW / dataset_id / "reference.json"
    if not ref.exists():
        return set()
    pats = json.loads(ref.read_text())["patterns"]
    return tie_aware_top({p: v["score"] for p, v in pats.items() if v["score"] is not None}, k)


def _safe_canonical(pattern: str) -> str:
    try:
        return canonical(pattern)
    except ValueError:                  # too many clauses to canonicalise: compare as printed
        return pattern


def build_result(record_path: Path, dataset_id: str, limit: int = 500) -> dict:
    """The patterns a run found, ranked by surprisingness, with what they mean for the
    evaluation: planted pattern recovered? in the reference top 10?"""
    rec = json.loads(Path(record_path).read_text())
    planted = {p: n for n, p in planted_for(config_for(dataset_id)).items()}
    top10 = _reference_tops(dataset_id)
    pats = sorted(rec.get("patterns") or [],
                  key=lambda p: (-(p.get("surprisingness") or 0), -(p.get("support") or 0)))
    rows = []
    for i, p in enumerate(pats[:limit]):
        canon = _safe_canonical(p["pattern"]) if planted else p["pattern"]
        rows.append({"rank": i + 1, "pattern": p["pattern"], "support": p.get("support"),
                     "surprisingness": p.get("surprisingness"),
                     "planted": planted.get(canon), "top10": p["pattern"] in top10})
    found = {p["pattern"] for p in pats}
    found_canon = {_safe_canonical(p) for p in found} if planted else set()
    ts = rec.get("trace_summary") or {}
    return {
        "patterns": rows,
        "n_patterns": rec.get("n_patterns", len(pats)),
        "seconds": rec.get("seconds"),
        "oracle_ok": (rec.get("verification") or {}).get("ok"),
        "oracle_checked": (rec.get("verification") or {}).get("checked"),
        "planted_found": sorted(n for p, n in planted.items() if p in found_canon),
        "planted_total": len(planted),
        "recall_at_10": round(len(found & top10) / len(top10), 4) if top10 else None,
        "generated": ts.get("generated"), "unique": ts.get("unique"),
        "verified": ts.get("selected"), "kept": ts.get("kept"),
    }


# --------------------------------------------------------------------------- evaluation results


def _num(v: str):
    if v in ("", None):
        return None
    if v in ("True", "False"):
        return v == "True"
    try:
        return float(v)
    except ValueError:
        return v


def results_summary() -> dict:
    summary_csv, verdicts = RESULTS / "summary.csv", RESULTS / "verdicts.json"
    rows = []
    if summary_csv.exists():
        with summary_csv.open() as fh:
            rows = [{k: _num(v) if k not in ("dataset", "family") else v for k, v in r.items()}
                    for r in csv.DictReader(fh)]
    return {"rows": rows,
            "verdicts": json.loads(verdicts.read_text()) if verdicts.exists() else None}
