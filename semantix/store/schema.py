"""Pydantic models for data structures."""
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ItemMeta(BaseModel):
    """Metadata for an ingested item."""

    mime: str
    bytes: int
    source: str
    raw_path: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Item(BaseModel):
    """Item payload stored in Redis."""

    id: str
    source: str
    created_at: str
    text: str
    meta: ItemMeta

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class VoteRequest(BaseModel):
    """Vote request payload."""

    label: Optional[str] = None
    delta: int = Field(default=1, ge=-1, le=1)
    quality: Optional[int] = Field(default=None, ge=-1, le=1)
    voter: str = "anonymous"


class VoteResponse(BaseModel):
    """Vote response."""

    id: str
    status: str  # "voting" | "approved" | "rejected"
    votes: Dict[str, int]
    quality: int


class IngestRequest(BaseModel):
    """Ingest request payload."""

    text: Optional[str] = None
    source: Optional[str] = None


class IngestResponse(BaseModel):
    """Ingest response."""

    id: str
    created: bool


class ItemResponse(BaseModel):
    """Item detail response."""

    item: Item
    votes: Dict[str, int]
    quality: int
    status: str
    voters: list[str]


class ModerateRequest(BaseModel):
    """Moderation request."""

    action: str = Field(..., pattern="^(approve|reject)$")


class TrainRequest(BaseModel):
    """Training job request."""

    filter_label: Optional[str] = None
    min_quality: int = 1
    target_size: Optional[int] = None
    out_dir: Optional[str] = None


class MetricsResponse(BaseModel):
    """Metrics response."""

    total_items: int
    pending_items: int
    approved_items: int
    rejected_items: int
    queue_depth: int
    ingest_rate: float  # items/sec
    approval_rate: float  # approvals/hour

