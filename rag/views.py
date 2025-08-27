import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db import transaction
from .models import Document, Chunk
from .serializers import DocumentIngestSerializer
from .services.embedding import embed_batch


def simple_chunk(text: str, max_chars=1200):
    parts, buf, count = [], [], 0
    for line in text.splitlines():
        if count + len(line) > max_chars:
            parts.append("\n".join(buf)); buf, count = [], 0
        buf.append(line); count += len(line)
    if buf: parts.append("\n".join(buf))
    return parts


class IndexDocumentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        s = DocumentIngestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        doc = Document.objects.create(
            id=s.validated_data.get("id") or uuid.uuid4(),
            title=s.validated_data["title"],
            owner=request.user,
            source="upload",
        )
        chunks = simple_chunk(s.validated_data["text"])
        vectors = embed_batch(chunks)

        objs = [
            Chunk(document=doc, order=i, text=t, embedding=v)
            for i, (t, v) in enumerate(zip(chunks, vectors))
        ]
        Chunk.objects.bulk_create(objs, batch_size=200)  # sem SQL manual

        return Response({"document_id": str(doc.id), "chunks": len(objs)},
                        status=status.HTTP_201_CREATED)
