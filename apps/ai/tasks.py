import logging

from celery import shared_task
from django.db import transaction

from apps.accounts.models import StudyPlan, StudyContext
from apps.ai.models import Document, Chunk
from apps.ai.services.embedding import embed_batch
from apps.ai.services.study_plan_generation import (
    generate_plan_payload,
    generate_day_payload,
    generate_tasks_payload,
    persist_plan_from_payload,
    persist_tasks_for_day,
    persist_tasks_for_section,
)

logger = logging.getLogger(__name__)


def _simple_chunk(text: str, max_chars: int = 1200):
    parts, buf, count = [], [], 0
    for line in text.splitlines():
        if count + len(line) > max_chars:
            parts.append("\n".join(buf))
            buf, count = [], 0
        buf.append(line)
        count += len(line)
    if buf:
        parts.append("\n".join(buf))
    return parts


def _set_plan_status(plan: StudyPlan, status: str, error: str | None = None, job_id: str | None = None):
    plan.generation_status = status
    if job_id:
        plan.job_id = job_id
    if error:
        plan.last_error = error
    plan.save(update_fields=["generation_status", "last_error", "job_id"])


def _set_day_status(day, status: str, error: str | None = None, job_id: str | None = None):
    meta = day.metadata or {}
    meta["generation_status"] = status
    if job_id:
        meta["job_id"] = job_id
    if error is not None:
        meta["last_error"] = error
    day.metadata = meta
    day.save(update_fields=["metadata"])


@shared_task(name="ai.generate_study_plan", bind=True)
def generate_study_plan_task(self, job_id: str, plan_id: str, study_context_id: str, goal_override: str | None, title: str | None):
    plan = StudyPlan.objects.filter(id=plan_id).first()
    ctx = StudyContext.objects.filter(id=study_context_id).first()
    if not plan or not ctx:
        return {"status": "failed", "message": "Plan or StudyContext not found"}
    _set_plan_status(plan, "running", job_id=job_id, error=None)
    try:
        documents = Document.objects.filter(owner=ctx.user)
        payload = generate_plan_payload(user_context=ctx, documents=documents, goal_override=goal_override)
        with transaction.atomic():
            persist_plan_from_payload(user_context=ctx, payload=payload, title=title, documents=documents, plan=plan)
        _set_plan_status(plan, "succeeded")
        return {"status": "succeeded", "plan_id": str(plan.id)}
    except Exception as exc:
        logger.exception("Erro ao gerar plano de estudo (job %s)", job_id)
        _set_plan_status(plan, "failed", error=str(exc))
        return {"status": "failed", "message": str(exc)}


@shared_task(name="ai.generate_study_day", bind=True)
def generate_study_day_task(self, job_id: str, plan_id: str, day_id: str, reset_existing: bool = True):
    plan = StudyPlan.objects.filter(id=plan_id).first()
    day = plan.days.filter(id=day_id).first() if plan else None
    if not plan or not day:
        return {"status": "failed", "message": "Plan or day not found"}
    _set_plan_status(plan, "running", job_id=job_id, error=None)
    _set_day_status(day, "running", job_id=job_id, error=None)
    try:
        documents = plan.rag_documents.all()
        if not documents:
            documents = Document.objects.filter(owner=plan.user_context.user)
        payload = generate_day_payload(plan, day, documents)
        with transaction.atomic():
            created = persist_tasks_for_day(day, payload, reset_existing=reset_existing)
        _set_day_status(day, "succeeded", job_id=job_id, error="")
        _set_plan_status(plan, "succeeded")
        return {"status": "succeeded", "day_id": str(day.id), "tasks": [str(t.id) for t in created]}
    except Exception as exc:
        logger.exception("Erro ao gerar dia do plano (job %s)", job_id)
        _set_day_status(day, "failed", error=str(exc), job_id=job_id)
        _set_plan_status(plan, "failed", error=str(exc))
        return {"status": "failed", "message": str(exc)}


@shared_task(name="ai.generate_section_tasks", bind=True)
def generate_section_tasks_task(self, job_id: str, plan_id: str, section_id: str, user_id: str | None = None):
    plan = StudyPlan.objects.filter(id=plan_id).first()
    if not plan:
        return {"status": "failed", "message": "Plan not found"}
    _set_plan_status(plan, "running", job_id=job_id, error=None)
    try:
        documents = plan.rag_documents.all()
        if not documents:
            documents = Document.objects.filter(owner=plan.user_context.user)
        payload = generate_tasks_payload(plan, section_id=section_id, documents=documents)
        with transaction.atomic():
            created = persist_tasks_for_section(plan, section_id, payload)
        _set_plan_status(plan, "succeeded")
        return {"status": "succeeded", "tasks": [str(t.id) for t in created]}
    except Exception as exc:
        logger.exception("Erro ao gerar tarefas da secao (job %s)", job_id)
        _set_plan_status(plan, "failed", error=str(exc))
        return {"status": "failed", "message": str(exc)}


@shared_task(name="ai.ingest_material", bind=True)
def ingest_material_task(self, job_id: str, plan_id: str, file_ref_id: str, document_id: str, document_title: str):
    plan = StudyPlan.objects.filter(id=plan_id).first()
    if not plan:
        return {"status": "failed", "message": "Plan not found"}
    doc = Document.objects.filter(id=document_id).first()
    file_ref = None
    try:
        from apps.accounts.models import FileRef  # lazy import to avoid cycles
        file_ref = FileRef.objects.filter(id=file_ref_id).first()
    except Exception:
        file_ref = None
    if not doc or not file_ref:
        return {"status": "failed", "message": "Document or FileRef not found"}

    doc.ingest_status = "running"
    doc.job_id = job_id
    doc.last_error = ""
    doc.save(update_fields=["ingest_status", "job_id", "last_error"])
    try:
        file_ref.file.open("rb")
        raw = file_ref.file.read()
        file_ref.file.close()
        if not raw:
            raise ValueError("Arquivo vazio ou nao lido")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="ignore")
        chunks = _simple_chunk(text)
        vectors = embed_batch(chunks)
        objs = [Chunk(document=doc, order=i, text=t, embedding=v) for i, (t, v) in enumerate(zip(chunks, vectors))]
        Chunk.objects.bulk_create(objs, batch_size=200)
        plan.rag_documents.add(doc)
        doc.ingest_status = "succeeded"
        doc.save(update_fields=["ingest_status"])
        return {"status": "succeeded", "document_id": str(doc.id), "chunks": len(objs)}
    except Exception as exc:
        logger.exception("Erro ao ingerir material (job %s)", job_id)
        doc.ingest_status = "failed"
        doc.last_error = str(exc)
        doc.save(update_fields=["ingest_status", "last_error"])
        return {"status": "failed", "message": str(exc)}
