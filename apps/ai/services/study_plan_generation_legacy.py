import json
import logging
from typing import Any

from django.db import models, transaction
from google.genai import types

from apps.ai.client import generate
from apps.accounts.models import (
    Assessment,
    AssessmentItem,
    Flashcard,
    FlashcardSet,
    LessonContent,
    PracticeContent,
    ProjectContent,
    ReadingContent,
    ReflectionContent,
    ReviewSessionContent,
    StudyDay,
    StudyPlan,
    StudyTask,
    StudyWeek,
    StudyContext,
)

logger = logging.getLogger(__name__)


PLAN_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "plan": {
            "type": "object",
            "properties": {
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "milestone": {"type": "string"},
                            "prerequisites": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["id", "title"],
                    },
                }
            },
            "required": ["sections"],
        },
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "section_id": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["flashcards", "quiz", "lecture", "summary", "project", "external_resource"],
                    },
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "estimated_time": {"type": "integer"},
                    "difficulty": {"type": "integer"},
                    "suggested_order": {"type": "integer"},
                    "research_needed": {"type": "boolean"},
                    "content": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string"},
                            "body": {"type": "string"},
                            "cards": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "front": {"type": "string"},
                                    },
                                },
                            },
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "prompt": {"type": "string"},
                                    },
                                },
                            },
                            "resources": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                    "prerequisites": {"type": "array", "items": {"type": "string"}},
                    "dependencies": {"type": "array", "items": {"type": "string"}},
                    "assessment_target": {"type": "string"},
                },
                "required": ["id", "section_id", "type", "title"],
            },
        },
    },
    "required": ["plan", "tasks"],
}


TASKS_ONLY_SCHEMA = {
    "type": "object",
    "properties": {
        "tasks": PLAN_RESPONSE_SCHEMA["properties"]["tasks"],
    },
    "required": ["tasks"],
}


DAY_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "day": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "focus": {"type": "string"},
                "target_minutes": {"type": "integer"},
                "summary": {"type": "string"},
                "metadata": {"type": "object"},
            },
        },
        "tasks": PLAN_RESPONSE_SCHEMA["properties"]["tasks"],
    },
    "required": ["day", "tasks"],
}


SYSTEM_PROMPT = """
Voce e um planejador de estudos em pt-BR. Gere um esquema de plano + tarefas com estrutura de JSON definida.
Priorize clareza, ids estaveis e conteudo usavel pelo front-end (flashcards, quizzes, resumos/lectures e recursos externos pesquisaveis).
Considere materiais proprios do usuario para RAG quando sugerir ou gerar resumos.
""".strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _map_task_type(raw: str | None) -> str:
    mapping = {
        "flashcards": "flashcards",
        "quiz": "assessment",
        "test": "assessment",
        "lecture": "lesson",
        "summary": "lesson",
        "project": "project",
    }
    if not raw:
        return "other"
    return mapping.get(raw.lower(), "other")


def _extract_resources(task: dict) -> list:
    resources = []
    content = task.get("content") or {}
    if task.get("type") == "external_resource":
        url = content.get("url")
        if url:
            resources.append({"url": url, "title": content.get("title") or task.get("title")})
        if content.get("fallback_if_unavailable"):
            resources.append({"fallback": content["fallback_if_unavailable"]})
    return resources


def _task_metadata(task: dict) -> dict:
    meta = {
        "section_id": task.get("section_id"),
        "task_schema_id": task.get("id"),
        "difficulty": task.get("difficulty"),
        "research_needed": task.get("research_needed"),
        "assessment_target": task.get("assessment_target"),
        "prerequisites": task.get("prerequisites") or [],
        "dependencies": task.get("dependencies") or [],
        "content": task.get("content") or {},
    }
    return {k: v for k, v in meta.items() if v not in [None, ""]}


def _ensure_week(plan: StudyPlan, index: int = 1, title: str | None = None) -> StudyWeek:
    week = plan.weeks.filter(week_index=index).first()
    if week:
        return week
    return StudyWeek.objects.create(
        plan=plan,
        week_index=index,
        title=title or f"Week {index}",
        status="active" if index == 1 else "pending",
    )


