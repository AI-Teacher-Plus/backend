import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db import transaction
from django.http import StreamingHttpResponse
from .models import Document, Chunk
from .serializers import DocumentIngestSerializer, ChatRequestSerializer
from .services.chat import chat_once, chat_stream
from .services.embedding import embed_batch
from .services.search import semantic_search


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


class SearchView(APIView): 
    permission_classes = [permissions.IsAuthenticated] 
    def get(self, request): 
        q = request.query_params.get("q", "") 
        k = int(request.query_params.get("k", "5")) 
        if not q: 
            return Response({"detail": "missing q"}, status=400) 
        rows = semantic_search(q, k) 
        return Response(rows)


class ChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        s = ChatRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        reply = chat_once(request.user, s.validated_data["messages"])
        return Response({"reply": reply}, status=status.HTTP_200_OK)
    

def sse_format(data: str) -> str:
    # cada "evento" precisa terminar com \n\n
    return f"data: {data}\n\n"

class ChatSSEView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        s = ChatRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        gen = chat_stream(request.user, s.validated_data["messages"])

        def event_source():
            yield "retry: 1000\n\n"  # client auto-reconnect hint
            try:
                for token in gen:
                    yield sse_format(token)
            except Exception as e:
                yield sse_format(f"[stream-error] {e}")

        resp = StreamingHttpResponse(event_source(), content_type="text/event-stream")
        resp["Cache-Control"] = "no-cache"
        resp["X-Accel-Buffering"] = "no"  # Nginx: não buferizar
        return resp
