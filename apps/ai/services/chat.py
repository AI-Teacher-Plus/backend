from typing import Any, Generator
import json
import logging
import time
import os
from datetime import datetime
from google.genai import types
from apps.ai.client import generate, make_tools
from apps.ai.tools.commit_user_context import function_declarations, handle_tool_call

SYSTEM = (
  "Você é um assistente de onboarding (AI Wizard) em pt-BR para Teacher Plus. "
  "Seu objetivo é coletar dados essenciais do usuário para criar seu perfil contextual (UserContext), respeitando LGPD. "
  "Siga este fluxo de perguntas de forma conversacional e natural:\n\n"
  "1. **Identificação inicial**: Pergunte 'Quem é você?' (estudante/concurseiro, professor(a), outro). "
  "   - Se estudante/concurseiro: pergunte objetivo principal (ENEM, vestibular específico, concurso, reforço em disciplina, graduação).\n"
  "   - Se professor(a): pergunte perfil de ensino (disciplinas, séries, BNCC/ENEM).\n"
  "   - Se outro: pergunte objetivo principal.\n\n"
  "2. **Prazo e intensidade**: Pergunte prazo/meta (data da prova) e intensidade de estudo semanal (dias/horas).\n\n"
  "3. **Disponibilidade e rotina**: Pergunte disponibilidade semanal, rotina de estudo e preferências (horários, dias da semana).\n\n"
  "4. **Background acadêmico**: Pergunte série/nível atual, tipo de escola (pública/privada/EJA), histórico resumido.\n\n"
  "5. **Autoavaliação**: Faça autoavaliação rápida por área (ex.: matemática, português, ciências) - 3 forças e 3 fraquezas em escala 1-5.\n\n"
  "6. **Diagnóstico**: Ofereça diagnóstico inicial adaptativo (10-15 min) ou agende para depois.\n\n"
  "7. **Interesses**: Pergunte interesses/temas favoritos para contextualizar exemplos (esporte, música, tecnologia, etc.).\n\n"
  "8. **Materiais**: Pergunte se tem materiais para anexar (PDFs, apostilas, anotações).\n\n"
  "9. **Preferências**: Formato de estudo (flashcards, vídeo, texto), idioma/variante, necessidades de acessibilidade.\n\n"
  "10. **Infraestrutura**: Dispositivo principal, conectividade, preferências de notificações (e-mail/app).\n\n"
  "11. **Consentimentos**: Explique uso de dados e materiais, peça consentimento LGPD.\n\n"
  "Valide formatos (datas, números), permita correções a qualquer momento. "
  "Quando TODOS os dados obrigatórios estiverem coletados (persona, goal, deadline, weekly_time_hours, consent_lgpd), "
  "recapitule o contexto coletado de forma clara, pergunte se confirma. "
  "Apenas se o usuário confirmar explicitamente, chame commit_user_context com os dados. "
  "Após persistência bem-sucedida, gere o primeiro plano de estudos personalizado baseado no contexto coletado, "
  "incluindo recomendações iniciais e agendamento para FSRS (repetição espaçada)."
)


STREAM_CHUNK_CHARS = int(os.getenv("AI_STREAM_CHUNK", "10"))
STREAM_DELAY_MS    = int(os.getenv("AI_STREAM_DELAY_MS", "22"))


def _chunk_text(s: str, n: int = STREAM_CHUNK_CHARS):
    for i in range(0, len(s), n):
        yield s[i:i+n]


def _make_history(messages: list[dict]) -> list[types.Content]:
    """
    messages: [{"role":"user"|"assistant"|"system","content":"..."}]
    """
    hist: list[types.Content] = [types.Content(role="user", parts=[types.Part(text=SYSTEM)])]
    role_map = {"user": "user", "assistant": "model", "system": "user"}
    for m in messages:
        role = role_map.get(m.get("role","user"), "user")
        hist.append(types.Content(role=role, parts=[types.Part(text=m.get("content",""))]))
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


def chat_once(user, messages: list[dict], session_id: str = None) -> str:
    if session_id:
        logging.info(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event": "chat_once_start",
            "messages": messages
        }))
    tools = make_tools(function_declarations())
    hist = _make_history(messages)
    if session_id:
        print(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event": "history_built",
            "system_prompt": SYSTEM,
            "history": [
                {
                    "role": c.role,
                    "parts": [{"text": p.text} for p in c.parts if hasattr(p, 'text')]
                } for c in hist
            ]
        }))
    # 1ª rodada: modelo pode propor chamadas de função
    resp = generate(contents=hist, tools=tools, stream=False, session_id=session_id)

    calls = _extract_function_calls(resp)
    if session_id:
        text = getattr(resp, "text", "")
        logging.info(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event": "initial_response",
            "text": text,
            "has_candidates": bool(getattr(resp, "candidates", None))
        }))
    while calls:
        if session_id:
            logging.info(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "event": "function_calls_detected",
                "calls": [{"name": c.name, "args": dict(c.args or {})} for c in calls]
            }))
        # Executa cada call e envia function_response de volta
        out_parts: list[types.Part] = []
        for call in calls:
            result = handle_tool_call(user, call.name, dict(call.args or {}))
            out_parts.append(types.Part.from_function_response(name=call.name, response=result))

        # Pede continuação incluindo:
        # - o conteúdo da chamada de função anterior (cand.content)
        # - as respostas de função como um novo Content(role="user")
        follow_up = [
            resp.candidates[0].content,  # conteúdo do modelo com function_call
            types.Content(role="user", parts=out_parts),
        ]
        if session_id:
            logging.info(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "event": "follow_up_prompt",
                "follow_up_summary": f"previous content + {len(out_parts)} function responses"
            }))
        resp = generate(contents=follow_up, tools=tools, stream=False, session_id=session_id)
        calls = _extract_function_calls(resp)

    # resposta final em texto
    return getattr(resp, "text", "") or ""



