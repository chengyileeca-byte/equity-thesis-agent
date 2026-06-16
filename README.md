# Equity Thesis Agent

A small, **grounded** equity-research agent: give it a ticker, it pulls a fact
sheet of real fundamentals and produces a structured 8-dimension investment
**thesis scorecard** — where every rating must cite the data point that backs
it, and the model is pushed to say *"insufficient data"* instead of making
numbers up.

It is built around one opinion: in 2026 anyone can wire an LLM to a stock API
and get a plausible-sounding report. The hard part — and the part worth
showing — is making the output **grounded, honest about its gaps, and
measurable**. So the design centers on citation-enforcement and an eval harness,
not on prompt cleverness.

> Personal project. **Not investment advice.**

## What it does

```
ticker ──▶ fact sheet (yfinance)  ──▶  grounded structured LLM call  ──▶  scorecard
           E1..En, human-labelled       (Claude Opus 4.8, schema-       (Markdown + JSON,
           — the ONLY ground truth        constrained, cited)             resolved citations)
```

Each of 8 dimensions (Growth, Profitability, Balance Sheet, Valuation, Cash
Flow, Moat, Momentum, Risks) gets a rating, a confidence level, a quoted
rationale, and **`evidence_ids`** pointing at the fact-sheet items that justify
it. Dimensions with no supporting evidence are rated `insufficient_data` and
listed under **Data Gaps** rather than guessed.

## Why it's built this way (the engineering, not the demo)

- **Citation as a schema constraint, not a hope.** The Pydantic output schema
  (`schema.py`) makes `evidence_ids` a required field per dimension. The model
  is structurally nudged to ground claims, and a downstream check can verify the
  IDs are real — catching the classic "confidently cites data that wasn't there"
  failure.
- **Single source of truth.** The model is told it may use *only* the fact sheet
  — not its own memory of the company. That makes a run **reproducible from its
  evidence** and side-steps stale-training-data hallucination.
- **Honest confidence + data gaps.** Thin or missing evidence is supposed to
  *lower* confidence and surface in `data_gaps`, not get papered over.
- **Eval-first mindset.** See [`evals/`](evals/README.md): groundedness checks,
  refusal-to-guess rate, and consistency-under-perturbation — the same
  out-of-sample rigor I use on quant backtests, applied to an LLM system.

## Eval results (real numbers)

Measured on live data via `python -m evals.run`:

- **Groundedness (AAPL):** PASS — 8/8 dimensions, **0 hallucinated citations,
  0 uncited ratings, ~98–100% of quoted numbers traced to cited evidence.**
- **Refusal-to-guess (AAPL, evidence stripped to price-only):** **75%** of
  dimensions correctly marked `insufficient_data` instead of inventing a thesis.
- **Consistency (AAPL, 3 runs on identical evidence):** per-dimension ratings are
  highly reproducible; the model's *holistic overall* can be the noisier part (it
  wobbled in earlier runs) — so the harness now reports it directly: run-to-run
  stability + calibration against a rules baseline, instead of hiding it.

The harness earned its keep — it surfaced real behaviour, which shaped the design:

| What the eval surfaced | How it's handled |
|---|---|
| Per-dimension ratings reproduce well, but the model's holistic **overall** can wobble run-to-run | **Keep the model's overall** — its judgment beats any fixed formula — but show a deterministic **rules-based baseline alongside** (`aggregate.py`) and have the eval measure the overall's **stability** and **calibration** (how often model and baseline agree). The disagreement is a signal, not a bug. |
| "Risks" dimension flip-flopped; vague news treated as risk | Explicit risk rubric in the prompt → Risks now stable across runs |
| Sparse data hedged to `neutral` instead of refusing | A `neutral` vs `insufficient_data` rule → refusal rate **62% → 75%** |

> **Design stance:** the model is the judge; the engineering makes its judgment
> *grounded, honest, and measurable*. That division — not out-scoring the model
> with hand-rolled rules — is the point.

## Quickstart

```bash
pip install -r requirements.txt
python -m thesis_agent AAPL
```

The agent needs an LLM backend. It auto-selects one:

| Backend | How to enable | Notes |
|---------|---------------|-------|
| `sdk` (default for users) | `export ANTHROPIC_API_KEY=sk-ant-...` ([get one](https://console.anthropic.com/)) | Anthropic Python SDK with **schema-enforced** structured outputs. Bring your own key. |
| `cli` | have the [`claude`](https://docs.claude.com/en/docs/claude-code) CLI installed & logged in | Shells out to `claude -p`; **no API key needed**. JSON shape enforced via embedded schema + Pydantic validation. |

`auto` (the default) uses `sdk` when `ANTHROPIC_API_KEY` is set, otherwise `cli`.
Force one with `--backend sdk|cli`. Output prints and is saved to
`examples/<TICKER>.md` and `.json`.

## Layout

| File | Role |
|------|------|
| `thesis_agent/data.py`   | Build the labelled evidence fact sheet (yfinance). |
| `thesis_agent/schema.py` | Pydantic scorecard schema — the citation contract. |
| `thesis_agent/agent.py`  | One structured, grounded Claude call. |
| `thesis_agent/report.py` | Render Markdown with citations resolved to labels. |
| `thesis_agent/__main__.py` | CLI. |
| `evals/`                 | Groundedness / honesty / consistency evals (in progress). |

## Roadmap

- [x] Fact sheet → grounded structured scorecard → report
- [x] Eval harness: citation groundedness + refusal-to-guess + consistency
      (`python -m evals.run ...`)
- [x] Rules-based overall baseline + calibration metric — the model gives the
      overall, a deterministic baseline (`aggregate.py`) is shown alongside, and
      the eval measures their agreement and the overall's run-to-run stability
- [ ] Earnings-call transcript ingestion (PDF) as additional cited evidence
- [ ] Pluggable data sources (TW market via FinMind) behind the same evidence
      interface

## Stack

Python · [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python)
(Claude Opus 4.8, adaptive thinking, structured outputs) · Pydantic · yfinance.
