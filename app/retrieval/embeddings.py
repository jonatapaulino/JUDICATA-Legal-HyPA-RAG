"""
Embedding generation using Legal-BERT for Portuguese legal text.
Provides singleton wrapper around sentence-transformers for efficient embedding generation.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingModel:
    """
    Singleton wrapper for Legal-BERT embedding model.
    Uses sentence-transformers for efficient embedding generation.
    """

    _instance: Optional["EmbeddingModel"] = None
    _model: Optional[SentenceTransformer] = None

    def __new__(cls) -> "EmbeddingModel":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_model(self) -> None:
        """
        Load the embedding model into memory.
        Only loads once (singleton pattern).
        """
        if self._model is None:
            logger.info(
                "loading_embedding_model",
                model=settings.embedding_model,
                device=settings.embedding_device
            )

            try:
                self._model = SentenceTransformer(
                    settings.embedding_model,
                    device=settings.embedding_device
                )

                # Test embedding generation
                test_embedding = self._model.encode(
                    "test",
                    convert_to_numpy=True,
                    show_progress_bar=False
                )

                logger.info(
                    "embedding_model_loaded",
                    embedding_dim=len(test_embedding),
                    expected_dim=settings.qdrant_embedding_dim
                )

                # Validate dimension
                if len(test_embedding) != settings.qdrant_embedding_dim:
                    logger.warning(
                        "embedding_dimension_mismatch",
                        actual=len(test_embedding),
                        expected=settings.qdrant_embedding_dim
                    )

            except Exception as e:
                logger.error("failed_to_load_embedding_model", error=str(e))
                raise

    def encode(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed
            batch_size: Batch size for encoding
            show_progress: Whether to show progress bar

        Returns:
            NumPy array of shape (len(texts), embedding_dim)
        """
        if self._model is None:
            self.load_model()

        logger.debug("generating_embeddings", num_texts=len(texts))

        try:
            embeddings = self._model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=show_progress,
                normalize_embeddings=True  # Normalize for cosine similarity
            )

            logger.debug(
                "embeddings_generated",
                num_embeddings=len(embeddings),
                shape=embeddings.shape
            )

            return embeddings

        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            raise

    def encode_single(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.

        Args:
            text: Text string to embed

        Returns:
            NumPy array of shape (embedding_dim,)
        """
        embeddings = self.encode([text], show_progress=False)
        return embeddings[0]

    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        return settings.qdrant_embedding_dim

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model is not None


# Global singleton instance
embedding_model = EmbeddingModel()


def get_embedding_model() -> EmbeddingModel:
    """
    Get the global embedding model instance.

    Returns:
        EmbeddingModel singleton instance
    """
    if not embedding_model.is_loaded:
        embedding_model.load_model()
    return embedding_model
