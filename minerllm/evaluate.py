"""Evaluation: run every method on every dataset, then compute metrics and the report.

Design (docs/02-hypothesis.md):

* **Same tasks, data, miner configuration** for every method: each dataset has one
  YAML config (minsup, depth, scorer) used unchanged by every arm.
* **Reference:** ``reference.json`` (minerllm/reference.py): the complete frequent set
  (exhaustive, budget 100 %, equal to upstream's frequent output) with every pattern's
  ``isurp`` score computed by upstream's own code in an isolated space, so the
  add-atom-nodup collision (Issue 7) can't drop any. Its ranking defines the top-K
  patterns each budgeted method should recover.
* **Arms:** upstream (time only), exhaustive, random × 5 seeds, heuristic, llm per
  provider (each provider alone, so their answers can be compared), llm-direct (cost
  comparison), at budgets 10 / 20 / 30 / 50 %.
* **Resumable:** each arm writes ``results/raw/<dataset>/<arm>.json``; existing
  successful results are skipped, so ``make eval-llm`` can be re-run after a failure.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import ROOT, MinerConfig, RankerConfig
from .patterns import canonical

RESULTS = ROOT / "results"
RAW = RESULTS / "raw"
FIGURES = RESULTS / "figures"

DATASETS = {
    "university": "configs/university.yaml",
    "university-anon": "configs/university-anon.yaml",
    "galaxy400": "configs/galaxy400.yaml",
}
BUDGETS = [0.1, 0.2, 0.3, 0.5]
SEEDS = [0, 1, 2, 3, 4]
PROVIDERS = ["groq", "nvidia", "gemini"]
K_VALUES = [10, 25]

# USD per 1M tokens (input, output). Sources in docs/06-results.md.
PRICES = {
    "gemini": (0.75, 3.75),     # gemini-3.8-flash, introductory price until 2026-12-31
    "groq": (0.15, 0.60),       # openai/gpt-oss-120b on GroqCloud
    "nvidia": (0.0, 0.0),       # build.nvidia.com hosted endpoints: free developer credits
}


# --------------------------------------------------------------------------- arms


@dataclass
class Arm:
    name: str
    strategy: str
    budget: float = 1.0
    seed: int = 0
    provider: str | None = None          # single provider for llm arms
    only: tuple = ()                     # restrict to these datasets (empty = all)

    def ranker(self) -> RankerConfig:
        # Groq's on-demand tier allows 8,000 tokens/minute: send its batches one at a time
        # and allow more retries (each waits as long as Groq asks).
        groq = self.provider == "groq"
        return RankerConfig(strategy=self.strategy, budget=self.budget, seed=self.seed,
                            providers=[self.provider] if self.provider else None,
                            max_retries=4 if groq else 2, workers=1 if groq else 4)

    @property
    def family(self) -> str:
        """Group for plotting: random / heuristic / llm:groq / llm-direct:groq / exhaustive."""
        return f"{self.strategy}:{self.provider}" if self.provider else self.strategy


def pct(b: float) -> str:
    return f"b{int(round(b * 100))}"


def baseline_arms(budgets=BUDGETS, seeds=SEEDS) -> list[Arm]:
    arms = [Arm("exhaustive-b100", "exhaustive", 1.0)]
    for b in budgets:
        arms.append(Arm(f"heuristic-{pct(b)}", "heuristic", b))
        arms.append(Arm(f"cardinality-{pct(b)}", "cardinality", b))
        arms += [Arm(f"random-{pct(b)}-s{s}", "random", b, seed=s) for s in seeds]
    return arms


def llm_arms(providers=PROVIDERS, budgets=BUDGETS, direct: bool = True,
             direct_provider: str = "nvidia") -> list[Arm]:
    """Join-level LLM arms per provider; plus one llm-direct arm (every candidate scored),
    on the university graph only. It needs ~150 calls per run, which a rate-limited tier
    (Groq: 8,000 tokens/min) can't serve, so it runs on NVIDIA by default."""
    arms = [Arm(f"llm-{p}-{pct(b)}", "llm", b, provider=p) for p in providers for b in budgets]
    if direct and direct_provider in providers:
        arms.append(Arm(f"llm-direct-{direct_provider}-b30", "llm-direct", 0.3,
                        provider=direct_provider, only=("university",)))
    return arms


# --------------------------------------------------------------------------- running


