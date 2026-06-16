"""CLI for the eval harness.

    python -m evals.run groundedness AAPL [--backend cli]
    python -m evals.run consistency  AAPL --n 3 [--backend cli]
    python -m evals.run refusal      AAPL [--backend cli]

`groundedness` works offline on a saved run if you pass --from-json (scorecard)
plus the evidence is re-fetched; by default it does a fresh generation so the
scorecard and evidence are guaranteed to be the matched pair.
"""

import argparse

from thesis_agent.agent import run_thesis
from thesis_agent.data import build_evidence

from .consistency import run_consistency, run_refusal_to_guess
from .groundedness import check_groundedness


def _groundedness(args) -> int:
    company, evidence = build_evidence(args.ticker.upper())
    if not evidence:
        print(f"No data for {args.ticker}")
        return 1
    card = run_thesis(args.ticker, company, evidence, backend=args.backend)
    print(check_groundedness(card, evidence).render())
    return 0


def _consistency(args) -> int:
    print(run_consistency(args.ticker, n=args.n, backend=args.backend).render())
    return 0


def _refusal(args) -> int:
    print(
        run_refusal_to_guess(
            args.ticker, keep_categories=tuple(args.keep), backend=args.backend
        ).render()
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals.run")
    sub = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("ticker")
    common.add_argument("--backend", choices=["auto", "sdk", "cli"], default="auto")

    g = sub.add_parser("groundedness", parents=[common],
                       help="Citation & number grounding (1 call).")
    g.set_defaults(func=_groundedness)

    c = sub.add_parser("consistency", parents=[common],
                       help="Rating stability over N runs.")
    c.add_argument("--n", type=int, default=3)
    c.set_defaults(func=_consistency)

    r = sub.add_parser("refusal", parents=[common],
                       help="Refusal-to-guess on stripped evidence.")
    r.add_argument("--keep", nargs="+", default=["Price"],
                   help="Evidence categories to keep.")
    r.set_defaults(func=_refusal)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
