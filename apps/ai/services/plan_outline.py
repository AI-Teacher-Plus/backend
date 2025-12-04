import math
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import StudyPlan, StudyWeek, StudyContext


def _coerce_dates(study_context: StudyContext):
    today = timezone.now().date()
    start_date = study_context.start_date or today
    end_candidate = study_context.end_date or study_context.deadline
    end_date = end_candidate or start_date
    if end_date < start_date:
        end_date = start_date
    return start_date, end_date


def _week_focus(goal: str, index: int, total: int) -> str:
    goal = goal or "Estudos"
    if index == 1:
        return f"Onboarding, diagnostico e planejamento inicial para {goal}."
    if index == total:
        return f"Consolidacao e revisoes finais para {goal}."
    return f"Progresso estruturado rumo a {goal} (checkpoint {index}/{total})."


def ensure_plan_outline(study_context: StudyContext) -> StudyPlan:
    if not study_context:
        raise ValueError("StudyContext e obrigatorio para gerar o outline")

    if getattr(settings, "STUDY_PLAN_LEGACY_MODE", False):
        return _generate_legacy_plan(study_context)

    start_date, end_date = _coerce_dates(study_context)
    total_days = (end_date - start_date).days + 1
    week_count = max(1, math.ceil(total_days / 7))
    title = study_context.plan_label or study_context.goal
    summary = f"Plano base dinamico para {study_context.goal}".strip()

    with transaction.atomic():
        plan = (
            study_context.study_plans.order_by("-generated_at").select_for_update().first()
        )
        if not plan:
            plan = StudyPlan.objects.create(
                user_context=study_context,
                title=title,
                summary=summary,
                status="draft",
                start_date=start_date,
                end_date=end_date,
                total_days=total_days,
                metadata={
                    "outline": {
                        "generated_from": "study_context",
                        "week_count": week_count,
                        "last_synced_at": timezone.now().isoformat(),
                    }
                },
                generation_status="succeeded",
                last_error="",
            )
        else:
            fields_to_update: list[str] = []
            if plan.title != title:
                plan.title = title
                fields_to_update.append("title")
            if plan.summary != summary:
                plan.summary = summary
                fields_to_update.append("summary")
            if plan.start_date != start_date:
                plan.start_date = start_date
                fields_to_update.append("start_date")
            if plan.end_date != end_date:
                plan.end_date = end_date
                fields_to_update.append("end_date")
            if plan.total_days != total_days:
                plan.total_days = total_days
                fields_to_update.append("total_days")
            meta = plan.metadata or {}
            outline_meta = meta.get("outline") or {}
            if outline_meta.get("week_count") != week_count:
                meta["outline"] = {
                    "generated_from": "study_context",
                    "week_count": week_count,
                    "last_synced_at": timezone.now().isoformat(),
                }
                plan.metadata = meta
                fields_to_update.append("metadata")
            if fields_to_update:
                plan.save(update_fields=list(set(fields_to_update + ["updated_at"])))
        _sync_weeks(plan, start_date, end_date, week_count, study_context.goal)
        return plan


def _sync_weeks(plan: StudyPlan, start_date, end_date, week_count: int, goal: str):
    existing = {week.week_index: week for week in plan.weeks.all()}
    keep_ids: list[str] = []
    for idx in range(1, week_count + 1):
        week_start = start_date + timedelta(days=(idx - 1) * 7) if start_date else None
        week_end = week_start + timedelta(days=6) if week_start else None
        if week_end and end_date and week_end > end_date:
            week_end = end_date
        focus = _week_focus(goal, idx, week_count)
        week = existing.get(idx)
        if week:
            changed = False
            if week.title != f"Semana {idx}":
                week.title = f"Semana {idx}"
                changed = True
            if week.focus != focus:
                week.focus = focus
                changed = True
            if week.start_date != week_start:
                week.start_date = week_start
                changed = True
            if week.end_date != week_end:
                week.end_date = week_end
                changed = True
            if week.status == "pending" and week_start and week_start <= timezone.now().date():
                week.status = "scheduled"
                changed = True
            if changed:
                week.save(update_fields=["title", "focus", "start_date", "end_date", "status", "updated_at"])
        else:
            week = StudyWeek.objects.create(
                plan=plan,
                week_index=idx,
                title=f"Semana {idx}",
                focus=focus,
                start_date=week_start,
                end_date=week_end,
                status="scheduled" if week_start and week_start <= timezone.now().date() else "pending",
                metadata={"generated_from": "study_context"},
            )
        keep_ids.append(week.id)
    plan.weeks.exclude(id__in=keep_ids).delete()


def _generate_legacy_plan(study_context: StudyContext) -> StudyPlan:
    """
    Quando o modo legacy estiver ativo reaproveitamos o pipeline completo
    de geracao persistido em study_plan_generation, garantindo que o
    onboarding produza o mesmo tipo de plano das requisicoes manuais.
    """
    from apps.ai.models import Document
    from apps.ai.services import study_plan_generation

    documents = Document.objects.filter(owner=study_context.user)
    payload = study_plan_generation.generate_plan_payload(
        user_context=study_context,
        documents=documents,
        goal_override=None,
    )
    plan = study_context.study_plans.order_by("-generated_at").first()
    with transaction.atomic():
        return study_plan_generation.persist_plan_from_payload(
            user_context=study_context,
            payload=payload,
            title=study_context.plan_label or study_context.goal,
            documents=documents,
            plan=plan,
        )
