"""
Pytest configuration and fixtures for testing.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
import pytest
import asyncio
from typing import AsyncGenerator

from app.core.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_query():
    """Sample judicial query for testing."""
    return "Um inquilino deixou de pagar aluguel por 6 meses. O proprietário pode rescindir o contrato?"


@pytest.fixture
def sample_documents():
    """Sample documents for testing."""
    from app.models.internal import Document

    return [
        Document(
            id="test_doc_1",
            content="Lei 8.245/91, Art. 9º - A locação poderá ser desfeita por falta de pagamento.",
            metadata={"source": "lei"},
            score=0.95,
            source="qdrant"
        ),
        Document(
            id="test_doc_2",
            content="Jurisprudência: Inadimplência superior a 3 meses autoriza rescisão.",
            metadata={"source": "jurisprudencia"},
            score=0.88,
            source="qdrant"
        )
    ]