def _create_task_content(task: StudyTask, task_payload: dict):
    content = task_payload.get("content") or {}
    raw_type = (task_payload.get("type") or "").lower()
    if raw_type in {"lesson", "lecture", "summary"}:
        LessonContent.objects.create(
            task=task,
            summary=content.get("summary") or task.description,
            body=content.get("body") or content.get("text") or "",
            key_points=content.get("key_points") or [],
            source_refs=content.get("source_refs") or [],
        )
    elif raw_type in {"reading", "external_resource"}:
        resources = content.get("resources")
        if not resources and (content.get("url") or content.get("title")):
            resources = [content]
        ReadingContent.objects.create(
            task=task,
            overview=content.get("rationale") or content.get("overview") or task.description,
            instructions=content.get("how_to_use") or "",
            resources=resources or [],
            generated_text=content.get("summary") or "",
        )
    elif raw_type == "practice":
        PracticeContent.objects.create(
            task=task,
            prompt=content.get("prompt") or task.description or task.title,
            expected_output=content.get("expected_output") or "",
            rubric=content.get("rubric") or {},
            hints=content.get("hints") or [],
        )
    elif raw_type == "project":
        ProjectContent.objects.create(
            task=task,
            brief=content.get("brief") or task.description or task.title,
            deliverables=content.get("deliverables") or [],
            evaluation=content.get("evaluation") or "",
            resources=content.get("resources") or [],
        )
    elif raw_type in {"reflection"}:
        ReflectionContent.objects.create(
            task=task,
            prompt=content.get("prompt") or task.description or task.title,
            guidance=content.get("guidance") or content.get("instructions") or "",
        )
    elif raw_type in {"review"}:
        ReviewSessionContent.objects.create(
            task=task,
            topics=content.get("topics") or [],
            strategy=content.get("strategy") or content.get("instructions") or "",
            follow_up=content.get("follow_up") or "",
        )
    elif raw_type == "flashcards":
        card_set = FlashcardSet.objects.create(
            task=task,
            title=content.get("title") or task.title,
            description=content.get("description") or task.description,
            tags=content.get("tags") or [],
        )
        for card in content.get("cards") or []:
            Flashcard.objects.create(
                card_set=card_set,
                front=card.get("front") or "",
                back=card.get("back") or "",
                hints=card.get("hints") or [],
                tags=card.get("tags") or [],
                difficulty=_safe_int(card.get("difficulty"), 1),
            )
    elif raw_type in {"quiz", "test", "assessment"}:
        time_limit = _safe_int(content.get("time_limit_minutes"), 0) if content.get("time_limit_minutes") is not None else None
        time_limit = time_limit or None
        assessment = Assessment.objects.create(
            task=task,
            title=task.title,
            description=task.description,
            assessment_type="test" if raw_type == "test" else "quiz",
            passing_score=content.get("passing_score"),
            time_limit_minutes=time_limit,
            metadata={k: v for k, v in content.items() if k not in {"items"}},
        )
        for item in content.get("items") or []:
            AssessmentItem.objects.create(
                assessment=assessment,
                item_type=item.get("type") or "mcq",
                prompt=item.get("question") or item.get("prompt") or "",
                choices=item.get("choices") or [],
                answer={"answer": item.get("answer"), "explanation": item.get("explanation")},
                explanation=item.get("explanation") or "",
                difficulty=_safe_int(item.get("difficulty"), 1),
                metadata={k: v for k, v in item.items() if k not in {"type", "question", "prompt", "choices", "answer", "explanation", "difficulty"}},
            )


def _format_user_context(ctx: StudyContext) -> str:
    return "\n".join(
        [
            f"- Persona: {ctx.persona}",
            f"- Objetivo: {ctx.goal}",
            f"- Prazo: {ctx.deadline}",
            f"- Tempo semanal (h): {ctx.weekly_time_hours}",
            f"- Rotina: {ctx.study_routine}",
            f"- Background: {ctx.background_level}",
            f"- Interesses: {', '.join(ctx.interests or [])}",
            f"- Preferencias de formato: {', '.join(ctx.preferences_formats or [])}",
            f"- Idioma: {ctx.preferences_language}",
        ]
    )


