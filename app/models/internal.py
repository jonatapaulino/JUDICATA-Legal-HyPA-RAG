"""
Internal data models used within the application logic.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class ValidationResult(BaseModel):
    """Result of a security validation check."""
    safe: bool
    reason: Optional[str] = None
    blocked_patterns: Optional[List[str]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class Document(BaseModel):
    """A retrieved document."""
    id: str
    content: str
    metadata: Dict[str, Any] = {}
    score: float = 0.0
    source: str = "unknown"

class Fact(BaseModel):
    """An extracted fact."""
    text: str
    source: str
    confidence: float
    entities: List[str] = []

class Rule(BaseModel):
    """A matched legal rule."""
    text: str
    source: str
    article: Optional[str] = None
    jurisdiction: Optional[str] = None
    confidence: float

class IntermediateConclusion(BaseModel):
    """A step in the reasoning chain."""
    step: int
    premise: List[str]
    rule_applied: str
    conclusion: str
    confidence: float

class ThoughtTrace(BaseModel):
    """Complete trace of the reasoning process."""
    facts: List[Fact]
    rules: List[Rule]
    intermediate_conclusions: List[IntermediateConclusion]
    final_conclusion: str
    safety_validated: bool
    safety_issues: List[str] = []

class ReasoningContext(BaseModel):
    """Context for the reasoning engine."""
    query: str
    documents: List[Document]
    trace_id: str

class QueryComplexity(str, Enum):
    """Complexity level of a query."""
    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"

class RAGSearchParams(BaseModel):
    """Parameters for RAG retrieval."""
    k: int
    dense_weight: float
    sparse_weight: float
    graph_weight: float
    use_graph: bool

class SourceReference(BaseModel):
    """Reference to a source document."""
    document_id: str
    citation: str
    relevance_score: float
    excerpt: str