def _done(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return bool(json.loads(path.read_text()).get("ok"))
    except json.JSONDecodeError:
        return False


def run_matrix(datasets: list[str], arms: list[Arm], upstream: bool = False,
               force: bool = False, log=print) -> None:
    from .harness import run_guided, run_upstream
    for ds in datasets:
        cfg = MinerConfig.from_yaml(ROOT / DATASETS[ds])
        out = RAW / ds
        out.mkdir(parents=True, exist_ok=True)
        if upstream and (force or not (out / "reference.json").exists()):
            from .reference import build_reference
            log(f"[{ds}] building reference (frequent set + isolated isurp scores)")
            build_reference(cfg, out, log=lambda m: log(f"[{ds}] {m}"))
        if upstream and (force or not _done(out / "upstream.json")):
            t = time.time()
            run, ver = run_upstream(cfg, out, label="upstream")
            log(f"[{ds}] upstream: {len(run.patterns)} patterns, {run.seconds:.1f}s, "
                f"oracle {'ok' if ver.ok else 'MISMATCH'}  ({time.time() - t:.0f}s)")
        for arm in arms:
            if arm.only and ds not in arm.only:
                continue
            if not force and _done(out / f"{arm.name}.json"):
                log(f"[{ds}] {arm.name}: cached result, skipped")
                continue
            t = time.time()
            run, ver, s = run_guided(cfg, arm.ranker(), out, label=arm.name)
            meta = json.loads((out / f"{arm.name}.json").read_text())
            meta["arm"] = {**arm.__dict__, "only": list(arm.only), "family": arm.family}
            (out / f"{arm.name}.json").write_text(json.dumps(meta, indent=2))
            log(f"[{ds}] {arm.name}: {len(run.patterns)} patterns, verified {s.get('selected')}"
                f"/{s.get('unique')}, {run.seconds:.1f}s, LLM fallbacks "
                f"{s.get('fallback_batches', 0)}/{s.get('batches', 0)}, "
                f"oracle {'ok' if ver.ok else 'MISMATCH'}  ({time.time() - t:.0f}s)")


# --------------------------------------------------------------------------- metrics


def tie_aware_top(scores: dict[str, float], k: int) -> set[str]:
    """Patterns whose score is >= the k-th best score (ties at the cut-off are included)."""
    if not scores:
        return set()
    ranked = sorted(scores.values(), reverse=True)
    cut = ranked[min(k, len(ranked)) - 1]
    return {p for p, s in scores.items() if s >= cut - 1e-12}


def _providers_used(trace: Path) -> dict[str, int]:
    used: dict[str, int] = {}
    if not trace.exists():
        return used
    for line in trace.read_text().splitlines():
        e = json.loads(line)
        if e.get("event") == "select":
            for b in e.get("batches", []):
                key = b.get("provider") or "fallback"
                used[key] = used.get(key, 0) + 1
    return used


def _cost(tokens_in: int, tokens_out: int, provider: str | None) -> float | None:
    if not provider or provider not in PRICES:
        return None
    pin, pout = PRICES[provider]
    return tokens_in / 1e6 * pin + tokens_out / 1e6 * pout


def metrics_for(ds: str) -> list[dict]:
    out = RAW / ds
    ref_path = out / "reference.json"
    if not ref_path.exists():
        return []
    ref = json.loads(ref_path.read_text())["patterns"]
    ref_scores = {p: v["score"] for p, v in ref.items() if v["score"] is not None}
    frequent = set(ref)
    tops = {k: tie_aware_top(ref_scores, k) for k in K_VALUES}
    cfg = MinerConfig.from_yaml(ROOT / DATASETS[ds])
    truth_path = cfg.dataset_path().with_suffix(".truth.json")
    planted = ({canonical(p) for p in json.loads(truth_path.read_text())["planted"].values()}
               if truth_path.exists() else set())
    rows = []
    for f in sorted(out.glob("*.json")):
        rec = json.loads(f.read_text())
        if "config" not in rec or f.stem in ("frequent-b100", "reference"):
            continue
        label = f.stem
        found = {p["pattern"] for p in rec["patterns"]}
        arm = rec.get("arm") or {"name": label, "strategy": "upstream" if label == "upstream"
                                 else label.split("-")[0], "budget": 1.0,
                                 "family": "upstream" if label == "upstream" else label}
        ts = rec.get("trace_summary") or {}
        row = {
            "dataset": ds, "arm": label, "family": arm.get("family", arm.get("strategy")),
            "strategy": arm.get("strategy"), "provider": arm.get("provider"),
            "budget": arm.get("budget", 1.0), "seed": arm.get("seed", 0),
            "ok": rec["ok"], "oracle_ok": (rec.get("verification") or {}).get("ok"),
            "patterns": rec["n_patterns"], "seconds": rec["seconds"],
            "llm_seconds": ts.get("llm_seconds", 0.0),
            "miner_seconds": round(rec["seconds"] - ts.get("llm_seconds", 0.0), 3),
            "generated": ts.get("generated"), "unique": ts.get("unique"),
            "verified": ts.get("selected"), "tokens_in": ts.get("input_tokens", 0),
            "tokens_out": ts.get("output_tokens", 0), "batches": ts.get("batches", 0),
            "fallback_batches": ts.get("fallback_batches", 0),
            "providers_used": json.dumps(_providers_used(out / f"{label}.trace.jsonl")),
            "precision_ok": found <= frequent,
            "scores_match_reference": all(
                abs(ref_scores.get(p["pattern"], -1) - p["surprisingness"]) < 1e-9
                for p in rec["patterns"] if p.get("surprisingness") is not None),
            "scored": sum(1 for p in rec["patterns"] if p.get("surprisingness") is not None),
        }
        for k in K_VALUES:
            row[f"recall@{k}"] = round(len(found & tops[k]) / len(tops[k]), 4) if tops[k] else None
            row[f"relevant@{k}"] = len(tops[k])
        row["planted_found"] = len(found & planted) if planted else None
        row["planted_total"] = len(planted) if planted else None
        cost = _cost(row["tokens_in"], row["tokens_out"], row["provider"])
        row["cost_usd"] = round(cost, 6) if cost is not None else None
        rows.append(row)
    return rows


def collect() -> list[dict]:
    rows = []
    for ds in DATASETS:
        rows += metrics_for(ds)
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


# --------------------------------------------------------------------------- summaries


def _mean_sd(vals: list[float]) -> tuple[float, float]:
    vals = [v for v in vals if v is not None]
    if not vals:
        return (math.nan, math.nan)
    return (statistics.mean(vals), statistics.pstdev(vals) if len(vals) > 1 else 0.0)


def summarize(rows: list[dict]) -> list[dict]:
    """One row per (dataset, family, budget); random seeds averaged (mean ± sd)."""
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["dataset"], r["family"], r["budget"]), []).append(r)
    out = []
    for (ds, fam, b), rs in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        s = {"dataset": ds, "family": fam, "budget": b, "runs": len(rs)}
        for key in ("recall@10", "recall@25", "verified", "seconds", "llm_seconds",
                    "miner_seconds", "patterns", "planted_found", "tokens_in", "tokens_out",
                    "cost_usd", "fallback_batches", "batches"):
            m, sd = _mean_sd([r.get(key) for r in rs])
            s[key] = None if math.isnan(m) else round(m, 4)
            s[f"{key}_sd"] = None if math.isnan(sd) else round(sd, 4)
        s["all_oracle_ok"] = all(r["oracle_ok"] in (True, None) for r in rs)
        s["all_scores_match"] = all(r.get("scores_match_reference", True) for r in rs)
        s["all_precision_ok"] = all(r["precision_ok"] for r in rs)
        out.append(s)
    return out


