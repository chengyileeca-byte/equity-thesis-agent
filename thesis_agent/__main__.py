"""CLI: `python -m thesis_agent AAPL` → grounded thesis scorecard.

Pipeline: fetch evidence (yfinance) → grounded structured Claude call → render.
Writes Markdown + JSON to examples/ and prints the report.
"""

import argparse
import json
import sys
from pathlib import Path

from .agent import run_thesis
from .data import build_evidence
from .report import render_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="thesis_agent",
        description="Generate a grounded, citation-enforced equity thesis scorecard.",
    )
    parser.add_argument("ticker", help="Stock symbol, e.g. AAPL, MSFT, NVDA")
    parser.add_argument(
        "--out-dir", default="examples", help="Directory for saved output."
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Print only; do not write files."
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "sdk", "cli"],
        default="auto",
        help="LLM backend. 'sdk' needs ANTHROPIC_API_KEY; 'cli' uses the local "
        "claude CLI login. 'auto' picks sdk if a key is set, else cli.",
    )
    args = parser.parse_args(argv)
    ticker = args.ticker.upper()

    print(f"Fetching evidence for {ticker} ...", file=sys.stderr)
    company, evidence = build_evidence(ticker)
    if not evidence:
        print(f"No data found for '{ticker}'. Check the symbol.", file=sys.stderr)
        return 1
    print(f"  {len(evidence)} evidence items. Asking Claude ...", file=sys.stderr)

    card = run_thesis(ticker, company, evidence, backend=args.backend)
    markdown = render_markdown(card, evidence)
    print("\n" + markdown)

    if not args.no_save:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{ticker}.md").write_text(markdown, encoding="utf-8")
        (out_dir / f"{ticker}.json").write_text(
            card.model_dump_json(indent=2), encoding="utf-8"
        )
        print(f"\nSaved to {out_dir}/{ticker}.md and {ticker}.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
