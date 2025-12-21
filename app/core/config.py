"""
Configuration module using Pydantic Settings for type-safe environment variables.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses Pydantic v2 BaseSettings for validation and type safety.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    environment: str = Field(default="development", description="Environment name")
    log_level: str = Field(default="INFO", description="Logging level")
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")

    # Qdrant Configuration
    qdrant_host: str = Field(default="localhost", description="Qdrant host")
    qdrant_port: int = Field(default=6333, description="Qdrant port")
    qdrant_collection_name: str = Field(
        default="judicial_cases",
        description="Qdrant collection name"
    )
    qdrant_embedding_dim: int = Field(
        default=768,
        description="Embedding dimension (Legal-BERT)"
    )

    # Neo4j Configuration
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j connection URI"
    )
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: str = Field(default="judicial123", description="Neo4j password")
    neo4j_database: str = Field(default="neo4j", description="Neo4j database name")

    # Redis Configuration
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_password: Optional[str] = Field(default=None, description="Redis password")

    # Ollama Configuration
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL"
    )
    ollama_model: str = Field(default="saul-7b", description="Ollama model name")
    ollama_temperature: float = Field(
        default=0.1,
        description="LLM temperature for deterministic outputs"
    )
    ollama_max_tokens: int = Field(
        default=2048,
        description="Maximum tokens for LLM generation"
    )

    # Embedding Model
    embedding_model: str = Field(
        default="neuralmind/bert-large-portuguese-cased",
        description="Embedding model for Legal-BERT"
    )
    embedding_device: str = Field(
        default="cpu",
        description="Device for embeddings (cpu/cuda)"
    )

    # RAG Configuration
    rag_top_k_low: int = Field(default=3, description="Top-K for low complexity queries")
    rag_top_k_medium: int = Field(default=8, description="Top-K for medium complexity")
    rag_top_k_high: int = Field(default=15, description="Top-K for high complexity")
    rag_defender_threshold: float = Field(
        default=0.85,
        description="Cosine distance threshold for RAG Defender"
    )

    # Query Classifier
    query_classifier_short_length: int = Field(
        default=10,
        description="Token count for short queries"
    )
    query_classifier_long_length: int = Field(
        default=30,
        description="Token count for long queries"
    )

    # Guardian Configuration
    guardian_enabled: bool = Field(
        default=True,
        description="Enable Guardian Agent security layer"
    )
    guardian_strict_mode: bool = Field(
        default=True,
        description="Strict mode blocks all suspicious patterns"
    )

    # Privacy Configuration
    anonymizer_enabled: bool = Field(
        default=True,
        description="Enable automatic anonymization"
    )
    ner_model: str = Field(
        default="pt_core_news_lg",
        description="spaCy NER model for Portuguese"
    )

    # SCOT (Safety Chain-of-Thought)
    scot_enabled: bool = Field(
        default=True,
        description="Enable Safety Chain-of-Thought validation"
    )
    scot_validation_threshold: float = Field(
        default=0.9,
        description="Confidence threshold for SCOT validation"
    )

    # API Security
    api_key_enabled: bool = Field(default=False, description="Enable API key auth")
    api_key: Optional[str] = Field(
        default=None,
        description="API key for authentication"
    )
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        description="Comma-separated CORS origins"
    )

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_per_minute: int = Field(
        default=10,
        description="Max requests per minute"
    )

    # Logging
    log_format: str = Field(default="json", description="Log format (json/text)")
    log_file_path: Optional[str] = Field(
        default=None,
        description="Path to log file"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the standard levels."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v_upper

    @field_validator("embedding_device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        """Validate device is cpu or cuda."""
        if v not in {"cpu", "cuda"}:
            raise ValueError("Device must be 'cpu' or 'cuda'")
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def qdrant_url(self) -> str:
        """Construct Qdrant URL."""
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment.lower() == "development"


# Global settings instance
settings = Settings()