def verdicts(summary: list[dict], budget: float = 0.3) -> dict:
    """Apply the rejection criteria stated in docs/02-hypothesis.md (mechanically)."""
    def get(ds, fam):
        return next((s for s in summary if s["dataset"] == ds and s["family"] == fam
                     and abs(s["budget"] - budget) < 1e-9), None)

    out = {"budget": budget, "H1": {}, "H2": {}}
    llm_fams = sorted({s["family"] for s in summary if s["family"].startswith("llm:")})
    for ds in DATASETS:
        h, r, c = get(ds, "heuristic"), get(ds, "random"), get(ds, "cardinality")
        for fam in llm_fams:
            l = get(ds, fam)
            if not (l and h and r) or l["recall@10"] is None:
                continue
            best = max(x["recall@10"] for x in (h, r, c) if x and x["recall@10"] is not None)
            ok90 = l["recall@10"] >= 0.9
            beats = l["recall@10"] > best
            verdict = ("supported" if ok90 and beats else
                       "rejected: a cheap baseline is as good" if ok90 else
                       "rejected: below 90 %")
            out["H1"][f"{ds} / {fam}"] = {"llm": l["recall@10"], "heuristic": h["recall@10"],
                                           "cardinality": c["recall@10"] if c else None,
                                           "random": r["recall@10"], "verdict": verdict}
    base_fam = "cardinality" if get("university", "cardinality") else "heuristic"
    for fam in llm_fams:
        named, anon = get("university", fam), get("university-anon", fam)
        hn, ha = get("university", base_fam), get("university-anon", base_fam)
        if not all([named, anon, hn, ha]):
            continue
        gap_named = named["recall@10"] - hn["recall@10"]
        gap_anon = anon["recall@10"] - ha["recall@10"]
        verdict = ("supported" if gap_named > 0.05 and gap_anon <= 0.05 else
                   "not supported")
        out["H2"][fam] = {"gap_named": round(gap_named, 4), "gap_anon": round(gap_anon, 4),
                          "baseline": base_fam, "verdict": verdict}
    return out


