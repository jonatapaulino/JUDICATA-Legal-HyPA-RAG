"""
Query complexity classifier for adaptive RAG parameters.
Uses heuristics to classify queries as BAIXA, MEDIA, or ALTA complexity.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
import re
from typing import List, Set

from app.core.config import settings
from app.core.logging import get_logger
from app.models.internal import QueryComplexity, RAGSearchParams

logger = get_logger(__name__)


class QueryClassifier:
    """
    Classifies query complexity using heuristic rules.
    Determines appropriate RAG parameters based on complexity.
    """

    # Legal entities that indicate higher complexity
    LEGAL_ENTITIES: Set[str] = {
        "artigo", "art.", "lei", "código", "constituição", "súmula",
        "jurisprudência", "acórdão", "sentença", "recurso", "apelação",
        "agravo", "embargos", "habeas corpus", "mandado", "ação",
        "processo", "tribunal", "stf", "stj", "trf", "tjsp", "tjrj"
    }

    # Complex legal terms
    COMPLEX_TERMS: Set[str] = {
        "prescrição", "decadência", "litispendência", "coisa julgada",
        "precatório", "repercussão geral", "recurso especial",
        "recurso extraordinário", "inconstitucionalidade", "legitimidade"
    }

    def __init__(self):
        self.short_threshold = settings.query_classifier_short_length
        self.long_threshold = settings.query_classifier_long_length

    def classify(self, query: str) -> QueryComplexity:
        """
        Classify query complexity based on multiple heuristics.

        Args:
            query: User query string

        Returns:
            QueryComplexity enum (BAIXA, MEDIA, ALTA)
        """
        query_lower = query.lower()
        tokens = query.split()
        token_count = len(tokens)

        # Count legal entities and complex terms
        # BUG FIX #4: Use word boundaries to avoid substring matches (e.g., "ação" in "locação")
        import re as regex_module
        legal_entity_count = sum(
            1 for entity in self.LEGAL_ENTITIES
            if regex_module.search(r'\b' + regex_module.escape(entity) + r'\b', query_lower)
        )

        complex_term_count = sum(
            1 for term in self.COMPLEX_TERMS
            if regex_module.search(r'\b' + regex_module.escape(term) + r'\b', query_lower)
        )

        # Check for citations (e.g., "Art. 5º", "Lei 8.245/91")
        citation_count = len(re.findall(
            r'(art\.?\s*\d+|lei\s*\d+[\./]\d+|súmula\s*\d+)',
            query_lower
        ))

        # Check for multiple questions
        question_count = query.count('?')

        # Scoring system
        complexity_score = 0

        # Token count factor
        # BUG FIX: Add more weight for very long queries (>40 tokens)
        if token_count <= self.short_threshold:
            complexity_score += 0
        elif token_count <= self.long_threshold:
            complexity_score += 1
        elif token_count <= 40:
            complexity_score += 2
        else:
            complexity_score += 4  # Very long queries (>40 tokens) - forces ALTA

        # Legal entities factor
        if legal_entity_count >= 3:
            complexity_score += 2
        elif legal_entity_count >= 1:
            complexity_score += 1

        # Complex terms factor
        if complex_term_count >= 2:
            complexity_score += 2
        elif complex_term_count >= 1:
            complexity_score += 1

        # Citation factor
        if citation_count >= 2:
            complexity_score += 2
        elif citation_count >= 1:
            complexity_score += 1

        # Multiple questions factor
        if question_count > 1:
            complexity_score += 1

        # BUG FIX #1: Lower BAIXA threshold from 2 to 1
        # Queries with legal entities/citations should be at least MEDIA
        # BUG FIX #2: Citations force minimum MEDIA
        # BUG FIX #5: Lower ALTA threshold to >= 4 (was >= 5)
        if complexity_score <= 1:
            result = QueryComplexity.BAIXA
        elif complexity_score <= 3:
            result = QueryComplexity.MEDIA
        else:  # >= 4
            result = QueryComplexity.ALTA

        # Override: Any citation OR legal entity forces at least MEDIA
        if (citation_count >= 1 or legal_entity_count >= 1) and result == QueryComplexity.BAIXA:
            result = QueryComplexity.MEDIA

        logger.info(
            "query_classified",
            complexity=result.value,
            score=complexity_score,
            token_count=token_count,
            legal_entities=legal_entity_count,
            complex_terms=complex_term_count,
            citations=citation_count
        )

        return result

    def get_rag_params(self, complexity: QueryComplexity) -> RAGSearchParams:
        """
        Get RAG search parameters based on query complexity.

        Args:
            complexity: Classified query complexity

        Returns:
            RAGSearchParams with appropriate weights and k value
        """
        if complexity == QueryComplexity.BAIXA:
            return RAGSearchParams(
                k=settings.rag_top_k_low,
                dense_weight=0.3,
                sparse_weight=0.6,  # Favor exact matches for simple queries
                graph_weight=0.1,
                use_graph=False  # Skip graph search for low complexity
            )

        elif complexity == QueryComplexity.MEDIA:
            return RAGSearchParams(
                k=settings.rag_top_k_medium,
                dense_weight=0.4,
                sparse_weight=0.4,  # Balanced approach
                graph_weight=0.2,
                use_graph=True
            )

        else:  # ALTA
            return RAGSearchParams(
                k=settings.rag_top_k_high,
                dense_weight=0.35,
                sparse_weight=0.35,
                graph_weight=0.3,  # Emphasize relational knowledge
                use_graph=True
            )


# Global instance
query_classifier = QueryClassifier()


def classify_query(query: str) -> QueryComplexity:
    """
    Classify a query's complexity.

    Args:
        query: User query string

    Returns:
        QueryComplexity enum
    """
    return query_classifier.classify(query)


def get_rag_params_for_query(query: str) -> RAGSearchParams:
    """
    Get RAG parameters for a query (convenience function).

    Args:
        query: User query string

    Returns:
        RAGSearchParams with appropriate settings
    """
    complexity = classify_query(query)
    return query_classifier.get_rag_params(complexity)
