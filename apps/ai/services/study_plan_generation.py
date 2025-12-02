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
                            "theme": {"type": "string"},
                            "milestone": {"type": "string"},
                            "success_metrics": {"type": "array", "items": {"type": "string"}},
                            "release_criteria": {"type": "array", "items": {"type": "string"}},
                            "focus_questions": {"type": "array", "items": {"type": "string"}},
                            "recommended_materials": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"},
                                        "type": {"type": "string"},
                                        "url": {"type": "string"},
                                        "notes": {"type": "string"},
                                    },
                                    "required": ["title"],
                                },
                            },
                            "suggested_day_count": {"type": "integer"},
                            "prerequisites": {"type": "array", "items": {"type": "string"}},
                            "checkpoint_prompt": {"type": "string"},
                        },
                        "required": ["id", "title", "milestone"],
                    },
                },
                "global_guidelines": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["sections"],
        }
    },
    "required": ["plan"],
}


DAY_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "section_id": {"type": "string"},
        "type": {
            "type": "string",
            "enum": ["flashcards", "quiz", "lecture", "summary", "project", "external_resource", "practice", "review"],
        },
        "title": {"type": "string"},
        "description": {"type": "string"},
        "estimated_time": {"type": "integer"},
        "difficulty": {"type": "integer"},
        "suggested_order": {"type": "integer"},
        "research_needed": {"type": "boolean"},
        "prerequisites": {"type": "array", "items": {"type": "string"}},
        "dependencies": {"type": "array", "items": {"type": "string"}},
        "assessment_target": {"type": "string"},
        "content": {
            "type": "object",
            "properties": {
                "summary_markdown": {"type": "string"},
                "body_markdown": {"type": "string"},
                "takeaways": {"type": "array", "items": {"type": "string"}},
                "cards": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "front": {"type": "string"},
                            "back": {"type": "string"},
                            "hint": {"type": "string"},
                        },
                        "required": ["front", "back"],
                    },
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["mcq", "tf"]},
                            "question": {"type": "string"},
                            "choices": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {"label": {"type": "string"}, "text": {"type": "string"}},
                                    "required": ["label", "text"],
                                },
                                "minItems": 2,
                            },
                            "answer": {"type": "string"},
                            "explanation": {"type": "string"},
                        },
                        "required": ["type", "question", "choices", "answer"],
                    },
                },
                "resources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "how_to_use": {"type": "string"},
                            "fallback_if_unavailable": {"type": "string"},
                        },
                        "required": ["title"],
                    },
                },
            },
        },
    },
    "required": ["id", "section_id", "type", "title"],
}


TASKS_ONLY_SCHEMA = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": DAY_TASK_SCHEMA,
        },
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
        "tasks": TASKS_ONLY_SCHEMA["properties"]["tasks"],
    },
    "required": ["day", "tasks"],
}


