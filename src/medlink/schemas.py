from datetime import datetime, timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class StructuredRequest(StrictModel):
    as_of: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    lookback_hours: int = Field(default=72, ge=1, le=720)
    min_delta_mg_l: float = Field(default=0, ge=0, le=10000)
    patient_id: str | None = Field(default=None, pattern=r"^P[0-9]{3,6}$")

    @field_validator("as_of")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)


class VectorRequest(StructuredRequest):
    query: str = Field(min_length=2, max_length=500)
    top_k: int = Field(default=5, ge=1, le=50)
    min_similarity: float = Field(default=0, ge=-1, le=1)
    note_kind: Literal["progress", "consult"] | None = None

    @field_validator("query")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Query must contain at least two non-whitespace characters")
        return value


class LabEvidence(StrictModel):
    id: str
    value_mg_l: float
    collected_at: datetime
    available_at: datetime
    source_value: float
    source_unit: str


class StructuredHit(StrictModel):
    patient_id: str
    encounter_id: str
    ward: str
    previous: LabEvidence
    latest: LabEvidence
    delta_mg_l: float


class NoteEvidence(StrictModel):
    chunk_id: str
    note_id: str
    note_kind: str
    recorded_at: datetime
    excerpt: str
    similarity: float


class VectorHit(StrictModel):
    patient_id: str
    encounter_id: str
    ward: str
    evidence: NoteEvidence
    crp: StructuredHit | None = None


class SearchResponse(StrictModel):
    mode: Literal["structured", "vector", "hybrid"]
    as_of: datetime
    hits: list[StructuredHit] | list[VectorHit]
    count: int
    elapsed_ms: float
    embedding_model: str | None = None
    notice: str = "Synthetic data. Similarity is not a diagnosis or a probability."
