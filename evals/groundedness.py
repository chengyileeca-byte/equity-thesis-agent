"""Groundedness checks — pure code, no LLM judge.

Catches the #1 failure mode of an LLM research tool: claiming things the data
never said. Three checks, in order of how damning a failure is:

1. Hallucinated citations — a dimension cites an evidence ID that doesn't exist.
   Hard fail, zero false positives.
2. Missing citations — a dimension with a real rating cites nothing.
   Hard fail.
3. Number grounding — precise figures quoted in a rationale should trace back to
   a cited fact. Soft signal: derived numbers (e.g. "~5.5% upside") legitimately
   won't match, so we report them separately rather than failing on them.
"""

import re
from dataclasses import dataclass, field

from thesis_agent.data import Evidence
from thesis_agent.schema import ThesisScorecard

# Digit runs like 35.84, 101.09, 312.72, 16.6, 1.07, 4,350. Commas allowed.
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
# Only check figures precise enough to be a real data point (≥3 significant
# digits). This skips small derived numbers like "72%" or "5.5%" that the model
# legitimately computes, keeping the check low-false-positive.
_MIN_DIGITS = 3


def _norm(text: str) -> str:
    return re.sub(r"[^\d.]", "", text)


def _numbers(text: str) -> list[str]:
    out = []
    for m in _NUM_RE.findall(text):
        norm = _norm(m)
        if len(norm.replace(".", "")) >= _MIN_DIGITS:
            out.append(norm)
    return out


@dataclass
class GroundednessReport:
    ticker: str
    n_dimensions: int
    hallucinated_ids: list[tuple[str, str]] = field(default_factory=list)  # (dim, id)
    uncited_dimensions: list[str] = field(default_factory=list)
    insufficient_with_claims: list[str] = field(default_factory=list)
    numbers_checked: int = 0
    numbers_grounded: int = 0
    ungrounded_numbers: list[tuple[str, str]] = field(default_factory=list)  # (dim, num)

    @property
    def passed(self) -> bool:
        return not self.hallucinated_ids and not self.uncited_dimensions

    @property
    def number_grounding_rate(self) -> float:
        return self.numbers_grounded / self.numbers_checked if self.numbers_checked else 1.0

    def render(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"Groundedness [{self.ticker}]: {status}",
            f"  dimensions checked        : {self.n_dimensions}",
            f"  hallucinated citation IDs : {len(self.hallucinated_ids)}"
            + (f"  {self.hallucinated_ids}" if self.hallucinated_ids else ""),
            f"  uncited real ratings      : {len(self.uncited_dimensions)}"
            + (f"  {self.uncited_dimensions}" if self.uncited_dimensions else ""),
            f"  insufficient_data w/ cites: {len(self.insufficient_with_claims)}"
            + (f"  {self.insufficient_with_claims}" if self.insufficient_with_claims else ""),
            f"  number grounding          : {self.numbers_grounded}/{self.numbers_checked}"
            f" ({self.number_grounding_rate:.0%}) traced to cited evidence",
        ]
        if self.ungrounded_numbers:
            sample = ", ".join(f"{n}({d[:14]})" for d, n in self.ungrounded_numbers[:8])
            lines.append(f"    untraced (likely derived): {sample}")
        return "\n".join(lines)


def check_groundedness(card: ThesisScorecard, evidence: list[Evidence]) -> GroundednessReport:
    valid_ids = {e.id for e in evidence}
    value_norm_by_id = {e.id: _norm(e.value) for e in evidence}

    rep = GroundednessReport(ticker=card.ticker, n_dimensions=len(card.dimensions))

    for dim in card.dimensions:
        rating = dim.rating.value
        cited = dim.evidence_ids

        for eid in cited:
            if eid not in valid_ids:
                rep.hallucinated_ids.append((dim.dimension, eid))

        if rating == "insufficient_data":
            if cited:
                rep.insufficient_with_claims.append(dim.dimension)
            continue  # no number grounding expected when there's no data

        if not cited:
            rep.uncited_dimensions.append(dim.dimension)

        cited_values = " ".join(value_norm_by_id.get(e, "") for e in cited)
        for num in _numbers(dim.rationale):
            rep.numbers_checked += 1
            if num in cited_values:
                rep.numbers_grounded += 1
            else:
                rep.ungrounded_numbers.append((dim.dimension, num))

    return rep
