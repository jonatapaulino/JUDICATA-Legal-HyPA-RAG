"""
RAG Defender - Protection against data poisoning attacks.
Uses TF-IDF clustering to detect and filter outlier documents.

"""
from typing import List
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_distances

from app.core.config import settings
from app.core.logging import get_logger
from app.models.internal import Document

logger = get_logger(__name__)


class RAGDefender:
    """
    Defense layer against poisoned or anomalous documents in RAG pipeline.

    Uses TF-IDF vectorization and cosine distance clustering to identify
    documents that are lexically very different from the retrieved set.
    These outliers may indicate poisoning attempts.
    """

    def __init__(self, threshold: float = None):
        """
        Initialize RAG Defender.

        Args:
            threshold: Cosine distance threshold for outlier detection
                      (default from settings)
        """
        self.threshold = threshold or settings.rag_defender_threshold
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words=None,  # Keep Portuguese stopwords for now
            ngram_range=(1, 2),  # Unigrams and bigrams
            min_df=1
        )

    def filter_poisoned(self, documents: List[Document]) -> List[Document]:
        """
        Filter out potentially poisoned documents.

        Args:
            documents: List of retrieved documents

        Returns:
            Filtered list of safe documents
        """
        if len(documents) < 3:
            # Need at least 3 documents for meaningful clustering
            logger.debug(
                "skipping_rag_defender",
                reason="insufficient_documents",
                count=len(documents)
            )
            return documents

        try:
            # Extract text content
            texts = [doc.content for doc in documents]

            # Vectorize using TF-IDF
            tfidf_matrix = self.vectorizer.fit_transform(texts)

            # Calculate centroid (mean vector)
            # BUG FIX: Convert to array to avoid np.matrix deprecated issues
            centroid = np.asarray(tfidf_matrix.mean(axis=0))

            # Calculate cosine distances from centroid
            distances = cosine_distances(tfidf_matrix, centroid)

            # Filter documents
            safe_documents = []
            filtered_count = 0

            for i, (doc, distance) in enumerate(zip(documents, distances)):
                distance_value = distance[0]

                if distance_value < self.threshold:
                    safe_documents.append(doc)
                else:
                    filtered_count += 1
                    logger.warning(
                        "document_filtered_by_defender",
                        document_id=doc.id,
                        distance=float(distance_value),
                        threshold=self.threshold,
                        source=doc.source
                    )

            logger.info(
                "rag_defender_filtering_complete",
                total_documents=len(documents),
                safe_documents=len(safe_documents),
                filtered_documents=filtered_count,
                filter_rate=filtered_count / len(documents) if documents else 0
            )

            # If too many documents were filtered, it might indicate a problem
            # with the threshold or legitimate diversity in results
            if filtered_count > len(documents) * 0.5:
                logger.warning(
                    "high_filter_rate_detected",
                    filtered=filtered_count,
                    total=len(documents),
                    rate=filtered_count / len(documents)
                )

            return safe_documents

        except Exception as e:
            logger.error(
                "rag_defender_error",
                error=str(e),
                error_type=type(e).__name__
            )
            # On error, return original documents (fail-open for availability)
            return documents

    def calculate_document_similarity(
        self,
        doc1: Document,
        doc2: Document
    ) -> float:
        """
        Calculate TF-IDF cosine similarity between two documents.

        Args:
            doc1: First document
            doc2: Second document

        Returns:
            Similarity score (0-1, higher is more similar)
        """
        try:
            texts = [doc1.content, doc2.content]
            tfidf_matrix = self.vectorizer.fit_transform(texts)

            similarity = 1 - cosine_distances(
                tfidf_matrix[0:1],
                tfidf_matrix[1:2]
            )[0][0]

            return float(similarity)

        except Exception as e:
            logger.error("similarity_calculation_error", error=str(e))
            return 0.0


# Global instance
rag_defender = RAGDefender()


def filter_documents(documents: List[Document]) -> List[Document]:
    """
    Filter potentially poisoned documents (convenience function).

    Args:
        documents: List of retrieved documents

    Returns:
        Filtered list of safe documents
    """
    return rag_defender.filter_poisoned(documents)
