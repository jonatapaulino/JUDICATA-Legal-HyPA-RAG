"""
Unified Legal Data Ingestor.
Coordinates ingestion from all sources into Qdrant (vector) and Neo4j (graph) databases.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""

import asyncio
import uuid
import hashlib
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

from qdrant_client.models import PointStruct, Distance, VectorParams

from .planalto_scraper import PlanaltoScraper, LegislationMetadata, BRAZILIAN_LEGISLATION_CATALOG
from .lexml_client import LexMLClient, LexMLDocument
from .stf_stj_client import STFSTJClient, Sumula, JurisprudenceDocument
from .sumulas_scraper import SumulasScraper

logger = logging.getLogger(__name__)


@dataclass
class IngestionStats:
    """Statistics for ingestion run."""
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    # Counts
    legislation_fetched: int = 0
    legislation_indexed: int = 0
    sumulas_fetched: int = 0
    sumulas_indexed: int = 0
    jurisprudence_fetched: int = 0
    jurisprudence_indexed: int = 0

    # Errors
    errors: List[str] = field(default_factory=list)

    # Chunks
    total_chunks: int = 0
    total_vectors: int = 0
    total_graph_nodes: int = 0
    total_graph_edges: int = 0

    def to_dict(self) -> Dict:
        """Convert stats to dictionary."""
        return {
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': (self.completed_at - self.started_at).total_seconds() if self.completed_at else None,
            'legislation': {
                'fetched': self.legislation_fetched,
                'indexed': self.legislation_indexed
            },
            'sumulas': {
                'fetched': self.sumulas_fetched,
                'indexed': self.sumulas_indexed
            },
            'jurisprudence': {
                'fetched': self.jurisprudence_fetched,
                'indexed': self.jurisprudence_indexed
            },
            'totals': {
                'chunks': self.total_chunks,
                'vectors': self.total_vectors,
                'graph_nodes': self.total_graph_nodes,
                'graph_edges': self.total_graph_edges
            },
            'errors': self.errors
        }


class UnifiedLegalIngestor:
    """
    Unified ingestor for Brazilian legal data.
    Coordinates data collection from multiple sources and indexes into vector and graph databases.
    Gracefully handles missing Neo4j by skipping graph operations.
    """

    def __init__(
        self,
        qdrant_manager,
        neo4j_manager,
        embedding_model,
        legislation_parser,
        settings
    ):
        """
        Initialize the unified ingestor.

        Args:
            qdrant_manager: Qdrant database manager
            neo4j_manager: Neo4j database manager (can be None)
            embedding_model: Embedding model for vectorization
            legislation_parser: Parser for legislation text
            settings: Application settings
        """
        self.qdrant = qdrant_manager
        self.neo4j = neo4j_manager
        self.embeddings = embedding_model
        self.parser = legislation_parser
        self.settings = settings
        self._neo4j_available = False

        # Initialize scrapers/clients
        self.planalto = PlanaltoScraper(rate_limit=1.0)
        self.lexml = LexMLClient()
        self.stf_stj = STFSTJClient()
        self.sumulas_scraper = SumulasScraper()

        # Track indexed documents to avoid duplicates
        self._indexed_ids: Set[str] = set()

    def _generate_id(self, *args) -> str:
        """Generate deterministic UUID from components."""
        content = "_".join(str(a) for a in args)
        hash_hex = hashlib.md5(content.encode()).hexdigest()
        return str(uuid.UUID(hash_hex))

    async def ingest_all(
        self,
        include_legislation: bool = True,
        include_sumulas: bool = True,
        include_jurisprudence: bool = True,
        legislation_categories: Optional[List[str]] = None,
        batch_size: int = 100
    ) -> IngestionStats:
        """
        Run complete ingestion from all sources.

        Args:
            include_legislation: Include legislation from Planalto
            include_sumulas: Include sumulas from courts
            include_jurisprudence: Include jurisprudence (future)
            legislation_categories: Filter legislation by category
            batch_size: Batch size for database operations

        Returns:
            IngestionStats with results
        """
        stats = IngestionStats()
        logger.info("Starting unified legal data ingestion...")

        try:
            # Ensure Qdrant connection (required)
            await self.qdrant.connect()

            # Try Neo4j connection (optional - graph features)
            try:
                if self.neo4j:
                    await self.neo4j.connect()
                    self._neo4j_available = True
                    logger.info("Neo4j connected - graph features enabled")
            except Exception as neo4j_err:
                self._neo4j_available = False
                logger.warning(f"Neo4j unavailable ({neo4j_err}) - continuing without graph features")

            # Ensure collection exists with correct settings
            await self._ensure_collection()

            # 1. Ingest Legislation
            if include_legislation:
                await self._ingest_legislation(
                    stats,
                    categories=legislation_categories,
                    batch_size=batch_size
                )

            # 2. Ingest Sumulas
            if include_sumulas:
                await self._ingest_sumulas(stats, batch_size=batch_size)

            # 3. Ingest Jurisprudence (placeholder for future)
            if include_jurisprudence:
                await self._ingest_jurisprudence(stats, batch_size=batch_size)

            stats.completed_at = datetime.now()
            logger.info(f"Ingestion complete! Stats: {stats.to_dict()}")

        except Exception as e:
            stats.errors.append(f"Critical error: {str(e)}")
            logger.error(f"Ingestion failed: {e}")
            raise

        return stats

    async def _ensure_collection(self):
        """Ensure Qdrant collection exists with correct configuration."""
        client = self.qdrant.client

        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.settings.qdrant_collection_name not in collection_names:
            logger.info(f"Creating collection: {self.settings.qdrant_collection_name}")
            client.create_collection(
                collection_name=self.settings.qdrant_collection_name,
                vectors_config=VectorParams(
                    size=self.settings.qdrant_embedding_dim,
                    distance=Distance.COSINE
                )
            )
        else:
            logger.info(f"Collection {self.settings.qdrant_collection_name} already exists")

    async def _ingest_legislation(
        self,
        stats: IngestionStats,
        categories: Optional[List[str]] = None,
        batch_size: int = 100
    ):
        """Ingest legislation from Planalto."""
        logger.info("Starting legislation ingestion...")

        points_batch = []
        graph_operations = []

        async for metadata, text in self.planalto.fetch_all(categories=categories):
            stats.legislation_fetched += 1

            try:
                # Parse into chunks
                chunks = self.parser.parse_text(text, metadata.name, metadata.type)
                logger.info(f"Parsed {len(chunks)} articles from {metadata.name}")

                if not chunks:
                    continue

                # Create Law node for graph
                graph_operations.append({
                    'type': 'law',
                    'data': {
                        'id': metadata.id,
                        'name': metadata.name,
                        'type': metadata.type,
                        'category': metadata.category,
                        'date': metadata.date,
                        'tags': metadata.tags
                    }
                })

                # Process each chunk
                for chunk in chunks:
                    chunk_id = self._generate_id(metadata.id, chunk.article_number)

                    if chunk_id in self._indexed_ids:
                        continue

                    # Generate embedding
                    vector = self.embeddings.encode_single(chunk.full_text)

                    # Create point for Qdrant
                    point = PointStruct(
                        id=chunk_id,
                        vector=vector.tolist(),
                        payload={
                            'content': chunk.full_text,
                            'metadata': {
                                'type': 'legislation',
                                'law_id': metadata.id,
                                'law_name': metadata.name,
                                'law_type': metadata.type,
                                'category': metadata.category,
                                'article': chunk.article_number,
                                'hierarchy': chunk.hierarchy,
                                'date': metadata.date,
                                'tags': metadata.tags
                            }
                        }
                    )
                    points_batch.append(point)
                    self._indexed_ids.add(chunk_id)

                    # Create Article node for graph
                    graph_operations.append({
                        'type': 'article',
                        'data': {
                            'id': f"{metadata.id}_Art_{chunk.article_number}",
                            'law_id': metadata.id,
                            'number': chunk.article_number,
                            'content': chunk.content[:500] if chunk.content else ''
                        }
                    })

                    stats.total_chunks += 1

                    # Batch upload
                    if len(points_batch) >= batch_size:
                        await self._upload_vectors(points_batch)
                        stats.total_vectors += len(points_batch)
                        points_batch = []

                stats.legislation_indexed += 1

            except Exception as e:
                stats.errors.append(f"Error processing {metadata.name}: {str(e)}")
                logger.error(f"Error processing {metadata.name}: {e}")

        # Upload remaining points
        if points_batch:
            await self._upload_vectors(points_batch)
            stats.total_vectors += len(points_batch)

        # Update graph
        await self._update_graph(graph_operations)
        stats.total_graph_nodes += len([op for op in graph_operations if op['type'] in ('law', 'article')])

        logger.info(f"Legislation ingestion complete: {stats.legislation_indexed} laws indexed")

    async def _ingest_sumulas(self, stats: IngestionStats, batch_size: int = 100):
        """Ingest sumulas from all courts."""
        logger.info("Starting sumulas ingestion...")

        # Fetch all sumulas
        all_sumulas = await self.sumulas_scraper.get_all_sumulas_flat()
        stats.sumulas_fetched = len(all_sumulas)
        logger.info(f"Fetched {len(all_sumulas)} sumulas")

        points_batch = []
        graph_operations = []

        for sumula in all_sumulas:
            try:
                sumula_id = self._generate_id(sumula.court, sumula.type, sumula.number)

                if sumula_id in self._indexed_ids:
                    continue

                # Create full text for embedding
                full_text = f"Sumula {sumula.number} do {sumula.court}: {sumula.text}"

                # Generate embedding
                vector = self.embeddings.encode_single(full_text)

                # Create point for Qdrant
                point = PointStruct(
                    id=sumula_id,
                    vector=vector.tolist(),
                    payload={
                        'content': full_text,
                        'metadata': {
                            'type': 'sumula',
                            'sumula_type': sumula.type,
                            'court': sumula.court,
                            'number': sumula.number,
                            'status': sumula.status,
                            'date': sumula.date,
                            'references': sumula.references
                        }
                    }
                )
                points_batch.append(point)
                self._indexed_ids.add(sumula_id)

                # Create Sumula node for graph
                graph_operations.append({
                    'type': 'sumula',
                    'data': {
                        'id': sumula.id,
                        'court': sumula.court,
                        'number': sumula.number,
                        'type': sumula.type,
                        'text': sumula.text[:500],
                        'status': sumula.status
                    }
                })

                stats.total_chunks += 1

                # Batch upload
                if len(points_batch) >= batch_size:
                    await self._upload_vectors(points_batch)
                    stats.total_vectors += len(points_batch)
                    points_batch = []

                stats.sumulas_indexed += 1

            except Exception as e:
                stats.errors.append(f"Error processing sumula {sumula.id}: {str(e)}")
                logger.error(f"Error processing sumula {sumula.id}: {e}")

        # Upload remaining points
        if points_batch:
            await self._upload_vectors(points_batch)
            stats.total_vectors += len(points_batch)

        # Update graph
        await self._update_graph(graph_operations)
        stats.total_graph_nodes += len(graph_operations)

        logger.info(f"Sumulas ingestion complete: {stats.sumulas_indexed} sumulas indexed")

    async def _ingest_jurisprudence(self, stats: IngestionStats, batch_size: int = 100):
        """Ingest jurisprudence from courts (placeholder for future implementation)."""
        logger.info("Jurisprudence ingestion not yet implemented (requires court API access)")
        # Future: Implement using STF/STJ APIs when available
        pass

    async def _upload_vectors(self, points: List[PointStruct]):
        """Upload vectors to Qdrant."""
        try:
            self.qdrant.client.upsert(
                collection_name=self.settings.qdrant_collection_name,
                points=points
            )
            logger.debug(f"Uploaded {len(points)} vectors to Qdrant")
        except Exception as e:
            logger.error(f"Error uploading vectors: {e}")
            raise

    async def _update_graph(self, operations: List[Dict]):
        """Update Neo4j graph with nodes and relationships."""
        if not operations:
            return

        if not self._neo4j_available or not self.neo4j:
            logger.debug("Skipping graph update - Neo4j not available")
            return

        driver = self.neo4j.driver

        async with driver.session(database=self.settings.neo4j_database) as session:
            for op in operations:
                try:
                    if op['type'] == 'law':
                        await session.run(
                            """
                            MERGE (l:Law {id: $id})
                            SET l.name = $name,
                                l.type = $type,
                                l.category = $category,
                                l.date = $date,
                                l.tags = $tags
                            """,
                            **op['data']
                        )

                    elif op['type'] == 'article':
                        await session.run(
                            """
                            MATCH (l:Law {id: $law_id})
                            MERGE (a:Article {id: $id})
                            SET a.number = $number,
                                a.content = $content
                            MERGE (l)-[:CONTAINS]->(a)
                            """,
                            **op['data']
                        )

                    elif op['type'] == 'sumula':
                        await session.run(
                            """
                            MERGE (s:Sumula {id: $id})
                            SET s.court = $court,
                                s.number = $number,
                                s.type = $type,
                                s.text = $text,
                                s.status = $status
                            """,
                            **op['data']
                        )

                except Exception as e:
                    logger.warning(f"Graph operation failed: {e}")

        logger.debug(f"Executed {len(operations)} graph operations")

    async def get_ingestion_status(self) -> Dict:
        """Get current status of indexed data."""
        try:
            # Get Qdrant stats
            collection_info = self.qdrant.client.get_collection(
                self.settings.qdrant_collection_name
            )
            vector_count = collection_info.points_count

            # Get Neo4j stats if available
            node_stats = {}
            edge_stats = {}

            if self._neo4j_available and self.neo4j and self.neo4j.driver:
                try:
                    driver = self.neo4j.driver
                    async with driver.session(database=self.settings.neo4j_database) as session:
                        result = await session.run("""
                            MATCH (n)
                            RETURN labels(n)[0] as type, count(n) as count
                        """)
                        node_stats = {r['type']: r['count'] async for r in result}

                        result = await session.run("""
                            MATCH ()-[r]->()
                            RETURN type(r) as type, count(r) as count
                        """)
                        edge_stats = {r['type']: r['count'] async for r in result}
                except Exception as neo4j_err:
                    logger.warning(f"Could not get Neo4j stats: {neo4j_err}")

            return {
                'vectors': vector_count,
                'nodes': node_stats,
                'edges': edge_stats,
                'indexed_ids_count': len(self._indexed_ids),
                'neo4j_available': self._neo4j_available
            }

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {'error': str(e)}

    async def clear_all_data(self):
        """Clear all indexed data (use with caution!)."""
        logger.warning("Clearing all indexed data...")

        # Clear Qdrant
        try:
            self.qdrant.client.delete_collection(self.settings.qdrant_collection_name)
            await self._ensure_collection()
        except Exception as e:
            logger.error(f"Error clearing Qdrant: {e}")

        # Clear Neo4j if available
        if self._neo4j_available and self.neo4j and self.neo4j.driver:
            try:
                driver = self.neo4j.driver
                async with driver.session(database=self.settings.neo4j_database) as session:
                    await session.run("MATCH (n) DETACH DELETE n")
            except Exception as e:
                logger.error(f"Error clearing Neo4j: {e}")

        self._indexed_ids.clear()
        logger.info("All data cleared")
