# Evaluation harness (milestone 2 — in progress)

The differentiator of this project is not "an LLM writes a stock report" — anyone
can do that. It is **measuring whether the agent's output is grounded and
consistent**, the same rigor I apply to backtests in my quant work.

Planned evals:

### 1. Citation groundedness (automatic, no LLM judge)
For every `DimensionAssessment`, check that:
- `evidence_ids` are all real IDs present in the fact sheet (no hallucinated IDs).
- Non-`insufficient_data` ratings have ≥1 citation.
- Numbers quoted in `rationale` appear in the cited evidence values
  (regex-extract numerics, fuzzy-match against the fact sheet).

This catches the #1 LLM failure mode — confidently citing data that wasn't there.

### 2. Refusal-to-guess rate
Feed deliberately sparse fact sheets (e.g. price only). A good agent should mark
most dimensions `insufficient_data`, not invent a thesis. Measure the share of
dimensions correctly flagged vs. fabricated.

### 3. Consistency under perturbation
Run the same ticker N times and on lightly reworded fact sheets; measure
rating stability (do ratings flip on noise?). Borrows the holdout/reverse-test
idea from my OOS Guardian.

### 4. Known-case rubric (small LLM-judge set)
A handful of hand-labelled tickers with expected directional ratings, scored by
a separate judge model — used sparingly, since (1)–(3) are cheaper and harder
to game.

Run with: `python -m evals.run` (to be added).
