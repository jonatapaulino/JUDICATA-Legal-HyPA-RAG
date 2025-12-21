"""
Seed script for Qdrant vector database.
Populates with sample legal documents and their embeddings.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.database import qdrant_manager
from app.core.config import settings
from app.retrieval.embeddings import get_embedding_model
from app.models.internal import Document
from qdrant_client.models import PointStruct


# Sample legal documents
SAMPLE_DOCUMENTS = [
    {
        "id": "doc_001",
        "content": "Lei 8.245/91, Art. 9º, III - A locação também poderá ser desfeita: III - por falta de pagamento do aluguel e demais encargos. A inadimplência superior a 3 meses configura infração contratual grave que autoriza a rescisão unilateral do contrato de locação.",
        "metadata": {
            "source": "lei",
            "citation": "Brasil. Lei 8.245/91, Art. 9º, III",
            "date": "1991-10-18",
            "subject": "locação"
        }
    },
    {
        "id": "doc_002",
        "content": "REsp 1.623.847/SP - RECURSO ESPECIAL. LOCAÇÃO. DESPEJO POR FALTA DE PAGAMENTO. INADIMPLÊNCIA PROLONGADA. O Superior Tribunal de Justiça firmou entendimento de que a inadimplência prolongada, superior a três meses, autoriza a rescisão do contrato locatício, independentemente de notificação prévia quando há cláusula resolutiva expressa.",
        "metadata": {
            "source": "jurisprudencia",
            "citation": "STJ, REsp 1.623.847/SP",
            "court": "STJ",
            "date": "2017-03-15",
            "subject": "locação, despejo"
        }
    },
    {
        "id": "doc_003",
        "content": "Código Civil, Art. 186 - Aquele que, por ação ou omissão voluntária, negligência ou imprudência, violar direito e causar dano a outrem, ainda que exclusivamente moral, comete ato ilícito. Este artigo estabelece os requisitos para configuração da responsabilidade civil.",
        "metadata": {
            "source": "lei",
            "citation": "Brasil. Código Civil, Art. 186",
            "date": "2002-01-10",
            "subject": "responsabilidade civil"
        }
    },
    {
        "id": "doc_004",
        "content": "Constituição Federal, Art. 5º, LIV - Ninguém será privado da liberdade ou de seus bens sem o devido processo legal. O devido processo legal é garantia fundamental que assegura aos litigantes, em processo judicial ou administrativo, o contraditório e a ampla defesa.",
        "metadata": {
            "source": "constituição",
            "citation": "Constituição Federal, Art. 5º, LIV",
            "date": "1988-10-05",
            "subject": "devido processo legal"
        }
    },
    {
        "id": "doc_005",
        "content": "Súmula 283 do STF - É inadmissível o recurso extraordinário, quando a decisão recorrida assenta em mais de um fundamento suficiente e o recurso não abrange todos eles. Esta súmula estabelece requisito de admissibilidade para recursos extraordinários.",
        "metadata": {
            "source": "súmula",
            "citation": "STF, Súmula 283",
            "court": "STF",
            "subject": "recurso extraordinário"
        }
    },
    {
        "id": "doc_006",
        "content": "Lei 13.105/15 (CPC), Art. 489, § 1º - Não se considera fundamentada qualquer decisão judicial, seja ela interlocutória, sentença ou acórdão, que: I - se limitar à indicação, à reprodução ou à paráfrase de ato normativo, sem explicar sua relação com a causa ou a questão decidida.",
        "metadata": {
            "source": "lei",
            "citation": "Brasil. CPC, Art. 489, § 1º",
            "date": "2015-03-16",
            "subject": "fundamentação de decisões"
        }
    }
]


async def seed_qdrant():
    """Seed Qdrant with sample documents."""
    print("🌱 Starting Qdrant seeding...")

    # Connect to Qdrant
    print("📡 Connecting to Qdrant...")
    client = await qdrant_manager.connect()

    # Load embedding model
    print("🤖 Loading embedding model...")
    embedding_model = get_embedding_model()

    # Generate embeddings for all documents
    print(f"📝 Generating embeddings for {len(SAMPLE_DOCUMENTS)} documents...")
    texts = [doc["content"] for doc in SAMPLE_DOCUMENTS]
    embeddings = embedding_model.encode(texts, show_progress=True)

    # Create points
    points = []
    for i, doc in enumerate(SAMPLE_DOCUMENTS):
        point = PointStruct(
            id=doc["id"],
            vector=embeddings[i].tolist(),
            payload={
                "content": doc["content"],
                "metadata": doc["metadata"]
            }
        )
        points.append(point)

    # Upsert points
    print(f"💾 Uploading {len(points)} points to Qdrant...")
    client.upsert(
        collection_name=settings.qdrant_collection_name,
        points=points
    )

    print(f"✅ Successfully seeded {len(points)} documents to Qdrant!")

    # Verify
    collection_info = client.get_collection(settings.qdrant_collection_name)
    print(f"📊 Collection status: {collection_info.points_count} points")


if __name__ == "__main__":
    asyncio.run(seed_qdrant())