# --------------------------------------------------------------------------- figures


def figures(summary: list[dict], rows: list[dict]) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURES.mkdir(parents=True, exist_ok=True)
    paths = []
    colors = {"random": "#9aa0a6", "heuristic": "#f29900", "cardinality": "#d93025",
              "llm:groq": "#1a73e8",
              "llm:nvidia": "#188038", "llm:gemini": "#a142f4"}
    names = {"random": "random (mean ± sd, 5 seeds)", "heuristic": "structural heuristic",
             "cardinality": "cardinality (schema stats, no LLM)",
             "llm:groq": "LLM joins: Groq gpt-oss-120b",
             "llm:nvidia": "LLM joins: NVIDIA minimax-m3.1-flash",
             "llm:gemini": "LLM joins: Gemini 3.8 Flash"}

    # 1. recall@10 vs budget, one panel per dataset
    ds_list = [d for d in DATASETS if any(s["dataset"] == d for s in summary)]
    if ds_list:
        fig, axes = plt.subplots(1, len(ds_list), figsize=(5.2 * len(ds_list), 4.2), squeeze=False)
        for ax, ds in zip(axes[0], ds_list):
            for fam, col in colors.items():
                pts = sorted((s["budget"], s["recall@10"], s["recall@10_sd"]) for s in summary
                             if s["dataset"] == ds and s["family"] == fam
                             and s["recall@10"] is not None and s["budget"] < 1)
                if not pts:
                    continue
                xs = [p[0] * 100 for p in pts]
                ys = [p[1] * 100 for p in pts]
                ax.plot(xs, ys, marker="o", color=col, label=names[fam], linewidth=2)
                if fam == "random":
                    lo = [(p[1] - (p[2] or 0)) * 100 for p in pts]
                    hi = [(p[1] + (p[2] or 0)) * 100 for p in pts]
                    ax.fill_between(xs, lo, hi, color=col, alpha=0.2)
            ax.axhline(90, color="#d93025", linestyle="--", linewidth=1)
            ax.text(11, 91.5, "H1 target 90 %", color="#d93025", fontsize=8)
            ax.set_title(ds)
            ax.set_xlabel("budget: % of unique candidates verified per level")
            ax.set_ylim(-3, 103)
            ax.grid(alpha=0.3)
        axes[0][0].set_ylabel("recall@10 of the exhaustive miner's top patterns (%)")
        axes[0][-1].legend(fontsize=8, loc="lower right")
        fig.tight_layout()
        p = FIGURES / "recall_vs_budget.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(p)

    # 2. upstream vs exhaustive (non-LLM speed-up, same output)
    pairs = []
    for ds in ds_list:
        up = next((r for r in rows if r["dataset"] == ds and r["arm"] == "upstream"), None)
        ex = next((r for r in rows if r["dataset"] == ds and r["arm"] == "exhaustive-b100"), None)
        if up and ex:
            pairs.append((ds, up["seconds"], ex["seconds"]))
    if pairs:
        fig, ax = plt.subplots(figsize=(6.5, 3.6))
        xs = range(len(pairs))
        ax.bar([x - 0.2 for x in xs], [p[1] for p in pairs], 0.4, label="upstream miner",
               color="#9aa0a6")
        ax.bar([x + 0.2 for x in xs], [p[2] for p in pairs], 0.4,
               label="guided, exhaustive @100 % (same output)", color="#1a73e8")
        for x, p in zip(xs, pairs):
            ax.text(x + 0.2, p[2], f"{p[1] / p[2]:.1f}× faster", ha="center", va="bottom", fontsize=8)
        ax.set_xticks(list(xs), [p[0] for p in pairs])
        ax.set_ylabel("wall time (s)")
        ax.set_title("No LLM involved: dedupe + filter order (ADR 0005)")
        ax.legend(fontsize=8)
        fig.tight_layout()
        p = FIGURES / "upstream_vs_exhaustive.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(p)

    # 3. ablation: LLM minus heuristic at 30 %, named vs anonymised
    v = verdicts(summary)
    if v["H2"]:
        fams = list(v["H2"])
        fig, ax = plt.subplots(figsize=(6.5, 3.6))
        xs = range(len(fams))
        ax.bar([x - 0.2 for x in xs], [v["H2"][f]["gap_named"] * 100 for f in fams], 0.4,
               label="named relations", color="#1a73e8")
        ax.bar([x + 0.2 for x in xs], [v["H2"][f]["gap_anon"] * 100 for f in fams], 0.4,
               label="anonymised (R1..R9)", color="#9aa0a6")
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_xticks(list(xs), [names.get(f, f).replace("LLM joins: ", "") for f in fams],
                      fontsize=8)
        ax.set_ylabel("recall@10: LLM − cardinality baseline (points)")
        ax.set_title("H2: does the gain come from the relation names? (budget 30 %)")
        ax.legend(fontsize=8)
        fig.tight_layout()
        p = FIGURES / "ablation_named_vs_anon.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(p)
    return paths


