"""
LangGraph state definition for the judicial reasoning workflow.
Defines the shared state that flows through the agent graph.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
from typing import List, Optional, TypedDict, Annotated
from operator import add

from app.models.internal import Document, ThoughtTrace, QueryComplexity


class JudicialState(TypedDict):
    """
    State for the judicial reasoning workflow.

    This state is passed through all nodes in the LangGraph.
    Fields with Annotated[List, add] are accumulated across nodes.
    """
    # Input
    query: str
    trace_id: str
    anonymize: bool
    enable_scot: bool

    # Retrieval phase
    documents: Optional[List[Document]]
    query_complexity: Optional[QueryComplexity]

    # Reasoning phase
    thought_trace: Optional[ThoughtTrace]

    # Output preparation
    final_response: Optional[dict]

    # Error handling
    errors: Annotated[List[str], add]

    # Guardian validations
    guardian_checks: Annotated[List[dict], add]
