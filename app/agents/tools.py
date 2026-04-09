"""
Tools available to the LangGraph agents.
Wraps core functionality for use in the agent workflow.

"""
from typing import List, Tuple

from app.core.logging import get_logger
from app.models.internal import Document, QueryComplexity, ReasoningContext, ThoughtTrace
from app.retrieval.hypa_rag import hypa_rag
from app.reasoning.lsim_engine import lsim_engine

logger = get_logger(__name__)


async def retrieve_documents_tool(
    query: str,
    trace_id: str
) -> Tuple[List[Document], QueryComplexity]:
    """
    Tool for retrieving relevant documents using HyPA-RAG.

    Args:
        query: User query
        trace_id: Request trace ID

    Returns:
        Tuple of (documents, query_complexity)
    """
    logger.info("tool_retrieve_documents", trace_id=trace_id)

    try:
        documents, complexity = await hypa_rag.retrieve(query, trace_id)
        return documents, complexity
    except Exception as e:
        logger.error("retrieve_documents_tool_error", error=str(e), trace_id=trace_id)
        return [], QueryComplexity.BAIXA


async def reason_with_lsim_tool(
    query: str,
    documents: List[Document],
    complexity: QueryComplexity,
    trace_id: str
) -> ThoughtTrace:
    """
    Tool for performing LSIM reasoning.

    Args:
        query: User query
        documents: Retrieved documents
        complexity: Query complexity
        trace_id: Request trace ID

    Returns:
        ThoughtTrace with complete reasoning
    """
    logger.info("tool_reason_with_lsim", trace_id=trace_id)

    try:
        context = ReasoningContext(
            query=query,
            documents=documents,
            complexity=complexity,
            trace_id=trace_id
        )

        trace = await lsim_engine.reason(context)
        return trace
    except Exception as e:
        logger.error("lsim_tool_error", error=str(e), trace_id=trace_id)
        # Return minimal trace on error
        return ThoughtTrace(
            facts=[],
            rules=[],
            intermediate_conclusions=[],
            final_conclusion="Erro ao processar raciocínio.",
            safety_validated=False,
            safety_issues=["Erro no processamento"]
        )
