"""
Seed script for Neo4j graph database.
Creates sample legal knowledge graph with cases, laws, and relationships.

"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.database import neo4j_manager
from app.core.config import settings


# Sample graph data
SAMPLE_GRAPH_DATA = """
// Create Case nodes
CREATE (c1:Case {
    id: 'case_001',
    number: '0001234-56.2024.8.26.0100',
    court: 'TJSP',
    subject: 'Locação - Despejo por falta de pagamento',
    content: 'Ação de despejo por falta de pagamento. Inquilino inadimplente há 6 meses.',
    decision: 'Procedente',
    date: date('2024-01-15')
})

CREATE (c2:Case {
    id: 'case_002',
    number: '0007890-12.2023.8.26.0100',
    court: 'TJSP',
    subject: 'Locação - Renovação compulsória',
    content: 'Ação renovatória de contrato de locação comercial.',
    decision: 'Parcialmente procedente',
    date: date('2023-12-10')
})

CREATE (c3:Case {
    id: 'case_003',
    number: '0003456-78.2023.8.26.0100',
    court: 'TJSP',
    subject: 'Responsabilidade civil - Danos morais',
    content: 'Ação de indenização por danos morais decorrentes de acidente de trânsito.',
    decision: 'Procedente',
    date: date('2023-11-20')
})

// Create Law nodes
CREATE (l1:Law {
    id: 'law_001',
    citation: 'Lei 8.245/91',
    name: 'Lei do Inquilinato',
    content: 'Dispõe sobre as locações dos imóveis urbanos e os procedimentos a elas pertinentes.'
})

CREATE (l2:Law {
    id: 'law_002',
    citation: 'Código Civil, Art. 186',
    name: 'Responsabilidade Civil',
    content: 'Aquele que, por ação ou omissão voluntária, negligência ou imprudência, violar direito e causar dano a outrem, ainda que exclusivamente moral, comete ato ilícito.'
})

CREATE (l3:Law {
    id: 'law_003',
    citation: 'CPC, Art. 489',
    name: 'Fundamentação das Decisões',
    content: 'Não se considera fundamentada qualquer decisão judicial que não explicar a relação da norma com a causa.'
})

// Create Principle nodes
CREATE (p1:Principle {
    id: 'principle_001',
    name: 'Devido Processo Legal',
    content: 'Ninguém será privado da liberdade ou de seus bens sem o devido processo legal.',
    source: 'CF, Art. 5º, LIV'
})

CREATE (p2:Principle {
    id: 'principle_002',
    name: 'Boa-fé Objetiva',
    content: 'Os contratantes são obrigados a guardar, na conclusão do contrato e em sua execução, os princípios de probidade e boa-fé.',
    source: 'CC, Art. 422'
})

// Create relationships
// Cases applying Laws
MATCH (c:Case {id: 'case_001'}), (l:Law {id: 'law_001'})
CREATE (c)-[:APPLIES_LAW]->(l)

MATCH (c:Case {id: 'case_002'}), (l:Law {id: 'law_001'})
CREATE (c)-[:APPLIES_LAW]->(l)

MATCH (c:Case {id: 'case_003'}), (l:Law {id: 'law_002'})
CREATE (c)-[:APPLIES_LAW]->(l)

// Cases citing Principles
MATCH (c:Case {id: 'case_001'}), (p:Principle {id: 'principle_001'})
CREATE (c)-[:CITES_PRINCIPLE]->(p)

MATCH (c:Case {id: 'case_002'}), (p:Principle {id: 'principle_002'})
CREATE (c)-[:CITES_PRINCIPLE]->(p)

// Case precedents
MATCH (c1:Case {id: 'case_002'}), (c2:Case {id: 'case_001'})
CREATE (c1)-[:FOLLOWS_PRECEDENT]->(c2)

// Similar cases
MATCH (c1:Case {id: 'case_001'}), (c2:Case {id: 'case_002'})
CREATE (c1)-[:SIMILAR_TO]->(c2)
"""


async def seed_neo4j():
    """Seed Neo4j with sample legal knowledge graph."""
    print("🌱 Starting Neo4j seeding...")

    # Connect to Neo4j
    print("📡 Connecting to Neo4j...")
    driver = await neo4j_manager.connect()

    async with driver.session(database=settings.neo4j_database) as session:
        # Clear existing data (optional)
        print("🗑️  Clearing existing data...")
        await session.run("MATCH (n) DETACH DELETE n")

        # Execute Cypher script
        print("📝 Creating graph data...")

        # Split by semicolon and execute each statement
        statements = [s.strip() for s in SAMPLE_GRAPH_DATA.split("//") if s.strip()]

        for i, statement in enumerate(statements, 1):
            if statement and not statement.startswith("//"):
                try:
                    await session.run(statement)
                    print(f"  ✓ Executed statement {i}/{len(statements)}")
                except Exception as e:
                    print(f"  ✗ Error in statement {i}: {e}")

        # Create indexes for better performance
        print("🔍 Creating indexes...")

        indexes = [
            "CREATE INDEX case_id IF NOT EXISTS FOR (c:Case) ON (c.id)",
            "CREATE INDEX law_id IF NOT EXISTS FOR (l:Law) ON (l.id)",
            "CREATE INDEX principle_id IF NOT EXISTS FOR (p:Principle) ON (p.id)",
        ]

        for index in indexes:
            try:
                await session.run(index)
                print(f"  ✓ Index created")
            except Exception as e:
                print(f"  ℹ️  Index may already exist: {e}")

        # Verify data
        print("\n📊 Verifying data...")
        result = await session.run("""
            MATCH (n)
            RETURN labels(n)[0] as type, count(n) as count
            ORDER BY type
        """)

        records = [record async for record in result]

        print("\nGraph Statistics:")
        for record in records:
            print(f"  {record['type']}: {record['count']} nodes")

        # Count relationships
        result = await session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, count(r) as count
            ORDER BY rel_type
        """)

        records = [record async for record in result]

        if records:
            print("\nRelationships:")
            for record in records:
                print(f"  {record['rel_type']}: {record['count']} relationships")

    print("\n✅ Neo4j seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_neo4j())
