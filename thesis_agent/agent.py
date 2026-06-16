"""The agent: turn an evidence fact sheet into a grounded thesis scorecard.

Two interchangeable backends produce the same validated `ThesisScorecard`:

* ``sdk`` — Anthropic Python SDK with structured outputs (schema enforced by the
  API). This is the path end users run with their own ``ANTHROPIC_API_KEY``.
* ``cli`` — shells out to the local ``claude`` CLI in print mode
  (``claude -p``), which reuses an existing Claude Code login, so no API key is
  needed. JSON shape is enforced via the embedded schema + Pydantic validation.

``backend="auto"`` (default) picks ``sdk`` when ``ANTHROPIC_API_KEY`` is set,
otherwise falls back to ``cli``.

Either way the model is handed ONLY the fact sheet as ground truth — its job is
to reason over the evidence, not to recall facts about the company.
"""

import json
import os
import subprocess

from .aggregate import compute_overall
from .data import Evidence, format_evidence
from .schema import ThesisScorecard

MODEL = "claude-opus-4-8"

DIMENSIONS = [
    "Growth (revenue & earnings trajectory)",
    "Profitability & Margins",
    "Balance Sheet & Financial Health",
    "Valuation",
    "Cash Flow Quality",
    "Competitive Position / Moat",
    "Momentum & Market Sentiment",
    "Risks & Red Flags",
]

SYSTEM = """You are a disciplined equity research analyst producing a structured \
investment thesis scorecard.

Hard rules — these define the quality bar:
1. GROUND EVERYTHING. You may only use facts present in the EVIDENCE list. Do \
not introduce prices, ratios, growth rates, or facts from your own memory, even \
if you think you know them — this analysis must be reproducible from the \
evidence alone.
2. CITE. Every dimension's `evidence_ids` must list the IDs (e.g. "E4") of the \
evidence items that support your rating. If you cannot cite evidence for a \
dimension, set its rating to `insufficient_data` and confidence to `low`.
3. CALIBRATE CONFIDENCE honestly. Thin, stale, or indirect evidence → `low`. \
Only use `high` when multiple direct, current data points agree.
4. NO FABRICATION OF MISSING DATA. If something important is absent (e.g. no \
moat/competitive data is ever provided here), say so in `data_gaps` and let it \
lower confidence — never invent it.
5. Be specific and quantitative in rationales, quoting the evidence values.
6. `neutral` vs `insufficient_data`: use `neutral` ONLY when you have relevant \
evidence and it is genuinely balanced. If a dimension cannot be judged because \
the relevant evidence is ABSENT, you MUST use `insufficient_data` — never use \
`neutral` to paper over missing data.
7. For "Risks & Red Flags", rate strictly from concrete risk signals present in \
the evidence: stretched valuation multiples, high leverage, weak liquidity, \
negative or declining cash flow / revenue, dilution. Vague or off-topic news \
headlines are NOT risk evidence — ignore them. If no concrete risk signal is \
present, use `insufficient_data` rather than defaulting to `neutral`.

You assess a FIXED set of dimensions. Some (e.g. Competitive Position / Moat) \
will usually lack direct evidence — rate them `insufficient_data` rather than \
guessing, and note the gap. This honesty is the point of the tool.

Note: the `overall_rating` you provide is recomputed deterministically from your \
dimension ratings, so focus your effort on getting each dimension right."""


def build_user_message(ticker: str, company: str, evidence: list[Evidence]) -> str:
    dims = "\n".join(f"- {d}" for d in DIMENSIONS)
    return (
        f"Company: {company} ({ticker.upper()})\n\n"
        f"Assess EACH of these dimensions exactly once:\n{dims}\n\n"
        f"EVIDENCE (the only facts you may use):\n"
        f"{format_evidence(evidence)}\n\n"
        f"Produce the thesis scorecard. Remember: cite evidence IDs for every "
        f"rating, and mark dimensions without supporting evidence as "
        f"`insufficient_data`."
    )


# --- backends ---------------------------------------------------------------


def _complete_sdk(system: str, user: str) -> ThesisScorecard:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=ThesisScorecard,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(
            f"Model declined or returned no output (stop_reason={response.stop_reason})."
        )
    return response.parsed_output


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        return text[start : end + 1]
    return text


def _complete_cli(system: str, user: str) -> ThesisScorecard:
    schema = json.dumps(ThesisScorecard.model_json_schema())
    prompt = (
        f"{system}\n\n{user}\n\n"
        f"Return ONLY a single JSON object matching this JSON Schema "
        f"(no markdown fences, no commentary):\n{schema}"
    )
    proc = subprocess.run(
        ["claude", "-p", "--output-format", "json", "--max-turns", "1"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed ({proc.returncode}): {proc.stderr[:500]}")
    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"claude CLI returned an error: {envelope.get('result')}")
    raw = envelope.get("result", "")
    try:
        data = json.loads(_extract_json(raw))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse JSON from CLI output: {exc}\n---\n{raw[:1000]}")
    return ThesisScorecard.model_validate(data)


def run_thesis(
    ticker: str,
    company: str,
    evidence: list[Evidence],
    backend: str = "auto",
) -> ThesisScorecard:
    if backend == "auto":
        backend = "sdk" if os.environ.get("ANTHROPIC_API_KEY") else "cli"
    system, user = SYSTEM, build_user_message(ticker, company, evidence)
    if backend == "sdk":
        card = _complete_sdk(system, user)
    elif backend == "cli":
        card = _complete_cli(system, user)
    else:
        raise ValueError(f"Unknown backend: {backend!r} (use 'auto', 'sdk', or 'cli').")

    # The overall rating is computed from dimensions, not left to the model
    # (eval found the model's holistic roll-up wobbles run-to-run).
    card.overall_rating, card.overall_confidence = compute_overall(card.dimensions)
    return card
