"""
API Request models.
"""
from typing import Optional
from pydantic import BaseModel, Field

class AdjudicateRequest(BaseModel):
    """Request for the adjudication endpoint."""
    query: str = Field(..., min_length=5, description="The legal query to adjudicate")
    anonymize: bool = Field(default=True, description="Whether to anonymize sensitive entities")
    enable_scot: bool = Field(default=True, description="Whether to enable Safety Chain-of-Thought")
    trace_id: Optional[str] = Field(default=None, description="Optional trace ID for tracking")

class HealthCheckRequest(BaseModel):
    """Request for health check (usually empty)."""
    pass

class ClassifyQueryRequest(BaseModel):
    """Request to classify query complexity."""
    query: str

class ValidateTextRequest(BaseModel):
    """Request to validate text for security."""
    text: str
    strict_mode: Optional[bool] = None
