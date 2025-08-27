from django.db.models import F
from pgvector.django import CosineDistance
from rag.models import Chunk
from rag.services.embedding import embed_one


def semantic_search(query: str, k: int = 5):
    qvec = embed_one(query)
    qs = (Chunk.objects
          .exclude(embedding=None)
          .annotate(distance=CosineDistance(F("embedding"), qvec))
          .order_by("distance")
          .only("id", "text", "document", "order")
          .defer("embedding"))[:k]
    return [{"chunk_id": c.id, "doc_id": str(c.document_id), "ord": c.order,
             "text": c.text, "distance": float(c.distance)} for c in qs]