def chat_stream(user, messages: list[dict], session_id: str | None = None) -> Generator[dict[str, Any], None, None]:
    """
    Stream chat flow as structured events for SSE consumers.
    Each yielded item is a dict like {"event": <str>, "data": {..}}.
    """
    if session_id:
        logging.info(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event": "chat_stream_start",
            "messages": messages
        }))

    def _wrap(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = payload.copy()
        if session_id:
            data.setdefault("session_id", session_id)
        return {"event": event_type, "data": data}

    yield _wrap("meta", {"type": "session_started"})

    tools = make_tools(function_declarations())
    hist = _make_history(messages)
    if session_id:
        logging.info(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event": "stream_history_built",
            "system_prompt": SYSTEM,
            "history": [
                {
                    "role": c.role,
                    "parts": [{"text": p.text} for p in c.parts if hasattr(p, 'text')]
                } for c in hist
            ]
        }))

    resp = generate(contents=hist, tools=tools, stream=False, session_id=session_id)
    calls = _extract_function_calls(resp)
    committed = False
    context_id: str | None = None
    token_index = 0

    while calls:
        out_parts: list[types.Part] = []
        for call in calls:
            yield _wrap("heartbeat", {"stage": "tool_call", "tool": call.name})
            try:
                result = handle_tool_call(user, call.name, dict(call.args or {}))
            except Exception as exc:
                error_payload = {
                    "stage": "tool_call",
                    "tool": call.name,
                    "message": str(exc),
                }
                yield _wrap("error", error_payload)
                yield _wrap("meta", {
                    "type": "session_finished",
                    "total_tokens": token_index,
                    "committed": committed,
                    "user_context_id": context_id,
                    "error": error_payload,
                })
                return

            if call.name == "commit_user_context":
                if result.get("status") == "ok":
                    committed = True
                    context_id = result.get("user_context_id")
                    yield _wrap("meta", {
                        "type": "context_committed",
                        "user_context_id": context_id,
                    })
                else:
                    error_payload = {
                        "stage": "tool_call",
                        "tool": call.name,
                        "message": "commit_user_context returned a non-ok status",
                        "payload": result,
                    }
                    yield _wrap("error", error_payload)
                    yield _wrap("meta", {
                        "type": "session_finished",
                        "total_tokens": token_index,
                        "committed": committed,
                        "user_context_id": context_id,
                        "error": error_payload,
                    })
                    return

            out_parts.append(types.Part.from_function_response(name=call.name, response=result))

        follow_up = [
            resp.candidates[0].content,
            types.Content(role="user", parts=out_parts),
        ]
        resp = generate(contents=follow_up, tools=tools, stream=False, session_id=session_id)
        calls = _extract_function_calls(resp)

    if committed:
        plan_prompt = "Com base no contexto do usu�rio rec�m-persistido, gere um plano de estudos inicial personalizado."
        plan_contents = _make_history(messages) + [
            resp.candidates[0].content,
            types.Content(role="user", parts=[types.Part(text=plan_prompt)]),
        ]
        if session_id:
            print(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "event": "plan_prompt_assembled",
                "plan_prompt": plan_prompt,
                "plan_contents_count": len(plan_contents)
            }))
        yield _wrap("meta", {
            "type": "plan_generation_started",
            "user_context_id": context_id,
        })
        stream = generate(contents=plan_contents, stream=True, session_id=session_id)
        for chunk in stream:
            text_piece = getattr(chunk, "text", None)
            if not text_piece:
                continue
            token_index += 1
            yield _wrap("token", {
                "index": token_index,
                "stage": "study_plan",
                "text": text_piece,
            })
            if STREAM_DELAY_MS:
                time.sleep(STREAM_DELAY_MS / 1000.0)
        yield _wrap("meta", {
            "type": "plan_generation_completed",
            "user_context_id": context_id,
            "tokens_streamed": token_index,
        })
    else:
        final_text = getattr(resp, "text", "") or "Desculpe, n�o consegui gerar a mensagem."
        if session_id:
            print(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "event": "final_text_streaming",
                "final_text_length": len(final_text)
            }))
        for piece in _chunk_text(final_text):
            token_index += 1
            yield _wrap("token", {
                "index": token_index,
                "stage": "assistant_response",
                "text": piece,
            })
            if STREAM_DELAY_MS:
                time.sleep(STREAM_DELAY_MS / 1000.0)

    yield _wrap("meta", {
        "type": "session_finished",
        "total_tokens": token_index,
        "committed": committed,
        "user_context_id": context_id,
    })

