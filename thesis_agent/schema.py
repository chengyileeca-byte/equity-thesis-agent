"""Pydantic schema for the thesis scorecard.

This schema is the anti-hallucination core of the project. Every dimension
assessment must reference `evidence_ids` drawn from the fact sheet we hand the
model — the model is structurally pushed to ground each claim in a real data
point rather than free-associating. `insufficient_data` + `data_gaps` give the
model an honest exit instead of inventing numbers to fill a dimension.
"""

from enum import Enum

from pydantic import BaseModel, Field


class Rating(str, Enum):
    strong_positive = "strong_positive"
    positive = "positive"
    neutral = "neutral"
    negative = "negative"
    strong_negative = "strong_negative"
    insufficient_data = "insufficient_data"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class DimensionAssessment(BaseModel):
    dimension: str = Field(description="The analysis dimension being assessed.")
    rating: Rating
    confidence: Confidence = Field(
        description="How well the available evidence supports this rating. "
        "Use 'low' whenever evidence is thin, stale, or indirect."
    )
    rationale: str = Field(
        description="2-4 sentences. Must be grounded strictly in the cited "
        "evidence — do not introduce numbers or facts not present in it."
    )
    evidence_ids: list[str] = Field(
        description="IDs of fact-sheet items (e.g. 'E3') that directly support "
        "this assessment. Must be non-empty unless rating is "
        "'insufficient_data'."
    )


class ThesisScorecard(BaseModel):
    ticker: str
    company_name: str
    overall_rating: Rating
    overall_confidence: Confidence
    summary: str = Field(
        description="3-5 sentence investment thesis, grounded in the evidence."
    )
    dimensions: list[DimensionAssessment]
    key_risks: list[str] = Field(
        description="Material risks supported by the evidence."
    )
    data_gaps: list[str] = Field(
        description="Important information that was NOT in the evidence and that "
        "limits the confidence of this analysis."
    )
