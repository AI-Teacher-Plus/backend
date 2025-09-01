from typing import Generator
from google.genai import types
from apps.ai.client import generate, make_tools
from apps.ai.tools.commit_user_context import function_declarations, handle_tool_call

SYSTEM = (
  "Você é um assistente de onboarding (AI Wizard) em pt-BR. "
  "Colete somente dados necessários (LGPD), valide formatos e permita correções. "
  "Quando os dados estiverem suficientes, chame commit_user_context."
)


def _make_history(messages: list[dict]) -> list[types.Content]:
    """
    messages: [{"role":"user"|"assistant"|"system","content":"..."}]
    """
    hist: list[types.Content] = [types.Content(role="user", parts=[types.Part.from_text(SYSTEM)])]
    role_map = {"user": "user", "assistant": "model", "system": "user"}
    for m in messages:
        role = role_map.get(m.get("role","user"), "user")
        hist.append(types.Content(role=role, parts=[types.Part.from_text(m.get("content",""))]))
    return hist


def _extract_function_calls(resp) -> list[types.FunctionCall]:
    calls = []
    for cand in getattr(resp, "candidates", []) or []:
        parts = getattr(getattr(cand, "content", None), "parts", []) or []
        for p in parts:
            fc = getattr(p, "function_call", None)
            if fc:
                calls.append(fc)
    return calls


def chat_once(user, messages: list[dict]) -> str:
    tools = make_tools(function_declarations())
    resp = generate(contents=_make_history(messages), tools=tools, stream=False)

    calls = _extract_function_calls(resp)
    while calls:
        # executa cada call e envia function_response de volta
        out_parts = []
        for call in calls:
            result = handle_tool_call(user, call.name, dict(call.args or {}))
            out_parts.append(types.Part.from_function_response(name=call.name, response=result))

        # pede continuação com as respostas de função
        resp = generate(contents=out_parts, tools=tools, stream=False)
        calls = _extract_function_calls(resp)

    # resposta final em texto
    return getattr(resp, "text", "") or ""


def chat_stream(user, messages: list[dict]) -> Generator[str, None, None]:
    """
    Streaming de texto (SSE-friendly). Por simplicidade, não streamamos a etapa de tool;
    executamos tools primeiro (se houver) e depois streamamos a continuação.
    """
    tools = make_tools(function_declarations())
    resp = generate(contents=_make_history(messages), tools=tools, stream=False)
    calls = _extract_function_calls(resp)
    while calls:
        out_parts = []
        for call in calls:
            result = handle_tool_call(user, call.name, dict(call.args or {}))
            out_parts.append(types.Part.from_function_response(name=call.name, response=result))
        resp = generate(contents=out_parts, tools=tools, stream=False)
        calls = _extract_function_calls(resp)

    # agora peça streaming do texto final
    stream = generate(contents=[types.Part.from_text("continue")], stream=True)
    for chunk in stream:
        t = getattr(chunk, "text", None)
        if t:
            yield t
