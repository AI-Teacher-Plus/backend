import uuid
from django.db import models
from django.conf import settings
from pgvector.django import VectorField, HnswIndex

class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # default
    title = models.CharField(max_length=255)
    source = models.CharField(max_length=50, default="upload")
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="documents", on_delete=models.CASCADE, null=True
    )
    def __str__(self):
        return f"{self.title} ({self.id})"

class Chunk(models.Model):
    id = models.BigAutoField(primary_key=True)
    document = models.ForeignKey(Document, related_name="chunks", on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    text = models.TextField()
    embedding = VectorField(dimensions=1536, null=True)  # 1536 p/ gemini-embedding-001

    class Meta:
        indexes = [
            HnswIndex(
                name="chunk_embedding_hsnw_cosine",
                fields=["embedding"],
                m=16, ef_construction=200,
                opclasses=["vector_cosine_ops"]
            )
        ]
