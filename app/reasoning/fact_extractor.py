"""
Fact extraction from queries and retrieved documents.
Uses LLM to identify and structure factual claims.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
from typing import List
from langchain_community.chat_models import ChatOllama

from app.core.config import settings
from app.core.logging import get_logger
from app.models.internal import Fact, Document

logger = get_logger(__name__)


class FactExtractor:
    """
    Extracts structured facts from unstructured text using LLM.
    Facts are the building blocks for the LSIM reasoning engine.
    """

    def __init__(self):
        self.llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.0,  # Deterministic extraction
        )

    async def extract_from_query(self, query: str) -> List[Fact]:
        """
        Extract facts from the user's query.

        Args:
            query: User query text

        Returns:
            List of extracted Fact objects
        """
        try:
            logger.debug("extracting_facts_from_query", query_length=len(query))

            prompt = f"""Você é um assistente jurídico especializado em análise de fatos.

Analise a seguinte consulta e extraia APENAS os fatos objetivos mencionados.
Um fato é uma afirmação objetiva, verificável, sem opinião ou interpretação.

Consulta: {query}

Para cada fato identificado, responda no formato:
FATO: [afirmação factual]

Se não houver fatos explícitos, responda "NENHUM FATO IDENTIFICADO"."""

            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # Parse response
            facts = []
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('FATO:'):
                    fact_text = line.replace('FATO:', '').strip()
                    if fact_text:
                        facts.append(
                            Fact(
                                text=fact_text,
                                source="user_query",
                                confidence=1.0,
                                entities=[]
                            )
                        )

            logger.info("facts_extracted_from_query", count=len(facts))
            return facts

        except Exception as e:
            logger.error("fact_extraction_error", error=str(e))
            return []

    async def extract_from_documents(
        self,
        documents: List[Document],
        query: str
    ) -> List[Fact]:
        """
        Extract facts from retrieved documents relevant to the query.

        Args:
            documents: Retrieved documents
            query: Original user query for context

        Returns:
            List of extracted Fact objects
        """
        try:
            logger.debug("extracting_facts_from_documents", doc_count=len(documents))

            # Combine top documents (limit to avoid token overflow)
            combined_text = "\n\n".join([
                f"Documento {i+1}: {doc.content[:500]}"
                for i, doc in enumerate(documents[:3])
            ])

            prompt = f"""Você é um assistente jurídico especializado em análise de precedentes.

Consulta do usuário: {query}

Documentos recuperados:
{combined_text}

Extraia os fatos relevantes mencionados nesses documentos que se relacionam com a consulta.
Foque em fatos objetivos e verificáveis.

Para cada fato, responda no formato:
FATO: [afirmação factual]
FONTE: [documento X]

Se não houver fatos relevantes, responda "NENHUM FATO IDENTIFICADO"."""

            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # Parse response
            facts = []
            current_fact = None
            current_source = None

            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('FATO:'):
                    if current_fact:
                        facts.append(
                            Fact(
                                text=current_fact,
                                source=current_source or "document",
                                confidence=0.9,
                                entities=[]
                            )
                        )
                    current_fact = line.replace('FATO:', '').strip()
                    current_source = None
                elif line.startswith('FONTE:'):
                    current_source = line.replace('FONTE:', '').strip()

            # Add last fact
            if current_fact:
                facts.append(
                    Fact(
                        text=current_fact,
                        source=current_source or "document",
                        confidence=0.9,
                        entities=[]
                    )
                )

            logger.info("facts_extracted_from_documents", count=len(facts))
            return facts

        except Exception as e:
            logger.error("document_fact_extraction_error", error=str(e))
            return []


# Global instance
fact_extractor = FactExtractor()
