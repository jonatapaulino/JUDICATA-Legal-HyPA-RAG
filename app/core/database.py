"""
Database connection managers for Qdrant, Neo4j, and Redis.
Provides async-safe singleton connections with health checks.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
from typing import Optional

import redis.asyncio as aioredis
from neo4j import AsyncGraphDatabase, AsyncDriver
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class QdrantManager:
    """
    Singleton manager for Qdrant vector database connections.
    Handles collection initialization and hybrid search configuration.
    """

    _instance: Optional["QdrantManager"] = None
    _client: Optional[QdrantClient] = None

    def __new__(cls) -> "QdrantManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> QdrantClient:
        """
        Connect to Qdrant and ensure collection exists.

        Returns:
            QdrantClient instance
        """
        if self._client is None:
            logger.info(
                "connecting_to_qdrant",
                host=settings.qdrant_host,
                port=settings.qdrant_port
            )

            self._client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                timeout=30
            )

            # Ensure collection exists
            await self._ensure_collection()

        return self._client

    async def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        try:
            collections = self._client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if settings.qdrant_collection_name not in collection_names:
                logger.info(
                    "creating_qdrant_collection",
                    collection=settings.qdrant_collection_name
                )

                self._client.create_collection(
                    collection_name=settings.qdrant_collection_name,
                    vectors_config=VectorParams(
                        size=settings.qdrant_embedding_dim,
                        distance=Distance.COSINE
                    )
                )

                logger.info("collection_created", collection=settings.qdrant_collection_name)
            else:
                logger.info("collection_exists", collection=settings.qdrant_collection_name)

        except Exception as e:
            logger.error("failed_to_ensure_collection", error=str(e))
            raise

    async def health_check(self) -> bool:
        """Check if Qdrant is healthy."""
        try:
            if self._client is None:
                return False
            self._client.get_collections()
            return True
        except Exception as e:
            logger.error("qdrant_health_check_failed", error=str(e))
            return False

    async def disconnect(self) -> None:
        """Close Qdrant connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("qdrant_disconnected")

    @property
    def client(self) -> Optional[QdrantClient]:
        """Get the current client instance."""
        return self._client


class Neo4jManager:
    """
    Singleton manager for Neo4j graph database connections.
    Provides async driver with connection pooling.
    """

    _instance: Optional["Neo4jManager"] = None
    _driver: Optional[AsyncDriver] = None

    def __new__(cls) -> "Neo4jManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> AsyncDriver:
        """
        Connect to Neo4j database.

        Returns:
            AsyncDriver instance
        """
        if self._driver is None:
            logger.info(
                "connecting_to_neo4j",
                uri=settings.neo4j_uri,
                database=settings.neo4j_database
            )

            self._driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60
            )

            # Verify connectivity
            await self._driver.verify_connectivity()
            logger.info("neo4j_connected")

        return self._driver

    async def health_check(self) -> bool:
        """Check if Neo4j is healthy."""
        try:
            if self._driver is None:
                return False

            await self._driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error("neo4j_health_check_failed", error=str(e))
            return False

    async def disconnect(self) -> None:
        """Close Neo4j driver."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            logger.info("neo4j_disconnected")

    @property
    def driver(self) -> Optional[AsyncDriver]:
        """Get the current driver instance."""
        return self._driver


class RedisManager:
    """
    Singleton manager for Redis connections.
    Used for caching and LangGraph state checkpointing.
    """

    _instance: Optional["RedisManager"] = None
    _client: Optional[aioredis.Redis] = None

    def __new__(cls) -> "RedisManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> aioredis.Redis:
        """
        Connect to Redis.

        Returns:
            Redis client instance
        """
        if self._client is None:
            logger.info(
                "connecting_to_redis",
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db
            )

            self._client = await aioredis.from_url(
                f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
                password=settings.redis_password,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50
            )

            # Test connection
            await self._client.ping()
            logger.info("redis_connected")

        return self._client

    async def health_check(self) -> bool:
        """Check if Redis is healthy."""
        try:
            if self._client is None:
                return False

            await self._client.ping()
            return True
        except Exception as e:
            logger.error("redis_health_check_failed", error=str(e))
            return False

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            logger.info("redis_disconnected")

    @property
    def client(self) -> Optional[aioredis.Redis]:
        """Get the current client instance."""
        return self._client


# Global singleton instances
qdrant_manager = QdrantManager()
neo4j_manager = Neo4jManager()
redis_manager = RedisManager()


async def connect_databases() -> None:
    """Connect to all databases on application startup."""
    logger.info("initializing_database_connections")

    await qdrant_manager.connect()
    await neo4j_manager.connect()
    await redis_manager.connect()

    logger.info("all_databases_connected")


async def disconnect_databases() -> None:
    """Disconnect from all databases on application shutdown."""
    logger.info("closing_database_connections")

    await qdrant_manager.disconnect()
    await neo4j_manager.disconnect()
    await redis_manager.disconnect()

    logger.info("all_databases_disconnected")


async def health_check_databases() -> dict:
    """
    Check health of all database connections.

    Returns:
        Dict with health status of each database
    """
    return {
        "qdrant": await qdrant_manager.health_check(),
        "neo4j": await neo4j_manager.health_check(),
        "redis": await redis_manager.health_check()
    }