SYSTEM_PROMPT = """
Voce e um planejador de estudos em pt-BR que trabalha em duas etapas:
- Etapa OUTLINE: gerar apenas o esqueleto semanal/por seções do plano (sem dias, sem tarefas detalhadas). Foque em milestones, critérios de sucesso, perguntas-guia e materiais recomendados.
- Etapa DIA: quando solicitado, gere um unico dia com tarefas completas (conteudo em Markdown, flashcards com frente/verso, quizzes de multipla escolha etc.).
Sempre produza JSON estrito conforme o schema informado para cada etapa e reuse ids consistentes entre outline e dias.
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
            summary=content.get("summary_markdown") or content.get("summary") or task.description,
            body=content.get("body_markdown") or content.get("body") or content.get("text") or "",
            key_points=content.get("key_points") or content.get("takeaways") or [],
            source_refs=content.get("source_refs") or [],
        )
    elif raw_type in {"reading", "external_resource"}:
        resources = content.get("resources")
        if not resources and (content.get("url") or content.get("title")):
            resources = [content]
        ReadingContent.objects.create(
            task=task,
            overview=content.get("rationale") or content.get("overview") or content.get("summary_markdown") or task.description,
            instructions=content.get("how_to_use") or content.get("instructions_markdown") or "",
            resources=resources or [],
            generated_text=content.get("body_markdown") or content.get("summary_markdown") or "",
        )
    elif raw_type == "practice":
        PracticeContent.objects.create(
            task=task,
            prompt=content.get("prompt_markdown") or content.get("prompt") or task.description or task.title,
            expected_output=content.get("expected_output") or "",
            rubric=content.get("rubric") or {},
            hints=content.get("hints") or [],
        )
    elif raw_type == "project":
        ProjectContent.objects.create(
            task=task,
            brief=content.get("brief") or content.get("brief_markdown") or task.description or task.title,
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
            strategy=content.get("strategy_markdown") or content.get("strategy") or content.get("instructions") or "",
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
        "ETAPA: OUTLINE\n"
        "Regras de formato:\n"
        "- Responda apenas com JSON seguindo o schema definido para `plan` (nao existe campo `tasks`).\n"
        "- ids devem ser curtos e estaveis (ex.: s1, s2...).\n"
        "- Cada secao representa uma semana ou macrofase com milestone claro, criterios de sucesso e perguntas-guia.\n"
        "- Liste materiais recomendados com instrucoes de uso, mas nao gere nenhum dia nem tarefa detalhada.\n"
        "- Use `suggested_day_count` para indicar quantos dias aquela secao deve consumir (sera usado para geracoes futuras).\n\n"
        f"Contexto do usuario:\n{_format_user_context(user_context)}\n"
        f"Objetivo atual: {goal_line}\n"
        f"Materiais do usuario (RAG):\n{_format_documents(documents)}\n"
        "Gere 4-6 secoes (weeks) com milestones claros, criterios de liberacao, checkpoints e perguntas para refletir antes de liberar a proxima secao.\n"
        "Pode sugerir materiais externos, mas mantenha apenas o outline; os dias recebidos pelo usuario serao gerados posteriormente sob demanda.\n"
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
        "ETAPA: DIA/PREVIEW\n"
        "Gere apenas `tasks` para a secao solicitada em JSON seguindo o schema DAY_TASK_SCHEMA.\n"
        "- Inclua 3-5 tarefas variadas (quiz MCQ, flashcards com frente/verso, aulas/resumos em Markdown, praticas com passo a passo).\n"
        "- Quizes devem ser multipla escolha com opcoes (label + texto) e indicar a resposta correta e explicacao.\n"
        "- Flashcards precisam de `front` e `back` completos e, se possivel, `hint`.\n"
        "- Lesson/practice/review devem trazer `summary_markdown` e `body_markdown` com conteudo pronto para renderizacao.\n"
        "- Utilize materiais do usuario quando fizer sentido e cite-os em `resources`.\n\n"
        f"Secao alvo: {json.dumps(sec, ensure_ascii=False) if sec else section_id}\n"
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
        "ETAPA: DIA\n"
        "Gere um unico dia de estudo em JSON seguindo DAY_RESPONSE_SCHEMA.\n"
        "- Preencha `day` com title/focus/target_minutes coerentes com progresso e outline.\n"
        "- Liste 3-5 tasks completas; ids curtos (t1, t2...) e `section_id` igual ao da secao.\n"
        "- Para lições/resumos/praticas, escreva `summary_markdown` e `body_markdown` ricos (com listas, subtitulos, exemplos).\n"
        "- Flashcards DEVEM possuir frente/verso e, se possivel, dica.\n"
        "- Quizzes DEVEM ser multipla escolha (choices com label A/B/C... e texto) e incluir resposta + explicacao.\n"
        "- Inclua recursos externos apenas quando fizer sentido, com `how_to_use` em Markdown.\n"
        "- Preserve prerequisites/dependencies quando fizer sentido e use historico do dia/secao.\n\n"
        f"Contexto do usuario:\n{_format_user_context(ctx)}\n"
        f"Materiais do usuario (RAG):\n{_format_documents(documents)}\n"
        f"Plano: {plan.title}\n"
        f"Dia indexado: {day.day_index}\n"
        f"Secao alvo: {section or section_id}\n"
        f"Metas da secao: {(section or {}).get('success_metrics')}\n"
        f"Criterios de liberacao: {(section or {}).get('release_criteria')}\n"
        f"Perguntas-guia: {(section or {}).get('focus_questions')}\n"
        f"Materiais recomendados desta secao: {(section or {}).get('recommended_materials')}\n"
        f"Dia atual: title='{day.title}', focus='{day.focus}', target_minutes={day.target_minutes}\n"
        f"Prerequisitos do dia: {(day.metadata or {}).get('prerequisites', [])}\n"
        f"Historico recente do aluno nessa secao: {(day.metadata or {}).get('last_result')}\n"
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
    total_outline_days = sum(max(1, _safe_int(sec.get("suggested_day_count"), 1)) for sec in sections) or len(sections) or 1
    if plan is None:
        plan = StudyPlan.objects.create(
            user_context=user_context,
            title=title or user_context.goal,
            status="active",
            total_days=total_outline_days,
            metadata={"schema": payload.get("plan", {}), "raw_payload": payload},
            generation_status="succeeded",
            last_error="",
        )
    else:
        plan.title = title or plan.title or user_context.goal
        plan.status = "active"
        plan.total_days = total_outline_days
        plan.metadata = {"schema": payload.get("plan", {}), "raw_payload": payload}
        plan.generation_status = "succeeded"
        plan.last_error = ""
        plan.save(
            update_fields=["title", "status", "total_days", "metadata", "generation_status", "last_error", "updated_at"]
        )
        plan.weeks.all().delete()

    if documents:
        plan.rag_documents.set(documents)

    for idx, sec in enumerate(sections, start=1):
        week = _ensure_week(plan, idx, title=f"Week {idx}")
        sec_id = sec.get("id")
        default_minutes = max(
            45,
            int(
                ((user_context.weekly_time_hours or 5) * 60)
                / max(total_outline_days, 1)
            ),
        )
        day = StudyDay.objects.create(
            plan=plan,
            week=week,
            day_index=idx,
            title=sec.get("title", ""),
            focus=sec.get("milestone", ""),
            status="pending",
            target_minutes=_safe_int(sec.get("target_minutes"), default_minutes),
            metadata={
                "section_id": sec_id,
                "prerequisites": sec.get("prerequisites") or [],
                "success_metrics": sec.get("success_metrics") or [],
                "release_criteria": sec.get("release_criteria") or [],
                "focus_questions": sec.get("focus_questions") or [],
                "recommended_materials": sec.get("recommended_materials") or [],
                "checkpoint_prompt": sec.get("checkpoint_prompt"),
                "suggested_day_count": sec.get("suggested_day_count"),
            },
        )
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
        existing_orders = set()
    else:
        if not day.week:
            day.week = plan.weeks.order_by("week_index").first() or _ensure_week(plan, 1)
            day.save(update_fields=["week"])
        existing_orders = set(day.tasks.values_list("order", flat=True))

    created: list[StudyTask] = []
    existing_titles = set(
        StudyTask.objects.filter(day__plan=plan, day__metadata__section_id=section_id).values_list("title", flat=True)
    )
    used_orders = set(existing_orders)
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
    if created:
        day.status = "ready"
        day.save(update_fields=["status", "updated_at"])
    return created


@transaction.atomic
def persist_tasks_for_day(day: StudyDay, payload: dict, reset_existing: bool = True) -> list[StudyTask]:
    tasks = payload.get("tasks") or []
    day_payload = payload.get("day") or {}
    plan = day.plan

    # Atualiza metadados do dia sem perder referencias existentes.
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