def _format_documents(docs) -> str:
    if not docs:
        return "Nenhum material proprio enviado pelo usuario."
    lines = []
    for d in docs:
        lines.append(f"- {d.title} ({d.id})")
    return "\n".join(lines)


def _load_json_response(resp) -> dict:
    payload = getattr(resp, "text", "") or ""
    if not payload and getattr(resp, "candidates", None):
        first = resp.candidates[0]
        text_parts = [getattr(p, "text", "") for p in getattr(first.content, "parts", []) or []]
        payload = "\n".join([p for p in text_parts if p])
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        logger.error("Falha ao decodificar JSON do modelo: %s", exc, exc_info=True)
        raise


def generate_plan_payload(user_context: StudyContext, documents, goal_override: str | None = None) -> dict:
    goal_line = goal_override or user_context.goal
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "Regras de formato:\n"
        "- Responda apenas com JSON seguindo o schema definido.\n"
        "- ids devem ser curtos e estaveis (ex.: s1, t1, c1).\n"
        "- Para flashcards/testes inclua conteudo completo em `content`.\n"
        "- Para recursos externos, inclua url, rationale, how_to_use e fallback.\n\n"
        f"Contexto do usuario:\n{_format_user_context(user_context)}\n"
        f"Objetivo atual: {goal_line}\n"
        f"Materiais do usuario (RAG):\n{_format_documents(documents)}\n"
        "Gere 4-6 secoes enxutas com milestones claros e 2-4 tarefas por secao.\n"
        "Respeite o tempo semanal e niveis declarados.\n"
    )
    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    resp = generate(contents=contents, schema=PLAN_RESPONSE_SCHEMA)
    return _load_json_response(resp)


def generate_tasks_payload(plan: StudyPlan, section_id: str, documents) -> dict:
    existing_sections = (plan.metadata or {}).get("schema", {}).get("sections", [])
    sec = next((s for s in existing_sections if s.get("id") == section_id), None)
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "Gere apenas `tasks` para a secao solicitada, em JSON.\n"
        f"Secao alvo: {sec or section_id}\n"
        "Considere tarefas ja criadas para evitar duplicacao e aumentar dificuldade de forma gradual.\n"
        f"Tarefas existentes na secao: {list_plan_tasks(plan, section_id)}\n"
        f"Materiais do usuario (RAG):\n{_format_documents(documents)}\n"
    )
    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    resp = generate(contents=contents, schema=TASKS_ONLY_SCHEMA)
    return _load_json_response(resp)


def list_day_tasks(day: StudyDay) -> list[dict]:
    out: list[dict] = []
    for task in day.tasks.all().order_by("order"):
        meta = task.metadata or {}
        out.append(
            {
                "id": meta.get("task_schema_id"),
                "title": task.title,
                "status": task.status,
                "difficulty": meta.get("difficulty"),
            }
        )
    return out


def generate_day_payload(plan: StudyPlan, day: StudyDay, documents) -> dict:
    ctx = plan.user_context
    sections = (plan.metadata or {}).get("schema", {}).get("sections", [])
    section_id = (day.metadata or {}).get("section_id")
    section = next((s for s in sections if s.get("id") == section_id), None)
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "Gere um unico dia de estudo em JSON seguindo o schema DAY_RESPONSE_SCHEMA.\n"
        "- Preencha `day` com title/focus/target_minutes coerentes com o contexto.\n"
        "- Liste 3-5 tasks em `tasks`, mantendo ids curtos (t1, t2...) e section_id consistente.\n"
        "- Pode sugerir outline/resumo breve nas tasks, sem gerar textos longos.\n"
        "- Preserve prerequisites/dependencies quando fizer sentido.\n\n"
        f"Contexto do usuario:\n{_format_user_context(ctx)}\n"
        f"Materiais do usuario (RAG):\n{_format_documents(documents)}\n"
        f"Plano: {plan.title}\n"
        f"Dia indexado: {day.day_index}\n"
        f"Secao alvo: {section or section_id}\n"
        f"Dia atual: title='{day.title}', focus='{day.focus}', target_minutes={day.target_minutes}\n"
        f"Prerequisitos do dia: {(day.metadata or {}).get('prerequisites', [])}\n"
        f"Tarefas existentes neste dia: {list_day_tasks(day)}\n"
        f"Tarefas ja criadas na secao: {list_plan_tasks(plan, section_id)}\n"
    )
    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    resp = generate(contents=contents, schema=DAY_RESPONSE_SCHEMA)
    return _load_json_response(resp)


