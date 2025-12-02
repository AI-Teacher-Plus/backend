import json
import re
from datetime import timedelta

from django.utils import timezone
from google.genai import types

from apps.accounts.serializers import StudyContextSerializer
from apps.ai.services.plan_outline import ensure_plan_outline
from collections.abc import Mapping


# --- Sanitização para schemas de tools ---
_DROP_KEYS = {
    "additionalProperties", "additional_properties",
    "$schema", "patternProperties", "unevaluatedProperties", "strict",
    "format", "minimum", "maximum", "minLength", "maxLength", "pattern",
}

def _sanitize_schema_dict(d: Mapping) -> dict:
    out = {}
    for k, v in d.items():
        if k in _DROP_KEYS:
            continue
        if isinstance(v, Mapping):
            out[k] = _sanitize_schema_dict(v)
        elif isinstance(v, list):
            out[k] = [
                _sanitize_schema_dict(x) if isinstance(x, Mapping) else x
                for x in v
            ]
        else:
            out[k] = v
    return out

def _schema_from_dict(d: Mapping) -> types.Schema:
    d = _sanitize_schema_dict(d)
    t = d.get("type") or d.get("Type") or d.get("TYPE")
    if isinstance(t, str):
        t = t.upper()
    props = {
        k: _schema_from_dict(v) if isinstance(v, Mapping) else v
        for k, v in (d.get("properties") or {}).items()
    }
    items = d.get("items")
    if isinstance(items, Mapping):
        items = _schema_from_dict(items)
    return types.Schema(
        type=t,
        description=d.get("description"),
        enum=d.get("enum"),
        properties=props or None,
        items=items,
        required=d.get("required"),
    )


# JSON Schema mínimo do StudyContext
STUDY_CONTEXT_SCHEMA = {
  "type": "object",
  "properties": {
    "persona": {"type": "string", "enum": ["student", "teacher", "other"]},
    "goal": {"type": "string"},
    "deadline": {"type": "string", "format": "date"},
    "plan_label": {"type": "string"},
    "start_date": {"type": "string", "format": "date"},
    "end_date": {"type": "string", "format": "date"},
    "weekly_time_hours": {"type": "integer", "minimum": 0},
    "study_routine": {"type": "string"},
    "background_level": {"type": "string"},
    "background_institution_type": {"type": "string"},
    "self_assessment": {"type": "object"},
    "diagnostic_status": {"type": "string"},
    "diagnostic_snapshot": {"type": "array", "items": {"type": "string"}},
    "interests": {"type": "array", "items": {"type": "string"}},
    "preferences_formats": {"type": "array", "items": {"type": "string"}},
    "preferences_language": {"type": "string"},
    "preferences_accessibility": {"type": "array", "items": {"type": "string"}},
    "tech_device": {"type": "string"},
    "tech_connectivity": {"type": "string"},
    "notifications": {"type": "string"},
    "consent_lgpd": {"type": "boolean"}
  },
  "required": ["persona", "goal", "deadline", "weekly_time_hours", "consent_lgpd"]
}


_TOOL_NAMES = ("commit_study_context", "commit_user_context")


def function_declarations() -> list[types.FunctionDeclaration]:
    return [
        types.FunctionDeclaration(
            name=tool_name,
            description="Cria/atualiza o contexto do usuário autenticado.",
            parameters=_schema_from_dict(STUDY_CONTEXT_SCHEMA),
        )
        for tool_name in _TOOL_NAMES
    ]


_BOOL_TRUE = {"true", "yes", "sim", "1"}


def _extract_int(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+", value)
        if match:
            return int(match.group(0))
    return None


def _normalize_deadline(value: str | None) -> str | None:
    if not value:
        return value
    if isinstance(value, str):
        value = value.strip()
        # Already ISO-8601 YYYY-MM-DD
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value
        # Try to capture numeric duration in days
        days = _extract_int(value)
        if days is not None and days >= 0:
            target = timezone.now().date() + timedelta(days=days)
            return target.isoformat()
    return value


def _normalize_weekly_hours(value):
    if isinstance(value, int):
        return value
    hours = _extract_int(value)
    return hours if hours is not None and hours >= 0 else value


def _normalize_consent(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in _BOOL_TRUE
    return bool(value)


def _normalize_args(args: dict) -> dict:
    normalized = dict(args or {})
    for date_field in ("deadline", "start_date", "end_date"):
        if date_field in normalized:
            normalized[date_field] = _normalize_deadline(normalized.get(date_field))
    if "weekly_time_hours" in normalized:
        normalized["weekly_time_hours"] = _normalize_weekly_hours(normalized.get("weekly_time_hours"))
    if "consent_lgpd" in normalized:
        normalized["consent_lgpd"] = _normalize_consent(normalized.get("consent_lgpd"))
    return normalized


def handle_tool_call(user, name: str, args: dict) -> dict:
    if name not in _TOOL_NAMES:
        return {"status": "error", "message": f"Unknown tool {name}"}

    normalized_args = _normalize_args(args)
    print(json.dumps({
        "event": "commit_user_context_payload",
        "normalized": normalized_args,
    }))
    instance = getattr(user, "study_context", None)
    ser = StudyContextSerializer(instance=instance, data=normalized_args, partial=True)
    ser.is_valid(raise_exception=True)
    obj = ser.save(user=user)
    ensure_plan_outline(obj)
    return {
        "status": "ok",
        "study_context_id": str(obj.id),
        "user_context_id": str(obj.id),
    }
