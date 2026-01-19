"""
API Response models.
"""
from typing import List, Dict, Optional, Any
from enum import Enum
from pydantic import BaseModel
from app.models.internal import SourceReference

class Qualifier(str, Enum):
    """Degree of certainty in the conclusion."""
    CERTO = "CERTO"
    PROVAVEL = "PROVAVEL"
    POSSIVEL = "POSSIVEL"
    INCERTO = "INCERTO"

class ToulminResponse(BaseModel):
    """Structured response following Toulmin's argumentation model."""
    claim: str
    data: List[str]
    warrant: str
    backing: str
    rebuttal: str
    qualifier: Qualifier
    trace_id: str
    sources: List[SourceReference] = []
    processing_time_ms: int = 0
    query_complexity: str = "UNKNOWN"
    safety_validated: bool = False
    safety_warnings: List[str] = []
    anonymized: bool = False

class HealthCheckResponse(BaseModel):
    """Response for health check."""
    status: str
    databases: Dict[str, bool]
    version: str

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    trace_id: str

class ClassifyQueryResponse(BaseModel):
    """Response for query classification."""
    query: str
    complexity: str
    score: int
    rag_params: Dict[str, Any]

class ValidateTextResponse(BaseModel):
    """Response for text validation."""
    text: str
    safe: bool
    reason: Optional[str] = None
    blocked_patterns: List[str] = []

class StatusResponse(BaseModel):
    """Detailed status response."""
    api_status: str
    version: str
    environment: str
    services: Dict[str, Any]