def list_plan_tasks(plan: StudyPlan, section_id: str) -> list[dict]:
    out: list[dict] = []
    for day in plan.days.all():
        day_section = (day.metadata or {}).get("section_id")
        if day_section != section_id:
            continue
        for task in day.tasks.all().order_by("order"):
            meta = task.metadata or {}
            out.append(
                {
                    "id": meta.get("task_schema_id"),
                    "title": task.title,
                    "status": task.status,
                    "difficulty": meta.get("difficulty"),
                }
            )
    return out


@transaction.atomic
def persist_plan_from_payload(
    user_context: StudyContext,
    payload: dict,
    title: str | None = None,
    documents=None,
    plan: StudyPlan | None = None,
) -> StudyPlan:
    sections = payload.get("plan", {}).get("sections") or []
    if plan is None:
        plan = StudyPlan.objects.create(
            user_context=user_context,
            title=title or user_context.goal,
            status="active",
            total_days=len(sections),
            metadata={"schema": payload.get("plan", {}), "raw_payload": payload},
            generation_status="succeeded",
            last_error="",
        )
    else:
        plan.title = title or plan.title or user_context.goal
        plan.status = "active"
        plan.total_days = len(sections)
        plan.metadata = {"schema": payload.get("plan", {}), "raw_payload": payload}
        plan.generation_status = "succeeded"
        plan.last_error = ""
        plan.save(
            update_fields=["title", "status", "total_days", "metadata", "generation_status", "last_error", "updated_at"]
        )
        plan.weeks.all().delete()

    if documents:
        plan.rag_documents.set(documents)

    week = _ensure_week(plan, 1, title="Week 1")
    day_map: dict[str, StudyDay] = {}
    for idx, sec in enumerate(sections, start=1):
        day = StudyDay.objects.create(
            plan=plan,
            week=week,
            day_index=idx,
            title=sec.get("title", ""),
            focus=sec.get("milestone", ""),
            status="ready",
            metadata={
                "section_id": sec.get("id"),
                "prerequisites": sec.get("prerequisites") or [],
            },
        )
        day_map[sec.get("id")] = day

    tasks = payload.get("tasks") or []
    used_orders: set[int] = set()
    for pos, task in enumerate(tasks, start=1):
        section_key = task.get("section_id")
        day = day_map.get(section_key)
        if not day:
            continue
        desired_order = _safe_int(task.get("suggested_order"), pos)
        order_value = desired_order
        while order_value in used_orders:
            order_value += 1
        used_orders.add(order_value)
        task_obj = StudyTask.objects.create(
            day=day,
            order=order_value,
            task_type=_map_task_type(task.get("type")),
            status="pending",
            title=task.get("title") or "Tarefa",
            description=task.get("description", ""),
            duration_minutes=_safe_int(task.get("estimated_time"), 0),
            resources=_extract_resources(task),
            metadata=_task_metadata(task),
        )
        _create_task_content(task_obj, task)
    return plan


