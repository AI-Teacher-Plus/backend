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
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from celery.result import AsyncResult

from setup.celery import app as celery_app
from apps.accounts.models import StudyPlan, FileRef
from .models import Document, Chunk
from .serializers import (
    DocumentIngestSerializer,
    ChatRequestSerializer,
    DocumentIngestResponseSerializer,
    SearchResultSerializer,
    ChatResponseSerializer,
    GeneratePlanRequestSerializer,
    StudyPlanSerializer,
    StudyPlanSummarySerializer,
    GenerateDayRequestSerializer,
    GenerateTasksRequestSerializer,
    PlanMaterialUploadSerializer,
    StudyTaskSerializer,
    PlanMaterialUploadResponseSerializer,
    JobStatusSerializer,
)
from .services.chat import chat_once, chat_stream
from .services.embedding import embed_batch
from .services.search import semantic_search
from .tasks import (
    generate_study_plan_task,
    generate_study_day_task,
    generate_section_tasks_task,
    ingest_material_task,
)

logger = logging.getLogger(__name__)


def _log_api_event(event: str, **payload):
    record = {"event": event, **payload}
    try:
        logger.info(json.dumps(record, default=str))
    except Exception:
        logger.info("%s | %s", event, payload)


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
        description="""
        Envia uma mensagem de chat e recebe uma resposta completa (não-streaming).

        **Uso**: Para respostas rápidas ou quando streaming não é necessário.
        **Limitações**: Não suporta tool calls interativos ou geração de plano de estudos.
        **Alternativa**: Use /api/ai/chat/sse/ para funcionalidades completas com streaming.
        """
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
        description="""
        Estabelece uma conexão Server-Sent Events (SSE) para streaming de respostas de chat.

        **Funcionalidades**:
        - Streaming em tempo real com eventos estruturados
        - Suporte a tool calls (ex: commit_user_context para onboarding)
        - Geração automática de plano de estudos após commit
        - Controle de sessão com meta-eventos

        **Eventos SSE**:
        - `meta`: Controle da sessão (started, committed, finished)
        - `token`: Fragmentos de texto gerado
        - `heartbeat`: Progresso durante tool calls
        - `error`: Tratamento de erros

        **Fluxo típico**: session_started → tokens (assistant_response) → [tool calls] → [plan generation] → session_finished
        """
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


class StudyPlanListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="listStudyPlans",
        responses={200: StudyPlanSummarySerializer(many=True)},
        description="Lista os planos de estudo do usuario autenticado.",
    )
    def get(self, request):
        _log_api_event(
            "study_plan_list_started",
            user_id=str(request.user.id),
            username=request.user.username,
        )
        plans = StudyPlan.objects.filter(user_context__user=request.user).prefetch_related("weeks")
        data = StudyPlanSummarySerializer(plans, many=True).data
        _log_api_event(
            "study_plan_list_completed",
            user_id=str(request.user.id),
            plan_count=len(data),
        )
        return Response(data)


class GenerateStudyPlanView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="generateStudyPlan",
        request=GeneratePlanRequestSerializer,
        responses={201: StudyPlanSerializer},
        description="Gera um plano de estudo + tarefas iniciais via IA, persistindo secoes e tarefas.",
    )
    def post(self, request):
        user_context = getattr(request.user, "context", None)
        if not user_context:
            return Response({"detail": "UserContext inexistente para o usuario."}, status=400)

        s = GeneratePlanRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        _log_api_event(
            "study_plan_generate_request",
            user_id=str(request.user.id),
            payload={k: v for k, v in s.validated_data.items()},
        )

        job_id = str(uuid.uuid4())
        plan = StudyPlan.objects.create(
            user_context=user_context,
            title=s.validated_data.get("title") or user_context.goal,
            status="draft",
            generation_status="pending",
            job_id=job_id,
            metadata={"requested_goal_override": s.validated_data.get("goal_override")},
        )
        generate_study_plan_task.apply_async(
            args=[job_id, str(plan.id), str(user_context.id), s.validated_data.get("goal_override"), s.validated_data.get("title")],
            queue="ai_generation",
        )
        _log_api_event(
            "study_plan_generate_enqueued",
            user_id=str(request.user.id),
            plan_id=str(plan.id),
            job_id=job_id,
        )
        serialized = StudyPlanSerializer(plan).data
        return Response(serialized, status=status.HTTP_201_CREATED)


class StudyPlanDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="getStudyPlan",
        responses={200: StudyPlanSerializer},
        description="Retorna um plano de estudo com secoes e tarefas.",
    )
    def get(self, request, plan_id):
        plan = (
            StudyPlan.objects.filter(id=plan_id, user_context__user=request.user)
            .prefetch_related("weeks__days__tasks", "rag_documents")
            .first()
        )
        if not plan:
            _log_api_event(
                "study_plan_detail_not_found",
                user_id=str(request.user.id),
                plan_id=str(plan_id),
            )
            return Response({"detail": "Plano nao encontrado."}, status=404)
        _log_api_event(
            "study_plan_detail_loaded",
            user_id=str(request.user.id),
            plan_id=str(plan.id),
            weeks=plan.weeks.count(),
        )
        return Response(StudyPlanSerializer(plan).data)


class GenerateSectionTasksView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="generateSectionTasks",
        request=GenerateTasksRequestSerializer,
        responses={201: StudyTaskSerializer(many=True)},
        description="Gera e persiste novas tarefas para uma secao especifica do plano.",
    )
    def post(self, request, plan_id):
        plan = StudyPlan.objects.filter(id=plan_id, user_context__user=request.user).first()
        if not plan:
            return Response({"detail": "Plano nao encontrado."}, status=404)

        s = GenerateTasksRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        section_id = s.validated_data["section_id"]
        _log_api_event(
            "study_plan_section_tasks_request",
            user_id=str(request.user.id),
            plan_id=str(plan.id),
            section_id=section_id,
        )

        job_id = str(uuid.uuid4())
        plan.generation_status = "pending"
        plan.last_error = ""
        plan.job_id = job_id
        plan.save(update_fields=["generation_status", "last_error", "job_id"])
        generate_section_tasks_task.apply_async(
            args=[job_id, str(plan.id), section_id, str(request.user.id)],
            queue="ai_generation",
        )
        _log_api_event(
            "study_plan_section_tasks_enqueued",
            user_id=str(request.user.id),
            plan_id=str(plan.id),
            job_id=job_id,
            section_id=section_id,
        )
        return Response({"job_id": job_id, "plan_id": str(plan.id), "section_id": section_id}, status=status.HTTP_202_ACCEPTED)


class GenerateStudyDayView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="generateStudyDay",
        request=GenerateDayRequestSerializer,
        responses={202: {"type": "object", "properties": {"job_id": {"type": "string"}, "plan_id": {"type": "string"}, "day_id": {"type": "string"}}}},
        description="Gera ou regenera as tarefas de um dia especifico do plano de forma assincrona.",
    )
    def post(self, request, plan_id, day_id):
        plan = StudyPlan.objects.filter(id=plan_id, user_context__user=request.user).first()
        if not plan:
            return Response({"detail": "Plano nao encontrado."}, status=404)
        day = plan.days.filter(id=day_id).first()
        if not day:
            return Response({"detail": "Dia nao encontrado."}, status=404)

        s = GenerateDayRequestSerializer(data=request.data or {})
        s.is_valid(raise_exception=True)

        job_id = str(uuid.uuid4())
        plan.generation_status = "pending"
        plan.last_error = ""
        plan.job_id = job_id
        plan.save(update_fields=["generation_status", "last_error", "job_id"])

        day_meta = day.metadata or {}
        day_meta.update({"generation_status": "pending", "job_id": job_id, "last_error": ""})
        day.metadata = day_meta
        day.save(update_fields=["metadata"])

        generate_study_day_task.apply_async(
            args=[job_id, str(plan.id), str(day.id), s.validated_data["reset_existing"]],
            queue="ai_generation",
        )
        _log_api_event(
            "study_plan_day_generate_enqueued",
            user_id=str(request.user.id),
            plan_id=str(plan.id),
            day_id=str(day.id),
            job_id=job_id,
        )
        return Response({"job_id": job_id, "plan_id": str(plan.id), "day_id": str(day.id)}, status=status.HTTP_202_ACCEPTED)


class StudyPlanMaterialUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="uploadStudyPlanMaterial",
        request=PlanMaterialUploadSerializer,
        responses={201: PlanMaterialUploadResponseSerializer},
        description="Faz upload de arquivo, associa ao plano e o ingere no RAG (Document + chunks).",
    )
    @transaction.atomic
    def post(self, request, plan_id):
        plan = StudyPlan.objects.filter(id=plan_id, user_context__user=request.user).first()
        if not plan:
            return Response({"detail": "Plano nao encontrado."}, status=404)

        s = PlanMaterialUploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        uploaded = s.validated_data["file"]
        job_id = str(uuid.uuid4())
        file_ref = FileRef.objects.create(file=uploaded)
        user_context = plan.user_context
        user_context.materials.add(file_ref)

        doc = Document.objects.create(
            title=s.validated_data.get("title") or uploaded.name,
            owner=request.user,
            source="study_plan_upload",
            ingest_status="pending",
            job_id=job_id,
        )
        _log_api_event(
            "study_plan_material_upload_enqueued",
            user_id=str(request.user.id),
            plan_id=str(plan.id),
            job_id=job_id,
            document_id=str(doc.id),
            file_id=str(file_ref.id),
        )

        ingest_material_task.apply_async(
            args=[job_id, str(plan.id), str(file_ref.id), str(doc.id), doc.title],
            queue="ingest",
        )

        return Response(
            {"job_id": job_id, "plan_id": str(plan.id), "file_id": str(file_ref.id), "document_id": str(doc.id)},
            status=status.HTTP_202_ACCEPTED,
        )


class JobStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="jobStatus",
        responses={200: JobStatusSerializer},
        description="Consulta status de um job Celery.",
    )
    def get(self, request, job_id):
        res = AsyncResult(job_id, app=celery_app)
        data = {"job_id": job_id, "status": res.status.lower()}
        if res.failed():
            data["error"] = str(res.result)
        if res.successful():
            try:
                data["result"] = res.result if isinstance(res.result, dict) else {"result": res.result}
            except Exception:
                data["result"] = None
        ser = JobStatusSerializer(data=data)
        ser.is_valid(raise_exception=True)
        return Response(ser.data)


class JobStreamView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="jobStatusStream",
        parameters=[
            OpenApiParameter(name="job_id", type=OpenApiTypes.STR, description="Job ID a acompanhar", required=True),
        ],
        responses={200: {"description": "SSE com status do job"}},
        description="SSE que streama mudancas de status de um job Celery.",
    )
    def get(self, request):
        job_id = request.query_params.get("job_id")
        if not job_id:
            return Response({"detail": "job_id obrigatorio"}, status=400)

        def event_source():
            res = AsyncResult(job_id, app=celery_app)
            last_status = None
            for _ in range(360):  # ~6 minutos
                status_lower = res.status.lower()
                if status_lower != last_status:
                    yield encode_sse("meta", {"job_id": job_id, "status": status_lower})
                    last_status = status_lower
                if res.ready():
                    if res.failed():
                        yield encode_sse("error", {"job_id": job_id, "message": str(res.result)})
                    else:
                        payload = res.result if isinstance(res.result, dict) else {"result": res.result}
                        yield encode_sse("result", {"job_id": job_id, **(payload or {})})
                    break
                time.sleep(1)
            else:
                yield encode_sse("meta", {"job_id": job_id, "status": "timeout"})

        resp = StreamingHttpResponse(event_source(), content_type="text/event-stream")
        resp["Cache-Control"] = "no-cache"
        resp["X-Accel-Buffering"] = "no"
        return resp
