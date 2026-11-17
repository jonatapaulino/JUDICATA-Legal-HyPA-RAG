#!/usr/bin/env python3
"""
Ingest curated documents with provenance (dataset/precedents/*.json) into Qdrant.

Each JSON item: id, type (sumula | tese_rg | orientacao | ...), court, number,
content, source_url, retrieved_at, status. Added in the PLOS ONE revision to
cover the health-litigation use case (Súmulas Vinculantes 60 and 61, CNJ guide
on STF Temas 6 and 1234).

Usage: python scripts/ingest_extra_corpus.py dataset/precedents/health_corpus.json
"""
import asyncio
import hashlib
import json
import sys
import uuid
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from qdrant_client.models import PointStruct, VectorParams, Distance  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import qdrant_manager  # noqa: E402
from app.retrieval.embeddings import get_embedding_model  # noqa: E402


def _uuid(*parts) -> str:
    return str(uuid.UUID(hashlib.md5("_".join(map(str, parts)).encode()).hexdigest()))


async def main(paths):
    client = await qdrant_manager.connect()
    names = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection_name not in names:
        client.create_collection(settings.qdrant_collection_name,
                                 vectors_config=VectorParams(size=settings.qdrant_embedding_dim,
                                                             distance=Distance.COSINE))
    emb = get_embedding_model()
    points = []
    for p in paths:
        for d in json.load(open(p, encoding="utf-8")):
            md = {k: v for k, v in d.items() if k not in ("content", "id")}
            md["doc_id"] = d["id"]
            md["citation"] = d["id"].replace("_", " ")
            vec = emb.encode_single(d["content"])
            points.append(PointStruct(id=_uuid("extra", d["id"]), vector=vec.tolist(),
                                      payload={"content": d["content"], "metadata": md}))
    client.upsert(collection_name=settings.qdrant_collection_name, points=points)
    print(f"ingested {len(points)} documents")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
