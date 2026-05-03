"""
HyPA-RAG: Hybrid Parameter-Adaptive Retrieval-Augmented Generation.
Combines dense, sparse, and graph-based retrieval with fusion reranking.
Adapts retrieval parameters based on query complexity.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
import asyncio
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from rank_bm25 import BM25Okapi

from app.core.database import qdrant_manager, neo4j_manager
from app.core.config import settings
from app.core.logging import get_logger
from app.models.internal import Document, QueryComplexity, RAGSearchParams
from app.retrieval.embeddings import get_embedding_model
from app.retrieval.query_classifier import classify_query, query_classifier
from app.retrieval.rag_defender import filter_documents

logger = get_logger(__name__)


class HyPARAG:
    """
    Hybrid Parameter-Adaptive RAG (HyPA-RAG) system.

    Combines three retrieval strategies:
    1. Dense Search: Semantic similarity using Legal-BERT embeddings (Qdrant)
    2. Sparse Search: Keyword matching using BM25
    3. Graph Search: Relational knowledge using Neo4j

    Adapts parameters (top-k, weights) based on query complexity classification.
    Results are fused using weighted Reciprocal Rank Fusion (RRF).
    """

    def __init__(self):
        self.embedding_model = get_embedding_model()
        self.bm25_corpus: List[str] = []
        self.bm25_index: Optional[BM25Okapi] = None
        self.bm25_doc_ids: List[str] = []
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize HyPA-RAG by building BM25 index from Qdrant documents.
        Should be called at application startup.
        """
        if self._initialized:
            logger.debug("hypa_rag_already_initialized")
            return

        logger.info("initializing_hypa_rag_bm25_index")

        try:
            # Ensure Qdrant is connected
            client = await qdrant_manager.connect()

            # Get all documents from Qdrant for BM25 indexing
            # Use scroll to get all points
            scroll_result = client.scroll(
                collection_name=settings.qdrant_collection_name,
                limit=10000,  # Batch size
                with_payload=True,
                with_vectors=False
            )

            points, next_offset = scroll_result
            all_points = list(points)

            # Continue scrolling if there are more
            while next_offset is not None:
                scroll_result = client.scroll(
                    collection_name=settings.qdrant_collection_name,
                    offset=next_offset,
                    limit=10000,
                    with_payload=True,
                    with_vectors=False
                )
                points, next_offset = scroll_result
                all_points.extend(points)

            if not all_points:
                logger.warning("no_documents_in_qdrant_for_bm25")
                self._initialized = True
                return

            # Build BM25 corpus
            self.bm25_corpus = []
            self.bm25_doc_ids = []

            for point in all_points:
                content = point.payload.get("content", "")
                if content:
                    self.bm25_corpus.append(content)
                    self.bm25_doc_ids.append(str(point.id))

            # Tokenize and build BM25 index
            tokenized_corpus = [doc.lower().split() for doc in self.bm25_corpus]
            self.bm25_index = BM25Okapi(tokenized_corpus)

            self._initialized = True
            logger.info(
                "hypa_rag_bm25_index_built",
                document_count=len(self.bm25_corpus)
            )

        except Exception as e:
            logger.error("hypa_rag_initialization_error", error=str(e))
            # Mark as initialized to prevent retry loops, but with empty index
            self._initialized = True

    async def retrieve(
        self,
        query: str,
        trace_id: str = "unknown"
    ) -> Tuple[List[Document], QueryComplexity]:
        """
        Main retrieval method that orchestrates all search strategies.

        Args:
            query: User query string
            trace_id: Request trace ID for logging

        Returns:
            Tuple of (retrieved documents, query complexity)
        """
        # Ensure BM25 index is built
        if not self._initialized:
            await self.initialize()

        logger.info("starting_retrieval", query_length=len(query), trace_id=trace_id)

        # Classify query complexity
        complexity = classify_query(query)
        params = query_classifier.get_rag_params(complexity)

        logger.info(
            "query_classified",
            complexity=complexity.value,
            k=params.k,
            use_graph=params.use_graph,
            trace_id=trace_id
        )

        # Execute searches in parallel
        search_tasks = [
            self._dense_search(query, params.k, trace_id),
            self._sparse_search(query, params.k, trace_id)
        ]

        if params.use_graph:
            search_tasks.append(self._graph_search(query, params.k, trace_id))

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Handle exceptions
        dense_docs = results[0] if not isinstance(results[0], Exception) else []
        sparse_docs = results[1] if not isinstance(results[1], Exception) else []
        graph_docs = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else []

        # Log retrieval results
        logger.info(
            "retrieval_results",
            dense_count=len(dense_docs),
            sparse_count=len(sparse_docs),
            graph_count=len(graph_docs),
            trace_id=trace_id
        )

        # Fusion and reranking
        fused_docs = self._fusion_rerank(
            dense_docs=dense_docs,
            sparse_docs=sparse_docs,
            graph_docs=graph_docs,
            params=params
        )

        # Apply RAG Defender to filter poisoned documents
        safe_docs = filter_documents(fused_docs)

        logger.info(
            "retrieval_complete",
            final_count=len(safe_docs),
            complexity=complexity.value,
            trace_id=trace_id
        )

        return safe_docs, complexity

    async def _dense_search(
        self,
        query: str,
        k: int,
        trace_id: str
    ) -> List[Document]:
        """
        Dense semantic search using Legal-BERT embeddings in Qdrant.

        Args:
            query: User query
            k: Number of results to retrieve
            trace_id: Request trace ID

        Returns:
            List of retrieved documents
        """
        try:
            logger.debug("dense_search_start", k=k, trace_id=trace_id)

            # Generate query embedding
            query_embedding = self.embedding_model.encode_single(query)

            # Search in Qdrant
            client = qdrant_manager.client
            if client is None:
                logger.error("qdrant_client_not_initialized", trace_id=trace_id)
                return []

            search_result = client.search(
                collection_name=settings.qdrant_collection_name,
                query_vector=query_embedding.tolist(),
                limit=k
            )

            # Convert to Document objects
            documents = []
            for result in search_result:
                doc = Document(
                    id=str(result.id),
                    content=result.payload.get("content", ""),
                    metadata=result.payload.get("metadata", {}),
                    score=result.score,
                    source="qdrant"
                )
                documents.append(doc)

            logger.debug(
                "dense_search_complete",
                retrieved=len(documents),
                trace_id=trace_id
            )

            return documents

        except Exception as e:
            logger.error(
                "dense_search_error",
                error=str(e),
                error_type=type(e).__name__,
                trace_id=trace_id
            )
            return []

    async def _sparse_search(
        self,
        query: str,
        k: int,
        trace_id: str
    ) -> List[Document]:
        """
        Sparse keyword search using BM25.

        Args:
            query: User query
            k: Number of results to retrieve
            trace_id: Request trace ID

        Returns:
            List of retrieved documents
        """
        try:
            logger.debug("sparse_search_start", k=k, trace_id=trace_id)

            # Check if BM25 index is built
            if self.bm25_index is None:
                logger.warning("bm25_index_not_built", trace_id=trace_id)
                return []

            # Tokenize query
            tokenized_query = query.lower().split()

            # Get BM25 scores
            scores = self.bm25_index.get_scores(tokenized_query)

            # Get top-k indices
            top_indices = scores.argsort()[-k:][::-1]

            # Create Document objects
            documents = []
            for idx in top_indices:
                if idx < len(self.bm25_doc_ids) and scores[idx] > 0:
                    doc = Document(
                        id=self.bm25_doc_ids[idx],
                        content=self.bm25_corpus[idx],
                        metadata={},
                        score=float(scores[idx]),
                        source="bm25"
                    )
                    documents.append(doc)

            logger.debug(
                "sparse_search_complete",
                retrieved=len(documents),
                trace_id=trace_id
            )

            return documents

        except Exception as e:
            logger.error(
                "sparse_search_error",
                error=str(e),
                error_type=type(e).__name__,
                trace_id=trace_id
            )
            return []

    async def _graph_search(
        self,
        query: str,
        k: int,
        trace_id: str
    ) -> List[Document]:
        """
        Graph-based search using Neo4j for relational knowledge.

        Searches across Law, Article, and Sumula nodes using keywords
        and returns related legal content with graph context.

        Args:
            query: User query
            k: Number of results to retrieve
            trace_id: Request trace ID

        Returns:
            List of retrieved documents
        """
        try:
            logger.debug("graph_search_start", k=k, trace_id=trace_id)

            driver = neo4j_manager.driver
            if driver is None:
                logger.warning("neo4j_driver_not_initialized", trace_id=trace_id)
                return []

            # Extract keywords from query
            keywords = [word.lower() for word in query.split() if len(word) > 3][:10]

            if not keywords:
                return []

            # Search across Law, Article, and Sumula nodes
            cypher_query = """
            // Search in Articles
            CALL {
                MATCH (l:Law)-[:CONTAINS]->(a:Article)
                WHERE ANY(keyword IN $keywords WHERE toLower(a.content) CONTAINS keyword)
                RETURN a.id AS id,
                       a.content AS content,
                       l.name AS law_name,
                       l.type AS law_type,
                       'article' AS node_type,
                       a.number AS number
                LIMIT $limit
            }
            RETURN id, content, law_name, law_type, node_type, number

            UNION

            // Search in Sumulas
            CALL {
                MATCH (s:Sumula)
                WHERE ANY(keyword IN $keywords WHERE toLower(s.text) CONTAINS keyword)
                RETURN s.id AS id,
                       s.text AS content,
                       s.court AS law_name,
                       s.type AS law_type,
                       'sumula' AS node_type,
                       s.number AS number
                LIMIT $limit
            }
            RETURN id, content, law_name, law_type, node_type, number

            UNION

            // Search in Laws (by name/tags)
            CALL {
                MATCH (l:Law)
                WHERE ANY(keyword IN $keywords WHERE toLower(l.name) CONTAINS keyword)
                   OR ANY(keyword IN $keywords WHERE ANY(tag IN l.tags WHERE toLower(tag) CONTAINS keyword))
                RETURN l.id AS id,
                       l.name AS content,
                       l.name AS law_name,
                       l.type AS law_type,
                       'law' AS node_type,
                       '' AS number
                LIMIT $limit
            }
            RETURN id, content, law_name, law_type, node_type, number
            """

            async with driver.session(database=settings.neo4j_database) as session:
                result = await session.run(
                    cypher_query,
                    keywords=keywords,
                    limit=k
                )

                records = [record async for record in result]

                # Convert to Document objects
                documents = []
                for i, record in enumerate(records):
                    metadata = {
                        "law_name": record.get("law_name", ""),
                        "law_type": record.get("law_type", ""),
                        "node_type": record.get("node_type", ""),
                        "number": record.get("number", ""),
                        "source": "neo4j_graph"
                    }

                    doc = Document(
                        id=str(record["id"]),
                        content=record["content"] or "",
                        metadata=metadata,
                        score=1.0 / (i + 1),  # Ranking by position
                        source="neo4j"
                    )
                    documents.append(doc)

            logger.debug(
                "graph_search_complete",
                retrieved=len(documents),
                trace_id=trace_id
            )

            return documents[:k]  # Ensure we don't exceed k

        except Exception as e:
            logger.warning(
                "graph_search_error",
                error=str(e),
                error_type=type(e).__name__,
                trace_id=trace_id
            )
            return []

    def _fusion_rerank(
        self,
        dense_docs: List[Document],
        sparse_docs: List[Document],
        graph_docs: List[Document],
        params: RAGSearchParams
    ) -> List[Document]:
        """
        Fuse results from multiple searches using Reciprocal Rank Fusion (RRF).

        Args:
            dense_docs: Documents from dense search
            sparse_docs: Documents from sparse search
            graph_docs: Documents from graph search
            params: RAG search parameters with weights

        Returns:
            Fused and reranked list of documents
        """
        # Reciprocal Rank Fusion constant
        K_RRF = 60

        # Calculate RRF scores for each document
        rrf_scores: Dict[str, float] = defaultdict(float)
        doc_map: Dict[str, Document] = {}

        # Process dense results
        for rank, doc in enumerate(dense_docs, start=1):
            rrf_score = params.dense_weight / (K_RRF + rank)
            rrf_scores[doc.id] += rrf_score
            doc_map[doc.id] = doc

        # Process sparse results
        for rank, doc in enumerate(sparse_docs, start=1):
            rrf_score = params.sparse_weight / (K_RRF + rank)
            rrf_scores[doc.id] += rrf_score
            if doc.id not in doc_map:
                doc_map[doc.id] = doc

        # Process graph results
        for rank, doc in enumerate(graph_docs, start=1):
            rrf_score = params.graph_weight / (K_RRF + rank)
            rrf_scores[doc.id] += rrf_score
            if doc.id not in doc_map:
                doc_map[doc.id] = doc

        # Sort by RRF score
        sorted_doc_ids = sorted(
            rrf_scores.keys(),
            key=lambda doc_id: rrf_scores[doc_id],
            reverse=True
        )

        # Create final ranked list with updated scores
        fused_docs = []
        for doc_id in sorted_doc_ids[:params.k]:
            doc = doc_map[doc_id]
            doc.score = rrf_scores[doc_id]  # Update with fusion score
            fused_docs.append(doc)

        logger.debug(
            "fusion_complete",
            total_unique_docs=len(doc_map),
            final_docs=len(fused_docs)
        )

        return fused_docs

    async def index_documents(self, documents: List[Document]) -> None:
        """
        Index documents for BM25 sparse search.
        This should be called during initialization or data loading.

        Args:
            documents: Documents to index
        """
        logger.info("indexing_documents_for_bm25", count=len(documents))

        self.bm25_corpus = [doc.content for doc in documents]
        self.bm25_doc_ids = [doc.id for doc in documents]

        # Tokenize corpus
        tokenized_corpus = [doc.lower().split() for doc in self.bm25_corpus]

        # Build BM25 index
        self.bm25_index = BM25Okapi(tokenized_corpus)

        logger.info("bm25_indexing_complete")


# Global instance
hypa_rag = HyPARAG()
