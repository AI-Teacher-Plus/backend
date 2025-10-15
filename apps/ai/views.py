import uuid
import json
import logging
import time
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db import transaction
from django.http import StreamingHttpResponse
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes # Import extend_schema and OpenApiParameter
from .models import Document, Chunk
from .serializers import (
    DocumentIngestSerializer,
    ChatRequestSerializer,
    DocumentIngestResponseSerializer,
    SearchResultSerializer,
    ChatResponseSerializer
)
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

    @extend_schema(
        operation_id="indexDocument",
        request=DocumentIngestSerializer,
        responses={201: DocumentIngestResponseSerializer, 400: DocumentIngestSerializer},
        description="Ingests a document, chunks it, embeds the chunks, and stores them."
    )
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

    @extend_schema(
        operation_id="searchDocuments",
        parameters=[
            OpenApiParameter(name='q', type=OpenApiTypes.STR, description='Search query', required=True),
            OpenApiParameter(name='k', type=OpenApiTypes.INT, description='Number of results to return', default=5),
        ],
        responses={200: SearchResultSerializer(many=True), 400: {'description': 'Missing query parameter'}},
        description="Performs a semantic search based on the query."
    )
    def get(self, request): 
        q = request.query_params.get("q", "") 
        k = int(request.query_params.get("k", "5")) 
        if not q: 
            return Response({"detail": "missing q"}, status=400) 
        rows = semantic_search(q, k) 
        return Response(rows)


class ChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="chatWithAI",
        request=ChatRequestSerializer,
        responses={200: ChatResponseSerializer, 400: ChatRequestSerializer},
        description="Sends a chat message and receives a response."
    )
    def post(self, request):
        s = ChatRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        session_id = str(uuid.uuid4())
        print(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "session_id": session_id,
            "event": "chat_request",
            "user": str(request.user),
            "messages_count": len(s.validated_data['messages']),
            "messages": s.validated_data['messages']
        }))
        reply = chat_once(request.user, s.validated_data["messages"], session_id)
        logging.info(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "session_id": session_id,
            "event": "chat_response",
            "reply_length": len(reply),
            "reply": reply
        }))
        return Response({"reply": reply}, status=status.HTTP_200_OK)
    


def encode_sse(event: str, data, event_id=None) -> str:
    """
    Encode a server-sent event with optional name and id.
    When data is a dict/list we JSON-encode to keep the contract consistent.
    """
    if isinstance(data, (dict, list)):
        payload = json.dumps(data, ensure_ascii=False)
    else:
        payload = str(data)
    lines = payload.split("\n")
    parts = []
    if event_id is not None:
        parts.append(f"id: {event_id}\n")
    if event:
        parts.append(f"event: {event}\n")
    parts.extend(f"data: {ln}\n" for ln in lines)
    parts.append("\n")
    return ''.join(parts)


class ChatSSEView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="streamChatWithAI",
        request=ChatRequestSerializer,
        responses={200: {'description': 'Server-Sent Events stream of chat response'}},
        description="Establishes a Server-Sent Events (SSE) connection for streaming chat responses."
    )
    def post(self, request):
        s = ChatRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        session_id = str(uuid.uuid4())
        print(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "session_id": session_id,
            "event": "chat_sse_request",
            "user": str(request.user),
            "messages_count": len(s.validated_data['messages']),
            "messages": s.validated_data['messages']
        }))
        # chat_stream agora emite eventos estruturados {"event": ..., "data": {...}}
        gen = chat_stream(request.user, s.validated_data["messages"], session_id)
        print(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "session_id": session_id,
            "event": "starting_sse_stream"
        }))

        def event_source():
            yield "retry: 1000\n\n"
            try:
                event_index = 0
                token_count = 0
                for packet in gen:
                    event_index += 1
                    if not isinstance(packet, dict):
                        packet = {"event": "message", "data": {"raw": packet}}
                    event_name = packet.get("event") or "message"
                    payload = packet.get("data", {})
                    if event_name == "token":
                        token_count += 1
                        preview = str(payload.get("text", ""))[:50]
                    else:
                        preview = str(payload)[:50]
                    print(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "session_id": session_id,
                        "event": "sse_event",
                        "event_name": event_name,
                        "event_index": event_index,
                        "token_count": token_count,
                        "preview": preview
                    }))
                    yield encode_sse(event_name, payload, event_id=event_index)
                print(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "session_id": session_id,
                    "event": "sse_stream_completed",
                    "total_tokens": token_count,
                    "total_events": event_index
                }))
            except Exception as e:
                print(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "session_id": session_id,
                    "event": "sse_stream_error",
                    "error": str(e)
                }))
                error_payload = {
                    "session_id": session_id,
                    "message": str(e),
                }
                yield encode_sse("error", error_payload)

        resp = StreamingHttpResponse(event_source(), content_type="text/event-stream")
        resp["Cache-Control"] = "no-cache"
        resp["X-Accel-Buffering"] = "no"  # Nginx: nÃ£o buferizar
        return resp
