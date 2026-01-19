"""
Load tests for FastAPI endpoints.
Simulates concurrent requests to test API throughput and stability.
"""
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
class TestAPILoad:
    
    async def test_concurrent_adjudicate_requests(self):
        """
        Simulate 50 concurrent requests to /adjudicate.
        """
        # Mock the heavy orchestrator to focus on API layer overhead
        with patch("app.agents.orchestrator.orchestrator.adjudicate", new_callable=AsyncMock) as mock_adjudicate:
            
            mock_adjudicate.return_value = {
                "claim": "Decisão Teste",
                "data": ["Fato 1"],
                "warrant": "Regra 1",
                "backing": "Lei",
                "rebuttal": "",
                "qualifier": "CERTO",
                "trace_id": "trace_123",
                "processing_time_ms": 50
            }
            
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                
                # Create 50 concurrent tasks
                tasks = []
                for i in range(50):
                    payload = {
                        "query": f"Query teste {i}",
                        "anonymize": True,
                        "enable_scot": False
                    }
                    # Add API Key header since we enabled it
                    headers = {"X-API-Key": "test_key"} 
                    # Note: In test env, we might need to set the key in settings or mock verify_api_key
                    
                    tasks.append(ac.post("/adjudicate", json=payload))
                
                # We need to bypass API key check for this test or set it
                with patch("app.main.settings.api_key_enabled", False):
                     responses = await asyncio.gather(*tasks)
                
                # Check results
                assert len(responses) == 50
                for resp in responses:
                    assert resp.status_code == 200
                    assert resp.json()["claim"] == "Decisão Teste"

    async def test_concurrent_validate_requests(self):
        """
        Simulate 100 concurrent requests to /api/v1/validate (lighter endpoint).
        """
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            tasks = []
            for i in range(100):
                payload = {"text": f"Texto para validar {i}", "strict_mode": True}
                tasks.append(ac.post("/api/v1/validate", json=payload))
            
            responses = await asyncio.gather(*tasks)
            
            assert len(responses) == 100
            for resp in responses:
                if resp.status_code != 200:
                    print(f"Error response: {resp.json()}")
                assert resp.status_code == 200
                assert "safe" in resp.json()
