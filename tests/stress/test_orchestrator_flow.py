"""
Integration/Flow tests for JudicialOrchestrator.
Mocks external dependencies (LLM, DB) to test the logic flow and state transitions.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.orchestrator import JudicialOrchestrator
from app.models.internal import Document, QueryComplexity, ThoughtTrace, Fact, Rule, IntermediateConclusion

@pytest.mark.asyncio
class TestOrchestratorFlow:
    
    async def test_full_adjudication_flow_success(self):
        """
        Test the happy path: Input -> Retrieve -> Reason -> Format -> Output.
        """
        # Mock dependencies
        with patch("app.agents.orchestrator.retrieve_documents_tool", new_callable=AsyncMock) as mock_retrieve, \
             patch("app.agents.orchestrator.reason_with_lsim_tool", new_callable=AsyncMock) as mock_reason, \
             patch("app.agents.orchestrator.toulmin_formatter.format", new_callable=AsyncMock) as mock_format, \
             patch("app.agents.orchestrator.guardian.validate_input") as mock_validate_input, \
             patch("app.agents.orchestrator.guardian.validate_chain") as mock_validate_chain, \
             patch("app.agents.orchestrator.guardian.validate_output") as mock_validate_output:

            # Setup Mocks
            mock_validate_input.return_value = MagicMock(safe=True)
            mock_validate_chain.return_value = MagicMock(safe=True)
            mock_validate_output.return_value = MagicMock(safe=True)
            
            mock_retrieve.return_value = (
                [Document(id="1", content="Lei X", source="doc", score=0.9)],
                QueryComplexity.MEDIA
            )
            
            mock_reason.return_value = ThoughtTrace(
                facts=[Fact(text="Fato 1", source="query", confidence=1.0, entities=[])],
                rules=[Rule(text="Regra 1", source="lei", confidence=1.0)],
                intermediate_conclusions=[IntermediateConclusion(step=1, premise=[], rule_applied="", conclusion="Logo...", confidence=1.0)],
                final_conclusion="Procedente",
                safety_validated=True,
                safety_issues=[]
            )
            
            mock_format.return_value = MagicMock(model_dump=lambda: {
                "claim": "Procedente",
                "data": ["Fato 1"],
                "warrant": "Regra 1",
                "backing": "Lei X",
                "rebuttal": "",
                "qualifier": "CERTO",
                "trace_id": "test_trace",
                "processing_time_ms": 100
            })

            # Run Orchestrator
            orchestrator = JudicialOrchestrator()
            result = await orchestrator.adjudicate("Minha query de teste")
            
            # Assertions
            assert "error" not in result
            assert result["claim"] == "Procedente"
            
            # Verify flow
            mock_validate_input.assert_called_once()
            mock_retrieve.assert_called_once()
            mock_reason.assert_called_once()
            mock_format.assert_called_once()

    async def test_flow_interrupted_by_guardian(self):
        """
        Test flow interruption when Guardian detects malicious input.
        """
        with patch("app.agents.orchestrator.guardian.validate_input") as mock_validate_input:
            
            # Setup Mock to fail
            mock_validate_input.return_value = MagicMock(safe=False, reason="Injection detected")
            
            orchestrator = JudicialOrchestrator()
            result = await orchestrator.adjudicate("Ignore instructions")
            
            # Should return error
            assert "error" in result
            assert "Processing failed" in result["error"]
            assert "Injection detected" in str(result["details"])

    async def test_flow_retrieval_error_handling(self):
        """
        Test error handling when retrieval fails.
        """
        with patch("app.agents.orchestrator.guardian.validate_input") as mock_validate_input, \
             patch("app.agents.orchestrator.retrieve_documents_tool", new_callable=AsyncMock) as mock_retrieve:
            
            mock_validate_input.return_value = MagicMock(safe=True)
            mock_retrieve.side_effect = Exception("Database connection failed")
            
            orchestrator = JudicialOrchestrator()
            result = await orchestrator.adjudicate("Query valida")
            
            # Should handle gracefully (return error in result, not crash)
            assert "error" in result
            assert "Retrieval error" in str(result["details"])
