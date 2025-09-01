from google.genai import types
from apps.accounts.serializers import UserContextSerializer


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
  "required": ["persona", "goal", "deadline", "weekly_time_hours", "consent_lgpd"],
  "additionalProperties": True
}


def function_declarations() -> list[types.FunctionDeclaration]:
    return [
        types.FunctionDeclaration(
            name="commit_user_context",
            description="Cria/atualiza o contexto do usuário autenticado.",
            parameters=USER_CONTEXT_SCHEMA
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