@transaction.atomic
def persist_tasks_for_section(plan: StudyPlan, section_id: str, payload: dict) -> list[StudyTask]:
    tasks = payload.get("tasks") or []
    day = next((d for d in plan.days.all() if (d.metadata or {}).get("section_id") == section_id), None)
    if not day:
        day_index = (plan.days.aggregate(idx=models.Max("day_index")).get("idx") or 0) + 1
        week = plan.weeks.order_by("week_index").first() or _ensure_week(plan, 1)
        day = StudyDay.objects.create(
            plan=plan,
            week=week,
            day_index=day_index,
            title=f"Secao {section_id}",
            focus="",
            status="ready",
            metadata={"section_id": section_id},
        )
    elif not day.week:
        day.week = plan.weeks.order_by("week_index").first() or _ensure_week(plan, 1)
        day.save(update_fields=["week"])
    created: list[StudyTask] = []
    existing_titles = set(
        StudyTask.objects.filter(day__plan=plan, day__metadata__section_id=section_id).values_list("title", flat=True)
    )
    used_orders = set(
        StudyTask.objects.filter(day=day).values_list("order", flat=True)
    )
    base_order = max(used_orders) if used_orders else 0
    for pos, task in enumerate(tasks, start=1):
        if task.get("title") in existing_titles:
            continue
        desired_order = _safe_int(task.get("suggested_order"), base_order + pos)
        order_value = desired_order
        while order_value in used_orders:
            order_value += 1
        used_orders.add(order_value)
        obj = StudyTask.objects.create(
            day=day,
            order=order_value,
            task_type=_map_task_type(task.get("type")),
            status="pending",
            title=task.get("title") or "Tarefa",
            description=task.get("description", ""),
            duration_minutes=_safe_int(task.get("estimated_time"), 0),
            resources=_extract_resources(task),
            metadata=_task_metadata(task),
        )
        _create_task_content(obj, task)
        created.append(obj)
    return created


@transaction.atomic
def persist_tasks_for_day(day: StudyDay, payload: dict, reset_existing: bool = True) -> list[StudyTask]:
    tasks = payload.get("tasks") or []
    day_payload = payload.get("day") or {}
    plan = day.plan

    meta = day.metadata or {}
    meta.update(day_payload.get("metadata") or {})
    updates = []
    if day_payload.get("title"):
        day.title = day_payload["title"]
        updates.append("title")
    if day_payload.get("focus"):
        day.focus = day_payload["focus"]
        updates.append("focus")
    if day_payload.get("summary"):
        day.summary = day_payload["summary"]
        updates.append("summary")
    if day_payload.get("target_minutes") is not None:
        day.target_minutes = _safe_int(day_payload.get("target_minutes"), day.target_minutes)
        updates.append("target_minutes")
    if meta != day.metadata:
        day.metadata = meta
        updates.append("metadata")
    if not day.week:
        day.week = plan.weeks.order_by("week_index").first() or _ensure_week(plan, 1)
        updates.append("week")
    if updates:
        day.save(update_fields=updates + ["updated_at"])

    if reset_existing:
        StudyTask.objects.filter(day=day).delete()
        existing_titles = set()
        used_orders: set[int] = set()
        base_order = 0
    else:
        existing_titles = set(StudyTask.objects.filter(day=day).values_list("title", flat=True))
        used_orders = set(StudyTask.objects.filter(day=day).values_list("order", flat=True))
        base_order = max(used_orders) if used_orders else 0

    created: list[StudyTask] = []
    for pos, task in enumerate(tasks, start=1):
        if not reset_existing and task.get("title") in existing_titles:
            continue
        desired_order = _safe_int(task.get("suggested_order"), base_order + pos)
        order_value = desired_order
        while order_value in used_orders:
            order_value += 1
        used_orders.add(order_value)
        obj = StudyTask.objects.create(
            day=day,
            order=order_value,
            task_type=_map_task_type(task.get("type")),
            status="pending",
            title=task.get("title") or "Tarefa",
            description=task.get("description", ""),
            duration_minutes=_safe_int(task.get("estimated_time"), 0),
            resources=_extract_resources(task),
            metadata=_task_metadata(task),
        )
        _create_task_content(obj, task)
        created.append(obj)
    day.status = "ready"
    day.save(update_fields=["status", "updated_at"])
    return created
