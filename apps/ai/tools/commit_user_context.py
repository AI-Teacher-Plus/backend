from google.genai import types
from apps.accounts.serializers import UserContextSerializer
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


# JSON Schema mínimo do UserContext
USER_CONTEXT_SCHEMA = {
  "type": "object",
  "properties": {
    "persona": {"type": "string", "enum": ["student", "teacher", "other"]},
    "goal": {"type": "string"},
    "deadline": {"type": "string", "format": "date"},
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


def function_declarations() -> list[types.FunctionDeclaration]:
    return [
        types.FunctionDeclaration(
            name="commit_user_context",
            description="Cria/atualiza o contexto do usuário autenticado.",
            parameters=_schema_from_dict(USER_CONTEXT_SCHEMA)
        )
    ]


def handle_tool_call(user, name: str, args: dict) -> dict:
    if name != "commit_user_context":
        return {"status": "error", "message": f"Unknown tool {name}"}

    instance = getattr(user, "context", None)
    ser = UserContextSerializer(instance=instance, data=args, partial=True)
    ser.is_valid(raise_exception=True)
    obj = ser.save(user=user)
    return {"status": "ok", "user_context_id": str(obj.id)}
