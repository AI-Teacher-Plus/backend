from typing import Generator
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
    committed = False
    while calls:
        out_parts = []
        for call in calls:
            result = handle_tool_call(user, call.name, dict(call.args or {}))
            if call.name == "commit_user_context" and result.get("status") == "ok":
                committed = True
            out_parts.append(types.Part.from_function_response(name=call.name, response=result))
        resp = generate(contents=out_parts, tools=tools, stream=False)
        calls = _extract_function_calls(resp)

    # se contexto foi committed, gerar plano de estudos
    if committed:
        plan_prompt = "Com base no contexto do usuário recém-persistido, gere um plano de estudos inicial personalizado."
        plan_contents = _make_history(messages) + [types.Content(role="model", parts=[types.Part.from_text(getattr(resp, "text", ""))]), types.Content(role="user", parts=[types.Part.from_text(plan_prompt)])]
        stream = generate(contents=plan_contents, stream=True)
    else:
        # agora peça streaming do texto final
        stream = generate(contents=[types.Part.from_text("continue")], stream=True)

    for chunk in stream:
        t = getattr(chunk, "text", None)
        if t:
            yield t
