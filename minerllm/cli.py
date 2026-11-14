"""Command-line interface:  ``minerllm <command> ...``  (or ``python -m minerllm``)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ROOT, MinerConfig


def cmd_mine(args) -> int:
    from .harness import run_upstream
    cfg = MinerConfig.from_yaml(args.config) if args.config else MinerConfig(
        dataset=args.dataset, minsup=args.minsup, depth=args.depth, surp_mode=args.surp)
    run, ver = run_upstream(cfg, Path(args.out) if args.out else None)
    ranked = sorted(run.patterns, key=lambda p: -(p.surprisingness or 0))
    for mp in ranked[: args.top]:
        score = f"{mp.surprisingness:.3f}" if mp.surprisingness is not None else "  -  "
        print(f"{score}  sup={mp.support:<6} {mp.pattern}")
    status = "ok" if ver is None or ver.ok else f"{len(ver.mismatches)} ORACLE MISMATCHES"
    print(f"\n{len(run.patterns)} distinct patterns in {run.seconds:.1f}s — supports vs oracle: {status}")
    return 0 if run.ok and (ver is None or ver.ok) else 1


def cmd_guided(args) -> int:
    from .config import RankerConfig
    from .harness import run_guided
    cfg = MinerConfig.from_yaml(args.config)
    if args.depth is not None:
        cfg.depth = args.depth
    rc = RankerConfig(strategy=args.strategy, budget=args.budget, seed=args.seed,
                      providers=args.providers.split(","), batch_size=args.batch_size,
                      cache_dir=None if args.no_cache else ".cache/llm")
    run, ver, s = run_guided(cfg, rc, Path(args.out) if args.out else None, progress=True)
    ranked = sorted(run.patterns, key=lambda p: -(p.surprisingness or 0))
    for mp in ranked[: args.top]:
        score = f"{mp.surprisingness:.3f}" if mp.surprisingness is not None else "  -  "
        print(f"{score}  sup={mp.support:<6} {mp.pattern}")
    print(f"\n{len(run.patterns)} patterns in {run.seconds:.1f}s | strategy={rc.strategy} "
          f"budget={rc.budget:.0%} | candidates generated={s.get('generated')} "
          f"unique={s.get('unique')} verified={s.get('selected')} | "
          f"LLM {s.get('llm_seconds', 0):.1f}s, {s.get('input_tokens', 0)}+{s.get('output_tokens', 0)} "
          f"tokens, {s.get('fallback_batches', 0)}/{s.get('batches', 0)} batches fell back | "
          f"supports vs oracle: {'ok' if ver.ok else 'MISMATCH'}")
    return 0 if run.ok and ver.ok else 1


def cmd_models(args) -> int:
    """List the model IDs each configured provider offers this account (keys from .env)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    import os
    from .llm.base import LLMError
    from .llm.providers import DEFAULT_MODELS, list_models
    envs = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "nvidia": "NVIDIA_API_KEY"}
    for prov in args.providers.split(","):
        current = os.environ.get(f"{prov.upper()}_MODEL", DEFAULT_MODELS[prov])
        if not os.environ.get(envs[prov]):
            print(f"\n{prov}: no {envs[prov]} set")
            continue
        try:
            ids = list_models(prov)
        except (LLMError, Exception) as e:      # noqa: BLE001 - report and continue
            print(f"\n{prov}: could not list models ({str(e)[:120]})")
            continue
        shown = [m for m in ids if not args.filter or args.filter.lower() in m.lower()]
        status = "OK" if current in ids else "NOT AVAILABLE for this key"
        print(f"\n{prov}: {len(ids)} models | configured: {current} -> {status}")
        for m in shown[: args.limit]:
            print(f"  {m}")
    return 0


def cmd_datagen(args) -> int:
    from .datagen import UniversitySpec, write_dataset
    spec = UniversitySpec(students=args.students, strength=args.strength, seed=args.seed,
                          anonymize=args.anonymize)
    path = write_dataset(spec, args.out)
    print(path)
    return 0


def cmd_galaxy(args) -> int:
    from .datasets import galaxy_subset
    print(galaxy_subset(args.n, args.out, seed=args.seed))
    return 0


def cmd_support(args) -> int:
    from .datasets import load_atoms
    from .oracle import Oracle
    o = Oracle(load_atoms(args.dataset))
    for p in args.patterns:
        print(o.support(p), p)
    return 0


def cmd_stats(args) -> int:
    from .datasets import load_atoms, stats
    print(stats(load_atoms(args.dataset)).describe())
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="minerllm", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("mine", help="run the upstream miner and verify supports")
    m.add_argument("--config", help="YAML MinerConfig (overrides the flags below)")
    m.add_argument("--dataset", default="external/hyperon-miner/experiments/data/ugly_man_sodaDrinker")
    m.add_argument("--minsup", type=int, default=10)
    m.add_argument("--depth", type=int, default=0)
    m.add_argument("--surp", default="isurp")
    m.add_argument("--top", type=int, default=15)
    m.add_argument("--out")
    m.set_defaults(func=cmd_mine)

    gm = sub.add_parser("guided", help="run the LLM-guided miner (or a baseline ranker)")
    gm.add_argument("--config", default="configs/university.yaml")
    gm.add_argument("--strategy", default="llm", choices=["exhaustive", "random", "heuristic", "llm", "llm-direct"])
    gm.add_argument("--budget", type=float, default=0.3, help="fraction of candidates verified")
    gm.add_argument("--providers", default="gemini,groq,nvidia",
                    help="comma-separated; 'mock' runs offline")
    gm.add_argument("--batch-size", type=int, default=60)
    gm.add_argument("--seed", type=int, default=0)
    gm.add_argument("--depth", type=int)
    gm.add_argument("--no-cache", action="store_true")
    gm.add_argument("--top", type=int, default=15)
    gm.add_argument("--out")
    gm.set_defaults(func=cmd_guided)

    md = sub.add_parser("models", help="list model IDs your API keys can use")
    md.add_argument("--providers", default="gemini,groq,nvidia")
    md.add_argument("--filter", default="", help="only show IDs containing this text")
    md.add_argument("--limit", type=int, default=60)
    md.set_defaults(func=cmd_models)

    g = sub.add_parser("datagen", help="write a synthetic university graph with planted patterns")
    g.add_argument("--students", type=int, default=60)
    g.add_argument("--strength", type=float, default=0.8)
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--anonymize", action="store_true")
    g.add_argument("--out", default=str(ROOT / "experiments" / "data"))
    g.set_defaults(func=cmd_datagen)

    gx = sub.add_parser("galaxy", help="write a deterministic Galaxy subset")
    gx.add_argument("n", type=int)
    gx.add_argument("--seed", type=int, default=7)
    gx.add_argument("--out", default=str(ROOT / "experiments" / "data"))
    gx.set_defaults(func=cmd_galaxy)

    s = sub.add_parser("support", help="oracle support of one or more patterns")
    s.add_argument("dataset")
    s.add_argument("patterns", nargs="+")
    s.set_defaults(func=cmd_support)

    st = sub.add_parser("stats", help="relation statistics of a dataset")
    st.add_argument("dataset")
    st.set_defaults(func=cmd_stats)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