# --------------------------------------------------------------------------- report


def _fmt(v, pct_=False, nd=1):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v * 100:.0f} %" if pct_ else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def results_tables(summary: list[dict], rows: list[dict]) -> str:
    lines = []
    for ds in DATASETS:
        ss = [s for s in summary if s["dataset"] == ds]
        if not ss:
            continue
        up = next((r for r in rows if r["dataset"] == ds and r["arm"] == "upstream"), None)
        ex = next((s for s in ss if s["family"] == "exhaustive"), None)
        lines += [f"### {ds}", ""]
        if ex:
            lines.append(f"Exhaustive @ 100 %: {ex['patterns']:.0f} patterns, "
                         f"{ex['verified']:.0f} candidates verified, {ex['seconds']:.1f} s"
                         + (f"; upstream miner (same config): {up['seconds']:.1f} s, "
                            f"{up['scored']} patterns scored" if up else "") + ".")
            lines.append("")
        lines += ["| method | budget | recall@10 | recall@25 | planted | verified | time (s) | "
                  "LLM (s) | tokens in/out | LLM fallbacks |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for s in sorted(ss, key=lambda s: (s["budget"], s["family"])):
            if s["family"] in ("exhaustive", "upstream"):
                continue
            rc = _fmt(s["recall@10"], True)
            if s["family"] == "random" and s["recall@10_sd"] is not None:
                rc += f" ± {s['recall@10_sd'] * 100:.0f}"
            planted = (f"{s['planted_found']:.1f}/3" if s["planted_found"] is not None else "–")
            tok = (f"{s['tokens_in']:.0f} / {s['tokens_out']:.0f}" if s["tokens_in"] else "–")
            fb = (f"{s['fallback_batches']:.0f}/{s['batches']:.0f}" if s["batches"] else "–")
            lines.append(f"| {s['family']} | {s['budget'] * 100:.0f} % | {rc} | "
                         f"{_fmt(s['recall@25'], True)} | {planted} | {s['verified']:.0f} | "
                         f"{s['seconds']:.1f} | {_fmt(s['llm_seconds'])} | {tok} | {fb} |")
        lines.append("")
    return "\n".join(lines)


def verdict_table(v: dict) -> str:
    lines = [f"**H1** (budget {v['budget'] * 100:.0f} %, recall@10):", "",
             "| dataset / ranker | LLM | cardinality | structural | random (mean) | verdict |",
             "|---|---:|---:|---:|---:|---|"]
    for k, x in v["H1"].items():
        card = f"{x['cardinality'] * 100:.0f} %" if x.get("cardinality") is not None else "–"
        lines.append(f"| {k} | {x['llm'] * 100:.0f} % | {card} | {x['heuristic'] * 100:.0f} % | "
                     f"{x['random'] * 100:.0f} % | {x['verdict']} |")
    if v["H2"]:
        lines += ["", "**H2** (LLM − best cheap baseline, recall@10, budget 30 %):", "",
                  "| ranker | named | anonymised | verdict |", "|---|---:|---:|---|"]
        for k, x in v["H2"].items():
            lines.append(f"| {k} | {x['gap_named'] * 100:+.0f} pts | {x['gap_anon'] * 100:+.0f} pts | "
                         f"{x['verdict']} |")
    return "\n".join(lines)


def headline(summary: list[dict], budget: float = 0.3) -> str:
    """Compact table for the README: recall@10 and planted patterns at one budget."""
    fams = ["random", "heuristic", "cardinality"] + sorted(
        {s["family"] for s in summary if s["family"].startswith("llm")})
    label = {"random": "random (5 seeds)", "heuristic": "structural heuristic",
             "cardinality": "cardinality (schema stats)"}
    ds_list = [d for d in DATASETS if any(s["dataset"] == d for s in summary)]
    head = "| method | " + " | ".join(ds_list) + " |"
    lines = [f"Recall@10 of the full miner's top patterns when only **{budget * 100:.0f} %** of "
             "candidates are verified (planted patterns found in brackets, synthetic graphs only):", "",
             head, "|---|" + "---:|" * len(ds_list)]
    for fam in fams:
        cells = []
        for ds in ds_list:
            s = next((x for x in summary if x["dataset"] == ds and x["family"] == fam
                      and abs(x["budget"] - budget) < 1e-9), None)
            if not s or s["recall@10"] is None:
                cells.append("–")
                continue
            c = f"{s['recall@10'] * 100:.0f} %"
            if s.get("planted_found") is not None:
                c += f" ({s['planted_found']:.1f}/3)" if fam == "random" else f" ({s['planted_found']:.0f}/3)"
            cells.append(c)
        if any(c != "–" for c in cells):
            lines.append(f"| {label.get(fam, fam.replace('llm:', 'LLM joins · '))} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _replace_block(path: Path, name: str, content: str) -> None:
    start, end = f"<!-- BEGIN {name} -->", f"<!-- END {name} -->"
    text = path.read_text()
    if start not in text:
        return
    pre, rest = text.split(start, 1)
    _, post = rest.split(end, 1)
    path.write_text(f"{pre}{start}\n{content}\n{end}{post}")


def report(log=print) -> dict:
    rows = collect()
    if not rows:
        log("no results yet: run `make eval-baselines` first")
        return {}
    write_csv(rows, RESULTS / "runs.csv")
    summary = summarize(rows)
    write_csv(summary, RESULTS / "summary.csv")
    v = verdicts(summary)
    (RESULTS / "verdicts.json").write_text(json.dumps(v, indent=2))
    figs = figures(summary, rows)
    tables = results_tables(summary, rows)
    (RESULTS / "results.md").write_text("# Results (generated)\n\n" + tables + "\n" +
                                        verdict_table(v) + "\n")
    for doc in (ROOT / "docs" / "05-baseline.md", ROOT / "docs" / "06-results.md"):
        if doc.exists():
            _replace_block(doc, "RESULTS-TABLES", tables)
            _replace_block(doc, "VERDICTS", verdict_table(v))
    _replace_block(ROOT / "README.md", "HEADLINE", headline(summary))
    bad = [r for r in rows if r["oracle_ok"] is False or not r["precision_ok"]
           or not r["scores_match_reference"]]
    log(f"{len(rows)} runs, {len(summary)} groups, figures: {[p.name for p in figs]}")
    log("oracle, precision and score checks: " + ("all ok" if not bad else
        f"{len(bad)} FAILED: " + ", ".join(f"{r['dataset']}/{r['arm']}" for r in bad[:8])))
    return v


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="minerllm eval")
    ap.add_argument("part", choices=["baselines", "llm", "report"])
    ap.add_argument("--datasets", default=",".join(DATASETS))
    ap.add_argument("--providers", default=",".join(PROVIDERS))
    ap.add_argument("--budgets", default=",".join(str(b) for b in BUDGETS))
    ap.add_argument("--no-direct", action="store_true", help="skip the llm-direct arm")
    ap.add_argument("--force", action="store_true", help="re-run arms that already have results")
    args = ap.parse_args(argv)
    budgets = [float(b) for b in args.budgets.split(",")]
    ds = [d for d in args.datasets.split(",") if d]
    log = lambda m: print(m, file=sys.stderr, flush=True)  # noqa: E731
    if args.part == "baselines":
        run_matrix(ds, baseline_arms(budgets), upstream=True, force=args.force, log=log)
    elif args.part == "llm":
        run_matrix(ds, llm_arms([p for p in args.providers.split(",") if p], budgets,
                                direct=not args.no_direct), force=args.force, log=log)
    report(log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
