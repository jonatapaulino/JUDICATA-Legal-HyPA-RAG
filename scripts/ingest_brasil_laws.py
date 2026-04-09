"""
Script de Ingestão da Legislação Brasileira.
Baixa, processa e indexa os principais códigos brasileiros no Qdrant e Neo4j.

Uso:
    python scripts/ingest_brasil_laws.py
"""
import asyncio
import sys
import os
import requests
from bs4 import BeautifulSoup
from typing import List

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import qdrant_manager, neo4j_manager
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.retrieval.legislation_parser import legislation_parser, LegalChunk
from app.retrieval.embeddings import get_embedding_model

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Map of major Brazilian laws (Source: Planalto/Public Domain)
# Using stable URLs or raw text sources would be ideal. 
# For this script, we will simulate fetching from a clean source or scrape Planalto.
LAWS_TO_INGEST = [
    {
        "name": "Constituição Federal de 1988",
        "type": "CF",
        "url": "http://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
        "id": "CF88"
    },
    {
        "name": "Código Civil (Lei 10.406/2002)",
        "type": "CODIGO",
        "url": "http://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm",
        "id": "CC2002"
    },
    {
        "name": "Código de Processo Civil (Lei 13.105/2015)",
        "type": "CODIGO",
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm",
        "id": "CPC2015"
    },
    {
        "name": "Código Penal (Decreto-Lei 2.848/1940)",
        "type": "CODIGO",
        "url": "http://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm",
        "id": "CP"
    },
    {
        "name": "Código de Processo Penal (Decreto-Lei 3.689/1941)",
        "type": "CODIGO",
        "url": "http://www.planalto.gov.br/ccivil_03/decreto-lei/del3689compilado.htm",
        "id": "CPP"
    },
    {
        "name": "CLT (Decreto-Lei 5.452/1943)",
        "type": "CODIGO",
        "url": "http://www.planalto.gov.br/ccivil_03/decreto-lei/del5452.htm",
        "id": "CLT"
    },
    {
        "name": "Código Tributário Nacional (Lei 5.172/1966)",
        "type": "CODIGO",
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm",
        "id": "CTN"
    },
    {
        "name": "Código de Defesa do Consumidor (Lei 8.078/1990)",
        "type": "CODIGO",
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm",
        "id": "CDC"
    }
]

async def fetch_law_text(url: str) -> str:
    """Fetch and clean text from Planalto URL."""
    logger.info(f"Fetching {url}...")
    try:
        # In a real scenario, we would use a robust scraper or API.
        # Here we use requests + BeautifulSoup for a basic extraction.
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'windows-1252' # Planalto usually uses this encoding
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Planalto HTML is messy. Extracting all text is a heuristic.
        # A production parser would target specific <p> tags with specific classes.
        text = soup.get_text(separator='\n')
        return text
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return ""

async def ingest_laws():
    """Main ingestion process."""
    logger.info("Starting legislation ingestion pipeline...")
    
    # Connect to DBs
    await qdrant_manager.connect()
    await neo4j_manager.connect()
    
    embedding_model = get_embedding_model()
    
    total_chunks = 0
    
    for law in LAWS_TO_INGEST:
        logger.info(f"Processing {law['name']}...")
        
        # 1. Fetch
        raw_text = await fetch_law_text(law['url'])
        if not raw_text:
            continue
            
        # 2. Parse
        chunks = legislation_parser.parse_text(raw_text, law['name'], law['type'])
        logger.info(f"Parsed {len(chunks)} articles from {law['name']}")
        
        if not chunks:
            continue

        # 3. Index in Qdrant (Vector Search)
        points = []
        for i, chunk in enumerate(chunks):
            # Generate embedding
            vector = embedding_model.encode_single(chunk.full_text)
            
            # Create payload
            payload = {
                "content": chunk.full_text,
                "metadata": {
                    "law_id": law['id'],
                    "law_name": law['name'],
                    "article": chunk.article_number,
                    "type": "legislation",
                    "hierarchy": chunk.hierarchy
                }
            }
            
            # Create point ID (deterministic based on content hash would be better, using simple int here for demo)
            # Using a composite ID string for Qdrant (requires UUID or int)
            # We'll use UUID generated from string
            import uuid
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{law['id']}_{chunk.article_number}"))
            
            from qdrant_client.models import PointStruct
            points.append(PointStruct(
                id=point_id,
                vector=vector.tolist(),
                payload=payload
            ))
            
        # Batch upload to Qdrant
        client = qdrant_manager.client
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            client.upsert(
                collection_name=settings.qdrant_collection_name,
                points=batch
            )
        logger.info(f"Uploaded {len(points)} vectors to Qdrant")

        # 4. Index in Neo4j (Graph Structure)
        driver = neo4j_manager.driver
        async with driver.session(database=settings.neo4j_database) as session:
            # Create Law Node
            await session.run(
                """
                MERGE (l:Law {id: $id})
                SET l.name = $name, l.type = $type
                """,
                id=law['id'], name=law['name'], type=law['type']
            )
            
            # Create Article Nodes and Relationships
            # Using a simpler loop for clarity, batching is better for perf
            for chunk in chunks:
                await session.run(
                    """
                    MATCH (l:Law {id: $law_id})
                    MERGE (a:Article {id: $art_id})
                    SET a.number = $art_num, a.content = $content
                    MERGE (l)-[:CONTAINS]->(a)
                    """,
                    law_id=law['id'],
                    art_id=f"{law['id']}_Art_{chunk.article_number}",
                    art_num=chunk.article_number,
                    content=chunk.content
                )
        logger.info(f"Updated Graph for {law['name']}")
        
        total_chunks += len(chunks)

    logger.info(f"Ingestion complete! Total articles processed: {total_chunks}")
    
    # Cleanup
    await qdrant_manager.disconnect()
    await neo4j_manager.disconnect()

if __name__ == "__main__":
    asyncio.run(ingest_laws())
