"""
Orchestrator using LangGraph for judicial reasoning workflow.
Implements the Plan-Execute pattern with Guardian validation.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
from typing import Literal
import time
import uuid

from langgraph.graph import StateGraph, END

from app.core.logging import get_logger
from app.agents.state import JudicialState
from app.agents.tools import retrieve_documents_tool, reason_with_lsim_tool
from app.agents.guardian import guardian
from app.reasoning.toulmin import toulmin_formatter
from app.privacy.anonymizer import anonymize_text
from app.defense.p2p_defense import P2PDefense
from app.defense.safety_validator import SafetyValidator

logger = get_logger(__name__)

# Initialize P2P Defense system
p2p_defense = P2PDefense()
safety_validator = SafetyValidator(p2p_defense=p2p_defense)


class JudicialOrchestrator:
    """
    Orchestrates the complete judicial reasoning workflow using LangGraph.

    Workflow:
    1. START -> Guardian Input Validation
    2. Retrieve Documents (HyPA-RAG)
    3. Guardian Document Validation
    4. Reason with LSIM
    5. Guardian Output Validation
    6. Format Toulmin Response
    7. Anonymize (if enabled)
    8. END
    """

    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""

        workflow = StateGraph(JudicialState)

        # Add nodes
        workflow.add_node("validate_input", self._validate_input_node)
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("validate_documents", self._validate_documents_node)
        workflow.add_node("reason", self._reason_node)
        workflow.add_node("validate_reasoning", self._validate_reasoning_node)
        workflow.add_node("format_response", self._format_response_node)
        workflow.add_node("anonymize", self._anonymize_node)

        # Define edges
        workflow.set_entry_point("validate_input")

        workflow.add_conditional_edges(
            "validate_input",
            self._check_validation,
            {
                "continue": "retrieve",
                "error": END
            }
        )

        workflow.add_edge("retrieve", "validate_documents")

        workflow.add_conditional_edges(
            "validate_documents",
            self._check_validation,
            {
                "continue": "reason",
                "error": END
            }
        )

        workflow.add_edge("reason", "validate_reasoning")

        workflow.add_conditional_edges(
            "validate_reasoning",
            self._check_validation,
            {
                "continue": "format_response",
                "error": END
            }
        )

        workflow.add_conditional_edges(
            "format_response",
            self._check_anonymization,
            {
                "anonymize": "anonymize",
                "skip": END
            }
        )

        workflow.add_edge("anonymize", END)

        return workflow.compile()

    # Node implementations

    async def _validate_input_node(self, state: JudicialState) -> JudicialState:
        """Validate user input with Guardian and P2P Defense."""
        logger.info("node_validate_input", trace_id=state["trace_id"])

        # Guardian validation
        validation = guardian.validate_input(state["query"], source="user_query")

        state["guardian_checks"].append({
            "stage": "input",
            "result": validation.model_dump()
        })

        if not validation.safe:
            state["errors"].append(f"Input validation failed: {validation.reason}")
            logger.warning("input_validation_failed", trace_id=state["trace_id"])

        # P2P Defense validation
        p2p_response = p2p_defense.get_safe_response(state["query"])
        if p2p_response:
            logger.warning("p2p_defense_triggered", trace_id=state["trace_id"])
            state["guardian_checks"].append({
                "stage": "p2p_defense",
                "result": {
                    "triggered": True,
                    "safe_response": p2p_response
                }
            })
            state["errors"].append(f"P2P Defense activated: {p2p_response}")

        return state

    async def _retrieve_node(self, state: JudicialState) -> JudicialState:
        """Retrieve documents using HyPA-RAG."""
        logger.info("node_retrieve", trace_id=state["trace_id"])

        try:
            documents, complexity = await retrieve_documents_tool(
                state["query"],
                state["trace_id"]
            )

            state["documents"] = documents
            state["query_complexity"] = complexity

        except Exception as e:
            logger.error("retrieve_node_error", error=str(e))
            state["errors"].append(f"Retrieval error: {str(e)}")

        return state

    async def _validate_documents_node(self, state: JudicialState) -> JudicialState:
        """Validate retrieved documents."""
        logger.info("node_validate_documents", trace_id=state["trace_id"])

        if not state["documents"]:
            logger.warning("no_documents_retrieved", trace_id=state["trace_id"])
            return state

        # Validate a sample of document contents
        sample_texts = [doc.content[:500] for doc in state["documents"][:3]]
        validation = guardian.validate_chain(sample_texts, context="documents")

        state["guardian_checks"].append({
            "stage": "documents",
            "result": validation.model_dump()
        })

        if not validation.safe:
            state["errors"].append(f"Document validation failed: {validation.reason}")

        return state

    async def _reason_node(self, state: JudicialState) -> JudicialState:
        """Perform LSIM reasoning."""
        logger.info("node_reason", trace_id=state["trace_id"])

        try:
            thought_trace = await reason_with_lsim_tool(
                state["query"],
                state["documents"] or [],
                state["query_complexity"],
                state["trace_id"]
            )

            state["thought_trace"] = thought_trace

        except Exception as e:
            logger.error("reason_node_error", error=str(e))
            state["errors"].append(f"Reasoning error: {str(e)}")

        return state

    async def _validate_reasoning_node(self, state: JudicialState) -> JudicialState:
        """Validate reasoning output with Guardian and P2P Defense."""
        logger.info("node_validate_reasoning", trace_id=state["trace_id"])

        if not state["thought_trace"]:
            return state

        trace = state["thought_trace"]

        # Guardian validation
        validation = guardian.validate_output(
            trace.final_conclusion,
            context="final_conclusion"
        )

        state["guardian_checks"].append({
            "stage": "reasoning",
            "result": validation.model_dump()
        })

        if not validation.safe:
            state["errors"].append(f"Reasoning validation failed: {validation.reason}")

        # P2P Defense output validation
        is_safe, reason = p2p_defense.validate_output(
            state["query"],
            trace.final_conclusion
        )

        if not is_safe:
            logger.warning("p2p_output_validation_failed", trace_id=state["trace_id"])
            state["guardian_checks"].append({
                "stage": "p2p_output",
                "result": {
                    "safe": False,
                    "reason": reason
                }
            })
            # Log but don't block - SCOT will handle final validation

        return state

    async def _format_response_node(self, state: JudicialState) -> JudicialState:
        """Format response using Toulmin model."""
        logger.info("node_format_response", trace_id=state["trace_id"])

        try:
            # Calculate processing time (placeholder - should be tracked from start)
            processing_time_ms = 0

            response = await toulmin_formatter.format(
                trace=state["thought_trace"],
                documents=state["documents"] or [],
                query=state["query"],
                trace_id=state["trace_id"],
                processing_time_ms=processing_time_ms,
                query_complexity=state["query_complexity"].value,
                anonymized=state["anonymize"]
            )

            state["final_response"] = response.model_dump()

        except Exception as e:
            logger.error("format_response_error", error=str(e))
            state["errors"].append(f"Response formatting error: {str(e)}")

        return state

    async def _anonymize_node(self, state: JudicialState) -> JudicialState:
        """Anonymize sensitive entities in the response."""
        logger.info("node_anonymize", trace_id=state["trace_id"])

        if not state["final_response"]:
            return state

        try:
            response = state["final_response"]

            # Anonymize text fields
            response["claim"] = anonymize_text(response["claim"])
            response["warrant"] = anonymize_text(response["warrant"])
            response["backing"] = anonymize_text(response["backing"])
            response["rebuttal"] = anonymize_text(response["rebuttal"])
            response["data"] = [anonymize_text(d) for d in response["data"]]

            state["final_response"] = response

        except Exception as e:
            logger.error("anonymize_node_error", error=str(e))
            state["errors"].append(f"Anonymization error: {str(e)}")

        return state

    # Conditional edge functions

    def _check_validation(self, state: JudicialState) -> Literal["continue", "error"]:
        """Check if any errors occurred in validation."""
        if state.get("errors"):
            return "error"
        return "continue"

    def _check_anonymization(self, state: JudicialState) -> Literal["anonymize", "skip"]:
        """Check if anonymization is enabled."""
        if state.get("anonymize", False):
            return "anonymize"
        return "skip"

    # Public interface

    async def adjudicate(
        self,
        query: str,
        anonymize: bool = True,
        enable_scot: bool = True,
        trace_id: str = None
    ) -> dict:
        """
        Execute the complete judicial reasoning workflow.

        Args:
            query: User query
            anonymize: Enable anonymization
            enable_scot: Enable SCOT validation
            trace_id: Optional trace ID

        Returns:
            Dictionary with final response or error
        """
        if not trace_id:
            trace_id = f"req_{uuid.uuid4().hex[:12]}"

        logger.info("orchestrator_start", trace_id=trace_id)
        start_time = time.time()

        # Initialize state
        initial_state: JudicialState = {
            "query": query,
            "trace_id": trace_id,
            "anonymize": anonymize,
            "enable_scot": enable_scot,
            "documents": None,
            "query_complexity": None,
            "thought_trace": None,
            "final_response": None,
            "errors": [],
            "guardian_checks": []
        }

        # Execute graph
        try:
            final_state = await self.graph.ainvoke(initial_state)

            processing_time = int((time.time() - start_time) * 1000)

            if final_state.get("errors"):
                logger.error(
                    "orchestrator_failed",
                    errors=final_state["errors"],
                    trace_id=trace_id
                )
                return {
                    "error": "Processing failed",
                    "details": final_state["errors"],
                    "trace_id": trace_id
                }

            logger.info(
                "orchestrator_complete",
                trace_id=trace_id,
                processing_time_ms=processing_time
            )

            # Update processing time in response
            if final_state.get("final_response"):
                final_state["final_response"]["processing_time_ms"] = processing_time

            return final_state.get("final_response") or {
                "error": "No response generated",
                "trace_id": trace_id
            }

        except Exception as e:
            logger.error("orchestrator_error", error=str(e), trace_id=trace_id)
            return {
                "error": "Orchestrator error",
                "details": str(e),
                "trace_id": trace_id
            }


# Global instance
orchestrator = JudicialOrchestrator()
